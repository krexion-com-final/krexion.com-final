"""
AI Automation Generator — uses Gemini 2.5 Pro (via Emergent LLM Key) to:

1. Analyse user-uploaded screenshots / video demonstrating a form-fill flow
   and produce a structured JSON step-list compatible with
   `real_user_traffic._execute_automation_steps`.

2. At runtime, when the Playwright bot encounters an unexpected page
   (cookie banner, interstitial, "are you sure?" popup, consent modal),
   take a screenshot and ask Gemini for the single next best action to
   dismiss/continue, so the main automation can keep going.

Actions the model is constrained to output (must match the executor
in real_user_traffic.py):

    goto, click, fill, type, select, check, uncheck, press, wait,
    wait_for_selector, wait_for_navigation, scroll, screenshot, evaluate

Placeholders in values:
    {{first}} {{last}} {{email}} {{day}} {{month}} {{year}} ...
    {{random.N}} {{randomletters.N}}
"""
from __future__ import annotations

import json
import logging
import os
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ── Supported media ──────────────────────────────────────────────────
IMAGE_MIMES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}
VIDEO_MIMES = {
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".webm": "video/webm",
    ".mpeg": "video/mpeg",
    ".avi": "video/x-msvideo",
}

MAX_IMAGES = 15
MAX_VIDEO_BYTES = 40 * 1024 * 1024  # 40 MB soft limit

# ── Model / key ──────────────────────────────────────────────────────
GEMINI_MODEL = "gemini-2.5-pro"

# 2026-06 — Per-user multi-provider AI integration (Roman Urdu user ask:
# "Visual recorder mein AI integration ka option ho... har user apna AI
# integration apne account mein alehda se kre... emergent wala llm,
# chatgpt, gemini, claude... ta k company ko kharcha na pare").
#
# We support FOUR providers. The choice + key lives on the user document
# (`ai_provider`, `gemini_api_key`, `openai_api_key`, `anthropic_api_key`).
# When the user picks "emergent" we still fall back to the platform's
# universal key — useful for new accounts who haven't set up their own
# key yet.
PROVIDER_EMERGENT = "emergent"
PROVIDER_GEMINI = "gemini"
PROVIDER_OPENAI = "openai"
PROVIDER_CLAUDE = "claude"
SUPPORTED_PROVIDERS = {PROVIDER_EMERGENT, PROVIDER_GEMINI, PROVIDER_OPENAI, PROVIDER_CLAUDE}

# Default models per provider — chosen for "best JSON generation quality
# vs cost" balance. Users can override via env var if they need a smaller/
# bigger model.
OPENAI_MODEL = os.environ.get("AI_OPENAI_MODEL", "gpt-4o")
CLAUDE_MODEL = os.environ.get("AI_CLAUDE_MODEL", "claude-sonnet-4-5-20250929")
GEMINI_USER_MODEL = os.environ.get("AI_GEMINI_USER_MODEL", "gemini-2.5-pro")


def _emergent_key() -> str:
    k = os.environ.get("EMERGENT_LLM_KEY")
    if not k:
        raise RuntimeError("EMERGENT_LLM_KEY is not configured")
    return k


def _resolve_provider_and_key(user_doc: Optional[Dict[str, Any]]) -> tuple:
    """Return (provider, api_key) tuple for this user. If user has no
    AI settings configured we fall back to the platform Emergent key so
    the existing UX (zero-config AI on a fresh install) keeps working.

    Returns ("provider_name", "api_key_string") OR raises RuntimeError
    when the chosen provider has no key configured and Emergent fallback
    is unavailable.
    """
    user_doc = user_doc or {}
    chosen = (user_doc.get("ai_provider") or "").strip().lower()
    if chosen not in SUPPORTED_PROVIDERS:
        chosen = ""  # blank → auto-pick

    # Explicit picks
    if chosen == PROVIDER_GEMINI:
        k = (user_doc.get("gemini_api_key") or "").strip()
        if k:
            return PROVIDER_GEMINI, k
    if chosen == PROVIDER_OPENAI:
        k = (user_doc.get("openai_api_key") or "").strip()
        if k:
            return PROVIDER_OPENAI, k
    if chosen == PROVIDER_CLAUDE:
        k = (user_doc.get("anthropic_api_key") or "").strip()
        if k:
            return PROVIDER_CLAUDE, k
    if chosen == PROVIDER_EMERGENT:
        # 2026-06 — User can save their OWN Emergent universal key
        # (sk-emergent-...) in settings to use their personal subscription
        # instead of the Krexion-platform key. Falls back to platform
        # key if the user hasn't saved one.
        own = (user_doc.get("emergent_api_key") or "").strip()
        if own:
            return PROVIDER_EMERGENT, own
        return PROVIDER_EMERGENT, _emergent_key()

    # No explicit choice OR chosen provider has no key — fall back to
    # FIRST configured user key, else Emergent platform key.
    for prov, field in (
        (PROVIDER_GEMINI, "gemini_api_key"),
        (PROVIDER_OPENAI, "openai_api_key"),
        (PROVIDER_CLAUDE, "anthropic_api_key"),
        (PROVIDER_EMERGENT, "emergent_api_key"),
    ):
        k = (user_doc.get(field) or "").strip()
        if k:
            return prov, k
    return PROVIDER_EMERGENT, _emergent_key()


# ── Prompt builders ──────────────────────────────────────────────────
ALLOWED_ACTIONS_DOC = """
Allowed actions (use ONLY these):
- goto           {"action":"goto","value":"https://..."}
- click          {"action":"click","selector":"CSS","wait_nav":true,"optional":true}
- fill           {"action":"fill","selector":"CSS","value":"{{first}}"}
- type           {"action":"type","selector":"CSS","value":"{{email}}","delay":50}
- select         {"action":"select","selector":"select[name='state']","value":"{{state}}"}
- check          {"action":"check","selector":"input[type=checkbox]"}
- uncheck        {"action":"uncheck","selector":"input[type=checkbox]"}
- press          {"action":"press","selector":"body","value":"Enter"}
- wait           {"action":"wait","ms":1500}
- wait_for_selector {"action":"wait_for_selector","selector":"CSS","timeout":20000}
- wait_for_load  {"action":"wait_for_load","timeout":20000}
- scroll         {"action":"scroll","y":500}
- evaluate       {"action":"evaluate","script":"document.querySelector('X').click()"}

Placeholders you may use inside "value":
  {{first}} {{last}} {{email}} {{address}} {{city}} {{state}} {{zip}}
  {{cellphone}} {{phone}} {{day}} {{month}} {{year}}
  {{random.N}}  {{randomletters.N}}
(Any column name from the user's Excel can be referenced the same way.)

Rules:
- Return a JSON ARRAY of step objects only. No prose. No markdown fences.
- Use robust CSS selectors. Prefer name attribute and :has-text() fallbacks.
- Mark any step that may not exist on every render with "optional": true.
- Add a `wait_for_load` / small `wait` after navigation-causing clicks.
- End with a final wait of 5000-7000 ms so the page settles before screenshot.
- If you see a cookie / consent popup in the screenshots, add an optional click
  step for it BEFORE the main CTA.
"""


def _build_system_prompt() -> str:
    return (
        "You are an expert browser-automation engineer. Your job is to look at "
        "screenshots or a video of a human completing a web form, and produce "
        "a JSON step-list that a Playwright bot can execute to reproduce the "
        "same flow for many leads. Output ONLY valid JSON — no markdown, no "
        "explanation, no comments.\n\n"
        + ALLOWED_ACTIONS_DOC
    )


def _build_user_prompt(target_url: Optional[str],
                       description: Optional[str],
                       excel_columns: Optional[List[str]]) -> str:
    bits: List[str] = []
    bits.append("Generate an automation JSON step-list for this website.")
    if target_url:
        bits.append(f"Target URL: {target_url}")
    if excel_columns:
        bits.append(
            "Excel/CSV lead columns available (use these EXACT names in placeholders): "
            + ", ".join(excel_columns)
        )
    if description:
        bits.append(f"User description of the flow:\n{description.strip()}")
    bits.append(
        "Use the attached screenshots/video to infer: which buttons to click, "
        "which form fields exist, their order, dropdowns vs text inputs, and "
        "any consent/cookie banners that appear."
    )
    bits.append("Return JSON array only.")
    return "\n\n".join(bits)


# ── Core generator ───────────────────────────────────────────────────
async def generate_automation_from_media(
    image_paths: Optional[List[str]] = None,
    video_path: Optional[str] = None,
    target_url: Optional[str] = None,
    description: Optional[str] = None,
    excel_columns: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Send the media + prompt to Gemini 2.5 Pro and return:
        {"status":"ok", "steps":[...], "raw": "<model text>"}
    or {"status":"failed", "error":"..."}
    """
    from emergentintegrations.llm.chat import (
        LlmChat,
        UserMessage,
        FileContentWithMimeType,
    )

    image_paths = image_paths or []
    if not image_paths and not video_path:
        return {"status": "failed", "error": "No images or video provided"}

    file_contents: List[Any] = []

    # Attach video (up to 1 per call)
    if video_path:
        vp = Path(video_path)
        if not vp.exists():
            return {"status": "failed", "error": f"Video not found: {video_path}"}
        mime = VIDEO_MIMES.get(vp.suffix.lower(), "video/mp4")
        file_contents.append(FileContentWithMimeType(
            file_path=str(vp),
            mime_type=mime,
        ))

    # Attach images (capped)
    for p in image_paths[:MAX_IMAGES]:
        ip = Path(p)
        if not ip.exists():
            continue
        mime = IMAGE_MIMES.get(ip.suffix.lower(), "image/png")
        file_contents.append(FileContentWithMimeType(
            file_path=str(ip),
            mime_type=mime,
        ))

    if not file_contents:
        return {"status": "failed", "error": "No readable media files"}

    try:
        chat = LlmChat(
            api_key=_emergent_key(),
            session_id=f"ai-automation-{uuid.uuid4().hex[:10]}",
            system_message=_build_system_prompt(),
        ).with_model("gemini", GEMINI_MODEL)

        msg = UserMessage(
            text=_build_user_prompt(target_url, description, excel_columns),
            file_contents=file_contents,
        )
        raw = await chat.send_message(msg)
    except Exception as e:
        logger.exception("Gemini call failed")
        return {"status": "failed", "error": f"AI call failed: {str(e)[:300]}"}

    steps = _parse_steps_from_response(raw)
    if steps is None:
        return {"status": "failed", "error": "Could not parse JSON from model output",
                "raw": raw[:2000] if isinstance(raw, str) else str(raw)[:2000]}

    steps = _sanitize_steps(steps)
    return {"status": "ok", "steps": steps, "raw": raw if isinstance(raw, str) else str(raw)}


# ── Runtime self-healing ─────────────────────────────────────────────
SELF_HEAL_SYSTEM = (
    "You are assisting a running Playwright automation. You will be shown a "
    "screenshot of an UNEXPECTED page/popup that blocked the main automation. "
    "Return ONLY a JSON object with the single next best action to dismiss or "
    "continue past this obstacle, using one of these actions: click, check, "
    "uncheck, press, scroll, wait, evaluate. Include an `optional: true` flag. "
    "Example: {\"action\":\"click\",\"selector\":\"button:has-text('Accept')\","
    "\"optional\":true}. If no safe action can dismiss it, return "
    "{\"action\":\"wait\",\"ms\":1000,\"optional\":true}. Output JSON only."
)


async def suggest_self_heal_action(
    screenshot_path: str,
    page_title: Optional[str] = None,
    page_url: Optional[str] = None,
    failed_step: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Ask Gemini to propose a single recovery action. Returns dict or None."""
    from emergentintegrations.llm.chat import (
        LlmChat,
        UserMessage,
        FileContentWithMimeType,
    )

    sp = Path(screenshot_path)
    if not sp.exists():
        return None
    mime = IMAGE_MIMES.get(sp.suffix.lower(), "image/png")

    ctx: List[str] = ["Automation is stuck. Propose one recovery action."]
    if page_url:
        ctx.append(f"Current URL: {page_url}")
    if page_title:
        ctx.append(f"Page title: {page_title}")
    if failed_step:
        try:
            ctx.append(f"Failed step: {json.dumps(failed_step)[:300]}")
        except Exception:
            pass

    try:
        chat = LlmChat(
            api_key=_emergent_key(),
            session_id=f"ai-self-heal-{uuid.uuid4().hex[:10]}",
            system_message=SELF_HEAL_SYSTEM,
        ).with_model("gemini", GEMINI_MODEL)
        raw = await chat.send_message(UserMessage(
            text="\n".join(ctx),
            file_contents=[FileContentWithMimeType(
                file_path=str(sp), mime_type=mime,
            )],
        ))
    except Exception as e:
        logger.warning(f"self-heal AI call failed: {e}")
        return None

    obj = _parse_single_json_object(raw)
    if not isinstance(obj, dict) or "action" not in obj:
        return None
    obj.setdefault("optional", True)
    return obj


# ── Parsing helpers ──────────────────────────────────────────────────
def _strip_code_fences(text: str) -> str:
    t = text.strip()
    # ```json ... ``` or ``` ... ```
    m = re.match(r"^```(?:json)?\s*(.*?)```\s*$", t, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return t


def _parse_steps_from_response(raw: Any) -> Optional[List[Dict[str, Any]]]:
    if not isinstance(raw, str):
        return None
    cleaned = _strip_code_fences(raw)

    # Try direct JSON
    try:
        data = json.loads(cleaned)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "steps" in data and isinstance(data["steps"], list):
            return data["steps"]
    except Exception:
        pass

    # Fallback: find the first [...] block in the text
    m = re.search(r"\[[\s\S]*\]", cleaned)
    if m:
        try:
            data = json.loads(m.group(0))
            if isinstance(data, list):
                return data
        except Exception:
            return None
    return None


def _parse_single_json_object(raw: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(raw, str):
        return None
    cleaned = _strip_code_fences(raw)
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    m = re.search(r"\{[\s\S]*\}", cleaned)
    if m:
        try:
            data = json.loads(m.group(0))
            if isinstance(data, dict):
                return data
        except Exception:
            return None
    return None


_ALLOWED_ACTIONS = {
    "goto", "click", "fill", "type", "select", "check", "uncheck", "press",
    "wait", "wait_for_selector", "wait_for_navigation", "wait_for_load",
    "wait_for_networkidle", "scroll", "screenshot", "evaluate",
}


def _sanitize_steps(steps: List[Any]) -> List[Dict[str, Any]]:
    """Drop malformed / unknown-action entries. Keep only supported steps."""
    out: List[Dict[str, Any]] = []
    for s in steps:
        if not isinstance(s, dict):
            continue
        action = str(s.get("action", "")).strip().lower()
        if action not in _ALLOWED_ACTIONS:
            continue
        clean: Dict[str, Any] = {"action": action}
        for k in ("selector", "value", "script", "state", "name"):
            if k in s and s[k] is not None:
                clean[k] = s[k]
        for k in ("ms", "timeout", "delay", "y"):
            if k in s:
                try:
                    clean[k] = int(s[k])
                except Exception:
                    pass
        for k in ("wait_nav", "optional"):
            if k in s:
                clean[k] = bool(s[k])
        out.append(clean)
    return out


# ── Validation helpers for the HTTP layer ────────────────────────────
def classify_upload(filename: str) -> Optional[str]:
    """Return 'image' | 'video' | None."""
    ext = Path(filename).suffix.lower()
    if ext in IMAGE_MIMES:
        return "image"
    if ext in VIDEO_MIMES:
        return "video"
    return None



# ─────────────────────────────────────────────────────────────────────
# 2026-06 — Multi-provider generator (Gemini direct, OpenAI direct,
# Claude direct, Emergent universal). Mirrors the LlmChat-based
# `generate_automation_from_media` above but routes each provider via
# its OWN SDK / REST endpoint using the user's stored key, so we never
# burn the company's Emergent quota when the user has their own key.
# ─────────────────────────────────────────────────────────────────────


def _load_image_b64(path: str) -> Optional[tuple]:
    """Read image file → (base64_str, mime_type). None on failure."""
    p = Path(path)
    if not p.exists():
        return None
    try:
        import base64 as _b64
        data = p.read_bytes()
        mime = IMAGE_MIMES.get(p.suffix.lower(), "image/png")
        return _b64.b64encode(data).decode("ascii"), mime
    except Exception as e:
        logger.debug(f"image read err {path}: {e}")
        return None


async def _generate_gemini_direct(
    api_key: str,
    image_paths: List[str],
    video_path: Optional[str],
    sys_prompt: str,
    user_prompt: str,
) -> str:
    """Call Gemini directly with user's AIza key via google-genai SDK."""
    import asyncio as _asyncio
    try:
        from google import genai as _genai
        from google.genai import types as _gtypes
    except ImportError as e:
        raise RuntimeError(f"google-genai not installed: {e}")

    parts: List[Any] = []
    for ip in image_paths[:MAX_IMAGES]:
        loaded = _load_image_b64(ip)
        if not loaded:
            continue
        b64, mime = loaded
        import base64 as _b64
        parts.append(_gtypes.Part.from_bytes(
            data=_b64.b64decode(b64), mime_type=mime,
        ))
    if video_path and Path(video_path).exists():
        vp = Path(video_path)
        mime = VIDEO_MIMES.get(vp.suffix.lower(), "video/mp4")
        try:
            parts.append(_gtypes.Part.from_bytes(
                data=vp.read_bytes(), mime_type=mime,
            ))
        except Exception as e:
            logger.warning(f"gemini video read failed: {e}")
    parts.append(_gtypes.Part.from_text(text=user_prompt))

    def _sync_call() -> str:
        client = _genai.Client(api_key=api_key)
        resp = client.models.generate_content(
            model=GEMINI_USER_MODEL,
            contents=[_gtypes.Content(role="user", parts=parts)],
            config=_gtypes.GenerateContentConfig(
                system_instruction=sys_prompt,
                temperature=0.4,
                max_output_tokens=8000,
            ),
        )
        return resp.text or ""

    return await _asyncio.to_thread(_sync_call)


async def _generate_openai_direct(
    api_key: str,
    image_paths: List[str],
    video_path: Optional[str],
    sys_prompt: str,
    user_prompt: str,
) -> str:
    """Call OpenAI Chat Completions (gpt-4o vision) directly with user's
    sk-... key. Video input is not natively supported in the chat API —
    we fall through to images only and ignore the video path.
    """
    import httpx as _httpx

    user_content: List[Dict[str, Any]] = [{"type": "text", "text": user_prompt}]
    for ip in image_paths[:MAX_IMAGES]:
        loaded = _load_image_b64(ip)
        if not loaded:
            continue
        b64, mime = loaded
        user_content.append({
            "type": "image_url",
            "image_url": {"url": f"data:{mime};base64,{b64}"},
        })

    payload = {
        "model": OPENAI_MODEL,
        "temperature": 0.4,
        "max_tokens": 8000,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": sys_prompt + "\n\nWrap your JSON array inside an outer object: {\"steps\": [...]}."},
            {"role": "user", "content": user_content},
        ],
    }
    async with _httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
        )
        if r.status_code >= 400:
            raise RuntimeError(f"OpenAI HTTP {r.status_code}: {r.text[:300]}")
        data = r.json()
        try:
            return data["choices"][0]["message"]["content"] or ""
        except Exception as e:
            raise RuntimeError(f"OpenAI bad response: {e}: {str(data)[:300]}")


async def _generate_claude_direct(
    api_key: str,
    image_paths: List[str],
    video_path: Optional[str],
    sys_prompt: str,
    user_prompt: str,
) -> str:
    """Call Anthropic Messages API directly with user's sk-ant-... key.
    Claude does NOT accept video natively — video_path is ignored.
    """
    import httpx as _httpx

    content_blocks: List[Dict[str, Any]] = []
    for ip in image_paths[:MAX_IMAGES]:
        loaded = _load_image_b64(ip)
        if not loaded:
            continue
        b64, mime = loaded
        content_blocks.append({
            "type": "image",
            "source": {"type": "base64", "media_type": mime, "data": b64},
        })
    content_blocks.append({"type": "text", "text": user_prompt})

    payload = {
        "model": CLAUDE_MODEL,
        "max_tokens": 8000,
        "system": sys_prompt + "\n\nReturn ONLY a valid JSON array, no prose. Wrap nothing.",
        "messages": [{"role": "user", "content": content_blocks}],
    }
    async with _httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json=payload,
        )
        if r.status_code >= 400:
            raise RuntimeError(f"Claude HTTP {r.status_code}: {r.text[:300]}")
        data = r.json()
        try:
            return data["content"][0]["text"] or ""
        except Exception as e:
            raise RuntimeError(f"Claude bad response: {e}: {str(data)[:300]}")


async def generate_automation_for_user(
    user_doc: Optional[Dict[str, Any]],
    image_paths: Optional[List[str]] = None,
    video_path: Optional[str] = None,
    target_url: Optional[str] = None,
    description: Optional[str] = None,
    excel_columns: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """User-aware AI automation generator. Picks provider+key from the
    user document (`ai_provider` + `gemini_api_key`/`openai_api_key`/
    `anthropic_api_key`) and falls back to platform Emergent key when
    nothing is configured. Returns the same shape as
    `generate_automation_from_media` so callers stay identical.
    """
    image_paths = image_paths or []
    if not image_paths and not video_path:
        return {"status": "failed", "error": "No images or video provided"}

    # Filter out files that don't exist before we even call the provider
    image_paths = [p for p in image_paths if Path(p).exists()]
    if video_path and not Path(video_path).exists():
        video_path = None
    if not image_paths and not video_path:
        return {"status": "failed", "error": "No readable media files"}

    try:
        provider, api_key = _resolve_provider_and_key(user_doc)
    except Exception as e:
        return {"status": "failed", "error": f"AI provider misconfigured: {str(e)[:200]}"}

    sys_prompt = _build_system_prompt()
    user_prompt = _build_user_prompt(target_url, description, excel_columns)

    raw: str = ""
    try:
        if provider == PROVIDER_GEMINI:
            raw = await _generate_gemini_direct(
                api_key, image_paths, video_path, sys_prompt, user_prompt,
            )
        elif provider == PROVIDER_OPENAI:
            raw = await _generate_openai_direct(
                api_key, image_paths, video_path, sys_prompt, user_prompt,
            )
        elif provider == PROVIDER_CLAUDE:
            raw = await _generate_claude_direct(
                api_key, image_paths, video_path, sys_prompt, user_prompt,
            )
        else:
            # Emergent universal — use LlmChat with the resolved key
            # (user's own sk-emergent-… key if saved, else platform key).
            from emergentintegrations.llm.chat import (
                LlmChat,
                UserMessage,
                FileContentWithMimeType,
            )
            file_contents: List[Any] = []
            if video_path and Path(video_path).exists():
                vp = Path(video_path)
                file_contents.append(FileContentWithMimeType(
                    file_path=str(vp),
                    mime_type=VIDEO_MIMES.get(vp.suffix.lower(), "video/mp4"),
                ))
            for p in image_paths[:MAX_IMAGES]:
                ip = Path(p)
                if not ip.exists():
                    continue
                file_contents.append(FileContentWithMimeType(
                    file_path=str(ip),
                    mime_type=IMAGE_MIMES.get(ip.suffix.lower(), "image/png"),
                ))
            if not file_contents:
                return {"status": "failed", "error": "No readable media files"}
            chat = LlmChat(
                api_key=api_key,
                session_id=f"ai-automation-{uuid.uuid4().hex[:10]}",
                system_message=sys_prompt,
            ).with_model("gemini", GEMINI_MODEL)
            msg = UserMessage(text=user_prompt, file_contents=file_contents)
            raw = await chat.send_message(msg)
    except Exception as e:
        logger.exception(f"AI generator failed via {provider}")
        return {
            "status": "failed",
            "error": f"AI call failed ({provider}): {str(e)[:300]}",
            "provider": provider,
        }

    steps = _parse_steps_from_response(raw)
    if steps is None:
        return {
            "status": "failed",
            "error": "Could not parse JSON from model output",
            "raw": raw[:2000] if isinstance(raw, str) else str(raw)[:2000],
            "provider": provider,
        }
    steps = _sanitize_steps(steps)
    return {
        "status": "ok",
        "steps": steps,
        "raw": raw if isinstance(raw, str) else str(raw),
        "provider": provider,
    }

"""AI Vision fallback for browser automation.

When rule-based form/survey detection can't progress, this module sends
a screenshot of the current page + the user's data row + the target
screenshot to Google Gemini 2.5 Flash and asks it to decide the next
action.

Uses the user's own FREE Google AI Studio API key (1500 req/day free tier)
— stored per-user in MongoDB. NOT the Emergent universal key.

Design goals:
1. Cheap — only invoked as fallback (not per-step)
2. Robust — Gemini returns structured JSON; we validate & execute safely
3. Anti-fingerprint — randomize click positions, add subtle delays
"""
from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import random
import re
from typing import Any, Dict, List, Optional

from playwright.async_api import Page

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """\
You are a browser-automation decision engine helping a bot complete a
multi-stage online survey/reward funnel (e.g., FlashRewards/RetailProductsUSA).

You will be given:
1. A screenshot of the current page
2. The user's data row (name, address, phone, email, etc. as JSON)
3. A description of the GOAL screenshot (the final "deals" page where conversion fires)
4. A short list of recent actions taken

Your job: decide ONE next action. Reply with EXACTLY this JSON schema, nothing else:

{
  "stage": "<short label e.g. 'survey-yes-no' / 'email-gate' / 'phone-gate' / 'address-form' / 'sms-opt-in' / 'agree-continue' / 'deals-page' / 'unknown'>",
  "action": "click" | "fill" | "select" | "wait" | "done" | "fail",
  "target_text": "<EXACT text shown on the button/link to click>",
  "field_label": "<label/placeholder of the field — only when action='fill' or 'select'>",
  "value": "<value to fill — only when action='fill' or 'select'>",
  "reason": "<one-line explanation>"
}

Rules:
- If the page is a Yes/No question, pick a randomly varied answer (don't always say Yes).
- If the page has multi-choice answers, pick a plausible one based on the user's data — but vary across calls so the bot doesn't fingerprint.
- If asked about debt/insurance/medicare etc. SPONSORED ads, prefer "No Thanks" / "Maybe Later" / "Skip".
- If the page is asking for SMS/text opt-in (e.g., "Text me reward updates"), prefer "NO THANKS" to skip.
- For text inputs, fill from the user's data row using the closest match (e.g., field "First Name" → row.first; "ZIP Code" → row.zip).
- For phone numbers, return the digits only (no dashes).
- For DOB year, prefer 1970-1990 if the row doesn't have it.
- For gender if missing, use "M" or "F" alternating randomly.
- If the page shows "REVIEWING PROGRESS" / "Preparing your final steps" / loading screens with NO clickable CTA, return action="wait".
- If you see the deals/offers grid (multiple offer cards, "Complete N Deal", "BEST MATCH FOR YOU"), return action="done", stage="deals-page".
- If the page is broken / blocked / shows a captcha you can't solve, return action="fail" with reason.
- NEVER return text other than the JSON object.
"""


async def screenshot_for_ai(page: Page, max_dim: int = 1280) -> Optional[str]:
    """Capture a viewport screenshot, downscale, return base64 PNG."""
    try:
        png_bytes = await page.screenshot(full_page=False, type="png")
        # Lazy resize via PIL if image is larger than max_dim
        try:
            from PIL import Image
            buf = io.BytesIO(png_bytes)
            img = Image.open(buf)
            if max(img.width, img.height) > max_dim:
                ratio = max_dim / max(img.width, img.height)
                img = img.resize(
                    (int(img.width * ratio), int(img.height * ratio)),
                    Image.LANCZOS,
                )
                out = io.BytesIO()
                img.save(out, format="PNG", optimize=True)
                png_bytes = out.getvalue()
        except Exception:
            pass
        return base64.b64encode(png_bytes).decode("ascii")
    except Exception as e:
        logger.debug(f"screenshot_for_ai err: {e}")
        return None


def _strip_json_fence(text: str) -> str:
    """Gemini sometimes wraps JSON in ```json ... ``` fences."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text


async def ask_gemini_for_next_action(
    api_key: str,
    page_screenshot_b64: str,
    row: Dict[str, Any],
    target_description: str,
    recent_actions: List[str],
    model: str = "gemini-2.5-flash",
) -> Optional[Dict[str, Any]]:
    """Call Gemini Vision and return parsed action dict, or None on failure."""
    if not api_key:
        return None

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        logger.error("google-genai not installed")
        return None

    user_data_compact = {
        k: str(v) for k, v in row.items()
        if v is not None and str(v).strip() and not str(v).startswith("nan")
    }

    prompt = (
        f"USER DATA (Excel row):\n```json\n{json.dumps(user_data_compact, default=str)[:1500]}\n```\n\n"
        f"GOAL SCREENSHOT description: {target_description}\n\n"
        f"RECENT ACTIONS (last 5):\n" +
        "\n".join(f"- {a}" for a in recent_actions[-5:]) +
        "\n\nWhat is the next action? Reply with JSON only."
    )

    def _sync_call() -> Optional[str]:
        try:
            client = genai.Client(api_key=api_key)
            img_bytes = base64.b64decode(page_screenshot_b64)
            response = client.models.generate_content(
                model=model,
                contents=[
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_bytes(data=img_bytes, mime_type="image/png"),
                            types.Part.from_text(text=prompt),
                        ],
                    )
                ],
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.7,  # some variety per call
                    response_mime_type="application/json",
                    max_output_tokens=400,
                ),
            )
            return response.text or ""
        except Exception as e:
            logger.warning(f"gemini call err: {e}")
            return None

    raw = await asyncio.to_thread(_sync_call)
    if not raw:
        return None

    try:
        action = json.loads(_strip_json_fence(raw))
        if not isinstance(action, dict) or "action" not in action:
            return None
        return action
    except json.JSONDecodeError as e:
        logger.warning(f"gemini JSON parse err: {e} — raw: {raw[:200]}")
        return None


async def ask_openai_for_next_action(
    api_key: str,
    page_screenshot_b64: str,
    row: Dict[str, Any],
    target_description: str,
    recent_actions: List[str],
    model: str = "gpt-4o-mini",
) -> Optional[Dict[str, Any]]:
    """Call OpenAI GPT-4o-mini Vision and return parsed action dict, or None.

    `gpt-4o-mini` is the cheapest vision model — ~$0.0001 per image. New
    OpenAI accounts get $5 free credit which lasts ~50,000 calls.
    """
    if not api_key:
        return None

    user_data_compact = {
        k: str(v) for k, v in row.items()
        if v is not None and str(v).strip() and not str(v).startswith("nan")
    }
    text_prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        f"USER DATA (Excel row):\n```json\n{json.dumps(user_data_compact, default=str)[:1500]}\n```\n\n"
        f"GOAL SCREENSHOT description: {target_description}\n\n"
        f"RECENT ACTIONS (last 5):\n" +
        "\n".join(f"- {a}" for a in recent_actions[-5:]) +
        "\n\nWhat is the next action? Reply with JSON only."
    )

    def _sync_call() -> Optional[str]:
        try:
            import httpx as _httpx  # noqa: WPS440 (sync httpx in thread)
            r = _httpx.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model,
                    "temperature": 0.7,
                    "max_tokens": 400,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": text_prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/png;base64,{page_screenshot_b64}",
                                        "detail": "low",
                                    },
                                },
                            ],
                        },
                    ],
                },
                timeout=60.0,
            )
            if r.status_code != 200:
                logger.warning(f"openai vision err: HTTP {r.status_code} {r.text[:200]}")
                return None
            data = r.json()
            return (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
        except Exception as e:
            logger.warning(f"openai vision call err: {e}")
            return None

    raw = await asyncio.to_thread(_sync_call)
    if not raw:
        return None

    try:
        action = json.loads(_strip_json_fence(raw))
        if not isinstance(action, dict) or "action" not in action:
            return None
        return action
    except json.JSONDecodeError as e:
        logger.warning(f"openai JSON parse err: {e} — raw: {raw[:200]}")
        return None


async def ask_ai_for_next_action(
    *,
    provider: str,
    api_key: str,
    page_screenshot_b64: str,
    row: Dict[str, Any],
    target_description: str,
    recent_actions: List[str],
) -> Optional[Dict[str, Any]]:
    """Provider-agnostic dispatcher. provider is 'gemini' or 'openai'.
    Falls back to Gemini for unknown providers."""
    p = (provider or "gemini").lower().strip()
    if p == "openai":
        return await ask_openai_for_next_action(
            api_key, page_screenshot_b64, row, target_description, recent_actions,
        )
    return await ask_gemini_for_next_action(
        api_key, page_screenshot_b64, row, target_description, recent_actions,
    )


# ─────── Action executors ───────────────────────────────────────────────

async def _execute_click(page: Page, target_text: str) -> bool:
    """Click an element with text matching target_text."""
    if not target_text:
        return False
    # Try exact match first
    try:
        loc = page.get_by_text(target_text, exact=True).first
        await loc.wait_for(state="visible", timeout=2500)
        await loc.scroll_into_view_if_needed(timeout=2000)
        await loc.click(timeout=4000)
        return True
    except Exception:
        pass
    # Fallback: normalised contains-match
    try:
        normalized = target_text.strip().lower()
        clicked = await page.evaluate(
            """(target) => {
                const all = Array.from(document.querySelectorAll(
                    'a, button, [role="button"], div, span, li, label'
                ));
                for (const el of all) {
                    if (!el.offsetParent) continue;
                    const inner = el.querySelector('a, button, [role="button"]');
                    if (inner) continue;
                    const t = (el.innerText || '').trim().toLowerCase();
                    if (t === target || t.includes(target)) {
                        el.click();
                        return true;
                    }
                }
                return false;
            }""",
            normalized,
        )
        return bool(clicked)
    except Exception:
        return False


async def _execute_fill(page: Page, field_label: str, value: str) -> bool:
    """Find a text/email/tel input matching field_label and fill with value."""
    if not field_label or not value:
        return False
    label_norm = field_label.strip().lower()
    try:
        filled = await page.evaluate(
            """([label, val]) => {
                const inputs = Array.from(document.querySelectorAll(
                    'input:not([type="hidden"]):not([type="submit"]):not([type="button"]):not([type="checkbox"]):not([type="radio"]), textarea, select'
                ));
                let target = null;
                for (const inp of inputs) {
                    if (!inp.offsetParent) continue;
                    const labels = [
                        inp.placeholder || '',
                        inp.name || '',
                        inp.id || '',
                        inp.getAttribute('aria-label') || '',
                        document.querySelector('label[for="'+inp.id+'"]')?.innerText || '',
                        inp.closest('label')?.innerText || '',
                    ].join(' ').toLowerCase();
                    if (labels.includes(label) || label.split(' ').every(t => labels.includes(t))) {
                        target = inp;
                        break;
                    }
                }
                if (!target) return false;
                target.focus();
                const setter = Object.getOwnPropertyDescriptor(
                    target instanceof HTMLSelectElement ? HTMLSelectElement.prototype :
                    target instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype :
                    HTMLInputElement.prototype,
                    'value'
                )?.set;
                if (setter) setter.call(target, val); else target.value = val;
                target.dispatchEvent(new Event('input', {bubbles: true}));
                target.dispatchEvent(new Event('change', {bubbles: true}));
                target.dispatchEvent(new Event('blur', {bubbles: true}));
                return true;
            }""",
            [label_norm, str(value)],
        )
        return bool(filled)
    except Exception as e:
        logger.debug(f"fill err: {e}")
        return False


async def execute_action(page: Page, action: Dict[str, Any]) -> bool:
    """Run an action returned by ask_gemini_for_next_action.
    Returns True if action was executed (or wait completed), False on
    fail/done."""
    a = (action.get("action") or "").lower()
    if a == "click":
        # Subtle random delay — avoid fingerprintable timing
        await page.wait_for_timeout(400 + random.randint(50, 700))
        return await _execute_click(page, action.get("target_text") or "")
    if a in ("fill", "select"):
        await page.wait_for_timeout(300 + random.randint(50, 500))
        return await _execute_fill(
            page, action.get("field_label") or "", action.get("value") or ""
        )
    if a == "wait":
        await page.wait_for_timeout(3000 + random.randint(0, 2000))
        try:
            await page.wait_for_load_state("networkidle", timeout=4000)
        except Exception:
            pass
        return True
    return False  # done / fail / unknown

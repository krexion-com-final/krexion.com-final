"""Smart UI navigator — auto-handle onboarding popups (consent, language,
permission dialogs) by reading the device UI hierarchy via uiautomator dump
and tapping known buttons by text/resource-id."""
from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from typing import TYPE_CHECKING, List, Optional, Tuple

if TYPE_CHECKING:
    from .adb import ADB

logger = logging.getLogger("cpi.ui_nav")

# Buttons we always want to tap if we see them (onboarding flow auto-accept)
# Matched case-insensitively against text/content-desc/resource-id.
ACCEPT_PATTERNS: List[str] = [
    # English
    r"\bagree\b", r"\baccept\b", r"\bcontinue\b", r"\ballow\b", r"\bok\b",
    r"\bgot it\b", r"\bnext\b", r"\bstart\b", r"\bdone\b", r"\byes\b",
    r"\bget started\b", r"\bmaybe later\b", r"\bskip\b", r"\bnot now\b",
    r"\bclose\b", r"\bdismiss\b",
    # Japanese (TikTok JP onboarding)
    "同意", "同意して続ける", "次へ", "OK", "許可", "続ける", "スキップ", "閉じる",
    "後で", "確認", "はい", "始める",
    # Spanish/Portuguese/French (extra geos)
    "aceptar", "acepto", "aceitar", "accepter", "continuar", "continuer",
    "permitir", "siguiente", "saltar",
    # Indonesian
    "setuju", "lanjutkan", "lewati",
    # Vietnamese
    "đồng ý", "tiếp tục", "bỏ qua",
    # Russian
    "принять", "продолжить", "разрешить", "пропустить",
    # Chinese simplified/traditional
    "同意", "继续", "允许", "跳过", "下一步", "确定",
    # Korean
    "동의", "계속", "허용", "다음",
    # Thai
    "ยอมรับ", "ดำเนินการต่อ",
    # Turkish
    "kabul", "devam",
    # Arabic
    "موافق", "متابعة", "تخطي",
]

# Buttons we should NEVER tap (decline / negative actions)
DENY_PATTERNS: List[str] = [
    r"\bcancel\b", r"\bdeny\b", r"\bdecline\b", r"\bno thanks\b", r"\breject\b",
    "拒否", "拒绝", "거부", "ปฏิเสธ", "rechazar", "rejeitar", "refuser",
]


def _matches_any(text: str, patterns: List[str]) -> bool:
    if not text:
        return False
    t = text.lower()
    for p in patterns:
        if not p:
            continue
        if p.startswith("\\b") or p.endswith("\\b"):
            if re.search(p, t, re.IGNORECASE):
                return True
        else:
            if p.lower() in t:
                return True
    return False


def _parse_bounds(b: str) -> Optional[Tuple[int, int]]:
    """'[x1,y1][x2,y2]' -> (cx, cy)."""
    m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", b or "")
    if not m:
        return None
    x1, y1, x2, y2 = map(int, m.groups())
    return (x1 + x2) // 2, (y1 + y2) // 2


def _find_clickable_accepts(xml_text: str) -> List[Tuple[int, int, str]]:
    """Return list of (cx, cy, label) of clickable nodes whose text matches an
    accept pattern but no deny pattern."""
    try:
        root = ET.fromstring(xml_text)
    except Exception:  # noqa: BLE001
        return []

    out: List[Tuple[int, int, str]] = []
    for node in root.iter("node"):
        attr = node.attrib
        text = (attr.get("text") or "").strip()
        cd = (attr.get("content-desc") or "").strip()
        rid = (attr.get("resource-id") or "").strip()
        clickable = attr.get("clickable") == "true"
        enabled = attr.get("enabled") == "true"
        if not (clickable and enabled):
            continue
        label = text or cd or rid
        if not label:
            continue
        if _matches_any(label, DENY_PATTERNS):
            continue
        if not _matches_any(label, ACCEPT_PATTERNS):
            continue
        bounds = _parse_bounds(attr.get("bounds") or "")
        if not bounds:
            continue
        out.append((bounds[0], bounds[1], label[:40]))
    return out


async def auto_dismiss_popups(
    adb: "ADB",
    serial: str,
    *,
    max_iters: int = 10,
    pause_seconds: float = 1.5,
) -> int:
    """Repeatedly dump the UI and tap any visible accept/continue buttons.

    Stops when no more matches found or max_iters reached. Returns the number
    of buttons tapped.
    """
    import asyncio

    tapped = 0
    for i in range(max_iters):
        # Dump UI
        rc, _ = await adb.shell(serial, "uiautomator dump /sdcard/ui.xml", timeout=15)
        if rc != 0:
            logger.debug("uiautomator dump failed (likely app loading)")
            await asyncio.sleep(pause_seconds)
            continue
        rc, xml_out = await adb.shell(serial, "cat /sdcard/ui.xml", timeout=10)
        if rc != 0 or not xml_out.strip():
            await asyncio.sleep(pause_seconds)
            continue

        targets = _find_clickable_accepts(xml_out)
        if not targets:
            logger.debug(f"auto_dismiss: no more buttons after {i} iters")
            return tapped
        # Pick the bottom-most one (popups usually have buttons at bottom)
        targets.sort(key=lambda t: t[1], reverse=True)
        cx, cy, label = targets[0]
        logger.info(f"auto-tap '{label}' at ({cx},{cy})")
        await adb.tap(serial, cx, cy)
        tapped += 1
        await asyncio.sleep(pause_seconds)

    return tapped

"""
AI-driven answer learning for survey-based offers.

The bot picks survey answers randomly on first runs. Over time, we record
which (question, answer) pairs lead to thank-you-page conversions vs not,
and bias future random picks toward higher-converting answers.

Statistical model: Beta-Bernoulli per (offer_host, question_signature, answer_text).
We sample from each candidate's posterior and pick the highest sample —
Thompson sampling — which naturally explores low-data answers while
exploiting high-converting ones.

Storage: MongoDB collection `rut_answer_learning`, one doc per offer host:
    {
        host: "warm-click-studio.lovable.app",
        questions: {
            "do you shop at target?": {
                "yes": {clicks: 12, conv: 8},
                "no":  {clicks: 9,  conv: 3}
            },
            ...
        },
        updated_at: <iso>
    }

Public API (call from real_user_traffic.py):
    stats = await load_stats(db, offer_url)
    pick = make_picker(stats)              # returns callable
    picks = await survey_click_random_answers(page, picker=pick)
    await record_outcomes(db, offer_url, picks, converted=entry["thank_you_reached"])
"""
from __future__ import annotations

import logging
import random
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urlparse

logger = logging.getLogger("rut.learning")


def _host(url: str) -> str:
    try:
        h = urlparse(url).hostname or ""
        return h.lower()
    except Exception:
        return ""


def _norm_q(s: str) -> str:
    return " ".join((s or "").lower().split())[:160]


def _norm_a(s: str) -> str:
    return " ".join((s or "").lower().split())[:80]


# ─────────────────────────────────────────────────────────
# Storage
# ─────────────────────────────────────────────────────────
async def load_stats(db, offer_url: str) -> Dict[str, Dict[str, Dict[str, int]]]:
    """Return {q_norm: {a_norm: {clicks, conv}}} for the offer host. Safe to
    return empty dict if no history or DB unavailable."""
    if db is None:
        return {}
    host = _host(offer_url)
    if not host:
        return {}
    try:
        doc = await db["rut_answer_learning"].find_one({"host": host}, {"_id": 0, "questions": 1})
        if not doc:
            return {}
        q = doc.get("questions") or {}
        if not isinstance(q, dict):
            return {}
        return q
    except Exception as e:
        logger.debug(f"load_stats failed: {e}")
        return {}


async def record_outcomes(
    db,
    offer_url: str,
    picks: List[Tuple[str, str]],
    converted: bool,
) -> None:
    """Increment click + (optionally) conv counters for each (q, a) pair.

    picks is a list of (question_signature, answer_text) tuples returned from
    survey_click_random_answers. `converted` is True when the visit reached
    the thank-you page.
    """
    if db is None or not picks:
        return
    host = _host(offer_url)
    if not host:
        return
    inc: Dict[str, int] = {}
    for q, a in picks:
        qk = _norm_q(q)
        ak = _norm_a(a)
        if not qk or not ak:
            continue
        # Mongo dot-key path for $inc
        base = f"questions.{_safe_key(qk)}.{_safe_key(ak)}"
        inc[f"{base}.clicks"] = inc.get(f"{base}.clicks", 0) + 1
        if converted:
            inc[f"{base}.conv"] = inc.get(f"{base}.conv", 0) + 1
    if not inc:
        return
    try:
        await db["rut_answer_learning"].update_one(
            {"host": host},
            {
                "$inc": inc,
                "$set": {
                    "host": host,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
            },
            upsert=True,
        )
    except Exception as e:
        logger.debug(f"record_outcomes failed: {e}")


# Mongo doesn't allow `.` or `$` in key names — escape them
def _safe_key(s: str) -> str:
    return s.replace(".", "·").replace("$", "＄")


def _unsafe_key(s: str) -> str:
    return s.replace("·", ".").replace("＄", "$")


# ─────────────────────────────────────────────────────────
# Thompson-sampling picker
# ─────────────────────────────────────────────────────────
def make_picker(
    stats: Dict[str, Dict[str, Dict[str, int]]],
    explore_prob: float = 0.15,
) -> Callable[[str, List[Tuple[Any, str]]], Tuple[Any, str]]:
    """Return a function (q_sig, candidates) → (chosen_handle, chosen_text).

    `candidates` is a list of (playwright_handle, answer_text) tuples.
    With probability `explore_prob` we pick uniformly random; otherwise
    we use Thompson sampling on Beta(1+conv, 1+clicks-conv) per candidate.
    """

    def _pick(q_sig: str, candidates: List[Tuple[Any, str]]) -> Tuple[Any, str]:
        if not candidates:
            return (None, "")
        # Force pure random with small probability (prevents starvation)
        if random.random() < explore_prob:
            return random.choice(candidates)

        qkey = _safe_key(_norm_q(q_sig))
        q_stats = stats.get(qkey) if stats else None
        if not q_stats:
            return random.choice(candidates)

        best_sample = -1.0
        best = candidates[0]
        for handle, text in candidates:
            akey = _safe_key(_norm_a(text))
            row = q_stats.get(akey) or {}
            clicks = max(0, int(row.get("clicks", 0)))
            conv = max(0, min(int(row.get("conv", 0)), clicks))
            # Beta(alpha=1+conv, beta=1+clicks-conv)
            alpha = 1.0 + conv
            beta = 1.0 + (clicks - conv)
            sample = random.betavariate(alpha, beta)
            if sample > best_sample:
                best_sample = sample
                best = (handle, text)
        return best

    return _pick


def summarize_stats(
    stats: Dict[str, Dict[str, Dict[str, int]]],
    min_clicks: int = 3,
) -> List[Dict[str, Any]]:
    """Human-readable summary for the UI ("AI Learning" panel).

    Returns sorted list of {question, best_answer, conv_rate, clicks}.
    """
    out: List[Dict[str, Any]] = []
    if not isinstance(stats, dict):
        return out
    for qkey, ans in stats.items():
        if not isinstance(ans, dict):
            continue
        best_ans = None
        best_rate = -1.0
        total_clicks = 0
        rows: List[Dict[str, Any]] = []
        for akey, row in ans.items():
            if not isinstance(row, dict):
                continue
            clicks = max(0, int(row.get("clicks", 0)))
            conv = max(0, min(int(row.get("conv", 0)), clicks))
            total_clicks += clicks
            rate = (conv / clicks) if clicks > 0 else 0.0
            rows.append({
                "answer": _unsafe_key(akey),
                "clicks": clicks,
                "conv": conv,
                "rate": round(rate, 3),
            })
            if clicks >= min_clicks and rate > best_rate:
                best_rate = rate
                best_ans = _unsafe_key(akey)
        out.append({
            "question": _unsafe_key(qkey),
            "best_answer": best_ans,
            "best_rate": round(best_rate if best_rate >= 0 else 0.0, 3),
            "total_clicks": total_clicks,
            "answers": sorted(rows, key=lambda r: -r["rate"]),
        })
    out.sort(key=lambda r: -r["total_clicks"])
    return out

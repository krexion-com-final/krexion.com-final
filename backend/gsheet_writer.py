"""
gsheet_writer.py
────────────────
Google Sheets read+write helpers using a Service Account.

Why this module exists:
    Previously the project read sheets via a public CSV-export URL (read-only).
    There was no way to delete a row from the source Google Sheet after a lead
    was consumed in a job, so the same sheet would still show consumed rows
    and we had to maintain a `consumed_keys` list in MongoDB to avoid
    re-using leads.

What this module adds:
    With a Service Account JSON (path set via env GOOGLE_SHEETS_SA_PATH or
    inline JSON via GOOGLE_SHEETS_SA_JSON) the backend can call the Sheets
    API directly to:
      • fetch rows live (no caching)
      • delete a specific row from the live sheet after it has been used

Setup:
    1. Create a Google Service Account, enable Sheets API, download JSON key.
    2. Either:
         - set GOOGLE_SHEETS_SA_PATH=/path/to/sa.json  in backend/.env, OR
         - paste the JSON content into GOOGLE_SHEETS_SA_JSON env var.
    3. Share each sheet with the service-account email as Editor — OR set the
       sheet's link sharing to "Anyone with the link → Editor". Either works.

This module is sync (Sheets API client is sync). Callers should wrap calls in
`asyncio.to_thread(...)` or `loop.run_in_executor(None, ...)` from async code.
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ──────────────────────────── Configuration ─────────────────────────────

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

_service_lock = threading.Lock()
_cached_service: Any = None
_cached_creds: Any = None


def _load_credentials():
    """Load Service Account credentials from env. Returns None when not
    configured (caller should fall back to read-only CSV path)."""
    sa_path = (os.environ.get("GOOGLE_SHEETS_SA_PATH") or "").strip()
    sa_json_inline = (os.environ.get("GOOGLE_SHEETS_SA_JSON") or "").strip()

    try:
        from google.oauth2 import service_account  # lazy import
    except Exception as e:  # pragma: no cover
        logger.warning(f"google-auth not installed: {e}")
        return None

    if sa_path and os.path.exists(sa_path):
        try:
            return service_account.Credentials.from_service_account_file(sa_path, scopes=SCOPES)
        except Exception as e:
            logger.warning(f"failed to load SA from path {sa_path}: {e}")
            return None

    if sa_json_inline:
        try:
            info = json.loads(sa_json_inline)
            return service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
        except Exception as e:
            logger.warning(f"failed to load SA from inline JSON: {e}")
            return None

    return None


def _get_service():
    """Return a cached Sheets API service client. Returns None if SA not
    configured (caller should treat as 'write disabled')."""
    global _cached_service, _cached_creds
    with _service_lock:
        if _cached_service is not None:
            return _cached_service
        creds = _load_credentials()
        if creds is None:
            return None
        try:
            from googleapiclient.discovery import build  # lazy import
            _cached_service = build("sheets", "v4", credentials=creds, cache_discovery=False)
            _cached_creds = creds
            return _cached_service
        except Exception as e:
            logger.warning(f"failed to build Sheets service: {e}")
            return None


def is_write_enabled() -> bool:
    """True when SA credentials are configured AND service builds successfully.
    UI / decision code should branch on this."""
    return _get_service() is not None


# ──────────────────────────── URL parsing ───────────────────────────────

_ID_RE = re.compile(r"/d/([a-zA-Z0-9_-]+)")
_GID_RE = re.compile(r"[?&#]gid=(\d+)")


def parse_sheet_id_and_gid(url: str) -> Tuple[Optional[str], Optional[int]]:
    """Extract spreadsheet_id and gid (sheet/tab id) from a Google Sheet URL.
    gid is None when not specified (we'll resolve to first sheet)."""
    if not url:
        return None, None
    m = _ID_RE.search(url)
    sid = m.group(1) if m else None
    gm = _GID_RE.search(url)
    gid = int(gm.group(1)) if gm else None
    return sid, gid


# ──────────────────────────── Read helpers ───────────────────────────────

def _resolve_target_sheet(service, spreadsheet_id: str, gid: Optional[int]) -> Tuple[str, int]:
    """Return (sheet_title, sheet_inner_id) for the gid (or first tab when
    gid is None)."""
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    sheets = meta.get("sheets", [])
    if not sheets:
        raise ValueError("spreadsheet has no sheets/tabs")
    if gid is None:
        s = sheets[0]["properties"]
        return s["title"], int(s["sheetId"])
    for s in sheets:
        p = s["properties"]
        if int(p["sheetId"]) == int(gid):
            return p["title"], int(p["sheetId"])
    # fallback to first tab if gid mismatch (sheet was renamed/re-tabbed)
    s = sheets[0]["properties"]
    return s["title"], int(s["sheetId"])


def _norm_header(s: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(s or "").lower()).strip("_")


def read_rows(url: str) -> List[Dict[str, Any]]:
    """Fetch rows via authenticated Sheets API. Returns list of dicts keyed by
    normalised header. Raises on failure (caller may catch and fall back to
    CSV)."""
    service = _get_service()
    if service is None:
        raise RuntimeError("gsheets SA not configured (GOOGLE_SHEETS_SA_PATH/_JSON missing)")
    sid, gid = parse_sheet_id_and_gid(url)
    if not sid:
        raise ValueError(f"could not extract spreadsheet id from URL: {url[:80]}")
    title, _ = _resolve_target_sheet(service, sid, gid)
    res = service.spreadsheets().values().get(
        spreadsheetId=sid,
        range=f"'{title}'",
        valueRenderOption="UNFORMATTED_VALUE",
    ).execute()
    values: List[List[Any]] = res.get("values", []) or []
    if not values:
        return []
    header = [_norm_header(c) for c in values[0]]
    rows: List[Dict[str, Any]] = []
    for raw in values[1:]:
        row: Dict[str, Any] = {}
        for i, h in enumerate(header):
            if not h:
                continue
            row[h] = raw[i] if i < len(raw) else ""
        rows.append(row)
    return rows


# ──────────────────────────── Delete operations ──────────────────────────

def delete_row_by_email(url: str, email: str) -> bool:
    """Find the first data row whose `email` column matches (case-insensitive,
    trimmed) and delete it from the live sheet via batchUpdate. Returns True
    when a row was actually deleted, False otherwise (no match / write
    disabled). Raises only on auth/network errors so caller can decide."""
    if not email or not email.strip():
        return False
    service = _get_service()
    if service is None:
        return False

    sid, gid = parse_sheet_id_and_gid(url)
    if not sid:
        return False
    title, sheet_inner_id = _resolve_target_sheet(service, sid, gid)

    # Read just the email column block — but since we don't know the column
    # index without the header, fetch header + all rows.
    res = service.spreadsheets().values().get(
        spreadsheetId=sid,
        range=f"'{title}'",
        valueRenderOption="UNFORMATTED_VALUE",
    ).execute()
    values: List[List[Any]] = res.get("values", []) or []
    if len(values) < 2:
        return False
    header = [_norm_header(c) for c in values[0]]
    email_col_idx = None
    for cand in ("email", "email_address", "emailaddress", "e_mail", "mail"):
        if cand in header:
            email_col_idx = header.index(cand)
            break
    if email_col_idx is None:
        return False

    target = email.strip().lower()
    target_sheet_row_zero_based: Optional[int] = None
    for i, raw in enumerate(values[1:], start=1):  # start=1 → sheet row 2 = index 1
        if email_col_idx >= len(raw):
            continue
        cell = str(raw[email_col_idx] or "").strip().lower()
        if cell == target:
            target_sheet_row_zero_based = i  # this is the 0-based row in sheet
            break
    if target_sheet_row_zero_based is None:
        return False

    body = {
        "requests": [{
            "deleteDimension": {
                "range": {
                    "sheetId": sheet_inner_id,
                    "dimension": "ROWS",
                    "startIndex": target_sheet_row_zero_based,
                    "endIndex": target_sheet_row_zero_based + 1,
                }
            }
        }]
    }
    service.spreadsheets().batchUpdate(spreadsheetId=sid, body=body).execute()
    # Drop the cached read for this sheet so the next caller sees fresh
    # contents (we just removed a row).
    try:
        import gsheet_cache  # local import to avoid circular at boot
        gsheet_cache.invalidate(url)
    except Exception:
        pass
    return True


def delete_rows_by_emails(url: str, emails: List[str]) -> int:
    """Bulk delete: remove every row whose email matches any in `emails`.
    Returns count of rows actually deleted. Single batchUpdate request — ranges
    are sorted bottom-up to keep indices valid as deletions shift the sheet."""
    if not emails:
        return 0
    targets = {(e or "").strip().lower() for e in emails if (e or "").strip()}
    if not targets:
        return 0
    service = _get_service()
    if service is None:
        return 0

    sid, gid = parse_sheet_id_and_gid(url)
    if not sid:
        return 0
    title, sheet_inner_id = _resolve_target_sheet(service, sid, gid)

    res = service.spreadsheets().values().get(
        spreadsheetId=sid,
        range=f"'{title}'",
        valueRenderOption="UNFORMATTED_VALUE",
    ).execute()
    values: List[List[Any]] = res.get("values", []) or []
    if len(values) < 2:
        return 0
    header = [_norm_header(c) for c in values[0]]
    email_col_idx = None
    for cand in ("email", "email_address", "emailaddress", "e_mail", "mail"):
        if cand in header:
            email_col_idx = header.index(cand)
            break
    if email_col_idx is None:
        return 0

    rows_to_delete: List[int] = []  # 0-based sheet row indices
    for i, raw in enumerate(values[1:], start=1):
        if email_col_idx >= len(raw):
            continue
        cell = str(raw[email_col_idx] or "").strip().lower()
        if cell in targets:
            rows_to_delete.append(i)
    if not rows_to_delete:
        return 0

    # Sort descending so each delete doesn't shift earlier indices
    rows_to_delete.sort(reverse=True)
    requests = [{
        "deleteDimension": {
            "range": {
                "sheetId": sheet_inner_id,
                "dimension": "ROWS",
                "startIndex": r,
                "endIndex": r + 1,
            }
        }
    } for r in rows_to_delete]

    service.spreadsheets().batchUpdate(spreadsheetId=sid, body={"requests": requests}).execute()
    # Drop the cached read so next caller sees post-delete state
    try:
        import gsheet_cache
        gsheet_cache.invalidate(url)
    except Exception:
        pass
    return len(rows_to_delete)


__all__ = [
    "is_write_enabled",
    "parse_sheet_id_and_gid",
    "read_rows",
    "delete_row_by_email",
    "delete_rows_by_emails",
    "delete_rows_by_first_column",
    "list_tabs",
]


def delete_rows_by_first_column(url: str, values: List[str]) -> int:
    """Bulk delete rows whose FIRST column matches any value in `values`.

    Used for proxy and user-agent sheets (which don't have an email
    column — the first column IS the proxy string / UA string itself).
    Matching is case-insensitive + whitespace-trimmed.

    Returns count of rows actually deleted from the live sheet (0 when
    SA not configured / no matches / sheet empty). Single batchUpdate
    request, ranges sorted descending so deletions don't shift earlier
    indices. Raises only on auth/network errors so the caller can
    decide whether to surface the failure.
    """
    if not values:
        return 0
    targets = {(v or "").strip().lower() for v in values if (v or "").strip()}
    if not targets:
        return 0
    service = _get_service()
    if service is None:
        return 0

    sid, gid = parse_sheet_id_and_gid(url)
    if not sid:
        return 0
    title, sheet_inner_id = _resolve_target_sheet(service, sid, gid)

    res = service.spreadsheets().values().get(
        spreadsheetId=sid,
        range=f"'{title}'",
        valueRenderOption="UNFORMATTED_VALUE",
    ).execute()
    raw_values: List[List[Any]] = res.get("values", []) or []
    if not raw_values:
        return 0

    # IMPORTANT: proxy / UA sheets typically DON'T have a header row —
    # row 0 is already a proxy/UA string. data-file sheets DO have one
    # (column titles like "first / last / email / state"). We auto-
    # detect: if the first cell of row 0 matches one of our delete
    # targets, treat row 0 as a data row; otherwise assume it's a
    # header and start from row 1. Either way the delete is precise.
    rows_to_delete: List[int] = []
    start_row = 0
    if raw_values and raw_values[0]:
        first_cell = str(raw_values[0][0] or "").strip().lower()
        # Heuristic: if the very first cell looks like a header label
        # ("proxy", "user_agent", "ua", "host", "ip", etc.) skip it.
        header_markers = {
            "proxy", "proxies", "user_agent", "useragent", "user-agent",
            "ua", "useragents", "agent", "host", "ip", "url", "value",
        }
        if first_cell in header_markers and first_cell not in targets:
            start_row = 1

    for i, raw in enumerate(raw_values[start_row:], start=start_row):
        if not raw:
            continue
        cell = str(raw[0] or "").strip().lower()
        if cell in targets:
            rows_to_delete.append(i)
    if not rows_to_delete:
        return 0

    rows_to_delete.sort(reverse=True)
    requests = [{
        "deleteDimension": {
            "range": {
                "sheetId": sheet_inner_id,
                "dimension": "ROWS",
                "startIndex": r,
                "endIndex": r + 1,
            }
        }
    } for r in rows_to_delete]

    service.spreadsheets().batchUpdate(spreadsheetId=sid, body={"requests": requests}).execute()
    try:
        import gsheet_cache
        gsheet_cache.invalidate(url)
    except Exception:
        pass
    return len(rows_to_delete)


def list_tabs(url: str) -> List[Dict[str, Any]]:
    """Return list of all worksheet tabs in the spreadsheet, with their
    title, gid, row count and a ready-to-paste URL pointing at that tab.
    Used by the UI so the user can pick which tab to attach to which
    upload (proxy / UA / data) without manually copying gid from the
    browser address bar.

    Returns [] when SA is not configured or the URL is invalid (caller
    decides how to surface that to the user)."""
    service = _get_service()
    if service is None:
        return []
    sid, _ = parse_sheet_id_and_gid(url)
    if not sid:
        return []
    try:
        meta = service.spreadsheets().get(spreadsheetId=sid).execute()
    except Exception as e:
        logger.warning(f"list_tabs failed for {url[:80]}: {e}")
        return []
    out: List[Dict[str, Any]] = []
    for s in meta.get("sheets", []):
        p = s.get("properties", {})
        title = p.get("title") or ""
        gid = int(p.get("sheetId") or 0)
        grid = p.get("gridProperties", {})
        out.append({
            "title": title,
            "gid": gid,
            "row_count": int(grid.get("rowCount") or 0),
            "column_count": int(grid.get("columnCount") or 0),
            "url": f"https://docs.google.com/spreadsheets/d/{sid}/edit#gid={gid}",
        })
    return out

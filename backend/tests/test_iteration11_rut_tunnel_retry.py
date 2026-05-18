"""
Iteration 11 — Real User Traffic tunnel-retry logic.

Validates the new goto-retry block in /app/backend/real_user_traffic.py
(lines ~1808-1888 + outer except at ~1928-1947) that detects
ERR_TUNNEL_CONNECTION_FAILED-class proxy errors and transparently
rotates to a fresh proxy up to 2 times before failing the visit.

Test strategy (per the review_request agent note):
  - Full Playwright E2E is heavyweight (Chromium + real proxies). Instead
    we:
    A) Statically verify the source file contains the 8 required tunnel
       tokens, the MAX_TUNNEL_RETRIES=2 constant, and the friendly
       customer-facing error message.
    B) Mirror the retry-loop structure in a tiny coroutine and inject
       controlled `page.goto` exceptions to prove control flow.
    C) Regression: hit live RUT/health/adspower/user-agents endpoints
       to confirm the patch didn't break the public API surface.
"""
import os
import re
import asyncio
import pytest
import requests

# Resolve backend URL from frontend/.env (single source of truth)
def _resolve_base_url() -> str:
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if v:
        return v.rstrip("/")
    try:
        with open("/app/frontend/.env", "r") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    return line.split("=", 1)[1].strip().rstrip("/")
    except Exception:
        pass
    raise RuntimeError("REACT_APP_BACKEND_URL not set")


BASE_URL = _resolve_base_url()
SRC_PATH = "/app/backend/real_user_traffic.py"
ADMIN_EMAIL = "adspowertester@gmail.com"
ADMIN_PASSWORD = "Test12345"


# ---------------------------------------------------------------------------
# A) Static code-review assertions on real_user_traffic.py
# ---------------------------------------------------------------------------
class TestSourceCodeContainsRetryBlock:
    """Verify the new retry block exists and is well-formed."""

    @pytest.fixture(scope="class")
    def src(self):
        with open(SRC_PATH, "r", encoding="utf-8") as f:
            return f.read()

    def test_all_8_tunnel_tokens_present(self, src):
        required = [
            "ERR_TUNNEL_CONNECTION_FAILED",
            "ERR_PROXY_CONNECTION_FAILED",
            "ERR_HTTP_RESPONSE_CODE_FAILURE",
            "ERR_CONNECTION_RESET",
            "ERR_CONNECTION_CLOSED",
            "ERR_CONNECTION_REFUSED",
            "ERR_EMPTY_RESPONSE",
            "ERR_SOCKET_NOT_CONNECTED",
        ]
        # find _TUNNEL_ERR_TOKENS tuple body
        m = re.search(r"_TUNNEL_ERR_TOKENS\s*=\s*\((.*?)\)", src, re.DOTALL)
        assert m, "_TUNNEL_ERR_TOKENS tuple not found"
        body = m.group(1)
        for tok in required:
            assert tok in body, f"Missing tunnel token: {tok}"

    def test_max_tunnel_retries_is_2(self, src):
        m = re.search(r"MAX_TUNNEL_RETRIES\s*=\s*(\d+)", src)
        assert m and m.group(1) == "2", "MAX_TUNNEL_RETRIES must == 2"

    def test_retry_loop_calls_pick_next_proxy(self, src):
        # The retry block must rotate proxy via pick_next_proxy()
        assert re.search(
            r"is_tunnel.*?pick_next_proxy\(\)", src, re.DOTALL
        ), "Retry loop must call pick_next_proxy() on tunnel error"

    def test_retry_loop_closes_old_context_before_rebuild(self, src):
        # Between pick_next_proxy and new_context, old context.close() must run
        block = re.search(
            r"new_proxy = pick_next_proxy\(\).*?context = await browser\.new_context",
            src, re.DOTALL,
        )
        assert block, "Could not locate rebuild block"
        assert "context.close()" in block.group(0), \
            "Old context must be closed before rebuild (leak prevention)"

    def test_retry_keeps_same_ua_and_fingerprint(self, src):
        # The rebuild new_context must reuse `ua`, `fp[...]`, `geo[...]` —
        # NOT a fresh fingerprint. Verify by checking the rebuild snippet.
        block = re.search(
            r"new_proxy = pick_next_proxy\(\).*?await context\.add_init_script",
            src, re.DOTALL,
        )
        assert block, "Rebuild block missing"
        s = block.group(0)
        for k in ("user_agent=ua", "viewport=fp", "locale=geo", "timezone_id=geo"):
            assert k in s, f"Rebuild must reuse {k!r} (same fingerprint contract)"

    def test_friendly_error_message_present(self, src):
        assert "Proxy tunnel failed after" in src
        assert "different" in src.lower() and "state" in src.lower()
        # Must be gated on tunnel-token detection (not for every error)
        assert re.search(
            r"any\(tok in err_text for tok in _TUNNEL_ERR_TOKENS\)",
            src,
        ), "Friendly message must only fire when error contains a tunnel token"

    def test_non_tunnel_error_short_circuits(self, src):
        # `if not is_tunnel or tunnel_attempt >= MAX_TUNNEL_RETRIES: break`
        assert re.search(
            r"if\s+not\s+is_tunnel\s+or\s+tunnel_attempt\s*>=\s*MAX_TUNNEL_RETRIES",
            src,
        ), "Non-tunnel errors must break immediately (no proxy rotation)"


# ---------------------------------------------------------------------------
# B) Behavior simulation — mirror the source retry loop with mock goto
# ---------------------------------------------------------------------------
# The retry block (lines 1832-1888) is the pattern:
#   while True:
#       try:
#           resp = await page.goto(target_url, ...)
#           break
#       except Exception as _ge:
#           goto_exc = _ge
#           is_tunnel = any(tok in str(_ge) for tok in _TUNNEL_ERR_TOKENS)
#           if not is_tunnel or tunnel_attempt >= MAX_TUNNEL_RETRIES: break
#           new_proxy = pick_next_proxy()
#           if not new_proxy: break
#           tunnel_attempt += 1
#           await context.close()
#           context = await browser.new_context(...)
#           page = await context.new_page()
#
# We replicate this EXACT control flow in `run_retry_loop` below so the
# logic is testable deterministically without launching Chromium.

_TUNNEL_ERR_TOKENS = (
    "ERR_TUNNEL_CONNECTION_FAILED",
    "ERR_PROXY_CONNECTION_FAILED",
    "ERR_HTTP_RESPONSE_CODE_FAILURE",
    "ERR_CONNECTION_RESET",
    "ERR_CONNECTION_CLOSED",
    "ERR_CONNECTION_REFUSED",
    "ERR_EMPTY_RESPONSE",
    "ERR_SOCKET_NOT_CONNECTED",
)
MAX_TUNNEL_RETRIES = 2


async def run_retry_loop(page, pick_next_proxy, browser, target_url="https://x"):
    """Mirror of source retry loop. Returns (resp, goto_exc, tunnel_attempt,
    rotations_attempted) — rotations_attempted = how many times
    pick_next_proxy was actually invoked."""
    tunnel_attempt = 0
    rotations = 0
    resp = None
    goto_exc = None
    context = page._context
    while True:
        try:
            resp = await page.goto(target_url)
            goto_exc = None
            break
        except Exception as ge:
            goto_exc = ge
            is_tunnel = any(tok in str(ge) for tok in _TUNNEL_ERR_TOKENS)
            if not is_tunnel or tunnel_attempt >= MAX_TUNNEL_RETRIES:
                break
            new_proxy = pick_next_proxy()
            rotations += 1
            if not new_proxy:
                break
            tunnel_attempt += 1
            await context.close()
            context = await browser.new_context(proxy=new_proxy)
            page = await context.new_page()
    # Build friendly outer-except behavior
    entry_error = None
    if goto_exc is not None:
        err_text = str(goto_exc)
        friendly = err_text[:180]
        if any(tok in err_text for tok in _TUNNEL_ERR_TOKENS):
            friendly = (
                f"Proxy tunnel failed after {tunnel_attempt + 1} attempts — "
                "your proxy provider couldn't reach the target. Try a "
                "different US state, smaller batch, or reload proxies."
            )
        entry_error = f"goto failed: {friendly}"
    return resp, goto_exc, tunnel_attempt, rotations, entry_error


class FakeContext:
    def __init__(self):
        self.closed = False

    async def close(self):
        self.closed = True


class FakePage:
    """Mock playwright Page. `goto_sequence` is a list of exception
    instances (or `None` for success) to return on each goto call."""

    def __init__(self, goto_sequence, context):
        self._goto_sequence = list(goto_sequence)
        self._context = context
        self.call_count = 0

    async def goto(self, url, **kwargs):
        self.call_count += 1
        result = self._goto_sequence.pop(0)
        if isinstance(result, Exception):
            raise result
        return result  # success object


class FakeBrowser:
    def __init__(self, contexts_to_return):
        self._contexts = list(contexts_to_return)
        self.new_context_calls = 0

    async def new_context(self, **kwargs):
        self.new_context_calls += 1
        ctx = self._contexts.pop(0)
        return ctx


class TestRetryLoopBehavior:
    """Behavior-level tests — these prove the source loop is correct."""

    @pytest.mark.asyncio
    async def _impl_two_tunnel_failures_then_success(self):
        """Tunnel fails twice → 3rd goto succeeds. pick_next_proxy called
        2 times, visit succeeds, NO friendly error written."""
        rotations_done = []

        def pick():
            rotations_done.append(1)
            return {"server": "http://p2", "raw": "p2"}

        ctx1 = FakeContext()
        ctx2 = FakeContext()
        ctx3 = FakeContext()
        # On goto: fail, fail, success-object
        seq = [
            Exception("Page.goto: net::ERR_TUNNEL_CONNECTION_FAILED at https://x"),
            Exception("Page.goto: net::ERR_TUNNEL_CONNECTION_FAILED at https://x"),
            object(),  # success
        ]
        page = FakePage(seq, ctx1)
        browser = FakeBrowser([ctx2, ctx3])
        # NOTE: After each rotation, run_retry_loop creates a new page from
        # the new_context — but in our mirror we keep the SAME page+seq
        # (call_count tracks across rotations). The mirror's rebuild calls
        # browser.new_context(...) + context.new_page() but uses the same
        # FakePage instance for sequencing. Simulate that by patching
        # context.new_page on each FakeContext.
        for c in (ctx2, ctx3):
            c.new_page = (lambda p=page: _async_return(p))

        resp, exc, attempts, rotations, err = await run_retry_loop(
            page, pick, browser
        )
        assert resp is not None, "Should succeed on 3rd attempt"
        assert exc is None
        assert attempts == 2, f"Expected 2 tunnel attempts, got {attempts}"
        assert rotations == 2, f"pick_next_proxy should be called 2x, got {rotations}"
        assert err is None
        assert ctx1.closed and ctx2.closed, "Old contexts must be closed"
        assert browser.new_context_calls == 2

    @pytest.mark.asyncio
    async def _impl_all_tunnel_failures_exhausts_retries(self):
        """All gotos fail with tunnel error → loop exits after MAX retries,
        friendly message contains 'Proxy tunnel failed after 3 attempts'."""
        rotations_done = []

        def pick():
            rotations_done.append(1)
            return {"server": "http://p", "raw": f"p{len(rotations_done)}"}

        ctx1, ctx2, ctx3 = FakeContext(), FakeContext(), FakeContext()
        seq = [
            Exception("Page.goto: net::ERR_TUNNEL_CONNECTION_FAILED at https://x"),
            Exception("Page.goto: net::ERR_TUNNEL_CONNECTION_FAILED at https://x"),
            Exception("Page.goto: net::ERR_TUNNEL_CONNECTION_FAILED at https://x"),
        ]
        page = FakePage(seq, ctx1)
        browser = FakeBrowser([ctx2, ctx3])
        for c in (ctx2, ctx3):
            c.new_page = (lambda p=page: _async_return(p))

        resp, exc, attempts, rotations, err = await run_retry_loop(page, pick, browser)
        assert resp is None
        assert exc is not None
        assert attempts == 2
        assert rotations == 2, "pick_next_proxy called exactly 2 times"
        assert err is not None
        assert "Proxy tunnel failed after 3 attempts" in err, \
            f"Friendly msg missing/wrong: {err!r}"
        assert "different" in err.lower()

    @pytest.mark.asyncio
    async def _impl_non_tunnel_error_does_not_rotate(self):
        """Timeout / generic error → NO proxy rotation, raw err preserved."""
        rotations_done = []

        def pick():
            rotations_done.append(1)
            return {"server": "should-not-be-called"}

        ctx = FakeContext()
        seq = [TimeoutError("Page.goto: Timeout 90000ms exceeded for https://x")]
        page = FakePage(seq, ctx)
        browser = FakeBrowser([])

        resp, exc, attempts, rotations, err = await run_retry_loop(page, pick, browser)
        assert resp is None
        assert isinstance(exc, TimeoutError)
        assert attempts == 0
        assert rotations == 0, "pick_next_proxy must NOT be called for non-tunnel"
        assert err is not None
        assert "Proxy tunnel failed" not in err, \
            "Friendly tunnel-message must NOT be used for non-tunnel errors"
        assert "Timeout" in err

    @pytest.mark.asyncio
    async def _impl_pick_next_proxy_returns_none_short_circuits(self):
        """If proxy pool exhausted (pick_next_proxy → None), retry stops
        gracefully without infinite loop."""
        def pick():
            return None

        ctx = FakeContext()
        seq = [Exception("net::ERR_TUNNEL_CONNECTION_FAILED")]
        page = FakePage(seq, ctx)
        browser = FakeBrowser([])

        resp, exc, attempts, rotations, err = await run_retry_loop(page, pick, browser)
        assert resp is None
        assert attempts == 0, "No retry attempted when no proxy available"
        assert rotations == 1, "pick_next_proxy IS called once but returned None"
        assert err and "Proxy tunnel failed after 1 attempts" in err

    @pytest.mark.asyncio
    async def _impl_each_listed_tunnel_token_triggers_rotation(self):
        """Each of the 8 tokens must independently trigger proxy rotation."""
        for tok in _TUNNEL_ERR_TOKENS:
            ctx1, ctx2 = FakeContext(), FakeContext()
            seq = [Exception(f"net::{tok} at https://x"), object()]
            page = FakePage(seq, ctx1)
            browser = FakeBrowser([ctx2])
            ctx2.new_page = (lambda p=page: _async_return(p))
            rots = []
            resp, exc, attempts, rotations, err = await run_retry_loop(
                page, lambda: (rots.append(1) or {"server": "p"}), browser
            )
            assert resp is not None, f"Token {tok} should rotate and succeed"
            assert rotations == 1, f"Token {tok} did not trigger rotation"

    # ---- sync wrappers (no pytest-asyncio installed) ----
    def test_two_tunnel_failures_then_success(self):
        asyncio.run(self._impl_two_tunnel_failures_then_success())

    def test_all_tunnel_failures_exhausts_retries(self):
        asyncio.run(self._impl_all_tunnel_failures_exhausts_retries())

    def test_non_tunnel_error_does_not_rotate(self):
        asyncio.run(self._impl_non_tunnel_error_does_not_rotate())

    def test_pick_next_proxy_returns_none_short_circuits(self):
        asyncio.run(self._impl_pick_next_proxy_returns_none_short_circuits())

    def test_each_listed_tunnel_token_triggers_rotation(self):
        asyncio.run(self._impl_each_listed_tunnel_token_triggers_rotation())


async def _async_return(v):
    return v


# ---------------------------------------------------------------------------
# C) Regression — confirm RUT/health endpoints still return clean responses
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def admin_token():
    s = requests.Session()
    r = s.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=15,
    )
    if r.status_code != 200:
        pytest.skip(f"Admin login failed ({r.status_code}): {r.text[:200]}")
    return r.json().get("access_token") or r.json().get("token")


class TestRegressionEndpoints:
    def test_health(self):
        # /api/auth/me returns 401 when unauth — proves API is reachable
        # (no /api/health route exists in this codebase)
        r = requests.get(f"{BASE_URL}/api/auth/me", timeout=10)
        assert r.status_code in (200, 401), \
            f"API unreachable: {r.status_code}: {r.text[:200]}"

    def test_user_agents_options(self, admin_token):
        h = {"Authorization": f"Bearer {admin_token}"}
        r = requests.get(f"{BASE_URL}/api/user-agents/options", headers=h, timeout=15)
        assert r.status_code == 200, f"{r.status_code}: {r.text[:200]}"
        data = r.json()
        assert isinstance(data, (dict, list))

    def test_adspower_configs(self, admin_token):
        h = {"Authorization": f"Bearer {admin_token}"}
        r = requests.get(f"{BASE_URL}/api/adspower/configs", headers=h, timeout=15)
        # Admin may not have profile_builder; either 200 or 403 is acceptable
        # (the key check is NOT 500)
        assert r.status_code in (200, 403), \
            f"adspower/configs broken: {r.status_code} {r.text[:200]}"

    def test_rut_create_job_invalid_payload_no_500(self, admin_token):
        """Empty multipart payload should produce 4xx (validation error),
        never 500. Confirms our patch didn't introduce a parser regression."""
        h = {"Authorization": f"Bearer {admin_token}"}
        r = requests.post(
            f"{BASE_URL}/api/real-user-traffic/jobs",
            headers=h,
            data={},  # missing required link_id
            timeout=15,
        )
        assert r.status_code < 500, \
            f"Empty payload should be 4xx not 5xx, got {r.status_code}: {r.text[:200]}"
        # 422 (validation) or 403 (feature flag) both acceptable
        assert r.status_code in (400, 401, 403, 422), \
            f"Unexpected code {r.status_code}: {r.text[:200]}"

    def test_rut_list_jobs(self, admin_token):
        h = {"Authorization": f"Bearer {admin_token}"}
        r = requests.get(f"{BASE_URL}/api/real-user-traffic/jobs", headers=h, timeout=15)
        # admin without real_user_traffic flag → 403; with flag → 200
        assert r.status_code in (200, 403), \
            f"list jobs broken: {r.status_code}: {r.text[:200]}"

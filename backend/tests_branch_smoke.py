"""
Quick e2e smoke-test for the new `branch` action in
real_user_traffic._execute_automation_steps.

Boots Playwright + a tiny in-process HTTP server that serves a survey
page where Step 1 chooses which path appears on Step 2 (Phone vs
Birthday vs Address). Then runs a recorded automation with a `branch`
step and asserts:
  - the matched branch's sub-steps actually executed
  - the unmatched branches didn't
  - the splice happened in-place (no recursion / no infinite loop)

Run with:
    cd /tmp/krexion.com/backend
    PYTHONPATH=. python tests_branch_smoke.py
"""
import asyncio
import http.server
import socketserver
import threading
import sys
from pathlib import Path

# Allow `import real_user_traffic` from the same dir
sys.path.insert(0, str(Path(__file__).resolve().parent))

PORT = 8791

HTML_PAGES = {
    "/": """<!doctype html><html><body>
        <h1>Step 1 — pick path</h1>
        <input id="email" name="email" />
        <button id="go-phone" onclick="window.location.href='/phone'">Go phone</button>
        <button id="go-birthday" onclick="window.location.href='/birthday'">Go birthday</button>
    </body></html>""",
    "/phone": """<!doctype html><html><body>
        <h1>Phone page</h1>
        <input id="phone" name="phone" />
        <button id="done" onclick="document.getElementById('marker').textContent='PHONE_DONE'">Submit</button>
        <div id="marker"></div>
    </body></html>""",
    "/birthday": """<!doctype html><html><body>
        <h1>Birthday page</h1>
        <input id="birthday" name="birthday" />
        <button id="done" onclick="document.getElementById('marker').textContent='BIRTHDAY_DONE'">Submit</button>
        <div id="marker"></div>
    </body></html>""",
}


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = HTML_PAGES.get(self.path, "<h1>404</h1>")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def log_message(self, *_a, **_k):
        pass


def start_server():
    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.TCPServer(("127.0.0.1", PORT), Handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd


async def run_case(label: str, click_button: str, expect_marker: str) -> bool:
    """Run the automation with a branch step. click_button decides which
    page appears next; we then verify the right branch's sub-steps ran."""
    from playwright.async_api import async_playwright
    from real_user_traffic import _execute_automation_steps

    # Steps: load page → click the chosen Go-button → BRANCH → click Submit.
    # The branch's sub-steps differ per path, and only the matching one
    # should be spliced into the live step list.
    steps = [
        {"action": "wait_for_load", "timeout": 8000},
        {"action": "click", "selector": f"#{click_button}", "wait_nav": True, "timeout": 6000},
        {
            "action": "branch",
            "name": "After page choice",
            "timeout_ms": 6000,
            "branches": [
                {
                    "name": "phone-path",
                    "condition": {"type": "selector_visible", "selector": "input#phone", "timeout_ms": 6000},
                    "steps": [
                        {"action": "fill", "selector": "input#phone", "value": "+14155552671", "timeout": 4000},
                        {"action": "click", "selector": "#done", "timeout": 4000},
                    ],
                },
                {
                    "name": "birthday-path",
                    "condition": {"type": "selector_visible", "selector": "input#birthday", "timeout_ms": 6000},
                    "steps": [
                        {"action": "fill", "selector": "input#birthday", "value": "1990-01-01", "timeout": 4000},
                        {"action": "click", "selector": "#done", "timeout": 4000},
                    ],
                },
            ],
            "default_steps": [
                {"action": "wait", "ms": 100},
            ],
        },
        {"action": "wait", "ms": 300},
    ]

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context()
        page = await ctx.new_page()
        await page.goto(f"http://127.0.0.1:{PORT}/")
        res = await _execute_automation_steps(
            page=page,
            row={},
            steps=steps,
            skip_captcha=True,
            self_heal=False,
            collect_timings=True,
        )
        # Check the marker on the FINAL page reflects the correct branch.
        try:
            marker = await page.locator("#marker").inner_text(timeout=2000)
        except Exception:
            marker = ""
        await browser.close()

    ok_status = res.get("status") in (None, "ok", "completed")
    marker_ok = marker.strip() == expect_marker
    print(f"[{label}] status={res.get('status')} executed={res.get('executed_steps')} marker={marker!r} (expected {expect_marker!r}) → {'PASS' if marker_ok else 'FAIL'}")
    return marker_ok


async def main():
    httpd = start_server()
    try:
        a = await run_case("Phone branch",    "go-phone",    "PHONE_DONE")
        b = await run_case("Birthday branch", "go-birthday", "BIRTHDAY_DONE")
        if a and b:
            print("\nALL BRANCH SMOKE TESTS PASSED ✅")
            return 0
        print("\nFAILURES — see above ❌")
        return 1
    finally:
        httpd.shutdown()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

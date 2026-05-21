"""Quick page inspection - just visit URL and screenshot."""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, "/app/backend")
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "/pw-browsers")

OUT = Path("/app/backend/tests/demo_results")
OUT.mkdir(parents=True, exist_ok=True)

URLS = [
    "https://giftclick.org/aff_c?offer_id=250&aff_id=179687",
]

DEMO_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
           "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36")


async def main():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--headless=new", "--no-sandbox"])
        ctx = await browser.new_context(user_agent=DEMO_UA, viewport={"width": 1366, "height": 768})
        page = await ctx.new_page()

        nav_log = []
        page.on("framenavigated", lambda f: f == page.main_frame and nav_log.append(f.url))

        for u in URLS:
            print(f"GOTO: {u}", flush=True)
            try:
                await page.goto(u, timeout=60000, wait_until="domcontentloaded")
            except Exception as e:
                print("goto err:", e)
            # let JS redirects fire
            for sec in range(20):
                await asyncio.sleep(1)
                print(f"  +{sec+1}s url={page.url}", flush=True)
            # Capture page HTML excerpt
            try:
                html = await page.content()
                (OUT / "page_html.txt").write_text(html[:50000])
                print("HTML len:", len(html))
            except Exception:
                pass
            try:
                png = await page.screenshot(full_page=True)
                (OUT / "page_final.png").write_bytes(png)
                print("Screenshot saved")
            except Exception as e:
                print("ss err:", e)
            # Body text snippet
            try:
                txt = await page.evaluate("() => document.body.innerText")
                print("--- BODY TEXT (first 1500 chars) ---")
                print((txt or "")[:1500])
            except Exception:
                pass
            print("Nav log:")
            for n in nav_log:
                print(" -", n)
        await browser.close()

asyncio.run(main())

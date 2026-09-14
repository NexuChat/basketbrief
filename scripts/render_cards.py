"""Render the demo-film cards from their canonical HTML at 1920x1080."""

import os
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "scripts" / "cards.html"
OUTPUT = ROOT / "video2" / "cards"
CHROME = os.environ.get(
    "BASKETBRIEF_CHROME",
    "/home/dev/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome",
)


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, executable_path=CHROME)
        page = browser.new_page(viewport={"width": 1920, "height": 1080})
        page.goto(SOURCE.as_uri(), wait_until="networkidle")
        page.evaluate("document.fonts.ready")
        for card in page.locator(".card").all():
            target = OUTPUT / f"{card.get_attribute('id')}.png"
            card.screenshot(path=str(target))
            print(target)
        browser.close()


if __name__ == "__main__":
    main()

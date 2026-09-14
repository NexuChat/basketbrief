"""Record the raw footage for the demo film.

Two things this does that the first recorder did not.

The page is laid out at 1280 CSS pixels and rendered into a 1920x1080 frame, so
every word is half again as large as it was. A judge watches in a small player;
a screen recording nobody can read is a screen recording nobody watches.

And it writes a mark for every beat. The film is cut from these marks — the
payoff first, the explanation after — which is only possible if the editor knows
where each moment starts and ends. Nothing here is staged: the marks are taken
while the deployed agent runs, from the captions the app itself writes.
"""
import json, time
from pathlib import Path
from playwright.sync_api import sync_playwright

CHROME = "/home/dev/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome"
URL = "https://basketbrief.mlki.app"
ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "video2" / "raw"
STILLS = ROOT / "video2" / "mark-frames"
ZOOM = "1.5"


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    STILLS.mkdir(parents=True, exist_ok=True)
    marks = []
    t0 = None

    def mark(name):
        marks.append({"name": name, "t": round(time.time() - t0, 2)})
        pg.screenshot(path=str(STILLS/f'{name}.png'))
        print(f"  {marks[-1]['t']:7.2f}  {name}")

    with sync_playwright() as p:
        b = p.chromium.launch(headless=True, executable_path=CHROME,
                              args=["--hide-scrollbars", "--force-device-scale-factor=1"])
        ctx = b.new_context(viewport={"width": 1920, "height": 1080}, device_scale_factor=1,
                            record_video_dir=str(RAW),
                            record_video_size={"width": 1920, "height": 1080})
        pg = ctx.new_page()
        pg.goto(URL, wait_until="networkidle")
        # The first review of a fresh workspace runs on arrival; wait it out so the
        # footage starts on a settled screen rather than a spinner.
        for _ in range(60):
            if "Reading what" not in pg.content():
                break
            pg.wait_for_timeout(2500)
        pg.evaluate(f"document.documentElement.style.zoom='{ZOOM}'")
        pg.wait_for_timeout(2000)

        t0 = time.time()
        mark("start")

        # ── the settled workspace, top of page
        pg.evaluate("window.scrollTo({top:0})")
        mark("idle_top")
        pg.wait_for_timeout(7000)

        # ── the visitor's own receipt
        pg.eval_on_selector("#own", "el => el.scrollIntoView({block:'center'})")
        pg.wait_for_timeout(1600)
        mark("own_panel")
        pg.set_input_files("#own-file", str(ROOT / "basketbrief" / "static" / "sample-receipt.png"))
        mark("own_upload")
        for _ in range(40):
            pg.wait_for_timeout(1000)
            if "Only these numbers" in pg.content() or "did not read" in pg.content():
                break
        pg.wait_for_timeout(1200)
        mark("own_result")
        pg.wait_for_timeout(5000)
        mark("own_hold_end")

        # ── the group's own week
        pg.evaluate("window.scrollTo({top:0})")
        pg.wait_for_timeout(2500)
        mark("workbench")

        # ── the live run, marked by the captions the app writes for itself
        pg.click("[data-action=play-story]")
        mark("play_click")
        seen, last = set(), time.time()
        while time.time() - last < 150:
            try:
                step = pg.eval_on_selector("#story-caption", "el => el.dataset.step || ''")
            except Exception:
                step = ""
            if step and step not in seen:
                seen.add(step)
                mark(f"story_{step}")
                last = time.time()
            if step == "11" and "Both donors receive" in pg.content():
                mark("story_done")
                break
            pg.wait_for_timeout(400)
        pg.wait_for_timeout(1500)

        # ── hold on the completed amendment and its before/after table
        pg.evaluate("window.scrollTo({top:0})")
        pg.wait_for_timeout(1200)
        mark("amendment_head")
        pg.wait_for_timeout(6000)
        try:
            pg.eval_on_selector(".changes", "el => el.scrollIntoView({block:'center'})")
        except Exception:
            pg.evaluate("window.scrollBy({top:520})")
        pg.wait_for_timeout(1400)
        mark("amendment_changes")
        pg.wait_for_timeout(6000)

        # ── immutable donor snapshots, in both languages
        await_role = lambda value: pg.select_option("#role", value)
        await_role("donor_a")
        pg.wait_for_timeout(1400)
        pg.eval_on_selector("#reports", "el => el.scrollIntoView({block:'start'})")
        pg.wait_for_timeout(1000)
        mark("donor_english")
        pg.wait_for_timeout(6000)
        await_role("donor_b")
        pg.wait_for_timeout(1400)
        pg.eval_on_selector("#reports", "el => el.scrollIntoView({block:'start'})")
        pg.wait_for_timeout(1000)
        mark("donor_arabic")
        pg.wait_for_timeout(6000)
        mark("end")

        path = pg.video.path()
        ctx.close()
        b.close()

    (ROOT / "video2" / "marks.json").write_text(json.dumps(
        {"video": str(path), "marks": marks}, indent=2))
    print(f"\nfootage: {path}\nmarks:   {len(marks)}  over {marks[-1]['t']:.1f}s")


if __name__ == "__main__":
    main()

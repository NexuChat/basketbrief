"""Record the demo video by driving the deployed app — no mockups, no re-enactment.

Scene lengths follow the narration, so the picture and the voice stay in step.
The guided run is the same one a visitor triggers; this script only watches it.
"""
import subprocess, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

CHROME = "/home/dev/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome"
URL = "https://basketbrief.mlki.app"
ROOT = Path(__file__).resolve().parent.parent
NARR = ROOT / "video" / "narration"


def secs(n):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "default=nw=1:nk=1", str(NARR / f"{n:02d}.mp3")],
                         capture_output=True, text=True)
    return float(out.stdout.strip())


def main():
    d = {n: secs(n) for n in range(1, 10)}
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True, executable_path=CHROME,
                              args=["--hide-scrollbars", "--force-device-scale-factor=1"])
        ctx = b.new_context(viewport={"width": 1920, "height": 1080}, device_scale_factor=1,
                            record_video_dir=str(ROOT / "video" / "raw"),
                            record_video_size={"width": 1920, "height": 1080})
        pg = ctx.new_page()
        pg.goto(URL, wait_until="networkidle")
        for _ in range(50):
            if "Reading what" not in pg.content():
                break
            pg.wait_for_timeout(3000)
        pg.wait_for_timeout(2500)
        mark = time.time()
        print("scene 1+2: the settled workspace")
        pg.wait_for_timeout(int((d[1] + d[2]) * 1000))

        print("scene 3: press play")
        pg.click("[data-action=play-story]")
        pg.wait_for_timeout(int(d[3] * 1000))

        # the run itself carries scenes 4-7; hold until the closing caption appears
        deadline = time.time() + 150
        while time.time() < deadline:
            pg.wait_for_timeout(1500)
            cap = pg.evaluate("()=>{const e=document.querySelector('#story-caption');return e&&e.classList.contains('show')?e.innerText:''}")
            if cap.startswith("✓"):
                break
        print("run finished at", round(time.time() - mark, 1), "s")
        pg.wait_for_timeout(2500)

        print("scene 8: the donor's copy")
        pg.select_option("#role", "donor_a"); pg.wait_for_timeout(3500)
        pg.mouse.wheel(0, 400); pg.wait_for_timeout(int(d[8] * 1000 * .55))
        pg.select_option("#role", "coordinator"); pg.wait_for_timeout(2500)
        pg.mouse.wheel(0, 300)
        pg.wait_for_timeout(int(d[8] * 1000 * .45))

        print("scene 9: close")
        pg.mouse.wheel(0, -700)
        pg.wait_for_timeout(int(d[9] * 1000))
        path = pg.video.path()
        ctx.close(); b.close()
    print("RAW:", path)
    print(Path(path).stat().st_size, "bytes")


if __name__ == "__main__":
    main()

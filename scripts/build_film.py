"""Cut the demo film from the recorded footage.

The first version was one uncut screen recording with a voice reading a story
over it. This one is edited: the payoff opens the film, the explanation follows,
and every beat is either the product doing something real or a card in the
product's own type. Detail shots are composed onto the film's ground rather than
blown up to full frame, so nothing is ever soft.

Nothing is re-enacted. Every product frame comes from one continuous recording
of the deployed app driving the live agent; the cuts only choose where to look.
"""
import json, subprocess, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
V2 = ROOT / "video2"
FOOT = V2 / "raw" / "page@fd798e97545a6a87bf06d0742ca77a6f.webm"
CARDS = V2 / "cards"
WORK = V2 / "cut"
OFFSET = 10.92          # recorder clock zero sits this far into the footage
VOICE = "en-US-AndrewNeural"
RATE = "+6%"
GROUND = "0x11110f"

def sh(*a, **k):
    return subprocess.run(a, check=True, capture_output=True, text=True, **k)

def dur(p):
    return float(sh("ffprobe", "-v", "error", "-show_entries", "format=duration",
                    "-of", "csv=p=0", str(p)).stdout.strip())

# ── the cut ──────────────────────────────────────────────────────────────
# kind: "shot" takes footage at mark time t for d seconds; "card" holds a still.
# crop (x,y,w,h) composes that region onto the ground at `zoom`, centred.
# Each beat's length is the longer of its planned hold and its narration.
BEATS = [
    dict(k="shot", t=75.6, d=5.0, crop=(400, 252, 1480, 452), zoom=1.26, fade=True,
         vo="Four kits are missing, and BasketBrief will not sign the report until someone says where they went."),
    dict(k="card", img="c-problem", d=6.0,
         vo="Every week, a small aid group has to prove to its donors where the money went."),
    dict(k="card", img="c-who", d=7.4,
         vo="Neighbourhood groups. Food banks. Small nonprofits. The receipts are with one person, the counts with another, and one receipt is always missing."),
    dict(k="shot", t=4.0, d=4.4,
         vo="BasketBrief is the agent that does the chasing."),
    dict(k="card", img="c-own", d=4.4,
         vo="Start with a receipt from your own wallet."),
    dict(k="still", img="own-panel", d=5.0,
         vo="The same deployed agent reads your paper on Amazon Bedrock."),
    dict(k="still", img="own-result", d=9.6,
         vo="Vendor, invoice, line items, added up against the printed total — and the only numbers that could ever enter a ledger from it. Anything else is refused by the code, not by the prompt."),
    dict(k="card", img="c-play", d=3.8,
         vo="Now the group's own week."),
    # a cropped view where the caption would contradict the line being spoken,
    # the full frame where the app's own caption says the same thing
    dict(k="shot", t=27.0, d=5.2, crop=(400, 252, 1480, 452), zoom=1.26,
         vo="One button runs the live agent. It finds the gap — sixty dollars with no receipt — and asks the one person who has it, once."),
    dict(k="shot", t=31.5, d=6.4,
         vo="She answers with a photograph, and Nova Pro reads it on AgentCore Runtime before the review even starts."),
    dict(k="shot", t=46.5, d=5.0, crop=(400, 252, 1480, 452), zoom=1.26,
         vo="Sixty dollars, printed on the paper. Every reported dollar now has a receipt behind it."),
    dict(k="shot", t=50.0, d=5.4,
         vo="One human decision, bound to one version and its content hash. Both donors receive it."),
    dict(k="shot", t=58.2, d=5.2,
         vo="Then the count changes. Eighty-eight, not ninety-two."),
    dict(k="shot", t=76.0, d=6.2, crop=(400, 252, 1480, 452), zoom=1.26,
         vo="A hundred loaded. Eighty-eight out, eight back. Four unaccounted for."),
    dict(k="still", img="gap", d=8.4, fit="width",
         vo="And BasketBrief says what those four are: households that registered at the shelter and have no answer either way. That sentence is written by the reconciliation code, not by the model."),
    dict(k="card", img="c-line", d=6.4,
         vo="The model decides what a source means. The code decides what is allowed."),
    dict(k="card", img="c-arch", d=8.6,
         vo="Strands on Amazon Bedrock. The reader deployed on AgentCore Runtime, the team's vendor history in AgentCore Memory, and a follow-up gate that re-checks the model after its turn."),
    dict(k="card", img="c-measured", d=7.2,
         vo="Seven identical runs. Fifty-three tests, twenty-eight of them adversarial. Three prompt injections refused."),
    dict(k="card", img="c-end", d=6.6, fadeout=True,
         vo="BasketBrief. It chases the evidence, and it will not sign off on four households it cannot account for."),
]


def narrate():
    out = V2 / "vo"
    out.mkdir(parents=True, exist_ok=True)
    for i, b in enumerate(BEATS, 1):
        f = out / f"{i:02d}.mp3"
        if not f.exists():
            sh("edge-tts", "--voice", VOICE, "--rate", RATE, "--text", b["vo"], "--write-media", str(f))
        b["vo_len"] = dur(f)
        b["vo_file"] = f
        # 0.45s of air before the line, 0.7s after, or the planned hold — whichever is longer
        b["len"] = round(max(b["d"], b["vo_len"] + 1.15), 2)
        print(f"  {i:2d}  hold {b['d']:4.1f}  voice {b['vo_len']:5.1f}  → {b['len']:5.1f}")


def compose(b, i):
    """One beat, 1920x1080, 30fps, no audio."""
    out = WORK / f"{i:02d}.mp4"
    n = b["len"]
    if b["k"] == "shot":
        # accurate seek: the page re-renders in place, so a keyframe-only seek
        # lands on a layout that is not the one the beat was chosen for
        src = ["-i", str(FOOT), "-ss", f"{b['t'] + OFFSET:.2f}", "-t", f"{n:.2f}"]
        vf = []
        if b.get("crop"):
            x, y, w, h = b["crop"]
            z = b.get("zoom", 1.0)
            vf += [f"crop={w}:{h}:{x}:{y}",
                   f"scale={int(w*z)//2*2}:{int(h*z)//2*2}:flags=lanczos",
                   f"pad=1920:1080:(ow-iw)/2:(oh-ih)/2:{GROUND}"]
        else:
            vf += ["scale=1920:1080:flags=lanczos"]
        vf += ["fps=30", "format=yuv420p"]
    else:
        img = (CARDS / f"{b['img']}.png") if b["k"] == "card" else (V2 / "stills" / f"{b['img']}.png")
        if b["img"] == "__arch":
            img = ROOT / "docs" / "architecture.png"
        src = ["-loop", "1", "-t", f"{n:.2f}", "-i", str(img)]
        # a still is held, not pushed: the type is the movement
        if b.get("fit") == "width":
            vf = ["scale=1560:-2:flags=lanczos"]
        else:
            vf = ["scale=1920:1000:force_original_aspect_ratio=decrease:flags=lanczos"]
        vf += [f"pad=1920:1080:(ow-iw)/2:(oh-ih)/2:{GROUND}", "fps=30", "format=yuv420p"]
    if b.get("fade"):
        vf.insert(0, "fade=t=in:st=0:d=0.7")
    if b.get("fadeout"):
        vf.append(f"fade=t=out:st={max(0, n-1.1):.2f}:d=1.1")
    sh("ffmpeg", "-y", "-loglevel", "error", *src,
       "-vf", ",".join(vf), "-c:v", "libopenh264", "-b:v", "7000k",
       "-r", "30", "-an", str(out))
    return out


def main():
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True)
    print("narration")
    narrate()
    print("frames")
    clips = [compose(b, i) for i, b in enumerate(BEATS, 1)]
    total = sum(b["len"] for b in BEATS)
    print(f"  {len(clips)} beats, {total:.1f}s")

    lst = WORK / "list.txt"
    lst.write_text("".join(f"file '{c}'\n" for c in clips))
    silent = V2 / "film_silent.mp4"
    sh("ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
       "-i", str(lst), "-c", "copy", str(silent))

    # narration laid onto one timeline at each beat's own offset
    # offsets come from the encoded clips, not the plan: frame rounding would
    # otherwise walk the voice off the picture by the end of the film
    inputs, filters, mixes, at = [], [], [], 0.0
    for i, (b, c) in enumerate(zip(BEATS, clips)):
        inputs += ["-i", str(b["vo_file"])]
        ms = int((at + 0.45) * 1000)
        filters.append(f"[{i}:a]adelay={ms}|{ms}[a{i}]")
        mixes.append(f"[a{i}]")
        at += dur(c)
    chain = ";".join(filters) + ";" + "".join(mixes) + \
        f"amix=inputs={len(BEATS)}:duration=longest:dropout_transition=0,loudnorm=I=-16:TP=-1.5:LRA=11[out]"
    voice = V2 / "film_voice.m4a"
    sh("ffmpeg", "-y", "-loglevel", "error", *inputs,
       "-filter_complex", chain, "-map", "[out]", "-c:a", "aac", "-b:a", "192k", str(voice))

    final = V2 / "BasketBrief-demo.mp4"
    sh("ffmpeg", "-y", "-loglevel", "error", "-i", str(silent), "-i", str(voice),
       "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
       "-shortest", "-movflags", "+faststart", str(final))
    print(f"\n{final}  {dur(final):.1f}s  {final.stat().st_size/1e6:.1f} MB")


if __name__ == "__main__":
    main()

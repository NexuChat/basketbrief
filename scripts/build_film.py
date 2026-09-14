"""Cut the demo film from the recorded footage.

The first version was one uncut screen recording with a voice reading a story
over it. This one is edited: the payoff opens the film, the explanation follows,
and every beat is either the product doing something real or a card in the
product's own type. Detail shots are composed onto the film's ground rather than
blown up to full frame, so nothing is ever soft.

The main story comes from a continuous recording of the deployed app driving the
live agent. Team cutaways are actual screenshots from the separate-account staging
journey. The fictional participants are automated for demonstration; product screens
are not fabricated.
"""
import json, subprocess, shutil, hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
V2 = ROOT / "video2"
CARDS = V2 / "cards"
WORK = V2 / "cut"
VOICE = "en-US-AndrewNeural"
RATE = "+6%"
GROUND = "0x11110f"

def sh(*a, **k):
    return subprocess.run(a, check=True, capture_output=True, text=True, **k)

def dur(p):
    return float(sh("ffprobe", "-v", "error", "-show_entries", "format=duration",
                    "-of", "csv=p=0", str(p)).stdout.strip())


recording = json.loads((V2 / "marks.json").read_text())
FOOT = Path(recording["video"])
MARK = recording.get('video_marks') or {item["name"]: item["t"] for item in recording["marks"]}
# Video capture begins before the recorder's clock. The pre-roll is exactly the
# part of the file before the final recorder mark.
OFFSET = 0 if recording.get('video_marks') else max(0.0, dur(FOOT) - max(MARK.values()))

# ── the cut ──────────────────────────────────────────────────────────────
# kind: "shot" takes footage at mark time t for d seconds; "card" holds a still.
# crop (x,y,w,h) composes that region onto the ground at `zoom`, centred.
# Each beat's length is the longer of its planned hold and its narration.
BEATS = [
    dict(k="card", img="c-payoff", d=5.2, fade=True,
         vo="The report was already with both donors. Then the count changed. BasketBrief followed through."),
    dict(k="card", img="c-problem", d=6.0,
         vo="Small aid groups collect receipts and delivery counts from different volunteers. A late correction leaves the coordinator chasing answers and keeping both donor reports consistent."),
    dict(k="card", img="c-who", d=7.4,
         vo="BasketBrief is for Amal, a coordinator. Rana has the receipt. Sami has the counts. The agent carries one evidence trail across both donors."),
    dict(k="shot", t=MARK["idle_top"], d=4.4,
         vo="BasketBrief is a Strands agent that owns the follow-up work."),
    # a cropped view where the caption would contradict the line being spoken,
    # the full frame where the app's own caption says the same thing
    dict(k="shot", t=MARK["story_2"], d=5.2, crop=(400, 252, 1480, 452), zoom=1.26,
         vo="It finds sixty dollars without a receipt and asks the person who can resolve it. One answer serves both reports."),
    dict(k="shot", t=MARK["story_3"], d=6.4,
         vo="Rana answers with a photograph. Nova Pro reads it through AgentCore Runtime before the review starts."),
    dict(k="shot", t=MARK["story_4"], d=5.0, crop=(400, 252, 1480, 452), zoom=1.26,
         vo="The transcription states sixty dollars. The original stays visible for review. Receipt support is not proof of payment."),
    dict(k="shot", t=MARK["story_5"], d=5.4,
         vo="Amal approves one exact version, bound to its content hash. Both donors receive immutable inbox snapshots."),
    dict(k="shot", t=MARK["story_7"], d=5.2,
         vo="Then the count changes. Eighty-eight, not ninety-two."),
    dict(k="shot", t=MARK["story_8"], d=6.2, crop=(400, 252, 1480, 452), zoom=1.26,
         vo="A hundred loaded. Eighty-eight delivered. Eight returned. Four unaccounted for, and the old approval is refused."),
    dict(k="shot", t=MARK["story_9"], d=6.2,
         vo="That discrepancy says nothing about households. BasketBrief asks Sami to check storage instead of inventing impact."),
    dict(k="shot", t=MARK["story_10"], d=6.2,
         vo="Sami confirms twelve returned. The figures reconcile, and both changes are shown before approval."),
    dict(k="shot", t=MARK["donor_english"], d=5.4,
         vo="Northstar keeps the original report and receives the amendment beside it."),
    dict(k="shot", t=MARK["donor_arabic"], d=5.4,
         vo="The Arabic donor receives the same approved evidence and exact changes."),
    dict(k="still", img="team-notifications", d=6.4,
         vo="Beyond the guided story, teammates sign in separately. New evidence and questions reach the people responsible."),
    dict(k="still", img="team-source", d=6.4,
         vo="A requested receipt completes the original expense, without counting it twice. Reviewers inspect the source. Donors receive only the approved snapshot."),
    dict(k="card", img="c-line", d=6.4,
         vo="The model decides what a source means. The code decides what is allowed."),
    dict(k="card", img="c-arch", d=8.6,
         vo="Strands and Nova choose tools. AgentCore Runtime reads images, Memory carries vendor history, and deterministic code owns facts, roles, follow-ups, and approval validity."),
    dict(k="card", img="c-measured", d=7.2,
         vo="One hundred twenty-one tests pass, including thirty adversarial boundary cases. Separate team accounts completed the handoff, and a private Gmail import passed its checks."),
    dict(k="card", img="c-end", d=6.6, fadeout=True,
         vo="Fictional participants. A live system. BasketBrief keeps the follow-up moving and every correction visible, so the people doing the work can stay with the work."),
]


def narrate():
    out = V2 / "vo"
    out.mkdir(parents=True, exist_ok=True)
    for i, b in enumerate(BEATS, 1):
        f = out / f"{i:02d}.mp3"
        key=hashlib.sha256((VOICE+RATE+b['vo']).encode()).hexdigest()
        cache=f.with_suffix('.sha256')
        if not (f.exists() and cache.exists() and cache.read_text()==key):
            sh("edge-tts", "--voice", VOICE, "--rate", RATE, "--text", b["vo"], "--write-media", str(f))
            cache.write_text(key)
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
       "-af", "apad", "-shortest", "-movflags", "+faststart", str(final))
    print(f"\n{final}  {dur(final):.1f}s  {final.stat().st_size/1e6:.1f} MB")


if __name__ == "__main__":
    main()

# BasketBrief final film — 14 September 2026

The final cut is **3:44** (223.733 seconds), 1920×1080, 30 fps, H.264/AAC.
[Download the MP4](https://basketbrief.mlki.app/static/BasketBrief-polished-20260914.mp4) · [Watch with captions](https://basketbrief.mlki.app/static/film.html)

The [official rules](https://agentsforhumans.devpost.com/rules) allow **five minutes**, including slides, screen recording and voiceover. A public YouTube or Vimeo video is required for the submission. Three minutes is not the maximum. The owner will upload this replacement; the submission still links the earlier YouTube film until its URL is updated.

## Story and evidence

The opening introduces the relief coordinator’s paperwork problem and BasketBrief’s purpose. It then names the fictional team and follows one example in chronological order. The count changes only after the viewer has seen the first approved report; it is an event inside the demonstration, not a reference to an earlier submission or video:

1. Introduce the coordinator, contributors and two recipients.
2. Find USD 60 without a receipt and show the question in Rana's actual inbox.
3. Upload the source, review the reading, approve and show the first donor copy.
4. Introduce a later update from Sami, explicitly within this example. Four kits need an explanation; the previous approval cannot authorize the changed report.
5. Show the question in Sami's inbox and his answer: 12 returned.
6. Review both changes and deliver the amendment in English and Arabic.
7. Show the separate-account team workflow, explain the architecture, and state the validation boundaries.

Main application images and video come from one fresh run of the public app. The edit uses recorded actions, cropped screenshots, chapter headings and original motion graphics. The team cutaways are actual screenshots from a separate-account staging test. Fictional participant replies and human approvals are automated for demonstration; agent inference and application operations execute live. Waiting periods are edited, so the film is not a latency benchmark.

The recording verified stale approval returns HTTP 409, the final counts are 88 delivered and 12 returned, each donor retains two versions, and the browser reports zero JavaScript errors. The last full suite passed 121 tests. No private Gmail content appears. Architecture cards are illustrations; the evidence card summarizes tests, not a customer study.

## Editorial references

[Presentation review](WINNER-PRESENTATION-REVIEW.md) records the winning projects, sources actually inspected, access limits and applicable lessons. No competitor footage, audio, graphics or script is included. The score is generated specifically for this film; narration uses the Andrew neural voice. Captions are supplied as VTT and SRT, with estimated phrase timing.

## Upload metadata

**Title:** BasketBrief — Evidence connected. People informed. | Agents for Humans

**Thumbnail:** [Download the 1280×720 cover](https://basketbrief.mlki.app/static/BasketBrief-video-cover.jpg). Source artwork: `docs/video-cover.html`. Checked at both full size and 320×180.

**Visibility:** Public

**Description:**

BasketBrief helps relief coordinators chase missing evidence, reconcile late corrections and keep every donor on the approved version. This demonstration follows one complete receipt-to-amendment workflow, including English and Arabic donor reports and a separate-account team workspace.

Built with Strands Agents SDK, Amazon Bedrock Nova Pro, AgentCore Runtime and AgentCore Memory. Fictional demonstration participants; real agent and application execution. No field pilot or measured human-time savings. Gmail app-password import was tested privately; Google/Microsoft OAuth and external SMTP delivery are not live-verified.

Live demo: https://basketbrief.mlki.app
Source and verification: https://github.com/NexuChat/basketbrief

## Rebuild and verify

The production scripts are `scripts/record_story_v3.py`, `scripts/align_story_v3.py` and `scripts/film_v3.py`. They require Playwright with Chromium, FFmpeg/ffprobe, NumPy, Pillow and edge-tts. Record the fictional public workspace, align the reference captures against its encoded WebM, then generate narration and render the edit:

```sh
.venv/bin/python scripts/record_story_v3.py
.venv/bin/python scripts/align_story_v3.py
.venv/bin/python scripts/film_v3.py voice
.venv/bin/python scripts/film_v3.py render
```

The two team screenshots in `video2/stills` are from the prior separate-account staging test. Raw recording, intermediate frames and cached narration remain in ignored `video3/`. Do not include private documents or credentials in publishing artifacts. Check the final encode, not only the source screenshots: the review caught and removed a crop that clipped editorial titles. See [FILM-VERIFICATION.json](FILM-VERIFICATION.json) for the delivered file hash and checks.

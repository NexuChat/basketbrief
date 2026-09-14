# BasketBrief replacement demo film

Official maximum: **5 minutes**, verified on 2026-09-14 in the [Agents for Humans rules](https://agentsforhumans.devpost.com/rules), Submission Requirements. The rules permit slides, screen recordings and voiceover and require a working demonstration plus the problem, audience and reason it matters. The video must be public on YouTube or Vimeo.

Editorial duration follows the evidence needed for a clear story; **three minutes is not a limit**. Use up to roughly 4:45 when useful, leaving encoding headroom below the official 5:00 maximum. Do not cut important proof to hit an arbitrary three-minute target or add filler to reach five minutes. Export at 1920×1080 and verify the final encoded duration with ffprobe.

The film shows the post-review behavior and avoids the withdrawn claims in the first recording. Main product footage comes from one continuous browser-driven run of the deployed application. Two actual screenshots from the separate-account staging journey show team notifications and source review. Fictional participants are automated for demonstration. Cards explain context and architecture; no product screen is fabricated.

## Story

Open on the amendment payoff: the donor report was already sent, then the field count changed. BasketBrief followed up until the discrepancy closed and delivered a new approved version without changing the old one.

Then explain the person and problem, show the receipt follow-up and first delivery, return to the late correction, and finish with the exact before/after table.

## Voiceover and shot plan

| Beat | Picture | Voiceover |
|---|---|---|
| 1 | Opening card using the verified amendment figures: delivered 92 → 88, returned 8 → 12 | The report was already with both donors. Then the count changed. BasketBrief followed through. |
| 2 | Problem card | Small aid groups collect receipts and delivery counts from different volunteers. A late correction leaves the coordinator chasing answers and keeping both donor reports consistent. |
| 3 | Who card: Amal, Rana, Sami, two donors | BasketBrief is for Amal, a coordinator. Rana has the receipt. Sami has the counts. The agent carries one evidence trail across both donors. |
| 4 | Fresh workspace, three sources | BasketBrief is a Strands agent that owns the follow-up work. |
| 5 | Missing receipt question in Rana's inbox | It finds sixty dollars without a receipt and asks the person who can resolve it. One answer serves both reports. |
| 6 | Receipt image and transcription | Nova Pro reads the synthetic receipt through AgentCore Runtime. The original image stays available for human review. |
| 7 | First approval and two donor inboxes | Amal approves one exact version. The content hash binds that approval, and both donors receive immutable snapshots. |
| 8 | Correction to 88 and HTTP 409 | After delivery, Sami corrects ninety-two to eighty-eight. The old approval cannot authorize a report nobody reviewed. |
| 9 | Four-kit discrepancy and question to Sami | Four kits are now unaccounted for. That does not tell us how many households were affected, so BasketBrief asks Sami to check the records. |
| 10 | Sami answers returned=12; issue closes | Sami confirms twelve returned. The figures reconcile without inventing impact. |
| 11 | Before/after table and both donor amendments | Amal sees both changes, approves the amendment, and each donor receives the new snapshot beside the original. |
| 12 | Architecture card | Strands and Nova choose tools. AgentCore Runtime reads images, Memory carries vendor history, and deterministic code owns facts, roles, follow-ups, and approval validity. |
| 13 | Evidence card | One hundred twenty-one tests pass. Separate contributor, coordinator and donor accounts completed a live handoff. A private Gmail PDF import passed duplication and access checks. |
| 14 | Scope/end card | Fictional participants. A live system. BasketBrief keeps the follow-up moving and every correction visible, so the people doing the work can stay with the work. |

## Required visual proof

- The engine label reads **Live agent · Strands + Bedrock**.
- The receipt reader shows where the image was read.
- The first report is visible in both donor inboxes before the correction.
- Reuse of the first approval returns HTTP 409 or the equivalent visible caption.
- The reconciliation question is visible in Sami's role.
- The amendment table shows both changed fields.
- Each donor inbox contains the original and amended snapshot.
- The English disclosure states that the scenario is synthetic and field counts are not independently verified.

## Claims excluded

- No “four households” claim.
- No “41 manual acts → 2” comparison.
- No statement that a live model refused three prompt injections.
- No claim that OCR proves what the original pixels contain.
- No claim of real users, savings, delivery impact, or external donor delivery.

## Upload metadata

- **Title:** `BasketBrief — the report changed, and the agent followed through | Agents for Humans`
- **Visibility:** Public
- **Description:** `BasketBrief follows missing evidence through two approved donor reports, then handles a late field correction end to end. Built with the Strands Agents SDK, Amazon Bedrock Nova Pro, AgentCore Runtime, and AgentCore Memory. Fictional scenario; measured system behavior, no claimed human-time or aid impact. Live demo: https://basketbrief.mlki.app Code: https://github.com/NexuChat/basketbrief`

## Rebuild and verify

Optional tools: install `.[video]`, Chromium, and FFmpeg/ffprobe. `scripts/record_v2.py` records the public guided demonstration and captures reference screenshots at every mark. `scripts/align_film_marks.py` locates those screenshots in the encoded video, avoiding a misleading estimate based on raw duration. `scripts/render_cards.py` renders the cards; `scripts/build_film.py` cuts and narrates the film; `scripts/caption_film.py` writes optional English VTT/SRT captions from the encoded beat lengths. Existing voice files are reused only when their text, voice and rate hashes match.

The two team screenshots in `video2/stills` come from the actual separate-account test. `team-notifications.png` is also published as `docs/team-workspace.png`; `team-source.png` shows the synthetic receipt in the review dialog. Raw footage, credentials and private test records are not committed. Inspect the cut visually, check the English/Arabic donor shots against narration, and verify the encoded file remains at most 300 seconds. Website hosting alone does not satisfy the competition's public YouTube/Vimeo requirement.

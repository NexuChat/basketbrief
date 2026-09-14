# BasketBrief — demo video

Target 3:40, hard limit 5:00. Screen recording of the deployed app at basketbrief.mlki.app driving the real agent on Amazon Bedrock — no mockups, no pre-recorded results. English voiceover. Synthetic data labelled on screen throughout.

| # | Scene | Narration |
|---|---|---|
| 1 | The settled coordinator screen: **“One thing is still missing.”** Cursor rests on the amber tile: **$60 still needs a receipt**. | Friday. A five-person food-aid team owes two donors a report on last week's distribution. Twelve hundred dollars of the spending has a receipt behind it. Sixty dollars does not. BasketBrief already noticed, and it has already asked the one person who has it. |
| 2 | Scroll the three sources: food receipt, transport expense claim, field update. Then the right-hand panel: **“Asked once. Not asked again.”** with Rana's name and the question. | These three sources came from two different people. The agent read each one, recorded only the amounts the sources actually state, and worked out what was missing. Then it went straight to Rana in finance — not to the coordinator — and asked once. One answer will update both donor reports. |
| 3 | Switch role to **Rana · Finance**. Upload a photograph of a receipt. The timeline shows Amazon Nova Pro reading it; the transcription appears as the source text. | Rana has the receipt on her phone. She uploads the photograph. Before the agent reviews anything, Amazon Nova Pro reads the picture: vendor, invoice number, two line items, sixty dollars. The code adds the line items up against the printed total, and the transcription becomes the source text — so an amount can only enter the ledger if it was actually printed on the paper. |
| 4 | Back as **Amal**. Tiles now read $1,260 supported, $0 waiting. Panel: “Ready for your eyes.” Click **Approve**. | Back on the coordinator's screen: every reported dollar now has a receipt behind it, and version two is ready. This is the only decision she is asked to make. Her approval is bound to this exact version and its content hash. |
| 5 | Deliveries appear. Switch to **Northstar Foundation** and open the received report. | Both donors have it, each with their own delivery receipt, each able to open only what was sent to them. Notice what the report does not say: ninety-two baskets are *field-reported* delivered. The agent never claims to have verified that aid reached anyone. |
| 6 | Switch to **Sami · Field team**. Send: *“Correction: we recounted at the warehouse. 88 baskets were delivered, not 92.”* | Then, hours after the reports went out, the field team recounts. This is the moment that usually costs a coordinator her evening. |
| 7 | Back as **Amal**: headline reads **“A correction changed the figures.”** Delivered count is 88. The issue box states the arithmetic gap. Panel: **“Your approval no longer fits.”** Attempt to reuse the old approval — refused. | The figures move. Both reports are redrafted. The arithmetic no longer closes — eighty-eight delivered plus eight returned against a hundred loaded — so BasketBrief says exactly that instead of quietly picking a number. And the approval bound to version two is refused. It cannot be reused for a version nobody read. |
| 8 | Architecture diagram, cursor tracing: contributors → worker transcribes → Strands agent loop → guards in code → follow-up gate → approval → donor inboxes. | One Strands agent on Amazon Nova Pro. The model decides what a source means, what is missing and who to ask. The code decides what is allowed: amounts must appear in their source, four different basket facts never collapse into one, and a known gap is re-checked after the model's turn — because the model does not always remember to ask, and the promise shouldn't depend on it. |
| 9 | The finished screen. Title card: **BasketBrief — chases the missing evidence, then delivers the donor report.** | Four runs of this exact journey produced identical figures. It also runs with no cloud credentials at all. BasketBrief. For the teams who spend their evening proving they did the work they already did. |

## Production

- `scripts/record_demo.py` drives the deployed app with Playwright at 1920×1080 and writes one clip per scene.
- `edge-tts --voice en-US-AndrewNeural` per scene; each clip is padded to its narration length.
- ffmpeg concatenates, mixes narration, normalises to −16 LUFS, H.264 yuv420p 30 fps, AAC 48 kHz.

## YouTube

- Visibility **Public**, not made for kids, embedding on, category Science & Technology, language English.
- Title: `BasketBrief — chases the missing evidence, then delivers the donor report | Agents for Humans`
- Verify in a private window before pasting the URL into Devpost.

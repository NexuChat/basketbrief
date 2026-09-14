# BasketBrief — demo video

**Delivered:** `BasketBrief-demo.mp4` — 2:47 (166.6 s), 1920×1080, H.264 / AAC, 15.2 MB.

Screen recording of the deployed app at basketbrief.mlki.app driving the real agent on Amazon Bedrock — no mockups, no pre-recorded results. English voiceover. Synthetic data labelled on screen throughout.

The first thing the viewer sees is not our scenario. It is an invitation to put their own receipt through the same reader, because the fastest way to be believed is to let someone test the claim on paper we have never seen.

| # | Scene | Narration |
|---|---|---|
| 1 | Cold open on the coordinator screen: **“Four households with no answer.”** Hold on the tiles — 88 of 100 loaded, 8 returned. | The water went down on Tuesday. By Thursday a neighbourhood group had handed out a hundred relief kits, paid for by two small donors who — reasonably — want to know what happened to their money. |
| 2 | The own-receipt panel, **“Before the story, try it on something of yours.”** A real receipt is dropped in; Nova Pro reads it on AgentCore Runtime; vendor, invoice, date, printed total, line-item sum and the chip row of *only* the numbers that could be recorded. | Before any of that, try it on something of your own. Drop in a real receipt from your wallet and the same agent reads it: vendor, invoice, line items. It adds them up against the printed total, and it shows you the only numbers that could ever enter a ledger from your paper. Anything else is refused by the code, not by the prompt. |
| 3 | Scroll to the workbench: three sources from two people, $1,200 supported, $60 waiting on a receipt. | Now the group's own week. BasketBrief has read three sources from two different people, recorded only the amounts each one states, and found the gap: twelve hundred dollars has a receipt behind it, sixty does not. |
| 4 | Click **Play the whole story**. The live-agent strip lights up; the timeline starts writing. | One button runs the real thing. Same agent, same live calls, nothing recorded. |
| 5 | The question goes to **Rana · Supplies & receipts** — once. She answers with a photograph; the timeline shows `read_on: agentcore-runtime` and the transcription becomes the source text. | It goes straight to Rana, who keeps the receipts, and asks once. She replies with a photograph, and Amazon Nova Pro reads the picture on AgentCore Runtime before the review even starts. Sixty dollars, printed on the paper. |
| 6 | Tiles flip to $1,260 supported / $0 waiting. **Approve** — bound to the version and its content hash. Two deliveries land, each with its own receipt. | Every reported dollar now has a receipt behind it. This is the only decision the coordinator is asked to make, and her approval is bound to this exact version and its content hash. Both donors receive it, each with their own delivery receipt. |
| 7 | Switch to **Sami · Delivery team**. The correction is sent: *“We recounted at the church hall. 88 delivered, not 92.”* | Then Sami recounts at the church hall. Eighty-eight delivered, not ninety-two. |
| 8 | Back as Amal. Headline rewrites itself to **“Four households with no answer.”** The gap sentence is on screen; the stale approval is refused. | Here is the part that matters. A hundred kits were loaded. Eighty-eight went out and eight came back. Four are unaccounted for — and those four are households that registered at the shelter and have no answer either way. BasketBrief says that in those words instead of quietly picking a number, and the approval bound to the delivered version is refused. |
| 9 | Architecture diagram: contributors → AgentCore Runtime reader → Strands agent loop → guards in code → follow-up gate → approval → donor inboxes, with AgentCore Memory off to the side. | One Strands agent on Amazon Nova Pro. The reader runs on Bedrock AgentCore Runtime; the team's vendor history lives in AgentCore Memory, because a workspace lasts one distribution and a team does not. The model decides what a source means and who to ask. The code decides what is allowed. |
| 10 | End card: **BasketBrief chases the evidence** · basketbrief.mlki.app · github.com/NexuChat/basketbrief · “All organisations, people, receipts and figures in this demo are fictional.” | Twenty-eight deliberate defects — invented amounts, prompt injections inside field evidence, a receipt whose lines disagree with its total — all refused, and one of them found a real defect in our own guard. Seven identical runs. No human baseline was timed, so we claim no hours saved. BasketBrief: it chases the evidence, and it will not sign off on four households it cannot account for. |

## Production

- `scripts/record_demo.py` drives the deployed app with Playwright at 1920×1080 and writes one clip per scene; the run itself finished in 91.7 s.
- `edge-tts --voice en-US-AndrewNeural` per scene; each clip is padded to its narration length.
- ffmpeg concatenates, mixes narration, normalises to −16 LUFS, H.264 (libopenh264) yuv420p 30 fps, AAC 48 kHz.
- Frames extracted after assembly and reviewed one by one to confirm every scene reads correctly.

## YouTube

- Visibility **Public**, not made for kids, embedding on, category Science & Technology, language English.
- Title: `BasketBrief — chases the missing evidence, then delivers the donor report | Agents for Humans`
- Verify in a private window before pasting the URL into Devpost.

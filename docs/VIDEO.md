# BasketBrief — demo film

**Delivered:** `BasketBrief-demo.mp4` — 2:17 (136.6 s), 1920×1080, H.264 / AAC, 9.1 MB.

The first cut was one uncut screen recording with a voice reading a story over it:
a third of it was a still frame, and the page was recorded at a width that made
every word unreadable in a small player. This one is edited.

Three things changed, and they are the whole difference:

- **The page is laid out at 1280 CSS pixels inside a 1920×1080 frame,** so every
  word is half again as large. A judge watches in a small player.
- **It is cut.** Nineteen beats, hard cuts, the payoff first and the explanation
  after. Detail shots are composed onto the film's own ground rather than blown
  up, so nothing is soft.
- **The cards are the product's typography,** rendered in a browser against the
  same stylesheet the app serves — so the film and the app are one object.

Nothing is re-enacted. Every product frame comes from one continuous recording of
the deployed app driving the live agent on Amazon Bedrock; the cuts only choose
where to look. Where the app writes its own caption, the narration says the same
thing; where it would say something else, the shot is cropped so it is not on
screen.

## The cut

| # | Picture | Narration |
|---|---|---|
| 1 | Payoff, punched in: **“Four households with no answer.”** 88 · $1,260 · $0 | Four kits are missing, and BasketBrief will not sign the report until someone says where they went. |
| 2 | Card — *the evening this takes* | Every week, a small aid group has to prove to its donors where the money went. |
| 3 | Card — *who it is for* | Neighbourhood groups. Food banks. Small nonprofits. The receipts are with one person, the counts with another, and one receipt is always missing. |
| 4 | The settled workspace | BasketBrief is the agent that does the chasing. |
| 5 | Card — *start with your own paper* | Start with a receipt from your own wallet. |
| 6 | The own-receipt panel | The same deployed agent reads your paper on Amazon Bedrock. |
| 7 | The read: vendor, invoice, line-item sum, the chip row | Vendor, invoice, line items, added up against the printed total — and the only numbers that could ever enter a ledger from it. Anything else is refused by the code, not by the prompt. |
| 8 | Card — *now the group's own week* | One button. The live agent. |
| 9 | Hero: **One thing is still missing** · $60 | One button runs the live agent. It finds the gap — sixty dollars with no receipt — and asks the one person who has it, once. |
| 10 | Full frame, the app's caption 3/8 | She answers with a photograph, and Nova Pro reads it on AgentCore Runtime before the review even starts. |
| 11 | Hero: **The evidence is in order** · $1,260 · $0 | Sixty dollars, printed on the paper. Every reported dollar now has a receipt behind it. |
| 12 | Full frame, the app's caption 5/8 | One human decision, bound to one version and its content hash. Both donors receive it. |
| 13 | Full frame, the app's caption 7/8 | Then the count changes. Eighty-eight, not ninety-two. |
| 14 | Hero: **Four households with no answer** · 88 | A hundred loaded. Eighty-eight out, eight back. Four unaccounted for. |
| 15 | The gap sentence alone, full width | And BasketBrief says what those four are: households that registered at the shelter and have no answer either way. That sentence is written by the reconciliation code, not by the model. |
| 16 | Card — *where the line is drawn* | The model decides what a source means. The code decides what is allowed. |
| 17 | Card — one cycle, end to end | Strands on Amazon Bedrock. The reader deployed on AgentCore Runtime, the team's vendor history in AgentCore Memory, and a follow-up gate that re-checks the model after its turn. |
| 18 | Card — *measured, not claimed* | Seven identical runs. Fifty-three tests, twenty-eight of them adversarial. Three prompt injections refused. |
| 19 | End card | BasketBrief. It chases the evidence, and it will not sign off on four households it cannot account for. |

## Production

- `scripts/record_v2.py` drives the deployed app with Playwright, marks every beat
  off the app's own caption state, and writes `video2/marks.json`.
- `scripts/cards.html` holds the cards; they are screenshotted in the browser so
  they carry the real fonts and the real colour tokens.
- `scripts/build_film.py` cuts, composes, narrates and mixes. Narration offsets
  are taken from the encoded clips, not the plan, so the voice cannot walk off
  the picture.
- Voice `edge-tts en-US-AndrewNeural` at +6%. Loudness normalised to −16 LUFS.
  H.264 (libopenh264) yuv420p 30 fps, AAC 48 kHz.
- Every beat was checked as an extracted frame before the film was published.

## YouTube

- Visibility **Public**, not made for kids, embedding on, category Science & Technology, language English.
- Title: `BasketBrief — chases the missing evidence, then delivers the donor report | Agents for Humans`
- Verify in a private window before pasting the URL into Devpost.

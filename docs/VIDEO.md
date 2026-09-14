# BasketBrief replacement demo film

Target: 2–3 minutes, 1920×1080, public YouTube or Vimeo, under the competition's five-minute limit.

The film must show the post-review behavior and avoid the withdrawn claims in the first recording. Product footage comes from one continuous browser-driven run of the deployed application. Cards may explain context and architecture; they must not re-enact product behavior.

## Story

Open on the amendment payoff: the donor report was already sent, then the field count changed. BasketBrief followed up until the discrepancy closed and delivered a new approved version without changing the old one.

Then explain the person and problem, show the receipt follow-up and first delivery, return to the late correction, and finish with the exact before/after table.

## Voiceover and shot plan

| Beat | Picture | Voiceover |
|---|---|---|
| 1 | Amendment table: delivered 92 → 88, returned 8 → 12 | The report was already with both donors. Then the count changed. BasketBrief followed through. |
| 2 | Problem card | Small aid groups lose hours chasing receipts, reconciling field messages, and keeping donor reports consistent. |
| 3 | Who card: Amal, Rana, Sami, two donors | Amal coordinates the work. The receipt is with Rana. The distribution count is with Sami. Two donors need the same evidence. |
| 4 | Fresh workspace, three sources | BasketBrief is a Strands agent that owns the follow-up work. |
| 5 | Missing receipt question in Rana's inbox | It finds sixty dollars without a receipt and asks the person who can resolve it. One answer serves both reports. |
| 6 | Receipt image and transcription | Nova Pro reads the synthetic receipt through AgentCore Runtime. The original image stays available for human review. |
| 7 | First approval and two donor inboxes | Amal approves one exact version. The content hash binds that approval, and both donors receive immutable snapshots. |
| 8 | Correction to 88 and HTTP 409 | After delivery, Sami corrects ninety-two to eighty-eight. The old approval cannot authorize a report nobody reviewed. |
| 9 | Four-kit discrepancy and question to Sami | Four kits are now unaccounted for. That does not tell us how many households were affected, so BasketBrief asks Sami to check the records. |
| 10 | Sami answers returned=12; issue closes | Sami confirms twelve returned. The figures reconcile without inventing impact. |
| 11 | Before/after table and both donor amendments | Amal sees both changes, approves the amendment, and each donor receives the new snapshot beside the original. |
| 12 | Architecture card | Nova Pro chooses tools. Code owns typed facts, arithmetic, roles, follow-up delivery, report versions, and approval validity. AgentCore Runtime reads images; AgentCore Memory carries an advisory vendor history. |
| 13 | Evidence card | Seventy-six tests pass. Three consecutive live staging journeys completed in sixty-three to sixty-six seconds with four donor snapshots and no browser errors. |
| 14 | Scope/end card | The scenario is fictional. We measured system behavior, not human time or aid impact. BasketBrief: the report was sent, then the count changed, and the work still got finished. |

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

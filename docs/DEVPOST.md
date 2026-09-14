# BasketBrief

**Tagline:** Chases the missing evidence, then delivers the donor report.

**Track:** Good Neighbor Agents · **Built with:** Strands Agents SDK, Amazon Bedrock (Amazon Nova Pro — text and vision), Python, FastAPI, SQLite, Cloudflare Tunnel

**Live demo:** https://basketbrief.mlki.app — no login, no setup, a fresh fictional workspace per visitor
**Code:** https://github.com/NexuChat/basketbrief

---

## Inspiration

Small aid organisations run on three or four people. Amal coordinates one: five staff, one office, and a distribution every week. The money comes from donors who — reasonably — want to know what happened to it, and each of them wants it framed slightly differently.

So every week ends the same way. Receipts are with the finance volunteer. Delivery counts are in a message from the field team. One receipt is missing and nobody is sure who has it. Amal becomes a switchboard: ask Rana, wait, re-ask, ask Sami, wait, then add it all up twice and write two reports that must not contradict each other. Then, at 9pm on the day the reports went out, the field team recounts at the warehouse and the number changes.

That last part is the one that hurts. A correction after the reports are out means going back through everything by hand and hoping nothing was missed.

## What it does

BasketBrief is a background agent that owns the follow-up work.

1. **Reads what arrived** — messages, expense claims, receipts, and **photographs of receipts**, which Amazon Nova Pro transcribes before the review starts. The transcription becomes the source text, so an amount can only enter the ledger if it was printed on the paper.
2. **Records only what a source states.** `$1,200` of food spending has a receipt behind it. `$60` of transport spending was reported without one. Those are two different facts, and the reports say so.
3. **Asks the one person who has the gap — once.** Not Amal. Rana gets the question directly, and the single answer updates both donor reports. A question already open is never asked again.
4. **Recalculates in code.** Budget, reported spending, and receipt-supported spending are separate columns. Baskets loaded, delivered, returned, and unique households are four different facts; the agent is not allowed to turn one into another.
5. **Drafts one report per donor** — English for one, Arabic for the other — from stored facts. The model writes the sentences; it never writes the figures.
6. **Waits for one human decision.** Amal approves one exact version, bound to its content hash and its recipients. Unresolved items have to be acknowledged, not skipped.
7. **Delivers** to each donor's inbox with its own receipt. A donor can open only what was sent to them, and it stays exactly as it was sent.
8. **Then the correction arrives.** *"We recounted. 88 delivered, not 92."* The figures move, both reports are redrafted, the arithmetic gap is stated plainly — *88 delivered + 8 returned vs 100 loaded, 4 unaccounted for* — and the approval bound to version 2 is **refused**. It cannot be reused for a version Amal never read.

## How we built it

One Strands `Agent` on `BedrockModel` (`us.amazon.nova-pro-v1:0`, temperature 0), seven tools, a sequential tool executor, and a hook that caps tool calls and wall time so a confused turn cannot run away. The interesting part is the division of labour:

**The model decides** what a source means, what is missing, who to ask, how to word the question and the report.
**The code decides** what is allowed: an amount must literally appear in its source; a field the source does not state is dropped rather than invented; loaded/delivered/returned/households never collapse into each other; contributor text is untrusted data, so an instruction inside a field message is evidence, not a command.

Two pieces exist because we measured the model failing:

- **A follow-up gate.** Nova Pro does not always remember to ask. After the model's turn, code recomputes the known gaps and, if one has no open question, hands it back to the agent once. The agent still chooses the wording; the system guarantees the gap is chased.
- **Transcription before the review.** The model also does not always remember to look at an attached photograph. So the worker transcribes every attachment before the agent runs. Reading a receipt is not a judgement call.

Role-scoped capability links give every contributor and donor their own workspace view, which is why the demo needs no email account, no bot and no setup from a judge.

## Challenges we ran into

**A correction was silently lost.** Our guard refused any number not literally present in the source. A correction saying *"88 delivered, not 92 — four more came back"* implies 12 returned, and 12 is not in the text, so the whole correction was refused and the agent deferred it. The safe-looking rule was destroying the most important event in the product. It now drops the unsupported field, records what the source does state, and raises the arithmetic gap as a visible issue instead of pretending the numbers reconcile.

**`EventStreamError` under load.** A boto3 client created per call inside a worker thread broke Bedrock's response stream. One client per thread fixed it; four consecutive end-to-end runs since then, zero stream errors.

**Arabic.** Nova Pro reads printed Latin-script receipts exactly in our fixtures — it caught a planted total mismatch on the first try — but it hallucinates Arabic wording. We tested this before designing around it, so the prompt asks for Latin-script text and returns null rather than guessing. Stated as a measured limit, not hidden.

## Accomplishments we're proud of

Four consecutive full journeys against the deployed app produced identical figures at every step. The whole thing also runs with **no AWS credentials at all** — a clearly labelled local parser stands in — so anyone can clone it and see the journey in one command.

And the honesty holds under pressure: the page never says "fully accounted for" while money is undocumented, the ledger separates reported from supported spending, and "delivered" means delivered to an inbox in this app with a stored receipt — not that aid reached a household.

## What we learned

That the hard part of an agent for real work is not the reasoning. It is deciding, for every single behaviour you promise, whether the model is allowed to be the one who remembers. Every promise we kept, we moved into code; everything left to the model is a judgement a person would also have to make.

## What's next

Per-donor reporting requirements defined by the donor rather than hard-coded; an amendment flow that shows a donor precisely what changed since the version they read; and a measured comparison against a coordinator doing the same work with a spreadsheet and a template.

## Honest scope

Every organisation, person, receipt, figure and donor in the demo is fictional and labelled in the app itself. There is no pilot, no real deployment, no donor endorsement, and no claim of money saved or recovered. A field-reported delivery count is not independent proof of impact, and BasketBrief says so on the report it sends.

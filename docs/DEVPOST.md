# BasketBrief

**The report was sent. Then the count changed. BasketBrief follows through.**

**Live demo:** https://basketbrief.mlki.app — no login or AWS account required
**Code:** https://github.com/NexuChat/basketbrief
**Track:** Good Neighbor Agents

BasketBrief helps a small volunteer relief group finish donor reports without making its coordinator chase every receipt and correction. It reads incoming evidence, asks the contributor who can resolve a gap, prepares English and Arabic reports, waits for approval of an exact version, and delivers immutable snapshots to two donor inboxes.

The harder part begins after delivery. If a field correction changes a reported count, BasketBrief invalidates the old approval, shows exactly what changed, follows up on any new discrepancy, and sends an approved amendment. It preserves the original report instead of silently rewriting history.

## Inspiration

Amal coordinates a fictional neighbourhood flood-relief group. Rana has the receipts. Sami has the distribution counts. Two donors need reports from the same evidence. One transport receipt is missing, so Amal becomes a switchboard: ask, wait, re-ask, reconcile the figures, and keep two reports consistent.

Then Sami corrects 92 delivered kits to 88 after the first reports have already gone out. The existing figures now leave four kits unaccounted for. That arithmetic establishes a discrepancy; it does **not** establish how many households were affected. BasketBrief keeps that distinction visible and asks Sami to check the delivery and storage records. His follow-up confirms 12 returned kits, closing the discrepancy before the amendment is approved.

The scenario and every participant are synthetic. The reporting burden is real. The [Center for Effective Philanthropy](https://cep.org/blog/reimagining-reporting-part-1-insights-from-the-field/) reported a 2023 study in which nonprofits reduced time spent on one funder's reporting requirements from eight hours to six. [Stanford Social Innovation Review](https://ssir.org/articles/entry/the_nonprofit_starvation_cycle/) described a grantee spending 31 percent of a grant's value on administration while the funder allowed 13 percent. These sources establish a reporting burden; neither source tested or endorsed BasketBrief, and we derive no product savings from them.

## What the working demo does

1. Three sources arrive: a supplies receipt, a transport expense without its receipt, and a field distribution message.
2. A Strands agent on Amazon Bedrock Nova Pro reads the sources and asks Rana for the missing transport receipt. The same answer serves both donor reports.
3. Rana uploads a synthetic receipt image. Nova Pro transcribes it through Amazon Bedrock AgentCore Runtime. The coordinator can compare the transcription with the original image.
4. Amal reviews and approves version 2. The approval is bound to that report's content hash. English and Arabic snapshots are delivered to separate in-app donor inboxes.
5. Sami corrects delivered kits from 92 to 88. BasketBrief refuses reuse of the old approval with HTTP 409 and asks Sami about the four-kit discrepancy.
6. Sami confirms that 12 kits were returned. The discrepancy closes. BasketBrief shows both changes: delivered 92 → 88 and returned 8 → 12.
7. Amal approves the amendment. Both donors receive version 4, while their original version 2 remains unchanged.

The guided button supplies fictional replies and approvals, while model calls, tool calls, versioning, guardrails, database writes, and inbox delivery execute live. Visitors can also switch roles and perform each step themselves.

## How it works

BasketBrief uses one Strands `Agent`, seven scoped tools, a sequential tool executor, and Amazon Bedrock Nova Pro at temperature zero.

The model interprets free-form evidence and chooses the next tool. Code owns the facts and irreversible boundaries:

- expense totals must be unambiguously associated with currency or an explicit total;
- loaded, delivered, returned, and household counts are separate typed facts;
- denied or wrongly associated numbers cannot enter a fact;
- a second transaction cannot silently overwrite the one transaction supported by this demo;
- contributor roles cannot approve or deliver reports;
- approvals are bound to one revision and SHA-256 content hash;
- a post-turn gate computes known gaps and delivers a scoped follow-up if the model omitted it;
- a direct answer to a scoped field question is recorded before another model turn only when each stated field has exactly one accepted interpretation; ambiguous answers remain pending.

Reports use deterministic English and Arabic templates over stored facts. The model does not write report figures or narrative. Delivery means a persisted message in this application's donor inbox, with a unique receipt; it is not email delivery or proof that aid reached a household.

## Why the AWS pieces are there

- **Amazon Bedrock + Nova Pro:** reasoning over incoming messages and tool selection.
- **Amazon Bedrock AgentCore Runtime:** the stateless receipt-image reader. If Runtime is unavailable, the app records that it used the in-process Bedrock fallback.
- **Amazon Bedrock AgentCore Memory:** an advisory vendor-name history shared across demo workspaces. A new vendor is a review hint, not a fraud verdict; Memory failure never blocks a report.
- **Dedicated workload identity:** the public service uses a narrowly scoped application identity instead of an expiring human login session.

The website gives Amal, Rana, Sami, and each donor separate capability links inside a fresh fictional workspace. Judges need no login, bot, inbox, or cloud account.

## What we fixed under pressure

An independent review found that the first submission overstated what four missing kits meant, compared an asymmetrical “41 manual acts” model with two approval decisions, and described guard-only prompt-injection cases as if a live model had refused them. Those claims were withdrawn.

The review also found real boundary defects: a receipt quantity could be accepted as money, a denied number could be attached to the wrong field, a second transaction could overwrite the first, and one generated follow-up type could not be delivered. Regression tests now pin each case.

The extended story initially failed when a terse response such as `Returned kits: 12.` reached a fourth model cycle. The field parser rejected sentence-ending punctuation, the model retried the wrong tool shape, and Strands ended the loop. A test reproduced the parser defect. The fix accepts the labelled form, records unambiguous replies at the deterministic boundary, and leaves ambiguous replies pending.

## Evidence

- **76 tests pass**, including 30 adversarial guard cases and new review regressions.
- Three consecutive full staging journeys after the final reliability fix completed in **66.0 s, 64.6 s, and 63.0 s** with 88 delivered, 12 returned, zero unresolved questions, four donor snapshots, and no browser errors.
- Every run preserved the first donor snapshots, rejected the stale approval, and delivered the approved amendment to both donors.
- `scripts/baseline.py` executes the full local-parser workflow and reports persisted interactions: two contributor questions, two contributor replies, two coordinator approvals, and four donor deliveries. It makes no claim about human time or productivity.

The prompt-injection tests exercise storage and role boundaries, not a live model. Receipt transcription is tested on the included Latin-script fixture; OCR can still be wrong, so the original image remains available to the coordinator. Detailed evidence and limitations are in `docs/EVALUATION.md`.

## What we learned

Reliable agent work depends on deciding which behavior may remain probabilistic. Interpretation and wording can belong to the model. Arithmetic, provenance, permissions, follow-up delivery, versioning, and approval validity need deterministic checks and an audit trail.

We also learned to distinguish repeatable arithmetic from a valid measurement. A script can reproduce an unfair comparison perfectly. Directly logged questions, replies, approvals, report versions, and delivery receipts are the defensible evidence here.

## What's next

The current demo deliberately supports one supplies transaction and one transport transaction per distribution. A production version needs transaction identities, donor-defined reporting requirements, external delivery connectors, durable organizational identity, and a real pilot before making any claim about time saved or outcomes improved.

## Honest scope

All organizations, people, receipts, donors, and distribution events in the demo are fictional. There is no field pilot, donor endorsement, independent verification of delivery, measured human baseline, or measured savings. A field-reported kit count is not proof that a household received aid, and a receipt is not proof of payment or impact.

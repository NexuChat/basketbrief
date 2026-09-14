# BasketBrief — follow through when the report changes

**An agent for relief coordinators: chase missing evidence, reconcile corrections, and keep every donor on the approved version.**

[Try the live story](https://basketbrief.mlki.app) · [Watch the film](https://basketbrief.mlki.app/static/film.html) · [Source code](https://github.com/NexuChat/basketbrief) · Good Neighbor Agents

## Inspiration

A small relief team's work does not end when supplies arrive. Its coordinator still has to find receipts, reconcile volunteers' updates, and explain the same figures to different donors. A late correction starts that work again.

BasketBrief tackles that follow-up. Our demonstration follows a fictional coordinator, Amal, and two contributors: Rana has the receipts; Sami has the delivery counts. Two donors need reports. A missing transport receipt is the first gap. Then, after the reports are approved and delivered, Sami corrects the delivery count from 92 kits to 88.

That second moment is the heart of BasketBrief: a correction must reach everyone who received the original, with its evidence and approval history intact.

## What it does

BasketBrief reads incoming evidence, asks the responsible contributor to resolve a gap, and prepares reports for human approval. It delivers the approved version to separate English and Arabic donor inboxes inside the application.

Watch the complete loop in the live demonstration:

1. **Ask the person who knows.** The agent finds USD 60 without a receipt and asks Rana. Her answer serves both donor reports.
2. **Keep the source visible.** Rana uploads a receipt image. The reader classifies it, transcribes it, compares the transcription with the image, and checks the arithmetic. Amal can inspect the original.
3. **Review before sharing.** Amal approves one exact version. Each donor receives a saved snapshot.
4. **Follow a late correction.** Sami changes 92 delivered to 88. The old approval cannot authorize the changed report. Four kits now need an explanation, so BasketBrief asks Sami to check the records.
5. **Close the gap without inventing impact.** Sami confirms 12 returned. Amal reviews both changes and approves an amendment. Donors keep the original alongside the new version. Unique households remain unknown.

The guided story supplies fictional replies and approvals; Strands inference, tools, evidence storage and donor inbox delivery execute live. Visitors can also perform the steps themselves.

## Work with separate accounts

The [team workspace](https://basketbrief.mlki.app/team) supports individual accounts, project invitations, contributor uploads, reviewer access and donor-only approved reports. Persistent in-app notifications tell the responsible person when evidence or a question arrives.

A receipt requested for an existing expense completes that expense without a second charge. Multiple expenses retain their original currencies; a combined reporting total requires reviewed exchange rates with dates and sources. Selected PNG/JPEG files, PDFs and saved-email attachments can be imported. PDF originals remain available; multi-page documents require full human review.

## How we built it

**Strands Agents SDK and Amazon Bedrock Nova Pro** interpret evidence and choose tools for the next follow-up. The guided story uses seven scoped tools; the team workspace uses a separate project-scoped three-tool agent. Neither agent can approve a report.

**Amazon Bedrock AgentCore Runtime** hosts the image reader. A recorded in-process Bedrock fallback keeps the same reader available if Runtime fails. **AgentCore Memory** provides advisory vendor history for the fictional demo team; it is not evidence that a vendor is trustworthy or fraudulent.

Deterministic code owns arithmetic, permissions, saved facts, follow-up persistence, versioning and delivery. Each approval binds to a report revision and content hash. Reports use templates over stored facts rather than model-written financial claims.

[Architecture](https://github.com/NexuChat/basketbrief/blob/main/docs/architecture.png) · [Verification and limits](https://github.com/NexuChat/basketbrief/blob/main/docs/EVALUATION.md)

## What we verified

- 121 automated tests passed, including 30 adversarial boundary cases. These test code boundaries; they are not a live-model attack benchmark.
- Live guided runs exercised receipt follow-up, first approval, a late correction, refusal of stale approval and delivery of both amendments.
- A separate-account browser test exercised contributor upload → reviewer notification → agent follow-up → coordinator approval → donor access. Donors saw no report before approval.
- An owner-authorized Gmail app-password test imported one selected PDF, retained its original, and blocked duplicate import and access from another account. The test connection was removed afterward; no private mail is published.
- A private document review exposed incorrect assumptions about statements and utility tables. The reader now rejects statements and transfers as purchase evidence. Unconfirmed readings remain for review.

## Challenges and lessons

A number appearing in a document is not enough: its meaning matters. A debit, a meter reading and a purchase total are different facts. We classify before extracting and require source review when the evidence is unclear.

Corrections exposed another boundary: the system must preserve supported information while asking about what remains unresolved. It must also retire approval of an earlier revision. Those behaviors are enforced in code, with regression tests and visible report history.

## Current scope and next steps

All demonstration participants and evidence are fictional. We have not run an organization pilot or measured human time saved. Our evidence establishes working software behavior, not independently verified payments or aid outcomes.

OCR can still fail, including on Arabic documents. Gmail app-password import was tested; Google/Microsoft OAuth activation and external SMTP notification delivery are not live-verified. Team notifications and donor delivery currently work inside BasketBrief. Bank statements are outside its purchase-receipt scope.

The next validation is a supervised trial with a relief coordinator, measuring task completion, corrections caught and time spent reviewing. Provider OAuth activation and an independent security review follow before broader use.

Built during this hackathon with AI coding assistance. Persistence/channel patterns were reused from an abandoned entry in the same competition; the domain-specific evidence, reconciliation, vision and approval workflows were implemented here. Public source: MIT license.

## Build notes on AWS Builder Center

Three articles trace the implementation and lessons from earlier revisions. Current behavior and verification limits are recorded in the repository's evaluation notes.

- [Agents for Humans: deciding where a model is allowed to remember](https://builder.aws.com/content/3JKJsDJK8k4xdjiXgjw1C7APCZ9)
- [Agents for Humans: four AWS pieces, and why each one is there](https://builder.aws.com/content/3JKIVfEIXxflSCjzSGeE382YQOd)
- [Agents for Humans: the test that found our own defect](https://builder.aws.com/content/3JKKRcQ2xoqyBQZKEVwHTpAFOfD)

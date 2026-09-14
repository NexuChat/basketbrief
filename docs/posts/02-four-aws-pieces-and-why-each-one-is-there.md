# Agents for Humans: four AWS pieces, and why each one is there

BasketBrief finishes the weekly donor report for a neighbourhood mutual-aid group. It reads the receipts and field messages, chases the one that is missing, recalculates, and delivers an approved report to each donor. Four AWS pieces carry it. This is what each one is actually for — and what I would have got wrong without measuring first.

## 1. Strands Agents SDK — the part that decides

In the guided demonstration, one `Agent`, seven tools, `BedrockModel`, `temperature=0`, a `SequentialToolExecutor`, and a hook that caps tool calls and wall time so a confused turn cannot run away.

The division of labour is the whole design:

- **The model decides** what a source means, what is missing, who to ask, and how to word a question.
- **The code decides** what is allowed: a stated total or currency-associated amount must appear in its source; loaded, delivered, returned and unique households are four different facts and never collapse into one; contributor text is untrusted data, so an instruction inside a field message is evidence, not a command. Report bodies come from deterministic templates over the accepted facts.

Before the later document-reader and team-workspace updates, three consecutive browser-driven journeys through the full two-report amendment flow produced identical figures in 63–66 seconds each. These timings are specific to that earlier build; current checks and limitations are recorded in docs/EVALUATION.md.

## 2. Amazon Nova Pro — the part that reads a photograph

Volunteers often have photographs rather than typed expense records. Our first reader assumed every image was a purchase receipt. A private review with 13 document images showed why that was unsafe: statement credits and debits and utility meter tables do not belong in a purchase schema.

The current shared reader classifies the document first. Statements and transfers return without an expense total. For supported documents, one call transcribes and another compares the proposed fields with the image; deterministic Decimal checks then assess the arithmetic. The original remains available for review. A bill or unpaid invoice does not establish payment.

The final probe covered the 13 private images and the synthetic transport receipt. Six statements/transfer records were rejected without totals; five Arabic utility images required review; two Latin-script purchase documents retained printed totals but required review; the synthetic USD 60 receipt passed. These results establish conservative scope handling, not general OCR accuracy. A second model call can still share the first model's mistakes.

The prompt asks for legible text in its original language. Unclear values remain unknown. All private images and identifying extracted data stay outside this repository.

## 3. AgentCore Runtime — the part that is genuinely stateless

Most of BasketBrief is stateful: evidence, versioned facts, approvals bound to a content hash. That does not belong in a stateless runtime, and pretending otherwise would have been architecture theatre.

Reading a photograph, though, is bytes in and a typed reading out. So that is the piece that moved:

```
npm i -g @aws/agentcore
agentcore create --framework Strands --model-provider Bedrock --build CodeZip
agentcore deploy --yes
```

The deployment provisions the execution role and runtime. The live final receipt probe returned schema version 2 through AgentCore Runtime. We report its observed result separately from historical latency measurements; a successful request does not establish availability throughout judging.

The part I would argue for keeping: **the app falls back to reading in-process if the runtime does not answer**, and the timeline records which path was used — `read_on: agentcore-runtime` or `read_on: in-process`. A managed dependency should not be able to stop a coordinator finishing her evening.

## 4. AgentCore Memory — the part that outlives the workspace

The guided demo creates a fresh workspace for a fictional distribution. Vendor history can be useful across distributions, even though it cannot validate a payment.

For the configured fictional demo team, that history sits in AgentCore Memory. When a receipt names a vendor nobody on this team has ever bought from, the agent says so before it reaches a donor. When it names the haulier they always use, it says that too.

Two things kept it honest:

- **It is advisory in its own words.** A new vendor is "worth a look — a hint, not a finding." It never changes a number.
- **It cannot fail a review.** If the memory service is unreachable, the check returns `known: None`, the reason is recorded, and the review continues. There is a test that pins this.

Vendor names are folded before comparison, so `AL-NOOR TRANSPORT`, `Al Noor Transport Co.` and `AL NOOR TRANSPORT LTD` are one vendor, and `QASIM WHOLESALE` is not.

## What I would tell someone starting this week

Pick the AWS piece for the job it is actually good at, and be able to say in one sentence why it is there. Runtime because one step is stateless. Memory because one kind of knowledge outlives the request. Nova vision because volunteers photograph things. Strands because something has to decide what a messy message means.

If you cannot finish that sentence for a service, you are decorating.

---

Open source under MIT: **github.com/NexuChat/basketbrief** — the deployed runtime is in `runtime/`, the measurements are in `docs/EVALUATION.md`, and the live demo is at **basketbrief.mlki.app**. All demo data is fictional and labelled.

Built for the Agents for Humans Hackathon, Good Neighbor Agents track.

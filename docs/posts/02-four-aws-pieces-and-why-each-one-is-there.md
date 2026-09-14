# Agents for Humans: four AWS pieces, and why each one is there

BasketBrief finishes the weekly donor report for a neighbourhood mutual-aid group. It reads the receipts and field messages, chases the one that is missing, recalculates, and delivers an approved report to each donor. Four AWS pieces carry it. This is what each one is actually for — and what I would have got wrong without measuring first.

## 1. Strands Agents SDK — the part that decides

One `Agent`, seven tools, `BedrockModel`, `temperature=0`, a `SequentialToolExecutor`, and a hook that caps tool calls and wall time so a confused turn cannot run away.

The division of labour is the whole design:

- **The model decides** what a source means, what is missing, who to ask, and how to word both the question and the report.
- **The code decides** what is allowed: an amount must appear in its source; loaded, delivered, returned and unique households are four different facts and never collapse into one; contributor text is untrusted data, so an instruction inside a field message is evidence, not a command.

A cycle takes 4–9 seconds and 8–12k input tokens. Seven consecutive end-to-end journeys produced identical figures.

## 2. Amazon Nova Pro — the part that reads a photograph

Volunteers do not type receipts. They photograph them. So before any review starts, every attached image is transcribed by Nova Pro, and **the transcription becomes the source text** — which means the "amount must appear in its source" guard now applies to what was actually printed on the paper.

I measured this before designing around it, and the measurement changed the design:

| Input | Result |
|---|---|
| Printed Latin-script receipt | vendor, invoice number, date, currency, both line items, total — all exact |
| A receipt with a **planted** total mismatch (lines sum to 506,000; printed total 512,000) | mismatch caught; the printed total was **not** rewritten |
| Arabic-only receipt | numbers exact, **wording hallucinated** — the vendor became an unrelated bank name |
| Mixed-script receipt, asking only for the Latin text | exact |

That third row is why the prompt asks for Latin-script text and returns `null` rather than guessing. A limitation you have measured is a design input. A limitation you have assumed is a bug waiting for a demo.

## 3. AgentCore Runtime — the part that is genuinely stateless

Most of BasketBrief is stateful: evidence, versioned facts, approvals bound to a content hash. That does not belong in a stateless runtime, and pretending otherwise would have been architecture theatre.

Reading a photograph, though, is bytes in and a typed reading out. So that is the piece that moved:

```
npm i -g @aws/agentcore
agentcore create --framework Strands --model-provider Bedrock --build CodeZip
agentcore deploy --yes
```

The CDK stack creates the execution role and the runtime. `invoke_agent_runtime` with a 100 KB receipt returns **HTTP 200 in 8.4 s** with every field correct, and the runtime emits structured logs and OpenTelemetry spans to CloudWatch without any extra work.

The part I would argue for keeping: **the app falls back to reading in-process if the runtime does not answer**, and the timeline records which path was used — `read_on: agentcore-runtime` or `read_on: in-process`. A managed dependency should not be able to stop a coordinator finishing her evening.

## 4. AgentCore Memory — the part that outlives the workspace

A workspace exists for one distribution and is then thrown away. A *team* is not: the same haulier and the same wholesaler come back every month.

That history sits in AgentCore Memory, keyed by the team. When a receipt names a vendor nobody on this team has ever bought from, the agent says so before it reaches a donor. When it names the haulier they always use, it says that too.

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

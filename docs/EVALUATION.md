# BasketBrief evaluation and limits

This document separates deterministic tests, live model runs, provider liveness, and claims we did not measure. All people, organizations, receipts, donors, and distribution events in the demo are fictional.

Measured on 2026-09-14. The post-review build was exercised against Amazon Bedrock with the same application identity and service configuration used by the public demo.

## 1. Complete live journey

Before the document-scope update described below, three consecutive browser-driven staging journeys completed with no browser errors. These timings measure that earlier reader version:

| | run 1 | run 2 | run 3 |
|---|---:|---:|---:|
| Wall clock | 66.0 s | 64.6 s | 63.0 s |
| Final delivered count | 88 | 88 | 88 |
| Final returned count | 12 | 12 | 12 |
| Open questions | 0 | 0 | 0 |
| Contributor questions | 2 | 2 | 2 |
| Donor snapshots delivered | 4 | 4 | 4 |
| Browser page errors | 0 | 0 | 0 |

Each run performed the same sequence through the HTTP API and visible interface:

1. create a fresh workspace;
2. let the Strands agent review three seeded sources;
3. upload the included receipt image as Rana;
4. wait for live Nova Pro transcription and evidence review;
5. approve and deliver the first version to both donors;
6. submit 88 delivered as Sami;
7. verify that the old approval is rejected with HTTP 409;
8. verify that a reconciliation question reaches Sami;
9. submit 12 returned in response;
10. approve and deliver the amendment;
11. open the Arabic donor inbox, verify both snapshots and the before/after table, download the report, and check a 390 px viewport for overflow.

The final summary was identical in all runs: USD 1,260 reported, USD 1,260 receipt-supported, USD 0 unsupported, 100 loaded, 88 delivered, 12 returned, and unique households unknown. The first donor snapshots retained 92 delivered and 8 returned; the amendment recorded both changes.

These runs demonstrate the configured synthetic journey. They do not establish accuracy on arbitrary evidence or availability throughout judging.

## 2. Automated checks

After the document-scope update, `python -m coverage run -m pytest -q` completed with **105 passed** and one upstream deprecation warning. `python -m coverage report` reports the coverage below.

The suite includes:

- 30 adversarial guard cases;
- workflow and report-version tests;
- API role, upload, export, and capability tests;
- regressions discovered by independent review;
- conservative parsing cases for totals, field association, negation, punctuation, and ambiguity.

The most relevant review regressions prove that:

| Attempt | Required result |
|---|---|
| Treat receipt quantity 100 or unit price 12 as the USD total | refused |
| Use 92 from “88 delivered, not 92” as delivered | refused |
| Attach 88 to loaded or returned in the same sentence | refused |
| Turn a kit count near the word “families” into households | refused |
| Infer four households from a four-kit discrepancy | never produced |
| Submit a second transport transaction over the first | refused and original total preserved |
| Generate a supplies-receipt follow-up | delivered once, not duplicated |
| Resolve 88 delivered plus 12 returned | old issue retired and amendment changes both fields |
| Re-run after a report was delivered without new evidence | no self-amendment |
| Parse `Returned kits: 12.` | accepted as returned=12 |
| Parse two possible returned values in one reply | kept pending for review |

The three prompt-injection strings in `tests/test_adversarial.py` exercise storage and role boundaries. They show that merely storing hostile contributor text cannot approve a report, deliver a report, or create money. They do **not** run a model against those strings and are not reported as live model refusals.

Overall line coverage in this run was 70 percent. The new shared document reader was 97 percent and the store was 87 percent; live Bedrock, AgentCore, demo rendering, and provider-failure branches remain partly outside unit coverage. Passing tests do not replace live browser evidence.

## 3. The defect found in the extended story

The first version of the extended journey stopped on Sami's second answer. A sentence-ending period after `Returned kits: 12.` caused the labelled-value pattern to reject the count. The model then retried an unsupported tool shape until Strands ended the cycle with `EventLoopException`.

The fix has two parts:

- the parser accepts a labelled field/value followed by normal punctuation;
- replies to scoped field questions are recorded before another model turn only when every mentioned field has exactly one grounded value.

If a reply says returned may be 12 or 10, it remains pending. The reliability gate narrows accepted input; it does not pick one possibility.

## 4. What the source guards establish

The guards enforce supported formats, typed field association, source ownership, role permissions, and approval freshness. They are deliberately conservative. Unrecognized wording requires clarification.

They do not prove that:

- a receipt transcription matches the pixels;
- a receipt represents a real payment;
- a field message describes a real delivery;
- a delivered kit reached a unique household;
- a contributor is honest;
- every natural-language phrasing is understood.

The original image stays available to the coordinator. A new vendor in AgentCore Memory is an advisory hint, not evidence of fraud.

## 5. Receipt reading and AgentCore

### Document-scope update, 2026-09-14

A private set of 13 user-provided document images exposed a serious assumption: the earlier prompt treated every image as a purchase receipt. Card credits and debits could be added together; a utility meter table could become invented purchase items. Matching those invented line amounts to an invented total did not detect the error.

The deployed reader now classifies first. Statements and transfers return `unsupported` without amounts. Supported purchase documents get a transcription call and a separate image-comparison call, followed by typed Decimal and arithmetic checks. A repeated summary row cannot become another item. The application and AgentCore use the same source, checked by a synchronization regression.

Expense storage requires a saved eligible USD purchase-receipt reading and the exact saved total. Replacing its source text cannot authorize a different amount. Rejected images remain visible as review issues and leave their contributor question unresolved. Bills and invoices are not treated as proof of payment. The standalone preview shows the original image, uncertainty warnings, and whether any expense amount is eligible. Provider failures return an explicit generic error.

The final public HTTP probe used all 13 private cases plus the synthetic demo receipt. All 14 responses used schema version 2 through AgentCore Runtime:

| Cases | Observed behavior |
|---|---|
| Six statements/transfer documents | Rejected with no total, no item sum and no expense amount |
| Two Latin-script purchase documents | Printed totals read correctly; final public reads required review because date verification did not pass |
| Five Arabic utility images | Required review; none could support an expense; no meter-reading sum produced |
| Included synthetic transport receipt | USD 60.00, two items, eligible after the checks |

This is a scope-and-refusal result, **not 13 accurate OCR reads**. One water-bill transcription still contained an incorrect proposed total; the image check failed and the result remained unconfirmed. The model also failed to establish totals on clearer Arabic bills. A second model call is not independent ground truth and can make correlated mistakes or reject a correct normalization. Human comparison remains necessary. The private images and identifying extracted data are not published in this repository.

The complete guided journey also passed with the new reader in staging and on the public deployment: USD 1,260 supported, 88 delivered, 12 returned, unknown households, and four donor snapshots. The source-dialog bug found during this review was fixed and opening both text sources and an uploaded original was rechecked. The standalone result was checked at 390 px with both a rejected statement and the accepted synthetic receipt, without horizontal overflow.

The included Latin-script receipt fixture has been read successfully through Amazon Bedrock AgentCore Runtime. The reader returns vendor, invoice, date, currency, line items, stated total, calculated total, and any mismatch. The timeline records whether the image was read in AgentCore Runtime or by the in-process Bedrock fallback.

Earlier fixture work found unreliable wording on an Arabic-only receipt. BasketBrief therefore does not claim general OCR accuracy. The donor report's Arabic is a deterministic application template over stored facts, separate from receipt transcription.

AgentCore Memory stores an advisory normalized vendor history for the configured synthetic team. Similar spellings of the same vendor fold together. A Memory outage returns unknown and does not block the evidence workflow.

The public service now authenticates as `basketbrief-demo-runtime`, a dedicated application user, instead of relying on an expiring interactive AWS login. The identity was exercised against text inference, receipt reading, and Memory before the live staging runs.

## 6. Directly counted workflow interactions

`python scripts/baseline.py` runs the complete scripted local-parser scenario and reads counts from its temporary database. It reports:

| Persisted event | Count |
|---|---:|
| Initial evidence sources | 3 |
| Total evidence sources | 6 |
| Contributor questions | 2 |
| Contributor replies | 2 |
| Coordinator approvals | 2 |
| Donor inbox deliveries | 4 |
| Unresolved questions | 0 |
| Stale approval refused | yes |

These are system interactions. The script does not time a person, compare against a spreadsheet, or claim productivity, cost, or outcome improvement.

The earlier “41 human acts → 2” comparison was withdrawn because it counted manual reading and transcription in detail while reducing the assisted path to approval decisions. Reproducibility did not make the comparison balanced.

## 7. Evidence that the problem exists

Two external sources support the existence of reporting burden:

- [Center for Effective Philanthropy](https://cep.org/blog/reimagining-reporting-part-1-insights-from-the-field/), Alice Mei and Nina Groleger, *Reimagining Reporting, Part 1: Insights From the Field*, 11 November 2025, reports a 2023 study in which nonprofits reduced time spent on one funder's reporting requirements from eight hours to six.
- [Stanford Social Innovation Review](https://ssir.org/articles/entry/the_nonprofit_starvation_cycle/), Ann Goggins Gregory and Don Howard, *The Nonprofit Starvation Cycle*, Fall 2009, describes a grantee that calculated reporting administration at about 31 percent of a grant's value while the funder allowed 13 percent for indirect costs.

These sources concern grant reporting in the United States philanthropic sector. They are not about neighbourhood flood relief, do not mention BasketBrief, and do not establish demand, usability, or impact for this product.

## 8. Scope and claims deliberately withheld

- No real organization, field pilot, donor endorsement, or independent delivery verification.
- No measured human baseline, time saving, cost saving, or aid outcome.
- One supplies transaction and one transport transaction per distribution; this is not a general ledger.
- In-app donor inbox delivery, not external email, a read receipt, or proof of real-world receipt.
- Demonstration role switching for fictional participants, not a production identity and onboarding system.
- No claim that guard tests establish resistance to every prompt injection.
- No claim that three successful runs predict uninterrupted availability through the judging period.

The evaluation artifacts under `/home/dev/competitions/reviews/basketbrief-2026-09-14/` include the audit, reproduction results, staging state, downloaded Arabic amendment, and desktop/mobile screenshots. They are local review evidence and are not required to run the repository.

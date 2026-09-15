# Try BasketBrief

**Start:** https://basketbrief.mlki.app — no account required for the fictional demonstration.

Select **Play the whole story**. The demonstration supplies fictional replies and approvals while the Strands agent, receipt reader, storage and inbox delivery run live. The work depends on model requests; loading time varies. You can stop the guided story and use the role selector to perform the steps yourself.

## What to look for

| Step | Observable result |
|---|---|
| Missing receipt | USD 60 remains unsupported; Rana receives a direct question. |
| Receipt arrives | The original stays available; supported spending becomes USD 1,260. |
| First approval | Both donor inboxes receive version 2: 92 delivered, 8 returned. |
| Late correction | 88 delivered creates a four-kit discrepancy; the previous approval cannot approve new content. |
| Field reply | Sami confirms 12 returned; households remain unknown. |
| Amendment | Amal reviews both changed counts and approves version 4; donor inboxes retain both versions. |

At the end, choose each donor from **Experience as**. Open the original and the amendment. The English and Arabic reports use the same approved facts.

The optional receipt checker is below the report workspace. Upload only an image you are authorized to process. It classifies before extraction; statements and transfers cannot authorize a purchase expense. Unconfirmed readings require source review.

## Try a correction that is not in the film

After the whole story finishes:

1. Under **Experience as**, choose **Sami · Delivery team**.
2. Choose **Correction to the figures** and enter: `Correction: 87 kits were delivered, not 88.`
3. Send the evidence, then switch back to **Amal · Coordinator** and wait for the review.
4. Expect 100 loaded, 87 delivered, 12 returned, and a question about the one-kit discrepancy. Unique households stay unknown. The new report awaits human approval.
5. Open each donor inbox. Both previously approved snapshots remain: 92/8 and 88/12. The unapproved 87-kit correction has not replaced either one.

This exact additional scenario was verified through the public browser UI on 2026-09-15 after the final code fixes, with no browser page errors and no horizontal overflow at 390 pixels. [Observed results](live-probes/04-public-browser.json).

To reproduce the separate five-case live challenge probe with your own Bedrock credentials, run `python scripts/live_stress.py --output /tmp/basketbrief-probes.json`. [All batches and limitations](EVALUATION.md#live-challenge-probes-defects-found-and-retested) are published, including the defects found before the final passing run.

## Your own team

Use https://basketbrief.mlki.app/team. Create an account, create a project, then invite another person to a role. Each member signs in separately. A contributor's expense or receipt creates a notification for the relevant reviewers; the donor sees approved snapshots only.

Mailbox connection is optional. In-app notifications work without it. Gmail app-password import was privately tested; Google/Microsoft OAuth and external notification emails are not live-verified. This is a prototype with no organization pilot or independent security audit.

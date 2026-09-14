# The receipt reader, on Amazon Bedrock AgentCore Runtime

Reading a photograph of a receipt is the one genuinely stateless step in BasketBrief — bytes in, a typed reading out — so it is the step that belongs in a managed runtime rather than in the coordinator's web process.

This directory is the deployed agent, created with the AgentCore CLI and deployed with its CDK project.

```
app/receiptreader/main.py            the entrypoint: BedrockAgentCoreApp + a Strands Agent
app/receiptreader/receipt_vision.py  the same reader the web app uses in-process
agentcore/                           CLI config and the CDK stack
```

**What it does.** The model transcribes; this service validates. Fields are typed, amounts become `Decimal`, and the line items are added up against the printed total. A receipt whose own arithmetic disagrees comes back with the disagreement stated — never silently corrected. Images over 2 MB and anything that is not valid base64 are refused before a model is called.

**How the app uses it.** When `BASKETBRIEF_RUNTIME_ARN` is set, `basketbrief/vision.py` sends the photograph here and the timeline records `read_on: agentcore-runtime`. If the runtime is unreachable, the app reads in-process instead and records `read_on: in-process`. A managed dependency should not be able to stop a coordinator finishing her evening.

**Measured.** `invoke_agent_runtime` with a 100 KB receipt: HTTP 200 in 8.4 s, vendor, invoice number, date, currency, both line items and the total all exact.

## Deploy your own

```bash
npm i -g @aws/agentcore
cd runtime
agentcore deploy --yes          # creates the execution role and the runtime via CDK
agentcore invoke --prompt-file payload.json --runtime receiptreader
```

`payload.json` is `{"image_b64": "<base64 of a PNG or JPEG>"}`. The deployed ARN then goes into the web app's `BASKETBRIEF_RUNTIME_ARN`.

The account id in `agentcore/aws-targets.json` is ours; change it to yours. Nothing here holds a credential — the CLI uses your ambient AWS session.

## A note on the CDK lockfile

`agentcore/cdk/package-lock.json` is not committed. `aws-cdk-lib` bundles its own copy of `brace-expansion`, and npm `overrides` cannot reach inside a bundled dependency, so any lockfile we ship carries an advisory we cannot patch from here. The lockfile is generated at deploy time by `agentcore deploy`, which resolves the current versions; `package.json` pins an override to `^5.0.9` for everything that is not bundled.

This affects the infrastructure tooling that runs on a maintainer's machine at deploy time. It is not part of the deployed runtime or of the web application.

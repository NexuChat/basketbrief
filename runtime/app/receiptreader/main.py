"""BasketBrief's receipt reader, deployed on Amazon Bedrock AgentCore Runtime.

This is the one piece of BasketBrief that is genuinely stateless — bytes of a
photograph in, a typed reading out — so it is the piece that belongs in a managed
runtime. The coordinator's workspace calls it instead of calling Bedrock itself.

The model transcribes. This service validates: typed fields, Decimal amounts, and
the line items added up against the printed total. A receipt whose own arithmetic
disagrees is returned with the disagreement stated, never silently corrected.
"""

import base64
import binascii
import json

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent, tool

import receipt_vision

app = BedrockAgentCoreApp()
log = app.logger

MAX_BYTES = 2_000_000

SYSTEM = """You read photographs of receipts for a small food-aid team.
Call read_receipt exactly once with the image you were given, then return its
JSON unchanged. Never restate an amount from memory, never total anything
yourself, and never describe a receipt you were not shown."""


@tool
def read_receipt(image_b64: str) -> dict:
    """Transcribe a receipt photograph and check its arithmetic in code."""
    try:
        raw = base64.b64decode(image_b64, validate=True)
    except (binascii.Error, ValueError):
        return {"ok": False, "reason": "The image was not valid base64."}
    if not raw or len(raw) > MAX_BYTES:
        return {"ok": False, "reason": "Send a PNG or JPEG under 2 MB."}
    reading = receipt_vision.read_receipt(raw)
    return {**{k: (str(v) if hasattr(v, "quantize") else v) for k, v in reading.items() if k != "items"},
            "items": [{k: (str(v) if hasattr(v, "quantize") else v) for k, v in item.items()}
                      for item in reading.get("items", [])],
            "source_text": receipt_vision.as_source_text(reading)}


@app.entrypoint
def invoke(payload, context=None):
    """payload: {"image_b64": "..."} — returns the validated reading.

    Callers that wrap everything in a `prompt` string (the agentcore CLI does)
    are unwrapped here so the same runtime answers both shapes.
    """
    payload = payload or {}
    if "image_b64" not in payload and isinstance(payload.get("prompt"), str):
        try:
            payload = json.loads(payload["prompt"])
        except (json.JSONDecodeError, TypeError):
            pass
    image_b64 = payload.get("image_b64")
    if not image_b64:
        return {"ok": False, "reason": "Send image_b64."}
    log.info("reading a receipt photograph (%d b64 chars)", len(image_b64))
    return read_receipt(image_b64)


if __name__ == "__main__":
    app.run()

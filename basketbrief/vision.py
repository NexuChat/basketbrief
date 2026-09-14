"""Reading a receipt photograph with Amazon Nova Pro, and checking it in code.

The model transcribes; it never decides. Everything it returns is validated here:
the fields are typed, the amounts are Decimals, and the line items are added up and
compared with the printed total. A receipt whose own arithmetic disagrees is not
corrected and not discarded — the disagreement is returned so a human sees it.

Measured on this project's fixtures: Nova Pro reads printed amounts exactly and
catches a planted total mismatch. It mistranscribes Arabic words, so the prompt asks
for Latin-script text only and leaves other-script fields null rather than inventing them.
"""

from __future__ import annotations

import json
import os
import re
import threading
from decimal import Decimal, InvalidOperation

PROMPT = (
    "This is a photograph of a purchase receipt from a small aid organisation. "
    "Return JSON only, no prose, exactly this shape:\n"
    '{"vendor": string|null, "date": "YYYY-MM-DD"|null, "currency": string|null, '
    '"invoice_no": string|null, "items": [{"name": string, "qty": number, '
    '"unit_price": number, "line_total": number}], "stated_total": number|null, '
    '"customer": string|null, "confidence": number}\n'
    "Copy every number exactly as printed. Do NOT correct arithmetic, do NOT total "
    "anything yourself, and do NOT convert currencies. For text fields transcribe the "
    "Latin-script wording when the receipt shows it; if a field appears only in another "
    "script, return null for it rather than guessing. If the image is not a receipt, "
    "return items: [] and stated_total: null."
)

MODEL = os.environ.get("BASKETBRIEF_VISION_MODEL", "us.amazon.nova-pro-v1:0")
RUNTIME_ARN = os.environ.get("BASKETBRIEF_RUNTIME_ARN", "")

_local = threading.local()


def _client():
    """One Bedrock client per thread: botocore clients are not safe to share across threads."""
    existing = getattr(_local, "client", None)
    if existing is None:
        import boto3
        from botocore.config import Config
        existing = _local.client = boto3.Session(
            region_name=os.environ.get("AWS_REGION", "us-east-1")
        ).client("bedrock-runtime", config=Config(
            read_timeout=45, connect_timeout=10, retries={"max_attempts": 3, "mode": "standard"}))
    return existing


def _decimal(value) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return Decimal(str(value).replace(",", "").strip()).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError, ArithmeticError):
        return None


def read_receipt_on_runtime(image_bytes: bytes) -> dict | None:
    """Ask the reader deployed on Amazon Bedrock AgentCore Runtime.

    Reading a photograph is the one genuinely stateless step in BasketBrief, so it
    is the step that belongs in a managed runtime rather than in the web process.
    Returns None when no runtime is configured or it does not answer, and the
    caller falls back to reading in-process — a managed dependency should not be
    able to stop a coordinator finishing her evening.
    """
    if not RUNTIME_ARN:
        return None
    import base64, json as _json, uuid
    try:
        client = getattr(_local, "runtime", None)
        if client is None:
            import boto3
            from botocore.config import Config
            client = _local.runtime = boto3.Session(
                region_name=os.environ.get("AWS_REGION", "us-east-1")
            ).client("bedrock-agentcore", config=Config(
                read_timeout=40, connect_timeout=8, retries={"max_attempts": 1}))
        session = (uuid.uuid4().hex + uuid.uuid4().hex)[:40]
        answer = client.invoke_agent_runtime(
            agentRuntimeArn=RUNTIME_ARN, runtimeSessionId=session,
            payload=_json.dumps({"image_b64": base64.b64encode(image_bytes).decode()}).encode())
        data = _json.loads(answer["response"].read().decode())
    except Exception:
        return None
    if not isinstance(data, dict) or "ok" not in data:
        return None
    # the runtime returns decimals as strings; bring them back to Decimal here so
    # every downstream check sees exactly what an in-process read would produce
    for key in ("stated_total", "summed_total"):
        if data.get(key) is not None:
            data[key] = _decimal(data[key])
    for item in data.get("items", []):
        for key in ("qty", "unit_price", "line_total"):
            if item.get(key) is not None:
                item[key] = _decimal(item[key])
    data["where"] = "agentcore-runtime"
    return data


def read_receipt(image_bytes: bytes, client=None) -> dict:
    """Transcribe a receipt image. Returns the fields, the arithmetic check, and the raw text.

    Raises RuntimeError only when the model call itself fails; a model that returns
    nonsense produces an empty, explicitly low-confidence reading instead.
    """
    if client is None:
        remote = read_receipt_on_runtime(image_bytes)
        if remote is not None:
            return remote
        client = _client()

    response = client.converse(
        modelId=MODEL,
        messages=[{"role": "user", "content": [
            {"image": {"format": "png", "source": {"bytes": image_bytes}}},
            {"text": PROMPT},
        ]}],
        inferenceConfig={"maxTokens": 900, "temperature": 0},
    )
    raw = response["output"]["message"]["content"][0]["text"].strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        return {"ok": False, "reason": "The model did not return a reading.", "raw": raw[:400]}
    try:
        data = json.loads(raw[start:end + 1])
    except json.JSONDecodeError:
        return {"ok": False, "reason": "The reading was not valid JSON.", "raw": raw[:400]}

    items = []
    for item in data.get("items") or []:
        if not isinstance(item, dict):
            continue
        line_total = _decimal(item.get("line_total"))
        if line_total is None:
            continue
        items.append({
            "name": str(item.get("name") or "")[:80],
            "qty": _decimal(item.get("qty")),
            "unit_price": _decimal(item.get("unit_price")),
            "line_total": line_total,
        })

    stated = _decimal(data.get("stated_total"))
    summed = sum((i["line_total"] for i in items), Decimal("0.00")) if items else None
    mismatch = None
    if stated is not None and summed is not None and items and stated != summed:
        mismatch = (f"The receipt's line items add up to {summed}, but it states "
                    f"{stated} — a difference of {abs(stated - summed)}.")

    currency = (data.get("currency") or "").strip().upper()[:8] or None
    date = data.get("date") if re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(data.get("date") or "")) else None
    confidence = _decimal(data.get("confidence"))

    return {
        "ok": bool(items or stated is not None),
        "vendor": (data.get("vendor") or None) and str(data["vendor"])[:80],
        "customer": (data.get("customer") or None) and str(data["customer"])[:80],
        "invoice_no": (data.get("invoice_no") or None) and str(data["invoice_no"])[:40],
        "date": date,
        "currency": currency,
        "items": items,
        "stated_total": stated,
        "summed_total": summed,
        "mismatch": mismatch,
        "confidence": float(confidence) if confidence is not None else None,
        "model": MODEL,
        "where": "in-process",
    }


def as_source_text(reading: dict) -> str:
    """The transcription, written back as the evidence text.

    Everything downstream — the amount guard, the report, the audit trail — reads this
    text. The source checks constrain the transcription, not the original pixels;
    OCR can be wrong and the coordinator must review the image.
    """
    if not reading.get("ok"):
        return "RECEIPT IMAGE · unreadable. " + str(reading.get("reason") or "")[:160]
    lines = ["RECEIPT IMAGE · transcribed by Amazon Nova Pro from the photograph."]
    head = []
    if reading.get("vendor"):
        head.append(f"Vendor: {reading['vendor']}")
    if reading.get("invoice_no"):
        head.append(f"Invoice: {reading['invoice_no']}")
    if reading.get("date"):
        head.append(f"Date: {reading['date']}")
    if head:
        lines.append(" · ".join(head))
    for item in reading["items"]:
        qty = f"{item['qty']} × " if item["qty"] is not None else ""
        lines.append(f"- {item['name'] or 'item'}: {qty}{item['unit_price'] if item['unit_price'] is not None else ''} = {item['line_total']}")
    if reading.get("stated_total") is not None:
        lines.append(f"Printed total: {reading['stated_total']} {reading.get('currency') or ''}".strip())
    if reading.get("mismatch"):
        lines.append("Note: " + reading["mismatch"])
    return "\n".join(lines)

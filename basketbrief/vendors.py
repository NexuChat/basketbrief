"""What this team has seen before — held in Amazon Bedrock AgentCore Memory.

A workspace lives for one distribution. A team does not: the same wholesaler,
the same haulier and the same transport rates come back month after month, and a
vendor nobody has ever bought from is worth a second look before it becomes a
line in a donor's report.

That knowledge cannot live in the workspace's SQLite file, because the workspace
is thrown away. It lives in AgentCore Memory, keyed by the team, and outlives
every individual report.

The memory is advisory and says so. A vendor being new is a review hint for the
coordinator; it is never evidence of anything, and it never changes a number.
"""

from __future__ import annotations

import os
import re
import threading
import time

MEMORY_ID = os.environ.get("BASKETBRIEF_MEMORY_ID", "")
ACTOR = os.environ.get("BASKETBRIEF_TEAM", "al-amal-relief")
REGION = os.environ.get("AWS_REGION", "us-east-1")
SESSION = "vendor-ledger"

_local = threading.local()
_seen_cache: dict[str, float] = {}
_cache_lock = threading.Lock()
CACHE_TTL = 120


def enabled() -> bool:
    return bool(MEMORY_ID)


def _client():
    existing = getattr(_local, "client", None)
    if existing is None:
        import boto3
        from botocore.config import Config
        existing = _local.client = boto3.Session(region_name=REGION).client(
            "bedrock-agentcore",
            config=Config(read_timeout=12, connect_timeout=5, retries={"max_attempts": 2}))
    return existing


def normalise(vendor: str) -> str:
    """Fold a vendor name to something comparable across receipts."""
    text = re.sub(r"[^a-z0-9 ]+", " ", (vendor or "").lower())
    text = re.sub(r"\b(co|ltd|llc|inc|company|trading|est|establishment|for|and|the)\b", " ", text)
    return " ".join(text.split())


def _known() -> dict[str, float]:
    """Every vendor this team has recorded before, with when it was last seen."""
    with _cache_lock:
        cached = _seen_cache.get("__at__", 0)
        if time.time() - cached < CACHE_TTL and "__data__" in _seen_cache:
            return _seen_cache["__data__"]  # type: ignore[return-value]
    seen: dict[str, float] = {}
    token = None
    for _ in range(5):  # bounded: this runs inside a review
        kwargs = {"memoryId": MEMORY_ID, "actorId": ACTOR, "sessionId": SESSION, "maxResults": 100}
        if token:
            kwargs["nextToken"] = token
        page = _client().list_events(**kwargs)
        for event in page.get("events", []):
            for item in event.get("payload", []):
                text = (item.get("conversational", {}).get("content", {}) or {}).get("text", "")
                if text.startswith("vendor:"):
                    key = text.split("vendor:", 1)[1].split("|", 1)[0].strip()
                    if key:
                        seen[key] = max(seen.get(key, 0), event["eventTimestamp"].timestamp())
        token = page.get("nextToken")
        if not token:
            break
    with _cache_lock:
        _seen_cache["__data__"] = seen  # type: ignore[assignment]
        _seen_cache["__at__"] = time.time()
    return seen


def check(vendor: str) -> dict:
    """Has this team bought from this vendor before? Advisory, never a verdict."""
    key = normalise(vendor)
    if not enabled() or not key:
        return {"known": None, "vendor": vendor, "reason": "no vendor ledger configured"}
    try:
        seen = _known()
    except Exception as exc:  # the ledger is a convenience; a review never fails on it
        return {"known": None, "vendor": vendor, "error": f"{type(exc).__name__}"}
    if key in seen:
        return {"known": True, "vendor": vendor, "last_seen": seen[key],
                "note": "This team has recorded a receipt from this vendor before."}
    return {"known": False, "vendor": vendor,
            "note": "No receipt from this vendor in this team's history. "
                    "Worth a look before it reaches a donor — it is a hint, not a finding."}


def remember(vendor: str, invoice: str | None, amount: str | None) -> bool:
    """Record that this team has now seen this vendor. Best effort, never fatal."""
    key = normalise(vendor)
    if not enabled() or not key:
        return False
    line = f"vendor:{key}|name:{vendor}|invoice:{invoice or '-'}|amount:{amount or '-'}"
    try:
        _client().create_event(
            memoryId=MEMORY_ID, actorId=ACTOR, sessionId=SESSION,
            eventTimestamp=int(time.time()),
            payload=[{"conversational": {"role": "ASSISTANT", "content": {"text": line}}}])
    except Exception:
        return False
    with _cache_lock:
        _seen_cache.pop("__at__", None)
    return True

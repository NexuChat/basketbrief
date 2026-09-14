from __future__ import annotations

import hashlib
import json
import re
import secrets
import sqlite3
import time
from contextlib import contextmanager
from decimal import Decimal, InvalidOperation
from pathlib import Path


class Conflict(ValueError):
    pass


class Forbidden(ValueError):
    pass


ROLES = {"coordinator": "Amal · Coordinator", "finance": "Rana · Finance", "field": "Sami · Field team",
         "donor_a": "Northstar Foundation", "donor_b": "Community Giving Circle"}


def pack(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def money(value):
    try:
        d = Decimal(str(value).replace(",", ""))
        if not d.is_finite() or d < 0 or d > 1000000 or d != d.quantize(Decimal("0.01")):
            raise ValueError()
        return format(d, ".2f")
    except (ValueError, InvalidOperation):
        raise Conflict("Use a non-negative amount with at most two decimal places.")


WORD_NUMBERS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
    "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "صفر": 0, "واحد": 1, "واحدة": 1, "اثنان": 2, "اثنين": 2, "ثلاث": 3, "ثلاثة": 3,
    "أربع": 4, "اربع": 4, "أربعة": 4, "اربعة": 4, "خمس": 5, "خمسة": 5, "ست": 6, "ستة": 6,
    "سبع": 7, "سبعة": 7, "ثمان": 8, "ثمانية": 8, "تسع": 9, "تسعة": 9, "عشر": 10, "عشرة": 10,
}


HOUSEHOLD_WORD = re.compile(r"household|famil|أسر|اسر|عائل", re.I)
NEGATION = re.compile(r"\b(not|never|no|haven't|have not|didn't|did not|unknown|unable)\b|لم|لا\s|غير", re.I)


def states_household_count(text, value):
    """True only when the source actually claims that many households.

    The first version of this guard looked for the word "household" anywhere in the
    source. The seeded field message says "We have NOT counted unique households",
    which contains the word — so a basket count could have been recorded as a
    household count. The window now has to carry the number and no negation.
    """
    text = text.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
    for match in HOUSEHOLD_WORD.finditer(text):
        window = text[max(0, match.start() - 70): match.end() + 70]
        if NEGATION.search(window):
            continue
        if re.search(rf"(?<!\d){int(value)}(?!\d)", window):
            return True
    return False


def numeric_values(text):
    """Every number a source states — digits, or a written word. Nothing derived."""
    text = text.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩٫٬", "0123456789.,"))
    found = {Decimal(n.replace(",", "")) for n in re.findall(r"\d[\d,]*(?:\.\d+)?", text)}
    for word in re.findall(r"[A-Za-z\u0600-\u06FF]+", text):
        value = WORD_NUMBERS.get(word.lower())
        if value is not None:
            found.add(Decimal(value))
    return found


class Store:
    def __init__(self, path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.db() as c:
            c.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY, engine TEXT NOT NULL,
              revision INTEGER NOT NULL DEFAULT 0, created REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS members(project TEXT, role TEXT, token_hash TEXT,
              PRIMARY KEY(project,role), FOREIGN KEY(project) REFERENCES projects(id));
            CREATE TABLE IF NOT EXISTS evidence(id INTEGER PRIMARY KEY, project TEXT, actor TEXT,
              kind TEXT, text TEXT, fingerprint TEXT, created REAL, status TEXT DEFAULT 'pending',
              note TEXT DEFAULT '', question_id INTEGER, attachment TEXT,
              UNIQUE(project,fingerprint));
            CREATE TABLE IF NOT EXISTS facts(project TEXT, key TEXT, value TEXT, evidence_id INTEGER,
              PRIMARY KEY(project,key));
            CREATE TABLE IF NOT EXISTS questions(id INTEGER PRIMARY KEY, project TEXT, key TEXT,
              recipient TEXT, text TEXT, status TEXT DEFAULT 'open', created REAL,
              UNIQUE(project,key));
            CREATE TABLE IF NOT EXISTS reports(id INTEGER PRIMARY KEY, project TEXT, version INTEGER,
              revision INTEGER, hash TEXT, payload TEXT, status TEXT DEFAULT 'draft', created REAL,
              UNIQUE(project,version));
            CREATE TABLE IF NOT EXISTS approvals(report_id INTEGER PRIMARY KEY, project TEXT,
              hash TEXT, acknowledged INTEGER, created REAL);
            CREATE TABLE IF NOT EXISTS inbox(id INTEGER PRIMARY KEY, project TEXT, recipient TEXT,
              kind TEXT, subject TEXT, body TEXT, delivery_key TEXT UNIQUE, created REAL);
            CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, project TEXT, kind TEXT,
              title TEXT, detail TEXT, created REAL);
            CREATE TABLE IF NOT EXISTS jobs(id INTEGER PRIMARY KEY, project TEXT, status TEXT DEFAULT 'queued',
              created REAL, started REAL, error TEXT DEFAULT '', attempts INTEGER DEFAULT 0);
            CREATE INDEX IF NOT EXISTS evidence_project ON evidence(project);
            CREATE INDEX IF NOT EXISTS events_project ON events(project);
            CREATE INDEX IF NOT EXISTS jobs_pending ON jobs(status,created);
            """)

    @contextmanager
    def db(self):
        c = sqlite3.connect(self.path, timeout=20)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys=ON")
        try:
            c.execute("BEGIN IMMEDIATE")
            yield c
            c.commit()
        except BaseException:
            c.rollback()
            raise
        finally:
            c.close()

    @staticmethod
    def event(c, pid, kind, title, detail=None):
        c.execute("INSERT INTO events(project,kind,title,detail,created) VALUES(?,?,?,?,?)",
                  (pid, kind, title, pack(detail or {}), time.time()))

    @staticmethod
    def enqueue(c, pid):
        if not c.execute("SELECT 1 FROM jobs WHERE project=? AND status='queued'", (pid,)).fetchone():
            c.execute("INSERT INTO jobs(project,created) VALUES(?,?)", (pid, time.time()))

    def create_project(self, engine="local"):
        if engine not in ("local", "bedrock"):
            raise Conflict("Unknown agent engine.")
        pid = secrets.token_urlsafe(12)
        tokens = {role: secrets.token_urlsafe(32) for role in ROLES}
        with self.db() as c:
            if c.execute("SELECT count(*) FROM projects WHERE created>?", (time.time()-3600,)).fetchone()[0] >= 100:
                raise Conflict("The demo has reached its hourly workspace limit. Try again later.")
            c.execute("INSERT INTO projects(id,engine,created) VALUES(?,?,?)", (pid, engine, time.time()))
            for role, token in tokens.items():
                c.execute("INSERT INTO members VALUES(?,?,?)", (pid, role, digest(token)))
            self.event(c, pid, "workspace", "A fresh field report, ready to follow through", {"synthetic": True})
        self.submit(pid, "finance", "FOOD RECEIPT F-101. 100 food baskets at USD 12.00 each. Total USD 1,200.00. Paid. Synthetic receipt.", "receipt")
        self.submit(pid, "finance", "Transport cost: USD 60.00. I recorded this expense but the receipt is still missing.", "expense_claim")
        self.submit(pid, "field", "We loaded 100 baskets. 92 baskets delivered, 8 returned to storage. We have not counted unique households.", "message")
        return {"id": pid, "tokens": tokens, "engine": engine}

    def authenticate(self, pid, token):
        if not token or len(token) > 200:
            raise Forbidden("Open your workspace invitation to continue.")
        with self.db() as c:
            row = c.execute("SELECT role FROM members WHERE project=? AND token_hash=?", (pid, digest(token))).fetchone()
            if not row:
                raise Forbidden("This invitation cannot access this workspace.")
            return row["role"]

    def submit(self, pid, role, text, kind="message", question_id=None, attachment=None):
        if role not in ("field", "finance"):
            raise Forbidden("Only registered contributors can add field evidence.")
        if kind not in ("message", "receipt", "expense_claim", "correction"):
            raise Conflict("Unsupported evidence type.")
        text = text.strip()
        if not text or len(text) > 10000:
            raise Conflict("Evidence must contain between 1 and 10,000 characters.")
        fp = digest(role + kind + text + (attachment or ""))
        with self.db() as c:
            if not c.execute("SELECT 1 FROM projects WHERE id=?", (pid,)).fetchone():
                raise Forbidden("Unknown workspace.")
            if question_id is not None:
                q = c.execute("SELECT * FROM questions WHERE project=? AND id=?", (pid, question_id)).fetchone()
                if not q or q["recipient"] != role:
                    raise Forbidden("This question belongs to a different contributor.")
            duplicate = c.execute("SELECT id FROM evidence WHERE project=? AND fingerprint=?", (pid, fp)).fetchone()
            if duplicate:
                return {"id": duplicate["id"], "duplicate": True}
            if c.execute("SELECT count(*) FROM evidence WHERE project=?", (pid,)).fetchone()[0] >= 80:
                raise Conflict("This demonstration workspace has reached its evidence limit.")
            eid = c.execute("INSERT INTO evidence(project,actor,kind,text,fingerprint,created,question_id,attachment) VALUES(?,?,?,?,?,?,?,?)",
                            (pid, role, kind, text, fp, time.time(), question_id, attachment)).lastrowid
            c.execute("UPDATE projects SET revision=revision+1 WHERE id=?", (pid,))
            c.execute("UPDATE reports SET status='outdated' WHERE project=? AND status IN ('draft','approved')", (pid,))
            self.event(c, pid, "evidence", f"{ROLES[role].split(' · ')[0]} added {'a correction' if kind == 'correction' else 'evidence'}", {"evidence_id": eid, "kind": kind})
            self.enqueue(c, pid)
            return {"id": eid, "duplicate": False}

    def pending(self, pid):
        with self.db() as c:
            return [dict(r) for r in c.execute("SELECT * FROM evidence WHERE project=? AND status='pending' ORDER BY id", (pid,))]

    @staticmethod
    def get_evidence(c, pid, eid, role=None):
        row = c.execute("SELECT * FROM evidence WHERE project=? AND id=?", (pid, eid)).fetchone()
        if not row:
            raise Conflict("Evidence does not belong to this workspace.")
        if role and row["actor"] != role:
            raise Forbidden("This contributor cannot attest this type of fact.")
        return row

    @staticmethod
    def set_fact(c, pid, key, value, eid):
        existing = c.execute("SELECT evidence_id FROM facts WHERE project=? AND key=?", (pid, key)).fetchone()
        if existing and existing["evidence_id"] > eid:
            raise Conflict("An older source cannot replace a newer accepted fact.")
        c.execute("INSERT INTO facts VALUES(?,?,?,?) ON CONFLICT(project,key) DO UPDATE SET value=excluded.value,evidence_id=excluded.evidence_id",
                  (pid, key, pack(value), eid))

    def record_expense(self, pid, eid, category, amount, currency, supported):
        if category not in ("food", "transport"):
            raise Conflict("This distribution report supports food and transport expenses.")
        amount = money(amount)
        with self.db() as c:
            e = self.get_evidence(c, pid, eid, "finance")
            if currency != "USD" or re.search(r"\b(EUR|GBP|YER)\b", e["text"], re.I):
                raise Conflict("Currency needs a finance decision. No exchange rate was assumed.")
            if Decimal(amount) not in numeric_values(e["text"]):
                raise Conflict("The amount does not appear in this source. Ask for clarification.")
            if supported and e["kind"] != "receipt":
                raise Conflict("An expense message is not a supporting receipt.")
            if e["status"] == "accepted":
                return {"recorded": False, "reason": "already accepted"}
            self.set_fact(c, pid, category, {"amount": amount, "supported": bool(supported), "currency": currency}, eid)
            c.execute("UPDATE evidence SET status='accepted',note=? WHERE id=?", (f"{category.title()} · USD {amount} · {'receipt-supported' if supported else 'reported, receipt missing'}", eid))
            if category == "transport" and supported:
                c.execute("UPDATE questions SET status='answered' WHERE project=? AND key='transport_receipt'", (pid,))
            self.event(c, pid, "fact", f"{category.title()} expense linked to its source", {"evidence_id": eid, "amount": amount, "supported": supported})
            return {"recorded": True}

    def record_distribution(self, pid, eid, loaded=None, delivered=None, returned=None, households=None):
        vals = {"loaded": loaded, "delivered": delivered, "returned": returned, "households": households}
        with self.db() as c:
            e = self.get_evidence(c, pid, eid, "field")
            if e["status"] == "accepted":
                return {"recorded": False}
            numbers = numeric_values(e["text"])
            # A field the source does not state is dropped, never recorded and never fatal:
            # losing one unsupported number must not cost us the counts the source does state.
            ignored = {}
            for key, v in list(vals.items()):
                if v is None:
                    continue
                if type(v) is not int or not 0 <= v <= 10000 or Decimal(v) not in numbers:
                    ignored[key] = "not stated in this source"
                    vals[key] = None
                elif key == "households" and not states_household_count(e["text"], v):
                    ignored[key] = ("the source does not state a household count; "
                                    "basket counts do not establish unique households")
                    vals[key] = None
            loaded, delivered, returned, households = (vals["loaded"], vals["delivered"],
                                                       vals["returned"], vals["households"])
            if all(v is None for v in vals.values()):
                raise Conflict("None of those counts appear in this source. Read it again, or defer it.")
            for key, v in vals.items():
                if v is not None:
                    self.set_fact(c, pid, key, v, eid)
            # A correction is never refused for failing to add up: the new counts are
            # recorded and the arithmetic gap becomes a visible issue for the coordinator.
            merged = {k: (v["value"] if isinstance(v, dict) else v)
                      for k, v in self.facts(c, pid).items()}
            gap = None
            if all(isinstance(merged.get(k), int) for k in ("loaded", "delivered", "returned")):
                missing = merged["loaded"] - merged["delivered"] - merged["returned"]
                if missing:
                    # The arithmetic is the easy half. What it means is that some
                    # households on the list have no answer, and the report says so
                    # in those words rather than hiding behind a sum.
                    n = abs(missing)
                    if missing > 0:
                        gap = (f"{n} basket{'s' if n != 1 else ''} unaccounted for: "
                               f"{merged['loaded']} loaded, {merged['delivered']} reported "
                               f"delivered, {merged['returned']} returned. "
                               f"{n} household{'s were' if n != 1 else ' was'} on the list "
                               f"with no answer either way.")
                    else:
                        gap = (f"{merged['delivered']} delivered plus {merged['returned']} "
                               f"returned is {n} more than the {merged['loaded']} loaded. "
                               f"One of these counts is wrong.")
            if gap:
                c.execute("UPDATE evidence SET status='review',note=? WHERE id=?", (gap, eid))
                self.event(c, pid, "review", "An uncertainty stays visible", {"evidence_id": eid, "reason": gap})
            else:
                c.execute("UPDATE evidence SET status='accepted',note='Field-reported counts; not independently verified' WHERE id=?", (eid,))
            if delivered is not None:
                c.execute("UPDATE questions SET status='answered' WHERE project=? AND key='delivery_count'", (pid,))
            self.event(c, pid, "correction" if e["kind"] == "correction" else "fact",
                       "Distribution figures updated from the field",
                       {"evidence_id": eid, **{k: v for k, v in vals.items() if v is not None},
                        **({"ignored": ignored} if ignored else {})})
            return {"recorded": True, **({"ignored": ignored} if ignored else {}),
                    **({"note": gap} if gap else {})}

    def transcribe_attachment(self, pid, eid, uploads_dir, reader=None):
        """Read an attached receipt photograph and write the transcription back as the source text.

        The picture becomes words in the evidence row, so every later guard — the amount
        must appear in the source — applies to what the paper actually said.
        """
        from . import vision
        with self.db() as c:
            e = self.get_evidence(c, pid, eid)
            if not e["attachment"]:
                raise Conflict("That source has no attached image.")
            if e["status"] != "pending":
                return {"transcribed": False, "reason": "already processed"}
        path = Path(uploads_dir) / Path(e["attachment"]).name
        if not path.exists():
            raise Conflict("The attached image is no longer available.")
        reading = (reader or vision.read_receipt)(path.read_bytes())
        text = vision.as_source_text(reading)
        # A vendor this team has never bought from is a review hint, carried in
        # AgentCore Memory because it outlives this workspace. Advisory only.
        ledger = {}
        if reading.get("ok") and reading.get("vendor"):
            from . import vendors
            ledger = vendors.check(reading["vendor"])
            if ledger.get("known") is False:
                text += "\nLedger: " + ledger["note"]
            vendors.remember(reading["vendor"], reading.get("invoice_no"),
                             str(reading["stated_total"]) if reading.get("stated_total") is not None else None)
        with self.db() as c:
            c.execute("UPDATE evidence SET text=? WHERE id=?", (text, eid))
            self.event(c, pid, "vision", "Read the receipt photograph", {
                "evidence_id": eid, "model": reading.get("model"),
                "total": str(reading.get("stated_total")) if reading.get("stated_total") is not None else None,
                "currency": reading.get("currency"), "items": len(reading.get("items") or []),
                "confidence": reading.get("confidence"),
                **({"mismatch": reading["mismatch"]} if reading.get("mismatch") else {}),
                **({"vendor_new": True} if ledger.get("known") is False else {}),
                **({"vendor_known": True} if ledger.get("known") is True else {})})
            if reading.get("mismatch"):
                c.execute("UPDATE evidence SET note=? WHERE id=?", (reading["mismatch"], eid))
        return {"transcribed": bool(reading.get("ok")), "text": text,
                "mismatch": reading.get("mismatch"),
                "currency": reading.get("currency"),
                "stated_total": str(reading["stated_total"]) if reading.get("stated_total") is not None else None}

    def unfollowed_gaps(self, pid):
        """Known gaps with no open question: (question key, recipient, what the agent must chase).

        Deterministic, so the promise 'it follows up' does not depend on the model
        remembering to. Returns nothing once a question for that key exists.
        """
        gaps = []
        with self.db() as c:
            open_keys = {r["key"] for r in c.execute(
                "SELECT key FROM questions WHERE project=? AND status IN ('open','answered')", (pid,))}
            facts = self.facts(c, pid)
        for key in ("transport", "food"):
            fact = facts.get(key)
            value = fact["value"] if isinstance(fact, dict) else None
            if isinstance(value, dict) and value.get("supported") is False and f"{key}_receipt" not in open_keys:
                gaps.append((f"{key}_receipt", "finance",
                             f"{value['amount']} {value.get('currency', 'USD')} of {key} spending is reported "
                             f"without a receipt."))
        if facts.get("delivered") is None and "delivery_count" not in open_keys:
            gaps.append(("delivery_count", "field", "No field-reported delivery count has been recorded."))
        return gaps

    def defer(self, pid, eid, reason):
        reason = reason.strip()[:400] or "This source needs a contributor clarification."
        with self.db() as c:
            e = self.get_evidence(c, pid, eid)
            if e['kind'] == 'expense_claim' and re.search(r'missing.*receipt|receipt.*missing|no receipt', reason, re.I):
                raise Conflict('Preserve reported spending: record this expense claim with supported=false. A missing receipt does not erase the reported expense.')
            if e["status"] != "pending":
                return {"deferred": False}
            c.execute("UPDATE evidence SET status='review',note=? WHERE id=?", (reason, eid))
            if e["question_id"]:
                c.execute("UPDATE questions SET status='unresolved' WHERE project=? AND id=?", (pid, e["question_id"]))
            self.event(c, pid, "review", "An uncertainty stays visible", {"evidence_id": eid, "reason": reason})
            return {"deferred": True}

    @staticmethod
    def facts(c, pid):
        return {r["key"]: {"value": json.loads(r["value"]), "source": r["evidence_id"]}
                for r in c.execute("SELECT * FROM facts WHERE project=?", (pid,))}

    @staticmethod
    def summary_from(facts):
        expenses = [facts[k]["value"] for k in ("food", "transport") if k in facts]
        reported = sum((Decimal(e["amount"]) for e in expenses), Decimal(0))
        supported = sum((Decimal(e["amount"]) for e in expenses if e["supported"]), Decimal(0))
        return {"reported": money(reported), "supported": money(supported), "unsupported": money(reported-supported),
                **{k: facts.get(k, {}).get("value") for k in ("loaded", "delivered", "returned", "households")}}

    def ask(self, pid, key, recipient, text):
        allowed = {"transport_receipt": "finance", "delivery_count": "field"}
        if allowed.get(key) != recipient:
            raise Forbidden("The agent cannot choose an unregistered recipient or question type.")
        with self.db() as c:
            f = self.facts(c, pid)
            if key == "transport_receipt" and ("transport" not in f or f["transport"]["value"]["supported"]):
                return {"asked": False, "reason": "No missing transport receipt"}
            if key == "delivery_count" and "delivered" in f:
                return {"asked": False, "reason": "The existing answer covers both donor reports"}
            exists = c.execute("SELECT id FROM questions WHERE project=? AND key=?", (pid, key)).fetchone()
            if exists:
                return {"asked": False, "question_id": exists["id"], "reason": "Already asked; avoid another interruption"}
            qid = c.execute("INSERT INTO questions(project,key,recipient,text,created) VALUES(?,?,?,?,?)", (pid, key, recipient, text[:1000], time.time())).lastrowid
            c.execute("INSERT INTO inbox(project,recipient,kind,subject,body,delivery_key,created) VALUES(?,?,?,?,?,?,?)",
                      (pid, recipient, "question", "One answer, two reports", pack({"question_id": qid, "text": text[:1000], "key": key}), f"question:{qid}", time.time()))
            self.event(c, pid, "question", f"Asked {ROLES[recipient].split(' · ')[0]} directly", {"question_id": qid, "text": text[:1000], "reused_by": 2})
            return {"asked": True, "question_id": qid}

    def prepare(self, pid):
        with self.db() as c:
            if c.execute("SELECT 1 FROM evidence WHERE project=? AND status='pending'", (pid,)).fetchone():
                raise Conflict("Process every new source before preparing the report.")
            f = self.facts(c, pid)
            summary = self.summary_from(f)
            revision = c.execute("SELECT revision FROM projects WHERE id=?", (pid,)).fetchone()[0]
            issues = [dict(r) for r in c.execute("SELECT id,note FROM evidence WHERE project=? AND status='review' ORDER BY id", (pid,))]
            payload = {"title": "September food distribution", "period": "September 2026 · Demonstration",
                       "summary": summary, "facts": f, "issues": issues,
                       "recipients": ["donor_a", "donor_b"], "synthetic": True,
                       "disclosure": "Synthetic scenario. Delivery counts are field-reported, not independently verified — a basket counted as delivered is not proof that a household received it. Receipt-supported spending is not proof of payment or impact."}
            h = digest(pack(payload))
            last = c.execute("SELECT * FROM reports WHERE project=? ORDER BY version DESC LIMIT 1", (pid,)).fetchone()
            if last and last["hash"] == h and last["revision"] == revision:
                return {"report_id": last["id"], "changed": False}
            version = last["version"] + 1 if last else 1
            rid = c.execute("INSERT INTO reports(project,version,revision,hash,payload,created) VALUES(?,?,?,?,?,?)", (pid, version, revision, h, pack(payload), time.time())).lastrowid
            self.event(c, pid, "report", f"Report v{version} prepared for two donors", {"report_id": rid, "hash": h, "version": version})
            return {"report_id": rid, "version": version, "changed": True}

    def approve(self, pid, role, report_id, content_hash, acknowledge=False):
        if role != "coordinator":
            raise Forbidden("A coordinator must approve the exact report version.")
        with self.db() as c:
            r = c.execute("SELECT * FROM reports WHERE project=? AND id=?", (pid, report_id)).fetchone()
            revision = c.execute("SELECT revision FROM projects WHERE id=?", (pid,)).fetchone()[0]
            if not r or r["revision"] != revision or r["hash"] != content_hash or r["status"] == "outdated":
                raise Conflict("Evidence changed. Review and approve the current report instead.")
            if c.execute("SELECT 1 FROM evidence WHERE project=? AND status='pending'", (pid,)).fetchone():
                raise Conflict("New evidence is still being reviewed.")
            if c.execute("SELECT 1 FROM questions WHERE project=? AND status='open'", (pid,)).fetchone():
                raise Conflict("A contributor is still answering. Wait for their reply.")
            payload = json.loads(r["payload"])
            if payload["summary"]["delivered"] is None or "food" not in payload["facts"]:
                raise Conflict("A food expense and field-reported delivery count are required.")
            if (Decimal(payload["summary"]["unsupported"]) > 0 or payload["issues"]) and not acknowledge:
                raise Conflict("Acknowledge the unresolved items before sharing this incomplete report.")
            c.execute("INSERT OR IGNORE INTO approvals VALUES(?,?,?,?,?)", (report_id, pid, content_hash, int(acknowledge), time.time()))
            if r["status"] != "delivered":
                c.execute("UPDATE reports SET status='approved' WHERE id=?", (report_id,))
            self.event(c, pid, "approval", f"Amal approved report v{r['version']}", {"hash": content_hash, "report_id": report_id})
            return {"approved": True}

    def deliver(self, pid):
        with self.db() as c:
            revision = c.execute("SELECT revision FROM projects WHERE id=?", (pid,)).fetchone()[0]
            reports = c.execute("SELECT r.* FROM reports r JOIN approvals a ON a.report_id=r.id AND a.hash=r.hash WHERE r.project=? AND r.status='approved' AND r.revision=?", (pid, revision)).fetchall()
            for r in reports:
                payload = json.loads(r["payload"])
                # Native inbox insertion, receipt and status commit in one transaction.
                # No external network delivery or exactly-once external-send claim.
                for recipient in payload["recipients"]:
                    key = f"report:{r['id']}:{recipient}"
                    body = {"report_id": r["id"], "version": r["version"], "hash": r["hash"],
                            "summary": payload["summary"], "disclosure": payload["disclosure"],
                            "issues": [i["note"] for i in payload["issues"]], "title": payload["title"],
                            "language": "ar" if recipient == "donor_b" else "en"}
                    result = c.execute("INSERT OR IGNORE INTO inbox(project,recipient,kind,subject,body,delivery_key,created) VALUES(?,?,?,?,?,?,?)",
                                       (pid, recipient, "report", f"September distribution · v{r['version']}", pack(body), key, time.time()))
                    if result.rowcount:
                        self.event(c, pid, "delivery", f"Delivered to {ROLES[recipient]}", {"report_id": r["id"], "recipient": recipient, "receipt": key, "channel": "native_inbox"})
                c.execute("UPDATE reports SET status='delivered' WHERE id=?", (r["id"],))
            return {"reports_delivered": len(reports)}

    def claim_job(self):
        with self.db() as c:
            c.execute("UPDATE jobs SET status='queued' WHERE status='running' AND started<? AND attempts<3", (time.time()-300,))
            c.execute("UPDATE jobs SET status='failed',error='Worker lease expired; retry this workspace.' WHERE status='running' AND started<? AND attempts>=3", (time.time()-300,))
            job = c.execute("SELECT j.*,p.engine FROM jobs j JOIN projects p ON p.id=j.project WHERE j.status='queued' ORDER BY j.id LIMIT 1").fetchone()
            if not job:
                return None
            c.execute("UPDATE jobs SET status='running',started=?,attempts=attempts+1 WHERE id=?", (time.time(), job["id"]))
            return dict(job)

    def finish_job(self, job_id, error=""):
        with self.db() as c:
            c.execute("UPDATE jobs SET status=?,error=? WHERE id=?", ("failed" if error else "done", error[:200], job_id))

    def retry(self, pid, role):
        if role != "coordinator":
            raise Forbidden("Only the coordinator can retry the agent.")
        with self.db() as c:
            if c.execute("SELECT 1 FROM jobs WHERE project=? AND status IN ('queued','running')", (pid,)).fetchone():
                return
            c.execute("UPDATE jobs SET status='done' WHERE project=? AND status='failed'", (pid,))
            self.enqueue(c, pid)

    def log(self, pid, kind, title, detail=None):
        with self.db() as c:
            self.event(c, pid, kind, title, detail)

    def state(self, pid, role):
        if role not in ROLES:
            raise Forbidden("Unknown role.")
        with self.db() as c:
            project = c.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
            if not project:
                raise Forbidden("Unknown workspace.")
            donor = role.startswith("donor")
            f = self.facts(c, pid)
            evidence = [dict(r) for r in c.execute("SELECT id,actor,kind,text,created,status,note,question_id,attachment FROM evidence WHERE project=? ORDER BY id", (pid,))] if not donor else []
            if role in ("field", "finance"):
                evidence = [e for e in evidence if e["actor"] == role]
            questions = [dict(r) for r in c.execute("SELECT * FROM questions WHERE project=? ORDER BY id", (pid,))] if not donor else []
            if role != "coordinator":
                questions = [q for q in questions if q["recipient"] == role]
            inbox = [dict(r) for r in c.execute("SELECT * FROM inbox WHERE project=? AND recipient=? ORDER BY id DESC", (pid, role))]
            for item in inbox:
                item["body"] = json.loads(item["body"])
            report = c.execute("SELECT * FROM reports WHERE project=? ORDER BY version DESC LIMIT 1", (pid,)).fetchone() if role == "coordinator" else None
            report = dict(report) if report else None
            if report:
                report["payload"] = json.loads(report["payload"])
            events = [dict(r) for r in c.execute("SELECT * FROM events WHERE project=? ORDER BY id DESC LIMIT 80", (pid,))] if role == "coordinator" else []
            for e in events:
                e["detail"] = json.loads(e["detail"])
            jobs = [dict(r) for r in c.execute("SELECT id,status,error,created FROM jobs WHERE project=? ORDER BY id DESC LIMIT 5", (pid,))]
            receipts = [dict(r) for r in c.execute("SELECT recipient,delivery_key,created FROM inbox WHERE project=? AND kind='report' ORDER BY id DESC", (pid,))] if role == "coordinator" else []
            return {"project": dict(project), "role": role, "role_name": ROLES[role], "summary": self.summary_from(f) if role == "coordinator" else None,
                    "facts": f if role == "coordinator" else {}, "evidence": evidence, "questions": questions, "report": report,
                    "inbox": inbox, "events": events, "jobs": jobs if role == "coordinator" else [], "receipts": receipts,
                    "busy": any(j["status"] in ("queued", "running") for j in jobs), "synthetic": True}

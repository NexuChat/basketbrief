"""What the work costs without the agent, counted rather than guessed.

    python scripts/baseline.py

We did not time a coordinator. Timing one person once would be an anecdote, and
timing enough people to mean anything was not available to us before the
deadline — so this file measures the thing that *is* measurable from the same
evidence the agent consumes: **the acts a person must perform**.

An act here is one irreducible piece of human work:

  read        opening one source and understanding what it claims
  transcribe  copying one figure from a source into a ledger or a report
  compose     writing one message to a contributor and later reading the reply
  chase       sending a reminder because the first message went unanswered
  reconcile   recomputing the totals by hand and checking they still agree
  cross-check comparing two donor reports so they cannot contradict each other
  decide      a judgement only a person can make

The manual column is derived from the real data — the number of sources, the
number of distinct figures each one states, the number of donors, the number of
facts the correction invalidates. Nothing is hard-coded except the two constants
named below, which are stated so you can disagree with them and rerun.

What this is not: a time saving, a cost saving, or a claim about outcomes for
anyone receiving aid. It is a count of steps, and a count of steps is all it is.
"""
import sys
import tempfile
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from basketbrief.agent import local_process                       # noqa: E402
from basketbrief.store import Conflict, Store                     # noqa: E402

# The two assumptions. Both are deliberately conservative — generous to the
# manual way of working, so the comparison cannot be accused of stacking itself.
CHASES_PER_UNANSWERED_QUESTION = 1     # one reminder, not the two or three that are usual
REREADS_PER_RECONCILE = 1             # the figures are checked once, not twice

CORRECTION = "Correction: we recounted at the church hall. 88 kits were delivered, not 92."
RECEIPT = ("RECEIPT T-204 · AL-NOOR TRANSPORT · 2026-09-09. Truck hire, depot to "
           "Creekside, plus loading labour. Total USD 60.00. Paid in cash. "
           "Synthetic receipt.")


class Tally:
    def __init__(self, label):
        self.label = label
        self.rows = []

    def add(self, kind, n, why):
        if n:
            self.rows.append((kind, n, why))

    @property
    def total(self):
        return sum(n for _, n, _ in self.rows)

    def show(self):
        print(f"\n  {self.label}")
        print(f"  {'─' * 74}")
        for kind, n, why in self.rows:
            print(f"    {kind:<12} {n:>3}   {why}")
        print(f"    {'total':<12} {self.total:>3}")


def figures_in(fact_value):
    """A money fact is two figures a person must carry: the amount and whether
    a receipt stands behind it. A count is one."""
    return 2 if isinstance(fact_value, dict) else 1


def main():
    tmp = Path(tempfile.mkdtemp(prefix="basketbrief-baseline-"))
    store = Store(tmp / "baseline.db")
    pid = store.create_project("local")["id"]

    seeded = store.state(pid, "coordinator")["evidence"]
    local_process(store, pid)
    st = store.state(pid, "coordinator")
    facts = st["facts"]
    donors = st["report"]["payload"]["recipients"]
    open_q = [q for q in st["questions"] if q["status"] == "open"]

    n_sources = len(seeded)
    n_figures = sum(figures_in(f["value"]) for f in facts.values())
    n_donors = len(donors)
    n_gaps = len(open_q)

    # ── by hand ──────────────────────────────────────────────────────────
    hand = Tally("Without the agent — what a coordinator must do")
    hand.add("read", n_sources, f"{n_sources} sources, each from a different person")
    hand.add("transcribe", n_figures,
             f"{n_figures} figures stated across those sources, into one ledger")
    hand.add("compose", n_gaps, f"{n_gaps} question about the missing receipt")
    hand.add("chase", n_gaps * CHASES_PER_UNANSWERED_QUESTION,
             "one reminder, because the first message is not answered at once")
    hand.add("read", n_gaps, "the reply, and the receipt attached to it")
    hand.add("transcribe", 2, "the amount from that receipt, and that it is now supported")
    hand.add("reconcile", 1 + REREADS_PER_RECONCILE,
             "budget, reported and supported spending must agree with the counts")
    hand.add("transcribe", n_figures * n_donors,
             f"every figure again, into {n_donors} donor reports written separately")
    hand.add("cross-check", 1, f"the {n_donors} reports must not contradict each other")
    hand.add("decide", 1, "is this fit to send")
    before_correction = hand.total

    # ── the correction lands ─────────────────────────────────────────────
    store.submit(pid, "field", CORRECTION, "message")
    local_process(store, pid)
    after = store.state(pid, "coordinator")
    moved = [k for k, v in after["facts"].items()
             if k in facts and v["value"] != facts[k]["value"]]
    issues = [e for e in after["evidence"] if e["status"] == "review"]

    hand.add("read", 1, "the correction")
    hand.add("transcribe", len(moved) * (1 + n_donors),
             f"{len(moved)} changed fact, in the ledger and in each donor report")
    hand.add("reconcile", 1 + REREADS_PER_RECONCILE,
             "the counts no longer add up; work out by how much and what it means")
    hand.add("cross-check", 1, "both reports again, against each other and against v2")
    hand.add("decide", 1, "is the amended version fit to send")

    # ── with the agent ───────────────────────────────────────────────────
    agent = Tally("With the agent — what is left for a person")
    agent.add("decide", 1, "approve one exact version, bound to its content hash")
    agent.add("decide", 1, "approve the amended version after the correction")

    # what the agent did instead, taken from the record rather than asserted
    ev = after["events"]
    kinds = {}
    for e in ev:
        kinds[e["kind"]] = kinds.get(e["kind"], 0) + 1

    hand.show()
    agent.show()

    print(f"\n  {'─' * 76}")
    print(f"  Acts required of a person:  {hand.total} by hand   →   {agent.total} with the agent")
    print(f"  Of those, {before_correction} fall before the correction and "
          f"{hand.total - before_correction} after it.")
    print(f"\n  The agent recorded {len(ev)} steps of its own to absorb them "
          f"({', '.join(f'{v} {k}' for k, v in sorted(kinds.items()))}).")

    # ── the part that is not about effort at all ─────────────────────────
    print(f"\n  {'─' * 76}")
    print("  And the two things the count cannot show:")
    if issues:
        print(f"    · the gap is stated, not absorbed — \"{issues[0]['note'][:96]}…\"")
    try:
        r = st["report"]
        store.approve(pid, "coordinator", r["id"], r["hash"], acknowledge=True)
        print("    · \033[31mthe stale approval was accepted — that is a defect\033[0m")
        return 1
    except Conflict:
        print("    · the approval bound to the old version is refused, not silently reused")

    print(f"\n  Assumptions, so you can disagree and rerun: "
          f"{CHASES_PER_UNANSWERED_QUESTION} chase per unanswered question, "
          f"{REREADS_PER_RECONCILE} re-read per reconciliation.")
    print("  This counts steps. It is not a time saving, a cost saving, or a claim")
    print(f"  about outcomes for anyone receiving aid.\n  Workspace: {tmp}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Measure the deployed agent across full journeys. Everything here is observed."""
import json, subprocess, sys, time

B = "https://basketbrief.mlki.app"
SHOT = str(__import__("pathlib").Path(__file__).resolve().parent.parent / "basketbrief" / "static" / "sample-receipt.png")


def curl(args, timeout=40):
    out = subprocess.run(["curl", "-s", "-m", str(timeout)] + args, capture_output=True, text=True)
    return out.stdout


def api(pid, token, path="", method="GET", data=None, form=None, code_only=False):
    args = [f"{B}/api/projects/{pid}{path}", "-H", f"authorization: Bearer {token}"]
    if code_only:
        args = ["-o", "/dev/null", "-w", "%{http_code}"] + args
    if method != "GET":
        args += ["-X", method]
    if data is not None:
        args += ["-H", "content-type: application/json", "-d", json.dumps(data)]
    for f in (form or []):
        args += ["-F", f]
    return curl(args)


def idle(pid, token, limit=90):
    for _ in range(limit):
        time.sleep(2)
        st = json.loads(api(pid, token))
        if not st["busy"]:
            return st
    raise SystemExit("never went idle")


def run_once(n):
    t0 = time.time()
    created = json.loads(curl([f"{B}/api/projects", "-X", "POST", "-H", "content-type: application/json", "-d", "{}"]))
    pid, tok = created["id"], created["tokens"]
    st = idle(pid, tok["coordinator"])
    first_cycle = time.time() - t0
    q = [x for x in st["questions"] if x["status"] == "open"]
    asked_once = len(q) == 1
    api(pid, tok["finance"], "/upload", "POST",
        form=[f"file=@{SHOT};type=image/png", f"question_id={q[0]['id'] if q else 0}"])
    st = idle(pid, tok["coordinator"])
    read_from_photo = st["summary"]["unsupported"] == "0.00"
    report = st["report"]
    api(pid, tok["coordinator"], "/approve", "POST",
        data={"report_id": report["id"], "hash": report["hash"], "acknowledge": True})
    time.sleep(1.5)
    st = json.loads(api(pid, tok["coordinator"]))
    deliveries = len(st["receipts"])
    api(pid, tok["field"], "/evidence", "POST",
        data={"text": "Correction: we recounted at the church hall. 88 kits were delivered, not 92.",
              "kind": "message"})
    st = idle(pid, tok["coordinator"])
    stale = api(pid, tok["coordinator"], "/approve", "POST",
                data={"report_id": report["id"], "hash": report["hash"], "acknowledge": True}, code_only=True)
    wall = time.time() - t0

    def det(e):
        return e["detail"] if isinstance(e["detail"], dict) else json.loads(e["detail"])

    cycles = [det(e) for e in st["events"] if e["kind"] == "complete"]
    issues = [i["note"] for i in (st["report"] or {}).get("payload", {}).get("issues", [])]
    return {
        "run": n, "wall_s": round(wall, 1), "first_cycle_s": round(first_cycle, 1),
        "cycles": len(cycles), "cycle_seconds": [c.get("seconds") for c in cycles],
        "input_tokens": sum(c.get("input_tokens") or 0 for c in cycles),
        "asked_exactly_once": asked_once,
        "photo_closed_the_gap": read_from_photo,
        "supported": st["summary"]["supported"], "unsupported": st["summary"]["unsupported"],
        "delivered": st["summary"]["delivered"], "report_version": (st["report"] or {}).get("version"),
        "donor_deliveries": deliveries, "stale_approval_http": stale,
        "gap_named_in_households": bool(issues and "household" in issues[0]),
    }


if __name__ == "__main__":
    rows = [run_once(i) for i in range(1, int(sys.argv[1]) + 1)]
    print(json.dumps(rows, indent=1))
    with open("measurements.json", "w") as f:
        json.dump(rows, f, indent=1)

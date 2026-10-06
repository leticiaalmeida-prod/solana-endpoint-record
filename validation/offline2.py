"""Re-judge round-2 saved replies (verifier format v2) with the current checker: section 2 claims and literal levels."""
import json, os, subprocess, sys, collections
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "record"))
from knock import judge, VERSION  # noqa: E402
from literal import level  # noqa: E402

W, labels, sample, out = sys.argv[1], json.load(open(sys.argv[2])), json.load(open(sys.argv[3])), sys.argv[4]
B = {f"{b['method']} {b['url']}": b["n"] for b in json.load(open(os.path.join(os.path.dirname(W), "blind-list.json")))}
eps = {e["id"]: e for e in json.loads(subprocess.check_output(["git", "show", f"{sample['snapshot']}:data/endpoints.json"]))["endpoints"]}

def fetch_of(path):
    r = json.load(open(path))
    st = r.get("status")
    h = r.get("response_headers") or []
    h = list(h.items()) if isinstance(h, dict) else [tuple(x) for x in h]
    return {"status": int(st) if str(st).isdigit() else None, "headers": h,
            "body": (r.get("body_first_64KB") or "").encode(), "error": r.get("error") or "timeout"}

def claims(j):
    c = set()
    for n in j["notes"]:
        if n.startswith("asks ") and "catalog says" in n: c.add("N1")
        elif n.startswith("payment address differs"): c.add("N2")
        elif n.startswith("gave a real answer without asking"): c.add("N3")
        elif n.startswith("network name"): c.add("N4")
        elif n.startswith("asks for payment but offers no Solana"): c.add("N5")
        elif n.startswith("only accepts test-network"): c.add("N6")
    v = j["verdict"]
    c |= {"error": {"E"}, "unclear": {"U"}, "down": {"D"}, "alive": {"ALIVE"}}.get(v, set())
    return c

tally = collections.Counter(); rows = []
for l in labels:
    i = f"{l['method']} {l['url']}"; n = B[i]; ep = eps.get(i, {"method": l["method"], "url": l["url"]})
    s2 = l.get("section2")
    p2 = f"{W}/raw/{n}-s2.json"
    if s2 and s2.get("codes") and os.path.exists(p2) and not all(v.get("value") == "not_applicable" for v in s2["codes"].values()):
        mine = claims(judge(ep, fetch_of(p2)))
        theirs = {k for k, v in s2["codes"].items() if v.get("value") in (True, "true")}
        ok = mine == theirs; tally["s2 agree" if ok else "s2 disagree"] += 1
        if not ok: rows.append(["s2", n, sorted(mine), sorted(theirs), i])
    ps = f"{W}/raw/{n}-strict.json"; t = ((l.get("literal") or {}).get("strict") or {}).get("level")
    if t and t != "L0" and os.path.exists(ps):
        mine = level(judge(ep, fetch_of(ps))); theirs = {"NONE": "served"}.get(t, t)
        ok = mine == theirs; tally["literal agree" if ok else "literal disagree"] += 1
        if not ok: rows.append(["lit", n, mine, theirs, i])
json.dump({"checker_version": VERSION, "tally": tally, "disagree": rows}, open(out, "w"), indent=1)
print(f"checker v{VERSION} on round-2 evidence:", dict(tally))
for r in rows: print("  ", r[0], f"#{r[1]}", "ours", r[2], "theirs", r[3], "|", r[4][:70])

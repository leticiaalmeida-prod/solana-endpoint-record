"""Score round 4 (METHOD.md, "Round 4"): literal levels, catalog and waiting list, against the blind labels.

Usage: python3 compare4.py catalog <sample-catalog.json> <labels.json> <out.json>
       python3 compare4.py waitlist <sample-waitlist.json> <labels.json> <out.json> <queue.json>
"""
import collections, json, math, subprocess, sys

kind, sample, labels, out = sys.argv[1], json.load(open(sys.argv[2])), json.load(open(sys.argv[3])), sys.argv[4]
if kind == "catalog":
    ours = json.loads(subprocess.check_output(["git", "show", f"{sample['source']}:data/literal.json"]))["rows"]
else:
    ours = {e["id"]: e for r in json.load(open(sys.argv[5]))["new"] for e in r["endpoints"]}
lab = {f"{l['method']} {l['url']}": l for l in labels if l.get("kind") == kind}
SAME = {"NONE": "served", "free": "served"} if kind == "catalog" else {"served": "free"}


def wilson(k, n, z=1.96):
    if not n:
        return (0.0, 0.0)
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def theirs(i, mode):
    lv = (((lab[i].get("literal") or {}).get(mode)) or {}).get("level")
    return SAME.get(lv, lv)


report = {"kind": kind, "levels": [], "disagree": [], "mpp": None}
for mode in ("strict", "lenient"):
    print(f"{kind}, {mode}:")
    for lv, ids in sample["strata"].items():
        pairs = [(ours[i][mode]["level"], theirs(i, mode)) for i in ids if i in lab]
        k = sum(a == b for a, b in pairs); n = len(pairs); lo, hi = wilson(k, n)
        report["levels"].append([mode, lv, sample["population"].get(lv, 0), k, n, lo, hi, lo >= 0.8])
        print(f"  {lv} (pop {sample['population'].get(lv, 0)}): {k}/{n}, {lo:.0%}-{hi:.0%} "
              f"{'quotable' if lo >= 0.8 else 'NOT quotable'}  theirs when differ: "
              f"{dict(collections.Counter(b for a, b in pairs if a != b))}")
        if mode == "strict":
            report["disagree"] += [[lv, i] for i in ids if i in lab and ours[i][mode]["level"] != theirs(i, mode)]
# MPP agreement (change 22), strict request only
m = [(bool(ours[i]["strict"].get("mpp_solana")), bool(lab[i].get("mpp_solana")))
     for i in sample["cases"] if i in lab and "url" in ours[i]["strict"]]
report["mpp"] = {"both": sum(a and b for a, b in m), "ours_only": sum(a and not b for a, b in m),
                 "theirs_only": sum(b and not a for a, b in m), "n": len(m)}
print("MPP:", report["mpp"])
print("missing labels:", len([c for c in sample["cases"] if c not in lab]), "| disagreements:", len(report["disagree"]))
json.dump(report, open(out, "w"), indent=1)

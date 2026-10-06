"""Score round 2 (METHOD.md sections 6, 7 and 9): checker v0.2 claims and literal-agent levels vs the blind labels."""
import json, math, subprocess, sys, collections

sample, labels, out = json.load(open(sys.argv[1])), json.load(open(sys.argv[2])), sys.argv[3]
show = lambda p: json.loads(subprocess.check_output(["git", "show", f"{sample['snapshot']}:{p}"]))
literal = show("data/literal.json")["rows"]
lab = {f"{l['method']} {l['url']}": l for l in labels}

def wilson(k, n, z=1.96):
    if not n: return (0.0, 0.0)
    p = k / n; d = 1 + z*z/n; c = (p + z*z/(2*n)) / d; h = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / d
    return (c - h, c + h)

def code_true(l, code):
    s2 = l.get("section2") or {}
    for k, v in (s2.get("codes") or {}).items():
        if k.split()[0].upper() == code:
            return v.get("value") in (True, "true")
    return False

report = {"claims": [], "levels": [], "disagree": []}
print(f"{'claim':6} {'pop':>5} {'right':>7} {'95% CI':>12}  quotable")
for code, ids in sample["strataA"].items():
    k = sum(code_true(lab[i], code) for i in ids if i in lab); n = sum(i in lab for i in ids)
    lo, hi = wilson(k, n); q = lo >= 0.8
    report["claims"].append([code, sample["populationA"][code], k, n, lo, hi, q])
    print(f"{code:6} {sample['populationA'][code]:5} {k:3}/{n:<3} {lo:5.0%}-{hi:4.0%}  {'yes' if q else 'NO'}")
    report["disagree"] += [["A", code, i] for i in ids if i in lab and not code_true(lab[i], code)]
print()
for mode in ("strict", "lenient"):
    print(f"literal agent, {mode}:")
    for lv, ids in sample["strataB"].items():
        pairs = [(literal[i][mode]["level"], ((lab[i].get("literal") or {}).get(mode) or {}).get("level")) for i in ids if i in lab]
        k = sum(a == b for a, b in pairs); n = len(pairs); lo, hi = wilson(k, n)
        report["levels"].append([mode, lv, sample["populationB"][lv], k, n, lo, hi, lo >= 0.8])
        print(f"  {lv}: {k}/{n} agree, {lo:.0%}-{hi:.0%}  {'quotable' if lo >= 0.8 else 'NOT quotable'}  "
              f"(theirs when we differ: {dict(collections.Counter(b for a, b in pairs if a != b))})")
        if mode == "strict":
            report["disagree"] += [["B", lv, i] for i in ids if i in lab and literal[i][mode]["level"] != ((lab[i].get("literal") or {}).get(mode) or {}).get("level")]
missing = [c for c in sample["cases"] if c not in lab]
print("\nmissing labels:", len(missing), "| disagreements to adjudicate:", len(report["disagree"]))
json.dump(report, open(out, "w"), indent=1)

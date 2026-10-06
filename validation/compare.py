"""Compare the checker's snapshot claims with the independent labels (METHOD.md section 6)."""
import json, math, subprocess, sys, collections
sample = json.load(open(sys.argv[1])); labels = json.load(open(sys.argv[2])); blind = json.load(open(sys.argv[3]))
snap = json.loads(subprocess.check_output(["git", "show", f"{sample['snapshot']}:data/latest.json"]))["checks"]
lab = {f"{l['method']} {l['url']}": l for l in labels}

def wilson(k, n, z=1.96):
    if n == 0: return (0, 0)
    p = k / n; d = 1 + z*z/n; c = (p + z*z/(2*n)) / d; h = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / d
    return (c - h, c + h)

CODE = {"N1": "N1", "N2": "N2", "N3": "N3", "N4": "N4", "N5": "N5", "N6": "N6", "E": "E", "U": "U", "D": "D", "ALIVE": "ALIVE"}
def val(l, code):
    for k, v in l["codes"].items():
        if k.split()[0].upper().startswith(code): return v["value"]
    return None

rows, disagree = [], []
for code, ids in sample["strata"].items():
    k = n = 0
    for i in ids:
        v = val(lab[i], code)
        if v == "not_applicable" or v is None:
            disagree.append((code, i, "n/a", lab[i]["codes"])); n += 1; continue
        n += 1; k += v is True or v == "true"
        if not (v is True or v == "true"): disagree.append((code, i, v, None))
    lo, hi = wilson(k, n)
    rows.append((code, sample["population"][code], k, n, lo, hi))
print(f"{'claim':6} {'pop':>5} {'right':>6} {'95% CI':>14}  quotable(>=80%)")
for code, pop, k, n, lo, hi in rows:
    print(f"{code:6} {pop:5} {k:3}/{n:<3} {lo:6.0%}-{hi:4.0%}   {'yes' if lo >= .8 else 'NO'}")
# ALIVE as miss-rate: alive cases where independent check finds any problem code true
miss = [i for i in sample["strata"]["ALIVE"] if any(val(lab[i], c) in (True, "true") for c in ["N1","N2","N3","N4","N5","N6","E","U","D"])]
lo, hi = wilson(len(miss), 50); print(f"ALIVE misses: {len(miss)}/50, 95% CI {lo:.0%}-{hi:.0%}")
json.dump({"rows": rows, "disagree": [(c, i, str(v)) for c, i, v, _ in disagree], "alive_misses": miss},
          open(sys.argv[4], "w"), indent=1)
print("disagreements:", collections.Counter(c for c, *_ in disagree))

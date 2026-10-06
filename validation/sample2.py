"""Round 2 sample (METHOD.md sections 3 and 9): checker v0.2 claims (seed A) and literal-agent levels (seed B)."""
import json, random, subprocess, sys

SNAP, SEED_A, SEED_B, OUT = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
show = lambda p: json.loads(subprocess.check_output(["git", "show", f"{SNAP}:{p}"]))
checks = show("data/latest.json")["checks"]
literal = show("data/literal.json")["rows"]

def claims(c):
    out = set()
    for n in c["notes"]:
        if n.startswith("asks ") and "catalog says" in n: out.add("N1")
        elif n.startswith("payment address differs"): out.add("N2")
        elif n.startswith("gave a real answer without asking"): out.add("N3")
        elif n.startswith("network name"): out.add("N4")
        elif n.startswith("asks for payment but offers no Solana"): out.add("N5")
        elif n.startswith("only accepts test-network"): out.add("N6")
    v = c["verdict"]
    if v == "error": out.add("E")
    if v == "unclear": out.add("U")
    if v == "down": out.add("D")
    if v == "alive": out.add("ALIVE")
    return out

SIZES_A = {"N2": None, "N6": None, "N1": 20, "N3": 20, "N4": 20, "N5": 20, "E": 20, "D": 20, "U": 20, "ALIVE": 50}
SIZES_B = {"L0": 20, "L1": 20, "L2": 20, "L3": 50}
popA = {k: sorted(i for i, c in checks.items() if k in claims(c)) for k in SIZES_A}
popB = {k: sorted(i for i, r in literal.items() if r["strict"]["level"] == k) for k in SIZES_B}
ra, rb = random.Random(SEED_A), random.Random(SEED_B)
pick = lambda ids, n, r: ids if n is None or len(ids) <= n else r.sample(ids, n)
strataA = {k: pick(popA[k], n, ra) for k, n in SIZES_A.items()}
strataB = {k: pick(popB[k], n, rb) for k, n in SIZES_B.items()}
cases = sorted({i for v in list(strataA.values()) + list(strataB.values()) for i in v})
json.dump({"snapshot": SNAP, "seeds": [SEED_A, SEED_B], "populationA": {k: len(v) for k, v in popA.items()},
           "populationB": {k: len(v) for k, v in popB.items()}, "strataA": strataA, "strataB": strataB, "cases": cases},
          open(f"{OUT}/sample.json", "w"), indent=1)
blind = [{"n": n, "method": c.split(" ", 1)[0], "url": c.split(" ", 1)[1]}
         for n, c in enumerate(random.Random(SEED_A + SEED_B).sample(cases, len(cases)), 1)]
json.dump(blind, open(f"{OUT}/blind-list.json", "w"), indent=1)
print("A:", {k: f"{len(strataA[k])}/{len(popA[k])}" for k in SIZES_A})
print("B:", {k: f"{len(strataB[k])}/{len(popB[k])}" for k in SIZES_B}, "unique cases:", len(cases))

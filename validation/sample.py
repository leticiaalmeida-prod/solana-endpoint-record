"""Draw the stratified validation sample from a frozen snapshot (see METHOD.md section 3)."""
import json, random, subprocess, sys

SNAP, SEED, OUT = sys.argv[1], int(sys.argv[2]), sys.argv[3]
show = lambda p: json.loads(subprocess.check_output(["git", "show", f"{SNAP}:{p}"]))
checks = show("data/latest.json")["checks"]

def claims(c):
    out = set()
    for n in c["notes"]:
        if n.startswith("asks ") and "catalog says" in n: out.add("N1")
        elif n.startswith("payment address differs"): out.add("N2")
        elif n.startswith("answered without asking"): out.add("N3")
        elif n.startswith("network name"): out.add("N4")
        elif n.startswith("asks for payment but offers no Solana"): out.add("N5")
        elif n.startswith("only accepts test-network"): out.add("N6")
    v = c["verdict"]
    if v == "error": out.add("E")
    if v == "unclear": out.add("U")
    if v == "down": out.add("D")
    if v == "alive": out.add("ALIVE")
    return out

SIZES = {"N2": None, "N6": None, "N1": 20, "N3": 20, "N4": 20, "N5": 20, "E": 20, "D": 20, "U": 10, "ALIVE": 50}
pop = {k: sorted(i for i, c in checks.items() if k in claims(c)) for k in SIZES}
rng = random.Random(SEED)
strata = {k: (ids if n is None or len(ids) <= n else rng.sample(ids, n)) for k, ids in pop.items() for n in [SIZES[k]]}
cases = sorted({i for ids in strata.values() for i in ids})
human = random.Random(SEED + 1).sample(cases, 20)
json.dump({"snapshot": SNAP, "seed": SEED, "population": {k: len(v) for k, v in pop.items()},
           "strata": strata, "cases": cases, "human": sorted(human)}, open(f"{OUT}/sample.json", "w"), indent=1)
# The blind list: method and URL only, shuffled so stratum order does not leak.
blind = [{"n": n, "method": c.split(" ", 1)[0], "url": c.split(" ", 1)[1]}
         for n, c in enumerate(random.Random(SEED + 3).sample(cases, len(cases)), 1)]
json.dump(blind, open(f"{OUT}/blind-list.json", "w"), indent=1)
print({k: f"{len(strata[k])}/{len(pop[k])}" for k in SIZES}, "unique cases:", len(cases))

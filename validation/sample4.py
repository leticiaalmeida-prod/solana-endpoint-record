"""Round 4 samples (METHOD.md, "Round 4"): literal-agent levels only, catalog and waiting list.

Usage:
  python3 sample4.py catalog <snapshot commit> <out dir>      seed 20261014
  python3 sample4.py waitlist <queue.json> <out dir>          seed 20261015 (output names sellers; keep it private)
"""
import hashlib, json, random, subprocess, sys

SIZES = {"catalog": {"L0": 40, "L1": 40, "L2": 40, "L3": 50}, "waitlist": {"L0": 40, "L1": 40, "L2": 40, "L3": 50}}
SEEDS = {"catalog": 20261014, "waitlist": 20261015}

kind, src, out = sys.argv[1], sys.argv[2], sys.argv[3]
if kind == "catalog":
    rows = json.loads(subprocess.check_output(["git", "show", f"{src}:data/literal.json"]))["rows"]
    pop = {}
    for i, r in rows.items():
        pop.setdefault(r["strict"]["level"], []).append(i)
else:
    d = json.load(open(src))
    pop = {}
    for r in d["new"]:
        for e in r["endpoints"]:
            pop.setdefault(e["strict"]["level"], []).append(e["id"])
pop = {k: sorted(set(v)) for k, v in pop.items()}
rng = random.Random(SEEDS[kind])
strata = {k: (pop.get(k, []) if len(pop.get(k, [])) <= n else rng.sample(pop[k], n)) for k, n in SIZES[kind].items()}
cases = sorted({i for v in strata.values() for i in v})
doc = {"kind": kind, "source": src, "seed": SEEDS[kind], "population": {k: len(v) for k, v in pop.items()},
       "strata": strata, "cases": cases}
text = json.dumps(doc, indent=1, sort_keys=True)
open(f"{out}/sample-{kind}.json", "w").write(text)
print(kind, {k: f"{len(strata[k])}/{len(pop.get(k, []))}" for k in SIZES[kind]}, "cases:", len(cases),
      "sha256:", hashlib.sha256(text.encode()).hexdigest())

"""Re-check the validation sample with the checker itself, for the persistence rule (METHOD.md section 7).

Usage: python3 validation/repeat.py <sample dir> <vantage>   e.g. validation/2026-10-06 github-us
Appends one line per case to <sample dir>/repeats.jsonl. Stops doing anything after the window closes.
"""
import json, os, socket, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from checker_v01 import knock, verdict  # noqa: E402  (frozen v0.1: the instrument under test)

WINDOW_END = "2026-10-07T05:00:00Z"
d, vantage = sys.argv[1], sys.argv[2]
now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
if now > WINDOW_END:
    print("window closed"); sys.exit(0)
s = json.load(open(os.path.join(d, "sample.json")))
eps = {e["id"]: e for e in json.loads(subprocess.check_output(["git", "show", f"{s['snapshot']}:data/endpoints.json"]))["endpoints"]}
cases = [eps[c] for c in s["cases"]]
by_host = {}
for i, e in enumerate(cases):
    by_host.setdefault(e["url"].split("/")[2], []).append(i)
out = [None] * len(cases)

def run(idx):
    for n, i in enumerate(idx):
        if n: time.sleep(0.5)
        t = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        k = knock(cases[i]); v, notes = verdict(cases[i], k)
        out[i] = {"id": cases[i]["id"], "at": t, "vantage": vantage, "verdict": v, "notes": notes,
                  "status": k.get("status"), "ms": k.get("ms")}

with ThreadPoolExecutor(16) as ex:
    list(ex.map(run, by_host.values()))
with open(os.path.join(d, "repeats.jsonl"), "a") as f:
    for r in out: f.write(json.dumps(r) + "\n")
print(f"{vantage}: {len(out)} re-checks at {now}")

"""Re-judge the independent verifier's saved replies with the current checker (identical evidence, no timing noise).

Usage: python3 validation/offline.py <verifier work dir> <labels.json> <out.json>
"""
import ast, json, os, sys, collections
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "record"))
from knock import judge, solana_options, USDC, VERSION  # noqa: E402
from collect import PLACEHOLDER  # noqa: E402
from urllib.parse import urlparse

W, labels, out = sys.argv[1], json.load(open(sys.argv[2])), sys.argv[3]

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
    if v == "error": c.add("E")
    if v == "unclear" and any(n.startswith("HTTP 4") for n in j["notes"]): c.add("U")
    if v == "down": c.add("D")
    if v == "alive": c.add("ALIVE")
    return c

def truth(l):
    return {k for k, v in l["codes"].items() if v["value"] in (True, "true")}

rows, tally = [], collections.Counter()
for l in labels:
    n = str(l["n"]); raw = json.load(open(f"{W}/raw/{n}.json")); cat = json.load(open(f"{W}/catalog/{n}.json"))
    ep = {"method": l["method"], "url": l["url"], "sources": [], "price_usd": None, "catalog_options": None}
    for b in cat.get("bazaar") or []:
        ep["sources"].append("bazaar"); ep["catalog_options"] = solana_options(b["item"].get("accepts"))
    for p in cat.get("paysh") or cat.get("pay.sh") or []:
        ep["sources"].append("pay.sh")
        prices = [t.get("price_usd") or 0 for d in ((p.get("endpoint") or p).get("pricing") or {}).get("dimensions") or [] for t in d.get("tiers") or []]
        ep["price_usd"] = max(prices) if prices else None
    if PLACEHOLDER.search(urlparse(l["url"]).path):
        rows.append({"n": n, "id": f"{l['method']} {l['url']}", "result": "skipped (placeholder URL)", "indep": sorted(truth(l))}); tally["skipped"] += 1; continue
    st = raw.get("status")
    hdrs = raw.get("headers"); hdrs = ast.literal_eval(hdrs) if isinstance(hdrs, str) else (hdrs or [])
    body = raw.get("body") or ""
    f = {"status": None if st in (None, "", "None", "000", "timeout") or not str(st).isdigit() else int(st),
         "headers": hdrs, "body": body.encode(), "error": raw.get("curl_errormsg") or "timeout"}
    j = judge(ep, f); mine, theirs = claims(j), truth(l)
    ok = mine == theirs
    tally["agree" if ok else "disagree"] += 1
    rows.append({"n": n, "id": f"{l['method']} {l['url']}", "checker": sorted(mine), "indep": sorted(theirs),
                 "agree": ok, "notes": j["notes"], "verdict": j["verdict"]})
json.dump({"checker_version": VERSION, "tally": tally, "rows": rows}, open(out, "w"), indent=1)
print(f"checker v{VERSION} on identical evidence:", dict(tally))
for r in rows:
    if r.get("agree") is False: print(f"  #{r['n']} checker={r['checker']} indep={r['indep']} | {r['verdict']}: {'; '.join(r['notes'])[:120]} | {r['id'][:70]}")

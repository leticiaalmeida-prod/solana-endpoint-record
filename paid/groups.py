"""Accepted vs waiting on pay.sh: buy one working endpoint per provider and record what comes back (paid/METHOD.md 1b).

  python3 groups.py select                         free: pick one endpoint per provider, save the exact requests
  python3 groups.py run --group accepted --budget 1.00 --round 1
  python3 groups.py run --group waiting  --budget 2.50 --round 1

Pays USDC on Solana from the Solana wallet; PayBox signs, we send in the seller's x402 version (change P3).
Selections and results name unaccepted sellers, so they live outside the public repo.
"""
import argparse
import base64
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "record"))
sys.path.insert(0, HERE)
from bundles import send  # noqa: E402
from knock import USDC, fetch, payment_docs  # noqa: E402

OUT = os.path.expanduser("~/Gecko/product/2026-10-x402-agents-problem/measurement/paid")
QUEUE = os.path.expanduser("~/Gecko/product/2026-10-x402-agents-problem/measurement/queue-2026-10-06-r4/queue.json")
SNAPSHOT = "d96e085"
CREDENTIAL = "a90a60b8-432b-48ba-9697-231475818d0c"  # sol-default
SOLANA = {"solana", "solana:5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp"}
CAP = 0.10


def solana_option(req):
    f = fetch(req)
    docs = payment_docs(f.get("headers") or [], f.get("body") or b"")
    for d in docs:
        for a in d.get("accepts") or []:
            amt = str(a.get("amount") or a.get("maxAmountRequired") or "") if isinstance(a, dict) else ""
            if a.get("network") in SOLANA and a.get("asset") == USDC and amt.isdigit():
                return {"option": a, "price": int(amt) / 1e6, "version": d.get("x402Version"),
                        "resource": d.get("resource"), "status": f.get("status")}
    return {"option": None, "price": None, "status": f.get("status")}


def accepted_candidates():
    from literal import build
    show = lambda p: json.loads(subprocess.check_output(["git", "-C", os.path.join(HERE, ".."), "show", f"{SNAPSHOT}:{p}"]))
    eps = show("data/endpoints.json")["endpoints"]
    lit = show("data/literal.json")["rows"]
    by = {}
    for e in eps:  # listing order as collected
        if "pay.sh" in e["sources"] and lit.get(e["id"], {}).get("strict", {}).get("level") == "L3":
            req, _ = build(e)
            if not req:  # v0.5's change 23 can refuse a request v0.4 built; such an endpoint is not "working" now
                continue
            by.setdefault(e["seller"], []).append({"id": e["id"], "method": e["method"], "url": req["url"],
                                                   "body": req.get("body"), "headers": req.get("headers") or {}})
    return by


def waiting_candidates():
    from literal import build
    from waitlist import endpoints
    by = {}
    for r in json.load(open(QUEUE))["new"]:
        if r.get("trial_listing"):
            continue  # change 25
        l3 = {e["id"] for e in r["endpoints"] if e["strict"]["level"] == "L3"}
        if not l3:
            continue
        base, eps, _, _, _ = endpoints(r)
        for e in eps:
            ep = {"id": f"{e['method']} {base}/{e['path'].lstrip('/')}", "method": e["method"],
                  "url": f"{base}/{e['path'].lstrip('/')}", "input": e["input"]}
            if ep["id"] in l3:
                req, _ = build(ep)
                if req:
                    by.setdefault(r["pay_md"], []).append({"id": ep["id"], "method": ep["method"], "url": req["url"],
                                                           "body": req.get("body"), "headers": req.get("headers") or {},
                                                           "pr": r["pr"]})
    return by


def select():
    out = {}
    for group, fn in (("accepted", accepted_candidates), ("waiting", waiting_candidates)):
        chosen = {}
        for prov, cands in fn().items():
            for c in cands:  # first L3 endpoint whose price is at most the cap (METHOD.md 1b)
                ch = solana_option({"method": c["method"], "url": c["url"], "body": c["body"], "headers": c["headers"]})
                time.sleep(0.5)
                if ch["price"] is not None and ch["price"] <= CAP + 1e-9:
                    chosen[prov] = dict(c, price_at_select=ch["price"])
                    break
            print(f"  {group:8} {prov[:50]:50} {('$' + str(chosen[prov]['price_at_select'])) if prov in chosen else 'none under the cap'}")
        out[group] = chosen
    path = os.path.join(OUT, "groups-selection.json")
    json.dump({"selected_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "snapshot": SNAPSHOT, **out},
              open(path, "w"), indent=1)
    for g in ("accepted", "waiting"):
        print(f"{g}: {len(out[g])} providers, about ${sum(c['price_at_select'] for c in out[g].values()):.2f} per round")
    print("saved", path)


def buy(c, ch):
    tmp = os.path.join(OUT, ".accepts-sol.json")
    json.dump([ch["option"]], open(tmp, "w"))
    p = subprocess.run(["npx", "-y", "@paybox-sh/sdk", "--json", "pay-x402", "--credential", CREDENTIAL, "--url",
                        c["url"], "--accepts", "@" + tmp], capture_output=True, text=True, timeout=180)
    out = {"paybox_exit": p.returncode, "paybox_stderr": p.stderr[-2000:]}
    try:
        val = json.loads(p.stdout)["response"]["output"]["value"]
        signed = json.loads(base64.b64decode(val["x_payment"] + "=="))
    except Exception:
        out["paybox_stdout"] = p.stdout[-4000:]
        out["verdict_hint"] = "PayBox did not sign"
        return out
    out["paybox_payload_version"] = signed.get("x402Version")
    if ch.get("version") == 2:
        env = {"x402Version": 2, "resource": ch.get("resource"), "accepted": ch["option"], "payload": signed["payload"]}
        out["sent_as"] = "v2 envelope, PAYMENT-SIGNATURE"
        hv, hn = base64.b64encode(json.dumps(env).encode()).decode(), "PAYMENT-SIGNATURE"
    else:
        out["sent_as"] = "as signed, X-PAYMENT"
        hv, hn = val["x_payment"], "X-PAYMENT"
    out["reply"] = send(c["method"], c["url"], c["body"], hn, hv)
    return out


def run(group, budget, rnd, limit, offset=0):
    sel = json.load(open(os.path.join(OUT, "groups-selection.json")))[group]
    spent = 0.0
    path = os.path.join(OUT, f"groups-{group}-round{rnd}-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}.jsonl")
    with open(path, "w") as f:
        for n, (prov, c) in enumerate(list(sel.items())[offset:]):
            if limit and n >= limit:
                break
            ch = solana_option({"method": c["method"], "url": c["url"], "body": c["body"], "headers": c["headers"]})
            rec = {"group": group, "round": rnd, "provider": prov, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                   **{k: c[k] for k in ("id", "method", "url", "body")}, "price": ch["price"], "knock_status": ch["status"]}
            if ch["price"] is None:
                rec["skipped"] = f"no Solana USDC price now (status {ch['status']})"
            elif ch["price"] > CAP + 1e-9:
                rec["skipped"] = f"price {ch['price']} over the cap"
            elif spent + ch["price"] > budget + 1e-9:
                rec["skipped"] = "would pass the approved budget"
            else:
                rec["bought"] = buy(c, ch)
                spent += ch["price"]
            f.write(json.dumps(rec) + "\n")
            f.flush()
            st = rec.get("skipped") or f"paid, seller answered {(rec['bought'].get('reply') or {}).get('status')}"
            print(f"  {group} {prov[:44]:44} ${ch['price'] if ch['price'] is not None else '-':<7} {st}")
            time.sleep(0.5)
    print(f"\nspent about ${spent:.3f}; saved {path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["select", "run"])
    ap.add_argument("--group", choices=["accepted", "waiting"])
    ap.add_argument("--budget", type=float, default=0.0)
    ap.add_argument("--round", type=int, default=1)
    ap.add_argument("--limit", type=int, default=0, help="stop after N providers (pilot)")
    ap.add_argument("--offset", type=int, default=0, help="skip the first N providers (already bought this round)")
    a = ap.parse_args()
    if a.mode == "select":
        select()
    else:
        if not a.group or a.budget <= 0:
            sys.exit("A paid run needs --group and --budget.")
        run(a.group, a.budget, a.round, a.limit, a.offset)

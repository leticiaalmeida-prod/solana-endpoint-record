"""Knock on each endpoint without paying and record what it says.

A knock is the request an agent sends before paying: no payment header, so a working x402 endpoint
answers 402 with its price and payment address. Nothing is ever paid here.

Usage: python3 knock.py hourly|daily
"""
import base64
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
UA = "solana-endpoint-record/0.1 (+https://github.com/leticiaalmeida-prod/solana-endpoint-record)"
STANDARD_NETWORKS = {"solana", "solana:5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp"}
TEST_NETWORKS = {"solana-devnet", "solana:EtWTRABZaYq6iMfeYKouRu166VU2xqa1"}
SAFE_METHODS = {"GET", "POST"}  # never DELETE, PATCH or PUT
TIMEOUT = 10
WORKERS = 24  # sites in parallel; one request at a time per site
PAUSE = 0.5  # seconds between requests to the same site
KEEP = {"hourly": 168, "daily": 30}  # a week of hourly checks, a month of daily ones


def knock(ep):
    data = b"{}" if ep["method"] == "POST" else None
    headers = {"User-Agent": UA, "Accept": "application/json"}
    if data:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(ep["url"], data=data, method=ep["method"], headers=headers)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            status, hdrs, body = r.status, dict(r.headers), r.read(65536)
    except urllib.error.HTTPError as e:
        status, hdrs, body = e.code, dict(e.headers), e.read(65536)
    except Exception as e:
        return {"status": None, "ms": int((time.time() - t0) * 1000), "error": type(e).__name__}
    return {"status": status, "ms": int((time.time() - t0) * 1000), **read_requirements(hdrs, body)}


def read_requirements(hdrs, body):
    """Find the Solana payment option in a 402 reply (v2 header or v1 body)."""
    docs = []
    for k, v in hdrs.items():
        if k.lower() in ("payment-required", "x-payment-required"):
            try:
                docs.append(json.loads(base64.b64decode(v + "==")))
            except Exception:
                pass
    try:
        docs.append(json.loads(body))
    except Exception:
        pass
    mainnet, test = [], []
    for d in docs:
        if not isinstance(d, dict):
            continue
        for a in d.get("accepts") or []:
            net = str(a.get("network", ""))
            if not net.lower().startswith("solana"):
                continue
            amt = a.get("amount") or a.get("maxAmountRequired")
            opt = {"pay_to": a.get("payTo"), "network": net,
                   "price_usd": int(amt) / 1e6 if amt and str(amt).isdigit() else None}
            (test if net in TEST_NETWORKS else mainnet).append(opt)
        if mainnet or test:
            break
    if mainnet:
        prices = sorted({o["price_usd"] for o in mainnet if o["price_usd"] is not None})
        return {**mainnet[0], "price_usd": prices[0] if prices else None, "prices_usd": prices}
    if test:
        return {**test[0], "test_only": True}
    return {}


def verdict(ep, k):
    """One word for the page, plus the reasons behind it."""
    s = k.get("status")
    notes = []
    if s is None:
        return "down", [k.get("error", "no answer")]
    if s == 402 and k.get("test_only"):
        return "warning", ["only accepts test-network money; real buyers cannot pay it"]
    if s == 402 and k.get("pay_to"):
        if k.get("network") not in STANDARD_NETWORKS:
            notes.append(f"network name '{k.get('network')}' is not standard; some wallets cannot pay it")
        if ep.get("pay_to") and k["pay_to"] != ep["pay_to"]:
            notes.append("payment address differs from the catalog")
        listed, asked = ep.get("price_usd"), k.get("prices_usd") or []
        if listed and asked and not any(abs(a - listed) < 1e-9 for a in asked):
            notes.append(f"asks {asked[0]} but the catalog says {listed}")
        return ("alive" if not notes else "warning"), notes
    if s == 402:
        return "warning", ["asks for payment but offers no Solana option"]
    if 200 <= s < 300:
        return "warning", ["answered without asking for payment"]
    if ep["method"] == "POST" and s in (400, 422):
        return "unclear", [f"HTTP {s}: refused our empty test request before asking for payment"]
    if s == 429:
        return "unclear", ["HTTP 429: asked us to slow down"]
    return "error", [f"HTTP {s}"]


def main(tier):
    eps = json.load(open(os.path.join(DATA, "endpoints.json")))["endpoints"]
    todo = [e for e in eps if e["tier"] == tier and e["method"] in SAFE_METHODS
            and not e["free"] and not e["needs_params"]]
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    print(f"{tier}: knocking {len(todo)} endpoints")
    by_host = {}
    for i, e in enumerate(todo):
        by_host.setdefault(e["url"].split("/")[2], []).append(i)
    results = [None] * len(todo)

    def run_host(idx):
        for n, i in enumerate(idx):
            if n:
                time.sleep(PAUSE)
            results[i] = knock(todo[i])

    with ThreadPoolExecutor(WORKERS) as ex:
        list(ex.map(run_host, by_host.values()))

    latest_path = os.path.join(DATA, "latest.json")
    hist_path = os.path.join(DATA, f"history-{tier}.json")
    latest = json.load(open(latest_path)) if os.path.exists(latest_path) else {"checks": {}}
    hist = json.load(open(hist_path)) if os.path.exists(hist_path) else {}

    counts = {}
    for ep, k in zip(todo, results):
        v, notes = verdict(ep, k)
        counts[v] = counts.get(v, 0) + 1
        hid = hashlib.sha1(ep["id"].encode()).hexdigest()[:12]
        latest["checks"][ep["id"]] = {"at": now, "verdict": v, "notes": notes, "hid": hid, **k}
        h = hist.setdefault(hid, [])
        h.append([now, v[0], k.get("status"), k.get("ms")])
        del h[:-KEEP[tier]]

    latest["updated_at"] = now
    json.dump(latest, open(latest_path, "w"), indent=0)
    json.dump(hist, open(hist_path, "w"), separators=(",", ":"))
    print(f"{tier}: {counts}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "hourly")

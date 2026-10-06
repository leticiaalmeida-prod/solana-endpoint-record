"""Collect every paid Solana endpoint from public catalogs into data/endpoints.json.

Sources: Coinbase Bazaar discovery API, pay.sh catalog. Read-only, nothing is paid.
Standard library only, so it runs anywhere Python 3.9+ runs.
"""
import json
import os
import sys
import time
import urllib.request
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
UA = "solana-endpoint-record/0.1 (+https://github.com/leticiaalmeida-prod/solana-endpoint-record)"

BAZAAR = "https://api.cdp.coinbase.com/platform/v2/x402/discovery/resources"
PAYSH = "https://pay.sh/api"

# x402 v1 used "solana"; v2 uses CAIP-2 with the first 32 characters of the mainnet genesis hash.
STANDARD_NETWORKS = {"solana", "solana:5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp"}
USDC_DECIMALS = 6

# An endpoint is checked hourly if people actually pay it; the rest once a day.
HOURLY_MIN_PAYERS = 10


def get_json(url, timeout=30, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except Exception as e:
            if i == tries - 1:
                print(f"  failed {url}: {e}", file=sys.stderr)
                return None
            time.sleep(2 * (i + 1))


def is_solana(network):
    return str(network or "").lower().startswith("solana")


def bazaar():
    out, offset = [], 0
    while True:
        page = get_json(f"{BAZAAR}?limit=1000&offset={offset}")
        items = (page or {}).get("items") or []
        if not items:
            break
        for it in items:
            sol = [a for a in it.get("accepts") or [] if is_solana(a.get("network"))]
            if not sol:
                continue
            a = sol[0]
            amount = a.get("amount") or a.get("maxAmountRequired")
            info = ((it.get("extensions") or {}).get("bazaar") or {}).get("info") or {}
            method = ((info.get("input") or {}).get("method") or "GET").upper()
            q = it.get("quality") or {}
            out.append({
                "url": it["resource"],
                "method": method,
                "source": "bazaar",
                "seller": it.get("serviceName") or urlparse(it["resource"]).netloc,
                "price_usd": int(amount) / 10 ** USDC_DECIMALS if amount and str(amount).isdigit() else None,
                "pay_to": a.get("payTo"),
                "network": a.get("network"),
                "payers_30d": q.get("l30DaysUniquePayers"),
                "calls_30d": q.get("l30DaysTotalCalls"),
            })
        offset += len(items)
        print(f"  bazaar: {offset} read, {len(out)} on Solana")
    return out


def paysh():
    cat = get_json(f"{PAYSH}/catalog") or {}
    out = []
    for p in cat.get("providers") or []:
        d = get_json(f"{PAYSH}/providers/{p['fqn']}")
        if not d:
            continue
        base = (d.get("service_url") or "").rstrip("/")
        for e in d.get("endpoints") or []:
            prices = [t.get("price_usd") or 0
                      for dim in (e.get("pricing") or {}).get("dimensions") or []
                      for t in dim.get("tiers") or []]
            out.append({
                "url": f"{base}/{e.get('path', '').lstrip('/')}",
                "method": (e.get("method") or "GET").upper(),
                "source": "pay.sh",
                "seller": d.get("title") or p["fqn"],
                "price_usd": max(prices) if prices else None,
                "pay_to": None,  # pay.sh does not publish it; the knock reads it
                "network": "solana",
                "payers_30d": None,
                "calls_30d": None,
            })
    print(f"  pay.sh: {len(out)} endpoints")
    return out


def merge(rows):
    by = {}
    for r in rows:
        key = f"{r['method']} {r['url']}"
        if key in by:
            prev = by[key]
            prev["sources"] = sorted(set(prev["sources"]) | {r["source"]})
            for k, v in r.items():
                if prev.get(k) is None and v is not None:
                    prev[k] = v
        else:
            r = dict(r, id=key, sources=[r.pop("source")])
            by[key] = r
    for r in by.values():
        r["network_standard"] = r["network"] in STANDARD_NETWORKS
        r["needs_params"] = "{" in r["url"]
        r["free"] = r["price_usd"] == 0
        r["tier"] = "hourly" if ((r.get("payers_30d") or 0) >= HOURLY_MIN_PAYERS or "pay.sh" in r["sources"]) else "daily"
    return sorted(by.values(), key=lambda r: (r["tier"] != "hourly", -(r.get("payers_30d") or 0), r["id"]))


def main():
    os.makedirs(DATA, exist_ok=True)
    rows = merge(bazaar() + paysh())
    doc = {"collected_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "count": len(rows), "endpoints": rows}
    with open(os.path.join(DATA, "endpoints.json"), "w") as f:
        json.dump(doc, f, indent=0)
    hourly = sum(r["tier"] == "hourly" for r in rows)
    print(f"endpoints: {len(rows)} ({hourly} hourly)")


if __name__ == "__main__":
    main()

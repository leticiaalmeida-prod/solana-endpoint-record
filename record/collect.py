"""Collect every paid Solana endpoint from public catalogs into data/endpoints.json.

Sources: Coinbase Bazaar discovery API, pay.sh catalog. Read-only, nothing is paid.
Standard library only, so it runs anywhere Python 3.9+ runs.
"""
import json
import os
import sys
import time
import re
import urllib.request
from urllib.parse import urlparse

from knock import USDC, solana_options

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
UA = "solana-endpoint-record/0.1 (+https://github.com/leticiaalmeida-prod/solana-endpoint-record)"

BAZAAR = "https://api.cdp.coinbase.com/platform/v2/x402/discovery/resources"
PAYSH = "https://pay.sh/api"

# x402 v1 used "solana"; v2 uses CAIP-2 with the first 32 characters of the mainnet genesis hash.
STANDARD_NETWORKS = {"solana", "solana:5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp"}
# A path segment like ":address", "{id}" or "<mint>" is a template, not a real endpoint.
PLACEHOLDER = re.compile(r"/:[A-Za-z_]|\{[^}]*\}|<[^>]*>")

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


def bazaar():
    out, offset = [], 0
    while True:
        page = get_json(f"{BAZAAR}?limit=1000&offset={offset}")
        items = (page or {}).get("items") or []
        if not items:
            break
        for it in items:
            opts = solana_options(it.get("accepts"))
            if not opts:
                continue
            main = [o for o in opts if o["kind"] == "mainnet" and o["asset"] == USDC]
            prices = [o["price_usd"] for o in main if o["price_usd"] is not None]
            info = ((it.get("extensions") or {}).get("bazaar") or {}).get("info") or {}
            method = ((info.get("input") or {}).get("method") or "GET").upper()
            q = it.get("quality") or {}
            out.append({
                "url": it["resource"],
                "method": method,
                "source": "bazaar",
                "seller": it.get("serviceName") or urlparse(it["resource"]).netloc,
                "price_usd": min(prices) if prices else None,
                "pay_to": main[0]["pay_to"] if main else None,
                "network": (main or opts)[0]["network"],
                "catalog_options": opts,
                "input": {k: v for k, v in (info.get("input") or {}).items()
                          if k in ("pathParams", "queryParams", "body", "bodyType", "headers") and v is not None},
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
        doc = d.get("openapi_doc") if isinstance(d.get("openapi_doc"), dict) else {}
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
                "catalog_options": None,
                "input": openapi_input(doc, e.get("path", ""), e.get("method") or "GET"),
                "payers_30d": None,
                "calls_30d": None,
            })
    print(f"  pay.sh: {len(out)} endpoints")
    return out


def openapi_value(p):
    """A parameter's value as the OpenAPI document gives it, or None (validation/METHOD.md section 9)."""
    for src in (p, p.get("schema") or {}):
        if "example" in src:
            return src["example"]
        ex = src.get("examples")
        if isinstance(ex, dict) and ex:
            first = next(iter(ex.values()))
            return first.get("value") if isinstance(first, dict) else first
        if isinstance(ex, list) and ex:
            return ex[0]
        if "default" in src:
            return src["default"]
        if isinstance(src.get("enum"), list) and len(src["enum"]) == 1:
            return src["enum"][0]
    return None


def openapi_input(doc, path, method):
    """pay.sh: the listing's inputs for one endpoint, in the same shape as Bazaar's `input`."""
    paths = doc.get("paths") or {}
    item = next((v for k, v in paths.items() if k.strip("/") == path.strip("/")), {}) or {}
    op = item.get(method.lower()) or {}
    out = {"pathParams": {}, "queryParams": {}, "headers": {}, "described": []}
    # Parameters may sit on the path item and on the operation; the operation's win (OpenAPI 3).
    params = {(p.get("in"), p.get("name")): p for p in (item.get("parameters") or []) + (op.get("parameters") or [])
              if isinstance(p, dict) and "$ref" not in p}
    for prm in params.values():
        val = openapi_value(prm)
        if prm.get("in") == "path":
            out["described"].append(prm.get("name"))
            if val is not None:
                out["pathParams"][prm["name"]] = val
        elif prm.get("in") == "query" and val is not None:
            out["queryParams"][prm["name"]] = val
        elif prm.get("in") == "header" and val is not None:
            out["headers"][prm["name"]] = val
    body = ((op.get("requestBody") or {}).get("content") or {}).get("application/json") or {}
    if "example" in body:
        out["body"], out["bodyType"] = body["example"], "json"
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
        r["needs_params"] = bool(PLACEHOLDER.search(urlparse(r["url"]).path))
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

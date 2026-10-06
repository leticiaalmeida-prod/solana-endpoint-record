"""Knock on each endpoint without paying and record what it says.

A knock is the request an agent sends before paying: no payment header, so a working x402 endpoint
answers 402 with its price and payment address. Nothing is ever paid here.

Fetching and judging are separate so the same judging code can be re-run on saved replies
(validation/offline.py does that).

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

VERSION = "0.3"
HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
UA = "solana-endpoint-record/0.3 (+https://github.com/leticiaalmeida-prod/solana-endpoint-record)"
USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
STANDARD_NETWORKS = {"solana", "solana:5eykt4UsFv8P8NJdTREpY1vzqKqZKvdp"}
TEST_NETWORKS = {"solana-devnet", "solana:EtWTRABZaYq6iMfeYKouRu166VU2xqa1"}
LOOSE_MAINNET = {"solana:mainnet", "solana-mainnet", "solana:mainnet-beta"}  # meant as mainnet, not standard
SAFE_METHODS = {"GET", "POST"}  # never DELETE, PATCH or PUT
TIMEOUT = 10
MAX_BODY = 65536
WORKERS = 24  # sites in parallel; one request at a time per site
PAUSE = 0.5  # seconds between requests to the same site
KEEP = {"hourly": 168, "daily": 30}  # a week of hourly checks, a month of daily ones


def fetch(ep):
    if ep.get("body") is not None:
        data = json.dumps(ep["body"]).encode()
    else:
        data = b"{}" if ep["method"] == "POST" else None
    headers = {"User-Agent": UA, "Accept": "application/json", **(ep.get("headers") or {})}
    if data:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(ep["url"], data=data, method=ep["method"], headers=headers)
    at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            status, hdrs, body = r.status, list(r.headers.items()), r.read(MAX_BODY)
    except urllib.error.HTTPError as e:
        status, hdrs, body = e.code, list(e.headers.items()), e.read(MAX_BODY)
    except Exception as e:
        return {"at": at, "status": None, "ms": int((time.time() - t0) * 1000), "error": type(e).__name__}
    return {"at": at, "status": status, "ms": int((time.time() - t0) * 1000), "headers": hdrs, "body": body}


def network_kind(net):
    if net in STANDARD_NETWORKS:
        return "mainnet"
    if net in TEST_NETWORKS:
        return "test"
    if net in LOOSE_MAINNET:
        return "loose-mainnet"
    return "unknown"


def solana_options(accepts):
    """Solana options: network, kind, asset, price in USD (USDC only), payment address."""
    out = []
    for a in accepts if isinstance(accepts, list) else []:
        if not isinstance(a, dict):  # some servers send plain strings here; they offer nothing payable
            continue
        net = str(a.get("network", ""))
        if not net.lower().startswith("solana"):
            continue
        amt = a.get("amount") or a.get("maxAmountRequired")
        usdc = a.get("asset") == USDC
        out.append({"network": net, "kind": network_kind(net), "asset": a.get("asset"),
                    "price_usd": int(amt) / 1e6 if usdc and amt and str(amt).isdigit() else None,
                    "pay_to": a.get("payTo")})
    return out


def payment_docs(headers, body):
    docs = []
    for k, v in headers:
        if k.lower() in ("payment-required", "x-payment-required"):
            try:
                docs.append(json.loads(base64.b64decode(v + "==")))
            except Exception:
                pass
    try:
        docs.append(json.loads(body))
    except Exception:
        pass
    return [d for d in docs if isinstance(d, dict)]


def body_kind(body):
    """For a 2xx reply: 'answer', 'error' or 'empty'. Fixed rules, no model."""
    text = body.decode("utf-8", "replace").strip() if isinstance(body, bytes) else str(body or "").strip()
    if not text or text in ("{}", "[]", "null"):
        return "empty"
    try:
        d = json.loads(text)
    except Exception:
        return "answer"
    layers = [d] + ([v for v in d.values() if isinstance(v, dict)] if isinstance(d, dict) else [])
    for x in layers:
        if not isinstance(x, dict):
            continue
        if x.get("error") or x.get("errors") or x.get("ok") is False or x.get("success") is False:
            return "error"
        if str(x.get("status", "")).lower() in ("error", "failed", "placeholder"):
            return "error"
    return "answer"


def catalog_mainnet(ep):
    """The catalog's standard-mainnet USDC options. pay.sh gives a price but no network or address."""
    opts = [o for o in ep.get("catalog_options") or [] if o["kind"] == "mainnet" and o["asset"] == USDC]
    if not opts and "pay.sh" in (ep.get("sources") or []) and ep.get("price_usd") is not None:
        opts = [{"price_usd": ep["price_usd"], "pay_to": None}]
    return opts


def compare_with_catalog(ep, main):
    """N1 and N2 of validation/METHOD.md: compare sets, standard-mainnet USDC on both sides only."""
    notes = []
    # Addresses are compared whatever the asset: a wrong token in the catalog does not hide a wrong address.
    cat_to = {o["pay_to"] for o in ep.get("catalog_options") or [] if o["kind"] == "mainnet" and o.get("pay_to")}
    got_to = {o["pay_to"] for o in main if o["kind"] == "mainnet"}
    if cat_to and got_to and not cat_to & got_to:
        notes.append("payment address differs from the catalog")
    cat_main = [o for o in ep.get("catalog_options") or [] if o["kind"] == "mainnet"]
    if cat_main and not any(o["asset"] == USDC for o in cat_main):
        notes.append("catalog's Solana option names a token that is not USDC")
    cat = catalog_mainnet(ep)
    if "pay.sh-queue" in (ep.get("sources") or []):
        return notes  # METHOD.md section 10: a waiting listing is compared only on a price it states
    if not any(o.get("price_usd") is not None for o in cat):
        notes.append("the listing states no Solana USDC price to compare with")
        return notes
    asked = {round(o["price_usd"], 9) for o in main if o["kind"] == "mainnet" and o["price_usd"] is not None}
    listed = {round(o["price_usd"], 9) for o in cat if o["price_usd"] is not None}
    if asked and listed and not asked & listed:
        notes.append(f"asks {min(asked)} but the catalog says {min(listed)}")
    return notes


def judge(ep, f):
    """Turn one fetch into a verdict and notes. Verdicts: alive, warning, unclear, free, error, down."""
    s = f.get("status")
    if s is None:
        return {"verdict": "down", "notes": [f"no answer within {TIMEOUT} s ({f.get('error', 'error')})"]}
    s = int(s)
    docs = payment_docs(f.get("headers") or [], f.get("body") or b"")
    opts = [o for d in docs for o in solana_options(d.get("accepts"))]

    if s == 402:
        if not any(isinstance(d.get("accepts"), list) and any(isinstance(x, dict) for x in d["accepts"]) for d in docs):
            return {"verdict": "warning", "notes": ["asks for payment but gives no payment details"]}
        if not opts:
            return {"verdict": "warning", "notes": ["asks for payment but offers no Solana option"]}
        main = [o for o in opts if o["kind"] in ("mainnet", "loose-mainnet")]
        if not main:
            if all(o["kind"] == "test" for o in opts):
                return {"verdict": "warning", "notes": ["only accepts test-network money"]}
            names = ", ".join(sorted({o["network"] for o in opts if o["kind"] == "unknown"}))
            return {"verdict": "warning", "notes": [f"network name '{names}' is not recognised; offers no Solana mainnet option"]}
        notes = [f"network name '{n}' is not one of the two standard names"
                 for n in sorted({o["network"] for o in opts if o["kind"] in ("loose-mainnet", "unknown")})]
        if not any(o["asset"] == USDC for o in main):
            notes.append("Solana option is not priced in USDC")
        cat_notes = compare_with_catalog(ep, main)
        notes += cat_notes
        prices = [o["price_usd"] for o in main if o["price_usd"] is not None]
        # An agent can pay correctly if a standard mainnet USDC option exists and nothing but naming is off.
        standard_ok = any(o["kind"] == "mainnet" and o["asset"] == USDC for o in main) and not cat_notes
        return {"verdict": "warning" if notes else "alive", "notes": notes, "standard_ok": standard_ok,
                "pay_to": main[0]["pay_to"], "price_usd": min(prices) if prices else None}

    if 200 <= s < 300:
        kind = body_kind(f.get("body") or b"")
        if kind != "answer":
            what = "an error" if kind == "error" else "nothing"
            return {"verdict": "unclear", "notes": [f"HTTP {s} with {what} in the body, without asking for payment"]}
        if any(o["price_usd"] for o in catalog_mainnet(ep)):
            return {"verdict": "warning", "notes": ["gave a real answer without asking for payment, though the catalog lists a price"]}
        return {"verdict": "free", "notes": ["gave an answer without asking for payment; the listing states no price"]}

    if ep["method"] == "POST" and s in (400, 422):
        return {"verdict": "unclear", "notes": [f"HTTP {s}: refused our empty test request before asking for payment"]}
    if s == 429:
        return {"verdict": "unclear", "notes": ["HTTP 429: asked us to slow down"]}
    return {"verdict": "error", "notes": [f"HTTP {s}"]}


def checkable(e):
    return e["method"] in SAFE_METHODS and not e["free"] and not e["needs_params"]


def main(tier):
    eps = json.load(open(os.path.join(DATA, "endpoints.json")))["endpoints"]
    todo = [e for e in eps if e["tier"] == tier and checkable(e)]
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
            f = fetch(todo[i])
            results[i] = (f, judge(todo[i], f))

    with ThreadPoolExecutor(WORKERS) as ex:
        list(ex.map(run_host, by_host.values()))

    latest_path = os.path.join(DATA, "latest.json")
    hist_path = os.path.join(DATA, f"history-{tier}.json")
    latest = json.load(open(latest_path)) if os.path.exists(latest_path) else {"checks": {}}
    hist = json.load(open(hist_path)) if os.path.exists(hist_path) else {}

    counts = {}
    for ep, (f, j) in zip(todo, results):
        v = j["verdict"]
        counts[v] = counts.get(v, 0) + 1
        hid = hashlib.sha1(ep["id"].encode()).hexdigest()[:12]
        latest["checks"][ep["id"]] = {"at": f["at"], "v": VERSION, "verdict": v, "notes": j["notes"], "hid": hid,
                                      "status": f.get("status"), "ms": f.get("ms"),
                                      "pay_to": j.get("pay_to"), "price_usd": j.get("price_usd")}
        h = hist.setdefault(hid, [])
        h.append([f["at"], v[0], f.get("status"), f.get("ms")])
        del h[:-KEEP[tier]]

    # Endpoints no longer checkable (placeholders now skipped, or delisted) leave the page.
    keep = {e["id"] for e in eps if checkable(e)}
    latest["checks"] = {k: c for k, c in latest["checks"].items() if k in keep}
    latest["updated_at"] = now
    json.dump(latest, open(latest_path, "w"), indent=0)
    json.dump(hist, open(hist_path, "w"), separators=(",", ":"))
    print(f"{tier}: {counts}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "hourly")

"""Run agentic.market's bundles as published, paying each step through the PayBox CLI (paid/METHOD.md).

The recipes are followed step by step with fixed inputs, so no model chooses anything. Before every purchase the
step is knocked without paying to read its price; the purchase is refused if the price is over the cap, if the seller
is not on the approved list, or if the batch total would pass what Leticia approved.

Usage:
  python3 bundles.py practice                       knock every step of one run of each bundle, buy nothing
  python3 bundles.py run --runs 1 --budget 0.50     pay: N runs of each bundle, never more than BUDGET dollars
  python3 bundles.py run --bundle talent --runs 5 --budget 1.00

Results (they name sellers) go to OUT, outside the public repo.
"""
import argparse
import json
import os
import subprocess
import sys
import time
from urllib.parse import urlencode

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "record"))
from knock import fetch, payment_docs  # noqa: E402

OUT = os.path.expanduser("~/Gecko/product/2026-10-x402-agents-problem/measurement/paid")
CREDENTIAL = "e2632255-427b-4383-887f-27d80d5c7bd0"  # evm-default (Base), granted to this Mac's PayBox CLI
NETWORK = "eip155:8453"
USDC_BASE = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
CAP = 0.10  # dollars per purchase
APPROVED = {"blockrun.ai", "parallelmpp.dev", "finance.toon.haus", "api.seerium.xyz", "stablejobs.dev"}

EXA = "https://blockrun.ai/api/v1/exa"
PARALLEL = "https://parallelmpp.dev/api/search"
TOON = "https://finance.toon.haus/api"

# Fixed inputs, chosen before any purchase. Market Research: (question, ticker or None).
MARKET = [
    ("Coinbase stablecoin revenue strategy 2026", "COIN"), ("Nvidia data center demand outlook", "NVDA"),
    ("Shopify agentic commerce plans", "SHOP"), ("Robinhood crypto trading growth", "HOOD"),
    ("Circle USDC market share", "CRCL"), ("Microsoft AI capex 2026", "MSFT"), ("Tesla robotaxi launch status", "TSLA"),
    ("Visa agent payments program", "V"), ("Mastercard agentic tokens", "MA"), ("PayPal stablecoin PYUSD adoption", "PYPL"),
    ("Block bitcoin mining chips", "XYZ"), ("Strategy bitcoin treasury holdings", "MSTR"), ("Amazon Bedrock agents", "AMZN"),
    ("Alphabet Gemini enterprise adoption", "GOOGL"), ("Stripe stablecoin payments", None),
    ("Solana Foundation developer ecosystem 2026", None), ("x402 protocol adoption by APIs", None),
    ("MoonPay PayBox agent wallet", None), ("Anthropic enterprise market share", None),
    ("Brazil Pix international expansion", None), ("Tether USDT reserves attestation", None),
    ("Jupiter exchange Solana volume", None), ("agent-to-agent payments startups", None),
    ("stablecoin regulation United States 2026", None), ("Phantom wallet user growth", None),
]
TALENT = [  # (role, location, country)
    ("Data Engineer", "Austin, TX", "United States"), ("Product Designer", "London", "United Kingdom"),
    ("Machine Learning Engineer", "San Francisco, CA", "United States"), ("Backend Engineer", "Berlin", "Germany"),
    ("Solidity Developer", "New York, NY", "United States"), ("Rust Engineer", "Toronto, Ontario", "Canada"),
    ("Product Manager", "Seattle, WA", "United States"), ("DevOps Engineer", "Amsterdam", "Netherlands"),
    ("Data Scientist", "Boston, MA", "United States"), ("UX Researcher", "Chicago, IL", "United States"),
    ("Security Engineer", "Washington, DC", "United States"), ("Frontend Engineer", "Bengaluru, Karnataka", "India"),
    ("Site Reliability Engineer", "Dublin", "Ireland"), ("iOS Developer", "Los Angeles, CA", "United States"),
    ("Android Developer", "Singapore", "Singapore"), ("Technical Writer", "Denver, CO", "United States"),
    ("Developer Relations", "Paris", "France"), ("Growth Marketer", "Miami, FL", "United States"),
    ("Financial Analyst", "Charlotte, NC", "United States"), ("Compliance Officer", "Zurich", "Switzerland"),
    ("Solutions Architect", "Atlanta, GA", "United States"), ("Blockchain Engineer", "Lisbon", "Portugal"),
    ("AI Researcher", "Montreal, Quebec", "Canada"), ("Customer Success Manager", "Dallas, TX", "United States"),
    ("Engineering Manager", "Stockholm", "Sweden"),
]
RUNS_MORNING = 25  # Morning Briefing takes no input; each run is a separate briefing


def market_research(i):
    q, t = MARKET[i % len(MARKET)]
    steps = [
        ("exa_search", "POST", f"{EXA}/search", {"query": q, "type": "neural", "numResults": 5}, True),
        ("parallel_search", "POST", PARALLEL, {"query": q}, True),
        ("exa_answer", "POST", f"{EXA}/answer", {"query": q}, False),
    ]
    if t:  # recipe step 3: only for a public company
        steps += [(n, "GET", f"{TOON}/stock/{p}?" + urlencode({"ticker": t}), None, False)
                  for n, p in (("stock_quote", "quote"), ("stock_peers", "peers"), ("analyst_recs", "recommendations"))]
    return {"input": {"question": q, "ticker": t}, "steps": steps}


def morning_briefing(i, top_story=None):
    feeds = [
        ("seerium_pulse", "GET", "https://api.seerium.xyz/v1/pulse/latest", None, False),
        ("market_news", "GET", f"{TOON}/market/news?" + urlencode({"limit": 20}), None, True),
        # "Orbis Crypto Sentiment" (required in the recipe) is not listed by the marketplace; recorded as missing.
    ]
    deep = []
    if top_story:  # rule fixed in METHOD.md: the first headline of toon.haus market news is the top story
        deep = [
            ("exa_search_news", "POST", f"{EXA}/search", {"query": top_story, "type": "neural", "category": "news",
                                                          "numResults": 5}, True),
            ("parallel_search", "POST", PARALLEL, {"query": top_story}, True),
            ("exa_answer", "POST", f"{EXA}/answer", {"query": top_story}, False),
        ]
    return {"input": {"run": i, "top_story": top_story}, "steps": feeds + deep, "missing_required": ["orbis_sentiment"]}


def talent_scanner(i):
    role, loc, country = TALENT[i % len(TALENT)]
    return {"input": {"role": role, "location": loc}, "steps": [
        ("job_search", "POST", "https://stablejobs.dev/api/coresignal/job-search",
         {"title": role, "location": loc, "country": country, "page": 1}, True),
        ("exa_search", "POST", f"{EXA}/search", {"query": f"{role} hiring trends 2026", "type": "neural",
                                                 "numResults": 5}, True),
        ("parallel_search", "POST", PARALLEL, {"query": f"{role} salary {loc} 2026"}, True),
        # Stock quotes for "the top public companies" need a company-to-ticker choice; skipped (optional in recipe).
    ]}


BUNDLES = {"market": market_research, "talent": talent_scanner, "morning": morning_briefing}


def price_of(method, url, body):
    """Knock without paying; return (price in dollars on Base USDC or None, status)."""
    f = fetch({"method": method, "url": url, "body": body})
    docs = payment_docs(f.get("headers") or [], f.get("body") or b"")
    amts = [int(a.get("amount") or a.get("maxAmountRequired")) / 1e6 for d in docs for a in d.get("accepts") or []
            if isinstance(a, dict) and a.get("network") in (NETWORK, "base") and str(a.get("asset", "")).lower()
            == USDC_BASE.lower() and str(a.get("amount") or a.get("maxAmountRequired") or "").isdigit()]
    return (min(amts) if amts else None), f.get("status")


def buy(method, url, body):
    cmd = ["npx", "-y", "@paybox-sh/sdk", "--json", "use-service", "--credential", CREDENTIAL, "--url", url,
           "--method", method]
    if body is not None:
        cmd += ["--body", json.dumps(body)]
    t0 = time.time()
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    return {"exit": p.returncode, "stdout": p.stdout[-200000:], "stderr": p.stderr[-4000:], "secs": round(time.time() - t0, 1)}


def top_story_from(record):
    """METHOD.md section 1: the first headline in toon.haus Market News, read from the seller's own answer."""
    try:
        body = json.loads(record["bought"]["stdout"])["response"]["output"]["value"]["resource"]["body"]
        return (json.loads(body).get("news") or [{}])[0].get("headline")
    except Exception:
        return None


def run_bundle(name, i, pay, state):
    plan = BUNDLES[name](i)
    rec = {"bundle": name, "run": i, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "input": plan["input"],
           "missing_required": plan.get("missing_required", []), "steps": []}

    def do(steps):
        for sid, method, url, body, required in steps:
            host = url.split("/")[2]
            price, status = price_of(method, url, body)
            s = {"step": sid, "required": required, "method": method, "url": url, "body": body, "knock_status": status,
                 "price": price}
            if host not in APPROVED:
                s["skipped"] = "seller not on the approved list"
            elif price is None:
                s["skipped"] = f"no Base USDC price in the 402 (status {status})"
            elif price > CAP + 1e-9:
                s["skipped"] = f"price {price} over the ${CAP} cap"
            elif state["spent"] + price > state["budget"] + 1e-9:
                s["skipped"] = "would pass the approved budget"
            elif pay:
                s["bought"] = buy(method, url, body)
                state["spent"] += price
            rec["steps"].append(s)
            print(f"  {name} #{i} {sid:16} ${price if price is not None else '-':<7} "
                  f"{s.get('skipped') or ('bought, exit ' + str(s['bought']['exit']) if pay else 'would buy')}")
            time.sleep(0.5)

    do(plan["steps"])
    if name == "morning":
        news = next((s for s in rec["steps"] if s["step"] == "market_news" and s.get("bought")), None)
        story = top_story_from(news) if news else ("(practice: top story is read from the market news step)" if not pay else None)
        rec["input"]["top_story"] = story
        if story:
            do(morning_briefing(i, story)["steps"][2:])
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["practice", "run"])
    ap.add_argument("--bundle", choices=list(BUNDLES), action="append")
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--start", type=int, default=0, help="first input index (continue a series)")
    ap.add_argument("--budget", type=float, default=0.0, help="dollars; the batch never spends more")
    a = ap.parse_args()
    pay = a.mode == "run"
    if pay and a.budget <= 0:
        sys.exit("A paid run needs --budget (dollars Leticia approved for this batch).")
    state = {"spent": 0.0, "budget": a.budget if pay else 1e9}
    os.makedirs(OUT, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    path = os.path.join(OUT, f"bundles-{a.mode}-{stamp}.jsonl")
    with open(path, "w") as f:
        for i in range(a.start, a.start + a.runs):
            for name in a.bundle or list(BUNDLES):
                rec = run_bundle(name, i, pay, state)
                f.write(json.dumps(rec) + "\n")
                f.flush()
    print(f"\n{'spent' if pay else 'would spend'} about ${state['spent'] if pay else sum_would(path):.3f}; saved {path}")


def sum_would(path):
    return sum(s["price"] or 0 for l in open(path) for s in json.loads(l)["steps"] if not s.get("skipped"))


if __name__ == "__main__":
    main()

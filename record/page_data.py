"""Build data/page.json: the small file the page loads (latest verdict + last 24 hourly checks)."""
import json
import os

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")


def load(name, default):
    p = os.path.join(DATA, name)
    return json.load(open(p)) if os.path.exists(p) else default


def main():
    eps = {e["id"]: e for e in load("endpoints.json", {"endpoints": []})["endpoints"]}
    latest = load("latest.json", {"checks": {}})
    hist = {**load("history-daily.json", {}), **load("history-hourly.json", {})}
    rows = []
    for key, c in latest["checks"].items():
        e = eps.get(key, {})
        rows.append({
            "seller": e.get("seller"), "method": e.get("method"), "url": e.get("url"),
            "sources": e.get("sources"), "payers_30d": e.get("payers_30d"), "tier": e.get("tier"),
            "listed_price": e.get("price_usd"), "price": c.get("price_usd"), "pay_to": c.get("pay_to"),
            "verdict": c["verdict"], "notes": c["notes"], "status": c.get("status"), "ms": c.get("ms"),
            "at": c["at"], "recent": "".join(h[1] for h in hist.get(c["hid"], [])[-24:]),
        })
    page = {"updated_at": latest.get("updated_at"), "listed": len(eps), "rows": rows,
            "paid": load("paid_checks.json", [])}
    json.dump(page, open(os.path.join(DATA, "page.json"), "w"), separators=(",", ":"))
    print(f"page.json: {len(rows)} rows")


if __name__ == "__main__":
    main()

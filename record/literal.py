"""The literal agent: follow each listing exactly and see whether it reaches a correct payment request.

Claim L in validation/METHOD.md section 9. Uses only what the listing gives: method, URL, example path and
query values, example body. No model, no guessing. Never pays.

Levels: L0 cannot build the request, L1 no payment request, L2 payable but differs from the listing,
L3 payable and matches. "served" = a real answer without asking for payment (outside the four levels).

Usage: python3 literal.py
"""
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote, urlencode, urlparse, urlunparse

from knock import DATA, PAUSE, SAFE_METHODS, WORKERS, fetch, judge

TEMPLATE = re.compile(r":([A-Za-z_][A-Za-z0-9_]*)|\{([^}/]*)\}|<([^>/]*)>")
TRANSIENT = ("no answer", "HTTP 429", "HTTP 5")
SKIP_HEADERS = {"authorization", "x-payment", "payment-signature", "cookie"}


def norm(name):
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


def find(name, values, lenient):
    if name in values:
        return values[name], "exact"
    if not lenient:
        return None, None
    n = norm(name)
    for k, v in values.items():
        m = norm(k)
        if m and (m == n or n.endswith(m) or n.startswith(m) or m.endswith(n) or m.startswith(n)):
            return v, "lenient"
    return None, None


def build(ep, lenient=False):
    """Return (request ep, None) or (None, reason) when the listing does not give what the URL needs."""
    inp = ep.get("input") or {}
    path_vals = inp.get("pathParams") or {}
    u = urlparse(ep["url"])
    missing = []

    def fill(m):
        name = m.group(1) or m.group(2) or m.group(3)
        val, _ = find(name, path_vals, lenient)
        if val is None:
            missing.append(name)
            return m.group(0)
        return quote(str(val), safe="")

    path = TEMPLATE.sub(fill, u.path)
    if missing:
        if any(find(n, path_vals, True)[0] is not None for n in missing):
            why = "name mismatch"
        elif any(n in (inp.get("described") or []) for n in missing):
            why = "described only"
        else:
            why = "not described"
        return None, f"cannot fill {', '.join(':' + n for n in missing)} ({why})"
    query = inp.get("queryParams") or {}
    flat = {k: (json.dumps(v) if isinstance(v, (dict, list)) else v) for k, v in query.items() if v is not None}
    q = "&".join(x for x in (u.query, urlencode(flat)) if x)
    body = inp.get("body") if str(inp.get("bodyType") or "json").lower() == "json" else None
    headers = {k: str(v) for k, v in (inp.get("headers") or {}).items()
               if isinstance(v, (str, int)) and k.lower() not in SKIP_HEADERS}
    return {**ep, "url": urlunparse(u._replace(path=path, query=q)), "body": body, "headers": headers}, None


def level(j):
    v, notes = j["verdict"], j["notes"]
    if v == "alive":
        return "L3"
    if v == "warning" and any(n.startswith("gave a real answer") for n in notes):
        return "served"
    if v == "warning" and not any(n.startswith(("asks for payment", "only accepts test")) for n in notes):
        return "L2"
    return "L1"


def run(ep):
    out = {}
    for mode in ("strict", "lenient"):
        req, why = build(ep, lenient=(mode == "lenient"))
        if req is None:
            out[mode] = {"level": "L0", "why": why}
            continue
        if mode == "lenient" and out["strict"].get("url") == req["url"]:
            out[mode] = dict(out["strict"])  # same request, no second call
            continue
        f = fetch(req)
        j = judge(ep, f)
        lv = level(j)
        transient = lv == "L1" and any(n.startswith(TRANSIENT) for n in j["notes"])
        out[mode] = {"level": lv, "seen_once": transient, "url": req["url"], "status": f.get("status"),
                     "at": f["at"], "notes": j["notes"]}
    return out


def main():
    eps = json.load(open(os.path.join(DATA, "endpoints.json")))["endpoints"]
    todo = [e for e in eps if e["method"] in SAFE_METHODS and not e["free"]]
    print(f"literal agent: {len(todo)} listings")
    by_host = {}
    for i, e in enumerate(todo):
        by_host.setdefault(e["url"].split("/")[2], []).append(i)
    results = [None] * len(todo)

    def run_host(idx):
        for n, i in enumerate(idx):
            if n:
                time.sleep(PAUSE)
            results[i] = run(todo[i])

    with ThreadPoolExecutor(WORKERS) as ex:
        list(ex.map(run_host, by_host.values()))
    rows = {e["id"]: r for e, r in zip(todo, results)}
    summary = {m: {} for m in ("strict", "lenient")}
    for r in rows.values():
        for m in summary:
            k = r[m]["level"] + (" (seen once)" if r[m].get("seen_once") else "")
            summary[m][k] = summary[m].get(k, 0) + 1
    doc = {"checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "summary": summary, "rows": rows}
    json.dump(doc, open(os.path.join(DATA, "literal.json"), "w"), separators=(",", ":"))
    print(json.dumps(summary))


if __name__ == "__main__":
    main()

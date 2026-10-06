"""Claim Q (validation/METHOD.md section 10): the literal agent on providers waiting to be listed on pay.sh.

Reads each open pull request that adds a provider, at its head commit, and follows the listing exactly.
Never pays. Needs the GitHub CLI (`gh`) and PyYAML.

Usage: python3 queue.py <output dir>   (results name unaccepted sellers; keep them out of the public repo)
"""
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import yaml

from collect import openapi_input
from knock import PAUSE, fetch, judge
from literal import TRANSIENT, build

REPO = "solana-foundation/pay-skills"


def gh(path):
    out = subprocess.run(["gh", "api", "--paginate", path], capture_output=True, text=True)
    if out.returncode:
        return None
    try:
        return json.loads(out.stdout)
    except json.JSONDecodeError:  # paginated arrays come back concatenated
        return json.loads("[" + out.stdout.replace("][", "],[") + "]")


def content(path, ref):
    out = subprocess.run(["gh", "api", f"repos/{REPO}/contents/{path}?ref={ref}", "--jq", ".content"],
                         capture_output=True, text=True)
    if out.returncode:
        return None
    import base64
    return base64.b64decode(out.stdout.strip()).decode("utf-8", "replace")


def front_matter(text):
    if not text or not text.startswith("---"):
        return {}
    try:
        return yaml.safe_load(text.split("---", 2)[1]) or {}
    except yaml.YAMLError:
        return {}


def listings():
    prs = gh(f"repos/{REPO}/pulls?state=open&per_page=100") or []
    prs = [p for page in prs for p in (page if isinstance(page, list) else [page])] if prs and isinstance(prs[0], list) else prs
    new, changed = [], []
    for p in prs:
        sha = p["head"]["sha"]
        files = gh(f"repos/{REPO}/pulls/{p['number']}/files?per_page=100") or []
        pays = [f["filename"] for f in files if f["filename"].endswith("/PAY.md")]
        for path in pays:
            on_main = content(path, "main") is not None
            row = {"pr": p["number"], "author": p["user"]["login"], "opened": p["created_at"], "sha": sha, "pay_md": path}
            (changed if on_main else new).append(row)
    return new, changed


def endpoints(row):
    text = content(row["pay_md"], row["sha"])
    fm = front_matter(text)
    base = str(fm.get("service_url") or "").rstrip("/")
    eps, doc = [], {}
    oa = fm.get("openapi") or {}
    if isinstance(oa, dict) and oa.get("path"):
        raw = content(os.path.join(os.path.dirname(row["pay_md"]), oa["path"]), row["sha"])
        try:
            doc = json.loads(raw) if raw and raw.lstrip().startswith("{") else (yaml.safe_load(raw) if raw else {})
        except Exception:
            doc = {}
    elif isinstance(oa, dict) and isinstance(oa.get("content"), (dict, str)):
        doc = oa["content"] if isinstance(oa["content"], dict) else (yaml.safe_load(oa["content"]) or {})
    for path, ops in (doc.get("paths") or {}).items():
        for method, op in (ops or {}).items():
            if method.upper() in ("GET", "POST"):
                eps.append({"method": method.upper(), "path": path, "input": openapi_input(doc, path, method.upper())})
    for e in fm.get("endpoints") or []:  # legacy inline list
        if isinstance(e, dict) and str(e.get("method", "GET")).upper() in ("GET", "POST"):
            eps.append({"method": str(e.get("method", "GET")).upper(), "path": e.get("path", ""), "input": {}})
    return base, eps, bool(text), bool(doc) or bool(fm.get("endpoints"))


def level(j):
    v, notes = j["verdict"], j["notes"]
    if v == "alive":
        return "L3"
    if v == "warning" and any(n.startswith("gave a real answer") for n in notes):
        return "free"
    if v == "unclear" and any(n.startswith("gave an answer without asking") for n in notes):
        return "free"
    if v == "warning" and not any(n.startswith(("asks for payment", "only accepts test")) for n in notes):
        return "L2"
    return "L1"


def check(row):
    base, eps, has_md, has_spec = endpoints(row)
    row = dict(row, service_url=base, read_ok=has_md, spec_ok=has_spec, endpoints=[])
    if not base:
        return row
    for n, e in enumerate(eps):
        if n:
            time.sleep(PAUSE)
        ep = {"id": f"{e['method']} {base}/{e['path'].lstrip('/')}", "method": e["method"],
              "url": f"{base}/{e['path'].lstrip('/')}", "input": e["input"], "sources": ["pay.sh-queue"],
              "catalog_options": None, "price_usd": None}
        out = {"id": ep["id"]}
        for mode in ("strict", "lenient"):
            req, why = build(ep, lenient=(mode == "lenient"))
            if req is None:
                out[mode] = {"level": "L0", "why": why}
                continue
            if mode == "lenient" and out["strict"].get("url") == req["url"]:
                out[mode] = dict(out["strict"])
                continue
            f = fetch(req)
            j = judge(ep, f)
            lv = level(j)
            out[mode] = {"level": lv, "seen_once": lv == "L1" and any(x.startswith(TRANSIENT) for x in j["notes"]),
                         "url": req["url"], "status": f.get("status"), "at": f["at"], "notes": j["notes"]}
        row["endpoints"].append(out)
    return row


def main(outdir):
    os.makedirs(outdir, exist_ok=True)
    t0 = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    new, changed = listings()
    latest = {}
    for r in new:  # one provider can sit in several pull requests; keep the newest
        if r["pay_md"] not in latest or r["pr"] > latest[r["pay_md"]]["pr"]:
            latest[r["pay_md"]] = r
    dupes = len(new) - len(latest)
    new = sorted(latest.values(), key=lambda r: r["pr"])
    print(f"duplicate provider entries dropped: {dupes}")
    print(f"open PRs adding a provider: {len(new)}; changing an existing one: {len(changed)}")
    with ThreadPoolExecutor(12) as ex:
        rows = list(ex.map(check, new))
    json.dump({"snapshot_at": t0, "new": rows, "changed_only": changed}, open(os.path.join(outdir, "queue.json"), "w"), indent=1)
    lv = {}
    for r in rows:
        for e in r["endpoints"]:
            lv[e["strict"]["level"]] = lv.get(e["strict"]["level"], 0) + 1
    ready = sum(any(e["strict"]["level"] == "L3" for e in r["endpoints"]) for r in rows)
    print(f"providers: {len(rows)}, reach a correct payment request: {ready}; endpoint levels (strict): {lv}")


if __name__ == "__main__":
    main(sys.argv[1])

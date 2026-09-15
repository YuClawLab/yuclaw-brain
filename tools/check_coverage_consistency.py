#!/usr/bin/env python3
"""Coverage-consistency gate (QA-01, 2026-09-15). The same named quantity — Evidence Coverage (metric_id `ecs`,
protocol e3d51f5b0ca3) — must show the same value on every current public surface, and every surface must be
bound to the same artifact instance (as_of + source sha256). Surfaces joined on (ticker, metric_id, as_of, sha256):
  docs/coverage.json (the shared artifact) · docs/explorer_data.json rows[].ecs + coverage_source ·
  docs/why/{T}.json evidence_coverage.ecs (+ identity) · docs/index.html signals table (data attributes + cells) ·
  docs/why/{T}.html ECS term (data-ecs attribute).
Expected ticker set = the bound universe artifact (v3/universe.json scoring tier), never a fixed constant.
Fails on: missing tickers, a surface bound to a different (stale) artifact identity, or any unexplained
same-metric difference. Different documented metrics are never compared to each other.
Exit 0 = consistent; 1 = findings."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
DOCS = _REPO / "docs"
sys.path.insert(0, str(_REPO))


def load_surfaces(docs: Path = DOCS) -> dict:
    cov = json.loads((docs / "coverage.json").read_text())
    ident = (cov["as_of"], cov["source_identity"]["sha256"])
    ex = json.loads((docs / "explorer_data.json").read_text())
    ex_ident = (ex.get("coverage_source") or {}).get("as_of"), (ex.get("coverage_source") or {}).get("source_sha256")
    ex_vals = {r["ticker"]: r.get("ecs") for r in ex["rows"]}
    html = (docs / "index.html").read_text(errors="replace")
    m = re.search(r'<table\s+data-coverage-metric="ecs" data-coverage-as-of="([^"]*)" data-coverage-sha256="([^"]*)"', html)
    home_ident = (m.group(1), m.group(2)) if m else (None, None)
    home_vals = {}
    for row in re.findall(r"<tr>(.*?)</tr>", html, re.S):
        cells = [re.sub(r"<[^>]+>", "", c).strip() for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        if len(cells) >= 4 and re.fullmatch(r"[A-Z0-9.\-]{1,10}", cells[0]):
            home_vals[cells[0]] = cells[3]
    why_vals, why_ident, why_html = {}, {}, {}
    for f in sorted(docs.glob("why/*.json")):
        if f.name.endswith(".history.json") or f.name == "history_manifest.json":
            continue
        d = json.loads(f.read_text()); ec = d.get("evidence_coverage") or {}
        why_vals[d["ticker"]] = ec.get("ecs"); why_ident[d["ticker"]] = (ec.get("as_of"), ec.get("source_sha256"))
        h = docs / "why" / (f.stem + ".html")
        if h.exists():
            mm = re.search(r'data-ecs="([^"]*)"', h.read_text(errors="replace")); why_html[d["ticker"]] = mm.group(1) if mm else None
    return {"artifact": cov, "ident": ident, "explorer": (ex_vals, ex_ident), "home": (home_vals, home_ident), "why": (why_vals, why_ident, why_html)}


def check(docs: Path = DOCS) -> list[str]:
    from v3.universe_tiers import scoring_universe
    expected = sorted(scoring_universe())
    s = load_surfaces(docs); cov = s["artifact"]; ident = s["ident"]; f = []
    def same(a, b):
        return str(a) == str(b) or (a in (None, "—", "") and b in (None, "—", ""))
    art = cov["tickers"]
    for t in expected:
        if t not in art:
            f.append(f"{t}: missing from the shared coverage artifact")
    for name, (vals, sid) in (("explorer_data.json", s["explorer"]), ("index.html", s["home"])):
        if tuple(sid) != ident:
            f.append(f"{name}: bound to a different artifact identity {sid} != {ident} (stale or unbound surface)")
        for t in expected:
            if t not in vals:
                f.append(f"{name}: {t} missing")
            elif not same(vals[t], art.get(t, {}).get("ecs")):
                f.append(f"{name}: {t} ecs {vals[t]} != artifact {art.get(t, {}).get('ecs')}")
    why_vals, why_ident, why_html = s["why"]
    for t in expected:
        if t not in why_vals:
            f.append(f"why/{t}.json: missing"); continue
        if why_ident[t] != ident:
            f.append(f"why/{t}.json: bound to a different artifact identity {why_ident[t]} != {ident}")
        if not same(why_vals[t], art.get(t, {}).get("ecs")):
            f.append(f"why/{t}.json: ecs {why_vals[t]} != artifact {art.get(t, {}).get('ecs')}")
        if t in why_html and not same(why_html[t], art.get(t, {}).get("ecs")):
            f.append(f"why/{t}.html: ecs {why_html[t]} != artifact {art.get(t, {}).get('ecs')}")
    return f


def main(argv=None) -> int:
    f = check()
    for x in f[:40]:
        print(f"FAIL {x}")
    n = len(json.loads((DOCS / 'coverage.json').read_text())['tickers'])
    print(f"[coverage-consistency] {'OK' if not f else str(len(f)) + ' finding(s)'} — metric ecs; {n} tickers in the shared artifact; surfaces joined on ticker + metric + as_of + sha256")
    return 1 if f else 0


if __name__ == "__main__":
    sys.exit(main())

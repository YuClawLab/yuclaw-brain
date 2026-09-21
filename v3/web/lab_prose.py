"""Validation Lab prose that is DERIVED from the same data as the tables (8.0.1 C01).

Until 8.0.0 three sentences on the Lab page were typed by hand — "forward 5d IC +0.09", "the forward 20-day IC is
positive on all observed dates", "2,847 leaf hashes" — and stayed on the page after the tables and the public replay
bundle had moved to -0.0277, -0.0399 with 43% positive dates, and 7,192 leaves. Every numerical, directional and
sample-size statement is now computed here from the rigor dictionary (`v3.lab.rigor.compute_rigor()`, which is also
the bundle's `expected` block) and from the bundle's own identity, with the formats the tables use. Nothing here
turns a negative or non-significant result into a positive claim; where the data are insufficient it says so.

Pure functions, standard library only: the renderer, the restage tool and the tests share them. The statistics
themselves are not computed or changed here.
"""
from __future__ import annotations

import re
from html import escape

ALPHA = 0.05
MARK = "LAB-DERIVED"                       # <!-- LAB-DERIVED:<name> BEGIN --> … <!-- LAB-DERIVED:<name> END -->


def marked(name: str, html: str) -> str:
    return f"<!-- {MARK}:{name} BEGIN -->{html}<!-- {MARK}:{name} END -->"


def fmt_ic(x) -> str:
    return f"{x:+.4f}"                     # the IC table's format


def fmt_p(p) -> str:
    return "—" if p is None else ("<0.001" if p < 0.001 else f"{p:.3f}")


def _ic(fwd: dict | None, h: int) -> dict | None:
    ic = ((fwd or {}).get("ic") or {})
    v = ic.get(h) or ic.get(str(h))
    return v if v and v.get("mean_ic") is not None else None


def forward_significant(fwd: dict | None) -> list[dict]:
    """Every forward statistic whose overlap-corrected p-value is below 5%, with its value (so its SIGN is never lost).
    An IC whose t-statistic is not reliable (too few independent blocks) is never counted as significant."""
    out = []
    if not fwd or not fwd.get("evaluable"):
        return out
    for key, label in (("top_minus_bottom", "top − bottom decile spread"), ("top_minus_universe", "top decile − universe spread")):
        s = (fwd.get("spreads") or {}).get(key) or {}
        if s.get("p_value") is not None and s["p_value"] < ALPHA and s.get("mean_per_period") is not None:
            out.append({"label": label, "text": f"{s['mean_per_period'] * 100:+.3f}% per period", "value": s["mean_per_period"], "p": s["p_value"]})
    for h in (1, 5, 20):
        ic = _ic(fwd, h)
        if ic and ic.get("t_reliable", True) and ic.get("nw_p_value") is not None and ic["nw_p_value"] < ALPHA:
            out.append({"label": f"{h}-day IC", "text": fmt_ic(ic["mean_ic"]), "value": ic["mean_ic"], "p": ic["nw_p_value"]})
    for key, label in (("vs_universe", "alpha vs the universe"), ("vs_spy", "alpha vs SPY")):
        m = (fwd.get("market_model") or {}).get(key) or {}
        if m.get("p_alpha") is not None and m["p_alpha"] < ALPHA and m.get("alpha_per_period") is not None:
            out.append({"label": label, "text": f"{m['alpha_per_period'] * 100:+.3f}% per period", "value": m["alpha_per_period"], "p": m["p_alpha"]})
    return out


def ic_clause(fwd: dict | None, h: int) -> str:
    """One horizon, stated with the table's own numbers: value, share of positive dates, number of dates, and whether it can be tested."""
    ic = _ic(fwd, h)
    if ic is None:
        return f"the forward {h}-day IC is not available yet (insufficient data)"
    share = ic.get("ic_positive_share")
    pos = f", positive on {share * 100:.0f}% of {ic['n_dates']} observed dates" if share is not None and ic.get("n_dates") else ""
    if not ic.get("t_reliable", True):
        test = " — too few independent blocks to test; descriptive only"
    elif ic.get("nw_p_value") is None:
        test = " — no test available"
    else:
        test = f" (Newey–West p = {fmt_p(ic['nw_p_value'])}; {'significant' if ic['nw_p_value'] < ALPHA else 'not significant'} at 5%)"
    return f"the forward {h}-day IC is {fmt_ic(ic['mean_ic'])}{pos}{test}"


def rigor_reading(rig: dict) -> str:
    """The paragraph under Panel 3 (inner HTML)."""
    fwd = (rig or {}).get("forward")
    if not fwd or not fwd.get("evaluable"):
        return ("Honest reading: <strong style=\"color:#E2E8F0\">the forward panel is not evaluable yet — too few periods for any forward statistic</strong>. "
                "That is insufficient evidence, not a positive and not a negative finding; the statistics accrue daily and this panel recomputes with them.")
    sig = forward_significant(fwd); c20 = ic_clause(fwd, 20); c20 = c20[0].upper() + c20[1:]
    if not sig:
        return ("Honest reading: at the current sample sizes, <strong style=\"color:#E2E8F0\">no forward spread, IC, or alpha is "
                f"statistically significant at the 5% level once overlap is corrected</strong>. {escape(c20)}. "
                "\"Not yet significant\" is the finding — the statistics accrue daily and this panel recomputes with them.")
    parts = "; ".join(f"{escape(s['label'])} {escape(s['text'])} (p = {fmt_p(s['p'])}){' — NEGATIVE, adverse to the signal' if s['value'] < 0 else ''}" for s in sig)
    tone = ("Every one of them is negative: this window is evidence against the signal, not for it." if all(s["value"] < 0 for s in sig) else
            "One window is not proof: no claim of forward alpha is made, and a negative entry above is adverse evidence.")
    return (f"Honest reading: <strong style=\"color:#E2E8F0\">{len(sig)} forward statistic{'s' if len(sig) != 1 else ''} reach{'es' if len(sig) == 1 else ''} the 5% level in this window</strong> — {parts}. "
            f"{tone} {escape(c20)}. The statistics accrue daily and this panel recomputes with them.")


def ic_not_proven_line(rig: dict) -> str:
    """The 'not proven' list entry about IC significance (plain text; the caller escapes nothing further)."""
    fwd = (rig or {}).get("forward"); ic5 = _ic(fwd, 5) if fwd and fwd.get("evaluable") else None
    if ic5 is None:
        return "IC significance — the forward IC is not evaluable yet (insufficient dates); nothing is claimed"
    five = ic_clause(fwd, 5).replace("the forward 5-day IC is", "forward 5d IC"); twenty = ic_clause(fwd, 20).replace("the forward 20-day IC is", "20d IC")
    lead = "IC significance — " + five
    if ic5.get("t_reliable", True) and ic5.get("nw_p_value") is not None and ic5["nw_p_value"] < ALPHA:
        lead += " — NEGATIVE, adverse to the signal" if ic5["mean_ic"] < 0 else " — one window; replication pending, no claim of predictive power"
    return f"{lead}; {twenty}"


def reproducibility_line(bundle: dict | None) -> str:
    """The 'proven' list entry: the leaf count is the published bundle's own count, with the bundle's identity."""
    n = (bundle or {}).get("n_leaves")
    if not n:
        return "One-command reproducibility — every statistic and every ledger leaf hash re-derive from published data"
    # identity WITHOUT a timestamp: the site's stamp rule keeps raw build times inside the buildinfo footer (tools/check_site_walk.py)
    ident = (f" (the published replay bundle: {bundle['daily_roots']} daily roots" if bundle.get("daily_roots") else " (the published replay bundle") + (f", source {bundle['source_commit']}" if bundle.get("source_commit") else "") + ")"
    return f"One-command reproducibility — every statistic + {n:,} leaf hashes re-derive from published data{ident}"


def headline(rig: dict) -> str:
    """The bold first sentence of the 'Honest reading' card."""
    fwd = (rig or {}).get("forward")
    if not fwd or not fwd.get("evaluable"):
        return "The forward panel is not evaluable yet: nothing about forward alpha is claimed."
    alpha = [s for s in forward_significant(fwd) if "alpha" in s["label"] or "spread" in s["label"]]
    if not alpha:
        return "No forward alpha has been statistically proven yet."
    if all(s["value"] < 0 for s in alpha):
        return "No forward alpha has been proven; the forward results that reach significance in this window are NEGATIVE."
    return "A forward return statistic reaches the 5% level in this one window; that is not proof of forward alpha, and none is claimed."


def bundle_identity(bundle_json: dict | None) -> dict:
    if not bundle_json:
        return {}
    leaves = bundle_json.get("ledger_leaves") or {}
    return {"n_leaves": sum(len(v) for v in leaves.values()) if isinstance(leaves, dict) else len(leaves), "built_utc": bundle_json.get("built_utc"),
            "source_commit": (bundle_json.get("source_commit") or "")[:12], "daily_roots": len(bundle_json.get("ledger_daily_roots") or {})}


# ------------------------------------------------------------------ the page's derived fragments: find / replace / compare
_LEGACY = {"reproducibility": re.compile(r"One-command reproducibility — [^<]*"), "ic-significance": re.compile(r"IC significance — [^<]*"),
           "rigor-reading": re.compile(r"Honest reading: at the current sample sizes,.*?recomputes with them\.", re.S), "headline": re.compile(r"<strong>No forward alpha has been statistically proven yet\.</strong>")}


def fragments(rig: dict, bundle: dict | None) -> dict:
    return {"reproducibility": escape(reproducibility_line(bundle)), "ic-significance": escape(ic_not_proven_line(rig)), "rigor-reading": rigor_reading(rig), "headline": f"<strong>{escape(headline(rig))}</strong>"}


def restage(html: str, rig: dict, bundle: dict | None) -> str:
    """Put the derived fragments into an already rendered page — marked ones are replaced between their markers, the
    unmarked 8.0.0 sentences are found by their fixed openings. Tables and every other byte are untouched."""
    for name, frag in fragments(rig, bundle).items():
        pat = re.compile(re.escape(f"<!-- {MARK}:{name} BEGIN -->") + r".*?" + re.escape(f"<!-- {MARK}:{name} END -->"), re.S)
        if pat.search(html):
            html = pat.sub(lambda _m, f=frag, n=name: marked(n, f), html, count=1)
        elif _LEGACY[name].search(html):
            html = _LEGACY[name].sub(lambda _m, f=frag, n=name: marked(n, f), html, count=1)
        else:
            raise ValueError(f"the page carries neither the marked nor the 8.0.0 form of the derived fragment {name!r}")
    return html


def stale(html: str, rig: dict, bundle: dict | None) -> list[str]:
    """Names of derived fragments whose text on the page is not what the data say (empty list = consistent)."""
    out = []
    for name, frag in fragments(rig, bundle).items():
        m = re.search(re.escape(f"<!-- {MARK}:{name} BEGIN -->") + r"(.*?)" + re.escape(f"<!-- {MARK}:{name} END -->"), html, re.S)
        if not m or m.group(1) != frag:
            out.append(name)
    return out

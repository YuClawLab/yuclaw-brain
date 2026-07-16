"""
Evidence packets — downloadable, citable exports for the Lab, Open Index
Evidence, and Canada Resources pages (usefulness build, 2026-07-16).

One .zip per page under docs/packets/, regenerated in the daily chain
(cron/refresh_v3_pages.sh) so a packet is never staler than its page.

EXPORT RULE (hard): YUCLAW-derived data only — derived statistics, counts,
classifications, verified excerpts of public SEC filings. NEVER raw vendor
OHLCV/options rows (data-vendor ToS). CAR paths, period returns, and
coverage windows are derived statistics and ship; price series do not.

Every packet carries mandatory metadata (METADATA.json): data-through date,
build date, source commit, ledger root, methodology version, scope note,
known limitations — plus CITATION.txt with the locked citation snippet.

CLI:
    python3 -m v3.web.evidence_packets            # build all three
    python3 -m v3.web.evidence_packets --only lab
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import psycopg2

from v3.web.useful_blocks import VERSION, citation_snippet

_REPO = Path(__file__).resolve().parents[2]
OUT_DIR = _REPO / "docs" / "packets"
DSN = "dbname=yuclaw_events"

METHODOLOGY_VERSION = f"{VERSION} · docs/methodology/validation_lab.md"

PACKETS = {
    "lab": {
        "page_label": "Validation Lab",
        "zip": "yuclaw_validation_lab_packet.zip",
        "scope_note": ("Scoring universe only (79 tickers). Evidence-tier names are "
                       "excluded from every cohort, decile, and statistic in this packet."),
        "limitations": [
            "Forward window is young; no spread, IC, or alpha is significant at 5% with adequate power.",
            "In-sample replay panel carries parametric look-ahead — educational only.",
            "Insider-evidence stream: batch coverage 2026-02-18 → 2026-05-15; live from 2026-07-16; the gap is backfilled with ingestion-time available_as_of.",
        ],
    },
    "open_index": {
        "page_label": "Open Index Evidence",
        "zip": "yuclaw_open_index_evidence_packet.zip",
        "scope_note": ("SMH holdings ∩ the 79-ticker scoring universe (US EDGAR filers only). "
                       "Event-study statistics are derived abnormal-return aggregates; "
                       "two models (peer, market) are reported separately, never averaged."),
        "limitations": [
            "Coverage is the measured overlap only — not a total-index claim.",
            "Live-era event sample is small; backfill-era and live-era pools are reported separately.",
            "CAR aggregates are underpowered at current n for most event types.",
        ],
    },
    "canada": {
        "page_label": "Canada Resources Evidence",
        "zip": "yuclaw_canada_resources_packet.zip",
        "scope_note": ("Evidence tier ONLY (49 SEC filers across XEG/ZEO/GDX/URNM lenses) — "
                       "ingested, classified, displayed; NEVER scored, never in "
                       "signal_snapshots, never in Lab panels or the forward track."),
        "limitations": [
            "MJDS/FPI names: insider data is outside current evidence scope (SEDI substrate not ingested); Form-4 coverage exists only for the 8 US-domestic filers.",
            "Coverage percentages are SEC-filing evidence only, as measured in the Phase-1 study — not total-evidence claims.",
            "One name (WCPRF) is a low-quality OTC proxy line; its price history is not equivalent to primary US listings.",
        ],
    },
}


# --------------------------------------------------------------------------- #
# shared metadata helpers
# --------------------------------------------------------------------------- #
def _git_commit() -> str:
    r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=_REPO,
                       capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else "unknown"


def _ledger_tip() -> dict:
    from v3.web.render_validation_lab import _ledger_tip as tip
    return tip()


def _json_bytes(obj) -> bytes:
    return json.dumps(obj, indent=1, default=str, sort_keys=True).encode()


def _metadata(kind: str, data_through: str, built: str, commit: str, ledger: dict) -> dict:
    spec = PACKETS[kind]
    return {
        "packet": spec["page_label"],
        "version": VERSION,
        "data_through": data_through,
        "build_date": built,
        "source_commit": commit,
        "ledger_root": ledger.get("root"),
        "ledger_block_date": ledger.get("date"),
        "methodology_version": METHODOLOGY_VERSION,
        "scope_note": spec["scope_note"],
        "known_limitations": spec["limitations"],
        "export_rule": ("YUCLAW-derived data only — derived statistics, counts, "
                        "classifications, verified filing excerpts. No raw vendor "
                        "OHLCV/options data."),
        "compliance": ("Research and education only. Not investment advice. "
                       "Research classifications, not recommendations."),
    }


def _events_csv(tickers: list[str], columns_note: bool = True) -> bytes:
    """Accepted events for `tickers` as CSV — derived fields only (no prices)."""
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["event_id", "ticker", "event_type", "magnitude", "direction",
                "event_time_utc", "source_publish_time_utc", "available_as_of_utc",
                "source_form", "source_url", "llm_model", "llm_confidence",
                "verified_excerpt"])
    with psycopg2.connect(DSN) as cn:
        cn.set_session(readonly=True)
        with cn.cursor() as cur:
            cur.execute(
                """SELECT event_id, ticker, event_type, magnitude, direction,
                          event_time, source_publish_time, available_as_of,
                          source_type, source_url, llm_model, llm_confidence,
                          raw_excerpt
                   FROM events
                   WHERE event_status='accepted' AND ticker = ANY(%s)
                   ORDER BY available_as_of, ticker, event_id""", (sorted(tickers),))
            for row in cur.fetchall():
                w.writerow(["" if v is None else v for v in row])
    return buf.getvalue().encode()


def _write_zip(path: Path, files: dict[str, bytes]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in sorted(files.items()):
            z.writestr(name, data)


# --------------------------------------------------------------------------- #
# packet builders — each returns (zip_path, contents_listing, data_through)
# --------------------------------------------------------------------------- #
def build_lab_packet(built: str, commit: str, ledger: dict) -> tuple[Path, list[str], str]:
    from v3.lab.cohort_engine import compute_all, current_top_decile
    from v3.lab.qualified import compute_qualified
    from v3.lab.rigor import compute_rigor

    data_through = str(ledger.get("date") or built[:10])
    files: dict[str, bytes] = {}

    bundle = _REPO / "docs" / "replay" / "lab_replay_bundle.json"
    if bundle.exists():
        files["lab_replay_bundle.json"] = bundle.read_bytes()

    files["cohort_summary.json"] = _json_bytes(compute_all())
    files["statistical_tests.json"] = _json_bytes(compute_rigor())
    files["qualified_cohort.json"] = _json_bytes(compute_qualified())

    td = current_top_decile()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["as_of", "universe_n", "k", "ticker", "grade"])
    for m in td.get("members", []):
        if isinstance(m, dict):
            w.writerow([td.get("as_of"), td.get("universe_n"), td.get("k"),
                        m.get("ticker"), m.get("grade", "")])
        else:
            w.writerow([td.get("as_of"), td.get("universe_n"), td.get("k"), m, ""])
    files["decile_membership.csv"] = buf.getvalue().encode()

    meta = _metadata("lab", data_through, built, commit, ledger)
    files["METADATA.json"] = _json_bytes(meta)
    files["CITATION.txt"] = (citation_snippet(PACKETS["lab"]["page_label"],
                                              data_through, built[:10], commit) + "\n").encode()

    path = OUT_DIR / PACKETS["lab"]["zip"]
    _write_zip(path, files)
    listing = [n for n in sorted(files) if n not in ("METADATA.json", "CITATION.txt")]
    return path, listing, data_through


def build_open_index_packet(built: str, commit: str, ledger: dict) -> tuple[Path, list[str], str]:
    from v3.lab.etf_evidence import compute_all as oie_compute_all, overlap_summary

    data = oie_compute_all()
    es = data["event_study"]
    ov = overlap_summary()
    data_through = (es.get("price_coverage") or [None, built[:10]])[1]

    files: dict[str, bytes] = {}
    files["events.csv"] = _events_csv(list(ov.get("covered", [])))
    files["event_study_summary.json"] = _json_bytes(es)
    files["coverage_statement.json"] = _json_bytes({
        "overlap": ov, "rollup": data["rollup"].get("rollup"),
        "note": ("Coverage = SMH holdings that are US EDGAR filers inside the "
                 "79-ticker scoring universe, as measured — not a total-index claim."),
    })

    meta = _metadata("open_index", str(data_through), built, commit, ledger)
    files["METADATA.json"] = _json_bytes(meta)
    files["CITATION.txt"] = (citation_snippet(PACKETS["open_index"]["page_label"],
                                              str(data_through), built[:10], commit) + "\n").encode()

    path = OUT_DIR / PACKETS["open_index"]["zip"]
    _write_zip(path, files)
    listing = [n for n in sorted(files) if n not in ("METADATA.json", "CITATION.txt")]
    return path, listing, str(data_through)


def build_canada_packet(built: str, commit: str, ledger: dict) -> tuple[Path, list[str], str]:
    from v3.lab.etf_evidence import compute_canada
    from v3.universe_tiers import evidence_tier_tickers

    c = compute_canada()
    ev_tickers = sorted(evidence_tier_tickers())

    with psycopg2.connect(DSN) as cn:
        cn.set_session(readonly=True)
        with cn.cursor() as cur:
            cur.execute("SELECT max(available_as_of)::date FROM events "
                        "WHERE event_status='accepted' AND ticker = ANY(%s)", (ev_tickers,))
            row = cur.fetchone()
    data_through = str(row[0] or built[:10])

    files: dict[str, bytes] = {}
    files["events.csv"] = _events_csv(ev_tickers)

    coverage, lens_summaries, scope_lines = {}, {}, []
    for lens, entry in c["lenses"].items():
        p, mat = entry["posture"], entry["maturity"]
        coverage[lens] = {
            "name": p["name"], "theme": p["theme"],
            "holdings_as_of": p["holdings_as_of"], "holdings_source": p["holdings_source"],
            "sec_filer_weight_pct": p["sec_filer_weight_pct"],
            "n_names_total": p["n_names_total"], "n_names_covered": p["n_names_covered"],
            "members": [{k: m[k] for k in
                         ("ticker", "weight_pct", "sec_name", "filer_class",
                          "listing_quality", "n_filings", "n_events", "grade",
                          "insider_scope")} for m in p["members"]],
        }
        lens_summaries[lens] = {
            "events_total": p["events_total"], "filings_total": p["filings_total"],
            "prose_total": p["prose_total"], "n_events": mat["n_events"],
            "n_matured": mat["n_matured"],
            "event_study": {k: entry["event_study"][k] for k in
                            ("n_events_used", "by_type", "pooled_directional",
                             "insider_stream_note")
                            if k in entry.get("event_study", {})},
        }
        scope_lines.append(f"{lens}: {p['uncovered_scope']}")

    files["coverage.json"] = _json_bytes(coverage)
    files["lens_summaries.json"] = _json_bytes(lens_summaries)
    files["scope_disclosures.txt"] = ("\n".join([
        "SCOPE AND DISCLOSURES — Canada Resources Evidence (evidence tier only, never scored)",
        "",
        "MJDS/SEDI: insiders of MJDS filers report to SEDI (Canada), not SEC Form 4. The SEDI",
        "substrate is not currently ingested — insider data for those names is outside current",
        "evidence scope and is never rendered as zero. Form-4 insider coverage exists only for",
        "the 8 US-domestic filers (NEM, CDE, HL, RGLD, SSRM, UEC, UUUU, URG).",
        "",
        "Per-lens outside-scope blocks:",
        *scope_lines,
    ]) + "\n").encode()

    meta = _metadata("canada", data_through, built, commit, ledger)
    files["METADATA.json"] = _json_bytes(meta)
    files["CITATION.txt"] = (citation_snippet(PACKETS["canada"]["page_label"],
                                              data_through, built[:10], commit) + "\n").encode()

    path = OUT_DIR / PACKETS["canada"]["zip"]
    _write_zip(path, files)
    listing = [n for n in sorted(files) if n not in ("METADATA.json", "CITATION.txt")]
    return path, listing, data_through


BUILDERS = {
    "lab": build_lab_packet,
    "open_index": build_open_index_packet,
    "canada": build_canada_packet,
}


def build(only: str | None = None) -> dict[str, dict]:
    built = datetime.now(timezone.utc).isoformat(timespec="seconds")
    commit = _git_commit()
    ledger = _ledger_tip()
    out = {}
    for kind, fn in BUILDERS.items():
        if only and kind != only:
            continue
        path, listing, data_through = fn(built, commit, ledger)
        out[kind] = {"zip": path.name, "files": listing, "data_through": data_through,
                     "built": built[:10], "commit": commit,
                     "page_label": PACKETS[kind]["page_label"],
                     "size_kb": round(path.stat().st_size / 1024, 1)}
        print(f"[packets] {kind}: {path.name} ({out[kind]['size_kb']} KB) "
              f"data_through={data_through} files={listing}", flush=True)

    # Manifest lets page generators render the packet block (href, citation
    # fields, contents listing) without recomputing packet data.
    manifest = OUT_DIR / "manifest.json"
    existing = {}
    if manifest.exists():
        try:
            existing = json.loads(manifest.read_text())
        except Exception:
            existing = {}
    existing.update(out)
    manifest.write_text(json.dumps(existing, indent=1, sort_keys=True))
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Build downloadable evidence packets")
    p.add_argument("--only", choices=sorted(BUILDERS), help="build a single packet")
    args = p.parse_args(argv)
    build(args.only)
    return 0


if __name__ == "__main__":
    sys.exit(main())

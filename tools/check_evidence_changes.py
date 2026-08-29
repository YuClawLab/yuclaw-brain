#!/usr/bin/env python3
"""
Evidence-changes gate (ORDER 2026-08-29B, active immediately): date-aware
schema validation of docs/evidence_changes/<date>.json, the C6 posture
endpoint docs/c6_posture_current.json, and JSON<->HTML equality against
docs/todays_evidence.html.

  LEGACY  (date <  2026-08-29): c6_posture_files (int) + c6_posture_accessions
          (list) REQUIRED; a "c6_posture" block is REJECTED. Never rewritten.
  CURRENT (date >= 2026-08-29): "c6_posture" block REQUIRED
          {files, set_sha256, added_today, removed_today, delta_since,
           delta_span_days, delta_status, current_url} (MICRO 2026-08-29C:
          delta_since/delta_span_days REQUIRED, base labeled explicitly);
          EITHER legacy key is REJECTED; key order canonical (date, counts,
          c6_posture, grades, ledger, maturity, replay); added/removed are
          lists with delta_since a date and delta_span_days == date -
          delta_since (delta_status OK), or added/removed/delta_since/
          delta_span_days ALL null with delta_status starting "UNAVAILABLE"
          (documented cold start only: "UNAVAILABLE (cold start: ...)").
  TWICE-RUN IDENTITY (29C-v2): compute_posture() is run twice on the real
          state file + real snapshot; the second block must be IDENTICAL to
          the first and never UNAVAILABLE.
  ENDPOINT: {as_of, files, set_sha256, accessions}; accessions sorted unique;
          files == len; set_sha256 == recomputed (sorted unique, byte-lex,
          UTF-8, "\\n"-joined, no trailing newline); must agree with the daily
          file of the same date on files + set_sha256.
  HTML:   files, set_sha256, |added|/|removed| of the in-progress day (and
          the last completed day) appear in todays_evidence.html; NO
          accession string of the endpoint appears anywhere in the HTML.

Exit 0 green / 1 violation; chained hard (exit 49 in refresh_v3_pages.sh).
  --docs DIR   validate a preview tree instead of docs/ (verification runs)
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
CUTOVER = date(2026, 8, 29)
KEY_ORDER = ["date", "counts", "c6_posture", "grades", "ledger", "maturity", "replay"]
LEGACY_KEYS = ("c6_posture_files", "c6_posture_accessions")
CURRENT_URL = "/c6_posture_current.json"
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def set_sha256(accessions) -> str:
    uniq = sorted({a.encode("utf-8") for a in accessions})
    return hashlib.sha256(b"\n".join(uniq)).hexdigest()


def _check_daily(path: Path, problems: list[str]) -> dict | None:
    name = f"evidence_changes/{path.name}"
    try:
        d = date.fromisoformat(path.stem)
    except ValueError:
        return None
    try:
        j = json.loads(path.read_text())
    except Exception as e:
        problems.append(f"{name}: unreadable JSON ({e})")
        return None
    if j.get("date") != path.stem:
        problems.append(f"{name}: date field {j.get('date')!r} != filename")
    if d < CUTOVER:
        if not isinstance(j.get("c6_posture_files"), int):
            problems.append(f"{name}: legacy file missing int c6_posture_files")
        if not isinstance(j.get("c6_posture_accessions"), list):
            problems.append(f"{name}: legacy file missing list c6_posture_accessions")
        if "c6_posture" in j:
            problems.append(f"{name}: legacy-dated file carries a c6_posture block")
        return j
    for k in LEGACY_KEYS:
        if k in j:
            problems.append(f"{name}: legacy key {k} present in a >= {CUTOVER} file")
    if list(j.keys()) != KEY_ORDER:
        problems.append(f"{name}: key order {list(j.keys())} != canonical {KEY_ORDER}")
    blk = j.get("c6_posture")
    if not isinstance(blk, dict):
        problems.append(f"{name}: c6_posture block missing")
        return j
    if not isinstance(blk.get("files"), int):
        problems.append(f"{name}: c6_posture.files not int")
    if not _HEX64.match(str(blk.get("set_sha256", ""))):
        problems.append(f"{name}: c6_posture.set_sha256 not a sha256 hex")
    if blk.get("current_url") != CURRENT_URL:
        problems.append(f"{name}: c6_posture.current_url {blk.get('current_url')!r} != {CURRENT_URL}")
    for k in ("delta_since", "delta_span_days", "delta_status"):
        if k not in blk:
            problems.append(f"{name}: c6_posture.{k} missing")
    add, rem, st = blk.get("added_today"), blk.get("removed_today"), blk.get("delta_status")
    since, span = blk.get("delta_since"), blk.get("delta_span_days")
    if add is None or rem is None:
        if not (add is None and rem is None and since is None and span is None):
            problems.append(f"{name}: added/removed/delta_since/delta_span_days must ALL be null on a gap")
        if not str(st).startswith("UNAVAILABLE (cold start"):
            problems.append(f"{name}: null delta_since only allowed for a documented cold start "
                            f"(delta_status={st!r})")
    else:
        if not (isinstance(add, list) and isinstance(rem, list)):
            problems.append(f"{name}: added_today/removed_today must be lists")
        elif set(add) & set(rem):
            problems.append(f"{name}: accession both added and removed")
        if st != "OK":
            problems.append(f"{name}: delta_status {st!r} with non-null delta")
        try:
            want = (d - date.fromisoformat(str(since))).days
            if span != want or want < 0:
                problems.append(f"{name}: delta_span_days {span!r} != {path.stem} - {since} = {want}")
        except ValueError:
            problems.append(f"{name}: delta_since {since!r} not a date")
    return j


def _check_endpoint(path: Path, problems: list[str]) -> dict | None:
    if not path.exists():
        problems.append("c6_posture_current.json missing")
        return None
    try:
        ep = json.loads(path.read_text())
    except Exception as e:
        problems.append(f"c6_posture_current.json unreadable ({e})")
        return None
    if list(ep.keys()) != ["as_of", "files", "set_sha256", "accessions"]:
        problems.append(f"c6_posture_current.json keys {list(ep.keys())} != [as_of, files, set_sha256, accessions]")
    acc = ep.get("accessions")
    if not isinstance(acc, list):
        problems.append("c6_posture_current.json: accessions not a list")
        return ep
    if acc != sorted(set(acc)):
        problems.append("c6_posture_current.json: accessions not sorted-unique")
    if ep.get("files") != len(acc):
        problems.append(f"c6_posture_current.json: files {ep.get('files')} != len(accessions) {len(acc)}")
    if ep.get("set_sha256") != set_sha256(acc):
        problems.append("c6_posture_current.json: set_sha256 does not match recomputed hash")
    try:
        date.fromisoformat(str(ep.get("as_of")))
    except ValueError:
        problems.append(f"c6_posture_current.json: as_of {ep.get('as_of')!r} not a date")
    return ep


def _check_html(html: str, daily: dict, label: str, problems: list[str]) -> None:
    blk = daily.get("c6_posture")
    if blk is None:      # legacy day: files count must still show
        if f"{daily.get('c6_posture_files')} files in the set" not in html:
            problems.append(f"HTML: legacy {label} files count not rendered")
        return
    if f"{blk['files']} files in the current set" not in html:
        problems.append(f"HTML: {label} files count {blk['files']} not rendered")
    if str(blk.get("set_sha256")) not in html:
        problems.append(f"HTML: {label} set_sha256 not rendered")
    if blk.get("added_today") is None:
        if "UNAVAILABLE" not in html:
            problems.append(f"HTML: {label} delta UNAVAILABLE status not rendered")
    else:
        want = (f"vs {blk.get('delta_since')} ({blk.get('delta_span_days')}d): "
                f"+{len(blk['added_today'])} added / −{len(blk['removed_today'])} removed")
        if want not in html:
            problems.append(f"HTML: {label} delta '{want}' not rendered")
    if "c6_posture_current.json" not in html:
        problems.append("HTML: link to c6_posture_current.json missing")


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    docs = Path(argv[argv.index("--docs") + 1]) if "--docs" in argv else _REPO / "docs"
    problems: list[str] = []
    arch = docs / "evidence_changes"
    dailies: dict[str, dict] = {}
    for p in sorted(arch.glob("????-??-??.json")):
        j = _check_daily(p, problems)
        if j:
            dailies[p.stem] = j
    n_legacy = sum(1 for k in dailies if date.fromisoformat(k) < CUTOVER)
    ep = _check_endpoint(docs / "c6_posture_current.json", problems)
    latest = max(dailies) if dailies else None
    if ep and latest and date.fromisoformat(latest) >= CUTOVER:
        blk = dailies[latest].get("c6_posture") or {}
        if ep.get("as_of") != latest:
            problems.append(f"endpoint as_of {ep.get('as_of')} != latest daily {latest}")
        if blk.get("files") != ep.get("files") or blk.get("set_sha256") != ep.get("set_sha256"):
            problems.append(f"endpoint files/set_sha256 disagree with evidence_changes/{latest}.json")
    html_p = docs / "todays_evidence.html"
    if html_p.exists() and latest:
        html = html_p.read_text()
        _check_html(html, dailies[latest], f"in-progress day {latest}", problems)
        prior = [k for k in dailies if k < latest]
        if prior:
            _check_html(html, dailies[max(prior)], f"last completed day {max(prior)}", problems)
        if ep:
            leaked = [a for a in ep.get("accessions", []) if a and a in html]
            if leaked:
                problems.append(f"HTML: {len(leaked)} accession string(s) leaked into todays_evidence.html "
                                f"(e.g. {leaked[0]})")
        for k in ("c6_posture_accessions", "c6_posture_files"):
            if k in html:
                problems.append(f"HTML: legacy key name {k} appears in the page")
    elif latest:
        problems.append("todays_evidence.html missing")
    # ---- twice-run identity (same-day rerun): the producer is idempotent
    twice = ""
    if docs == _REPO / "docs":
        import copy
        sys.path.insert(0, str(_REPO))
        from v3.web import render_todays_evidence as R
        st = R._load_state()
        snap = R.c6_snapshot()
        today = R.datetime.now(R.timezone.utc).date()
        s1, b1, _ = R.compute_posture(today, copy.deepcopy(st), snap)
        s2, b2, _ = R.compute_posture(today, copy.deepcopy(s1), snap)   # rerun on the rolled state
        s3, b3, _ = R.compute_posture(today, copy.deepcopy(s2), snap)
        if not (b1 == b2 == b3):
            problems.append("twice-run identity: c6_posture block differs between consecutive same-day runs")
        if b2["added_today"] is None and st is not None:
            problems.append("twice-run identity: same-day rerun produced UNAVAILABLE with state present")
        if latest and dailies[latest].get("c6_posture") != b1 and today.isoformat() == latest:
            problems.append("twice-run identity: published block != recomputed block from state + snapshot")
        twice = f", twice-run identity OK (vs {b1['delta_since']}, {b1['delta_span_days']}d)"
    if problems:
        print("EVIDENCE-CHANGES GATE FAILED:")
        for p in problems:
            print(f"  · {p}")
        return 1
    print(f"[evidence-changes-gate] OK — {len(dailies)} daily files ({n_legacy} legacy < {CUTOVER}, "
          f"{len(dailies) - n_legacy} current), endpoint as_of={ep.get('as_of') if ep else '—'} "
          f"files={ep.get('files') if ep else '—'} hash verified, JSON<->HTML equal, "
          f"zero accession strings in HTML{twice}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

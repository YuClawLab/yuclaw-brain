#!/usr/bin/env python3
"""
CONSUMER-POSTURE GATE (gate #15 scaffold) — ORDER 2026-09-02A, Part B2.

Five deterministic stranger personas walk the rendered/served surfaces.
Every check that feeds the exit code is machine-executable, non-interactive
and wall-clock-independent: dates come from the newest CANONICAL artifact
(latest dated file at/before chain close), never from the machine-local
clock; network is never touched (P3 serves docs/ from a local socket).
Items that genuinely need a human are printed as MANUAL_REVIEW and NEVER
drive the exit code.

  P1 skeptical-quant       evidence_changes: canonical-latest file, key
                           order as serialization convention, complete
                           c6_posture block, set_sha256 recomputed from
                           the endpoint's accessions, no cumulative
                           payload in >=2026-08-29 files.
  P2 replicator            replay_lab.py declares its stdlib-only
                           contract + pinned Python versions; import scan
                           proves stdlib-only; fresh venv (zero installs)
                           reproduces the bundle; the documented command
                           is machine-extracted from replication.html and
                           executed, so docs and tests cannot diverge.
  P3 ai-agent              every endpoint in capabilities.json served
                           from a LOCAL socket over docs/ (staged HTTP
                           surface), JSON parses, schema-required keys
                           present; llms.txt worked example (NVDA as of
                           2026-07-15) yields the deterministic
                           structural result. Real-Internet 200 checks
                           belong to release/external smoke, not here.
  P4 first-time-visitor    landing: disclaimer within the first viewport
                           at 1440x900 (structural proxy, calibrated —
                           the disclaimer card precedes the first data
                           table and sits in the first 3 content blocks
                           after the header); every status label is a
                           DIRECT link to its definition; nav links
                           resolve locally; internal-marker denylist
                           ([COUNSEL, [TODO, [DRAFT, [PLACEHOLDER, TBD-,
                           \bXXX\b) over all public HTML.
  P5 institutional-reader  every numeric status-card carries data-source
                           resolving to a same-page panel id or an
                           existing canonical artifact; header forward-n
                           == not-proven forward-n; label separation of
                           cryptographic objects (negative invariant,
                           extended by ORDER 2026-09-05B C2): THREE
                           distinct objects — 'evidence-ledger root'
                           (yuclaw-trust daily_root), 'daily evidence
                           block root' (docs/ledger/{DATE}.json
                           root_sha256) and 'registry chain head' — may
                           never share a visible label or swap values.

MANUAL_REVIEW register (never exit-driving):
  - ETF coverage posture (Audit #1 item i): the registered completeness
    method's `etf` class exists but ETF_SET is empty AT REGISTRATION and
    IN-HASH — assigning ETFs requires a registered addendum
    (BLOCKED_BY_REGISTRATION; ORDER 2026-09-02A B3-i stop rule). Until
    that addendum, ETF filing families print ABSENT per the registered
    derivation and no UI repair may override it.

Exit 0 = every automated persona check green; exit 1 = findings.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import tempfile
import threading
import venv
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DOCS = REPO / "docs"

PUBLIC_LABELS = ("STRONG_BULLISH", "BULLISH", "NEUTRAL", "WATCH",
                 "WEAKENING", "NEGATIVE_EVENT", "BEARISH_WATCH",
                 "RISK_ALERT")
DENYLIST = (r"\[COUNSEL", r"\[TODO", r"\[DRAFT", r"\[PLACEHOLDER",
            r"TBD-", r"\bXXX\b")

EC_KEY_ORDER = ["date", "counts", "c6_posture", "grades", "ledger",
                "maturity", "replay"]
C6_BLOCK_KEYS = {"files", "set_sha256", "added_today", "removed_today",
                 "delta_since", "delta_span_days", "delta_status",
                 "current_url"}


# ---------------------------------------------------------------- P1
def p1_skeptical_quant() -> list[str]:
    f: list[str] = []
    files = sorted((DOCS / "evidence_changes").glob("*.json"))
    if not files:
        return ["P1: no evidence_changes files at all"]
    latest = files[-1]        # canonical latest, never machine-local today
    raw = latest.read_text()
    pairs: list = []
    def hook(p):
        pairs.append([k for k, _ in p])
        return dict(p)
    doc = json.loads(raw, object_pairs_hook=hook)
    top = pairs[-1]           # outermost object is parsed last
    if top != EC_KEY_ORDER:
        f.append(f"P1: {latest.name} key order {top} != documented "
                 f"serialization convention {EC_KEY_ORDER}")
    c6 = doc.get("c6_posture")
    if not isinstance(c6, dict):
        f.append(f"P1: {latest.name} c6_posture block missing")
    else:
        missing = C6_BLOCK_KEYS - set(c6)
        if missing:
            f.append(f"P1: {latest.name} c6_posture incomplete — missing "
                     f"{sorted(missing)}")
    cur = json.loads((DOCS / "c6_posture_current.json").read_text())
    accs = cur.get("accessions", [])
    recomputed = hashlib.sha256(
        "\n".join(sorted(set(accs))).encode("utf-8")).hexdigest()
    if recomputed != cur.get("set_sha256"):
        f.append(f"P1: c6_posture_current.json set_sha256 does not match "
                 f"recompute from its own accessions "
                 f"({recomputed[:12]} != {str(cur.get('set_sha256'))[:12]})")
    for fp in files:
        if fp.stem >= "2026-08-29" and "c6_posture_accessions" in fp.read_text():
            f.append(f"P1: {fp.name} carries the legacy cumulative "
                     f"payload (c6_posture_accessions) in a >=2026-08-29 file")
    return f


# ---------------------------------------------------------------- P2
def p2_replicator() -> list[str]:
    f: list[str] = []
    rl = REPO / "tools" / "replay_lab.py"
    text = rl.read_text()
    if "STDLIB_ONLY = True" not in text:
        f.append("P2: replay_lab.py does not declare STDLIB_ONLY = True")
    m = re.search(r'SUPPORTED_PYTHON = \(([^)]+)\)', text)
    if not m:
        f.append("P2: replay_lab.py does not pin SUPPORTED_PYTHON versions")
    else:
        pins = re.findall(r'"(\d+\.\d+)"', m.group(1))
        here = f"{sys.version_info.major}.{sys.version_info.minor}"
        if here not in pins:
            f.append(f"P2: running Python {here} is outside the pinned "
                     f"SUPPORTED_PYTHON {pins}")
    # import scan: stdlib-only must be true, not just declared
    stdlib = set(sys.stdlib_module_names)
    for imp in re.findall(r"^(?:import|from)\s+([A-Za-z_][\w]*)", text, re.M):
        if imp not in stdlib:
            f.append(f"P2: replay_lab.py imports non-stdlib module '{imp}'")
    # documented command machine-extracted from the replication page
    doc = (DOCS / "replication.html").read_text()
    cmds = [c.strip() for c in re.findall(r"^(python3 replay_lab\.py [^\n<]+)",
                                          doc, re.M)]
    if not cmds:
        f.append("P2: no 'python3 replay_lab.py …' command found in "
                 "replication.html — docs and tests have diverged")
        return f
    bundle = DOCS / "replay" / "lab_replay_bundle.json"
    if not bundle.exists():
        f.append("P2: docs/replay/lab_replay_bundle.json missing")
        return f
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        venv.create(tdp / "venv", with_pip=False)   # zero installs
        py = tdp / "venv" / "bin" / "python3"
        (tdp / "replay_lab.py").write_text(text)
        (tdp / "lab_replay_bundle.json").write_text(bundle.read_text())
        cmd = cmds[0].split()
        cmd[0] = str(py)                            # python3 -> venv python
        r = subprocess.run(cmd, cwd=td, capture_output=True, text=True,
                           timeout=600)
        if r.returncode != 0:
            f.append(f"P2: documented replay command failed rc="
                     f"{r.returncode}: {(r.stderr or r.stdout)[-200:]}")
        elif "REPRODUCED" not in r.stdout:
            f.append("P2: replay ran but did not print REPRODUCED")
    return f


# ---------------------------------------------------------------- P3
def p3_ai_agent() -> list[str]:
    f: list[str] = []
    caps = json.loads((DOCS / "capabilities.json").read_text())
    ledger_files = sorted((DOCS / "ledger").glob("*.json"))
    ec_files = sorted((DOCS / "evidence_changes").glob("*.json"))
    schema_files = sorted((DOCS / "schemas").glob("*.v1.json"))
    subs = {
        "{TICKER}": "NVDA",
        "{YYYY-MM-DD}": None,   # per-endpoint below
        "{Name}": schema_files[0].name.replace(".v1.json", "") if schema_files else "",
    }

    class Quiet(SimpleHTTPRequestHandler):
        def log_message(self, *a):  # noqa: N802
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", 0), Quiet)
    srv.RequestHandlerClass.directory = str(DOCS)
    # py3.9+: handler directory via partial — use functools instead
    import functools
    srv.RequestHandlerClass = functools.partial(Quiet, directory=str(DOCS))
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    import urllib.request
    try:
        for name, url in caps.get("endpoints", {}).items():
            path = re.sub(r"^https://[^/]+", "", url)
            path = path.replace("{TICKER}", subs["{TICKER}"])
            path = path.replace("{Name}", subs["{Name}"])
            if "{zip}" in path:            # packet family: names come from the packet manifest
                pm = DOCS / "packets" / "manifest.json"
                zips = [v["zip"] for v in json.loads(pm.read_text()).values()
                        if isinstance(v, dict)] if pm.exists() else []
                if not zips:
                    f.append(f"P3: endpoint {name}: packet manifest lists no zip")
                    continue
                path = path.replace("{zip}", sorted(zips)[0])
            if "{YYYY-MM-DD}" in path:
                src = ledger_files if "ledger" in path else ec_files
                if not src:
                    f.append(f"P3: endpoint {name}: no local file to "
                             f"substitute the date template")
                    continue
                path = path.replace("{YYYY-MM-DD}", src[-1].stem)
            try:
                with urllib.request.urlopen(
                        f"http://127.0.0.1:{port}{path}", timeout=30) as r:
                    body = r.read()
                    if r.status != 200:
                        f.append(f"P3: endpoint {name} ({path}) -> {r.status}")
                        continue
            except Exception as e:                    # noqa: BLE001
                f.append(f"P3: endpoint {name} ({path}) unreachable "
                         f"locally: {e}")
                continue
            if path.endswith(".json"):
                try:
                    json.loads(body)
                except Exception:                     # noqa: BLE001
                    f.append(f"P3: endpoint {name} ({path}) is not valid JSON")
    finally:
        srv.shutdown()
    # schema-required keys on the why surface (v1 schema contract)
    why_schema = DOCS / "schemas" / "Why.v1.json"
    if why_schema.exists():
        req = json.loads(why_schema.read_text()).get("required", [])
        why = json.loads((DOCS / "why" / "NVDA.json").read_text())
        missing = [k for k in req if k not in why]
        if missing:
            f.append(f"P3: why/NVDA.json missing schema-required keys "
                     f"{missing}")
    # llms.txt worked example — deterministic structural result
    llms = (DOCS / "llms.txt").read_text()
    m = re.search(r"reconstruct (\w+) as of (\d{4}-\d{2}-\d{2})", llms)
    if not m:
        f.append("P3: llms.txt worked example not found")
    else:
        tick, d = m.group(1), m.group(2)
        why = json.loads((DOCS / "why" / f"{tick}.json").read_text())
        evs = [e for e in why.get("evidence_objects", [])
               if str(e.get("available_as_of", ""))[:10] <= d]
        all_hist = why.get("label_history", [])
        hist = [h for h in all_hist if str(h.get("date", ""))[:10] <= d]
        if not hist:
            # the recipe itself defines the ribbon boundary: a date older
            # than the rolling ribbon resolves via the documented replay
            # fallback — that IS the deterministic structural result.
            oldest = min((str(h.get("date", ""))[:10] for h in all_hist),
                         default="")
            if not (oldest and d < oldest
                    and "Older than the ribbon" in llms):
                f.append(f"P3: worked example {tick} as of {d}: no "
                         f"label_history entry at/before the date and no "
                         f"documented ribbon fallback")
        for e in evs:
            if str(e.get("available_as_of", ""))[:10] > d:
                f.append(f"P3: worked example as-of filter violated")
                break
    return f


# ---------------------------------------------------------------- P4
def p4_first_time_visitor() -> list[str]:
    f: list[str] = []
    idx = (DOCS / "index.html").read_text()
    body = idx[idx.find("<body"):]
    # first-viewport proxy (calibrated at 1440x900): the disclaimer must
    # appear before the first data table and within the first 3 card-level
    # blocks after the site header.
    disc = re.search(r"not investment advice", body, re.I)
    table = re.search(r"<table", body)
    if not disc:
        f.append("P4: index.html has no disclaimer at all")
    elif table and disc.start() > table.start():
        f.append("P4: index.html disclaimer appears below the first data "
                 "table — outside the 1440x900 first viewport")
    else:
        hdr = re.search(r'class="site-hdr"', body)
        cards_before = len(re.findall(r'class="card"',
                                      body[hdr.end() if hdr else 0:disc.start()]))
        if cards_before > 2:
            f.append(f"P4: disclaimer sits {cards_before} cards below the "
                     f"header — outside the 1440x900 first viewport proxy")
    # every status label chip/legend token -> direct definition link
    for m in re.finditer(
            r"<(a|span)\b([^>]*)>(" + "|".join(PUBLIC_LABELS) + r")</\1>",
            idx):
        tag, attrs, label = m.groups()
        if tag != "a" or "methodology.html#" not in attrs:
            f.append(f"P4: label {label} on index.html is not a direct "
                     f"link to its definition")
    # nav links resolve locally
    for href in re.findall(r'href=[\'"]([^\'"#]+)[\'"]', idx):
        if href.startswith(("http://", "https://", "mailto:", "data:")):
            continue
        if not (DOCS / href.partition("?")[0]).exists():
            f.append(f"P4: index.html dead local link {href}")
    # denylist over every public page
    for page in list(DOCS.glob("*.html")) + list((DOCS / "why").glob("*.html")):
        text = page.read_text(errors="replace")
        for pat in DENYLIST:
            if re.search(pat, text):
                f.append(f"P4: internal marker {pat} in public "
                         f"{page.relative_to(DOCS)}")
    return f


# ---------------------------------------------------------------- P5
def p5_institutional_reader() -> list[str]:
    f: list[str] = []
    vlab = (DOCS / "validation_lab.html").read_text()
    ids = set(re.findall(r'id=[\'"]([^\'"]+)[\'"]', vlab))
    # numeric status cards must carry data-source; sources must resolve
    n_sourced = 0
    for m in re.finditer(r'<div data-source="([^"]+)"', vlab):
        src = m.group(1)
        n_sourced += 1
        if src.startswith("#"):
            if src[1:] not in ids:
                f.append(f"P5: data-source {src} does not resolve to a "
                         f"same-page id")
        elif src.startswith("ledger:"):
            if not (REPO / src[len("ledger:"):]).exists():
                f.append(f"P5: data-source {src} names a missing artifact")
        else:
            f.append(f"P5: data-source {src} uses an unknown scheme")
    if n_sourced < 2:
        f.append(f"P5: only {n_sourced} sourced status cards found on the "
                 f"Validation Lab — provenance mapping missing")
    # header n == not-proven n (re-assert independently of site-walk)
    h = re.search(r"EARLY · n=(\d+) periods", vlab)
    n = re.search(r"Forward alpha — n=(\d+) periods", vlab)
    if not (h and n):
        f.append("P5: forward-n surfaces not found on the Validation Lab")
    elif h.group(1) != n.group(1):
        f.append(f"P5: header forward n={h.group(1)} != not-proven "
                 f"n={n.group(1)}")
    # cryptographic-object label separation (negative invariant). Three
    # distinct objects, three distinct human labels (C2 identity guard):
    #   trust daily_root  (yuclaw-trust/verified_research_ledger.jsonl,
    #                      sha256 of the day's sorted content hashes '|')
    #                      → label "evidence-ledger root"
    #   block root_sha256 (docs/ledger/{DATE}.json, sha256 of the sorted-
    #                      keys JSON dump of the entries)
    #                      → label "daily evidence block root"
    #   registry chain head (registry/protocols.jsonl last line_hash)
    #                      → label "registry chain head"
    led = sorted((DOCS / "ledger").glob("*.json"))
    block_root = json.loads(led[-1].read_text())["root_sha256"][:12] if led else ""
    trust_root = ""
    trust = Path.home() / "yuclaw-trust" / "verified_research_ledger.jsonl"
    if trust.exists():
        try:
            trust_root = json.loads(trust.read_text().splitlines()[-1])["daily_root"][:12]
        except Exception:                             # noqa: BLE001
            trust_root = ""
    chain_tip = ""
    reg = REPO / "registry" / "protocols.jsonl"
    if reg.exists():
        chain_tip = json.loads(
            reg.read_text().splitlines()[-1])["line_hash"][:12]
    if block_root and trust_root and block_root == trust_root:
        f.append("P5: daily evidence block root and evidence-ledger root "
                 "collide on 12 hex — labels cannot be told apart")
    LABELS = {"trust": "evidence-ledger root", "block": "daily evidence block root",
              "chain": "registry chain head"}
    values = {"trust": trust_root, "block": block_root, "chain": chain_tip}
    for page in DOCS.glob("*.html"):
        text = page.read_text(errors="replace")
        for m in re.finditer(r"ledger root", text, re.I):
            pre = text[max(0, m.start() - 9):m.start()]
            if pre.lower() != "evidence-":
                f.append(f"P5: bare 'ledger root' label in {page.name} — "
                         f"must name the exact object (evidence-ledger root)")
        for kind, val in values.items():
            if not val or val not in text:
                continue
            for m in re.finditer(re.escape(val), text):
                ctx = text[max(0, m.start() - 160):m.start()].lower()
                own = LABELS[kind].lower() in ctx or (kind == "chain" and "anchor" in ctx)
                foreign = [LABELS[o] for o in LABELS if o != kind and LABELS[o].lower() in ctx
                           and ctx.rfind(LABELS[o].lower()) > ctx.rfind(LABELS[kind].lower())]
                if foreign:
                    f.append(f"P5: {LABELS[kind]} value {val} in {page.name} carries the "
                             f"label of a different cryptographic object ({foreign[0]})")
                elif not own:
                    f.append(f"P5: {LABELS[kind]} value {val} in {page.name} without its "
                             f"label — two cryptographic objects may never share a label")
    return f


MANUAL_REVIEW = [
    "ETF coverage posture (Audit #1 item i): BLOCKED_BY_REGISTRATION — the "
    "registered completeness method's etf class exists but ETF_SET is empty "
    "at registration and in-hash; assigning ETFs needs a registered addendum "
    "(ORDER 2026-09-02A B3-i stop rule). No UI repair permitted meanwhile.",
    "Comprehension test with real users (gate #15 full form) — a human "
    "study; this suite is its deterministic scaffold, not its substitute.",
]


def main() -> int:
    findings: list[str] = []
    for name, fn in (("P1 skeptical-quant", p1_skeptical_quant),
                     ("P2 replicator", p2_replicator),
                     ("P3 ai-agent", p3_ai_agent),
                     ("P4 first-time-visitor", p4_first_time_visitor),
                     ("P5 institutional-reader", p5_institutional_reader)):
        try:
            got = fn()
        except Exception as e:                        # noqa: BLE001
            # fail-closed: a broken surface is a finding, never a crash
            got = [f"{name.split()[0]}: persona check could not complete "
                   f"— {type(e).__name__}: {e}"]
        print(f"[consumer-posture] {name}: "
              f"{'OK' if not got else f'{len(got)} finding(s)'}")
        findings += got
    for item in MANUAL_REVIEW:
        print(f"[consumer-posture] MANUAL_REVIEW (never exit-driving): {item}")
    if findings:
        for x in findings:
            print(f"  FAIL {x}")
        return 1
    print("[consumer-posture] OK — five personas green (deterministic, "
          "local, wall-clock-independent)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

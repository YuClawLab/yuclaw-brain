#!/usr/bin/env python3
"""
SCIENCE TRUST GATE — release gate #11 (order 2026-08-14, Part B-1 + A-7).
===========================================================================
Verifies the STAGED Science Trust surfaces (docs/preview/ only):

  G11-EQUALITY        machine JSON == human card canonical block ==
                      fresh re-derivation, field-for-field, every name.
                      No hand-maintained duplicates, no second
                      derivation path.
  G11-PROVENANCE      research_state on every surface equals
                      registry/research_state.json DIRECTLY (a forced /
                      manual research state is refused); the sequential-
                      evidence panel equals an INDEPENDENT re-derivation
                      from the canonical Anytime artifact + observation
                      chain (a hardcoded sequential state is refused).
  G11-VISIBILITY      absence states (PENDING / UNKNOWN / NOT_APPLICABLE
                      / NOT_ESTIMABLE / NOT_IDENTIFIABLE /
                      INSUFFICIENT_EVIDENCE) present in the canonical
                      fields MUST appear in the card's visible HTML —
                      hiding, zeroing, or collapsing them fails.
  G11-ANNOTATION      every field annotation is one of FACT /
                      DERIVED_RESULT / LIMITATION / PENDING /
                      NOT_ESTIMABLE / NOT_IDENTIFIABLE.
  G11-BYTE-REPRO      write_all() into a scratch directory reproduces
                      every staged file byte-for-byte (same artifacts +
                      same renderer version => byte-identical output).
  G11-MIRROR          why/{T}.json preview mirrors = live why JSON +
                      the derived science_trust block and nothing else;
                      LIVE why JSON untouched by construction.
  G11-ISOLATION       no live docs/*.html links into docs/preview/.

Fail-closed: missing files, unparseable JSON, or a missing canonical
block are failures, not skips.
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
for p in (str(_REPO), str(_REPO / "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

from yuclaw_science_trust_cards import (  # noqa: E402
    ABSENCE_STATES, ANNOTATIONS, derive_all, write_all)
from yuclaw_anytime_observer import load_enrollments, load_obs_chain, \
    _state as _anytime_state  # noqa: E402

TRUST = _REPO / "docs" / "preview" / "trust"
WHY_PREV = _REPO / "docs" / "preview" / "why"
WHY_LIVE = _REPO / "docs" / "why"


def _canonical_block(html_text: str, path: Path) -> dict:
    m = re.search(r'<script type="application/json" id="st-canonical">\n'
                  r'(.*?)\n</script>', html_text, re.S)
    if not m:
        raise ValueError(f"{path.name}: canonical block missing")
    return json.loads(m.group(1))


def _visible_text(html_text: str) -> str:
    """Card text as a stranger sees it: canonical data block removed,
    tags stripped, hidden-by-style content refused separately."""
    no_script = re.sub(r"<script.*?</script>", "", html_text, flags=re.S)
    return re.sub(r"<[^>]+>", " ", no_script)


def _absence_tokens(fields: dict) -> set:
    toks = set()

    def _scan(v):
        if isinstance(v, str) and v.upper() in ABSENCE_STATES:
            toks.add(v.upper())
        elif isinstance(v, dict):
            for x in v.values():
                _scan(x)
        elif isinstance(v, list):
            for x in v:
                _scan(x)
    for f in fields.values():
        _scan(f["value"])
        if f["annotation"] in ABSENCE_STATES:
            toks.add(f["annotation"])
    return toks


def main() -> int:
    problems: list[str] = []
    derived = derive_all()
    rs_direct = json.loads(
        (_REPO / "registry" / "research_state.json").read_text())["names"]

    # independent sequential re-derivation (NOT via the renderer module's
    # derive_platform) — canonical Anytime artifact + observation chain
    enrollments = load_enrollments()
    obs = load_obs_chain(enrollments=enrollments)
    indep_seq = {e["enrollment_id"]: {"observations": obs[e["enrollment_id"]]["t"],
                                      "state": _anytime_state(e, obs[e["enrollment_id"]])}
                 for e in enrollments}

    n_cards = 0
    for name, fields in sorted(derived["names"].items()):
        jpath, hpath = TRUST / f"{name}.json", TRUST / f"{name}.html"
        if not jpath.exists() or not hpath.exists():
            problems.append(f"G11-EQUALITY {name}: staged surface missing "
                            f"({jpath.name if not jpath.exists() else hpath.name})")
            continue
        machine = json.loads(jpath.read_text())
        html_text = hpath.read_text()
        card = _canonical_block(html_text, hpath)

        if machine["science_trust"] != fields:
            problems.append(f"G11-EQUALITY {name}: machine JSON diverges "
                            f"from fresh derivation")
        if card["science_trust"] != fields:
            problems.append(f"G11-EQUALITY {name}: human card canonical "
                            f"block diverges from fresh derivation")
        if machine["science_trust"] != card["science_trust"]:
            problems.append(f"G11-EQUALITY {name}: machine JSON != human "
                            f"card (field-for-field)")

        # provenance: forced research state refused
        for surface, blob in (("machine", machine), ("card", card)):
            got = blob["science_trust"]["research_state"]["value"]
            want = rs_direct[name]["research_state"]
            if got != want:
                problems.append(
                    f"G11-PROVENANCE {name}: {surface} research_state "
                    f"{got!r} != Research-State Derivation v1 value "
                    f"{want!r} — forced/manual research states are "
                    f"refused")

        # provenance: hardcoded sequential state refused
        for s in machine["platform"]["sequential_evidence"]:
            ind = indep_seq.get(s["enrollment_id"])
            if ind is None or s["observations"] != ind["observations"] \
                    or s["sequential_state"] != ind["state"]:
                problems.append(
                    f"G11-PROVENANCE {name}: sequential panel "
                    f"{s['enrollment_id']} ({s['sequential_state']}, "
                    f"t={s['observations']}) != independent re-derivation "
                    f"from the canonical Anytime artifact "
                    f"({ind and ind['state']}, t={ind and ind['observations']}) "
                    f"— hardcoded sequential states are refused")

        # annotation vocabulary
        for k, f in machine["science_trust"].items():
            if f["annotation"] not in ANNOTATIONS:
                problems.append(f"G11-ANNOTATION {name}.{k}: "
                                f"{f['annotation']!r} outside the locked "
                                f"vocabulary")

        # absence-state visibility in the human card: canonical
        # field-level absence states must be visible in the MAIN CARD
        # region (not tucked behind a tab); platform-detail absence
        # states may live on drill-down tabs, which are click-reachable.
        m = re.search(r"<div class=['\"]card['\"]>(.*?)<div class=['\"]tabs",
                      html_text, re.S)
        main_region = _visible_text(m.group(1)) if m else ""
        if not m:
            problems.append(f"G11-VISIBILITY {name}: main card region "
                            f"not found")
        # structural: every canonical field must keep its row on the
        # main card — suppressing a field (PENDING included) is
        # refused regardless of token coincidences in prose
        raw_main = m.group(1) if m else ""
        for key in fields:
            if f"data-field='{key}'" not in raw_main:
                problems.append(
                    f"G11-VISIBILITY {name}: canonical field '{key}' "
                    f"has no row on the main card — suppressing a "
                    f"field (including PENDING/absence fields) is "
                    f"refused")
        for tok in sorted(_absence_tokens(fields)):
            if tok not in main_region:
                problems.append(
                    f"G11-VISIBILITY {name}: absence state {tok} present "
                    f"in canonical fields but not visible on the main "
                    f"card — absence is information and is never hidden")
        # no hiding mechanism at all: the drill-downs are native
        # <details> disclosures; display:none anywhere is refused
        if "display:none" in html_text.replace(" ", ""):
            problems.append(f"G11-VISIBILITY {name}: display:none "
                            f"on a card surface — hiding is refused")
        n_cards += 1

    # why-mirror integrity
    n_mirrors = 0
    for wf in sorted(WHY_PREV.glob("*.json")):
        t = wf.stem
        mirror = json.loads(wf.read_text())
        live = json.loads((WHY_LIVE / f"{t}.json").read_text())
        if mirror.get("science_trust") != derived["names"].get(t):
            problems.append(f"G11-MIRROR {t}: science_trust block "
                            f"diverges from fresh derivation")
        stripped = {k: v for k, v in mirror.items()
                    if k not in ("science_trust", "science_trust_meta")}
        if stripped != live:
            problems.append(f"G11-MIRROR {t}: mirror alters live why "
                            f"fields (mirrors add the staged block and "
                            f"nothing else)")
        n_mirrors += 1

    # byte-reproducibility
    with tempfile.TemporaryDirectory() as td:
        write_all(base=Path(td))
        scratch = Path(td)
        pairs = [(scratch / "trust" / p.name, p)
                 for p in sorted(TRUST.glob("*"))]
        pairs += [(scratch / "why" / p.name, p)
                  for p in sorted(WHY_PREV.glob("*"))]
        pairs += [(scratch / f, _REPO / "docs" / "preview" / f)
                  for f in ("capabilities.vnext.json",
                            "evidencebench_context.json",
                            "canada_trust_includes.html",
                            "lens_trust_includes.html")]
        for fresh, committed in pairs:
            if not fresh.exists():
                problems.append(f"G11-BYTE-REPRO: {committed.name} not "
                                f"reproduced by write_all()")
            elif fresh.read_bytes() != committed.read_bytes():
                problems.append(f"G11-BYTE-REPRO: {committed.relative_to(_REPO)} "
                                f"differs from a fresh rebuild — staged "
                                f"surfaces are derived, never edited")

    # preview isolation (live pages never link into preview/)
    for page in sorted((_REPO / "docs").glob("*.html")):
        if "preview/" in page.read_text():
            problems.append(f"G11-ISOLATION: {page.name} links into "
                            f"docs/preview/ — previews are unlinked by "
                            f"design")

    if problems:
        for p in problems:
            print(f"[science-trust-gate] FAIL — {p}")
        print(f"[science-trust-gate] {len(problems)} problem(s)")
        return 1
    print(f"[science-trust-gate] OK — {n_cards} cards: machine JSON == "
          f"human card == fresh derivation (field-for-field); research "
          f"states verified against research_state.json directly; "
          f"sequential panel verified against the canonical Anytime "
          f"artifact independently; absence states visible; "
          f"{n_mirrors} why mirrors add the staged block and nothing "
          f"else; byte-reproducible; preview isolation holds")
    return 0


if __name__ == "__main__":
    sys.exit(main())

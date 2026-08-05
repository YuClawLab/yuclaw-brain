"""
yuclaw check-claim — the Evidence Passport: a DETERMINISTIC claim-checker
against YUCLAW's evidence corpus. Statuses are the mechanical five:

  SOURCE_MATCHED   every structured element of the claim matched at
                   least one EvidenceObject (type, ticker, window, and —
                   when given — accession)
  PARTIAL_MATCH    some elements matched; the misses are listed
  UNSUPPORTED      nothing matched — "not found in YUCLAW's corpus —
                   never a truth verdict"
  NOT_IN_COVERAGE  the ticker is outside the 79-name scoring universe
  NOT_PARSEABLE    a --text claim the parser cannot confidently
                   structure (the false-denial guard: an unparsed claim
                   is never called unsupported)

Structured mode is exact: --ticker X --type T --date-range A..B
[--accession N]. Text mode (--text "...") is CONSERVATIVE keyword/type
matching — it only structures a claim when it finds an unambiguous
ticker plus either a known event-type keyword or an accession number;
anything less is NOT_PARSEABLE. Limits: no numeric-magnitude checking,
no negation handling, no multi-claim sentences.

Deterministic: same corpus + same claim → byte-identical passport
(modulo the generated timestamp). Not advice, ever.

Corpus resolution (v5.3.2): a research node (the events DB) when
reachable — behavior unchanged on-box; otherwise the bundled published
snapshot (v3/evidence/corpus_snapshot.json.gz — the same
evidence_objects served at https://yuclaw.ca/why/{TICKER}.json), with
the passport carrying an explicit "corpus" scope block. Only when
neither exists: friendly exit 3 pointing at the public JSON.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone

STATUSES = ("SOURCE_MATCHED", "PARTIAL_MATCH", "UNSUPPORTED",
            "NOT_IN_COVERAGE", "NOT_PARSEABLE")
NOT_ADVICE = ("Research and education only — not investment advice. "
              "A passport describes what YUCLAW's corpus contains; "
              "UNSUPPORTED means 'not found in YUCLAW's corpus — never "
              "a truth verdict'.")

TYPE_KEYWORDS = {
    "INSIDER_SELL": ("insider sale", "insider sell", "sold shares",
                     "form 4 sale"),
    "INSIDER_BUY": ("insider purchase", "insider buy", "bought shares"),
    "DIVIDEND_CHANGE": ("dividend",),
    "GUIDANCE_RAISE": ("raised guidance", "guidance raise"),
    "GUIDANCE_CUT": ("cut guidance", "guidance cut", "lowered guidance"),
    "M_AND_A_ANNOUNCE": ("acquisition announced", "merger announced",
                         "agreed to acquire"),
    "M_AND_A_CLOSE": ("acquisition closed", "merger closed",
                      "completed the acquisition"),
    "BUYBACK_ANNOUNCE": ("buyback", "share repurchase"),
    "EARNINGS_BEAT": ("earnings beat", "beat estimates"),
    "EARNINGS_MISS": ("earnings miss", "missed estimates"),
}
_ACC_TEXT_RE = re.compile(r"\b(\d{10})-?(\d{2})-?(\d{6})\b")
# the locked extraction taxonomy — validation surface for --type
VALID_TYPES = ("BUYBACK_ANNOUNCE", "CAPACITY_CHANGE", "CONTRACT_WIN",
               "DIVIDEND_CHANGE", "EARNINGS_BEAT", "EARNINGS_MISS",
               "EXEC_CHANGE", "GUIDANCE_CUT", "GUIDANCE_RAISE",
               "INSIDER_BUY", "INSIDER_SELL", "M_AND_A_ANNOUNCE",
               "M_AND_A_CLOSE", "OTHER_MATERIAL", "PARTNERSHIP",
               "REGULATORY_ACTION")
_TICKER_RE = re.compile(r"\b([A-Z]{1,5}(?:\.[A-Z])?)\b")


class CorpusUnavailable(Exception):
    """No research node AND no bundled snapshot — the caller prints the
    friendly public-JSON pointer and exits 3."""

    def __init__(self, ticker: str):
        self.ticker = ticker
        super().__init__(ticker)


def _corpus(ticker: str) -> tuple[list, dict | None]:
    """(evidence objects, corpus scope block). Research node first —
    on-box behavior unchanged (scope block None → field omitted, passport
    byte-identical to v5.3.1). Off-box: the bundled published snapshot,
    loudly scoped. Neither → CorpusUnavailable."""
    from v3.evidence import BackendUnavailable, evidence_objects
    try:
        return evidence_objects(ticker, limit=500), None
    except BackendUnavailable:
        from v3.evidence.snapshot import load_snapshot
        snap = load_snapshot()
        if snap is None:
            raise CorpusUnavailable(ticker) from None
        url = f"https://yuclaw.ca/why/{ticker}.json"
        return snap["names"].get(ticker, []), {
            "mode": "offline_snapshot",
            "snapshot_generated": snap.get("generated"),
            "scope": (f"published corpus snapshot bundled with this "
                      f"install — the same evidence_objects served at "
                      f"{url}, up to {snap.get('per_name_cap')} "
                      f"most-recent objects per name"),
            "confirm": (f"negative statuses here mean 'not found in the "
                        f"bundled snapshot' — confirm against {url} or a "
                        f"research node"),
        }


def _parse_text(text: str, universe: set) -> dict | None:
    """Conservative: unambiguous ticker + (type keyword | accession),
    else None → NOT_PARSEABLE."""
    tickers = sorted({m for m in _TICKER_RE.findall(text)
                      if m in universe})
    acc = _ACC_TEXT_RE.search(text)
    low = text.lower()
    types = sorted({t for t, kws in TYPE_KEYWORDS.items()
                    if any(k in low for k in kws)})
    if len(tickers) != 1:
        return None
    if not types and not acc:
        return None
    if len(types) > 1:
        return None
    return {"ticker": tickers[0],
            "type": types[0] if types else None,
            "accession": "-".join(acc.groups()) if acc else None,
            "date_range": None}


def _match(claim: dict, objs: list) -> tuple[str, list, list]:
    lo, hi = claim.get("date_range") or (None, None)
    misses = []
    pool = objs
    if claim.get("type"):
        typed = [o for o in pool if o["evidence_type"] == claim["type"]]
        if not typed:
            misses.append(f"no {claim['type']} object")
        pool = typed or pool if False else typed
    if claim.get("accession"):
        acc = [o for o in pool if o["accession_number"] == claim["accession"]]
        if not acc:
            # an accession is the citation's identity: if the cited
            # document is not in the corpus, the claim as-cited is
            # UNSUPPORTED — a type/window match cannot soften a failed
            # citation
            misses.append(f"accession {claim['accession']} not in corpus "
                          f"for this name")
            return "UNSUPPORTED", [], misses
        pool = acc
    if lo:
        dated = [o for o in pool if o["filing_date"]
                 and lo <= o["filing_date"] <= hi]
        if not dated and pool:
            misses.append(f"no object filed in {lo}..{hi}")
        pool = dated
    if pool:
        status = "SOURCE_MATCHED" if not misses else "PARTIAL_MATCH"
        return status, pool[:5], misses
    # nothing left: PARTIAL if some element matched along the way
    return ("PARTIAL_MATCH" if len(misses) < len(
        [k for k in ("type", "accession", "date_range")
         if claim.get(k)]) else "UNSUPPORTED"), [], misses


def passport(claim_raw: str, claim: dict | None,
             universe_ok: bool | None) -> dict:
    doc = {"claim_as_given": claim_raw,
           "claim_as_parsed": claim,
           "generated": datetime.now(timezone.utc).isoformat(),
           "status": None, "matched_evidence": [], "misses": [],
           "replay": None, "not_advice": NOT_ADVICE}
    if claim is None:
        doc["status"] = "NOT_PARSEABLE"
        doc["note"] = ("the conservative text parser could not "
                       "confidently structure this claim — an unparsed "
                       "claim is never called unsupported")
        return doc
    if universe_ok is False:
        doc["status"] = "NOT_IN_COVERAGE"
        doc["note"] = (f"{claim['ticker']} is outside the 79-name scoring "
                       f"universe — the corpus cannot speak to it")
        return doc
    objs, corpus_scope = _corpus(claim["ticker"])
    if corpus_scope is not None:
        doc["corpus"] = corpus_scope
    status, matched, misses = _match(claim, objs)
    doc["status"] = status
    doc["misses"] = misses
    doc["matched_evidence"] = [
        {k: o[k] for k in ("ticker", "evidence_type", "filing_date",
                           "accession_number", "excerpt", "source_hash",
                           "available_as_of")} for o in matched]
    if status == "UNSUPPORTED":
        doc["note"] = ("not found in YUCLAW's corpus — never a truth "
                       "verdict")
    args = [f"--ticker {claim['ticker']}"]
    if claim.get("type"):
        args.append(f"--type {claim['type']}")
    if claim.get("date_range"):
        args.append(f"--date-range {claim['date_range'][0]}.."
                    f"{claim['date_range'][1]}")
    if claim.get("accession"):
        args.append(f"--accession {claim['accession']}")
    doc["replay"] = "yuclaw check-claim " + " ".join(args)
    return doc


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="yuclaw check-claim",
        epilog="Exit codes: 0 = passport produced (whatever its status); "
               "2 = usage/validation error; 3 = environment unsupported.",
        description="Evidence Passport — deterministic claim check "
                    "against the corpus. Statuses: SOURCE_MATCHED / "
                    "PARTIAL_MATCH / UNSUPPORTED (= not found in the "
                    "corpus, never a truth verdict) / NOT_IN_COVERAGE / "
                    "NOT_PARSEABLE. Text mode is conservative keyword/"
                    "type matching: one unambiguous universe ticker plus "
                    "a known type keyword or accession; no magnitude "
                    "checks, no negation, single-claim sentences only.")
    p.add_argument("--ticker")
    p.add_argument("--type")
    p.add_argument("--date-range", help="A..B (ISO dates)")
    p.add_argument("--accession")
    p.add_argument("--text", help="free-text claim (conservative parse)")
    a = p.parse_args(argv)

    if not a.text and not a.ticker:
        p.print_help()
        return 2
    if a.type and a.type.upper() not in VALID_TYPES:
        print(f"unknown --type {a.type!r} — valid event types: "
              f"{', '.join(VALID_TYPES)}", file=sys.stderr)
        return 2
    try:
        from v3.universe_tiers import scoring_universe
        uni = set(scoring_universe())
    except Exception as exc:                     # noqa: BLE001
        print(f"environment unsupported: cannot load the universe "
              f"({type(exc).__name__}) — is this a full checkout/install?",
              file=sys.stderr)
        return 3
    try:
        doc = _run(a, uni)
    except CorpusUnavailable as exc:
        print(f"corpus matching needs a YUCLAW research node — but this "
              f"evidence is publicly checkable at "
              f"https://yuclaw.ca/why/{exc.ticker}.json (see "
              f"'evidence_objects'; the as-of recipe is in "
              f"capabilities.json)", file=sys.stderr)
        return 3
    if doc is None:
        return 2
    print(json.dumps(doc, indent=1))
    return 0


def _run(a, uni: set) -> dict | None:
    """Build the passport for parsed args; None → usage error (exit 2)."""
    if a.text:
        claim = _parse_text(a.text, uni)
        ok = claim is not None and claim["ticker"] in uni
        return passport(a.text, claim, ok if claim else None)
    dr = None
    if a.date_range:
        try:
            lo, hi = (x.strip() for x in a.date_range.split(".."))
            from datetime import date as _date
            _date.fromisoformat(lo), _date.fromisoformat(hi)
        except ValueError:
            print("--date-range must be A..B with ISO dates "
                  "(e.g. 2026-07-01..2026-07-31)", file=sys.stderr)
            return None
        if lo > hi:
            print(f"start date is after end date — did you mean "
                  f"{hi}..{lo}?", file=sys.stderr)
            return None
        dr = (lo, hi)
    claim = {"ticker": a.ticker.upper(),
             "type": a.type.upper() if a.type else None,
             "accession": a.accession, "date_range": dr}
    return passport(json.dumps(
        {k: v for k, v in claim.items() if v}), claim,
        claim["ticker"] in uni)


if __name__ == "__main__":
    sys.exit(main())

"""
Passport status-semantics guard (v5.3.3).

Asserts the load-bearing invariant fixed on 2026-08-05: PARTIAL_MATCH
requires at least one matched EvidenceObject (with some claim elements
unmatched); a claim that matches ZERO objects is UNSUPPORTED — "not
found in YUCLAW's corpus — never a truth verdict". The trigger was the
empty-corpus-name case (DIA-style: a universe name with no evidence
objects), which v5.3.2 stamped PARTIAL_MATCH with an empty
matched_evidence array.

Pure-logic tests against _match — no backend, no snapshot, no network.

Run:  python3 -m pytest tests/test_passport_semantics.py -v
"""
from v3.cli.check_claim import _match

OBJ = {
    "ticker": "NVDA", "evidence_type": "INSIDER_SELL",
    "filing_date": "2026-05-12",
    "accession_number": "0001234567-26-000001",
    "excerpt": "x", "source_hash": "h", "available_as_of": "2026-05-12",
    "protocol_id": None,
}


def _claim(**kw):
    base = {"ticker": "NVDA", "type": None, "accession": None,
            "date_range": None}
    base.update(kw)
    return base


def test_empty_corpus_name_is_unsupported():
    # the DIA-style case: universe name, zero objects in the corpus
    status, matched, _ = _match(
        _claim(type="INSIDER_SELL", date_range=("2026-05-01", "2026-05-31")),
        [])
    assert status == "UNSUPPORTED"
    assert matched == []


def test_ticker_only_empty_corpus_is_unsupported():
    status, matched, _ = _match(_claim(), [])
    assert status == "UNSUPPORTED"
    assert matched == []


def test_partial_match_carries_matched_evidence():
    # type matches, window does not → PARTIAL_MATCH must list the
    # objects that matched the matched element
    status, matched, misses = _match(
        _claim(type="INSIDER_SELL", date_range=("2026-07-01", "2026-07-31")),
        [OBJ])
    assert status == "PARTIAL_MATCH"
    assert len(matched) >= 1
    assert any("2026-07-01..2026-07-31" in m for m in misses)


def test_full_match_is_source_matched():
    status, matched, misses = _match(
        _claim(type="INSIDER_SELL", date_range=("2026-05-01", "2026-05-31")),
        [OBJ])
    assert status == "SOURCE_MATCHED"
    assert matched and not misses


def test_failed_accession_stays_unsupported():
    # the accession-identity rule survives the v5.3.3 rewrite: a cited
    # document absent from the corpus is UNSUPPORTED even when type matches
    status, matched, _ = _match(
        _claim(type="INSIDER_SELL", accession="0009999999-26-000009"),
        [OBJ])
    assert status == "UNSUPPORTED"
    assert matched == []


def test_partial_never_empty_handed():
    # the invariant itself, across a sweep of claim shapes and corpora
    corpora = ([], [OBJ])
    shapes = (
        _claim(),
        _claim(type="INSIDER_SELL"),
        _claim(type="DIVIDEND_CHANGE"),
        _claim(date_range=("2026-01-01", "2026-01-31")),
        _claim(type="INSIDER_SELL", date_range=("2026-01-01", "2026-01-31")),
        _claim(type="INSIDER_SELL", accession=OBJ["accession_number"],
               date_range=("2026-01-01", "2026-01-31")),
    )
    for objs in corpora:
        for claim in shapes:
            status, matched, _ = _match(claim, objs)
            if status == "PARTIAL_MATCH":
                assert matched, (claim, objs)

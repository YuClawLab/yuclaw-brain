"""
Accession-only resolution guard (v6.0.1, ORDER 2026-09-05B D2).

Asserts the semantic guard on `yuclaw check-claim --accession N` without
--ticker: the accession is normalized with the existing text-parser rule,
looked up in the SAME canonical corpus the ticker+accession path queries,
and

  * exactly one name  -> the existing ticker+accession path runs; the
    payload is byte-identical except input-echo metadata
    (claim_as_given, generated);
  * more than one     -> exit 2, deterministic sorted candidates,
    "--accession requires --ticker when ambiguous";
  * zero              -> the existing UNSUPPORTED outcome, exit 0;
  * malformed         -> exit 2 (validation error), never a usage dump.

Pure-logic: _corpus is monkeypatched with a synthetic corpus; no backend,
no snapshot, no network.

Run:  python3 -m pytest tests/test_check_claim_accession.py -v
"""
import json

import pytest

from v3.cli import check_claim as cc

UNIQUE = "0001045810-26-000019"          # NVDA only
SHARED = "0001645590-26-000045"          # NVDA + AMD (+ others in the real corpus)
UNKNOWN = "0000000000-00-000000"


def _obj(ticker, acc, etype="INSIDER_SELL"):
    return {"ticker": ticker, "evidence_type": etype, "filing_date": "2026-05-12",
            "accession_number": acc, "excerpt": "x", "source_hash": "h",
            "available_as_of": "2026-05-12T00:00:00+00:00", "protocol_id": None}


CORPUS = {
    "NVDA": [_obj("NVDA", UNIQUE), _obj("NVDA", SHARED, "OTHER_MATERIAL")],
    "AMD": [_obj("AMD", SHARED, "OTHER_MATERIAL")],
}


@pytest.fixture(autouse=True)
def fake_corpus(monkeypatch):
    calls = []

    def _corpus(ticker):
        calls.append(ticker)
        return list(CORPUS.get(ticker, [])), None
    monkeypatch.setattr(cc, "_corpus", _corpus)
    return calls


def _run(argv, capsys):
    rc = cc.main(argv)
    out = capsys.readouterr()
    return rc, out.out, out.err


def _strip_echo(doc):
    return {k: v for k, v in doc.items() if k not in ("claim_as_given", "generated")}


def test_unique_accession_equals_explicit_path_except_input_echo(capsys, fake_corpus):
    rc1, out1, _ = _run(["--accession", UNIQUE], capsys)
    rc2, out2, _ = _run(["--ticker", "NVDA", "--accession", UNIQUE], capsys)
    assert rc1 == rc2 == 0
    d1, d2 = json.loads(out1), json.loads(out2)
    assert d1["status"] == d2["status"] == "SOURCE_MATCHED"
    # byte-for-byte except the input echo and the timestamp
    assert json.dumps(_strip_echo(d1), sort_keys=True) == json.dumps(_strip_echo(d2), sort_keys=True)
    assert d1["claim_as_given"] == json.dumps({"accession": UNIQUE})
    assert d1["claim_as_parsed"]["ticker"] == "NVDA"


def test_accession_only_searches_the_scoring_universe_corpus(capsys, fake_corpus):
    from v3.universe_tiers import scoring_universe
    _run(["--accession", UNIQUE], capsys)
    # the SAME corpus function, one scoring-universe name at a time (plus the
    # final explicit-path lookup for the resolved name)
    assert set(fake_corpus) == set(scoring_universe())


def test_ambiguous_accession_exit_2_sorted_candidates(capsys):
    rc, out, err = _run(["--accession", SHARED], capsys)
    assert rc == 2 and out == ""
    assert "--accession requires --ticker when ambiguous" in err
    assert "AMD, NVDA" in err                    # deterministic sorted order


def test_unknown_accession_is_the_existing_unsupported_outcome(capsys):
    rc, out, _ = _run(["--accession", UNKNOWN], capsys)
    assert rc == 0
    d = json.loads(out)
    assert d["status"] == "UNSUPPORTED" and d["matched_evidence"] == []
    assert d["note"] == "not found in YUCLAW's corpus — never a truth verdict"
    assert d["claim_as_parsed"]["accession"] == UNKNOWN and d["claim_as_parsed"]["ticker"] is None


def test_malformed_accession_exit_2_not_a_usage_dump(capsys):
    rc, out, err = _run(["--accession", "not-an-accession"], capsys)
    assert rc == 2 and out == ""
    assert "not an SEC accession number" in err
    assert "usage:" not in err.lower()


def test_undashed_accession_normalizes_with_the_existing_rule(capsys):
    assert cc.normalize_accession("000104581026000019") == UNIQUE
    assert cc.normalize_accession(" 0001045810-26-000019 ") == UNIQUE
    assert cc.normalize_accession("1045810-26-19") is None
    rc, out, _ = _run(["--accession", "000104581026000019"], capsys)
    assert rc == 0 and json.loads(out)["claim_as_parsed"]["ticker"] == "NVDA"


def test_explicit_ticker_accession_path_unchanged(capsys):
    rc, out, _ = _run(["--ticker", "AMD", "--accession", UNIQUE], capsys)
    assert rc == 0
    d = json.loads(out)
    assert d["status"] == "UNSUPPORTED"
    assert d["misses"] == [f"accession {UNIQUE} not in corpus for this name"]

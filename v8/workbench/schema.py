"""CommitmentClaim.v1 — the typed financial commitment claim and its outcome record.

Every field that decides comparability is explicit and mandatory: metric, currency, measurement unit, scale as
stated, accounting basis, fiscal period (label + type + start + end) and the resolution rule. A claim with any of
them missing cannot be frozen; the validator returns EVERY blocking reason, not the first one. Values are never
coerced: a float amount, a bare year, a lowercase currency or an unknown basis is a reason, not a guess.
The machine-readable copy of this contract is schemas/CommitmentClaim.v1.json.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import re

from v3.receipts.contracts import ContractError, digest
from v8.workbench import money

SCHEMA = "yuclaw-commitment-claim/1"
OUTCOME_SCHEMA = "yuclaw-commitment-outcome/1"
KIND = "commitment"
PERIOD_TYPES = ("FY", "H", "Q", "M")
PERIOD_DAYS = {"FY": (360, 372), "H": (175, 190), "Q": (80, 95), "M": (27, 32)}
SOURCE_KINDS = ("filing", "press_release", "transcript", "other")
RIGHTS = ("FICTIONAL", "SEC_PUBLIC_FILING", "UNKNOWN")
RESOLUTION_RULES = {
    "RANGE_CONTAINS_ACTUAL": "resolved IN_RANGE when low <= actual <= high for an outcome with the same metric, currency, unit, basis and fiscal period; otherwise OUT_OF_RANGE; any mismatch or missing outcome is unresolved",
}
BASES = ("GAAP", "IFRS", "non-GAAP", "non-GAAP adjusted", "other-stated")
REQUIRED_CLAIM = ("schema", "claim_id", "issuer", "metric", "kind", "statement", "range", "unit", "currency", "scale_as_stated",
                  "basis", "fiscal_period", "resolution_rule", "stated_at", "source", "fictional")
REQUIRED_SOURCE = ("kind", "form", "accession", "url", "filed_at", "available_as_of", "excerpt", "source_hash", "fictional", "rights")
REQUIRED_PERIOD = ("label", "type", "start", "end")
REQUIRED_OUTCOME = ("schema", "claim_id", "metric", "actual", "unit", "currency", "basis", "fiscal_period", "comparable", "source", "fictional")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_TICKER = re.compile(r"^[A-Z][A-Z0-9.-]{0,9}$")
_CIK = re.compile(r"^[0-9]{10}$")
_ACCESSION = re.compile(r"^[0-9]{10}-[0-9]{2}-[0-9]{6}$")
_TS = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,6})?Z$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_PRINTABLE = re.compile(r"^[^\x00-\x08\x0b\x0c\x0e-\x1f]*$")
STATEMENT_MAX, EXCERPT_MAX, NAME_MAX = 1000, 4000, 200


def _date(v, field, reasons) -> _dt.date | None:
    if not isinstance(v, str):
        reasons.append(f"{field}: date YYYY-MM-DD required"); return None
    try:
        return _dt.datetime.strptime(v, "%Y-%m-%d").date()
    except ValueError:
        reasons.append(f"{field}: {v!r} is not a date YYYY-MM-DD"); return None


def parse_ts(v: str) -> _dt.datetime:
    """RFC3339 UTC ('Z') with optional fraction → aware datetime. Raises ContractError."""
    if not isinstance(v, str) or not _TS.match(v):
        raise ContractError(f"timestamp {v!r} is not RFC3339 UTC (YYYY-MM-DDTHH:MM:SS[.ffffff]Z)")
    base, _, frac = v[:-1].partition(".")
    dt = _dt.datetime.strptime(base, "%Y-%m-%dT%H:%M:%S")
    return dt.replace(microsecond=int((frac + "000000")[:6]) if frac else 0, tzinfo=_dt.timezone.utc)


def _text(v, field, maxlen, reasons, *, required=True) -> str | None:
    if v is None or v == "":
        if required:
            reasons.append(f"{field}: required")
        return None
    if not isinstance(v, str) or len(v) > maxlen or not _PRINTABLE.match(v):
        reasons.append(f"{field}: text up to {maxlen} characters without control characters required"); return None
    return v


def check_period(raw, field="fiscal_period") -> tuple[dict | None, list[str]]:
    reasons: list[str] = []
    if not isinstance(raw, dict):
        return None, [f"{field}: object with label, type, start, end required (a bare label is not a fiscal period)"]
    for k in REQUIRED_PERIOD:
        if k not in raw:
            reasons.append(f"{field}.{k}: required")
    if reasons:
        return None, reasons
    label = _text(raw["label"], f"{field}.label", 32, reasons)
    typ = raw["type"]
    if typ not in PERIOD_TYPES:
        reasons.append(f"{field}.type: one of {list(PERIOD_TYPES)} required (got {typ!r})")
    start = _date(raw["start"], f"{field}.start", reasons); end = _date(raw["end"], f"{field}.end", reasons)
    if start and end:
        days = (end - start).days + 1
        if days <= 0:
            reasons.append(f"{field}: end {raw['end']} is before start {raw['start']}")
        elif typ in PERIOD_DAYS and not (PERIOD_DAYS[typ][0] <= days <= PERIOD_DAYS[typ][1]):
            reasons.append(f"{field}: a {typ} period spans {PERIOD_DAYS[typ][0]}–{PERIOD_DAYS[typ][1]} days; {raw['start']}..{raw['end']} spans {days}")
    if reasons:
        return None, reasons
    return {"label": label, "type": typ, "start": raw["start"], "end": raw["end"]}, []


def check_source(raw, field="source") -> tuple[dict | None, list[str]]:
    reasons: list[str] = []
    if not isinstance(raw, dict):
        return None, [f"{field}: object required"]
    for k in REQUIRED_SOURCE:
        if k not in raw:
            reasons.append(f"{field}.{k}: required")
    if reasons:
        return None, reasons
    if raw["kind"] not in SOURCE_KINDS:
        reasons.append(f"{field}.kind: one of {list(SOURCE_KINDS)} required")
    _text(raw["form"], f"{field}.form", 64, reasons)
    acc = raw["accession"]
    if not isinstance(acc, str) or not _ACCESSION.match(acc):
        reasons.append(f"{field}.accession: EDGAR accession NNNNNNNNNN-NN-NNNNNN required (got {acc!r})")
    if raw["url"] is not None and (not isinstance(raw["url"], str) or not raw["url"].startswith(("https://", "http://")) or len(raw["url"]) > 500):
        reasons.append(f"{field}.url: null or an http(s) URL up to 500 characters")
    filed = _date(raw["filed_at"], f"{field}.filed_at", reasons)
    avail = raw["available_as_of"]
    try:
        avail_dt = parse_ts(avail)
    except ContractError as exc:
        reasons.append(f"{field}.available_as_of: {exc}"); avail_dt = None
    if filed and avail_dt and avail_dt.date() < filed:
        reasons.append(f"{field}: available_as_of {avail} precedes filed_at {raw['filed_at']}")
    ex = _text(raw["excerpt"], f"{field}.excerpt", EXCERPT_MAX, reasons)
    if ex is not None:
        h = hashlib.sha256(ex.encode("utf-8")).hexdigest()
        if raw["source_hash"] != h:
            reasons.append(f"{field}.source_hash: must equal sha256 of the excerpt bytes ({h[:16]}…)")
    if not isinstance(raw["fictional"], bool):
        reasons.append(f"{field}.fictional: boolean required")
    if raw["rights"] not in RIGHTS:
        reasons.append(f"{field}.rights: one of {list(RIGHTS)} required")
    elif raw["fictional"] is True and raw["rights"] != "FICTIONAL":
        reasons.append(f"{field}.rights: a fictional source is rights=FICTIONAL")
    elif raw["fictional"] is False and raw["rights"] == "FICTIONAL":
        reasons.append(f"{field}.rights: FICTIONAL rights require fictional=true")
    if reasons:
        return None, reasons
    return {k: raw[k] for k in REQUIRED_SOURCE}, []


def check_claim(raw) -> tuple[dict | None, list[str]]:
    """(normalized claim, []) or (None, [every blocking reason])."""
    reasons: list[str] = []
    if not isinstance(raw, dict):
        return None, ["claim: object required"]
    for k in REQUIRED_CLAIM:
        if k not in raw:
            reasons.append(f"{k}: required")
    if reasons:
        return None, reasons
    if raw["schema"] != SCHEMA:
        reasons.append(f"schema: {SCHEMA!r} required")
    if raw["kind"] != KIND:
        reasons.append(f"kind: {KIND!r} required")
    cid = raw["claim_id"]
    if not isinstance(cid, str) or not _ID.match(cid):
        reasons.append("claim_id: identifier [A-Za-z0-9][A-Za-z0-9._:-]{0,127} required")
    iss = raw["issuer"]
    if not isinstance(iss, dict) or set(iss) != {"name", "ticker", "cik"}:
        reasons.append("issuer: object with exactly name, ticker, cik required")
    else:
        _text(iss["name"], "issuer.name", NAME_MAX, reasons)
        if not isinstance(iss["ticker"], str) or not _TICKER.match(iss["ticker"]):
            reasons.append("issuer.ticker: uppercase ticker required")
        if not isinstance(iss["cik"], str) or not _CIK.match(iss["cik"]):
            reasons.append("issuer.cik: ten-digit CIK string required")
    _text(raw["metric"], "metric", 64, reasons)
    _text(raw["statement"], "statement", STATEMENT_MAX, reasons)
    rng = raw["range"]
    low = high = None
    if not isinstance(rng, dict) or set(rng) != {"low", "high"}:
        reasons.append("range: object with exactly low and high required")
    else:
        try:
            low = money.parse_amount(rng["low"], "range.low")
        except ContractError as exc:
            reasons.append(str(exc))
        try:
            high = money.parse_amount(rng["high"], "range.high")
        except ContractError as exc:
            reasons.append(str(exc))
        if low is not None and high is not None and low > high:
            reasons.append("range: low must not exceed high")
    unit = raw["unit"]
    try:
        money.validate_currency(raw["currency"], "currency")
    except ContractError as exc:
        reasons.append(str(exc))
    if not isinstance(unit, str) or not unit:
        reasons.append("unit: measurement unit required (for money, the currency code)")
    elif isinstance(raw["currency"], str) and unit != raw["currency"]:
        reasons.append(f"unit: a monetary claim's unit must equal its currency ({unit!r} vs {raw['currency']!r})")
    try:
        money.validate_scale(raw["scale_as_stated"])
    except ContractError as exc:
        reasons.append(str(exc))
    if raw["basis"] not in BASES:
        reasons.append(f"basis: one of {list(BASES)} required (got {raw['basis']!r})")
    period, pr = check_period(raw["fiscal_period"]); reasons += pr
    if raw["resolution_rule"] not in RESOLUTION_RULES:
        reasons.append(f"resolution_rule: one of {list(RESOLUTION_RULES)} required (got {raw['resolution_rule']!r})")
    stated = _date(raw["stated_at"], "stated_at", reasons)
    src, sr = check_source(raw["source"]); reasons += sr
    if not isinstance(raw["fictional"], bool):
        reasons.append("fictional: boolean required")
    elif src is not None and src["fictional"] != raw["fictional"]:
        reasons.append("fictional: claim and source must agree")
    if src is not None and stated is not None and src["filed_at"] != raw["stated_at"]:
        reasons.append("stated_at: must equal source.filed_at (the statement date is the filing date of its source)")
    if reasons:
        return None, reasons
    claim = {"schema": SCHEMA, "claim_id": cid, "issuer": {"name": iss["name"], "ticker": iss["ticker"], "cik": iss["cik"]}, "metric": raw["metric"], "kind": KIND,
             "statement": raw["statement"], "range": {"low": money.to_json(low), "high": money.to_json(high)}, "unit": unit, "currency": raw["currency"],
             "scale_as_stated": raw["scale_as_stated"], "basis": raw["basis"], "fiscal_period": period, "resolution_rule": raw["resolution_rule"],
             "stated_at": raw["stated_at"], "source": src, "fictional": raw["fictional"]}
    return claim, []


def validate_claim(raw) -> dict:
    claim, reasons = check_claim(raw)
    if reasons:
        raise ContractError("claim cannot be frozen: " + "; ".join(reasons))
    return claim


def claim_digest(claim: dict) -> str:
    return digest(claim)


def check_outcome(raw) -> tuple[dict | None, list[str]]:
    reasons: list[str] = []
    if not isinstance(raw, dict):
        return None, ["outcome: object required"]
    for k in REQUIRED_OUTCOME:
        if k not in raw:
            reasons.append(f"outcome.{k}: required")
    if reasons:
        return None, reasons
    if raw["schema"] != OUTCOME_SCHEMA:
        reasons.append(f"outcome.schema: {OUTCOME_SCHEMA!r} required")
    if not isinstance(raw["claim_id"], str) or not _ID.match(raw["claim_id"]):
        reasons.append("outcome.claim_id: identifier required")
    _text(raw["metric"], "outcome.metric", 64, reasons)
    actual = None
    try:
        actual = money.parse_amount(raw["actual"], "outcome.actual")
    except ContractError as exc:
        reasons.append(str(exc))
    try:
        money.validate_currency(raw["currency"], "outcome.currency")
    except ContractError as exc:
        reasons.append(str(exc))
    if not isinstance(raw["unit"], str) or not raw["unit"]:
        reasons.append("outcome.unit: required")
    if raw["basis"] not in BASES:
        reasons.append(f"outcome.basis: one of {list(BASES)} required (got {raw['basis']!r})")
    period, pr = check_period(raw["fiscal_period"], "outcome.fiscal_period"); reasons += pr
    if not isinstance(raw["comparable"], bool):
        reasons.append("outcome.comparable: boolean declaration required (the calculator still checks every field itself)")
    src, sr = check_source(raw["source"], "outcome.source"); reasons += sr
    if not isinstance(raw["fictional"], bool):
        reasons.append("outcome.fictional: boolean required")
    elif src is not None and src["fictional"] != raw["fictional"]:
        reasons.append("outcome.fictional: outcome and source must agree")
    if reasons:
        return None, reasons
    out = {"schema": OUTCOME_SCHEMA, "claim_id": raw["claim_id"], "metric": raw["metric"], "actual": money.to_json(actual), "unit": raw["unit"], "currency": raw["currency"],
           "basis": raw["basis"], "fiscal_period": period, "comparable": raw["comparable"], "source": src, "fictional": raw["fictional"]}
    return out, []


def validate_outcome(raw) -> dict:
    out, reasons = check_outcome(raw)
    if reasons:
        raise ContractError("outcome cannot be recorded: " + "; ".join(reasons))
    return out


# ---------------------------------------------------------------- fixture adapter (tests/fixtures/v8/commitments)
def _period_from_fixture(p, claim_period: dict | None = None) -> dict:
    """Fixture periods: {label,start,end} (type inferred from the label) or a bare label equal to the claim's."""
    if isinstance(p, str):
        if claim_period and p == claim_period["label"]:
            return dict(claim_period)
        return {"label": p, "type": "FY" if p.startswith("FY") else "Q" if p.startswith("Q") else "FY", "start": "1900-01-01", "end": "1900-01-01"}
    lab = p["label"]
    typ = p.get("type") or ("Q" if lab.upper().startswith("Q") else "H" if lab.upper().startswith("H") else "FY")
    return {"label": lab, "type": typ, "start": p["start"], "end": p["end"]}


def _source_from_fixture(s: dict) -> dict:
    return {"kind": s.get("kind", "filing"), "form": s["form"], "accession": s["accession"], "url": s.get("url"), "filed_at": s["filed_at"],
            "available_as_of": s["available_as_of"], "excerpt": s["excerpt"], "source_hash": s["source_hash"], "fictional": bool(s.get("fictional", False)),
            "rights": s.get("rights") or ("FICTIONAL" if s.get("fictional") else "UNKNOWN")}


def from_fixture(fx: dict) -> dict:
    """Map a yuclaw-commitment-fixture/1 document to validated v1 records:
    {'claim': ..., 'revisions': [{'revision_id','type','claim'|None,'reason','source'}], 'outcome': ...|None}."""
    c = fx["claim"]
    claim = validate_claim({"schema": SCHEMA, "claim_id": c["claim_id"], "issuer": fx["issuer"], "metric": c["metric"], "kind": KIND, "statement": c["statement"],
                            "range": c["range"], "unit": c["unit"], "currency": c["currency"], "scale_as_stated": c.get("scale_as_stated", "units"), "basis": c["basis"],
                            "fiscal_period": _period_from_fixture(c["fiscal_period"]), "resolution_rule": c.get("resolution_rule", "RANGE_CONTAINS_ACTUAL"),
                            "stated_at": c["stated_at"], "source": _source_from_fixture(c["source"]), "fictional": bool(fx.get("fictional"))})
    revs = []
    for r in fx.get("revisions", []):
        src = _source_from_fixture(r["source"])
        if r["type"] in ("REVISED", "CORRECTED_SOURCE"):
            new = dict(claim, range=r["range"], basis=r.get("basis", claim["basis"]), unit=r.get("unit", claim["unit"]), currency=r.get("currency", claim["currency"]),
                       statement=r.get("statement", claim["statement"]), stated_at=r["stated_at"], source=src,
                       fiscal_period=_period_from_fixture(r.get("fiscal_period", claim["fiscal_period"]), claim["fiscal_period"]))
            revs.append({"revision_id": r["revision_id"], "type": r["type"], "claim": validate_claim(new), "reason": r.get("reason", ""), "source": src, "supersedes": r.get("supersedes")})
        elif r["type"] == "WITHDRAWN":
            revs.append({"revision_id": r["revision_id"], "type": "WITHDRAWN", "claim": None, "reason": r.get("reason", ""), "source": src, "supersedes": r.get("supersedes")})
        else:
            raise ContractError(f"fixture revision type {r['type']!r} unknown")
    out = None
    if fx.get("outcome"):
        o = fx["outcome"]
        out = validate_outcome({"schema": OUTCOME_SCHEMA, "claim_id": claim["claim_id"], "metric": o.get("metric", claim["metric"]), "actual": o["actual"], "unit": o["unit"],
                                "currency": o["currency"], "basis": o["basis"], "fiscal_period": _period_from_fixture(o["fiscal_period"], claim["fiscal_period"]),
                                "comparable": bool(o["comparable"]), "source": _source_from_fixture(o["source"]), "fictional": bool(o["source"].get("fictional", fx.get("fictional")))})
    return {"claim": claim, "revisions": revs, "outcome": out}

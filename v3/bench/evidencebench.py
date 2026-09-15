"""EvidenceBench scorer — packaged, stdlib-only (QA-03 / QA-04, 2026-09-15).

RUBRIC v1 (released 2026-09-11, protocol 6adb3a06f578; reproduced here EXACTLY, byte-for-byte on the published
item set): T1 score 1.0 if normalized-token overlap of the answer with the keyed excerpt >= 0.5 OR the answer contains
the keyed accession verbatim; T2 exact normalized event_type; T3 exact normalized label; the literal abstention
string scores 0.25; else 0.0. KNOWN LIMITATION (reproduced, not validated): a QUESTION ECHO scores 1.0 on every
T1 item whose question quotes the accession — set-of-token overlap and accession occurrence are lexical tests,
not semantic verification. v1 numbers remain reproducible under this flawed rubric; they are not validated
measures of groundedness.

RUBRIC v2 (CANDIDATE — deterministic contract; NOT registered; NO real v2 item set exists until the protocol
registration is adopted — registration requires a research-chain append that is not part of the QA order):
  An answer is SUPPORTED only if ALL required facts of the item's key are stated and none is contradicted:
   * accession: required, exact verbatim match (normalized whitespace);
   * event_type: required when keyed — the locked vocabulary token itself OR one of its registered accepted
     expressions (ACCEPTED_EXPRESSIONS), matched as whole words after normalization;
   * numeric facts keyed for transaction items (shares, price, date): each required value must appear after
     numeric normalization (thousands separators and currency symbols removed; dates as YYYY-MM-DD); a DIFFERENT
     value of the same fact class present in the answer with the keyed value absent is a CONTRADICTION (score 0);
   * direction/negation: a keyed direction (buy/sell) contradicted by the opposite expression is a CONTRADICTION;
   * the question text itself is never a source of credit: tokens that appear in the question are excluded from
     fact matching, so a question echo can never satisfy a fact the question does not state;
   * abstention (the literal abstention string, case-insensitive) scores 0.25 and is counted separately;
   * empty/missing answer → 0.0 (counted as MISSING); a key with no scorable facts → item INVALID (never a
     silent zero): the scorer refuses to emit a score for such an item set.
  This is STRUCTURED FACT MATCHING — a bounded lexical/numeric rule. It is NOT semantic equivalence and NOT a
  verification of truth; its limitation is disclosed with every v2 result.

IDENTITY CONTRACT: every result binds rubric_version + the canonical item-set identity (sha256 of the items file
bytes) and the number of items; unsupported rubric, mismatched identity or malformed input fail with controlled
errors (BenchError) — never an apparently valid zero-result evaluation."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ABSTAIN = "cannot verify from the evidence provided"
RUBRICS = ("v1", "v2")
ACCEPTED_EXPRESSIONS = {
    "INSIDER_BUY": ["insider buy", "insider purchase", "purchased", "bought", "acquired", "open market purchase"],
    "INSIDER_SELL": ["insider sell", "insider sale", "sold", "sale of", "disposed", "disposition"],
    "BUYBACK_AUTHORIZED": ["buyback authorized", "repurchase authorization", "authorized a repurchase", "share repurchase program"],
    "BUYBACK_EXECUTED": ["buyback executed", "repurchased", "shares repurchased"],
    "GUIDANCE_RAISE": ["guidance raise", "raised guidance", "raises guidance", "increased guidance"],
    "GUIDANCE_CUT": ["guidance cut", "lowered guidance", "cut guidance", "reduced guidance"],
    "M_AND_A_CLOSE": ["acquisition closed", "completed the acquisition", "merger closed", "closing of the acquisition"],
}
OPPOSITES = {"INSIDER_BUY": "INSIDER_SELL", "INSIDER_SELL": "INSIDER_BUY", "GUIDANCE_RAISE": "GUIDANCE_CUT", "GUIDANCE_CUT": "GUIDANCE_RAISE"}
_norm_re = re.compile(r"[^a-z0-9 ]+")


class BenchError(ValueError):
    """Controlled scorer failure (exit code 3 at the CLI): identity mismatch, unsupported rubric, malformed input."""


def _norm(s: str) -> str:
    return _norm_re.sub(" ", (s or "").lower()).strip()


def item_set_hash(items: list[dict]) -> str:
    """The v1 generator's canonical item-set identity, reproduced exactly: sha256 of json.dumps(items sorted by
    item_id, sort_keys=True). Published as `item_set_hash` in meta.json since 7.0.0 (2026-09-11 set: 1bb76176…)."""
    canon = json.dumps(sorted(items, key=lambda x: x["item_id"]), sort_keys=True)
    return hashlib.sha256(canon.encode()).hexdigest()


def items_identity(path) -> dict:
    b = Path(path).read_bytes()
    lines = [l for l in b.decode("utf-8").splitlines() if l.strip()]
    try:
        canonical = item_set_hash([json.loads(l) for l in lines])
    except (ValueError, KeyError, TypeError):
        canonical = None
    return {"items_sha256": hashlib.sha256(b).hexdigest(), "item_set_hash": canonical, "n_items": len(lines), "bytes": len(b)}


def load_items(path) -> list[dict]:
    try:
        items = [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]
    except (OSError, ValueError) as exc:
        raise BenchError(f"items file unreadable or malformed ({exc.__class__.__name__})") from None
    for it in items:
        if not isinstance(it, dict) or not it.get("item_id") or it.get("template") not in ("T1", "T2", "T3") or not isinstance(it.get("key"), dict):
            raise BenchError("malformed item (item_id/template/key)")
    if not items:
        raise BenchError("empty item set")
    return items


def load_predictions(path) -> dict:
    try:
        preds = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise BenchError(f"predictions unreadable or malformed ({exc.__class__.__name__})") from None
    if not isinstance(preds, dict) or not all(isinstance(k, str) and (v is None or isinstance(v, str)) for k, v in preds.items()):
        raise BenchError("predictions must be an object of item_id -> answer string")
    return preds


# ------------------------------------------------------------------ v1 (exact reproduction of the released rule)
def _score_v1_item(it: dict, ans: str) -> float:
    a = _norm(ans)
    if a == _norm(ABSTAIN):
        return 0.25
    if it["template"] == "T1":
        key_toks = set(_norm(it["key"].get("excerpt", "")).split()); ans_toks = set(a.split())
        overlap = (len(key_toks & ans_toks) / len(key_toks) if key_toks else 0)
        return 1.0 if (overlap >= 0.5 or (it["key"].get("accession") or "") in ans) else 0.0
    if it["template"] == "T2":
        return 1.0 if a == _norm(it["key"].get("event_type", "")) else 0.0
    return 1.0 if a == _norm(it["key"].get("label", "")) else 0.0


# ------------------------------------------------------------------ v2 (structured fact matching; candidate)
_NUM = re.compile(r"(?<![a-z0-9])[$]?(\d[\d,]*\.?\d*)(?![a-z0-9])")
_DATE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")


def _numbers(s: str) -> set[str]:
    out = set()
    for m in _NUM.finditer(s.lower()):
        v = m.group(1).replace(",", "")
        try:
            f = float(v); out.add(f"{f:.4f}".rstrip("0").rstrip("."))
        except ValueError:
            pass
    return out


def _fact_numbers(key: dict) -> dict:
    facts = {}
    for k in ("shares", "price", "amount"):
        if key.get(k) is not None:
            try:
                facts[k] = f"{float(str(key[k]).replace(',', '').replace('$', '')):.4f}".rstrip("0").rstrip(".")
            except ValueError:
                pass
    if key.get("date"):
        facts["date"] = str(key["date"])[:10]
    return facts


def _type_expressed(answer_norm: str, etype: str) -> bool:
    words = [_norm(etype)] + [_norm(x) for x in ACCEPTED_EXPRESSIONS.get(etype, [])]
    return any(re.search(rf"(?<![a-z0-9]){re.escape(w)}(?![a-z0-9])", answer_norm) for w in words if w)


def _score_v2_item(it: dict, ans: str) -> tuple[float, str]:
    key = it["key"]; a_raw = ans or ""
    if _norm(a_raw) == _norm(ABSTAIN):
        return 0.25, "ABSTAIN"
    if not _norm(a_raw):
        return 0.0, "MISSING"
    q_norm = _norm(it.get("question", "")); a_norm = _norm(a_raw)
    acc = key.get("accession"); etype = key.get("event_type"); facts = _fact_numbers(key)
    if not acc and not etype and not facts and not key.get("label"):
        raise BenchError(f"item {it['item_id']}: key carries no scorable fact (empty or metadata-only key)")
    if it["template"] == "T3":
        return (1.0 if a_norm == _norm(key.get("label", "")) else 0.0), "LABEL"
    if acc and " ".join(acc.split()) not in " ".join(a_raw.split()):
        return 0.0, "ACCESSION_MISSING"
    if etype:
        opp = OPPOSITES.get(etype)
        if opp and _type_expressed(a_norm, opp):
            return 0.0, "CONTRADICTION_DIRECTION"           # the opposite direction stated: a contradiction, whatever else is present
        if not _type_expressed(a_norm, etype):
            return 0.0, "EVENT_TYPE_MISSING"
    if facts:
        ans_nums = _numbers(a_raw) | set(_DATE.findall(a_raw)); q_nums = _numbers(it.get("question", "")) | set(_DATE.findall(it.get("question", "")))
        credit_nums = ans_nums - q_nums                      # question tokens never earn credit
        for cls, val in facts.items():
            if val in credit_nums:
                continue
            if val in q_nums and val in ans_nums:
                return 0.0, f"FACT_FROM_QUESTION_ONLY:{cls}"
            if any(x != val for x in credit_nums) and val not in ans_nums:
                return 0.0, f"CONTRADICTION_VALUE:{cls}"
            return 0.0, f"FACT_MISSING:{cls}"
    if not etype and not facts:
        return 0.0, "NO_SUBSTANTIVE_FACT_KEYED"           # accession alone never proves support
    return 1.0, "SUPPORTED"


def score(items: list[dict], preds: dict, *, rubric: str, label: str, items_sha256: str, item_set_hash_value: str | None = None) -> dict:
    if rubric not in RUBRICS:
        raise BenchError(f"unsupported rubric {rubric!r}")
    per_type: dict[str, list] = {}; reasons: dict[str, int] = {}; abst = 0; missing = 0
    for it in items:
        ans = preds.get(it["item_id"], "") or ""
        if rubric == "v1":
            s = _score_v1_item(it, ans); why = "v1"
        else:
            s, why = _score_v2_item(it, ans)
        per_type.setdefault(it["template"], []).append(s); reasons[why] = reasons.get(why, 0) + 1
        if _norm(ans) == _norm(ABSTAIN): abst += 1
        if not _norm(ans): missing += 1
    n = len(items)
    out = {"label": label, "rubric_version": rubric, "items_sha256": items_sha256, "item_set_hash": item_set_hash_value or item_set_hash(items), "n_items": n, "scored": datetime.now(timezone.utc).isoformat(),
           "aggregate": round(sum(sum(v) for v in per_type.values()) / max(n, 1), 4), "per_type": {k: round(sum(v) / len(v), 4) for k, v in sorted(per_type.items())},
           "abstentions": abst, "missing": missing, "reasons": dict(sorted(reasons.items())),
           "scoring_rule": ("v1: correct 1.0 · 'cannot verify' 0.25 · else 0.0 — T1 = token overlap >= 0.5 OR accession occurrence (lexical; a question echo scores 1.0 — reproduced, not validated)" if rubric == "v1"
                            else "v2 CANDIDATE: structured fact matching (accession + event type + keyed numeric facts, question tokens excluded, contradictions score 0) — bounded lexical/numeric rule, not semantic verification"),
           "limitation": ("v1 numbers are reproducible under a flawed rubric; they are not validated measures of groundedness" if rubric == "v1"
                          else "v2 is a candidate rubric: not registered, no real v2 item set; structured matching is not semantic verification")}
    return out

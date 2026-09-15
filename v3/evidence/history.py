"""Complete historical evidence contract (QA-02, 2026-09-15).

A capped newest-first collection is a PREVIEW. Typed collection metadata declares scope, returned count, total
available in that scope, cap, actual ordering with a stable tie-breaker, oldest returned availability, build
identity and completeness. The complete public source is the per-ticker history file (why/{T}.history.json,
schema WhyHistory.v1) bound to one build through why/history_manifest.json. An as-of query is answered ONLY from
a collection whose declared completeness covers the request; a preview yields INCOMPLETE (with the partial
result) whenever objects outside the returned window could exist, whatever D is. Filtering is by the object's
recorded available_as_of, never by filing date or a generated-at timestamp. Completeness is for the declared
corpus and build — never a claim to hold every SEC filing ever made."""
from __future__ import annotations

from datetime import datetime, timezone

COLLECTION_SCHEMA = "evidence-collection/1"
HISTORY_SCHEMA = "WhyHistory.v1"
ORDERING_PREVIEW = "available_as_of DESC, accession_number DESC, source_hash DESC"
ORDERING_HISTORY = "available_as_of ASC, accession_number ASC, source_hash ASC"
STATUSES = ("COMPLETE", "COMPLETE_EMPTY", "INCOMPLETE", "OUT_OF_RANGE", "INVALID")


def _ts(s: str) -> datetime:
    d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _as_of_bound(D: str) -> datetime:
    """A date-only D means the END of that calendar day (UTC); a timestamp is used as given."""
    if len(D) == 10:
        return datetime.fromisoformat(D + "T23:59:59.999999+00:00")
    return _ts(D)


def sort_key(o: dict, ascending: bool = True):
    k = (_ts(o["available_as_of"]), o.get("accession_number") or "", o.get("source_hash") or "")
    return k


def collection_metadata(objects: list[dict], *, scope: str, total_available: int | None, cap: int | None, ordering: str, build_id: str, completeness: str, corpus_start: str | None, corpus_end: str | None) -> dict:
    avail = [o["available_as_of"] for o in objects]
    return {"schema": COLLECTION_SCHEMA, "scope": scope, "returned": len(objects), "total_available": total_available, "cap": cap, "ordering": ordering,
            "oldest_returned_available_as_of": (min(avail, key=_ts) if avail else None), "newest_returned_available_as_of": (max(avail, key=_ts) if avail else None),
            "build_id": build_id, "completeness": completeness, "corpus_start": corpus_start, "corpus_end": corpus_end,
            "note": ("PREVIEW: a capped newest-first slice; total_available counts objects in scope; an as-of query over this slice is INCOMPLETE unless returned == total_available"
                     if completeness == "PREVIEW" else "COMPLETE for the declared scope and build; not a claim to hold every SEC filing ever made")}


def validate_collection(meta: dict, objects: list[dict]) -> list[str]:
    p = []
    if not isinstance(meta, dict) or meta.get("schema") != COLLECTION_SCHEMA:
        return ["collection metadata missing or wrong schema"]
    if meta.get("returned") != len(objects):
        p.append("returned != len(objects)")
    if meta.get("completeness") not in ("PREVIEW", "COMPLETE"):
        p.append("completeness must be PREVIEW or COMPLETE")
    if not isinstance(meta.get("total_available"), int) or meta["total_available"] < 0:
        p.append("total_available unknown — must never be reported as complete or zero")
    elif meta.get("completeness") == "COMPLETE" and meta["total_available"] != len(objects):
        p.append("COMPLETE collection must return every object in scope")
    elif meta.get("completeness") == "PREVIEW" and meta["total_available"] < len(objects):
        p.append("total_available smaller than returned")
    asc = meta.get("ordering") == ORDERING_HISTORY
    keys = [sort_key(o) for o in objects]
    if keys != sorted(keys, reverse=not asc):
        p.append("objects are not in the declared ordering (with tie-breaker)")
    if not meta.get("build_id"):
        p.append("build_id missing")
    return p


def as_of_query(meta: dict, objects: list[dict], D: str) -> dict:
    """{'status', 'objects', 'reason'} for evidence as of D under the collection's declared completeness."""
    problems = validate_collection(meta, objects)
    if problems:
        return {"status": "INVALID", "objects": [], "reason": "; ".join(problems)}
    bound = _as_of_bound(D)
    subset = [o for o in objects if _ts(o["available_as_of"]) <= bound]
    if meta["completeness"] == "PREVIEW" and meta["total_available"] != meta["returned"]:
        return {"status": "INCOMPLETE", "objects": subset,
                "reason": f"preview returned {meta['returned']} of {meta['total_available']} objects in scope; objects outside the returned window may satisfy available_as_of <= D — use the complete history source"}
    cs, ce = meta.get("corpus_start"), meta.get("corpus_end")
    if cs and bound < _ts(cs):
        return {"status": "OUT_OF_RANGE", "objects": [], "reason": f"D precedes the declared corpus start {cs}"}
    if ce and bound > _ts(ce):
        return {"status": "OUT_OF_RANGE", "objects": subset, "reason": f"D is after the build's corpus end {ce}; later objects may exist in a newer build"}
    return {"status": "COMPLETE" if subset else "COMPLETE_EMPTY", "objects": subset, "reason": "complete for the declared scope and build"}

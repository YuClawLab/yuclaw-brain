"""Operation measurements: definitions, aggregation and the methods/limitations appendix.

Units and denominators are stated with every count. A LOGICAL OPERATION is one op_id; an ATTEMPT is one measured run of
it (the same op_id retried counts one operation, two attempts). Outcomes: COMMITTED (a new record), DUPLICATE (an idempotent
retry answered by the existing record), CONFLICT (same op_id, different bytes), REFUSED (a contract refusal; nothing
written), FAILED (an unexpected error), READ (a measured read-only task). Failed and refused attempts stay in their
denominators. Durations are wall-clock milliseconds of the software attempt: they measure the program, never a person's
cognitive effort, and a UI click measures an interaction, not labour. An attempt without a finished_at (process death)
is counted as MISSING_DURATION, never estimated. Historical totals before measurement began are not reconstructed.
"""
from __future__ import annotations

import statistics
from collections import Counter, defaultdict

from v9.brief import contracts
from v9.brief.sidecar import OUTCOMES, Sidecar

DEFINITIONS = {
    "operation": "one logical operation = one op_id; counted once however many times it was attempted",
    "attempt": "one measured run of an operation (a line in v9/operations.jsonl); retries are additional attempts of the same operation",
    "retries": "attempts − operations, over operations with ≥ 1 attempt",
    "outcome": "per attempt: " + " | ".join(OUTCOMES) + " — DUPLICATE is an idempotent retry answered by the existing record; CONFLICT is the same op_id with different bytes; REFUSED is a contract refusal with nothing written",
    "elapsed_ms": "wall-clock milliseconds of the software attempt, from entering the operation to leaving it; not labour time, not cognitive effort",
    "eligible_denominator": "all attempts recorded by this workspace's v9 surfaces since measurement began; nothing earlier is reconstructed",
    "exclusions": "v8 workbench operations (recorded in the v8 journal, not measured here); operations of other workspaces",
    "missingness": "an attempt whose line is corrupt or lacks finished_at is listed under missing, not estimated",
}


def aggregate(sc: Sidecar) -> dict:
    lines = sc.operations()
    good = [o for o in lines if not o.get("corrupt_line") and o.get("op_id")]
    corrupt = len(lines) - len(good)
    by_op = defaultdict(list)
    for o in good:
        by_op[o["op_id"]].append(o)
    per_task = defaultdict(lambda: {"operations": 0, "attempts": 0, "outcomes": Counter(), "durations_ms": []})
    outcomes = Counter(o.get("outcome") for o in good)
    durations = [o["elapsed_ms"] for o in good if isinstance(o.get("elapsed_ms"), int) and o.get("finished_at")]
    missing_duration = sum(1 for o in good if not (isinstance(o.get("elapsed_ms"), int) and o.get("finished_at")))
    for op_id, atts in by_op.items():
        task = atts[0].get("task", "unknown")
        per_task[task]["operations"] += 1; per_task[task]["attempts"] += len(atts)
        for a in atts:
            per_task[task]["outcomes"][a.get("outcome")] += 1
            if isinstance(a.get("elapsed_ms"), int) and a.get("finished_at"):
                per_task[task]["durations_ms"].append(a["elapsed_ms"])
    def summ(ds):
        return None if not ds else {"n": len(ds), "sum_ms": sum(ds), "median_ms": int(statistics.median(ds)), "max_ms": max(ds)}
    return {"schema": "yuclaw.brief-measurements/1", "definitions": DEFINITIONS, "operations": len(by_op), "attempts": len(good), "retries": len(good) - len(by_op),
            "outcomes": dict(outcomes), "durations": summ(durations), "missing": {"corrupt_lines": corrupt, "missing_duration": missing_duration},
            "per_task": {k: {"operations": v["operations"], "attempts": v["attempts"], "outcomes": dict(v["outcomes"]), "durations": summ(v["durations_ms"])} for k, v in sorted(per_task.items())},
            "scope": {"workspace_id": sc.meta["workspace_id"], "since": min((o.get("started_at") for o in good), default=None), "until": max((o.get("finished_at") or o.get("started_at") for o in good), default=None)}}


def appendix(view: dict, measurements: dict, *, software: dict, lang: str = "en") -> str:
    """Methods / limitations appendix generated from the records: identities, known settings, templates, provenance, dates,
    selection rules, measured counts and what is unavailable. Markdown."""
    fr = lang == "fr"
    H = (lambda s: f"## {s}\n")
    L = []
    L.append(("# Annexe — méthodes et limites" if fr else "# Methods and limitations appendix") + f" — {view['brief_id']} {view['version_id']}\n")
    L.append(H("Logiciel" if fr else "Software"))
    for k, v in software.items():
        L.append(f"- {k}: `{v}`")
    L.append("")
    L.append(H("Production du texte" if fr else "Text production"))
    for r in view.get("receipts", []):
        L.append(f"- {r['label']}: origin `{r['origin']}`, method `{r['recording_method']}`, template `{r.get('template')}`, provider `{r.get('provider')}`, model `{r.get('model')}`, settings `{r.get('settings')}`")
        if r.get("unknown"):
            L.append("  - " + ("inconnues explicites : " if fr else "explicit unknowns: ") + "; ".join(f"{k} — {v}" for k, v in r["unknown"].items()))
    L.append("")
    L.append(H("Instantané et portée temporelle" if fr else "Snapshot and time scope"))
    L.append(f"- snapshot `{view['snapshot_digest']}` at v8 tip `{view['v8_tip_at_snapshot']}`; " + ("information ultérieure : " if fr else "later information: ") + str(view.get("open_review_items", 0)) + (" élément(s) ouvert(s)" if fr else " open review item(s)"))
    for cid, s in (view.get("snapshot_summary") or {}).items():
        L.append(f"- {cid}: versions {s['versions']}, result `{s['result']}`, sources {len(s['sources'])}")
    L.append("")
    L.append(H("Énoncés" if fr else "Statements"))
    cov = view.get("coverage") or {}
    L.append(f"- {cov.get('sentence')}")
    L.append(f"- " + ("règle de sélection : " if fr else "selection rule: ") + str(cov.get("extraction_scope")))
    L.append(f"- " + ("appui par statut : " if fr else "support by status: ") + ", ".join(f"{k} {v}" for k, v in (view.get("support_counts") or {}).items()))
    L.append("")
    L.append(H("Rapports de détecteur" if fr else "Detector reports"))
    if not view.get("reports"):
        L.append("- " + ("aucun rapport importé ; aucune vérification de filigrane n’a été demandée ou effectuée" if fr else "none imported; no watermark check was requested or performed"))
    for r in view.get("reports", []):
        L.append(f"- `{r['detector']}` {r.get('detector_version') or ''}: execution `{r['execution']}`, signal `{r.get('signal')}`, calibration claimed `{r['calibration_claimed']}` → applicability `{r['calibration']['applicability']}` ({r['calibration']['reason']}); origin `{r['origin']}`; signature `{r['signature']['signature']}`/trust `{r['signature']['trust']}`")
        if r.get("unknown"):
            L.append("  - " + ("non exposé : " if fr else "not exposed: ") + "; ".join(f"{k} — {v}" for k, v in r["unknown"].items()))
    L.append("")
    L.append(H("Mesures des opérations" if fr else "Operation measurements"))
    L.append(f"- operations {measurements['operations']}, attempts {measurements['attempts']}, retries {measurements['retries']}, outcomes {measurements['outcomes']}")
    L.append(f"- durations {measurements['durations']}; missing {measurements['missing']}")
    L.append("- " + ("définitions : " if fr else "definitions: ") + "; ".join(f"{k} = {v}" for k, v in DEFINITIONS.items()))
    L.append("")
    L.append(H("Limites" if fr else "Limits"))
    for s in view.get("never_claims", []):
        L.append(f"- {s}")
    L.append("- " + view.get("dimension_note", ""))
    L.append("- " + ("Reproductibilité : les calculs enregistrés se recalculent à partir des entrées typées ; le texte importé, les reçus et les rapports sont des enregistrements de ce qui a été fourni, pas une preuve historique." if fr else
                     "Reproducibility: registered calculations recompute from typed inputs; imported text, receipts and reports are records of what was supplied, not historical proof."))
    L.append("- " + view.get("not_advice", ""))
    return "\n".join(L) + "\n"

#!/usr/bin/env python3
"""
EvidenceBench v0.1 — contamination-resistant financial-groundedness
benchmark (v5.3 PART D). Generator + scorer. The generation spec is the
release's ONE registration (uncomputed-standard class — no runs are ever
recorded against it; scoring a model is not a market statistic).

Contamination resistance is mechanical, not aspirational: items
regenerate WEEKLY in the chain from the newest post-cutoff accepted
evidence (trailing 7 days), so no static answer key can be memorized
from a training corpus — the answers did not exist at training time.
Keys ship openly (the property is regeneration, not secrecy).

Subcommands:
  generate   build docs/evidencebench/items.jsonl (+ item-set hash)
  score      score a predictions JSON {item_id: answer} against the keys
  selfscore  score our own extraction stack (answers read from the same
             corpus) — loudly labeled SELF-EVALUATION; format demo only
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
for p in (str(_REPO), str(_REPO / "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

SPEC = """
EVIDENCEBENCH GENERATION SPEC v0.1 (uncomputed-standard class; locked
2026-08-05). Deterministic Q/A construction from the canonical accepted
evidence record; no market statistic is computed here and no runs are
ever recorded against this entry.

ITEMS. For each accepted event with available_as_of in the trailing 7
calendar days as of generation time (the post-cutoff window — the
memorization-proof property: regenerated weekly in the daily chain,
answers that did not exist at any training cutoff), up to three items:
  T1 disclosure:  "What did {ticker} disclose on {filing_date} per
                   accession {accession}?"  — key: the verified excerpt
                   + source_hash; scored by grounded match.
  T2 event-type:  "Which event type did YUCLAW classify for {ticker}'s
                   filing {accession}?"  — key: the event_type string;
                   scored by exact match.
  T3 label:       "As of {date}, what was {ticker}'s YUCLAW signal
                   label?"  — key: the point-in-time label from the
                   snapshot record; scored by exact match.
Events without an accession are skipped for T1/T2 (disclosed in counts).
Item order and item_ids are deterministic (sorted by event_id); the
item-set hash = sha256 of the canonical JSON of all items, printed with
every release.

SCORING (exact; the scorer implements this and nothing else):
  grounded/exact correct = 1.0
  abstention — an answer that normalizes to "cannot verify" = 0.25
  anything else (including confident fabrication) = 0.0
"Cannot verify" beats confident fabrication BY CONSTRUCTION: an honest
abstention always outscores a wrong answer. Grounded match for T1 =
normalized-token overlap of the answer with the keyed excerpt >= 0.5,
or the answer contains the keyed accession verbatim. Per-type breakdown
reported; aggregate = mean over items. Groundedness, not prediction:
nothing here measures or implies future returns.
"""

BENCH_DIR = _REPO / "docs" / "evidencebench"
ABSTAIN = "cannot verify"


def register():
    from yuclaw_protocol_registry import Protocol, Registry, protocol_id
    reg = Registry(str(_REPO / "registry" / "protocols.jsonl"))
    pid = protocol_id(SPEC, {"class": "standard", "version": "0.1"})
    if not reg.get_protocol(pid):
        reg.register(Protocol(
            protocol_id=pid, name="EvidenceBench generation spec v0.1",
            method_hash=hashlib.sha256(SPEC.encode()).hexdigest()[:16],
            spec_summary="Deterministic weekly Q/A construction from "
                         "post-cutoff accepted evidence (three templates, "
                         "keys = verified excerpts/hashes, item-set hash "
                         "per release); abstention outscores fabrication "
                         "by construction; standard entry, no runs ever "
                         "recorded.",
            primary_endpoint="benchmark-generation ruling — standard "
                             "entry; no statistical endpoint, no runs "
                             "ever recorded",
            secondary_endpoints=[],
            lock_date=datetime.now(timezone.utc).strftime("%Y-%m-%d")))
        reg.verify_chain()
        print(f"LOCKED EvidenceBench generation spec v0.1 {pid}")
    return pid


def generate() -> dict:
    import psycopg2
    from v3.evidence import _accession
    pid = register()
    items = []
    with psycopg2.connect("dbname=yuclaw_events") as cn:
        cn.set_session(readonly=True)
        with cn.cursor() as cur:
            cur.execute("""SELECT event_id, ticker, event_type,
                       source_publish_time::date, source_url, raw_excerpt,
                       content_hash, available_as_of::date
                FROM events WHERE event_status='accepted'
                  AND available_as_of > now() - interval '7 days'
                ORDER BY event_id""")
            rows = cur.fetchall()
            cur.execute("""SELECT DISTINCT ON (ticker, signal_time::date)
                       ticker, signal_time::date, signal_label
                FROM signal_snapshots WHERE is_backfill=false
                  AND signal_time > now() - interval '7 days'
                ORDER BY ticker, signal_time::date, signal_time DESC""")
            labels = cur.fetchall()
    n_skipped = 0
    for eid, tk, etype, fdate, url, excerpt, chash, avail in rows:
        acc = _accession(eid, url)
        if not acc:
            n_skipped += 1
            continue
        items.append({
            "item_id": f"T1_{eid}", "template": "T1",
            "question": f"What did {tk} disclose on {fdate} per "
                        f"accession {acc}?",
            "key": {"excerpt": (excerpt or "")[:400],
                    "source_hash": chash, "accession": acc}})
        items.append({
            "item_id": f"T2_{eid}", "template": "T2",
            "question": f"Which event type did YUCLAW classify for "
                        f"{tk}'s filing {acc}?",
            "key": {"event_type": etype}})
    for tk, d, lbl in labels[:150]:
        items.append({
            "item_id": f"T3_{tk}_{d}", "template": "T3",
            "question": f"As of {d}, what was {tk}'s YUCLAW signal "
                        f"label?",
            "key": {"label": lbl}})
    items.sort(key=lambda x: x["item_id"])
    canon = json.dumps(items, sort_keys=True)
    iset_hash = hashlib.sha256(canon.encode()).hexdigest()
    BENCH_DIR.mkdir(exist_ok=True)
    (BENCH_DIR / "items.jsonl").write_text(
        "\n".join(json.dumps(i) for i in items) + "\n")
    meta = {"version": "0.1", "protocol_id": pid,
            "generated": datetime.now(timezone.utc).isoformat(),
            "window": "trailing 7 days (post-cutoff, regenerated weekly)",
            "n_items": len(items),
            "n_events_skipped_no_accession": n_skipped,
            "item_set_hash": iset_hash,
            "scoring": "grounded/exact correct 1.0 · 'cannot verify' "
                       "0.25 · anything else 0.0 — abstention outscores "
                       "fabrication by construction",
            "positioning": "groundedness, not prediction",
            "not_advice": "Research and education only — not investment "
                          "advice."}
    (BENCH_DIR / "meta.json").write_text(json.dumps(meta, indent=1))
    print(f"[bench] {len(items)} items · set hash {iset_hash[:16]} · "
          f"{n_skipped} events skipped (no accession, disclosed)")
    return meta


_norm_re = re.compile(r"[^a-z0-9 ]+")


def _norm(s: str) -> str:
    return _norm_re.sub(" ", (s or "").lower()).strip()


def score(pred_path: str, label: str) -> dict:
    items = [json.loads(l) for l in
             (BENCH_DIR / "items.jsonl").read_text().splitlines()]
    preds = json.loads(Path(pred_path).read_text())
    per_type: dict[str, list] = {}
    for it in items:
        ans = preds.get(it["item_id"], "")
        a = _norm(ans)
        if a == _norm(ABSTAIN):
            s = 0.25
        elif it["template"] == "T1":
            key_toks = set(_norm(it["key"]["excerpt"]).split())
            ans_toks = set(a.split())
            overlap = (len(key_toks & ans_toks) / len(key_toks)
                       if key_toks else 0)
            s = 1.0 if (overlap >= 0.5 or
                        it["key"]["accession"] in ans) else 0.0
        elif it["template"] == "T2":
            s = 1.0 if a == _norm(it["key"]["event_type"]) else 0.0
        else:
            s = 1.0 if a == _norm(it["key"]["label"]) else 0.0
        per_type.setdefault(it["template"], []).append(s)
    out = {"label": label,
           "scored": datetime.now(timezone.utc).isoformat(),
           "n_items": len(items),
           "aggregate": round(sum(sum(v) for v in per_type.values())
                              / max(len(items), 1), 4),
           "per_type": {k: round(sum(v) / len(v), 4)
                        for k, v in sorted(per_type.items())},
           "abstentions": sum(1 for it in items
                              if _norm(preds.get(it["item_id"], ""))
                              == _norm(ABSTAIN)),
           "scoring_rule": "correct 1.0 · 'cannot verify' 0.25 · else "
                           "0.0 (abstention outscores fabrication)"}
    return out


def selfscore() -> dict:
    """Answers read from the same corpus the items came from — a format
    demonstration ONLY, loudly labeled; nothing is claimed."""
    items = [json.loads(l) for l in
             (BENCH_DIR / "items.jsonl").read_text().splitlines()]
    preds = {}
    for it in items:
        k = it["key"]
        preds[it["item_id"]] = (k.get("excerpt") or k.get("event_type")
                                or k.get("label"))
    tmp = BENCH_DIR / "_self_preds.json"
    tmp.write_text(json.dumps(preds))
    res = score(str(tmp),
                "YUCLAW extraction stack — SELF-EVALUATION (answers read "
                "from the same corpus; format demonstration, nothing "
                "claimed)")
    tmp.unlink()
    (BENCH_DIR / "leaderboard.json").write_text(json.dumps(
        {"note": "this row is waiting for your model",
         "rows": [res]}, indent=1))
    print(f"[bench] self-evaluation aggregate {res['aggregate']} "
          f"(format demo; loudly labeled)")
    return res


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "generate"
    if cmd == "generate":
        generate()
    elif cmd == "score":
        print(json.dumps(score(sys.argv[2], sys.argv[3] if
                                len(sys.argv) > 3 else "unlabeled"),
                         indent=1))
    elif cmd == "selfscore":
        selfscore()
    else:
        print("usage: generate|score PREDS.json LABEL|selfscore")
        sys.exit(2)

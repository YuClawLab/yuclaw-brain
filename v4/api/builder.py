"""
v4/api/builder.py — the single ResearchResponse assembler.

EVERY v4 entry point (REST, MCP v2, SDK, CLI, Memo Generator, agent wrappers)
calls `build_response()`. There is exactly one place that maps v3 DB state →
the locked schema, so the contract can never drift between surfaces.

Closes the 7 data gaps from docs/v4/migration.md:
  1. component anatomy   — persisted `signal_snapshots.component_anatomy` (Q5) if present,
                           else recomputed via v3.signal.composite.compose_at(); snapshot's
                           9 stored scores remain authoritative for Component.score.
  2. composite_confidence — persisted column (Q5) or from compose_at; degraded fallback = mean evidence conf.
  3. signal-level ledger_hash — ResearchResponse.with_sealed_ledger_hash() (self-computed SHA-256, Q3).
  4. evidence.accession_number — derived from source_url (same regex as the 2026-05-30 migration).
  5. evidence.ledger_hash — events.content_hash.
  6. compliance provenance — model_id/prompt_version = dominant model across the (non-insider) evidence.
  7. confidence.grade + limitations — pure functions of in-response data.

Q1 RISK_ALERT overlay, Q2 score gating, Q3 ledger_anchor_url all applied here.
Read-only over v3 (events / events_raw / SourceLock untouched).
"""
from __future__ import annotations

import re
import subprocess
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import psycopg2
import psycopg2.extras

from v3.signal.base import COMPONENT_WEIGHTS
from v4.api.schema import (
    Compliance,
    Component,
    Confidence,
    DEFAULT_LIMITATIONS,
    COMPONENT_NAMES,
    Evidence,
    ResearchResponse,
    SignalLabel,
)

DSN = "dbname=yuclaw_events"
DEFAULT_N_EVIDENCE = 10

# Q1 — risk overlay: these event types, when recent, force RISK_ALERT regardless of score.
RISK_OVERLAY_EVENT_TYPES = {"REGULATORY_ACTION", "LAWSUIT"}
RISK_OVERLAY_WINDOW_DAYS = 30

# Insider/Form-4 events are tracked separately and are NOT part of the composite,
# so they are excluded from the evidence array (keeps the response internally
# consistent with the standing limitation about Form 4).
INSIDER_EVENT_TYPES = {"INSIDER_BUY", "INSIDER_SELL"}

# Default extraction provenance when there is no LLM-extracted evidence.
_DEFAULT_MODEL_ID = "yuclaw-llm-70b"
_DEFAULT_PROMPT_VERSION = "v2"
# Deterministic (non-LLM) extractors — compliance.model_id should name the research
# (LLM) model, not these. Form 4 events are parsed deterministically and feed C6
# under a cap, but the signal's narrative extraction is the LLM chain.
_DETERMINISTIC_MODELS = {"deterministic-xml-parser"}

_COMPONENT_COLS = {
    "c1": "c1_price_momentum", "c2": "c2_volume_confirm", "c3": "c3_sector_velocity",
    "c4": "c4_macro_regime", "c5": "c5_oil_rates_fx", "c6": "c6_event_impact",
    "c7": "c7_peer_correlation", "c8": "c8_cascade_effect", "c9": "c9_model_trust",
}
_ACC_RE = re.compile(r"/data/\d+/(\d{18})/")


# --------------------------------------------------------------------------- #
# small helpers
# --------------------------------------------------------------------------- #
def _accession_from_url(url: str) -> Optional[str]:
    m = _ACC_RE.search(url or "")
    if not m:
        return None
    a = m.group(1)
    return f"{a[:10]}-{a[10:12]}-{a[12:]}"


def _clip(x: Optional[float], lo: float, hi: float, default: float = 0.0) -> float:
    if x is None:
        return default
    return max(lo, min(hi, float(x)))


def _ledger_anchor_url(ticker: str, date_str: str) -> Optional[str]:
    """Best-effort permalink to the git-anchored Verified Research Ledger entry (Q3).

    Returns None if the ledger repo/remote/entry isn't resolvable yet — the field
    is optional and excluded from the content hash.
    """
    try:
        from v3.proof.ledger import LEDGER_REPO_DIR, LEDGER_FILE
        repo = Path(LEDGER_REPO_DIR)
        if not (repo / ".git").exists() or not Path(LEDGER_FILE).exists():
            return None
        rel = str(Path(LEDGER_FILE).relative_to(repo))
        remote = subprocess.run(["git", "config", "--get", "remote.origin.url"],
                                cwd=str(repo), capture_output=True, text=True, check=False)
        commit = subprocess.run(["git", "log", "-1", "--pretty=format:%H", "--", rel],
                                cwd=str(repo), capture_output=True, text=True, check=False)
        url = remote.stdout.strip()
        sha = commit.stdout.strip()
        if not url or not sha:
            return None
        # normalize git@github.com:org/repo.git or https://github.com/org/repo(.git) → https base
        if url.startswith("git@"):
            url = "https://" + url[len("git@"):].replace(":", "/", 1)
        if url.endswith(".git"):
            url = url[:-4]
        return f"{url}/blob/{sha}/{rel}#{ticker.upper()}-{date_str}"
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# core stages
# --------------------------------------------------------------------------- #
def _fetch_snapshot(cur, ticker: str, as_of: Optional[datetime]) -> Optional[dict]:
    if as_of is None:
        cur.execute(
            """SELECT * FROM signal_snapshots
               WHERE ticker = %s AND is_backfill = false
               ORDER BY signal_time DESC LIMIT 1""",
            (ticker,),
        )
    else:
        cur.execute(
            """SELECT * FROM signal_snapshots
               WHERE ticker = %s AND available_as_of <= %s
               ORDER BY signal_time DESC LIMIT 1""",
            (ticker, as_of),
        )
    row = cur.fetchone()
    return dict(row) if row else None


def _resolve_anatomy(row: dict, ticker: str, as_of: datetime, conn) -> tuple[dict, Optional[float]]:
    """Return ({cid: {confidence, rationale, evidence_ids, not_implemented}}, composite_confidence).

    Prefers persisted anatomy (Q5). Falls back to compose_at() recompute, then degraded.
    """
    persisted = row.get("component_anatomy")
    if persisted:
        cc = row.get("composite_confidence")
        return persisted, (float(cc) if cc is not None else None)

    try:
        from v3.signal.composite import compose_at
        res = compose_at(ticker, as_of, conn=conn)
        anatomy: dict[str, Any] = {}
        for cid, c in res.get("components", {}).items():
            details = c.get("details") or {}
            # C6 uses 'top_contributors', C8 uses 'top_cascades' (see snapshot_writer._evidence_event_ids).
            eids = [ctr["event_id"]
                    for key in ("top_contributors", "top_cascades", "contributors")
                    for ctr in (details.get(key) or [])
                    if isinstance(ctr, dict) and ctr.get("event_id")]
            anatomy[cid] = {
                "confidence": c.get("confidence"),
                "rationale": c.get("rationale", "") or "",
                "evidence_ids": eids,
                "not_implemented": bool(c.get("not_implemented", False)),
            }
        return anatomy, res.get("composite_confidence")
    except Exception:
        return {}, None


def _fetch_evidence(cur, ticker: str, contributor_ids: set[str], n: int) -> list[dict]:
    """Top-N non-insider accepted events UNION any component-contributor events.

    The union guarantees every Component.evidence_id resolves into `evidence`
    (schema invariant) and gives the memo every event that fed a component.
    """
    cur.execute(
        """SELECT event_id, event_type, direction, magnitude, available_as_of,
                  raw_excerpt, source_url, llm_confidence, cascade_depth,
                  content_hash, llm_model, prompt_version
           FROM events
           WHERE ticker = %s AND event_status = 'accepted'
             AND event_type <> ALL(%s)
           ORDER BY magnitude * llm_confidence DESC
           LIMIT %s""",
        (ticker, list(INSIDER_EVENT_TYPES), n),
    )
    rows = {r["event_id"]: dict(r) for r in cur.fetchall()}

    missing = [eid for eid in contributor_ids if eid not in rows]
    if missing:
        cur.execute(
            """SELECT event_id, event_type, direction, magnitude, available_as_of,
                      raw_excerpt, source_url, llm_confidence, cascade_depth,
                      content_hash, llm_model, prompt_version
               FROM events WHERE event_id = ANY(%s)""",
            (missing,),
        )
        for r in cur.fetchall():
            rows[r["event_id"]] = dict(r)
    return list(rows.values())


def _to_evidence(row: dict) -> Evidence:
    return Evidence(
        event_id=row["event_id"],
        event_type=row["event_type"],
        source_url=row["source_url"],
        accession_number=_accession_from_url(row["source_url"]),
        ledger_hash=row["content_hash"],
        available_as_of=row["available_as_of"],
        raw_excerpt=row.get("raw_excerpt"),
        direction=row.get("direction"),
        magnitude=(float(row["magnitude"]) if row.get("magnitude") is not None else None),
        llm_confidence=(float(row["llm_confidence"]) if row.get("llm_confidence") is not None else None),
        cascade_depth=row.get("cascade_depth"),
    )


# --------------------------------------------------------------------------- #
# public entry point
# --------------------------------------------------------------------------- #
def build_response(
    ticker: str,
    as_of: Optional[datetime] = None,
    *,
    include_score: bool = False,
    n_evidence: int = DEFAULT_N_EVIDENCE,
    dsn: str = DSN,
    conn: Optional[Any] = None,
) -> ResearchResponse:
    """Assemble the unified ResearchResponse for `ticker`.

    as_of=None → latest live snapshot; as_of=<dt> → most recent at-or-before (replay).
    include_score (Q2): REST/MCP pass False by default (opt-in), SDK/CLI pass True.
    Raises LookupError if no snapshot exists for the ticker.
    """
    ticker = ticker.upper()
    own_conn = conn is None
    if own_conn:
        conn = psycopg2.connect(dsn)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            snap = _fetch_snapshot(cur, ticker, as_of)
            if snap is None:
                raise LookupError(f"no snapshot for {ticker}"
                                  + (f" at or before {as_of.isoformat()}" if as_of else ""))

            pit = snap["available_as_of"]  # point-in-time the signal is valid as of
            anatomy, composite_conf = _resolve_anatomy(snap, ticker, pit, conn)

            contributor_ids: set[str] = set()
            for a in anatomy.values():
                contributor_ids.update(a.get("evidence_ids") or [])

            ev_rows = _fetch_evidence(cur, ticker, contributor_ids, n_evidence)
            evidence = [_to_evidence(r) for r in ev_rows]
            evidence_ids_present = {e.event_id for e in evidence}

        # --- components (snapshot scores authoritative; anatomy enriches) ---
        components: list[Component] = []
        for cid, col in _COMPONENT_COLS.items():
            a = anatomy.get(cid, {})
            snap_score = snap.get(col)
            implemented = not a.get("not_implemented", snap_score is None)
            eids = [e for e in (a.get("evidence_ids") or []) if e in evidence_ids_present]
            components.append(Component(
                key=cid, name=COMPONENT_NAMES[cid],
                score=_clip(snap_score, -1.0, 1.0, 0.0),
                confidence=_clip(a.get("confidence"), 0.0, 1.0, 0.0),
                weight=COMPONENT_WEIGHTS[cid],
                rationale=a.get("rationale", "") or "",
                evidence_ids=eids,
                implemented=implemented,
            ))

        # --- Q1 RISK_ALERT overlay ---
        score_label = snap["signal_label"]
        signal = SignalLabel(score_label)
        overlay: Optional[str] = None
        cutoff = pit - timedelta(days=RISK_OVERLAY_WINDOW_DAYS)
        risk_hits = sorted({
            e.event_type for e in evidence
            if e.event_type in RISK_OVERLAY_EVENT_TYPES and e.available_as_of >= cutoff
        })
        if risk_hits:
            signal = SignalLabel.RISK_ALERT
            overlay = f"RISK_ALERT: {'/'.join(risk_hits)} within {RISK_OVERLAY_WINDOW_DAYS}d"

        # --- confidence + grade ---
        if composite_conf is None:
            confs = [e.llm_confidence for e in evidence if e.llm_confidence is not None]
            composite_conf = round(sum(confs) / len(confs), 4) if confs else 0.0
        confidence = Confidence(
            value=_clip(composite_conf, 0.0, 1.0, 0.0),
            grade=Confidence.grade_for(composite_conf, evidence),
            basis=f"composite_confidence={round(composite_conf,4)}, "
                  f"{sum((e.llm_confidence or 0) >= 0.7 for e in evidence)} strong / {len(evidence)} evidence",
        )

        # --- limitations (default + per-signal) ---
        limitations = list(DEFAULT_LIMITATIONS)
        stubs = [c.key for c in components if not c.implemented]
        if stubs:
            limitations.append(f"Components {', '.join(stubs)} are stubs in this build (confidence 0).")
        if overlay:
            limitations.append("Label was set by the risk overlay and intentionally diverges from the composite score.")
        if snap.get("is_backfill"):
            limitations.append("This is a backfilled/historical snapshot, not a live signal.")

        # --- compliance provenance: dominant LLM (non-deterministic) model among evidence ---
        llm_rows = [r for r in ev_rows
                    if r.get("llm_model") and r["llm_model"] not in _DETERMINISTIC_MODELS]
        models = Counter(r["llm_model"] for r in llm_rows)
        prompts = Counter(r["prompt_version"] for r in llm_rows if r.get("prompt_version"))
        model_id = models.most_common(1)[0][0] if models else _DEFAULT_MODEL_ID
        prompt_version = prompts.most_common(1)[0][0] if prompts else _DEFAULT_PROMPT_VERSION

        resp = ResearchResponse(
            ticker=ticker,
            as_of=pit,
            replay_id=snap["snapshot_id"],
            signal=signal,
            signal_overlay=overlay,
            score=(round(float(snap["total_score"]), 4) if include_score else None),
            is_backfill=bool(snap.get("is_backfill")),
            components=components,
            evidence=evidence,
            confidence=confidence,
            limitations=limitations,
            ledger_hash="0" * 64,  # sealed below
            ledger_anchor_url=_ledger_anchor_url(ticker, pit.date().isoformat()),
            compliance=Compliance(model_id=model_id, prompt_version=prompt_version),
        )
        return resp.with_sealed_ledger_hash()
    finally:
        if own_conn:
            conn.close()


__all__ = ["build_response", "DSN", "DEFAULT_N_EVIDENCE"]

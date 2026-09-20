"""Append-only, digest-chained workspace log (`commitments.jsonl`) with operation identifiers.

Rules the store enforces, not merely documents:
  * every durable event is one newline-terminated line; its `event_hash` covers the whole record and `prev_hash`
    chains it to the previous line — a rewritten, reordered or deleted line breaks the chain and the store refuses
    to serve (StoreIntegrityError), it never "repairs" history;
  * a write is refused while a torn tail (bytes after the last newline) exists; `recover()` preserves the torn
    bytes in a side file, truncates ONLY those non-durable bytes, and records a RECOVERY event naming their digest;
  * every write carries a caller-chosen `op_id`; a retry with the same op_id and the same content returns the
    existing event (no duplicate), a different content under the same op_id is a conflict (E_OP_CONFLICT); the
    whole read-decide-append sequence of a write runs under one exclusive lock (threads and processes), so
    concurrent retries of one operation and concurrent first writes serialize instead of interleaving;
  * three times are kept apart on every event: `source_available_as_of` (when the source became public),
    `observed_at` (when this workspace saw it) and `recorded_at` (local action time). As-of views are cut by
    source availability for source-bearing events, so later information is never shown as known earlier.
The location boundary is the v7 one (v3.receipts.storage.resolve_store_root): never inside a public docs tree.
"""
from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import os
import re
import secrets
import threading
from datetime import datetime, timezone

from v3.receipts.contracts import ContractError, canonical_json, digest, format_ts
from v3.receipts.storage import resolve_store_root
from v8.workbench import availability, calc, schema
from v8.workbench.modkinds import MODULE_KINDS

FORMAT = "yuclaw-commitment-workspace/1"
LOG = "commitments.jsonl"
GENESIS = "0" * 64
KINDS = ("SOURCE_REGISTERED", "CLAIM_FROZEN", "CLAIM_REVISED", "SOURCE_CORRECTED", "CLAIM_WITHDRAWN", "OUTCOME_RECORDED",
         "ADJUDICATION_RECORDED", "RESEARCH_NOTE_RECORDED", "SCI_REPLAY_RECORDED", "EXPORT_BUILT", "PACKET_VERIFIED", "RECOVERY", availability.KIND) + MODULE_KINDS
# MODULE_KINDS (V8-014): SHD / EVO / COM / PRC and the local principal registry. Additive and workspace-level (claim_id None): a claim's
# derivation, its export and the verification of earlier exports never read them. See v8/workbench/modkinds.py.
# SOURCE_AVAILABILITY_CORRECTED (V8-011, TIM-08): a linked correction of WHEN a registered source became public. Workspace-level
# like the registration it names. It carries no source availability of its own, so an as-of view places it by its local action
# time: it takes effect for cutoffs at or after that time and is only listed — as a later correction — before it. The
# registration, the passage bytes, digests, observation times, claim versions, outcomes and adjudications are never edited.
# SCI_REPLAY_RECORDED (V8-005): a bounded science-journal input replayed through the adapted kernel — the input (data, never
# code), its identity, the recomputed report or the specific refusal, link verification and the replay status. Linked to a
# financial claim when the input names one; otherwise workspace-level (claim_id None). Never changes any claim.
# RESEARCH_NOTE_RECORDED (V8-004 §3): authored text about a frozen claim. Never a version, never an amendment: the claim's
# range, metric, currency, basis, period, sources and digests are untouched. A correction is a NEW note event that names the
# note it supersedes; the earlier text stays in its own event. Notes carry no source availability, so an as-of view cuts them
# by their local action time: a note written today never appears as contemporaneous at an earlier research cutoff.
_OP = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
MAX_LINE = 1 << 20


class StoreIntegrityError(ContractError):
    def __init__(self, code: str, detail: str = ""):
        self.code = code
        super().__init__(code + (f": {detail}" if detail else ""))


def now_ts() -> str:
    return format_ts(datetime.now(timezone.utc))


def new_op_id(prefix: str = "op") -> str:
    return f"{prefix}:{secrets.token_hex(12)}"


def _line_hash(event_without_hash: dict) -> str:
    return hashlib.sha256(canonical_json(event_without_hash)).hexdigest()


class Workspace:
    def __init__(self, root, *, create: bool = True):
        self.root = resolve_store_root(root, create=create)
        self.log = self.root / LOG
        self.lock_path = self.root / ".lock"
        self.exports = self.root / "exports"
        self.imports = self.root / "imports"
        self.meta_path = self.root / "workspace.json"
        self._rlock = threading.RLock(); self._depth = 0; self._fd = None
        for d in (self.exports, self.imports):
            d.mkdir(exist_ok=True)
            with contextlib.suppress(OSError):
                os.chmod(d, 0o700)
        if not self.meta_path.exists():
            self.meta_path.write_text(json.dumps({"format": FORMAT, "workspace_id": "ws-" + secrets.token_hex(6), "created_at": now_ts()}, indent=1, sort_keys=True) + "\n")
            with contextlib.suppress(OSError):
                os.chmod(self.meta_path, 0o600)
        self.meta = json.loads(self.meta_path.read_text())
        if self.meta.get("format") != FORMAT:
            raise StoreIntegrityError("E_FORMAT", f"workspace format {self.meta.get('format')!r}")

    # ------------------------------------------------------------------ primitives
    @contextlib.contextmanager
    def _locked(self):
        """Exclusive workspace lock: an in-process re-entrant lock (threads of one server) around the file lock
        (other processes). Every write API holds it from its first read to the append, so a retry of the same
        operation and a concurrent first write can never interleave between "read the state" and "append"."""
        with self._rlock:
            if self._depth == 0:
                self._fd = os.open(self.lock_path, os.O_RDWR | os.O_CREAT, 0o600)
                fcntl.flock(self._fd, fcntl.LOCK_EX)
            self._depth += 1
            try:
                yield
            finally:
                self._depth -= 1
                if self._depth == 0:
                    fcntl.flock(self._fd, fcntl.LOCK_UN); os.close(self._fd); self._fd = None

    def _raw(self) -> bytes:
        return self.log.read_bytes() if self.log.exists() else b""

    def load(self) -> dict:
        """{'events': [...], 'torn_tail': None | {'bytes','sha256','offset'}, 'tip': hash, 'durable_bytes': n}.
        Raises StoreIntegrityError for any complete line that is not a valid chained event."""
        raw = self._raw()
        last_nl = raw.rfind(b"\n")
        durable, tail = (raw[:last_nl + 1], raw[last_nl + 1:]) if last_nl >= 0 else (b"", raw)
        events, prev, seq = [], GENESIS, 0
        for n, line in enumerate(durable.split(b"\n")[:-1], start=1):
            if len(line) > MAX_LINE:
                raise StoreIntegrityError("E_LINE_TOO_LONG", f"line {n}")
            try:
                ev = json.loads(line.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                raise StoreIntegrityError("E_CORRUPT_LINE", f"line {n} is not JSON") from None
            if not isinstance(ev, dict) or set(ev) < {"seq", "kind", "claim_id", "op_id", "payload", "time", "actor", "prev_hash", "event_hash"}:
                raise StoreIntegrityError("E_CORRUPT_LINE", f"line {n} lacks event fields")
            h = ev["event_hash"]
            body = {k: v for k, v in ev.items() if k != "event_hash"}
            if not _HEX64.match(str(h)) or _line_hash(body) != h:
                raise StoreIntegrityError("E_HASH", f"line {n}: event_hash does not match its content (history rewritten?)")
            if ev["prev_hash"] != prev:
                raise StoreIntegrityError("E_CHAIN", f"line {n}: prev_hash {str(ev['prev_hash'])[:12]} != tip {prev[:12]} (line deleted, reordered or inserted?)")
            if ev["seq"] != seq + 1:
                raise StoreIntegrityError("E_SEQ", f"line {n}: seq {ev['seq']} != {seq + 1}")
            if canonical_json(ev) != line and json.dumps(ev, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode() != line:
                raise StoreIntegrityError("E_NONCANONICAL", f"line {n} is not canonical JSON")
            events.append(ev); prev, seq = h, ev["seq"]
        torn = None
        if tail:
            torn = {"bytes": len(tail), "sha256": hashlib.sha256(tail).hexdigest(), "offset": len(durable)}
        return {"events": events, "torn_tail": torn, "tip": prev, "durable_bytes": len(durable)}

    def status(self) -> dict:
        try:
            st = self.load()
            return {"workspace_id": self.meta["workspace_id"], "events": len(st["events"]), "tip": st["tip"], "torn_tail": st["torn_tail"], "integrity": "TORN_TAIL" if st["torn_tail"] else "OK", "claims": sorted(self.claim_ids(st["events"]))}
        except StoreIntegrityError as exc:
            return {"workspace_id": self.meta["workspace_id"], "integrity": exc.code, "detail": str(exc), "events": None, "claims": []}

    def recover(self) -> dict:
        """Preserve a torn tail in a side file, truncate only those non-durable bytes, and append a RECOVERY event."""
        with self._locked():
            st = self.load()
            torn = st["torn_tail"]
            if torn is None:
                return {"recovered": False, "reason": "no torn tail"}
            raw = self._raw()
            side = self.root / f"{LOG}.torn.{torn['sha256'][:16]}"
            side.write_bytes(raw[torn["offset"]:])
            with contextlib.suppress(OSError):
                os.chmod(side, 0o600)
            fd = os.open(self.log, os.O_RDWR)
            try:
                os.ftruncate(fd, torn["offset"]); os.fsync(fd)
            finally:
                os.close(fd)
            ev, dup = self._append_unlocked("RECOVERY", None, {"torn_bytes": torn["bytes"], "torn_sha256": torn["sha256"], "preserved_as": side.name,
                                                               "meaning": "an interrupted append left bytes without a terminating newline; they were never a durable event; nothing durable was changed"},
                                            op_id=f"recovery:{torn['sha256'][:24]}", observed_at=None, source_available_as_of=None, actor="workspace")
            return {"recovered": True, "torn": torn, "event": ev}

    def _append_unlocked(self, kind, claim_id, payload, *, op_id, observed_at, source_available_as_of, actor):
        if kind not in KINDS:
            raise ContractError(f"unknown event kind {kind!r}")
        if not isinstance(op_id, str) or not _OP.match(op_id):
            raise ContractError("op_id: identifier of 8–128 characters [A-Za-z0-9._:-] required (an operation identifier makes a retry safe)")
        st = self.load()
        if st["torn_tail"]:
            raise StoreIntegrityError("E_TORN_TAIL", "an interrupted write left a torn tail; run recovery before writing (nothing durable is lost)")
        pdig = digest(payload)
        for ev in st["events"]:
            if ev["op_id"] == op_id:
                if ev["kind"] == kind and digest(ev["payload"]) == pdig:
                    return ev, True
                raise StoreIntegrityError("E_OP_CONFLICT", f"op_id {op_id!r} was already used for a different operation; a retry must repeat the same content")
        if source_available_as_of is not None:
            schema.parse_ts(source_available_as_of)
        rec_at = now_ts()
        body = {"seq": len(st["events"]) + 1, "kind": kind, "claim_id": claim_id, "op_id": op_id, "payload": payload,
                "time": {"source_available_as_of": source_available_as_of, "observed_at": observed_at or rec_at, "recorded_at": rec_at},
                "actor": actor, "prev_hash": st["tip"]}
        body["event_hash"] = _line_hash(body)
        line = canonical_json(body) + b"\n"; created = not self.log.exists()
        fd = os.open(self.log, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        try:
            n = os.write(fd, line)
            if n != len(line):
                raise StoreIntegrityError("E_SHORT_WRITE", f"{n} of {len(line)} bytes")
            os.fsync(fd)
        finally:
            os.close(fd)
        if created:                                                       # the first event also needs a durable NAME for the journal file
            dfd = os.open(self.root, os.O_RDONLY)
            try:
                os.fsync(dfd)
            finally:
                os.close(dfd)
        with contextlib.suppress(OSError):
            os.chmod(self.log, 0o600)
        return body, False

    def append(self, kind, claim_id, payload, *, op_id, observed_at=None, source_available_as_of=None, actor="owner"):
        with self._locked():
            return self._append_unlocked(kind, claim_id, payload, op_id=op_id, observed_at=observed_at, source_available_as_of=source_available_as_of, actor=actor)

    # ------------------------------------------------------------------ reads
    @staticmethod
    def claim_ids(events) -> set:
        """Claims that exist here = claims frozen here. A verification event names the packet's claim id, but an imported
        packet never becomes a claim of this workspace."""
        return {e["claim_id"] for e in events if e["kind"] == "CLAIM_FROZEN"}

    @staticmethod
    def visible(ev: dict, as_of: str | None, idx: dict | None = None) -> bool:
        """`idx` is availability.index(events, as_of): with it, an event citing a source whose availability was corrected at
        or before the cutoff is cut by the corrected value; a correction recorded after the cutoff changes nothing here."""
        if as_of is None:
            return True
        cut = schema.parse_ts(as_of)
        src = availability.effective_stamp(ev, idx)
        stamp = src if src is not None else ev["time"]["recorded_at"]
        return schema.parse_ts(stamp) <= cut

    def events(self, claim_id=None, as_of=None) -> list[dict]:
        evs = self.load()["events"]
        idx = availability.index(evs, as_of) if as_of is not None else None
        return [e for e in evs if (claim_id is None or e["claim_id"] == claim_id) and self.visible(e, as_of, idx)]

    def claim_state(self, claim_id: str, as_of: str | None = None) -> dict | None:
        evs = self.load()["events"]; idx = availability.index(evs, as_of)
        st = self._derive(claim_id, [e for e in evs if e["claim_id"] == claim_id and self.visible(e, as_of, idx)], as_of)
        return None if st is None else availability.attach(st, idx)

    def _state_for(self, claim_id: str, prior: dict | None) -> dict | None:
        """The state a write is computed against: current, or — for a retry — the state as it was just before the
        prior event with the same op_id, so a genuine retry reproduces the same payload and append() answers it as a
        duplicate, while different content under the same op_id is a conflict."""
        if prior is None:
            return self.claim_state(claim_id)
        evs = [e for e in self.load()["events"] if e["seq"] < prior["seq"]]
        st = self._derive(claim_id, [e for e in evs if e["claim_id"] == claim_id], None)
        return None if st is None else availability.attach(st, availability.index(evs))

    def _derive(self, claim_id: str, evs: list[dict], as_of: str | None) -> dict | None:
        versions, withdrawn, outcome, adjs, exports, verifs, sources, notes, sci = [], None, None, [], [], [], [], [], []
        for e in evs:
            p = e["payload"]; k = e["kind"]
            if k == "SOURCE_REGISTERED":
                sources.append(dict(p, event_hash=e["event_hash"], time=e["time"]))
            elif k == "RESEARCH_NOTE_RECORDED":
                notes.append(dict(p, event_hash=e["event_hash"], time=e["time"], superseded_by=None))
            elif k == "SCI_REPLAY_RECORDED":
                sci.append(dict(p, event_hash=e["event_hash"], time=e["time"]))
            elif k == "CLAIM_FROZEN":
                versions.append({"version_id": p["version_id"], "type": "FROZEN", "claim": dict(p["claim"], _digest=p["claim_digest"]), "event_hash": e["event_hash"], "time": e["time"], "reason": None, "notes": None})
            elif k in ("CLAIM_REVISED", "SOURCE_CORRECTED"):
                versions.append({"version_id": p["version_id"], "type": p["type"], "claim": dict(p["claim"], _digest=p["claim_digest"]), "event_hash": e["event_hash"], "time": e["time"],
                                 "reason": p.get("reason"), "notes": p.get("notes"), "supersedes": p.get("supersedes")})
            elif k == "CLAIM_WITHDRAWN":
                withdrawn = {"revision_id": p["version_id"], "source": p["source"], "reason": p.get("reason"), "supersedes": p.get("supersedes"), "event_hash": e["event_hash"], "time": e["time"]}
            elif k == "OUTCOME_RECORDED":
                outcome = dict(p["outcome"], _digest=p["outcome_digest"], _event_hash=e["event_hash"], _time=e["time"])
            elif k == "ADJUDICATION_RECORDED":
                adjs.append(dict(p, event_hash=e["event_hash"], time=e["time"]))
            elif k == "EXPORT_BUILT":
                exports.append(dict(p, event_hash=e["event_hash"], time=e["time"]))
            elif k == "PACKET_VERIFIED":
                verifs.append(dict(p, event_hash=e["event_hash"], time=e["time"]))
        if not versions:
            return None
        by_id = {n["note_id"]: n for n in notes}
        for n in notes:                                                   # correction chain: the superseded note keeps its text and learns its successor
            if n.get("supersedes_note") and n["supersedes_note"] in by_id:
                by_id[n["supersedes_note"]]["superseded_by"] = n["note_id"]
        return {"claim_id": claim_id, "as_of": as_of, "versions": versions, "withdrawn": withdrawn, "outcome": outcome, "adjudications": adjs,
                "exports": exports, "verifications": verifs, "sources": sources, "events": evs, "current": versions[-1],
                "research_notes": notes, "research_notes_current": [n for n in notes if n["superseded_by"] is None], "sci": sci}

    # ------------------------------------------------------------------ write API (the seven steps)
    def _prior(self, op_id: str) -> dict | None:
        """An earlier event with this op_id, if any: a retry is answered by append() (duplicate or conflict) BEFORE
        any state-based refusal, so a resubmitted form never sees 'already frozen' for its own first success."""
        return next((e for e in self.load()["events"] if e["op_id"] == op_id), None)

    def register_source(self, raw_source: dict, *, op_id: str, observed_at: str | None = None) -> tuple[dict, bool]:
        with self._locked():
            src, reasons = schema.check_source(raw_source)
            if reasons:
                raise ContractError("source cannot be registered: " + "; ".join(reasons))
            sid = f"{src['accession']}:{src['source_hash'][:16]}"
            if self._prior(op_id) is None:
                # Replaying an ingestion or loading a second fixture that cites the same passage must not register the artifact
                # twice (DAT-10): the first registration — and the workspace's first observation of the passage — stands.
                first = next((e for e in self.load()["events"] if e["kind"] == "SOURCE_REGISTERED" and e["payload"]["source_id"] == sid), None)
                if first is not None:
                    if first["payload"]["source"] == src:
                        return first, True
                    differs = sorted(k for k in src if src[k] != first["payload"]["source"].get(k))
                    raise ContractError(f"source cannot be registered: {sid} is already registered with different {', '.join(differs)} (recorded {first['time']['recorded_at']}); a registered source is never edited and the first registration stands — "
                                        "check the values against the original document; nothing was written")
            return self.append("SOURCE_REGISTERED", None, {"source_id": sid, "source": src}, op_id=op_id, observed_at=observed_at, source_available_as_of=src["available_as_of"])

    def correct_source_availability(self, source_id: str, raw: dict, *, expected_prior: str, op_id: str) -> tuple[dict, bool]:
        """Record a correction of when a registered source became public (V8-011, TIM-08). `expected_prior` is the availability
        the caller was looking at: if another correction landed in between, this one is refused as stale and nothing is
        written. The values are computed against the state the operation first ran on, so a retry with the same op_id
        reproduces the same payload (one durable event) and different content under the same op_id is a conflict."""
        with self._locked():
            prior = self._prior(op_id)
            evs = [e for e in self.load()["events"] if prior is None or e["seq"] < prior["seq"]]
            ent = availability.index(evs).get(source_id)
            if ent is None:
                raise ContractError("source availability cannot be corrected: choose a registered source (step 1); an unregistered passage has no registration to correct")
            corr, reasons = schema.check_availability_correction(raw)
            if reasons:
                raise ContractError("source availability cannot be corrected: " + "; ".join(reasons))
            src = ent["registration"]["payload"]["source"]; last = ent["applied"][-1] if ent["applied"] else ent["registration"]
            if expected_prior != ent["effective"]:
                raise ContractError(f"source availability cannot be corrected: this form was prepared while the availability read {expected_prior or 'nothing'}, but it now reads {ent['effective']} "
                                    f"({last['payload'].get('correction_id', 'the registration')}, recorded {last['time']['recorded_at']}); review that record and choose the source again — nothing was written")
            new, old = schema.parse_ts(corr["corrected_available_as_of"]), schema.parse_ts(ent["effective"])
            if new == old:
                raise ContractError("source availability cannot be corrected: corrected_available_as_of equals the availability already in force (nothing to correct)")
            if new.date().isoformat() < src["filed_at"]:
                raise ContractError(f"source availability cannot be corrected: corrected_available_as_of {corr['corrected_available_as_of']} precedes the source's filing date {src['filed_at']}")
            n = sum(1 for e in evs if e["kind"] == availability.KIND) + 1
            payload = {"correction_id": f"AC{n}", "source_id": source_id, "accession": src["accession"], "source_hash": src["source_hash"],
                       "registration_event": ent["registration"]["event_hash"], "registered_available_as_of": ent["registered"],
                       "prior_available_as_of": ent["effective"], "prior_event": last["event_hash"], "corrected_available_as_of": corr["corrected_available_as_of"],
                       "direction": "EARLIER" if new < old else "LATER", "reason": corr["reason"], "evidence_ref": corr["evidence_ref"], "actor": corr["actor"],
                       "actor_kind": "simulated_test_action" if corr["simulated"] else "attribution_label", "attribution": availability.ATTRIBUTION,
                       "effect_rule": availability.EFFECT_RULE, "changes_source": False, "changes_claim": False}
            return self.append(availability.KIND, None, payload, op_id=op_id, actor="researcher")          # no source availability of its own: placed by its recorded (local action) time

    def freeze_claim(self, raw_claim: dict, *, op_id: str, observed_at: str | None = None) -> tuple[dict, bool]:
        with self._locked():
            claim = schema.validate_claim(raw_claim)
            prior = self._prior(op_id)
            if self._state_for(claim["claim_id"], prior) is not None:
                raise ContractError(f"claim_id {claim['claim_id']!r} is already frozen; a change is an amendment (REVISED / WITHDRAWN / CORRECTED_SOURCE), never a second freeze")
            d = schema.claim_digest(claim)
            return self.append("CLAIM_FROZEN", claim["claim_id"], {"version_id": "V1", "version": 1, "claim": claim, "claim_digest": d},
                               op_id=op_id, observed_at=observed_at, source_available_as_of=claim["source"]["available_as_of"])

    def amend_claim(self, claim_id: str, amend_type: str, *, changes: dict | None, reason: str, source: dict, notes: dict | None = None, op_id: str, observed_at: str | None = None) -> tuple[dict, bool]:
        with self._locked():
            st = self._state_for(claim_id, self._prior(op_id))
            if st is None:
                raise ContractError(f"claim {claim_id!r} is not frozen")
            if st["withdrawn"] is not None:
                raise ContractError(f"claim {claim_id!r} was withdrawn ({st['withdrawn']['revision_id']}); no further amendment is accepted")
            src, reasons = schema.check_source(source)
            if reasons:
                raise ContractError("amendment source invalid: " + "; ".join(reasons))
            cur = st["current"]["claim"]
            if not reason or not isinstance(reason, str):
                raise ContractError("reason: required for every amendment")
            if amend_type == "WITHDRAWN":
                return self.append("CLAIM_WITHDRAWN", claim_id, {"version_id": f"W{len(st['versions'])}", "supersedes": cur["_digest"], "reason": reason, "source": src},
                                   op_id=op_id, observed_at=observed_at, source_available_as_of=src["available_as_of"])
            if amend_type not in ("REVISED", "CORRECTED_SOURCE"):
                raise ContractError("amendment type must be REVISED, WITHDRAWN or CORRECTED_SOURCE")
            allowed = {"range", "basis", "unit", "currency", "statement", "fiscal_period", "scale_as_stated", "metric"}
            changes = changes or {}
            bad = set(changes) - allowed
            if bad:
                raise ContractError(f"amendment may change only {sorted(allowed)}; got {sorted(bad)}")
            new = {k: v for k, v in cur.items() if not k.startswith("_")}
            new.update(changes); new["source"] = src; new["stated_at"] = src["filed_at"]
            claim = schema.validate_claim(new)
            d = schema.claim_digest(claim)
            if d == cur["_digest"]:
                raise ContractError("amendment changes nothing (identical content); record a reason-only note instead")
            n = sum(1 for v in st["versions"] if v["type"] == amend_type) + 1
            vid = f"R{n}" if amend_type == "REVISED" else f"C{n}"
            kind = "CLAIM_REVISED" if amend_type == "REVISED" else "SOURCE_CORRECTED"
            nt = {"explanation_unresolved": (notes or {}).get("explanation_unresolved", ""), "next_evidence": (notes or {}).get("next_evidence", ""),
                  "source_discrepancy": (notes or {}).get("source_discrepancy", "")}      # verbatim, e.g. the amendment restates the prior range differently from the original source; never silently corrected
            payload = {"version_id": vid, "version": len(st["versions"]) + 1, "type": amend_type, "claim": claim, "claim_digest": d, "supersedes": cur["_digest"], "reason": reason, "notes": nt}
            if amend_type == "CORRECTED_SOURCE":
                payload["supersedes_source"] = {"accession": cur["source"]["accession"], "source_hash": cur["source"]["source_hash"], "retained": True}
            return self.append(kind, claim_id, payload, op_id=op_id, observed_at=observed_at, source_available_as_of=src["available_as_of"])

    def record_outcome(self, claim_id: str, raw_outcome: dict, *, op_id: str, observed_at: str | None = None) -> tuple[dict, bool]:
        with self._locked():
            st = self._state_for(claim_id, self._prior(op_id))
            if st is None:
                raise ContractError(f"claim {claim_id!r} is not frozen")
            out = schema.validate_outcome(dict(raw_outcome, claim_id=claim_id))
            payload = {"outcome": out, "outcome_digest": digest(out)}
            if st["outcome"] is not None:
                payload["supersedes"] = st["outcome"]["_digest"]
            return self.append("OUTCOME_RECORDED", claim_id, payload, op_id=op_id, observed_at=observed_at, source_available_as_of=out["source"]["available_as_of"])

    def record_adjudication(self, claim_id: str, *, reviewer: str, rule: str, evidence: list[str], reason: str, conflicts: str, label: str, disputed: bool, op_id: str) -> tuple[dict, bool]:
        with self._locked():
            st = self._state_for(claim_id, self._prior(op_id))
            if st is None:
                raise ContractError(f"claim {claim_id!r} is not frozen")
            if not reviewer or not reason:
                raise ContractError("reviewer identity and reason are required")
            if label not in calc.RESULTS:
                raise ContractError(f"label must be one of {list(calc.RESULTS)}")
            known = {e["event_hash"] for e in st["events"]} | availability.event_hashes(st)
            bad = [h for h in evidence if h not in known]
            if bad:
                raise ContractError(f"evidence must reference event hashes of this claim; unknown: {[b[:12] for b in bad]}")
            computed = calc.adjudicate(st)
            if label != computed["result"] and not disputed:
                raise ContractError(f"the reviewer label {label} differs from the computed result {computed['result']}; record it as DISPUTED with the reason, it is never applied silently")
            payload = {"reviewer": reviewer, "rule": rule, "evidence": evidence, "reason": reason, "conflicts": conflicts or "", "label": label, "disputed": bool(disputed),
                       "computed_result": computed["result"], "computed": {"original": computed["original"]["result"], "revised": None if computed["revised"] is None else computed["revised"]["result"],
                                                                            "comparison_permitted": computed["comparison_permitted"], "reasons": computed["reasons"]},
                       "state_tip": st["events"][-1]["event_hash"]}
            blk = availability.block(st)
            if blk is not None:                                          # what the reviewer was shown beside the as-recorded result; the label rule above is unchanged
                payload["availability_corrected_view"] = {"result": blk["corrected_view"]["result"], "result_changes": blk["corrected_view"]["result_changes"],
                                                          "corrections": [c["correction_id"] for s in blk["sources"] for c in s["corrections"]]}
            return self.append("ADJUDICATION_RECORDED", claim_id, payload, op_id=op_id)

    def record_note(self, claim_id: str, raw_note: dict, *, op_id: str) -> tuple[dict, bool]:
        """A research note on an existing frozen claim (V8-004 §3). Allowed on withdrawn claims and on claims without an
        outcome — it reopens nothing and resolves nothing. The note's identifier is derived from the state the operation
        is computed against, so a retry with the same op_id reproduces the same payload (one durable event) and different
        content under the same op_id is a conflict."""
        with self._locked():
            st = self._state_for(claim_id, self._prior(op_id))
            if st is None:
                raise ContractError(f"claim {claim_id!r} is not frozen; a note needs an existing frozen claim")
            note, reasons = schema.check_note(raw_note)
            if reasons:
                raise ContractError("note cannot be recorded: " + "; ".join(reasons))
            versions = {v["version_id"]: v for v in st["versions"]}
            if note["version_ref"] is not None and note["version_ref"] not in versions:
                raise ContractError(f"note.version_ref: {note['version_ref']!r} is not a version of this claim ({sorted(versions)})")
            vref = note["version_ref"] or st["current"]["version_id"]
            known = {e["event_hash"] for e in st["events"]} | availability.event_hashes(st)
            bad = [h for h in note["evidence"] if h not in known]
            if bad:
                raise ContractError(f"note.evidence must reference event hashes of this claim; unknown: {[b[:12] for b in bad]}")
            sup_event = None
            if note["supersedes_note"] is not None:
                prev = next((n for n in st["research_notes"] if n["note_id"] == note["supersedes_note"]), None)
                if prev is None:
                    raise ContractError(f"note.supersedes_note: {note['supersedes_note']!r} is not a note of this claim")
                if prev["superseded_by"] is not None:
                    raise ContractError(f"note {note['supersedes_note']} was already corrected by {prev['superseded_by']}; correct the latest version of the note")
                sup_event = prev["event_hash"]
            payload = {"note_id": f"N{len(st['research_notes']) + 1}", "category": note["category"], "actor": note["actor"],
                       "actor_kind": "simulated_test_action" if note["simulated"] else "attribution_label",
                       "attribution": "an actor label is attribution; it is not authenticated identity and does not establish independent human review",
                       "unresolved_question": note["unresolved_question"], "next_evidence": note["next_evidence"], "reason": note["reason"],
                       "version_ref": vref, "version_digest": versions[vref]["claim"]["_digest"], "evidence": note["evidence"],
                       "supersedes_note": note["supersedes_note"], "supersedes_event": sup_event, "state_tip": st["events"][-1]["event_hash"],
                       "changes_claim": False}
            return self.append("RESEARCH_NOTE_RECORDED", claim_id, payload, op_id=op_id, actor="researcher")

    def sci_records(self, claim_id: str | None = "*") -> list[dict]:
        """Scientific replay records: all ("*"), workspace-level (None) or those linked to one claim."""
        return [dict(e["payload"], event_hash=e["event_hash"], time=e["time"], claim_id=e["claim_id"]) for e in self.events() if e["kind"] == "SCI_REPLAY_RECORDED" and (claim_id == "*" or e["claim_id"] == claim_id)]

    def record_sci(self, payload: dict, *, claim_id: str | None, op_id: str) -> tuple[dict, bool]:
        """Record a scientific replay (V8-005). The identifier is derived from the state the operation is computed
        against, so a retry with the same op_id reproduces the same payload (one durable event)."""
        with self._locked():
            prior = self._prior(op_id)
            evs = self.load()["events"]
            if prior is not None:
                evs = [e for e in evs if e["seq"] < prior["seq"]]
            if claim_id is not None and self._derive(claim_id, [e for e in evs if e["claim_id"] == claim_id], None) is None:
                raise ContractError(f"claim {claim_id!r} is not frozen; a scientific record can link only to an existing frozen claim")
            n = sum(1 for e in evs if e["kind"] == "SCI_REPLAY_RECORDED") + 1
            body = dict(payload, sci_id=f"S{n}", state_tip=evs[-1]["event_hash"] if evs else GENESIS, changes_claim=False)
            return self.append("SCI_REPLAY_RECORDED", claim_id, body, op_id=op_id, actor="researcher")

    def record_export(self, claim_id: str | None, *, export_id: str, canonical_digest: str, zip_sha256: str, zip_name: str, op_id: str, extra: dict | None = None) -> tuple[dict, bool]:
        with self._locked():
            return self.append("EXPORT_BUILT", claim_id, {"export_id": export_id, "canonical_digest": canonical_digest, "zip_sha256": zip_sha256, "zip_name": zip_name, **(extra or {})}, op_id=op_id)

    def record_verification(self, claim_id: str | None, *, packet_sha256: str, result: str, first_discrepancy: str | None, canonical_digest: str | None, op_id: str) -> tuple[dict, bool]:
        with self._locked():
            return self.append("PACKET_VERIFIED", claim_id, {"packet_sha256": packet_sha256, "result": result, "first_discrepancy": first_discrepancy, "canonical_digest": canonical_digest}, op_id=op_id)


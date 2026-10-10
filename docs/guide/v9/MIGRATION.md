# YUCLAW v9 — Migration and downgrade note

Research and education only. Not investment advice.
Mission: Make financial AI accountable to evidence. Vision: Become the Science Trust Layer for Financial AI.

Covers the 9.0 **candidate** on branch `codex/v9-integration` (HEAD `70a6c8aa`, 9 October 2026), beside the released v8
workbench 8.0.1. 9.0 is not a published release.

## 1. A v8 workspace needs no migration

A v8 workspace (`workspace.json`, `commitments.jsonl`, `exports/`, `imports/`, `private/`) is used by v9 as it is. There is
no conversion step, no schema bump of the v8 journal, and no change to `workspace.json`. The first v9 command that needs a
sidecar creates it:

```
<workspace>/v9/sidecar.json        {"format": "yuclaw-brief-sidecar/1", "workspace_id": "<the v8 workspace id>", "created_at": "...", "v8_format": "yuclaw-commitment-workspace/1"}
<workspace>/v9/brief.jsonl         the chained v9 record log (one canonical-JSON line per record)
<workspace>/v9/operations.jsonl    the measurement log (append-only, not chained)
```

and v9 stores its private bytes (text views, imported files, raw provider responses when disclosure permits) in the existing
content-addressed vault `<workspace>/private/vault/<sha256>`. A read never creates anything: observed on a bare v8 workspace
(directory listing before and after `yuclaw workbench brief list`, then after the first write, `brief example`):

```
commitments.jsonl  exports  imports  workspace.json
no brief yet (this workspace has no v9 sidecar; a read never creates one)
commitments.jsonl  exports  imports  workspace.json
commitments.jsonl  exports  imports  private  v9  workspace.json
```

(`list` is a read, yet it opens the sidecar in create mode; the read-only commands `status`, `recover`, `orphans` and
`measure` do not create anything and answer `E_NO_SIDECAR` on a workspace without `v9/`.)

## 2. What v9 never touches

- **The v8 journal is never appended to by v9.** Every v9 record goes to `v9/brief.jsonl`; each one names the v8 journal
  tip (`v8_tip`, `v8_seq`) it was written beside, so a record can always say which v8 state it was computed against. The
  v8 journal accepts a fixed event vocabulary; an 8.0.1 reader would refuse to write an unknown kind and would ignore it on
  read, which is why v9 keeps a separate log instead of extending the journal.
- **One lock for both stores.** The read-decide-append sequence of the sidecar runs under the v8 workspace lock (`.lock`),
  so v8 and v9 writes never interleave. v9 refuses to write beside a torn or corrupt v8 journal.
- **Reading a snapshot never mutates v8.** A brief is composed from an `EvidenceSnapshot/1` read once at the recorded v8
  tip; later v8 events never change it, and `review` compares rather than rewrites.

## 3. An 8.0.1 client on a workspace with a sidecar

An 8.0.1 client (`yuclaw workbench …` without the v9 layer) opened on a workspace that carries `v9/` reads its own data and
leaves `v9/` untouched: it knows nothing of the directory, and its journal, claims, exports and verifier are unaffected.

How this was verified for this note (no 8.0.1 installation was available offline, so the v8 code of the same checkout —
version string 8.0.1 — stood in for the released client):

1. `tests/test_v9_brief_engine.py`, class `TestA_Compatibility` (acceptance letter A), exists in the checkout and holds the
   invariant in three tests:
   - `test_v8_reads_and_exports_agree_with_a_copy_without_the_sidecar` — after v9 activity (create, edit, translate, link,
     import a signed report, export, retry), a copy of the workspace with `v9/` deleted yields the same v8 events, tip,
     claim state, status, export canonical digest and `verify-export` result as the original; the v8 `canonical.json`
     carries no brief material.
   - `test_v9_never_appends_to_the_v8_journal` — `commitments.jsonl` is byte-identical before and after the v9 activity, no
     journal side files appear, and every v9 record names the unchanged v8 tip.
   - `test_v8_reads_leave_the_sidecar_untouched` — v8 reads (`load`, `claim_state`, `events`, `status`, as-of reads) and a
     v8 `build-export` + `verify-export` leave every file under `v9/` byte-identical; the sidecar's integrity and the
     brief's `COMPLETE` status are unchanged.
2. The same invariant was exercised by hand in a disposable workspace: `sha256sum` of every file under `v9/` before and
   after `yuclaw workbench status --workspace <ws>` was identical ("v9/ unchanged by the v8 read"), and the v8 status
   reported its own data only:

```
$ yuclaw workbench status --workspace ~/yuclaw-workspaces/research
{
 "workspace_id": "ws-9cc3e0f05241",
 "events": 8,
 "tip": "156779eb7ffc7646a41a7ded09d5b0ceaf256ef11f7fc5d87fb6054a87a5c04a",
 "torn_tail": null,
 "integrity": "OK",
 "claims": ["ZZFX-FY2026-REV-GUIDE--FIX-COMMIT-001-base"]
}
```

3. `yuclaw workbench brief selftest` includes the check `v8 journal untouched by v9 writes` (every v8 event kind is a v8
   kind and `v9/brief.jsonl` exists beside it).

To repeat the check yourself: run `yuclaw workbench status --workspace <ws>` (v8) and `yuclaw workbench brief status
--workspace <ws>` (v9) — the first lists events and claims, the second lists records and briefs and quotes the v8
integrity and tip it is bound to.

## 4. The downgrade boundary

Removing the v9 layer (installing a package without it, or an 8.0.1 release) loses exactly one thing: **the ability to read
briefs** — the `v9/` directory, the `brief` command family and the `/brief` pages. Everything else stands:

| | After v9 is removed |
|---|---|
| v8 journal, claims, sources, outcomes, corrections | unchanged (v9 never wrote to them) |
| v8 exports (`exp-….zip`, format `yuclaw-commitment-export/1`) | unchanged, verified by `yuclaw workbench verify-export` as before |
| `v9/` directory and vault objects that only v9 referenced | left in place, unread; reinstalling v9 reads them again (the sidecar is append-only and bound to the workspace id) |
| v9 packets already built (`bpk-….zip`) | still files in `exports/`; they identify themselves as `yuclaw.brief-packet/1` and need the v9 verifier |

The v8 export format is unchanged by v9, and the two formats never mix: `yuclaw workbench brief verify` on a v8 export
answers `UNSUPPORTED — this is a v8 export (EXPORT_MANIFEST.json present, no BRIEF_MANIFEST.json); verify it with the v8
verifier (`yuclaw workbench verify-export`) …`, and `yuclaw workbench verify-export` on a v9 packet answers `MISMATCH —
incomplete packet: missing ['EXPORT_MANIFEST.json']`. Neither reinterprets the other.

The server integration is additive as well: the v8 server imports the v9 pages only when the package is present
(`_briefweb()` returns `None` otherwise) and shows the "Briefs (v9)" navigation link only then; `yuclaw workbench brief …`
dispatches to the v9 parser before the v8 argument parser runs.

## 5. Recovery semantics (the v8 rules, applied to the sidecar)

- **Prepared objects, then the record = commit.** Bytes are written to `private/vault/<sha256>` first; the sidecar record
  naming them under `payload.objects` is the commit point (`E_NOT_PREPARED` if a record names an object not yet in the
  vault). A process death therefore leaves either an orphan vault object or a committed record — never a brief that looks
  complete but lacks its inputs. A record whose objects are missing reads as `INCOMPLETE` and is never shown or exported
  as complete.
- **Torn tail.** An interrupted append leaves bytes without a terminating newline. Reads still work (`status` reports
  `"integrity": "TORN_TAIL"` with the tail's byte count, digest and offset); writes refuse `E_TORN_TAIL` (exit 3). `yuclaw
  workbench brief recover --workspace <ws>` preserves the bytes as `v9/brief.jsonl.torn.<16 hex>`, truncates the log to its
  last durable record and appends a `RECOVERY` record (`op_id: recovery:<24 hex>`, actor `workspace`) stating that the torn
  bytes were never a durable record and that nothing durable changed. A second `recover` answers `"recovered": false,
  "reason": "no torn tail"`.
- **Orphans, bounded cleanup.** `yuclaw workbench brief orphans --workspace <ws>` lists vault objects named by no sidecar
  record and no v8 module event (bounded listing); it deletes nothing. `--remove` deletes only the objects that are orphans
  at that moment, re-checked under the lock, and reports `removed` and `kept_referenced_or_unknown`.
- **Same op_id rules as v8.** Every write carries an `op_id` (`^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$`; CLI default
  `cli:<24 hex>`). A retry with the same op_id and the same content is answered by the existing record (`DUPLICATE`, exit 0,
  nothing appended); the same op_id with different content is `E_OP_CONFLICT` (exit 1, nothing appended). Version
  identifiers and timestamps of a retried operation are derived from the state the operation first ran on, so the retry
  reproduces the same payload.
- **Chain integrity.** Each line's `record_hash` covers the whole record; `prev_hash` chains to the previous line; `seq`
  increments by one; lines must be canonical JSON. Any violation is refused on load (`E_HASH`, `E_CHAIN`, `E_SEQ`,
  `E_NONCANONICAL`, `E_CORRUPT_LINE`, `E_LINE_TOO_LONG`) rather than repaired. A sidecar copied beside another workspace's
  journal is refused with `E_WORKSPACE_MISMATCH`.

## 6. Explicitly not provided

- **No backup/restore feature.** The sidecar and vault are ordinary files inside the workspace folder; copy the folder
  with your usual tools while no writer is running. v9 adds no backup command and restores nothing.
- **No in-place conversion** of a v9 packet into a v8 export or back.

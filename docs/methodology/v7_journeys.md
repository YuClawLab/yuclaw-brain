# v7 journeys — executable commands, representative output, expected exits and limits (candidate)

Representative output below was produced by running the INSTALLED rehearsal wheel (built from candidate commit `49495fd13cee4854717ff930b6d78e2301566d10`; NOT the final artifact) in a directory outside any checkout, with an empty environment and synthetic stores. Exit-code contracts: `packet` 0 SUCCESS / 1 MISMATCH / 2 usage / 3 UNSUPPORTED; `receipts`, `challenge`, `decision` 0 ok / 1 contract, authority or input error / 2 usage / 3 (history) unusable snapshot. A synthetic walkthrough never becomes a real outsider receipt; a packet SUCCESS is not an outsider result, not proof of official origin and not a scientific validation.

## Journey 1 — check a claim

Limits: the passport reports coverage of the corpus, never a truth verdict, direction, return or prediction (`support_limits.research_interpretation` is always NONE).

```
$ yuclaw check-claim --text "the sky is blue"
{
 "status": "NOT_PARSEABLE",
 "support_limits": {
  "source_match": "NOT_EVALUATED",
  "source_match_meaning": "claim not parseable or outside coverage",
  "temporal_eligibility": "NOT_EVALUATED",
  "temporal_note": "matches are reported with their available_as_of; a date range constrains filing dates only",
  "replay_status": "NOT_APPLICABLE",
  "research_interpretation": "NONE",
  "research_interpretation_note": "the passport never states a truth verdict, direction, return, or prediction",
  "unsupported_conclusion": "no conclusion: the claim could not be evaluated",
  "matched_count": 0,
  "miss_count": 0
 }
}
[exit 0]
```
## Journey 2 — build and verify an offline packet

Limits: exact bytes + a replay of the frozen public Lab bundle; provenance is UNVERIFIED unless an independently obtained identity is supplied with `--trusted-manifest`; a rehearsal packet's source sha is the candidate's, not a release.

```
$ yuclaw packet build ./pk --source <checkout>
[packet] built <work>/cwd/pk: 10 files, source 49495fd13cee; verify with: yuclaw packet verify <work>/cwd/pk
[exit 0]
```
```
$ yuclaw packet verify ./pk
[packet] SUCCESS — manifest 09911480d4252c92…; exact bytes verified and published Lab statistics/ledger roots reproduced from the frozen bundle; not an outsider receipt, not a research interpretation, not proof of official origin | provenance: official artifact equality UNVERIFIED
[exit 0]
```
```
$ yuclaw packet verify ./pk --trusted-manifest trusted.json   # identity obtained through an independent channel
[packet] SUCCESS — manifest 09911480d4252c92…; exact bytes verified and published Lab statistics/ledger roots reproduced from the frozen bundle; not an outsider receipt, not a research interpretation, not proof of official origin | provenance: official artifact equality EQUAL
[exit 0]
```
```
$ yuclaw packet verify ./pk   # after one byte of an artifact changed
[packet] MISMATCH — manifest 09911480d4252c92…; first discrepancy: byte mismatch at docs/capabilities.json: expected 96beff4fa51b4f91…/3341 B, observed 266555f98b64662f…/3341 B | provenance: official artifact equality UNVERIFIED
[exit 1]
```
## Journey 3 — create and evaluate a challenge

Limits: a challenge states a criterion; a `general` criterion is resolved only by a designated reviewer's explicit evaluation; verifier-backed criteria need the store's own executed verification record; dispositions never erase the original finding. The reviewer credential comes from `--token-file` (mode 0600), never from an argument.

```
$ yuclaw challenge --store ./store --synthetic create ch-1 --artifact-type bundle --sha256 f0bde0a8fda9… --size-bytes 4318689 --claim-id claim-1 --expected "replay exit 0" --observed "replay exit 1" --criterion packet-integrity-and-replay
{
 "challenge_id": "ch-1",
 "criterion": "packet-integrity-and-replay",
 "disposition": "OPEN",
 "adverse": true
}
[exit 0]
```
```
$ yuclaw challenge --store ./store --synthetic dispose ch-1 CONFIRMED   # no reviewer credential
[challenge] REJECTED: no token source: reviewer token must not be a process argument (visible in `ps` and shell history); use --token-file <owner-only file, mode 0600>, --token-fd <inherited descriptor>, or run interactively to be prompted without echo
[exit 1]
```
```
$ yuclaw challenge --store ./store --synthetic verify-revision ch-1 --revised-type bundle --revised-sha256 <sha> --revised-size-bytes <n> --method packet-verify --packet ./pk
{
 "verification_id": "492eb2bdff7d82c063d62db545eda6bc1867c44e0f6171715f5a6471c0fa9ae9",
 "challenge_id": "ch-1",
 "criterion": "packet-integrity-and-replay",
 "method": "packet-verify",
 "result": "SUCCESS",
 "reason": "packet verification SUCCESS and the revised artifact's exact bytes were observed in it",
 "executed_at": "2026-09-14T07:31:31.393517Z"
}
[exit 0]
```
```
$ yuclaw challenge --store ./store --synthetic dispose ch-1 RESOLVED --role rev-syn --token-file tok --revised-type bundle --revised-sha256 <sha> --revised-size-bytes <n> --revised-path ./pk/artifacts/docs/replay/lab_replay_bundle.json --allowed-root . --verification-id <id>
[challenge] REJECTED: RESOLVED must reference a REVISED artifact — the original bytes cannot resolve their own failure
[exit 1]
```
```
$ yuclaw challenge --store ./store --synthetic list
[
 {
  "challenge_id": "ch-1",
  "criterion": "packet-integrity-and-replay",
  "disposition": "OPEN",
  "adverse": true,
  "disposed_by_authority": null
 }
]
[exit 0]
```
## Journey 4 — record a permitted research document use

Limits: a decision record is bound to the exact packet manifest digest; context stays private; export needs explicit permission; it is never evidence of investment benefit.

```
$ yuclaw decision --store ./store --synthetic record dec-1 REQUEST_EVIDENCE --packet-manifest-digest 09911480d425… --claim-id claim-1 --context '{"note": "private context"}'
{
 "decision_id": "dec-1",
 "decision": "REQUEST_EVIDENCE",
 "export_permitted": false,
 "disclaimer": "a document-use receipt records that a research decision was taken on an exact packet; it is not evidence of investment benefit, performance or endorsement"
}
[exit 0]
```
```
$ yuclaw decision --store ./store --synthetic export   # empty: permission not granted
[]
[exit 0]
```
## Receipts — explain, target-bound coverage, history

Limits: exact-target coverage is UNBOUND until a release target manifest is delivered as release evidence; `explain` shows reason codes publicly and private facts only with `--private`; `history` compares two validated snapshots and never reports a multiplier from a zero baseline.

```
$ yuclaw receipts --store ./store --synthetic explain demo-1
{
 "receipt_id": "r-5cf946c61f507a10dc992530c3179620",
 "attempt_id": "demo-1",
 "activity_type": "REPLICATION",
 "version": 1,
 "corrected": false,
 "artifact_scope": {
  "artifact_type": "bundle",
  "sha256": "f0bde0a8fda96377d56c51285eff4561d1db3bb4f11b8e3cae4139f79a5dd196",
  "size_bytes": 4318689
 },
 "release_identity": null,
 "observation": {
  "status": "VERIFIED",
  "source": "path"
 },
 "review": {
  "state": "QUALIFIED",
  "authority": "SYNTHETIC",
  "appointment_bound": true
 },
 "qualified": true,
 "successful": true,
 "reason_codes": [],
 "counting": {
  "eligibility": "unwindowed",
  "window": null,
  "bucket": "unwindowed",
  "registration": "PENDING (unwindowed)"
 },
 "lineage": {
  "versions": 1,
  "first_observed_at": "2026-09-14T01:00:00.000000Z",
  "superseded_at": null
 },
 "counts_because": "qualified attempt in the primary population and successful",
 "meaning": "derived from records; no trust score; research only"
}
[exit 0]
```
```
$ yuclaw receipts --store ./store --synthetic --now 2026-09-14T08:00:00.000000Z scoreboard --out a.json
[receipts] scoreboard written a.json (synthetic=True; target UNBOUND)
[exit 0]
```
```
$ yuclaw receipts --store ./store history a.json b.json   # (a synthetic board is refused: the comparison needs public snapshots)
[receipts] history: snapshot unusable: a.json: SYNTHETIC_REFUSED (E_SYNTHETIC at synthetic); b.json: SYNTHETIC_REFUSED (E_SYNTHETIC at synthetic)
[exit 3]
```

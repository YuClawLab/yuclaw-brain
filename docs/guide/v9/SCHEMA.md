# YUCLAW v9 — Schema reference (developer)

Research and education only. Not investment advice.
Mission: Make financial AI accountable to evidence. Vision: Become the Science Trust Layer for Financial AI.

Covers the 9.0 **candidate** on branch `codex/v9-integration` (HEAD `70a6c8aa`, 9 October 2026; package version string
8.0.1; layer identity `v9.brief/1`). Everything below is as implemented in `v9/brief/contracts.py`, `sidecar.py`,
`packet.py`, `reports.py`, `measure.py`, `reducer.py` and `finance.py`; `yuclaw workbench brief schema --json` prints the
vocabularies from the running code. All example values are fictional.

## 1. General rules

- A validator returns `(normalized record, [])` or `(None, [every blocking reason])`; it never coerces. A float, a character
  offset, an offset inside a multi-byte sequence, an unknown status word or a forbidden combination is a reason, not a guess.
  The CLI prints every reason: `refused: <what> cannot be recorded: <reason>; <reason>; …` and exits 2 with nothing written.
- Schema names are versioned strings; an unknown version is refused, never reinterpreted.
- **Record identity** (`record_id`) is the sha256 of the canonical JSON of the record without its own identity field, so one
  record has one identity everywhere and a self-referential hash is never inside a signed body. Exception: a TextView's
  identity is its `view_sha256` (a view *is* its bytes).
- Field helpers and bounds: text fields are printable strings without control characters; `SHORT_MAX` = 240 characters,
  `FIELD_MAX` = 2000; `TEXT_MAX` = 65 536 bytes for one text view; `MAX_SPANS` = 500; `MAX_LINKS` = 64 (evidence items,
  receipt inputs); `MAX_LIST` = 200; identifiers match `^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$`; digests are 64 lowercase hex;
  timestamps are parsed by the v8 `parse_ts`; integers are bounded (`0..10^15` unless stated) and booleans are never
  accepted as integers.
- Decimals: `check_decimal_string` accepts a canonical decimal string or an integer, refuses floats, NaN and exponent form;
  `percent_string` (diagnostics) accepts a finite decimal string, refuses floats and booleans.
- `unknown` objects (`{name: reason}`, ≤ 64 entries): every unexposed quantity names *why* it is unknown; a bare null is not
  an explanation.

## 2. Closed vocabularies

| Name | Values |
|---|---|
| `SUPPORTED_SCHEMAS` | `yuclaw.artifact-record/1`, `yuclaw.text-view/1`, `yuclaw.claim-span/1`, `yuclaw.generation-receipt/1`, `yuclaw.detection-report/1`, `yuclaw.transform-record/1`, `yuclaw.calibration-record/1`, `yuclaw.brief-packet/1`, `yuclaw.evidence-snapshot/1`, `yuclaw.brief-version/1`, `yuclaw.review-item/1` |
| `ROLES` | `direct_quotation`, `computed_statement`, `attributed_source_statement`, `analyst_interpretation`, `generated_commentary`, `unresolved_claim` |
| `SUPPORT` | `SUPPORTED`, `ATTRIBUTED`, `UNRESOLVED`, `CONTRADICTED`, `NOT_ASSESSED`, `INVALIDATED` |
| `SUPPORT_METHODS` | `exact_quotation_match/1`, `registered_arithmetic/1`, `typed_slot_render/1`, `method_statement/1`, `assessor_assertion/1`, `none` |
| `EXECUTION` | `NOT_REQUESTED`, `ACCESS_UNAVAILABLE`, `UNSUPPORTED`, `INSUFFICIENT_INPUT`, `COMPLETED`, `FAILED` |
| `SIGNAL` | `DETECTED`, `NOT_DETECTED`, `INCONCLUSIVE` |
| `CALIBRATION` | `APPLICABLE`, `OUT_OF_SCOPE`, `NOT_ESTABLISHED` |
| `ORIGIN_KINDS` | `operator_assertion`, `connector_observed`, `issuer_signed` |
| `TRANSFORM_KINDS` | `template_render`, `import`, `edit`, `translate`, `span_correction` |
| `RECORDING_METHODS` | `template_deterministic`, `operator_entered`, `imported_file`, `connector_observed` |
| `MAPPING_METHODS` | `identity`, `exact_bytes_unique/1`, `operator_mapped/1`, `none` |
| `LANGUAGES` | `en`, `fr` |
| `MEDIA_TYPES` | `text/plain; charset=utf-8`, `text/markdown; charset=utf-8`, `text/html; charset=utf-8`, `application/json`, `application/pdf`, `application/octet-stream` |
| `COLLECTION_METHODS` | `v8_source_registration`, `operator_entered`, `imported_file`, `template_render`, `connector_observed` |
| `NORMALIZATION_POLICIES` | `none`, `NFC/1`, `NFKC/1` |
| `CHECK_OUTCOMES` | `VERIFIED`, `FAILED`, `NOT_RECOMPUTABLE`, `REPORT_ONLY`, `UNSUPPORTED`, `NOT_APPLICABLE` |
| `REVIEW_REASONS` | `SOURCE_AVAILABILITY_CORRECTED`, `CLAIM_AMENDED`, `CLAIM_WITHDRAWN`, `OUTCOME_CHANGED`, `SPAN_UNMAPPED`, `PROTECTED_FACT_CHANGED`, `PROSE_CONTRADICTS_PROTECTED_FACT`, `OPERATOR_FLAG` |
| `DISCLOSURE` | `permitted`, `withheld`, `unknown` |
| `RIGHTS` | `FICTIONAL`, `SEC_PUBLIC_FILING`, `COMPANY_PRESS_RELEASE`, `UNKNOWN`, `OPERATOR_OWN_TEXT` |
| `BUNDLE_RIGHTS` | `FICTIONAL`, `SEC_PUBLIC_FILING`, `OPERATOR_OWN_TEXT` — the only rights classes whose excerpt bytes travel in a packet |
| evidence kinds (ClaimSpan) | `source_excerpt`, `claim_version`, `outcome`, `calculation`, `v8_event`, `artifact` |
| mapping status (TransformRecord) | `MAPPED`, `UNMAPPED`, `CHANGED` |
| review status (TransformRecord) | `unreviewed`, `operator_reviewed` |
| dispositions (review resolution) | `REVIEWED_NO_CHANGE`, `REVISED`, `WITHDRAWN_STATEMENT`, `DISPUTED` |
| signature evaluation | signature `NONE` / `VALID` / `INVALID` / `UNVERIFIABLE`; trust `NOT_EVALUATED` / `TRUSTED` / `UNKNOWN_SIGNER` / `REVOKED_ROOT`; binding `NOT_APPLICABLE` / `BOUND` / `MISMATCH` |
| version identifiers | v8 claim versions `^(V1|R[0-9]{1,3}|C[0-9]{1,3})$`; brief versions `^B[0-9]{1,4}$`; brief ids `brf-<12 hex>`; packet ids `bpk-<16 hex>` |

## 3. Byte semantics

- A **TextView** is an exact UTF-8 byte string with a digest. Invalid UTF-8 is refused (`text view: not valid UTF-8 (… at byte N)`),
  as is a view over `TEXT_MAX` bytes.
- A **ClaimSpan** addresses a view by **half-open UTF-8 byte offsets** `start..end` (`start` included, `end` excluded;
  `start < end`), never by a UI's character offsets. Boolean or non-integer offsets are refused with the reason
  `span: integer byte offsets required (a UI's character offsets must be converted to UTF-8 byte offsets)`.
- **Boundary rule** (`utf8_boundary`): an offset is valid when it is 0, the view length, or the first byte of a UTF-8
  sequence — never a continuation byte `10xxxxxx`. Reasons: `span: start offset N is inside a multi-byte UTF-8 sequence`,
  `span: end offset N is inside a multi-byte UTF-8 sequence`, `span: offsets a..b outside the view of L bytes`.
- **Span digest**: `span_sha256 = sha256(view_bytes[start:end])`. When the bytes are available the recorded digest is
  checked against them: `span.span_sha256: does not match the bytes a..b of the view (<16 hex>…)`.
- **Protected slots** inside a span (`{slot, value, start, end}`) must lie inside their sentence
  (`span.protected[i]: slot a..b is not inside its sentence s..e`).
- **Normalization creates a named view.** `normalize_text(text, policy)` with `NFC/1` or `NFKC/1` yields a new view with
  its own `view_sha256` and `normalization` field; it never rewrites an original. The product's own views use `none`.
- Offsets in Python: `start = len(text[:i].encode("utf-8"))` for character index `i`.

## 4. Contracts, field by field

### 4.1 ArtifactRecord/1 — `yuclaw.artifact-record/1` (`check_artifact`)

| Field | Type / bound | Rule |
|---|---|---|
| `schema` | string | must be `yuclaw.artifact-record/1` |
| `content_sha256` | hex64 | required |
| `byte_length` | int `0..2^31` | required |
| `media_type` | enum `MEDIA_TYPES` | required |
| `encoding` | text ≤ 32 | default `utf-8` |
| `rights` | enum `RIGHTS` | required |
| `collection_method` | enum `COLLECTION_METHODS` | required |
| `asserted_available_as_of` | timestamp | optional |
| `observed_at` | timestamp | required |
| `label` | text ≤ 240 | optional (default `""`) |
| `parents` | list ≤ 16 of hex64 | optional |
| `v8_source_id` | text ≤ 240 | optional |
| `record_id` | hex64 | computed |

Produced by `import` for the imported file (`media_type: text/plain; charset=utf-8`, `collection_method: imported_file`,
default `rights: OPERATOR_OWN_TEXT`).

### 4.2 TextView/1 — `yuclaw.text-view/1` (`make_text_view`, `check_text_view`)

| Field | Type / bound | Rule |
|---|---|---|
| `schema` | string | `yuclaw.text-view/1` |
| `source_artifact` | hex64 or null | the artifact or parent view the text derives from |
| `extraction` | text ≤ 240 | the tool/version that produced the view (`v9.brief.templates/1`, `imported draft, bytes as supplied`, `edit by operator`, `translate by operator`) |
| `normalization` | enum `NORMALIZATION_POLICIES` | required |
| `language` | `en` / `fr` or null | optional |
| `view_sha256` | hex64 | sha256 of the bytes |
| `byte_length` | int `0..65536` | required |
| `location_map` | list ≤ 500 | optional |
| `record_id` | = `view_sha256` | one byte string, one identity |

### 4.3 ClaimSpan/1 — `yuclaw.claim-span/1` (`check_claim_span(raw, view_bytes=None)`)

| Field | Type / bound | Rule |
|---|---|---|
| `schema` | string | `yuclaw.claim-span/1` |
| `view_sha256` | hex64 | required |
| `start`, `end` | int | half-open byte offsets, `start < end`; checked against `view_bytes` when given (section 3) |
| `span_sha256` | hex64 | must equal the digest of the bytes when `view_bytes` is given |
| `role` | enum `ROLES` | required |
| `claim` | object or null | `{claim_id (identifier), version_id (V1/Rn/Cn), claim_digest (hex64)}` |
| `evidence` | list ≤ 64 of `{kind, ref (≤ 240), digest (hex64, optional)}` | `kind` ∈ evidence kinds |
| `calculation` | object or null | a registered calculation record (section 9) |
| `support` | enum `SUPPORT` | required |
| `method` | enum `SUPPORT_METHODS` | required |
| `assessor` | text ≤ 240 | required (`v9.brief.templates/1`, `operator:<actor>`, the segmenter's description) |
| `limits` | text ≤ 2000 | optional |
| `protected` | list ≤ 32 of `{slot (≤ 64), value (≤ 240), start, end}` | slots inside the sentence |
| `record_id` | hex64 | computed |

Cross-field rules: `SUPPORTED` with method `assessor_assertion/1` or `none` is refused (*an assessor's assertion is
ATTRIBUTED, never SUPPORTED*); an `unresolved_claim` must be `UNRESOLVED`, `CONTRADICTED` or `INVALIDATED`.

### 4.4 GenerationReceipt/1 — `yuclaw.generation-receipt/1` (`check_generation_receipt`)

| Field | Type / bound | Rule |
|---|---|---|
| `schema` | string | `yuclaw.generation-receipt/1` |
| `origin` | enum `ORIGIN_KINDS` | required |
| `recording_method` | enum `RECORDING_METHODS` | required |
| `inputs` | list ≤ 64 of hex64 | digests of inputs (snapshot, parent view…) |
| `template` | text ≤ 240 | required when `recording_method` is `template_deterministic` |
| `prompt_sha256` | hex64 | optional |
| `prompt_disclosure` | enum `DISCLOSURE` | default `unknown` |
| `provider`, `model` | text ≤ 240 | for non-template methods: give the value **or** an explicit reason under `unknown.provider` / `unknown.model` |
| `settings` | object, canonical JSON ≤ 8192 bytes | for non-template methods: give the settings **or** `unknown.settings` |
| `raw_output_sha256` | hex64 | optional |
| `assembled_output_sha256` | hex64 | required; on import it must be the `view_sha256` of a brief version in the workspace |
| `request_id` | text ≤ 240 | optional; **not** a signature |
| `issued_at` | timestamp | optional |
| `observed_at` | timestamp | required |
| `unknown` | `{name: reason}` | see section 1 |
| `signature_envelope` | object or null | required when `origin` is `issuer_signed` |
| `note_same_bytes` | string | added when raw and assembled digests are equal for a non-template method |
| `record_id` | hex64 | computed |

Cross-field rules: `issuer_signed` without envelope → `receipt.origin: issuer_signed requires a signature_envelope (a
filename, screenshot or request id is not a provider signature)`; `connector_observed` origin requires
`recording_method: connector_observed`.

### 4.5 DetectionReport/1 — `yuclaw.detection-report/1` (`check_detection_report`)

| Field | Type / bound | Rule |
|---|---|---|
| `schema` | string | `yuclaw.detection-report/1` |
| `view_sha256` | hex64 | required; on import it must be a text view of a brief version here |
| `span` | `{start, end, span_sha256}` | integer byte offsets of the exact tested span; digest checked against the view's bytes on import |
| `detector` | text ≤ 240 | required |
| `detector_version` | text ≤ 240 | optional |
| `configuration` | object ≤ 8192 bytes canonical | optional |
| `key_scope` | text ≤ 240 | optional |
| `execution` | enum `EXECUTION` | required |
| `signal` | enum `SIGNAL` | **only** when `execution` is `COMPLETED` |
| `calibration` | enum `CALIBRATION` | required |
| `failure_reason` | text ≤ 2000 | required for every execution other than `NOT_REQUESTED` and `COMPLETED` |
| `diagnostics` | object ≤ 32 of decimal strings | floats refused |
| `origin` | enum `ORIGIN_KINDS` | required |
| `response_sha256` | hex64 | optional; if a `--raw-response` is supplied its digest must match |
| `selection` | text ≤ 2000 | why this span was tested |
| `test_family` | text ≤ 240 | optional |
| `calibration_ref` | hex64 | required when `calibration` is `APPLICABLE` |
| `observed_at` | timestamp | required |
| `issued_at` | timestamp | optional |
| `cache_reuse` | bool | default false; a `note_cache` is added when true with `COMPLETED` |
| `disclosure` | enum `DISCLOSURE` | default `unknown`; raw response bytes are retained in the vault only when `permitted` |
| `unknown` | `{name: reason}` | see below |
| `signature_envelope` | object or null | required when `origin` is `issuer_signed` |
| `record_id` | hex64 | computed |

Each of `threshold`, `p_value`, `scored_context_count`, `key_epoch` must appear in `diagnostics` or `configuration`, or be
declared under `unknown` with a reason (`report: <k> must be supplied (diagnostics/configuration) or declared unavailable
under report.unknown.<k>; it is never inferred from a paper`).

#### Allowed combinations (`report_combination_problems`)

| `execution` | `signal` | `failure_reason` | `calibration` |
|---|---|---|---|
| `COMPLETED` | required: `DETECTED` / `NOT_DETECTED` / `INCONCLUSIVE` | optional | any; `APPLICABLE` also needs `calibration_ref` |
| `NOT_REQUESTED` | must be absent | optional | `OUT_OF_SCOPE` or `NOT_ESTABLISHED` (`APPLICABLE` is meaningless without a COMPLETED execution) |
| `ACCESS_UNAVAILABLE`, `UNSUPPORTED`, `INSUFFICIENT_INPUT`, `FAILED` | must be absent (`<execution> cannot become <signal>`) | **required** | `OUT_OF_SCOPE` or `NOT_ESTABLISHED` |

### 4.6 CalibrationRecord/1 — `yuclaw.calibration-record/1` (`check_calibration`)

| Field | Type / bound | Rule |
|---|---|---|
| `schema` | string | `yuclaw.calibration-record/1` |
| `detector` | text ≤ 240 | required |
| `detector_version` | text ≤ 240 | optional |
| `configuration` | object | optional |
| `key_scope` | text ≤ 240 | optional |
| `corpus` | text ≤ 2000 | required |
| `label_provenance` | text ≤ 2000 | required |
| `languages` | list 1..16 of `en` / `fr` / `other` | at least one |
| `domains`, `length_strata`, `missing_strata` | lists ≤ 32 of text ≤ 240 | optional |
| `test_unit` | text ≤ 240 | required |
| `selection_rule` | text ≤ 2000 | required |
| `split` | text ≤ 240 | required |
| `error_rate_plan` | text ≤ 2000 | required |
| `confusion` | object with exactly `tp`, `fp`, `tn`, `fn` (int `0..10^9`) | required |
| `interval_method` | text ≤ 240 | required |
| `origin` | enum `ORIGIN_KINDS` | required; `issuer_signed` needs an envelope |
| `observed_at` | timestamp | required |
| `signature_envelope` | object or null | |
| `record_id` | hex64 | computed |

**Scope match** (`calibration_scope_matches`): same `detector`; same `detector_version` when the calibration states one;
identical canonical `configuration`; same `key_scope`; the view's language among the calibrated `languages`.
**Applicability** (`reports.calibration_applicability`): `NOT_ESTABLISHED` unless the report's execution is `COMPLETED`;
the report's own word unless it claims `APPLICABLE`; then `NOT_ESTABLISHED` when the `calibration_ref` is not enrolled here,
`OUT_OF_SCOPE` when the scope differs, `NOT_ESTABLISHED` when the calibration record is not `issuer_signed` with signature
`VALID`, trust `TRUSTED` and binding `BOUND` under the receiver's current roots, and `APPLICABLE` otherwise ("applicability
is the record's, not a YUCLAW measurement").

### 4.7 TransformRecord/1 — `yuclaw.transform-record/1` (`check_transform`)

| Field | Type / bound | Rule |
|---|---|---|
| `schema` | string | `yuclaw.transform-record/1` |
| `kind` | enum `TRANSFORM_KINDS` | required |
| `parent_view` | hex64 or null | required for `edit`, `translate`, `span_correction`; must differ from `child_view` |
| `child_view` | hex64 | required |
| `implementation` | text ≤ 240 | required |
| `language_from`, `language_to` | `en` / `fr` or null | a `translate` names two different languages |
| `mapping_method` | enum `MAPPING_METHODS` | required |
| `mapping` | list ≤ 500 of `{parent_span (hex64), child_start, child_end, status}` | `status` ∈ `MAPPED` / `UNMAPPED` / `CHANGED` |
| `review_findings` | list ≤ 500 of `{reason (REVIEW_REASONS), detail (≤ 2000), span (hex64, optional)}` | |
| `actor` | text ≤ 240 | required |
| `provenance` | text ≤ 2000 | optional |
| `review_status` | `unreviewed` / `operator_reviewed` | default `unreviewed` |
| `record_id` | hex64 | computed |

### 4.8 ReviewItem/1 — `yuclaw.review-item/1` (`check_review_item`)

`reason` (enum `REVIEW_REASONS`), `detail` (≤ 2000), `brief_id` (identifier), `version_id` (`B…`, optional), `span` (hex64,
optional), `dependency` (≤ 240, optional: `claim:<id>` or `source:<id>`). Item ids as shown by `review` are the first 24 hex
of the digest of `{reason, dependency, version_id, corrections, span, detail}` (`compose.review_item_id`), so the same
finding has the same id on every read; a `REVIEW_ITEM_RESOLVED` record names that id with a disposition and a note.

### 4.9 EvidenceSnapshot/1 — `yuclaw.evidence-snapshot/1` (`snapshot.build`)

A stable, digest-identified reading of the v8 claims a brief depends on (1..32 claims): `workspace_id`, `v8_tip`, `v8_seq`,
per claim its versions (`version_id`, `type`, `claim_digest`, `event_hash`, `time`, the typed claim), `current_version`,
`original_effective_version`, `revised_versions`, `withdrawn`, `outcome`, `sources` (`source_id`, `source_hash`, `kind`,
`form`, `accession`, `url`, `filed_at`, `registered_available_as_of`, `effective_available_as_of`, `corrections`,
`observed_at`, `rights`, `fictional`, `excerpt`, `excerpt_bytes`), the v8 calculator `results`, `comparison`,
`availability_review`, `adjudications`, `event_count`; `semantics` (what the three times mean; stability rule);
`snapshot_digest` = digest of everything else. `snapshot.public_view` withholds excerpt bytes outside `BUNDLE_RIGHTS`
(`excerpt: null`, `excerpt_withheld: "rights …"`); `snapshot.dependency_review` compares the live v8 state with the snapshot
and emits findings with `dependency` = `claim:<id>` or `source:<id>`.

### 4.10 BriefVersion/1 — `yuclaw.brief-version/1` (payload of `BRIEF_VERSION_RECORDED`)

`brief_id`, `version_id` (`B1`, `B2`, …, derived from the state the operation first ran on so a retry reproduces the same
payload), `parent_version` (null for `template_render` / `import`), `language`, `title`, `claim_ids`, `text_view`
(TextView/1), `spans` (ClaimSpan/1 list), `snapshot_digest`, `snapshot_object` (vault digest of the snapshot),
`v8_tip_at_snapshot`, `production` (`renderer`, `template`, `language`, `claim_id`, `deterministic`, `settings`,
`sections` — or `imported: true` / `kind: edit|translate` with `deterministic: false`), `receipt` (GenerationReceipt/1),
`transform` (TransformRecord/1), `artifact` (ArtifactRecord/1, imports only), `extraction_scope`, `objects` (the vault
digests the record commits: snapshot and text).

### 4.11 BriefPacket/1 — `yuclaw.brief-packet/1` (section 7)

## 5. The signed-body rule

- `reports.signed_body(record)` = the record **without** `signature_envelope`, `record_id` and `provenance_note`. That is
  what an issuer signs and what `import-record` compares with the body inside the envelope (`binding`: `BOUND` /
  `MISMATCH`).
- Envelope (`v8.workbench.modules.envelope`, `yuclaw.signed-record/1`): fields `envelope`, `record_type`, `body`, `signer`
  (`algorithm: Ed25519`, `key_id`, `public_key` base64 raw 32 bytes), `signature` (base64). Signing input is
  `b"YUCLAW-SIGNED-RECORD/1" 0x00 <record type ASCII> 0x00 <canonical JSON of the body>` — **domain separation**: the record
  type is inside the signed bytes and verification demands the type the receiver expects, so a signature is valid for one
  record type only. v9 record types: `brief.generation_receipt`, `brief.detection_report`, `brief.calibration_record`
  (and `brief.packet`, reserved). Bodies are canonical JSON of integers, strings, booleans, nulls, lists and objects (no
  floats; integers below 10^16; depth ≤ 16).
- `key_id` = `envelope.key_id(raw public key)`. Trust roots are `TRUST_ROOT_ENROLLED` / `TRUST_ROOT_REVOKED` records of the
  **receiving** sidecar; an envelope may carry its own public key, which makes integrity checkable anywhere and never
  makes it trusted (no trust on first use). A revoked root is never revived; `evaluate_signature` is run under the
  receiver's current roots at every read.
- Import rules: `origin: issuer_signed` requires signature `VALID` and binding `BOUND` (otherwise refused with the reason);
  an unsigned record is `signature NONE / trust NOT_EVALUATED / binding NOT_APPLICABLE`.

## 6. The sidecar

Location `<workspace>/v9/` (mode 0700): `sidecar.json` (`format: yuclaw-brief-sidecar/1`, `workspace_id`, `created_at`,
`v8_format`), `brief.jsonl` (the chained record log), `operations.jsonl` (measurements). Private bytes go to the existing
content-addressed vault `<workspace>/private/vault/<sha256>` **before** the record that names them is appended; the record
is the commit point. A record whose `payload.objects` are missing from the vault reads as `INCOMPLETE`.

**Record line format** — one newline-terminated canonical-JSON line, `MAX_LINE` = 1 MiB:

```
{"actor": "...", "brief_id": "brf-… | null", "kind": "<KIND>", "op_id": "...", "payload": {...}, "prev_hash": "<hex64>", "record_hash": "<hex64>",
 "seq": N, "time": {"recorded_at": "<UTC>"}, "v8_seq": M, "v8_tip": "<hex64>"}
```

`record_hash` is the sha256 of the canonical JSON of the record without `record_hash`; `prev_hash` chains to the previous
record (genesis `0`×64); `seq` increments by one; `v8_tip` / `v8_seq` name the v8 journal state observed at write time.
Load refuses `E_LINE_TOO_LONG`, `E_CORRUPT_LINE`, `E_HASH`, `E_CHAIN`, `E_SEQ`, `E_NONCANONICAL`; a final line without `\n`
is a torn tail (`TORN_TAIL`), and writes refuse `E_TORN_TAIL` until `recover()` moves the bytes to
`brief.jsonl.torn.<16 hex>` and appends a `RECOVERY` record (`op_id: recovery:<24 hex>`, actor `workspace`).

**Kinds**: `ARTIFACT_RECORDED`, `TEXT_VIEW_RECORDED`, `SNAPSHOT_RECORDED`, `BRIEF_VERSION_RECORDED`, `TRANSFORM_RECORDED`,
`SPAN_LINK_RECORDED`, `RECEIPT_IMPORTED`, `REPORT_IMPORTED`, `CALIBRATION_IMPORTED`, `TRUST_ROOT_ENROLLED`,
`TRUST_ROOT_REVOKED`, `REVIEW_ITEM_RECORDED`, `REVIEW_ITEM_RESOLVED`, `PACKET_BUILT`, `PACKET_VERIFIED`, `RECOVERY`.
Kinds in use by the 9.0 candidate's operations: `BRIEF_VERSION_RECORDED` (create / import / edit / translate),
`SPAN_LINK_RECORDED`, `RECEIPT_IMPORTED`, `REPORT_IMPORTED`, `CALIBRATION_IMPORTED`, `TRUST_ROOT_ENROLLED`,
`TRUST_ROOT_REVOKED`, `REVIEW_ITEM_RESOLVED`, `PACKET_BUILT`, `PACKET_VERIFIED`, `RECOVERY`.

**op_id**: `^[A-Za-z0-9][A-Za-z0-9._:-]{7,127}$` (8–128 characters); CLI default `cli:<24 hex>`. Same op_id and same kind and
payload digest → the existing record is returned (`DUPLICATE`); same op_id with different content → `E_OP_CONFLICT`. The
read-decide-append sequence runs under the v8 workspace lock (`.lock`), one lock for both stores. Writes also refuse when
the v8 journal itself has a torn tail. `E_WORKSPACE_MISMATCH` when `sidecar.json`'s `workspace_id` differs from
`workspace.json`'s; `E_NO_SIDECAR` when a read-only command opens a workspace without `v9/`; `E_FORMAT` for an unknown
sidecar format.

**operations.jsonl** — append-only, not chained (an observation log, not evidence), bound 64 MiB:

```
{"actor": "host-operator(cli)", "attempt": 1, "brief_id": "brf-…", "detail": null, "elapsed_ms": 28, "finished_at": "…", "op_id": "cli:…", "outcome": "COMMITTED", "started_at": "…", "surface": "cli", "task": "create_brief"}
```

`outcome` ∈ `COMMITTED`, `DUPLICATE`, `CONFLICT`, `REFUSED`, `FAILED`, `READ`; `surface` ∈ `cli`, `ui`; tasks: `create_brief`,
`import_draft`, `edit_brief`, `translate_brief`, `link_span`, `resolve_review`, `import_receipt` / `import_report` /
`import_calibration`, `trust_enroll`, `trust_revoke`, `export_packet`, `verify_packet`.

**Orphans**: vault objects named by no sidecar record and no v8 module event; `orphans()` lists them (bounded, 1000) and
deletes nothing; `remove_orphans()` deletes only objects that are orphans at that moment, re-checked under the lock.

## 7. The packet (`yuclaw.brief-packet/1`)

Members (fixed names, at most 64 members, no paths outside the root, member rules of the v8 export reader, deterministic
zip entry dates): `BRIEF_MANIFEST.json`, `VERIFY.md`, `brief.json`, `records.json`, `snapshot.json`, `brief.html`,
`appendix.md`, `text/<view_sha256>.txt` for every version. Required: all except the text members.

**Manifest** (`BRIEF_MANIFEST.json`, ASCII JSON, indent 1, sorted keys):

| Field | Meaning |
|---|---|
| `format` | `yuclaw.brief-packet/1` |
| `packet_id` | `bpk-<16 hex>` |
| `built_at` | UTC timestamp |
| `brief_id`, `version_id`, `language`, `workspace_id` | the exported version and the authoring workspace id |
| `verifier` | `v9.brief.packet/1` |
| `software` | `yuclaw_v9: v9.brief/1`, `reducer: v9.brief.reducer/1`, `calculator: v9.brief.finance/1 over v8.workbench.calc/1`, `renderer`, `candidate_commit` (`YUCLAW_CANDIDATE_COMMIT` or `not recorded`) |
| `snapshot_digest`, `research_cutoff` | `{v8_tip, snapshot_digest, packet_built_at}` |
| `files` | `[{path, sha256, size_bytes}]` for every member except the manifest and `VERIFY.md` |
| `content_digest` | digest of the `files` list (packet id and built-at are outside it) |
| `omitted` | `[{component, reason, effect}]` — withheld excerpts, undisclosed prompts, undisclosed raw responses |
| `verify` | `python3 -m v9.brief verify <zip>   (or: yuclaw workbench brief verify <zip>)` |
| `limitations` | six fixed sentences (see `LIMITS` in `packet.py`) |

`records.json` (`schema: yuclaw.brief-records/1`): `versions[]` (`version_id`, `parent_version`, `language`, `text_view`,
effective `spans`, `transform`, `receipt`, `production`, `snapshot_digest`, `v8_tip_at_snapshot`, `recorded_at`,
`record_hash`), `receipts[]`, `reports[]`, `calibrations[]` (each `{record, signature, imported_at}` — the record as
imported, raw bytes never included), `resolutions[]`, `trust_roots_of_author` (labels and revoked flags only — never
installed by the receiver), `measurements` (section 8), `research_cutoff`.

**Verification** (`verify_packet`, never raises): result `SUCCESS` when no check `FAILED`; `MISMATCH` on any `FAILED` with
`first_discrepancy` naming the first; `UNSUPPORTED` for an unreadable or foreign archive (not a zip; `EXPORT_MANIFEST.json`
present without `BRIEF_MANIFEST.json` → the message names the v8 verifier; unknown `format`; non-ASCII or non-canonical
JSON; unknown records/snapshot schema). Checks, in order: `archive-safety`, `required-members`, `sha256+length` per file,
`unlisted-members`, `content-digest`, `canonical-form`, `snapshot-digest` (or `NOT_RECOMPUTABLE` when an excerpt was
withheld), `text-view-digest`, per version `version-text`, `span-binding`, `quotation` (`NOT_RECOMPUTABLE` when its excerpt
was withheld), `calculation` (`finance.recompute`, section 9), `parent-link`, `receipt-binding`; per imported record
`report-binding`, `report-execution` (`REPORT_ONLY`), `signature` (`NOT_APPLICABLE` for unsigned; `VERIFIED` when `VALID`
and `BOUND`; `FAILED` when `INVALID` or `MISMATCH`; otherwise `NOT_RECOMPUTABLE`; trust under the **receiver's** roots or
`NOT_EVALUATED` without one); `measurements-consistency` (`retries == attempts − operations`); `html-safety` (no
`<script`, CSP meta present). Exit codes: 0 / 1 / 3.

## 8. Measurement definitions (`measure.DEFINITIONS`, verbatim)

| Term | Definition |
|---|---|
| operation | one logical operation = one op_id; counted once however many times it was attempted |
| attempt | one measured run of an operation (a line in v9/operations.jsonl); retries are additional attempts of the same operation |
| retries | attempts − operations, over operations with ≥ 1 attempt |
| outcome | per attempt: COMMITTED \| DUPLICATE \| CONFLICT \| REFUSED \| FAILED \| READ — DUPLICATE is an idempotent retry answered by the existing record; CONFLICT is the same op_id with different bytes; REFUSED is a contract refusal with nothing written |
| elapsed_ms | wall-clock milliseconds of the software attempt, from entering the operation to leaving it; not labour time, not cognitive effort |
| eligible_denominator | all attempts recorded by this workspace's v9 surfaces since measurement began; nothing earlier is reconstructed |
| exclusions | v8 workbench operations (recorded in the v8 journal, not measured here); operations of other workspaces |
| missingness | an attempt whose line is corrupt or lacks finished_at is listed under missing, not estimated |

`measure.aggregate` (`schema: yuclaw.brief-measurements/1`) reports `operations`, `attempts`, `retries`, `outcomes`,
`durations` (`n`, `sum_ms`, `median_ms`, `max_ms`), `missing` (`corrupt_lines`, `missing_duration`), `per_task`, `scope`
(`workspace_id`, `since`, `until`).

## 9. Registered calculations (`finance.py`)

Calculator identity `v9.brief.finance/1 over v8.workbench.calc/1`. Every record carries `scope` (`metric`, `currency`,
`unit`, `scale_as_stated`, `basis`, `fiscal_period`); a change of any of them makes a comparison inapplicable
(`guidance change not computable across scopes`). Kinds:

| `kind` | Inputs | Record values | Recompute rule |
|---|---|---|---|
| `guidance_change` | `original_low/high`, `revised_low/high` | `midpoint_original`, `midpoint_revised`, `absolute_change` (exact), `relative_change` = `{numerator, denominator, formula "(new - old) / old * 100", value_percent, approximate, rounding {ROUND_HALF_EVEN, 2 decimals, applies_to}}` | midpoints, difference, numerator, denominator and rounded percent must all reproduce |
| `containment` | `low`, `high`, `actual` | `result` (`IN_RANGE` / `OUT_OF_RANGE` / other v8 states), `contains` | inclusive containment `low ≤ actual ≤ high` must reproduce |
| `containment_pair` | an `original` and a `revised` containment record | both results | both recompute; `FAILED` if they disagree |
| `range_comparison` | `original`, `revised` ranges | `v8_comparison` (`low_delta`, `high_delta`, `width_a`, `width_b`, `overlap`, `direction`, `result`) | deltas and widths must reproduce |
| `pending` | — | `result: PENDING_OUTCOME` | `NOT_APPLICABLE` (no arithmetic) |

`finance.recompute` returns `VERIFIED`, `FAILED` (with a detail), `NOT_RECOMPUTABLE` (an input is null) or `UNSUPPORTED`
(unknown kind). The relative change is the one place rounding exists; it is explicit in the record.

## 10. The reducer's five dimensions (`reducer.brief_view`)

One function derives every CLI, JSON, HTML and packet view. For each effective span of a version (base spans with later
`SPAN_LINK_RECORDED` records applied — the newest link for the same byte range wins), it computes:

| Dimension | Computation |
|---|---|
| `byte_integrity` | `span_problems` over the view bytes, then `sha256(bytes[start:end])` compared with `span_sha256` → `VERIFIED` / `FAILED` (with `recorded` and `observed`) |
| `recorded_origin` | the version's transform kind and implementation, renderer, template, `deterministic`, the span's assessor, the receipts bound to this view and the first receipt's `unknown` map |
| `issuer_trust` | for each receipt and each covering report with an envelope: `evaluate_signature` under the receiver's **current** roots (`signature`, `trust`, `binding`, `key_id`); unsigned records are omitted; a fixed note says trust concerns the signer, not the statement's truth |
| `substantive_support` | the span's `support`, forced to `INVALIDATED` when byte integrity failed; a registered calculation is recomputed (`calculation_check`) and a `SUPPORTED` span whose calculation `FAILED` becomes `CONTRADICTED`; with method, assessor, limits, claim, evidence, protected slots |
| `time_scope` | the snapshot digest and v8 tip; `later_information` true when an open review item names one of the span's dependencies (`claim:<id>` from the claim or claim_version/outcome evidence; `source:<id>` from source_excerpt evidence) or the span itself; labels "Later information exists" / "No later information recorded" |
| `detector` (separate) | the reports whose span covers the statement's byte range, each with `execution`, `signal`, `calibration` applicability, origin, and the label `Watermark check not requested` / `unavailable` / `completed` (the first covering report decides the statement's label) |

Brief-level fields: `coverage` (`mapped` = statements whose status is `SUPPORTED` / `ATTRIBUTED` / `CONTRADICTED` /
`UNRESOLVED` and that carry a claim, evidence or the `unresolved_claim` role; `identified`; `completeness:
NOT_ESTABLISHED`), `support_counts`, `review_items` (live dependency findings + the version's transform findings, with
resolutions), `open_review_items`, `evidence_label` (`Evidence bound` when no item is open and every statement's bytes are
`VERIFIED`; otherwise `Evidence incomplete`), `trust_roots`, `snapshot_summary`, the mission and vision sentences, the
dimension note and the four never-claims. A version with missing vault objects returns `status: INCOMPLETE` with no text or
statements.

## 11. Worked examples (fictional)

Both JSON files were used in GUIDE_EN.md against brief `brf-4625e1016814`, version B1, whose text view is
`6cdbeff73b90f95383bab82f6e4cd4c824e22d0366faa833e3f4fc0bb75eb267` and whose statement 9 ("Management cut guidance because
demand collapsed.") occupies bytes `1358..1407` with span digest `5dba767631f8fb11064804c7e711c0d075ca3d2ed3427f34d5447398761d57a2`.

### 11.1 A DetectionReport/1 that imports successfully

```json
{
 "schema": "yuclaw.detection-report/1",
 "view_sha256": "6cdbeff73b90f95383bab82f6e4cd4c824e22d0366faa833e3f4fc0bb75eb267",
 "span": {"start": 1358, "end": 1407, "span_sha256": "5dba767631f8fb11064804c7e711c0d075ca3d2ed3427f34d5447398761d57a2"},
 "detector": "example-watermark-detector",
 "detector_version": "0.0-fictional",
 "configuration": {},
 "key_scope": null,
 "origin": "operator_assertion",
 "observed_at": "2026-10-09T12:00:00Z",
 "disclosure": "withheld",
 "unknown": {
  "threshold": "not exposed by the detector interface",
  "p_value": "not reported by the detector",
  "scored_context_count": "not reported by the detector",
  "key_epoch": "not disclosed by the provider"
 },
 "execution": "COMPLETED",
 "signal": "NOT_DETECTED",
 "calibration": "NOT_ESTABLISHED",
 "selection": "the operator chose the unresolved causal sentence of version B1"
}
```

```
$ yuclaw workbench brief import-record --workspace ~/yuclaw-workspaces/research --kind report --file report_completed.json --label "fictional detector record 2"
[brief] report 77bdd65b2c9af9e2 imported — origin operator_assertion; signature NONE / trust NOT_EVALUATED / binding NOT_APPLICABLE; bound to {'brief_id': 'brf-4625e1016814', 'version_id': 'B1', 'language': 'en'}; execution COMPLETED signal NOT_DETECTED calibration NOT_ESTABLISHED
```

The same record with `"execution": "ACCESS_UNAVAILABLE"`, no `signal`, and `"failure_reason": "no detector endpoint is
reachable from this workbench; nothing was tested (fictional record for the guide)"` imports as
`execution ACCESS_UNAVAILABLE signal None calibration NOT_ESTABLISHED`.

### 11.2 A DetectionReport/1 that is refused

Same fields as 11.1 except:

```json
 "execution": "FAILED",
 "signal": "NOT_DETECTED",
 "calibration": "APPLICABLE",
 "failure_reason": "x"
```

```
$ yuclaw workbench brief import-record --workspace ~/yuclaw-workspaces/research --kind report --file report_bad.json
[brief] refused: detection report cannot be recorded: report.signal: must be absent unless execution is COMPLETED (FAILED cannot become NOT_DETECTED); report.calibration: APPLICABLE is meaningless without a COMPLETED execution; report.calibration: APPLICABLE requires calibration_ref (the CalibrationRecord it rests on)
```

Exit code 2; nothing was written (the attempt is counted as `REFUSED` in `measure`).

### 11.3 Binding refusals (contract passes, binding fails)

```
report refused: view 0000000000000000… is not a text view of any brief version in this workspace (the report is unbound)
report refused: tested span invalid for that view: span: start offset 19 is inside a multi-byte UTF-8 sequence
report refused: span digest 0000000000000000… does not match the bytes 1358..1407 of the view (5dba767631f8fb11…)
receipt refused: assembled_output_sha256 0000000000000000… is not a text view of any brief version here; a receipt binds to the exact assembled bytes
```

Imports are parsed by the strict JSON reader (`MAX_IMPORT_BYTES` = 1 MiB): duplicate keys, floats, non-finite numbers,
excessive depth or size are refused before any field is read (`import refused: IMPORT_… (duplicate keys, floats, …)`).

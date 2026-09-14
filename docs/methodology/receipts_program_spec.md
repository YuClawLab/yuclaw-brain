# Outsider receipt program — prospective specification (v7 candidate, PROPOSAL)

**Status: unadopted proposal.** Nothing here is registered. Adoption requires (1) an owner-issued registration record `{protocol_id, anchor, registered_at, policy_version}` — the window anchor (UTC date) and the actual registration instant (RFC3339 UTC, microseconds) are separate fields; the anchor never precedes the registration instant; a supplied anchor alone is not adoption — (2) a designated reviewer appointment, (3) the applicable privacy review, (4) owner-sent recruitment. Earlier attempts are never backdated into a prospective program: an attempt observed or first imported before `registered_at` (including earlier on the same UTC day) is `pre-registration` forever; a correction cannot move it forward because eligibility uses the earliest observed and imported instants of its whole lineage. The engine that implements this contract exists in `v3/receipts/` and runs today in local/synthetic mode.

## Records (four, kept distinct)
- **Submission** (`receipt-1`): attempt_id, activity_id, opaque participant_id and group_id, relationship ∈ {OWNER-AFFILIATED, RELATED-DISCLOSED, UNRELATED, UNKNOWN}, execution_control ∈ {SELF, ASSISTED, OPERATOR-RUN}, assistance (closed enumeration), incentive_outcome_dependent, outcome ∈ {REPRODUCED, FAILED, INCONCLUSIVE}, observed_at (UTC, µs), artifact_binding {artifact_type, sha256, size_bytes}, release_identity {tag, source_sha} (descriptive only), environment {os, python}, limitations, private. A submission can describe; it cannot assert qualification, verification, approval or authority (such fields are stripped with a diagnostic).
- **Observation**: what the verifier established from actual bytes. FULL binding only when sha256 and byte length match; unavailable bytes stay UNVERIFIED.
- **Review**: a reviewer's decision bound to the exact receipt digest, the policy version and the reviewer's APPOINTMENT (role + credential + policy, each appointment designated or synthetic on its own; a legacy or ambiguous appointment is HELD and never inferred real); a changed receipt or credential invalidates nothing historical and authorizes nothing new.
- **Public export**: a fresh typed object; pseudonyms are store-keyed; private fields never leave.

## Counting rules
- Primary population = **qualified attempts** (validated + FULL binding + designated QUALIFIED review + eligible relationship/control/incentive); qualified FAILED and INCONCLUSIVE are retained.
- Successful cohort = qualified AND REPRODUCED, reported separately; its artifact set is labeled as such.
- Distinct persons and control groups are deduplicated across activities and versions inside a registered window (candidate: fixed 28-day UTC windows from the anchor; day 27 is window 0, day 28 is window 1). Records of another protocol are never reassigned: they stay visible in their own unregistered bucket. Without registration: unwindowed, "registration pending"; window zero is never fabricated.
- Package evidence (wheel, sdist) is separate from site/endpoint/chain checks. A receipt covers only the exact bytes it binds: an RC wheel receipt does not cover the sdist or a rebuilt final wheel.
- Program evidence (any release; legacy PREFIX_ONLY log) is separate from exact-release evidence.

## Proposed floor (historical, unadopted)
Three successful qualified non-owner reproductions spanning two independent control groups and two supported environments, plus one scoped external challenge and one historical-consistency check. **Adoption status: none on record.** The floor does not gate any release until adopted; it is not waived by a date.

## Privacy
Identity mappings, relationship supporting facts, contacts and reviewer notes stay in the private store. No public hash commitment to guessable private material. Free text is published only with permission and after the language rail and the private denylist sweep.

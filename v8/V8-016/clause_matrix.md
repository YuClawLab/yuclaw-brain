# V8-016 — clause-level acceptance matrix (43 families)

Candidate source `35d1d9d97e5d85b09ceb5ac1178ac7396ca4c76e`. Requirement text verbatim. Statuses: `VERIFIED_BY_SOFTWARE_TESTS` 104, `NOT_VERIFIABLE_IN_THIS_ENVIRONMENT` 3, `VERIFIED_WITH_STATED_LIMIT` 13, `EXTERNAL_EVIDENCE_REQUIRED` 5. Full evidence lists are in `clause_matrix.json`.

## X-01 — Fresh installed wheel and sdist expose all four normal browser workflows, help and required resources outside the source checkout.

| Clause | Missing when V8-016 began | Work performed | Residual limitation | Status |
|---|---|---|---|---|
| fresh installs of the wheel and of the sdist expose all four browser workflows | nothing | — | none | `VERIFIED_BY_SOFTWARE_TESTS` |
| help and required resources are present | nothing | — | none | `VERIFIED_BY_SOFTWARE_TESTS` |
| outside the source checkout | nothing | — | none | `VERIFIED_BY_SOFTWARE_TESTS` |
| (platform scope of the statement) | macOS and Windows installs were never run | test_S05_X01_a_kernel_without_landlock_and_a_host_without_bubblewrap_closes_admission_only (a Linux host WITHOUT any isolation facility, simulated by a kernel-level refusal of the Landlock calls: every page and every workflow except SHD admission works) ¹ | macOS and Windows: NOT RUN and not certified. Supported and verified: Linux aarch64 (executor) and Linux x86-64 (hosted runner). A simulated unsupported Linux kernel is not another operating system. | `NOT_VERIFIABLE_IN_THIS_ENVIRONMENT` |

## X-02 — Shared IDs refer to real canonical claim/source/version objects; changing an actor label cannot change authenticated authority.

| Clause | Missing when V8-016 began | Work performed | Residual limitation | Status |
|---|---|---|---|---|
| shared ids refer to real canonical claim, source and version objects | a real second process changing the object between showing a form and submitting it | test_X02_a_claim_amended_by_another_process_makes_the_shown_form_stale (two server/worker processes, barrier-ordered; durable state: no packet) ¹ | none | `VERIFIED_BY_SOFTWARE_TESTS` |
| changing an actor label cannot change authenticated authority | editing the RECORDED label or capability in the journal itself | test_S01_an_edited_approval_or_principal_record_stops_the_workspace_instead_of_being_used (a rewritten capability, approver or expiry stops the workspace; authentication and admission refuse; nothing is appended) ¹ | none | `VERIFIED_BY_SOFTWARE_TESTS` |

## X-03 — Cross-role, cross-object and cross-workspace access is denied across HTTP, CLI/service and export surfaces; sessions remain separate.

| Clause | Missing when V8-016 began | Work performed | Residual limitation | Status |
|---|---|---|---|---|
| cross-role access is denied over HTTP | evidence that the role test would notice a disabled check | test_X11_each_disabled_control_is_caught_by_its_test_and_none_reaches_the_candidate (variant 'the capability check always passes' → detected) ¹ | none | `VERIFIED_BY_SOFTWARE_TESTS` |
| cross-object access is denied | NO test exercised another practitioner reading, attempting, revealing or reflecting in a foreign session (found by the sensitivity run: disabling the ownership rule failed no test) | test_X03_P03_another_practitioner_cannot_read_attempt_reveal_or_reflect_in_a_foreign_session (domain and HTTP level; durable state unchanged) ¹; sensitivity variant 'another practitioner's session is served' → now detected | none | `VERIFIED_BY_SOFTWARE_TESTS` |
| cross-workspace access is denied | nothing | — | none | `VERIFIED_BY_SOFTWARE_TESTS` |
| CLI / service surface | the actual command-line trust boundary was neither established nor tested; `principals add|rotate|revoke|list` were not described in the guide | test_X03_the_command_line_surface_its_record_and_what_it_never_reveals (exact subcommand surface; no module action exists on it; host-operator actions are journaled as host-operator(cli); credentials printed once and stored nowhere; the claim export carries no module record or private comparison; CLI revocation ends the browser session) ¹; operator guide §7 now states the boundary | BY DESIGN the host operator (anyone who can run commands as the OS user owning the workspace) is not constrained by principal roles; this is documented, journaled and not presented as a control over that person. | `VERIFIED_WITH_STATED_LIMIT` |
| export surfaces | nothing | test_P02_a_practitioner_who_is_also_reviewer_and_submitter_finds_the_reference_nowhere_before_the_attempt (a packet built by a multi-capability practitioner holds no unrevealed reference) ¹ | none | `VERIFIED_BY_SOFTWARE_TESTS` |
| sessions remain separate | nothing | — | none | `VERIFIED_BY_SOFTWARE_TESTS` |

## X-04 — Existing data, seven-step journeys, source-time correction and old export verification remain valid after additive migration.

| Clause | Missing when V8-016 began | Work performed | Residual limitation | Status |
|---|---|---|---|---|
| existing data stays valid after the additive migration | no automated test (the evidence needed the old wheel) | tests/fixtures/v8/pre_modules/ (journal and export written by the PRE-MODULE build, fictional fixture); test_X04_a_journal_and_an_export_written_before_the_modules_existed_stay_valid (the old journal opens with integrity OK; module events are appended without changing one earlier hash) ¹ | none | `VERIFIED_BY_SOFTWARE_TESTS` |
| seven-step journeys stay valid | nothing | — | the real-source journey cannot run on hosted CI | `VERIFIED_BY_SOFTWARE_TESTS` |
| source-time correction stays valid | nothing | — | none | `VERIFIED_BY_SOFTWARE_TESTS` |
| old export verification stays valid | no automated test | test_X04_a_journal_and_an_export_written_before_the_modules_existed_stay_valid (the pre-module export verifies under the new code with the same canonical digest; the claim's export rebuilt after module events has the same canonical digest) ¹ | the opposite direction (a NEW export read by the OLD build) needs the old wheel and stays a private run, repeated for this candidate (private record x04_compat) | `VERIFIED_WITH_STATED_LIMIT` |

## X-05 — Repeated operations, concurrent writers, crashes and restart preserve atomic decisions, capacity and history.

| Clause | Missing when V8-016 began | Work performed | Residual limitation | Status |
|---|---|---|---|---|
| repeated operations are idempotent | a retry by a caller that never received the answer | test_X05_C05_a_killed_reservation_spends_nothing_and_a_durable_one_is_spent_once (AFTER-mode: the event is durable, the retry returns it and spends nothing twice) ¹ | none | `VERIFIED_BY_SOFTWARE_TESTS` |
| concurrent writers | every concurrency test used threads of ONE process | test_X05_C05_two_processes_reserving_the_last_capacity_and_the_same_task ¹; test_X05_C04_concurrent_admission_from_separate_processes_stops_at_the_cap ¹; test_S02_a_revocation_by_another_process_between_the_worker_and_the_commit_wins ¹; test_S02_free_races_never_record_an_admission_after_the_revocation ¹; test_P03_commit_and_reveal_from_separate_processes_never_disclose_before_a_durable_attempt ¹; test_S03_another_process_rewriting_the_staged_input_never_yields_a_result_for_other_bytes ¹; test_X02_a_claim_amended_by_another_process_makes_the_shown_form_stale ¹ | none | `VERIFIED_BY_SOFTWARE_TESTS` |
| crashes | no kill at a byte boundary INSIDE the append; no torn line from a module writer; no check of budget conservation after a crash | test_X05_P03_a_killed_attempt_never_opens_the_comparison_and_a_durable_one_is_never_doubled ¹; test_X05_C05_a_killed_reservation_spends_nothing_and_a_durable_one_is_spent_once ¹; test_X05_S05_a_killed_decision_admits_nothing_and_the_retry_decides_once ¹; test_X05_other_writers_killed_before_their_event_leave_only_unreferenced_private_files ¹; SIGKILL at BEFORE / TORN (half a line, synced) / AFTER (line synced, caller never told) | see the durability clause | `VERIFIED_BY_SOFTWARE_TESTS` |
| restart | nothing | — | none | `VERIFIED_BY_SOFTWARE_TESTS` |
| atomic decisions, capacity and history are preserved | history immutability and budget conservation were asserted only in the happy path | every crash case asserts: earlier event hashes unchanged; reserved = sum of live reservations; remaining never negative; no comparison without a durable attempt | none | `VERIFIED_BY_SOFTWARE_TESTS` |
| (durability actually claimed) | FOUND: a private object was synced but its directory entry was not — after a power cut the journal could name an object whose rename was lost | core.fsync_dir: vault objects, signing keys, the credential registry and a newly created journal get a synced directory entry before the event that relies on them; test_X05_durable_names_are_written_before_the_event_that_relies_on_them (system-call order asserted) ¹; sensitivity variant 'the private object's name is not made durable' → detected; guide §5 states what was and was not checked | PHYSICAL POWER LOSS WAS NOT STAGED and cannot be on this host: whether synced data survives depends on the disk, its write cache and the file system. SIGKILL shows process-death behaviour only. | `NOT_VERIFIABLE_IN_THIS_ENVIRONMENT` |

## X-06 — New inputs obey bounds, safe rendering, CSRF/origin rules, secret handling and dependency/platform constraints.

| Clause | Missing when V8-016 began | Work performed | Residual limitation | Status |
|---|---|---|---|---|
| new inputs obey bounds | the multipart reader itself was unbounded in parts and accepted truncated and ambiguous bodies | server.Multipart: at most 32 parts (counted before splitting), closing delimiter required, a name given twice refused, part header bounded; socket timeout; incomplete bodies refused; test_S07_malformed_truncated_duplicated_and_inconsistent_uploads_are_refused_and_write_nothing ¹; test_S07_a_body_made_of_delimiters_is_refused_before_it_is_split ¹; test_S07_generated_mutants_never_crash_the_server_and_every_stored_object_matches_its_digest ¹ | none | `VERIFIED_BY_SOFTWARE_TESTS` |
| safe rendering | one payload family; FOUND: terminal-escape and bidirectional-override characters of untrusted text reached module pages verbatim | modules/web.esc shows control and bidi-override characters as visible \uXXXX; test_S06_every_family_of_hostile_text_stays_inert_data (14 families) ¹ | constructed families only | `VERIFIED_BY_SOFTWARE_TESTS` |
| CSRF and origin rules | FOUND by generated input: a CSRF field with non-ASCII bytes raised an unhandled TypeError (connection dropped, nothing written) | constant-time comparison on bytes at both sites; test_S07_generated_mutants_never_crash_the_server_and_every_stored_object_matches_its_digest (a dropped connection is a failure unless the client under-delivered) ¹ | none | `VERIFIED_BY_SOFTWARE_TESTS` |
| secret handling | the command line's outputs were not checked | test_X03_the_command_line_surface_its_record_and_what_it_never_reveals ¹ | none | `VERIFIED_BY_SOFTWARE_TESTS` |
| dependency and platform constraints | the declared LOWER bound of the dependency was never installed | private run: every v8 test on CPython 3.10.21 with cryptography==41.0.0 exactly (result in packaging.json → lower_bound_run); test_S05_X01_a_kernel_without_landlock_and_a_host_without_bubblewrap_closes_admission_only (platform without an isolation facility) ¹ | one lower-bound combination, on aarch64 only; not part of hosted CI | `VERIFIED_WITH_STATED_LIMIT` |

## S-01 — A submitter cannot enroll a root, self-approve a bundle, overwrite approval/audit records or use a copied approval for another purpose/workspace.

| Clause | Missing when V8-016 began | Work performed | Residual limitation | Status |
|---|---|---|---|---|
| a submitter cannot enroll a root | nothing | — | none | `VERIFIED_BY_SOFTWARE_TESTS` |
| a submitter cannot self-approve | nothing | test_X11_each_disabled_control_is_caught_by_its_test_and_none_reaches_the_candidate (disposable-copy variant → detected) ¹ | none | `VERIFIED_BY_SOFTWARE_TESTS` |
| approval and audit records cannot be overwritten | no test edited a MODULE record | test_S01_an_edited_approval_or_principal_record_stops_the_workspace_instead_of_being_used (expiry pushed out, capability raised, approver renamed: each stops the workspace) ¹ | removing the LAST record leaves a valid shorter chain: only a separately held checkpoint shows it (P-06) | `VERIFIED_WITH_STATED_LIMIT` |
| a copied approval is useless for another purpose | nothing | — | none | `VERIFIED_BY_SOFTWARE_TESTS` |
| a copied approval is useless in another workspace | nothing | — | none | `VERIFIED_BY_SOFTWARE_TESTS` |

## S-02 — Expiry, revocation, key rotation, clock uncertainty and concurrent use have explicit tested outcomes; no stale-cache authorization.

| Clause | Missing when V8-016 began | Work performed | Residual limitation | Status |
|---|---|---|---|---|
| expiry | nothing | — | none | `VERIFIED_BY_SOFTWARE_TESTS` |
| revocation | nothing | — | none | `VERIFIED_BY_SOFTWARE_TESTS` |
| key rotation | nothing | — | none | `VERIFIED_BY_SOFTWARE_TESTS` |
| clock uncertainty | nothing that software can add | — | a clock that is wrong by LESS than the distance to the last journal record is undetectable locally; key-file theft is outside the model | `VERIFIED_WITH_STATED_LIMIT` |
| concurrent use | no second real process | test_S02_a_revocation_by_another_process_between_the_worker_and_the_commit_wins (the REAL worker finishes, another process revokes, the commit refuses; journal order asserted) ¹; test_S02_free_races_never_record_an_admission_after_the_revocation (4 unsynchronized rounds: never an admission after the revocation) ¹ | none | `VERIFIED_BY_SOFTWARE_TESTS` |
| no stale-cache authorization | no evidence that the freshness test would notice a cached decision | test_X11_each_disabled_control_is_caught_by_its_test_and_none_reaches_the_candidate (variant 'no re-validation at the commit' → detected) ¹ | none | `VERIFIED_BY_SOFTWARE_TESTS` |

## S-03 — Strict JSON, duplicate keys, parser exhaustion, archive/file escape, link/special-file and unstable-read cases fail at the integrated entry point.

| Clause | Missing when V8-016 began | Work performed | Residual limitation | Status |
|---|---|---|---|---|
| strict JSON and duplicate keys | nothing | — | none | `VERIFIED_BY_SOFTWARE_TESTS` |
| parser exhaustion | the PARENT's multipart splitter | test_S07_a_body_made_of_delimiters_is_refused_before_it_is_split (600001 delimiters refused before any split; time and memory measured) ¹ | none | `VERIFIED_BY_SOFTWARE_TESTS` |
| archive and file escape | nothing | — | none | `VERIFIED_BY_SOFTWARE_TESTS` |
| link and special files | nothing | — | none | `VERIFIED_BY_SOFTWARE_TESTS` |
| unstable reads | a scheduler-timed race by a second real process | test_S03_another_process_rewriting_the_staged_input_never_yields_a_result_for_other_bytes (another process rewrites the file in place while the REAL restricted worker verifies it 30 times: 0 results for other bytes; then 3 calm runs accept) ¹ | a rename-replacement gives the path a new file the open descriptor never reads; the parent accepts only a result whose digest equals the stored bytes' digest | `VERIFIED_BY_SOFTWARE_TESTS` |
| failures happen at the integrated entry point | the HTTP upload entry itself | test_S07_malformed_truncated_duplicated_and_inconsistent_uploads_are_refused_and_write_nothing ¹; test_S07_generated_mutants_never_crash_the_server_and_every_stored_object_matches_its_digest ¹ | none | `VERIFIED_BY_SOFTWARE_TESTS` |

## S-04 — The actual restricted worker cannot read canary secrets, write forbidden host paths, reach a canary network endpoint or escape resource bounds.

| Clause | Missing when V8-016 began | Work performed | Residual limitation | Status |
|---|---|---|---|---|
| the actual restricted worker cannot read canary secrets | evidence that the test notices missing confinement | test_X11_each_disabled_control_is_caught_by_its_test_and_none_reaches_the_candidate (Landlock rules not applied → detected) ¹ | none | `VERIFIED_BY_SOFTWARE_TESTS` |
| cannot write forbidden host paths | as above | same variant | none | `VERIFIED_BY_SOFTWARE_TESTS` |
| cannot reach a canary network endpoint | as above | test_X11_each_disabled_control_is_caught_by_its_test_and_none_reaches_the_candidate (seccomp filter not installed → detected) ¹ | none | `VERIFIED_BY_SOFTWARE_TESTS` |
| cannot escape resource bounds | the descriptor limit and the CPU limit were set but never observed | live probe now REQUIRES 'open_beyond_descriptor_limit' DENIED; test_S04_the_cpu_limit_stops_a_spinning_worker_before_the_wall_clock_does (a spinning worker is ended by the CPU limit at about 20 s, not by the wall clock) ¹; test_X11_each_disabled_control_is_caught_by_its_test_and_none_reaches_the_candidate (resource limits not applied → detected) ¹ | none | `VERIFIED_BY_SOFTWARE_TESTS` |
| (which backend) | bubblewrap has never passed a probe on any host | — | landlock backend: verified by live probe on Linux aarch64 (executor) and Linux x86-64 (hosted run 35500468128). bubblewrap: NOT VERIFIED ANYWHERE — the missing capability is a host that lets bubblewrap create an unprivileged user namespace (the executor's AppArmor policy denies it; the runner has no bubblewrap); nothing was installed or loosened. Process confinement, not a container; no independent security review. | `NOT_VERIFIABLE_IN_THIS_ENVIRONMENT` |

## S-05 — Isolation failure, worker error or forged output never falls back to an unprotected success route.

| Clause | Missing when V8-016 began | Work performed | Residual limitation | Status |
|---|---|---|---|---|
| isolation failure never falls back to an unprotected route | a REAL process on a host with no working backend | tests/v8_mod_oldkernel.py (unprivileged seccomp filter: the kernel's Landlock calls answer ENOSYS; no bubblewrap on PATH; product unpatched); test_S05_X01_a_kernel_without_landlock_and_a_host_without_bubblewrap_closes_admission_only ¹ | a simulated unsupported Linux kernel; not macOS or Windows | `VERIFIED_BY_SOFTWARE_TESTS` |
| worker error never falls back | nothing | test_X05_S05_a_killed_decision_admits_nothing_and_the_retry_decides_once (a decision process killed after the worker: no decision exists until the retry) ¹ | none | `VERIFIED_BY_SOFTWARE_TESTS` |
| forged worker output never falls back | nothing | test_X11_each_disabled_control_is_caught_by_its_test_and_none_reaches_the_candidate (parent accepts a result for other bytes → detected) ¹ | none | `VERIFIED_BY_SOFTWARE_TESTS` |

## S-06 — Hostile instruction text stays data; a correctly approved false statement can pass byte checks without acquiring truth or benefit status.

| Clause | Missing when V8-016 began | Work performed | Residual limitation | Status |
|---|---|---|---|---|
| hostile instruction text stays data | breadth | test_S06_every_family_of_hostile_text_stays_inert_data (14 families: markup, handlers, URLs, entities, templates, shell, lookups, SQL, terminal escapes, bidi override, instructions to a model, path-like, long line, CSV formula) ¹ | constructed families say nothing about prompt injection in general; no immunity from AI attacks is claimed | `VERIFIED_WITH_STATED_LIMIT` |
| a correctly approved false statement passes byte checks without acquiring truth or benefit status | nothing | — | none | `VERIFIED_BY_SOFTWARE_TESTS` |

## E-01 — All eight inventory components distinguish measured, declared, unknown and justified non-applicable state.

| Clause | Missing when V8-016 began | Work performed | Residual limitation | Status |
|---|---|---|---|---|
| all eight components distinguish measured, declared, unknown and justified not-applicable | nothing | — | none | `VERIFIED_BY_SOFTWARE_TESTS` |

## E-02 — Controlled real dependency/grader/policy changes invalidate relevant reviews; unrelated changes retain justified reuse.

| Clause | Missing when V8-016 began | Work performed | Residual limitation | Status |
|---|---|---|---|---|
| controlled real dependency, grader and policy changes invalidate relevant reviews | the RUNTIME change was a substituted digest | test_E02_an_actually_different_installed_distribution_invalidates_what_depends_on_the_runtime (two interpreter processes whose import path holds a different installed VERSION of a distribution; the product's own measurement differs; dependent evidence → REEVALUATE) ¹ | none | `VERIFIED_BY_SOFTWARE_TESTS` |
| unrelated changes retain justified reuse | nothing | test_E02_an_actually_different_installed_distribution_invalidates_what_depends_on_the_runtime (evidence outside the runtime's closure → REUSE with reasons) ¹ | none | `VERIFIED_BY_SOFTWARE_TESTS` |

## E-03 — Authentication, ancestry conflicts and previous protected-test exposure survive credential revocation and relabeling.

| Clause | Missing when V8-016 began | Work performed | Residual limitation | Status |
|---|---|---|---|---|
| authentication of the acting roles | nothing | — | release authorizers and the other authority lists are NAMED ids; no release is authorized here (EVO-05) | `VERIFIED_BY_SOFTWARE_TESTS` |
| ancestry conflicts | nothing | — | none | `VERIFIED_BY_SOFTWARE_TESTS` |
| previous protected-test exposure survives credential revocation and relabeling | nothing | — | none | `VERIFIED_BY_SOFTWARE_TESTS` |

## E-04 — A matching unresolved failure persists across later passes/protocol names; an authorized evidence-backed resolution is append-only and scoped.

| Clause | Missing when V8-016 began | Work performed | Residual limitation | Status |
|---|---|---|---|---|
| a matching unresolved failure persists across later passes and protocol names | nothing | — | none | `VERIFIED_BY_SOFTWARE_TESTS` |
| an authorized evidence-backed resolution is append-only and scoped | nothing | — | none | `VERIFIED_BY_SOFTWARE_TESTS` |

## E-05 — Historical views use knowledge recorded by the cutoff; later review cannot manufacture earlier approval.

| Clause | Missing when V8-016 began | Work performed | Residual limitation | Status |
|---|---|---|---|---|
| historical views use knowledge recorded by the cutoff | nothing | — | one-second resolution of cutoffs | `VERIFIED_BY_SOFTWARE_TESTS` |
| a later review cannot manufacture an earlier approval | nothing | — | none | `VERIFIED_BY_SOFTWARE_TESTS` |

## E-06 — Targeted reevaluation and export are usable; unknown monetary amounts remain separate by currency; external deployment is not falsely claimed controlled.

| Clause | Missing when V8-016 began | Work performed | Residual limitation | Status |
|---|---|---|---|---|
| targeted reevaluation is usable | nothing | — | two built-in job types exist (by design of the 8.0.0 scope) | `VERIFIED_BY_SOFTWARE_TESTS` |
| export is usable | nothing | — | none | `VERIFIED_BY_SOFTWARE_TESTS` |
| unknown monetary amounts stay separate by currency | nothing | — | none | `VERIFIED_BY_SOFTWARE_TESTS` |
| external deployment is not falsely claimed controlled | nothing | — | a separately trusted deployment controller needs an institution's authorized integration (EVO-10) | `EXTERNAL_EVIDENCE_REQUIRED` |

## C-01 — Duplicate membership persists across repeated ingestion and restart; incompatible claim contracts remain separate.

| Clause | Missing when V8-016 began | Work performed | Residual limitation | Status |
|---|---|---|---|---|
| duplicate membership persists across repeated ingestion and restart | nothing | — | none | `VERIFIED_BY_SOFTWARE_TESTS` |
| incompatible claim contracts remain separate | nothing | — | none | `VERIFIED_BY_SOFTWARE_TESTS` |

## C-02 — Aliases and shared roots do not create independent corroboration; unknown ancestry stays unknown.

| Clause | Missing when V8-016 began | Work performed | Residual limitation | Status |
|---|---|---|---|---|
| aliases do not create independent corroboration | REQUIRED BEHAVIOUR MISSING: the same passage registered under a second accession counted as a second independent root | commons: canonical roots — identical passage bytes resolve to the first registration automatically; a reviewer or administrator can declare (and retract) an alias; new event COM_ALIAS_RECORDED; packets record cited and canonical roots so a receiver recomputes the same view; COM page section; test_C02_aliases_are_one_root_for_grouping_corroboration_and_disputes ¹ | no similarity is computed: a different rendering that nobody declared still looks like a separate root (stated on the page and in the guide) | `VERIFIED_WITH_STATED_LIMIT` |
| shared roots do not create independent corroboration | nothing | the shared-root view now groups by canonical root | none | `VERIFIED_BY_SOFTWARE_TESTS` |
| unknown ancestry stays unknown | nothing | — | none | `VERIFIED_BY_SOFTWARE_TESTS` |

## C-03 — Only an authorized recorded dispute/withdrawal changes queue handling; propagation, appeal and resolution preserve original history.

| Clause | Missing when V8-016 began | Work performed | Residual limitation | Status |
|---|---|---|---|---|
| only an authorized recorded dispute or withdrawal changes queue handling | nothing | — | none | `VERIFIED_BY_SOFTWARE_TESTS` |
| propagation | propagation through ALIASES (COM-04) did not exist | test_C02_aliases_are_one_root_for_grouping_corroboration_and_disputes (a dispute on any name of a document quarantines every group resting on it; a retraction ends that) ¹ | none | `VERIFIED_BY_SOFTWARE_TESTS` |
| appeal and resolution preserve the original history | nothing | — | none | `VERIFIED_BY_SOFTWARE_TESTS` |

## C-04 — Stable-principal caps, rate/storage bounds and concurrent admission resist simple rename/replay/flood attempts.

| Clause | Missing when V8-016 began | Work performed | Residual limitation | Status |
|---|---|---|---|---|
| stable-principal caps | nothing | test_X11_each_disabled_control_is_caught_by_its_test_and_none_reaches_the_candidate (contributor cap not counted → detected) ¹ | none | `VERIFIED_BY_SOFTWARE_TESTS` |
| rate and storage bounds | nothing | — | none | `VERIFIED_BY_SOFTWARE_TESTS` |
| concurrent admission | separate processes | test_X05_C04_concurrent_admission_from_separate_processes_stops_at_the_cap (six processes at one barrier against a cap of three → exactly three) ¹ | none | `VERIFIED_BY_SOFTWARE_TESTS` |
| resists simple rename, replay and flood attempts | nothing | — | collusion between principals and real-world Sybil identity are outside what local credentials can establish (COM-05) | `VERIFIED_WITH_STATED_LIMIT` |

## C-05 — Reservations, leases, partial work, cancellation, rollover and urgent overrides neither double-spend nor silently erase capacity/backlog.

| Clause | Missing when V8-016 began | Work performed | Residual limitation | Status |
|---|---|---|---|---|
| reservations never double-spend | separate processes; process death | test_X05_C05_two_processes_reserving_the_last_capacity_and_the_same_task ¹; test_X05_C05_a_killed_reservation_spends_nothing_and_a_durable_one_is_spent_once ¹ | none | `VERIFIED_BY_SOFTWARE_TESTS` |
| leases, partial work, cancellation, rollover and urgent overrides never silently erase capacity or backlog | nothing | — | none | `VERIFIED_BY_SOFTWARE_TESTS` |

## C-06 — Practice reserve, fitting smaller tasks, backlog age, estimates, observed duration and manually declared effort are distinguishable.

| Clause | Missing when V8-016 began | Work performed | Residual limitation | Status |
|---|---|---|---|---|
| practice reserve, fitting smaller tasks, backlog age, estimates, observed duration and declared effort are distinguishable | nothing | — | a timer and a declaration are not verified attentive work (COM-06) | `VERIFIED_BY_SOFTWARE_TESTS` |

## C-07 — A reproducible FIFO comparison uses identical synthetic assumptions; human productivity/error reduction remains unestablished.

| Clause | Missing when V8-016 began | Work performed | Residual limitation | Status |
|---|---|---|---|---|
| a reproducible FIFO comparison uses identical synthetic assumptions | nothing | — | none | `VERIFIED_BY_SOFTWARE_TESTS` |
| human productivity or error reduction remains unestablished | cannot be produced by software | — | needs real participants (COM-12) | `EXTERNAL_EVIDENCE_REQUIRED` |

## P-01 — Frozen task and sources are useful in the browser; reference identity cannot silently change after opening.

| Clause | Missing when V8-016 began | Work performed | Residual limitation | Status |
|---|---|---|---|---|
| frozen task and sources are useful in the browser | nothing | — | whether a task is SUITABLE needs a qualified reviewer (PRC-01) | `EXTERNAL_EVIDENCE_REQUIRED` |
| reference identity cannot silently change after opening | nothing | — | none | `VERIFIED_BY_SOFTWARE_TESTS` |

## P-02 — No early answer through direct HTTP/API/static/help/journal/export/cache/error/alternate-view access by the practitioner.

| Clause | Missing when V8-016 began | Work performed | Residual limitation | Status |
|---|---|---|---|---|
| no early answer through direct HTTP/API, static, help, journal, export, error or alternate views | a practitioner who ALSO holds other capabilities reaches claim pages, the journal, COM, EVO, SHD and exports — never swept | test_P02_a_practitioner_who_is_also_reviewer_and_submitter_finds_the_reference_nowhere_before_the_attempt (27 URLs + reveal POST + a full export + the journal bytes, before the attempt) ¹ | whether a claim page itself gives the answer away is the curator's judgement; such sessions are labelled NOT_CONFINED | `VERIFIED_WITH_STATED_LIMIT` |
| no early answer through a cache | only one page was checked | test_P02_a_practitioner_who_is_also_reviewer_and_submitter_finds_the_reference_nowhere_before_the_attempt (every page reached carries Cache-Control: no-store) ¹ | none | `VERIFIED_BY_SOFTWARE_TESTS` |
| (would the sweep notice?) | nothing | test_X11_each_disabled_control_is_caught_by_its_test_and_none_reaches_the_candidate (the comparison opens without an attempt → detected) ¹ | none | `VERIFIED_BY_SOFTWARE_TESTS` |

## P-03 — Only a committed attempt unlocks a comparison; retries and concurrent requests cannot leak or overwrite the original attempt.

| Clause | Missing when V8-016 began | Work performed | Residual limitation | Status |
|---|---|---|---|---|
| only a committed attempt unlocks a comparison | process death between the private write and the event | test_X05_P03_a_killed_attempt_never_opens_the_comparison_and_a_durable_one_is_never_doubled ¹ | none | `VERIFIED_BY_SOFTWARE_TESTS` |
| retries cannot leak or overwrite the original attempt | nothing | — | none | `VERIFIED_BY_SOFTWARE_TESTS` |
| concurrent requests cannot leak or overwrite the original attempt | separate processes; a second, DIFFERENT attempt racing the first; another practitioner | test_P03_commit_and_reveal_from_separate_processes_never_disclose_before_a_durable_attempt (three processes per round: two different attempts and a reveal) ¹; test_X03_P03_another_practitioner_cannot_read_attempt_reveal_or_reflect_in_a_foreign_session ¹ | none | `VERIFIED_BY_SOFTWARE_TESTS` |

## P-04 — Assisted/already-exposed sessions are accepted with truthful labels; unresolved judgments are supported.

| Clause | Missing when V8-016 began | Work performed | Residual limitation | Status |
|---|---|---|---|---|
| assisted and already-exposed sessions are accepted with truthful labels; unresolved judgments are supported | nothing | — | a declaration is the practitioner's statement | `VERIFIED_BY_SOFTWARE_TESTS` |

## P-05 — Reflection, reviewer feedback and local delayed-task due states work without rewriting attempts or inventing human research.

| Clause | Missing when V8-016 began | Work performed | Residual limitation | Status |
|---|---|---|---|---|
| reflection, reviewer feedback and local delayed-task due states work without rewriting attempts | nothing | — | none | `VERIFIED_BY_SOFTWARE_TESTS` |
| without inventing human research | cannot be produced by software | — | learning transfer needs a consented study (PRC-09) | `EXTERNAL_EVIDENCE_REQUIRED` |

## P-06 — Export permissions/redaction protect participant content and hidden references; independent checkpoints detect modification/truncation.

| Clause | Missing when V8-016 began | Work performed | Residual limitation | Status |
|---|---|---|---|---|
| export permissions protect participant content | nothing | test_X03_the_command_line_surface_its_record_and_what_it_never_reveals (the command-line export too) ¹ | principal identifiers are exported as they are: a packet is not anonymous (PRC-08) | `VERIFIED_WITH_STATED_LIMIT` |
| redaction protects hidden references | nothing | test_P02_a_practitioner_who_is_also_reviewer_and_submitter_finds_the_reference_nowhere_before_the_attempt ¹ | none | `VERIFIED_BY_SOFTWARE_TESTS` |
| independent checkpoints detect modification and truncation | nothing | — | none | `VERIFIED_BY_SOFTWARE_TESTS` |

## P-07 — Later source/EVO changes annotate the session's current interpretation without replacing historical evidence or answers.

| Clause | Missing when V8-016 began | Work performed | Residual limitation | Status |
|---|---|---|---|---|
| later source or EVO changes annotate the session's current interpretation without replacing historical evidence or answers | nothing | — | none | `VERIFIED_BY_SOFTWARE_TESTS` |

## X-07 — End-to-end SHD -> COM -> PRC plus EVO change/review behavior can be repeated from both installed artifacts.

| Clause | Missing when V8-016 began | Work performed | Residual limitation | Status |
|---|---|---|---|---|
| the end-to-end chain repeats from both installed artifacts | nothing | — | hosted for 0c58de33; NOT hosted for the V8-016 commit | `VERIFIED_BY_SOFTWARE_TESTS` |

## X-08 — Fresh receiver recomputes valid exports, rejects forged relationships and distinguishes integrity from receiver trust.

| Clause | Missing when V8-016 began | Work performed | Residual limitation | Status |
|---|---|---|---|---|
| a fresh receiver recomputes valid exports | nothing | test_C02_aliases_are_one_root_for_grouping_corroboration_and_disputes (alias-bearing COM views recompute without the sender's sources) ¹ | none | `VERIFIED_BY_SOFTWARE_TESTS` |
| rejects forged relationships | nothing | — | none | `VERIFIED_BY_SOFTWARE_TESTS` |
| distinguishes integrity from receiver trust | nothing | — | none | `VERIFIED_BY_SOFTWARE_TESTS` |

## X-09 — Expanded CI checks are rehearsed and ready; hosted status is tied only to the SHA actually run after a separately approved push.

| Clause | Missing when V8-016 began | Work performed | Residual limitation | Status |
|---|---|---|---|---|
| expanded CI checks are rehearsed and ready | nothing | the new tests run inside the existing tests and python-floor jobs; no workflow change was needed | none | `VERIFIED_BY_SOFTWARE_TESTS` |
| hosted status is tied only to the SHA actually run after a separately approved push | the V8-015 commit had no hosted run | run 35500468128 ↔ 0c58de3387fa84d1037dd45c92753d1d942bcb92: success (v8/V8-016/hosted_ci.json) | the V8-016 commit has NO hosted run | `VERIFIED_WITH_STATED_LIMIT` |

## X-10 — Package contents exclude credentials, private approvals/participant records and order files; claims map to observed evidence and explicit limits.

| Clause | Missing when V8-016 began | Work performed | Residual limitation | Status |
|---|---|---|---|---|
| package contents exclude credentials, private approvals, participant records and order files | nothing | the new test fixtures and harnesses live under tests/ and are in neither distribution (checked by the same inspection) | none | `VERIFIED_BY_SOFTWARE_TESTS` |
| claims map to observed evidence and explicit limits | nothing | this matrix | none | `VERIFIED_BY_SOFTWARE_TESTS` |

## S-07 — Intake is bounded before complex parent parsing; restricted-worker setup leaks no unintended environment or handles; all output/error channels are bounded.

| Clause | Missing when V8-016 began | Work performed | Residual limitation | Status |
|---|---|---|---|---|
| intake is bounded before complex parent parsing | the multipart splitter was never exercised with hostile input | test_S07_malformed_truncated_duplicated_and_inconsistent_uploads_are_refused_and_write_nothing (15 hand-made cases + a stalled client) ¹; test_S07_a_body_made_of_delimiters_is_refused_before_it_is_split ¹; test_S07_generated_mutants_never_crash_the_server_and_every_stored_object_matches_its_digest (seed 20260920, 160 mutants; no 5xx, no dropped connection, every stored object matches its digest, no file outside the vault) ¹ | local generated cases, not a coverage-guided fuzzer | `VERIFIED_BY_SOFTWARE_TESTS` |
| restricted-worker setup leaks no unintended environment or handles | nothing | — | none | `VERIFIED_BY_SOFTWARE_TESTS` |
| all output and error channels are bounded | nothing | — | none | `VERIFIED_BY_SOFTWARE_TESTS` |

## S-08 — Offline results expose trust/revocation freshness; old imports cannot roll back trusted state, revive a revoked credential or reinterpret an approval as another signed record type.

| Clause | Missing when V8-016 began | Work performed | Residual limitation | Status |
|---|---|---|---|---|
| offline results expose trust and revocation freshness | nothing | — | none | `VERIFIED_BY_SOFTWARE_TESTS` |
| old imports cannot roll back trusted state | nothing that software can add | — | a receiver that never verified a newer packet from that origin cannot know a snapshot is old; the result states the snapshot's revision and time and changes nothing locally | `VERIFIED_WITH_STATED_LIMIT` |
| old imports cannot revive a revoked credential | nothing | — | none | `VERIFIED_BY_SOFTWARE_TESTS` |
| an approval cannot be reinterpreted as another signed record type | nothing | — | none | `VERIFIED_BY_SOFTWARE_TESTS` |

## E-07 — Actual execution uses the measured immutable subject; swapping an input or omitting a required dependency cannot preserve an invalid review result.

| Clause | Missing when V8-016 began | Work performed | Residual limitation | Status |
|---|---|---|---|---|
| actual execution uses the measured immutable subject | nothing | — | none | `VERIFIED_BY_SOFTWARE_TESTS` |
| swapping an input cannot preserve an invalid review result | nothing | — | none | `VERIFIED_BY_SOFTWARE_TESTS` |
| omitting a required dependency cannot preserve an invalid review result | nothing | — | none | `VERIFIED_BY_SOFTWARE_TESTS` |

## C-08 — Submitter cost manipulation cannot inflate/reduce established duplicate-group cost or evade reservations; estimates and scheduling authority remain distinguishable.

| Clause | Missing when V8-016 began | Work performed | Residual limitation | Status |
|---|---|---|---|---|
| submitter cost manipulation cannot inflate or reduce an established group's cost or evade reservations | nothing | — | none | `VERIFIED_BY_SOFTWARE_TESTS` |
| estimates and scheduling authority remain distinguishable | nothing | — | none | `VERIFIED_BY_SOFTWARE_TESTS` |

## C-09 — Aging/escalation and budget reduction preserve historical consumption and show starvation/overrun explicitly without creating capacity.

| Clause | Missing when V8-016 began | Work performed | Residual limitation | Status |
|---|---|---|---|---|
| aging, escalation and budget reduction preserve historical consumption and show starvation and overrun explicitly without creating capacity | nothing | — | none | `VERIFIED_BY_SOFTWARE_TESTS` |

## X-11 — Valid authorized counterparts succeed; targeted isolated test variants show that key boundary tests detect deliberately disabled controls.

| Clause | Missing when V8-016 began | Work performed | Residual limitation | Status |
|---|---|---|---|---|
| valid authorized counterparts succeed | nothing | every new V8-016 test carries its counterpart (calm verification, the owner's attempt, the unfiltered host, the valid upload, the retry) | none | `VERIFIED_BY_SOFTWARE_TESTS` |
| targeted isolated variants show that key boundary tests detect deliberately disabled controls | NO variant touched the isolation boundary; the three existing ones patched one process in memory | test_X11_each_disabled_control_is_caught_by_its_test_and_none_reaches_the_candidate (14 controls disabled one at a time in DISPOSABLE COPIES (fake HOME, own TMPDIR): Landlock, seccomp, resource limits, digest re-check, capability check, distinct approver, session ownership, commit-time re-validation, plan capacity, contributor cap, reveal rule, stale selection, truncated upload, durable name — each caught; the unmodified copy passes; the candidate's files hash the same before and after; every copy deleted) ¹ | fourteen chosen controls, not every line of the product | `VERIFIED_BY_SOFTWARE_TESTS` |

## X-12 — Reproducible workload and performance measurements disclose resource bounds, workload sizes, hardware, denominators, unfavorable outcomes and comparable baselines.

| Clause | Missing when V8-016 began | Work performed | Residual limitation | Status |
|---|---|---|---|---|
| reproducible workload and performance measurements disclose bounds, sizes, hardware, denominators, unfavorable outcomes and baselines | nothing required | v8/V8-016/verification_workloads.json: seeds, rounds, sizes, timings and the unfavorable results of the new tests (3 of 4 reveal races arrived first and were refused; 30 of 30 hammered reads were refused; 2 of 160 mutants exposed a defect) | one executor class (aarch64) for timings; hosted x86-64 runs are pass/fail, not benchmarks | `VERIFIED_WITH_STATED_LIMIT` |
| human benefit | cannot be produced by software | — | PENDING | `EXTERNAL_EVIDENCE_REQUIRED` |

¹ added in V8-016: no hosted run covers it.

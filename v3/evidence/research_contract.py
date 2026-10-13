"""Shared public research contracts; no data or model calls."""
AS_OF_RECIPE = (
    "Load /why/{TICKER}.json for history_url and history_manifest_url. Use ONLY "
    "the COMPLETE history file whose build_id, SHA-256, byte count and object "
    "count match the manifest. Filter available_as_of <= D after normalizing "
    "timestamps to UTC; a date-only D means 23:59:59.999999 UTC. Do not substitute "
    "filing_date or generated. A capped PREVIEW returns INCOMPLETE unless returned "
    "equals total_available; it cannot establish zero historical evidence. D "
    "outside corpus_start/corpus_end returns OUT_OF_RANGE. Classification at D "
    "uses the label_history entry with the maximum eligible date, not list order. "
    "Before that ribbon, use yuclaw replay TICKER --date D on a research backend."
)

EVENT_HASH_SCOPE = (
    "source_hash identifies the original stored event record; it is not a digest "
    "of the displayed excerpt or the original SEC file. Public event inclusion "
    "verification: NOT_AVAILABLE. /evidence/verify.json describes SIGNAL snapshot "
    "ledger checks and does not authenticate this event hash. Quote occurrence, "
    "semantic support, arithmetic and external provenance are separate checks."
)

LAB_LIMITATIONS = [
    "Forward statistical estimates are exploratory; fixed-sample p-values are not "
    "anytime-valid under repeated inspection. Read current uncertainty and power in the statistical tables.",
    "In-sample results are a historical reconstruction with later scoring design and "
    "approximated market inputs, not a contemporaneous forward record. The declared "
    "Llama 3.1 pretraining cutoff predates the filings; see the canonical look-ahead statement.",
    "Price-return definitions, missing prices and corporate-action exclusions limit "
    "interpretation; these results are not a total-return investment performance claim.",
    "IC rows are signal snapshots; repeated issuer/date observations may occur. "
    "Snapshot count, distinct issuer/date count and independent information count differ.",
    "The selected universe includes equities and funds with overlapping exposures; "
    "it does not represent independent randomly sampled firms.",
    "Insider evidence: batch coverage 2026-02-18 to 2026-05-15; live from 2026-07-16; "
    "the gap is backfilled with ingestion-time available_as_of.",
]

REPLAY_SCOPE = (
    "Exit 0 checks the core expected statistical tables and bundled signal-ledger "
    "consistency. External provenance is UNVERIFIED unless a separately acquired "
    "ledger and its independently obtained SHA-256 are supplied. Historical "
    "in-sample inputs and vendor-derived returns are not independently authenticated. "
    "Use --require-external-ledger to require full external coverage of forward inputs."
)

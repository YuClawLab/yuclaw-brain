# Verify a signal hasn't been edited

> Research/education only — not investment advice.

Every YUCLAW signal published on a trading day has its content hash appended to a JSONL file in a public git repo (`yuclaw-trust`). `yuclaw verify` recomputes the hash from the live database and compares.

```bash
python3 -m v3.cli verify NVDA --date 2026-05-20
```

```text
OK  VERIFIED: signal unaltered since ledger commit   NVDA @ 2026-05-20
    ledger commit:   2379ac8  (2026-05-20 12:43:23 -0600)
    ledger label:    HOLD  (current: HOLD)
    content_hash:    5e1897907999...

Verifies record integrity and timing — not investment merit.
```

Three outcomes:

| status | meaning |
|---|---|
| `VERIFIED` | Ledger entry exists; recomputed hash matches. Signal unaltered since publication. |
| `INTEGRITY_FAILURE` | Entry exists but hashes differ. The published snapshot was edited after the fact. |
| `NOT_FOUND` | No ledger entry. Either YUCLAW didn't publish that day or the ledger run hasn't fired. |

This is tamper-evidence, **not** a strategy proof. It confirms record integrity and timing — not investment merit.

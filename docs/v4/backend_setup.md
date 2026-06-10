# Connecting a YUCLAW backend (live signals)

`pip install yuclaw && yuclaw demo` works **with no backend** — it replays a bundled,
frozen capture of the canonical **AMD @ 2026-05-20** signal, including the
byte-identical ledger-hash verification.

To run signals for **any ticker or date** (`yuclaw why`, `memo`, `share`, `cascade`,
`verify` beyond the bundled demo), you need the YUCLAW evidence backend:

1. **Postgres** with the `yuclaw_events` database (schema in `v3/schema.sql`,
   migrations in `v3/migrations/`). The code connects via `dbname=yuclaw_events`.
2. **The signal pipeline** populated — EDGAR poller + event extraction + the
   snapshot writer (`v3.signal.snapshot_writer`) so `signal_snapshots` has rows.
3. *(optional)* the public ledger checkout (`yuclaw-trust`) for live `verify`
   permalinks; the bundled demo carries its own ledger entry.

Until then, only the bundled demo signal resolves offline. This keeps the
zero-config first experience honest: you always see real evidence and a real,
verifiable hash — just for one frozen signal — rather than a backend error.

See the repository README and `docs/` for full pipeline setup.

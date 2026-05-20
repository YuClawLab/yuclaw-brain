"""Track-record / backtest tooling.

`outcome_updater` computes forward returns against `price_history`;
`panels` aggregates by signal_label; `render_html` produces the static
two-panel page.

Price data in `price_history` is internal-only. Yahoo terms forbid raw
OHLCV redistribution — only derived metrics (returns, hit-rates) leave
the system.
"""

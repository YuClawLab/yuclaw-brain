"""
Generate the five starter notebooks from a single script so the markdown
disclaimers stay in lockstep with the SDK's compliance constants. Run
once whenever the notebooks need rebuilding; not part of the runtime
package.

    python3 sdk/_build_notebooks.py
"""
from __future__ import annotations

from pathlib import Path

import nbformat as nbf

DISCLAIMER = (
    "> **Disclaimer.** Research and education only. Not investment advice. "
    "Signal labels are research classifications, not buy/sell recommendations. "
    "YUCLAW is not a registered investment adviser. Past results — backtested or "
    "forward-tracked — do not predict future performance."
)

OUT_DIR = Path(__file__).resolve().parent / "notebooks"


def _nb(cells: list) -> nbf.NotebookNode:
    nb = nbf.v4.new_notebook()
    nb["cells"] = cells
    nb["metadata"] = {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.12"},
    }
    return nb


def _md(text: str): return nbf.v4.new_markdown_cell(text)
def _code(text: str): return nbf.v4.new_code_cell(text)


def header(title: str, intro: str) -> list:
    return [
        _md(f"# {title}\n\n{intro}\n\n{DISCLAIMER}"),
    ]


def quickstart() -> nbf.NotebookNode:
    return _nb(header(
        "01 · Quickstart",
        "Connect to a local YUCLAW instance, pull a live composite signal, and "
        "ask the SDK for the evidence behind it."
    ) + [
        _md("## Install + import\n\n"
            "`pip install yuclaw-py`. The cell below imports the SDK and prints the version."),
        _code(
            "import yuclaw_py\n"
            "yuclaw_py.__version__"
        ),
        _md("## Connect\n\n"
            "`source='postgres'` reads the local yuclaw_events database — the "
            "default v3.0 operator setup. `source='api'` will work once the hosted "
            "REST endpoint goes live (Day 11)."),
        _code(
            "client = yuclaw_py.Client(source='postgres', dsn='dbname=yuclaw_events')\n"
            "client.source"
        ),
        _md("## A composite signal"),
        _code(
            "sig = client.signal('NVDA')\n"
            "print('label :', sig['label'])\n"
            "print('score :', round(sig['score'], 3))\n"
            "print('time  :', sig['signal_time'])\n"
            "sig['components']"
        ),
        _md("Note the `compliance` dict on every signal-bearing return:"),
        _code("sig['compliance']"),
        _md("## Why?\n\n`client.why(ticker)` returns the same signal plus the top "
            "evidence events that informed it."),
        _code(
            "why = client.why('NVDA', n_evidence=3)\n"
            "for ev in why['evidence']:\n"
            "    print(f\"  {ev['event_type']:<15s}  mag={ev['magnitude']:.2f}  {ev['raw_excerpt'][:70]}\")\n"
        ),
        _md("---\n" + DISCLAIMER),
    ])


def evidence_layer() -> nbf.NotebookNode:
    return _nb(header(
        "02 · The evidence layer",
        "v3.0's central differentiator is the **evidence layer**: every signal "
        "ties back to a source SEC filing or deterministic cascade. This notebook "
        "walks through how to inspect the raw events feeding a ticker."
    ) + [
        _md("## All events for a ticker"),
        _code(
            "import yuclaw_py\n"
            "client = yuclaw_py.Client()\n"
            "events = client.events('AMD', since='2026-04-01')\n"
            "print(f'{len(events)} accepted events for AMD since 2026-04-01')\n"
            "events[['event_type', 'magnitude', 'direction', 'available_as_of', 'cascade_depth']].head(10)"
        ),
        _md("## Event-type mix\n\n"
            "Form 4 insider trades dominate volume; 8-K material events are the rarer signal."),
        _code(
            "events['event_type'].value_counts()"
        ),
        _md("## SourceLock: every event has a verifiable source URL"),
        _code(
            "for _, row in events.head(3).iterrows():\n"
            "    print(f\"{row['event_type']:<14s}  {row['available_as_of']}\")\n"
            "    print(f\"  excerpt: {row['raw_excerpt'][:90]}\")\n"
            "    print(f\"  source : {row['source_url']}\")\n"
            "    print()"
        ),
        _md("## Cascade vs primary\n\n"
            "Cascade events carry `cascade_depth >= 1` — they're derived from a "
            "primary event on an upstream ticker via the supply-chain graph. "
            "Their magnitudes are intentionally smaller."),
        _code(
            "events.groupby('cascade_depth').agg(\n"
            "    n=('event_id', 'count'),\n"
            "    mean_magnitude=('magnitude', 'mean'),\n"
            ").round(3)"
        ),
        _md("---\n" + DISCLAIMER),
    ])


def time_machine() -> nbf.NotebookNode:
    return _nb(header(
        "03 · Time-machine replay",
        "Replay a ticker's composite signal as it would have looked on a past date. "
        "Only data with `available_as_of <= as_of` feeds the computation — a "
        "guarantee enforced by point-in-time DB filters in C6 / C8 / C9."
    ) + [
        _md("## Replay AMD on three dates"),
        _code(
            "import yuclaw_py\n"
            "client = yuclaw_py.Client()\n"
            "for d in ['2026-03-01', '2026-04-15', '2026-05-13']:\n"
            "    snap = client.replay('AMD', d)\n"
            "    print(f\"{d}: {snap['label']:<15s}  score={snap['score']:+.3f}\")\n"
        ),
        _md("## What does each component contribute on a given date?"),
        _code(
            "snap = client.replay('AMD', '2026-03-01')\n"
            "import pandas as pd\n"
            "pd.Series(snap['components']).round(3).rename('score').to_frame()"
        ),
        _md("Notice C6 (event impact) and C8 (cascade) are point-in-time exact — "
            "they query events with `available_as_of <= as_of`. The market components "
            "(C1, C3, C4, C5, C7) are approximations on historical dates because "
            "v2.3.0 currently caches only the latest market snapshot. See "
            "`docs/methodology/backfill.md` for the full caveat."),
        _md("---\n" + DISCLAIMER),
    ])


def validation_analysis() -> nbf.NotebookNode:
    return _nb(header(
        "04 · In-Sample Event Validation",
        "Load the two YUCLAW panels and explore hit rates / median returns. "
        "Each hit rate is shown alongside its `n` — never quote a percentage "
        "without its sample size. "
        "**Important caveat**: the in-sample panel was *reconstructed* via "
        "point-in-time replay, with market components running at 0.3 confidence. "
        "Treat it as a check on the **evidence layer** (C6 / C8 / C9), not as a "
        "validated live-trading backtest."
    ) + [
        _md("## Load both panels"),
        _code(
            "import yuclaw_py\n"
            "import pandas as pd\n"
            "import matplotlib.pyplot as plt\n"
            "\n"
            "client = yuclaw_py.Client()\n"
            "panels = client.validation()\n"
            "in_sample, forward = panels['in_sample'], panels['forward']\n"
            "print(f\"In-sample: {len(in_sample)} rows ({in_sample['signal_date'].min()} → {in_sample['signal_date'].max()})\")\n"
            "print(f\"Forward:   {len(forward)} rows ({forward['signal_date'].min()} → {forward['signal_date'].max() if len(forward) else 'n/a'})\")"
        ),
        _md("## Hit rate by label and horizon (in-sample) — always with n"),
        _code(
            "directional = ['STRONG_BULLISH', 'BULLISH', 'WEAKENING', 'NEGATIVE_EVENT', 'BEARISH_WATCH']\n"
            "sub = in_sample[in_sample['signal_label'].isin(directional)].copy()\n"
            "summary = sub.groupby('signal_label').agg(\n"
            "    n=('snapshot_id', 'count'),\n"
            "    hit_1d=('hit_1d', 'mean'),\n"
            "    hit_5d=('hit_5d', 'mean'),\n"
            "    hit_20d=('hit_20d', 'mean'),\n"
            "    median_5d=('return_5d', 'median'),\n"
            ").round(3)\n"
            "summary  # n column is always visible alongside the hit rates"
        ),
        _md("## Median 5-day return by label"),
        _code(
            "ax = (sub.groupby('signal_label')['return_5d'].median() * 100).sort_values().plot(\n"
            "    kind='barh', figsize=(8, 4), title='Median 5d return by label — in-sample (May 2026)')\n"
            "ax.set_xlabel('median return %')\n"
            "plt.tight_layout()"
        ),
        _md("## Forward panel\n\nDay 0 = 2026-05-20. Outcomes mature daily; expect "
            "this panel to be sparse for the first few weeks after launch."),
        _code(
            "print(f'Forward snapshots: {len(forward)}')\n"
            "print(f'Matured 1d:  {forward[\"return_1d\"].notna().sum()}')\n"
            "print(f'Matured 5d:  {forward[\"return_5d\"].notna().sum()}')\n"
            "print(f'Matured 20d: {forward[\"return_20d\"].notna().sum()}')"
        ),
        _md("---\n" + DISCLAIMER),
    ])


def signal_radar() -> nbf.NotebookNode:
    return _nb(header(
        "05 · Custom signal radar",
        "Detect material changes between two YUCLAW composite signals and build "
        "a simple watchlist-style alert in pure Python."
    ) + [
        _md("## Compare two snapshots\n\n"
            "We use `client.replay` to get two point-in-time snapshots for the "
            "same ticker and compare them."),
        _code(
            "import yuclaw_py\n"
            "client = yuclaw_py.Client()\n"
            "\n"
            "earlier = client.replay('AMD', '2026-03-01')\n"
            "later   = client.replay('AMD', '2026-05-13')\n"
            "\n"
            "print(f\"AMD on 2026-03-01: {earlier['label']:<14s}  score={earlier['score']:+.3f}\")\n"
            "print(f\"AMD on 2026-05-13: {later['label']:<14s}  score={later['score']:+.3f}\")\n"
            "print(f\"Δ score: {later['score'] - earlier['score']:+.3f}\")"
        ),
        _md("## Simple alert function"),
        _code(
            "def changed(t, d1, d2, threshold=0.15):\n"
            "    a = client.replay(t, d1)\n"
            "    b = client.replay(t, d2)\n"
            "    delta = b['score'] - a['score']\n"
            "    label_flip = a['label'] != b['label']\n"
            "    return {\n"
            "        'ticker': t,\n"
            "        'flipped_label': label_flip,\n"
            "        'delta_score': round(delta, 3),\n"
            "        'material': label_flip or abs(delta) >= threshold,\n"
            "        'from': (a['label'], round(a['score'], 3)),\n"
            "        'to':   (b['label'], round(b['score'], 3)),\n"
            "    }\n"
            "\n"
            "for t in ['AMD', 'NVDA', 'INTC']:\n"
            "    r = changed(t, '2026-03-01', '2026-05-13')\n"
            "    flag = '⚠ ' if r['material'] else '  '\n"
            "    print(f\"{flag}{t}: {r['from']}  →  {r['to']}  (Δ {r['delta_score']:+.3f})\")\n"
        ),
        _md("In production this lives in `v3.radar.run` — the SDK version is for "
            "experimentation. The production radar adds: Telegram/Email/Slack "
            "adapters, an audit log, and the locked not-advice footer on every "
            "broadcast."),
        _md("---\n" + DISCLAIMER),
    ])


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    notebooks = [
        ("01_quickstart.ipynb", quickstart()),
        ("02_evidence_layer.ipynb", evidence_layer()),
        ("03_time_machine.ipynb", time_machine()),
        ("04_validation_analysis.ipynb", validation_analysis()),
        ("05_signal_radar.ipynb", signal_radar()),
    ]
    for name, nb in notebooks:
        path = OUT_DIR / name
        with path.open("w") as f:
            nbf.write(nb, f)
        print(f"wrote {path}")


if __name__ == "__main__":
    main()

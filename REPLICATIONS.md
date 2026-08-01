# Replications

External replications of YUCLAW's published statistics. The log below is
**honestly empty until someone outside the project replicates** — internal
reruns do not count and are never listed here.

## How to replicate (one command, no backend needed)

```bash
git clone https://github.com/YuClawLab/yuclaw-brain && cd yuclaw-brain
make replicate
```

or without the checkout:

```bash
pip install yuclaw && yuclaw replay-lab
```

Either path installs the published package, fetches the public replay
bundle from the live site, recomputes the published Validation Lab
statistics, and diffs them against the page values. Exit codes:
`0` reproduced · `1` mismatch · `3` bundle fetch failed (the tool prints
the URL tried and the manual-download fallback).

## How to report

Open an issue with the replication template
(`.github/ISSUE_TEMPLATE/replication.md`): your environment (OS, Python,
package version), the command run, the full output, and — for a mismatch —
the exact statistic(s) that differed. Mismatch reports are the most
valuable thing you can send; they are investigated publicly and the
resolution is linked here.

## What counts as a replication

- Run by someone with no write access to this repository or its build box.
- Uses only public artifacts (PyPI package + the live site's bundle).
- Reported with enough environment detail to be independently re-run.

## Log

| date | who | package | result | link |
|---|---|---|---|---|
| — | — | — | *no external replications yet — this row is waiting for you* | — |

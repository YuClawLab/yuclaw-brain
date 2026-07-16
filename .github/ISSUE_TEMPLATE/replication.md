---
name: Replication report
about: Report the result of independently replaying the Validation Lab (success or failure — both are wanted)
title: "Replication: <YYYY-MM-DD> — <pass|fail>"
labels: replication
---

<!-- Thank you for running an independent replication. Fill every field —
     failed replications are as valuable as successful ones and go in the
     same public log. -->

**OS:**
<!-- e.g. Ubuntu 24.04 (ARM64), macOS 15.1, Windows 11 + WSL2 -->

**Python:**
<!-- output of: python3 --version -->

**Command:**
<!-- exactly what you ran, e.g.
     yuclaw replay-lab
     or: python3 replay_lab.py lab_replay_bundle.json -->

**Bundle build metadata:**
<!-- from the downloaded lab_replay_bundle.json / packet METADATA.json:
     data_through, build date, source commit, ledger root -->

**Output hash:**
<!-- sha256 of the script's stdout, e.g.:
     yuclaw replay-lab | tee replay_out.txt ; sha256sum replay_out.txt -->

**Result:**
<!-- exit code + one of: PASS (exit 0 — statistics and ledger roots reproduced)
     or FAIL (non-zero — paste the mismatch report verbatim) -->

**Notes (optional):**

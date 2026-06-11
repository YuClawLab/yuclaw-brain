# Friday v4.2.0 Ship Checklist (DRAFT — Order B runs this, after VinZhang review gates)

**Gates before any step (ONLY VinZhang):**
- [ ] Read all 5 drafts in `drafts/v4.2/` (this dir).
- [ ] Verify the live dashboard prices/signals against an external reference (CNBC).
- [ ] Supply the authoritative **eleven-layer names + three locked values** for
      `clawfactory_announcement.md` (currently placeholdered — that draft is NOT
      shippable until filled).

**Ordered ship steps:**
1. **Pre-flight quality audit:**
   - Dashboard freshness — live page shows fresh (post-migration) signals; `price_history` current through the last close.
   - Price accuracy — spot-check a few tickers vs CNBC.
   - Version consistency — landing badge v4.0.1; release tag v4.2.0; README install = `pip install yuclaw`.
   - Repo cleanliness — only intended files committed; no stray source changes.
2. **Merge `v4.2-validation-lab` → main** (the Lab engine, renderer, page, methodology).
3. **Re-render the Lab fresh** on main against the current DB (forward panel + early-forward caveat intact).
4. **Deploy + link** the Lab from the landing nav (this is the first public exposure of `validation_lab.html`).
5. **Tag `v4.2.0`** on main.
6. **GitHub release** using `release_notes.md`.
7. **PyPI decision: NO bump.** The SDK was not changed this cycle; do not re-upload. *(Flagged post-flight cleanup: `sdk/pyproject.toml` is still named `yuclaw-evidence` while the canonical install is `yuclaw` — reconcile in a later, deliberate SDK release.)*
8. **X** — post `x_thread.md` (2 tweets).
9. **Telegram** — send `telegram_v4.2_launch.txt`.
10. **EOD verify** — live Lab page loads + compliance intact, landing nav link works, release + tag visible, no cron breakage (health_monitor prices:OK).

**Rollback:** the v4.1/migration commits are revertible (`git revert`), and pre-reconcile tags + the bare-metal backup remain armed.

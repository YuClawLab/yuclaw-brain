# Share-this-Signal (v4 Day 7)

`yuclaw share TICKER` generates a **single self-contained HTML card** — a beautiful,
point-in-time-frozen snapshot of a research signal that anyone can independently
verify. No server, no tracking, no external assets: one file you host wherever you like.

```bash
yuclaw share AMD --as-of 2026-05-20
# Card saved to ./share-AMD-2026-05-20.html
# Upload to GitHub Pages, share on X/Reddit, or open locally — anyone can re-verify
# the signal at the embedded ledger URL.
```

## What's on the card
- **Ticker, signal label, evidence grade** (semantic, muted colors — research, not alarmist).
- **Top 3 source events** — each with its SEC accession number and a link to the filing.
- **Verified Research Ledger hash** (SHA-256) shown prominently, abbreviated with the full hash
  on hover, plus a **"Verify independently →"** link to the public git-anchored ledger entry and a
  `✓ Verified` badge with the anchoring commit.
- **as_of date + replay_id** — the card is a *frozen snapshot*: the same file opened a year later
  shows the same signal.
- **Compliance** — a persistent banner at the very top (survives a social-preview crop) and a footer.

The displayed hash is the **published content_hash** that lives in the public ledger (what
`yuclaw verify` confirms), so "Verify independently" genuinely matches what a recipient sees at
the linked entry.

## Gated by default
| | Default | Flag |
|---|---|---|
| Composite score | OFF | `--include-score` |
| Supply-chain cascade | OFF (doesn't render compactly) | `--include-cascade` |

```bash
yuclaw share AMD --as-of 2026-05-20 --include-cascade            # adds the HPE→AMD cascade
yuclaw share AMD --as-of 2026-05-20 --include-score              # adds the composite score
yuclaw share AMD --as-of 2026-05-20 --output ./docs/amd.html     # custom path
```

## Sharing / preview
The card ships **Open Graph + Twitter Card** meta tags, so pasting the hosted URL into
X / Discord / Slack / LinkedIn renders a clean preview:
- `og:title` = `YUCLAW: AMD — Watch (C)`
- `og:description` = `Evidence-first research signal. 8 source events. Verified against the public ledger.`
- `twitter:card` = `summary` (an `og:image` can be added in v4.1).

Where to host: GitHub Pages, an S3 bucket, Netlify, or just send the file — it's ~7 KB and
fully standalone (all CSS inline, no external requests).

## Point-in-time & integrity (Q3)
Every card freezes at a `replay_id` + `as_of` and stamps the published ledger hash. It is a
snapshot, not a live query. The `no_data` case produces a graceful "no signal" card (compliance
still present), never a crash.

## What this is NOT (Q5)
- **Not** a PNG (that would kill verifiability) and **not** signed JSON (that would kill readability).
- **No** server-side persistence / `/v1/share/{id}` endpoint in v4 — you host the file. Verification
  flows through the existing public `ledger_anchor_url`. (Hosted share links are v4.1.)

## Architectural invariants
Every card always carries the **compliance block** and a **ledger hash + ledger_anchor_url** — these
are never omitted. SourceLock is untouched; nothing internal-only is exposed.

# Telegram Broadcast Bot — diagnosis, restore, and v4 launch

**Bot:** `@yuclaw_signals_bot` (id 8972214524) · **Channel:** `@yuclaw_signals` ("YUCLAW Signals")
**Code:** `~/yuclaw/yuclaw/telegram/broadcast_bot.py` (on `main`) · **Env:** `~/.yuclaw_env` (chmod 600)
**Audit log:** `~/.yuclaw/telegram_broadcasts.jsonl`

---

## Diagnosis (2026-06-01)

**Symptom:** the daily 09:35-ET signal post has been silent.

**Root cause: the daily cron line was missing.** The crontab had **no** `35 7 * * 1-5
… broadcast_bot daily` entry, so the daily job simply wasn't being invoked. Last successful send was
`message_id 7` on **2026-05-20T13:35Z** (`source: daily`); nothing since.

**Everything else is healthy — NOT the cause:**
| Check | Result |
|---|---|
| `getMe` (token valid) | ✅ ok — `@yuclaw_signals_bot` |
| `getChat` (channel + bot admin) | ✅ ok — channel "YUCLAW Signals" |
| `~/.yuclaw_env` `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHANNEL` | ✅ both set, perms 600 |
| Send path (`--dry-run`) | ✅ renders + reaches API layer |
| Alerts mode (`atros_daily.sh` → `broadcast_bot alerts`) | ✅ still wired; no new alerts to relay |

(There was a transient `CONFIG_ERROR` on 2026-05-19 from env not being sourced in one invocation, but
sends recovered the same day and on 2026-05-20. The line then disappeared from cron.)

## Fix applied (2026-06-01)

Restored the daily cron line, env-sourced inline (so the prior `CONFIG_ERROR` can't recur), logging to
`/tmp/yuclaw_telegram.log`, **date-guarded to first fire Thursday 2026-06-04**:

```cron
35 7 * * 1-5 [ "$(date +\%Y\%m\%d)" -ge 20260604 ] && { set -a; . /home/zhangd2/.yuclaw_env; set +a; cd /home/zhangd2/yuclaw && /usr/bin/python3 -m yuclaw.telegram.broadcast_bot daily; } >> /tmp/yuclaw_telegram.log 2>&1
```

The date-guard means **no auto-post Tue 06-02 or Wed 06-03** (Wednesday's launch is a separate manual
send), and the daily **resumes automatically Thursday 06-04** onward. Crontab backed up to
`/tmp/crontab.backup.*` before the change.

### ✅ Daily format updated to v4 (2026-06-01, main commit `90bf0770`)
`format_daily()` in `~/yuclaw/yuclaw/telegram/broadcast_bot.py` was rewritten:
- reads **live `signal_snapshots`** from Postgres (same source as the v4 dashboard / REST API) — no
  more stale `dashboard_state.json`;
- renders only the **8 locked labels** (non-locked labels are skipped, never broadcast);
- per signal: **Evidence Quality Grade** (faithful inline replica of `grade_for`), filing count, and
  the public-ledger content hash + a verify link;
- footer `pip install yuclaw`; bottom line is the canonical `COMPLIANCE_NOTICE`.

Dry-run verified: **0 STRONG_BUY/SELL/SHORT, 0 v2.3 refs**, current date stamp, evidence + compliance
present, 957 chars (< 4096). Sample output:

```
🦞 YUCLAW Research Signals — Mon Jun 1
(data as of Sun May 31)

Top signals — research classifications, not buy/sell:
  COP   STRONG_BULLISH    ·  Insufficient  ·  0 filings  ·  ledger ef956973
  XOM   STRONG_BULLISH    ·  Insufficient  ·  0 filings  ·  ledger 2659f0ea
  …
Each signal traces to its SEC filings and is hash-anchored in the public ledger.
Verify any signal: github.com/YuClawLab/yuclaw-trust

📦 pip install yuclaw  ·  yuclaw why <TICKER>
📊 yuclawlab.github.io/yuclaw-brain

YUCLAW research output. Not investment advice. Past performance does not guarantee future results. Signal labels are research classifications, not buy/sell recommendations.
```

> Note: signals are ranked by |score| (objective, no cherry-picking). Today's highest-score names
> happen to be Evidence-grade *Insufficient* (0 filings) — that's honest: the grade transparently
> shows when a directional label is thin on evidence. Thursday's live data may differ.

## Send-capability test

`getUpdates` returned an **empty queue** — there is no private chat or test channel to safely post a
live test to, and the production channel `@yuclaw_signals` is off-limits for tests. Capability is
otherwise fully verified (getMe + getChat ok, dry-run renders, and the same token/channel sent
`message_id 7` on 2026-05-20). **No test message was sent.**

To run a real live test to a non-production target: DM `@yuclaw_signals_bot` once (creates a private
chat), or make a throwaway test channel and add the bot, then:
```bash
set -a; . ~/.yuclaw_env; set +a
curl -s "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
  -d chat_id=<YOUR_PRIVATE_CHAT_ID> --data-urlencode text="yuclaw bot test ✅"
```

## Wednesday v4 launch broadcast — MANUAL one-liner

The launch text is at [`../../drafts/v4.0.0_telegram_launch.txt`](../../drafts/v4.0.0_telegram_launch.txt)
(plain text, Telegram-ready, canonical compliance line included). To send it to `@yuclaw_signals` on
Wednesday — run this **manually** (it posts to production; nothing auto-fires it):

```bash
cd /home/zhangd2/yuclaw && set -a && . /home/zhangd2/.yuclaw_env && set +a && \
python3 -c "from yuclaw.telegram.broadcast_bot import send_telegram; from pathlib import Path; \
print(send_telegram(Path('/home/zhangd2/yuclaw-v3/drafts/v4.0.0_telegram_launch.txt').read_text().strip(), \
dry_run=False, audit_path=Path.home()/'.yuclaw'/'telegram_broadcasts.jsonl', extras={'source':'v4_launch'})[0])"
```

It reuses the bot's audit log + rate-limit + idempotency. Prints the status (`SENT` on success). To
preview first, change `dry_run=False` → `dry_run=True`.

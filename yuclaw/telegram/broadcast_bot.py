"""
YUCLAW Telegram broadcast bot.

Modes (one per cron invocation):
    daily    Daily signals digest (cron: 35 7 * * 1-5 MDT = 09:35 EDT = open+5)
    alerts   Relay new ATROS alerts since last broadcast (invoked from
             atros_daily.sh after the daemon writes output/daemon/alerts.json)
    hello    One-shot channel-test message ("🦞 hello YUCLAW signals — testing channel")

Flags:
    --dry-run        Print formatted message to stdout; do not call Telegram API.
                     Audit log not written.
    --audit-log PATH Override the audit-log path (default: ~/.yuclaw/telegram_broadcasts.jsonl)
                     Useful for isolated test runs.

Env vars (from ~/.yuclaw_env):
    TELEGRAM_BOT_TOKEN  required for non-dry-run sends
    TELEGRAM_CHANNEL    target channel id or @username

Safety:
    - Rate limit: max 5 SENT broadcasts per rolling 1-hour window.
    - Idempotency: every send is hashed (sha256, first 16 hex) and the audit log
      is checked before send; a duplicate hash returns DUPLICATE without sending.
    - parse_mode is left unset (plain text) for maximum Telegram compatibility.
    - On any send (success or failure), an entry is appended to the audit log.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import requests

import psycopg2
import psycopg2.extras


# ---------------------------------------------------------------------------
# Config (env + paths)
# ---------------------------------------------------------------------------

TELEGRAM_API = "https://api.telegram.org"
RATE_LIMIT_PER_HOUR = 5
SIGNAL_CHANGE_DELTA_FLOOR = 0.20

YUCLAW_ROOT = Path(os.environ.get("YUCLAW_HOME", "/home/zhangd2/yuclaw"))
DASHBOARD_STATE = YUCLAW_ROOT / "docs/data/dashboard_state.json"
ATROS_ALERTS    = YUCLAW_ROOT / "output/daemon/alerts.json"
MACRO_REGIME    = YUCLAW_ROOT / "output/macro_regime.json"
SECTOR_ROTATION = YUCLAW_ROOT / "output/sector_rotation.json"
EARNINGS        = YUCLAW_ROOT / "output/earnings_this_week.json"

# v4 daily reads live signals straight from Postgres (NOT the v2.3 dashboard_state.json).
DB_DSN = os.environ.get("YUCLAW_DB_DSN", "dbname=yuclaw_events")
TOP_N_DAILY = 6
LEDGER_URL = "github.com/YuClawLab/yuclaw-trust"

# Locked public vocabulary (v4). Anything outside this set is NEVER broadcast —
# no STRONG_BUY / BUY / SELL / SHORT, ever.
PUBLIC_LABELS = {
    "STRONG_BULLISH", "BULLISH", "NEUTRAL", "WATCH",
    "WEAKENING", "NEGATIVE_EVENT", "BEARISH_WATCH", "RISK_ALERT",
}

DEFAULT_AUDIT_LOG = Path.home() / ".yuclaw" / "telegram_broadcasts.jsonl"

# Canonical compliance notice — MUST stay byte-identical to
# v4/api/schema.py::COMPLIANCE_NOTICE (single source of truth, v4 Day 9/Q5).
COMPLIANCE_NOTICE = (
    "YUCLAW research output. Not investment advice. "
    "Past performance does not guarantee future results. "
    "Signal labels are research classifications, not buy/sell recommendations."
)

FOOTER_LINKS = "📊 yuclawlab.github.io/yuclaw-brain"
FOOTER_PYPI  = "📦 pip install yuclaw  ·  yuclaw why <TICKER>"
FOOTER_DISCLAIMER_FULL  = "⚠️ Research only — not financial advice. AI signals may contain errors."
FOOTER_DISCLAIMER_SHORT = "⚠️ Not financial advice. Research only."


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

def _load_audit(audit_path: Path) -> list[dict]:
    if not audit_path.exists():
        return []
    out = []
    for line in audit_path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            pass
    return out


def _append_audit(audit_path: Path, entry: dict) -> None:
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    with open(audit_path, "a") as f:
        f.write(json.dumps(entry) + "\n")
    os.chmod(audit_path, 0o600)


def _hash_payload(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _rate_limit_blocked(audit_path: Path) -> bool:
    """True if RATE_LIMIT_PER_HOUR sends already happened in last 3600 s."""
    cutoff = time.time() - 3600
    recent = [e for e in _load_audit(audit_path)
              if e.get("status") == "SENT" and e.get("epoch", 0) > cutoff]
    return len(recent) >= RATE_LIMIT_PER_HOUR


def _already_broadcast(audit_path: Path, content_hash: str) -> bool:
    return any(
        e.get("content_hash") == content_hash and e.get("status") == "SENT"
        for e in _load_audit(audit_path)
    )


_WATERMARK_STATUSES = ("SENT", "DRY_RUN", "SEED")


def _last_broadcast_alert_epoch(audit_path: Path) -> float:
    """Return the most-recent alert_epoch the bot has accounted for.

    Considers SENT (real send), DRY_RUN (dry-run advance) and SEED (one-shot
    watermark inserted to suppress backfill on first cron firing). Older
    alerts than this watermark are skipped in alerts mode.
    """
    out = 0.0
    for e in _load_audit(audit_path):
        if e.get("source") == "alert" and e.get("status") in _WATERMARK_STATUSES:
            out = max(out, float(e.get("alert_epoch", 0) or 0))
    return out


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _load(path: Path) -> Any:
    try:
        return json.load(open(path))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

# Evidence Quality Grade — faithful replica of
# v4/api/schema.py::Confidence.grade_for(). Kept inline so the broadcaster stays
# dependency-light (no pydantic/v4 import inside the cron job). If the canonical
# thresholds change, mirror them here.
def _grade_label(confidence: Optional[float], ev_count: int, strong_count: int) -> str:
    v = confidence if confidence is not None else 0.0
    if v >= 0.75 and strong_count >= 3:
        return "Grade A"
    if v >= 0.55 and ev_count >= 1:
        return "Grade B"
    if v >= 0.30:
        return "Grade C"
    return "Insufficient"


# Ranking priority — surface evidence-graded signals before ungraded ones so the
# digest leads with the best-supported research, not the highest momentum score.
_GRADE_PRIORITY = {"Grade A": 4, "Grade B": 3, "Grade C": 2, "Insufficient": 1}


def _fetch_snapshot_signals() -> list[dict[str, Any]]:
    """Freshest non-backfill snapshot per ticker straight from signal_snapshots,
    with a per-signal strong-evidence count (events with llm_confidence >= 0.7).

    This is the SAME table the v4 dashboard + REST API read — today's live data,
    not the frozen v2.3 dashboard_state.json.
    """
    q = """
        SELECT DISTINCT ON (s.ticker)
            s.ticker, s.signal_label, s.total_score, s.signal_time,
            s.composite_confidence,
            COALESCE(s.content_hash, '') AS content_hash,
            COALESCE(array_length(s.evidence_event_ids, 1), 0) AS ev_count,
            (SELECT count(*) FROM events e
               WHERE e.event_id = ANY(s.evidence_event_ids)
                 AND e.llm_confidence >= 0.7) AS strong_count
        FROM signal_snapshots s
        WHERE s.is_backfill = false
        ORDER BY s.ticker, s.signal_time DESC
    """
    out: list[dict[str, Any]] = []
    with psycopg2.connect(DB_DSN) as conn, \
         conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(q)
        for r in cur.fetchall():
            label = (r["signal_label"] or "").upper()
            if label not in PUBLIC_LABELS:
                continue  # never broadcast a non-locked label
            out.append({
                "ticker": r["ticker"],
                "label": label,
                "score": float(r["total_score"] or 0.0),
                "signal_time": r["signal_time"],
                "confidence": (float(r["composite_confidence"])
                               if r["composite_confidence"] is not None else None),
                "ev_count": int(r["ev_count"] or 0),
                "strong_count": int(r["strong_count"] or 0),
                "hash8": (r["content_hash"] or "")[:8] or "—",
            })
    return out


def format_daily() -> str:
    """Daily research-signals digest (v4 format).

    Reads live signal_snapshots and renders each with the LOCKED public label,
    Evidence Quality Grade, evidence (filing) count, and the public-ledger content
    hash. Ranked grade-first (A>B>C>Insufficient), |score| as tiebreaker, so the
    digest leads with the best-supported research. No buy/sell vocabulary — ever.
    """
    today = datetime.now().strftime("%a %b %-d")
    rows = _fetch_snapshot_signals()

    if not rows:
        body = ["  (no signals available yet)"]
        data_as_of = today
    else:
        data_as_of = max(r["signal_time"] for r in rows).strftime("%a %b %-d")
        for r in rows:
            r["grade"] = _grade_label(r["confidence"], r["ev_count"], r["strong_count"])
        # Grade-first, then |score| — evidence-graded signals surface above
        # ungraded momentum. Full universe is still covered; this only reorders.
        top = sorted(
            rows,
            key=lambda r: (_GRADE_PRIORITY.get(r["grade"], 0), abs(r["score"])),
            reverse=True,
        )[:TOP_N_DAILY]
        body = []
        for r in top:
            n = r["ev_count"]
            body.append(
                f"  {r['ticker']:<5} {r['label']:<15}"
                f"  ·  {r['grade']}"
                f"  ·  {n} filing{'' if n == 1 else 's'}"
                f"  ·  ledger {r['hash8']}"
            )

    parts = [
        f"🦞 YUCLAW Research Signals — {today}",
        f"(data as of {data_as_of})",
        "",
        "Top signals — research classifications, not buy/sell:",
        "(ranked by evidence grade, then composite strength)",
        *body,
        "",
        "Each signal traces to its SEC filings and is hash-anchored in the public ledger.",
        f"Verify any signal: {LEDGER_URL}",
        "",
        FOOTER_PYPI,
        FOOTER_LINKS,
        "",
        COMPLIANCE_NOTICE,
    ]
    return "\n".join(parts)


def format_signal_new(alert: dict) -> str:
    msg = alert.get("message", "").strip()
    return "\n".join([
        "🆕 NEW IN TOP 10",
        msg,
        "",
        FOOTER_LINKS,
        FOOTER_DISCLAIMER_SHORT,
    ])


_SIGNAL_CHANGE_RE = re.compile(
    r"(?P<ticker>\S+)\s+signal\s+\w+:\s+(?P<prior>[+-]?\d+\.\d+)\s*[→>-]+\s*(?P<current>[+-]?\d+\.\d+)"
)


def _parse_signal_change(msg: str) -> Optional[tuple[str, float, float]]:
    m = _SIGNAL_CHANGE_RE.search(msg)
    if not m:
        return None
    return m.group("ticker"), float(m.group("prior")), float(m.group("current"))


def format_signal_change(alert: dict) -> Optional[str]:
    """Returns None if |delta| <= SIGNAL_CHANGE_DELTA_FLOOR — caller skips it."""
    parsed = _parse_signal_change(alert.get("message", ""))
    if parsed is None:
        return None
    ticker, prior, current = parsed
    delta = current - prior
    if abs(delta) <= SIGNAL_CHANGE_DELTA_FLOOR:
        return None
    return "\n".join([
        "📊 SIGNAL UPDATE",
        f"{ticker}  {current:+.3f} (was {prior:+.3f}, {delta:+.3f})",
        "",
        FOOTER_LINKS,
        FOOTER_DISCLAIMER_SHORT,
    ])


_REGIME_RE = re.compile(r"Regime\s+changed:\s+(\S+)\s*[→>-]+\s*(\S+)")


def format_regime_change(alert: dict) -> str:
    msg = alert.get("message", "")
    macro = _load(MACRO_REGIME) or {}
    conf = float(macro.get("confidence", 0) or 0)
    m = _REGIME_RE.search(msg)
    if m:
        old_regime, new_regime = m.group(1), m.group(2)
        return "\n".join([
            "🔄 REGIME CHANGE",
            f"{old_regime} → {new_regime} (confidence {conf:.0%})",
            "",
            "YUCLAW will reduce position aggressiveness. Track signals carefully.",
            "",
            FOOTER_LINKS,
            FOOTER_DISCLAIMER_SHORT,
        ])
    return "\n".join([
        "🔄 REGIME CHANGE",
        msg,
        "",
        FOOTER_LINKS,
        FOOTER_DISCLAIMER_SHORT,
    ])


# ---------------------------------------------------------------------------
# Send (with rate limit + idempotency + audit)
# ---------------------------------------------------------------------------

def send_telegram(
    text: str,
    *,
    dry_run: bool,
    audit_path: Path,
    extras: Optional[dict] = None,
) -> tuple[str, Any]:
    """Send text to TELEGRAM_CHANNEL.

    Returns (status, response_or_error_string) where status is one of:
        DRY_RUN | DUPLICATE | RATE_LIMITED | CONFIG_ERROR
        SENT | FAIL_API | FAIL_EXCEPTION
    Writes an audit-log entry for every non-DRY_RUN outcome.
    """
    extras = extras or {}
    content_hash = _hash_payload(text)
    now_iso = datetime.now(timezone.utc).isoformat()
    now_epoch = time.time()

    if dry_run:
        bar = "=" * 60
        print(bar)
        print(f"[DRY RUN] target=$TELEGRAM_CHANNEL  hash={content_hash}  len={len(text)}")
        print("-" * 60)
        print(text)
        print(bar)
        # In dry-run we still write a non-SENT marker if caller asks (extras),
        # so alerts mode can advance its alert-watermark and avoid re-spamming
        # the same alert on the next dry-run too.
        if extras.get("source") == "alert":
            _append_audit(audit_path, {
                "timestamp": now_iso, "epoch": now_epoch,
                "status": "DRY_RUN", "content_hash": content_hash,
                "length": len(text), **extras,
            })
        return "DRY_RUN", None

    if _already_broadcast(audit_path, content_hash):
        entry = {
            "timestamp": now_iso, "epoch": now_epoch,
            "status": "DUPLICATE", "content_hash": content_hash,
            "length": len(text), **extras,
        }
        _append_audit(audit_path, entry)
        return "DUPLICATE", f"content_hash {content_hash} already broadcast"

    if _rate_limit_blocked(audit_path):
        entry = {
            "timestamp": now_iso, "epoch": now_epoch,
            "status": "RATE_LIMITED", "content_hash": content_hash,
            "length": len(text), **extras,
        }
        _append_audit(audit_path, entry)
        return "RATE_LIMITED", f">= {RATE_LIMIT_PER_HOUR} sent in last hour"

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    channel = os.environ.get("TELEGRAM_CHANNEL", "")
    if not token or not channel:
        entry = {
            "timestamp": now_iso, "epoch": now_epoch,
            "status": "CONFIG_ERROR", "content_hash": content_hash,
            "length": len(text), **extras,
            "error": "TELEGRAM_BOT_TOKEN or TELEGRAM_CHANNEL not set",
        }
        _append_audit(audit_path, entry)
        return "CONFIG_ERROR", "TELEGRAM_BOT_TOKEN or TELEGRAM_CHANNEL not set"

    url = f"{TELEGRAM_API}/bot{token}/sendMessage"
    try:
        resp = requests.post(
            url,
            json={
                "chat_id": channel,
                "text": text,
                "disable_web_page_preview": True,
            },
            timeout=30,
        )
    except Exception as e:
        entry = {
            "timestamp": now_iso, "epoch": now_epoch,
            "status": "FAIL_EXCEPTION", "content_hash": content_hash,
            "length": len(text), **extras, "error": str(e)[:200],
        }
        _append_audit(audit_path, entry)
        return "FAIL_EXCEPTION", str(e)

    if resp.status_code == 200 and resp.json().get("ok"):
        result = resp.json().get("result", {})
        entry = {
            "timestamp": now_iso, "epoch": now_epoch,
            "status": "SENT", "content_hash": content_hash,
            "length": len(text), **extras,
            "message_id": result.get("message_id"),
        }
        _append_audit(audit_path, entry)
        return "SENT", result

    entry = {
        "timestamp": now_iso, "epoch": now_epoch,
        "status": "FAIL_API", "content_hash": content_hash,
        "length": len(text), **extras,
        "error": f"HTTP {resp.status_code}: {resp.text[:200]}",
    }
    _append_audit(audit_path, entry)
    return "FAIL_API", resp.text


# ---------------------------------------------------------------------------
# Modes
# ---------------------------------------------------------------------------

def run_daily(dry_run: bool, audit_path: Path) -> str:
    text = format_daily()
    status, _ = send_telegram(text, dry_run=dry_run, audit_path=audit_path,
                              extras={"source": "daily"})
    return status


def run_alerts(dry_run: bool, audit_path: Path) -> list[tuple[str, str, str]]:
    """Relay new ATROS alerts. Returns list of (alert_type, ticker_or_msg, status)."""
    alerts = _load(ATROS_ALERTS) or []
    if not isinstance(alerts, list):
        return []
    watermark = _last_broadcast_alert_epoch(audit_path)
    results: list[tuple[str, str, str]] = []
    for alert in alerts:
        ts_str = alert.get("timestamp", "")
        try:
            alert_epoch = datetime.fromisoformat(ts_str).timestamp()
        except Exception:
            continue
        if alert_epoch <= watermark:
            continue

        atype = alert.get("type", "")
        text: Optional[str] = None
        if atype == "SIGNAL_NEW":
            text = format_signal_new(alert)
        elif atype == "SIGNAL_CHANGE":
            text = format_signal_change(alert)  # may return None on small delta
        elif atype == "REGIME_CHANGE":
            text = format_regime_change(alert)
        # TRACK_UPDATE and anything else: deliberately skipped.

        label = alert.get("message", "")[:40]
        if text is None:
            results.append((atype, label, "FILTERED"))
            continue

        status, _ = send_telegram(
            text, dry_run=dry_run, audit_path=audit_path,
            extras={"source": "alert", "alert_type": atype, "alert_epoch": alert_epoch},
        )
        results.append((atype, label, status))
    return results


HELLO_MESSAGE = (
    "🦞 YUCLAW Signals — channel test\n"
    "\n"
    "This channel broadcasts evidence-first research classifications daily at "
    "09:35 ET on weekdays (market open + 5 min).\n"
    "\n"
    "Subscribers will also receive alerts when:\n"
    "- New tickers enter the top 10\n"
    "- Score changes >0.20 (significant moves only)\n"
    "- Market regime shifts (RISK_ON ↔ CRISIS)\n"
    "\n"
    "📊 yuclawlab.github.io/yuclaw-brain\n"
    "📦 pip install yuclaw\n"
    "\n"
    "⚠️ Research and education only. Not financial advice. AI-generated signals "
    "may contain errors. Past performance does not predict future returns."
)


def run_hello(dry_run: bool, audit_path: Path) -> str:
    status, _ = send_telegram(HELLO_MESSAGE, dry_run=dry_run, audit_path=audit_path,
                              extras={"source": "hello"})
    return status


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="YUCLAW Telegram broadcast bot")
    parser.add_argument("mode", choices=["daily", "alerts", "hello"])
    parser.add_argument("--dry-run", action="store_true",
                        help="Print formatted message to stdout; do not call Telegram API.")
    parser.add_argument("--audit-log", type=Path, default=DEFAULT_AUDIT_LOG,
                        help=f"Audit log path (default: {DEFAULT_AUDIT_LOG})")
    args = parser.parse_args(argv)

    if args.mode == "daily":
        status = run_daily(args.dry_run, args.audit_log)
        print(f"[daily] status={status}")
        return 0 if status in ("SENT", "DRY_RUN") else 1

    if args.mode == "alerts":
        results = run_alerts(args.dry_run, args.audit_log)
        if not results:
            print("[alerts] no new alerts to relay")
            return 0
        for atype, label, status in results:
            print(f"[alerts] {atype:14} {status:14} {label}")
        return 0

    # hello
    status = run_hello(args.dry_run, args.audit_log)
    print(f"[hello] status={status}")
    return 0 if status in ("SENT", "DRY_RUN") else 1


if __name__ == "__main__":
    sys.exit(main())

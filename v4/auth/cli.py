"""CLI: python3 -m v3.cli keys {create|list|revoke|usage}

  yuclaw keys create [--owner-email EMAIL] [--notes TEXT]   # prints the secret ONCE
  yuclaw keys list                                          # never shows secrets
  yuclaw keys revoke KEY_ID
  yuclaw keys usage KEY_ID [--days N]
"""
from __future__ import annotations

import argparse
import sys

from v4.auth import keys as K


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="yuclaw keys", description="API key management.")
    sub = p.add_subparsers(dest="action", required=True)
    c = sub.add_parser("create", help="create a key (secret shown once)")
    c.add_argument("--owner-email")
    c.add_argument("--notes")
    sub.add_parser("list", help="list keys (no secrets)")
    r = sub.add_parser("revoke", help="revoke a key")
    r.add_argument("key_id")
    u = sub.add_parser("usage", help="daily request counts for a key")
    u.add_argument("key_id")
    u.add_argument("--days", type=int, default=7)
    a = p.parse_args(argv)

    if a.action == "create":
        key_id, secret = K.create_api_key(owner_email=a.owner_email, notes=a.notes)
        print("API key created.")
        print(f"  key_id : {key_id}")
        print(f"  secret : {secret}")
        print("  ⚠  This secret is shown ONCE and is NOT recoverable — store it now.")
        print(f"  Use it as:  Authorization: Bearer {secret}")
    elif a.action == "list":
        rows = K.list_keys()
        if not rows:
            print("(no keys)")
        for k in rows:
            print(f"  {k.key_id}  {(k.owner_email or '-'):<28} "
                  f"created {k.created_at.date()}  {'active' if k.is_active else 'REVOKED'}")
    elif a.action == "revoke":
        ok = K.revoke_api_key(a.key_id)
        print(f"revoked {a.key_id}" if ok else f"no such key: {a.key_id}", file=None if ok else sys.stderr)
        return 0 if ok else 1
    elif a.action == "usage":
        u = K.usage(a.key_id, days=a.days)
        print(f"  {a.key_id}: {u['daily_today']}/{u['daily_limit']} requests today (UTC)")
        for day, n in u["by_day"].items():
            print(f"    {day}: {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Exact monetary arithmetic for the commitment workbench.

Amounts are decimal strings or integers in the claim's stated `unit` (for money, the ISO-4217 currency's major
unit). Floats are refused everywhere: a JSON number with a fractional part must be given as a string. All
arithmetic is `decimal.Decimal` with an explicit context that traps inexact results, so a midpoint or delta is
either exact or an error — never a rounded surprise.
"""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation, localcontext, Inexact, Rounded

from v3.receipts.contracts import ContractError

_AMOUNT = re.compile(r"^-?(0|[1-9][0-9]*)(\.[0-9]{1,12})?$")
_GROUPED = re.compile(r"^-?[1-9][0-9]{0,2}(,[0-9]{3})+(\.[0-9]{1,12})?$")
SCALES = ("units", "thousands", "millions", "billions")
SCALE_FACTOR = {"units": Decimal(1), "thousands": Decimal(1000), "millions": Decimal(1_000_000), "billions": Decimal(1_000_000_000)}
_CURRENCY = re.compile(r"^[A-Z]{3}$")
MAX_DIGITS = 34


def parse_amount(v, field: str = "amount") -> Decimal:
    """int or canonical decimal string → Decimal. bool/float/NaN/exponent forms are contract errors."""
    if isinstance(v, bool):
        raise ContractError(f"{field}: boolean is not an amount")
    if isinstance(v, int):
        return Decimal(v)
    if isinstance(v, float):
        raise ContractError(f"{field}: floating point is not accepted; give an integer or a decimal string")
    if isinstance(v, Decimal):
        s = format(v, "f")
    elif isinstance(v, str):
        s = v.strip()
        if "," in s:
            if not _GROUPED.match(s):
                raise ContractError(f"{field}: {s!r} uses separators that are not thousands groups")
            s = s.replace(",", "")
    else:
        raise ContractError(f"{field}: amount must be an integer or a decimal string")
    if not _AMOUNT.match(s):
        raise ContractError(f"{field}: {s!r} is not a canonical decimal (digits, optional '.', up to 12 fraction digits)")
    if len(s.replace("-", "").replace(".", "")) > MAX_DIGITS:
        raise ContractError(f"{field}: more than {MAX_DIGITS} significant digits")
    try:
        return Decimal(s)
    except InvalidOperation as exc:                       # pragma: no cover — the regex prevents this
        raise ContractError(f"{field}: unparseable amount") from exc


def to_json(d: Decimal):
    """Canonical JSON form: an int when integral, else a plain decimal string (never exponent notation)."""
    d = d.normalize() if d != 0 else Decimal(0)
    if d == d.to_integral_value():
        return int(d)
    return format(d, "f")


def exact(op):
    """Run `op()` in a context that refuses any inexact or rounded result."""
    with localcontext() as ctx:
        ctx.prec = MAX_DIGITS + 4
        ctx.traps[Inexact] = True
        ctx.traps[Rounded] = True
        try:
            return op()
        except (Inexact, Rounded) as exc:
            raise ContractError("inexact monetary arithmetic refused") from exc


def midpoint(low: Decimal, high: Decimal) -> Decimal:
    return exact(lambda: (low + high) / Decimal(2))


def width(low: Decimal, high: Decimal) -> Decimal:
    return exact(lambda: high - low)


def delta(a: Decimal, b: Decimal) -> Decimal:
    """a - b, exact."""
    return exact(lambda: a - b)


def contains(low: Decimal, high: Decimal, x: Decimal) -> bool:
    return low <= x <= high


def distance_outside(low: Decimal, high: Decimal, x: Decimal) -> Decimal:
    """0 when inside; signed distance to the violated bound otherwise (negative below low, positive above high)."""
    if x < low:
        return exact(lambda: x - low)
    if x > high:
        return exact(lambda: x - high)
    return Decimal(0)


def validate_currency(c, field: str = "currency") -> str:
    if not isinstance(c, str) or not _CURRENCY.match(c):
        raise ContractError(f"{field}: ISO-4217 three-letter uppercase code required (got {c!r})")
    return c


def validate_scale(s, field: str = "scale_as_stated") -> str:
    if s not in SCALES:
        raise ContractError(f"{field}: one of {list(SCALES)} required (got {s!r})")
    return s


def as_stated(value: Decimal, scale: str) -> str:
    """Human rendering in the stated scale (exact division; refuses inexact)."""
    q = exact(lambda: value / SCALE_FACTOR[scale])
    return f"{format(q.normalize(), 'f')} {scale}" if scale != "units" else format(q.normalize(), "f")

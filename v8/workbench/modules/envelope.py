"""Typed, versioned signing envelopes with domain separation (Ed25519 through the maintained `cryptography` package).

    signing input = b"YUCLAW-SIGNED-RECORD/1" 0x00 <record type, ASCII> 0x00 <canonical JSON of the body>

The record type is INSIDE the signed bytes, and verification demands the type the caller expects: an approval signature
can never be replayed as an evaluation or a checkpoint. Unknown envelope versions and unknown record types are refused.
The body is canonical JSON of integers, strings, booleans, nulls, lists and objects only (no floats; the strict parser
refuses duplicate keys before a body ever gets here), so one body has exactly one byte encoding.

Two separate answers, never merged: INTEGRITY (do these bytes verify under the key the envelope names?) and TRUST (is
that key a root THIS receiver's administrator enrolled, and not revoked?). An envelope can carry its own public key so
that integrity is checkable anywhere; carrying a key never makes it trusted — there is no trust on first use.
No algorithm here is custom: Ed25519 sign/verify only."""
from __future__ import annotations

import base64
import hashlib

from v3.receipts.contracts import canonical_json
from v8.workbench.modules.core import ModuleError

ENVELOPE = "yuclaw.signed-record/1"
DOMAIN = b"YUCLAW-SIGNED-RECORD/1"
RECORD_TYPES = ("shd.approval", "shd.evaluation", "prc.checkpoint", "module.export")


def available() -> bool:
    try:
        import cryptography.hazmat.primitives.asymmetric.ed25519  # noqa: F401
        return True
    except Exception:
        return False


def _need():
    if not available():
        raise ModuleError("E_SIGNATURES_UNAVAILABLE", "the `cryptography` package is not installed in this environment, so signed records cannot be made or checked here (install yuclaw with its declared dependencies)")


def _check_body(v, depth=0):
    if depth > 16:
        raise ModuleError("E_ENVELOPE", "body nested too deeply")
    if isinstance(v, bool) or v is None or isinstance(v, str):
        return
    if isinstance(v, int):
        if abs(v) >= 10 ** 16:
            raise ModuleError("E_ENVELOPE", "integer out of range")
        return
    if isinstance(v, list):
        for x in v:
            _check_body(x, depth + 1)
        return
    if isinstance(v, dict):
        for k, x in v.items():
            if not isinstance(k, str):
                raise ModuleError("E_ENVELOPE", "object keys must be strings")
            _check_body(x, depth + 1)
        return
    raise ModuleError("E_ENVELOPE", f"value of type {type(v).__name__} has no canonical encoding here (floats are refused)")


def signing_input(record_type: str, body: dict) -> bytes:
    if record_type not in RECORD_TYPES:
        raise ModuleError("E_RECORD_TYPE", f"unknown record type {record_type!r}")
    if not isinstance(body, dict):
        raise ModuleError("E_ENVELOPE", "the signed body is an object")
    _check_body(body)
    return DOMAIN + b"\x00" + record_type.encode("ascii") + b"\x00" + canonical_json(body)


def key_id(public_raw: bytes) -> str:
    return hashlib.sha256(b"YUCLAW-ED25519-KEY/1\x00" + public_raw).hexdigest()[:32]


def generate() -> tuple[bytes, str, str]:
    """(private key PEM, public key base64, key id). The PEM is for a private 0600 file; it is never exported or packaged."""
    _need()
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    sk = Ed25519PrivateKey.generate()
    pem = sk.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    raw = sk.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return pem, base64.b64encode(raw).decode("ascii"), key_id(raw)


def sign(record_type: str, body: dict, private_pem: bytes) -> dict:
    _need()
    from cryptography.hazmat.primitives import serialization
    sk = serialization.load_pem_private_key(private_pem, password=None)
    raw = sk.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    sig = sk.sign(signing_input(record_type, body))
    return {"envelope": ENVELOPE, "record_type": record_type, "body": body,
            "signer": {"algorithm": "Ed25519", "key_id": key_id(raw), "public_key": base64.b64encode(raw).decode("ascii")}, "signature": base64.b64encode(sig).decode("ascii")}


def verify(env, expected_type: str, trusted: dict | None = None) -> dict:
    """{'integrity': VALID|INVALID|UNVERIFIABLE, 'trust': TRUSTED|UNKNOWN_SIGNER|REVOKED_ROOT|NOT_EVALUATED, 'key_id', 'reason'}.
    `trusted` is the RECEIVER's own registry: {key_id: {'public_key': b64, 'revoked': bool}}. A key found only inside the
    envelope is never trusted. When a trusted root exists for the key id, ITS public key is the one used."""
    out = {"integrity": "INVALID", "trust": "NOT_EVALUATED", "key_id": None, "reason": None}
    try:
        if not isinstance(env, dict) or env.get("envelope") != ENVELOPE:
            out["reason"] = "unknown or missing envelope version"; return out
        if env.get("record_type") != expected_type or expected_type not in RECORD_TYPES:
            out["reason"] = f"record type {env.get('record_type')!r} is not the expected {expected_type!r} (a signature is valid for one record type only)"; return out
        signer = env.get("signer") or {}
        if signer.get("algorithm") != "Ed25519" or not isinstance(signer.get("public_key"), str) or not isinstance(env.get("signature"), str):
            out["reason"] = "signer block malformed"; return out
        raw = base64.b64decode(signer["public_key"], validate=True); sig = base64.b64decode(env["signature"], validate=True)
        if len(raw) != 32 or len(sig) != 64 or key_id(raw) != signer.get("key_id"):
            out["reason"] = "key or signature length wrong, or the key id does not belong to the key"; return out
        out["key_id"] = signer["key_id"]
        message = signing_input(expected_type, env.get("body"))
    except (ModuleError, ValueError, TypeError) as exc:
        out["reason"] = f"malformed envelope: {exc}"; return out
    root = (trusted or {}).get(out["key_id"])
    if root is not None:
        try:
            raw = base64.b64decode(root["public_key"], validate=True)
        except (ValueError, TypeError):
            out["reason"] = "the enrolled root is unreadable"; return out
    if not available():
        out["integrity"] = "UNVERIFIABLE"; out["reason"] = "the `cryptography` package is not installed here"; return out
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    try:
        Ed25519PublicKey.from_public_bytes(raw).verify(sig, message)
    except (InvalidSignature, ValueError):
        out["reason"] = "the signature does not verify for this record type and body"; return out
    out["integrity"] = "VALID"
    if trusted is not None:
        out["trust"] = "UNKNOWN_SIGNER" if root is None else ("REVOKED_ROOT" if root.get("revoked") else "TRUSTED")
    return out

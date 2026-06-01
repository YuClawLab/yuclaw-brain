"""
Compliance regression guard (v4 Day 9).

Asserts the load-bearing invariant: the compliance block is present on EVERY
signal-data response — success, no_data, 401 (invalid key), and 429 (over quota) —
and ABSENT on pure metadata/account responses. Future endpoints cannot silently
drop it without failing this test.

Run:  python3 -m pytest tests/test_compliance_regression.py -v
Uses FastAPI's in-process TestClient (no live server needed). Touches the DB for
api_keys / request_logs; all test rows are cleaned up.
"""
import psycopg2
import pytest
from fastapi.testclient import TestClient

from v3.api.server import app
from v4.auth import keys as K

DSN = "dbname=yuclaw_events"
VALID_TICKER = "AMD"
NODATA_TICKER = "ZZZZ"
AS_OF = "2026-05-20"

# (method path, query) for each class of endpoint.
SIGNAL_ENDPOINTS = [
    f"/v1/why/{VALID_TICKER}?as_of={AS_OF}",
    f"/v1/signal/{VALID_TICKER}",
    f"/v1/memo/{VALID_TICKER}?as_of={AS_OF}",
    f"/v1/cascade/{VALID_TICKER}?as_of={AS_OF}",
    f"/v1/verify/{VALID_TICKER}?date={AS_OF}",
]
SIGNAL_ENDPOINTS_NODATA = [
    f"/v1/why/{NODATA_TICKER}",
    f"/v1/signal/{NODATA_TICKER}",
    f"/v1/memo/{NODATA_TICKER}",
    f"/v1/cascade/{NODATA_TICKER}",
    f"/v1/verify/{NODATA_TICKER}?date={AS_OF}",
]
METADATA_ENDPOINTS = ["/health", "/v1/universe", "/v1/openapi.json"]
ACCOUNT_ENDPOINTS = ["/v1/keys/info", "/v1/keys/usage"]

client = TestClient(app)


def _has_compliance(body: dict) -> bool:
    if not isinstance(body, dict):
        return False
    if "compliance" in body:
        return True
    resp = body.get("response")
    return isinstance(resp, dict) and "compliance" in resp


@pytest.fixture(scope="module")
def test_key():
    key_id, secret = K.create_api_key(owner_email="regression@test", notes="compliance-regression")
    yield key_id, secret
    with psycopg2.connect(DSN) as c, c.cursor() as cur:
        cur.execute("DELETE FROM request_logs WHERE key_id = %s", (key_id,))
        cur.execute("DELETE FROM api_keys WHERE notes = 'compliance-regression'")
        c.commit()


def _auth(secret):
    return {"Authorization": f"Bearer {secret}"}


# --- signal endpoints: compliance ALWAYS present ---
@pytest.mark.parametrize("path", SIGNAL_ENDPOINTS)
def test_signal_ok_has_compliance(path, test_key):
    _, secret = test_key
    r = client.get(path, headers=_auth(secret))
    assert r.status_code == 200, (path, r.status_code, r.text[:200])
    assert _has_compliance(r.json()), f"{path}: compliance MISSING on ok response"


@pytest.mark.parametrize("path", SIGNAL_ENDPOINTS_NODATA)
def test_signal_no_data_has_compliance(path, test_key):
    _, secret = test_key
    r = client.get(path, headers=_auth(secret))
    assert r.status_code == 200, (path, r.status_code)
    assert _has_compliance(r.json()), f"{path}: compliance MISSING on no_data response"


@pytest.mark.parametrize("path", SIGNAL_ENDPOINTS)
def test_signal_invalid_key_401_has_compliance(path):
    r = client.get(path, headers=_auth("yks_invalid_bogus_key"))
    assert r.status_code == 401, (path, r.status_code)
    assert _has_compliance(r.json()), f"{path}: compliance MISSING on 401"


def test_signal_over_quota_429_has_compliance():
    # Dedicated key pre-seeded to the daily limit, then one more request → 429.
    key_id, secret = K.create_api_key(notes="compliance-regression-429")
    try:
        with psycopg2.connect(DSN) as c, c.cursor() as cur:
            cur.executemany(
                "INSERT INTO request_logs (key_id, endpoint, ticker, status_code) VALUES (%s,%s,%s,%s)",
                [(key_id, "/v1/why/AMD", "AMD", 200)] * K.FREE_TIER_DAILY,
            )
            c.commit()
        r = client.get(f"/v1/why/{VALID_TICKER}", headers=_auth(secret))
        assert r.status_code == 429, (r.status_code, r.text[:200])
        j = r.json()
        assert j.get("status") == "rate_limited"
        assert j.get("retry_after") is not None
        assert _has_compliance(j), "compliance MISSING on 429 rate_limited envelope"
    finally:
        with psycopg2.connect(DSN) as c, c.cursor() as cur:
            cur.execute("DELETE FROM request_logs WHERE key_id = %s", (key_id,))
            cur.execute("DELETE FROM api_keys WHERE notes = 'compliance-regression-429'")
            c.commit()


# --- metadata + account endpoints: compliance ABSENT ---
@pytest.mark.parametrize("path", METADATA_ENDPOINTS)
def test_metadata_has_no_compliance(path):
    r = client.get(path)
    assert r.status_code == 200, (path, r.status_code)
    assert not _has_compliance(r.json()), f"{path}: metadata must NOT carry compliance"


@pytest.mark.parametrize("path", ACCOUNT_ENDPOINTS)
def test_account_has_no_compliance(path, test_key):
    _, secret = test_key
    r = client.get(path, headers=_auth(secret))
    assert r.status_code == 200, (path, r.status_code)
    assert not _has_compliance(r.json()), f"{path}: account op must NOT carry compliance"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))

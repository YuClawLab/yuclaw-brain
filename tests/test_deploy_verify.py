"""Deploy-verify contract tests (V8-001 §3): the live-site verifier accepts a served body ONLY when it
reproduces the frozen expected artifact identity (exact sha256 AND byte length) at a 200 on the canonical
origin with no redirect hop, and refuses everything else — including genuine-looking bodies of the wrong
bytes, error pages, wrong origins and redirect chains. A generic minimum body size must not reject a valid
short artifact (the 730-byte v7 release target manifest is the motivating case).

All HTTP is mocked at the opener layer: no network. Run: python3 -m pytest tests/test_deploy_verify.py -q
"""
from __future__ import annotations

import email.message
import hashlib
import importlib.util
import io
import json
import pathlib
import sys
import tempfile
import unittest
import urllib.error

REPO = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("deploy_verify_under_test", REPO / "tools" / "deploy_verify.py")
dv = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = dv                     # dataclasses resolve annotations through sys.modules
SPEC.loader.exec_module(dv)

CANON = "https://yuclaw.ca"
GITHUB = "https://yuclawlab.github.io/yuclaw-brain"


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def short_manifest(n_bytes: int = 730) -> bytes:
    """A valid, clearly fictional release-target manifest padded to exactly n_bytes (JSON stays valid)."""
    base = {
        "schema": "yuclaw-release-target/1",
        "version": "0.0.0-fixture",
        "source_sha": "0" * 40,
        "source_tree": "1" * 40,
        "wheel_sha256": "2" * 64,
        "sdist_sha256": "3" * 64,
        "generated_at": "2026-01-01T00:00:00Z",
        "note": "",
    }
    body = json.dumps(base, indent=1).encode()
    pad = n_bytes - len(body)
    assert pad >= 0, "fixture too small for padding"
    base["note"] = "x" * pad
    body = json.dumps(base, indent=1).encode()
    assert len(body) == n_bytes, (len(body), n_bytes)
    json.loads(body)
    return body


class _Resp:
    def __init__(self, url: str, status: int, body: bytes, headers: dict | None = None):
        self._url, self.status, self._body = url, status, body
        self.headers = email.message.Message()
        for k, v in (headers or {}).items():
            self.headers[k] = v

    def read(self) -> bytes:
        return self._body

    def geturl(self) -> str:
        return self._url

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class FakeWeb:
    """Deterministic opener: url -> ('ok', status, body, headers) | ('redirect', code, location) | ('error', code, body)."""

    def __init__(self):
        self.routes: dict[str, tuple] = {}
        self.calls: list[str] = []

    def ok(self, url, body, status=200, headers=None):
        self.routes[url] = ("ok", status, body, headers or {})

    def redirect(self, url, code, location):
        self.routes[url] = ("redirect", code, location)

    def error(self, url, code, body=b"<html><title>404</title></html>"):
        self.routes[url] = ("error", code, body)

    def open(self, req, timeout=None):
        url = req.full_url
        self.calls.append(url)
        kind, *rest = self.routes.get(url, ("error", 404, b"not routed"))
        if kind == "ok":
            status, body, headers = rest
            return _Resp(url, status, body, headers)
        hdrs = email.message.Message()
        if kind == "redirect":
            code, loc = rest
            if loc is not None:
                hdrs["Location"] = loc
            raise urllib.error.HTTPError(url, code, "redirect", hdrs, io.BytesIO(b"<html>301 Moved</html>"))
        code, body = rest
        raise urllib.error.HTTPError(url, code, "error", hdrs, io.BytesIO(body))


class _Base(unittest.TestCase):
    def setUp(self):
        self.web = FakeWeb()
        self._opener = dv._OPENER
        dv._OPENER = self.web
        self.tmp = tempfile.TemporaryDirectory(prefix="dv-docs-")
        self.root = pathlib.Path(self.tmp.name)
        (self.root / "docs").mkdir()
        self._repo = dv._REPO
        dv._REPO = self.root
        self._sleep, self._poll = dv.time.sleep, dv.POLL_SECONDS
        dv.time.sleep = lambda s: None
        dv.POLL_SECONDS = 0

    def tearDown(self):
        dv._OPENER = self._opener
        dv._REPO = self._repo
        dv.time.sleep, dv.POLL_SECONDS = self._sleep, self._poll
        self.tmp.cleanup()

    def local(self, rel: str, body: bytes) -> str:
        p = self.root / "docs" / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(body)
        return sha(body)

    def run_main(self, *paths: str) -> int:
        return dv.main(["--timeout", "0", "--paths", *paths])


class TestShortArtifactRegression(_Base):
    """The behaviour that the 1,024-byte floor got wrong. These run unchanged before and after the fix."""

    def test_valid_730_byte_manifest_on_canonical_origin_is_live(self):
        body = short_manifest(730)
        self.local("packets/manifest.json", body)
        self.web.ok(f"{CANON}/packets/manifest.json", body, headers={"Content-Type": "application/json"})
        self.assertEqual(self.run_main("packets/manifest.json"), 0)

    def test_boundary_1023_and_1024_byte_artifacts_are_both_live(self):
        for n in (1023, 1024):
            body = short_manifest(n)
            self.local(f"b{n}.json", body)
            self.web.ok(f"{CANON}/b{n}.json", body)
        self.assertEqual(self.run_main("b1023.json", "b1024.json"), 0)

    def test_short_valid_text_artifact_is_live(self):
        body = b"# usage\n\nyuclaw --help\n"
        self.local("usage.md", body)
        self.web.ok(f"{CANON}/usage.md", body)
        self.assertEqual(self.run_main("usage.md"), 0)

    def test_normal_large_artifact_is_live(self):
        body = b"<!doctype html><html><body>" + b"x" * 5000 + b"</body></html>"
        self.local("index.html", body)
        self.web.ok(f"{CANON}/index.html", body)
        self.assertEqual(self.run_main("index.html"), 0)


class TestRefusals(_Base):
    """Nothing but the frozen identity at a clean 200 on the canonical origin may verify."""

    def test_wrong_bytes_same_length_refused(self):
        body = short_manifest(730)
        self.local("packets/manifest.json", body)
        wrong = body[:-2] + b"y}"                      # same length, different content
        assert len(wrong) == len(body)
        self.web.ok(f"{CANON}/packets/manifest.json", wrong, headers={"Content-Type": "application/json"})
        self.assertEqual(self.run_main("packets/manifest.json"), 1)

    def test_truncated_bytes_refused(self):
        body = short_manifest(1500)
        self.local("a.json", body)
        self.web.ok(f"{CANON}/a.json", body[:1100])
        self.assertEqual(self.run_main("a.json"), 1)

    def test_html_error_page_served_as_200_refused(self):
        body = short_manifest(730)
        self.local("packets/manifest.json", body)
        err_page = (b"<!doctype html><html><head><title>Site not found - GitHub Pages</title></head><body>" + b" " * 900 + b"</body></html>")
        self.web.ok(f"{CANON}/packets/manifest.json", err_page, headers={"Content-Type": "text/html"})
        self.assertEqual(self.run_main("packets/manifest.json"), 1)

    def test_mime_header_alone_does_not_verify(self):
        body = short_manifest(730)
        self.local("packets/manifest.json", body)
        self.web.ok(f"{CANON}/packets/manifest.json", b"{}", headers={"Content-Type": "application/json"})
        self.assertEqual(self.run_main("packets/manifest.json"), 1)

    def test_wrong_final_origin_refused(self):
        body = short_manifest(730)
        self.local("packets/manifest.json", body)
        # canonical URL answers with a clean redirect-free 200 whose reported final URL is another origin
        self.web.routes[f"{CANON}/packets/manifest.json"] = ("ok", 200, body, {})
        real_open = self.web.open

        def open_other_origin(req, timeout=None):
            r = real_open(req, timeout)
            r._url = f"{GITHUB}/packets/manifest.json"
            return r
        self.web.open = open_other_origin
        self.assertEqual(self.run_main("packets/manifest.json"), 1)

    def test_redirect_to_200_with_correct_bytes_refused(self):
        body = short_manifest(730)
        self.local("packets/manifest.json", body)
        self.web.redirect(f"{CANON}/packets/manifest.json", 301, f"{CANON}/moved/manifest.json")
        self.web.ok(f"{CANON}/moved/manifest.json", body)
        self.assertEqual(self.run_main("packets/manifest.json"), 1)

    def test_redirect_not_followed_and_without_location_refused(self):
        self.web.redirect(f"{CANON}/x.json", 302, f"{CANON}/y.json")
        b, err = dv._probe(f"{CANON}/x.json", follow=False)
        self.assertIsNone(b); self.assertIn("redirect", err)
        self.web.redirect(f"{CANON}/z.json", 302, None)
        b, err = dv._probe(f"{CANON}/z.json")
        self.assertIsNone(b); self.assertIn("without Location", err)

    def test_non_200_statuses_refused(self):
        body = short_manifest(730)
        self.local("packets/manifest.json", body)
        for code in (404, 500, 503):
            self.web.error(f"{CANON}/packets/manifest.json", code, body)   # even when the error body carries the right bytes
            self.assertEqual(self.run_main("packets/manifest.json"), 1, code)

    def test_missing_local_artifact_rejected_before_any_probe(self):
        self.assertEqual(self.run_main("nonexistent.json"), 1)
        self.assertEqual(self.web.calls, [])


class TestManifestContract(_Base):
    """New contract surface (V8-001): expected identity carries sha256 + length; unknown/invalid paths are rejected."""

    def test_expected_identity_carries_sha256_and_length(self):
        body = short_manifest(730)
        self.local("packets/manifest.json", body)
        exp, missing = dv.expected_from_local(["packets/manifest.json"])
        self.assertEqual(missing, [])
        e = exp["packets/manifest.json"]
        self.assertEqual((e.sha256, e.length), (sha(body), 730))

    def test_probe_with_expected_refuses_identity_mismatch_and_reports_both_sides(self):
        body = short_manifest(730)
        e = dv.Expected(rel="packets/manifest.json", sha256=sha(body), length=730)
        self.web.ok(f"{CANON}/packets/manifest.json", body[:-1] + b" ")
        b, err = dv._probe(f"{CANON}/packets/manifest.json", expected=e)
        self.assertIsNone(b)
        self.assertIn("identity", err)

    def test_probe_without_expected_keeps_legacy_floor(self):
        """Callers that pass no expected identity keep the old conservative guard — not a blanket allow."""
        self.web.ok(f"{CANON}/tiny.html", b"<html>redirect-ish</html>")
        b, err = dv._probe(f"{CANON}/tiny.html")
        self.assertIsNone(b)
        self.assertIn("bytes <", err)

    def test_invalid_manifest_paths_rejected_without_probing(self):
        for bad in ("../secrets.json", "/etc/passwd", "", "a\\b.html", "https://yuclaw.ca/index.html"):
            self.assertEqual(self.run_main(bad), 1, bad)
        self.assertEqual(self.web.calls, [])

    def test_content_kind_checks_follow_the_artifact_contract(self):
        ok, why = dv._content_kind_ok("a.json", b'{"k": 1}')
        self.assertTrue(ok, why)
        ok, why = dv._content_kind_ok("a.json", b"<html>404</html>")
        self.assertFalse(ok)
        ok, why = dv._content_kind_ok("guide.pdf", b"%PDF-1.7\n...")
        self.assertTrue(ok, why)
        ok, why = dv._content_kind_ok("packets/x.zip", b"PK\x03\x04rest")
        self.assertTrue(ok, why)
        ok, why = dv._content_kind_ok("page.html", b"<!doctype html><html></html>")
        self.assertTrue(ok, why)
        ok, why = dv._content_kind_ok("items.jsonl", b'{"a":1}\n{"b":2}\n')
        self.assertTrue(ok, why)
        ok, why = dv._content_kind_ok("items.jsonl", b'{"a":1}\nnot json\n')
        self.assertFalse(ok)

    def test_full_mocked_run_mixed_sizes_and_one_stale(self):
        big = b"<!doctype html><html>" + b"z" * 3000 + b"</html>"
        small = short_manifest(730)
        self.local("index.html", big); self.local("packets/manifest.json", small); self.local("lane.html", big)
        self.web.ok(f"{CANON}/index.html", big)
        self.web.ok(f"{CANON}/packets/manifest.json", small)
        self.web.ok(f"{CANON}/lane.html", big + b"<!-- stale -->")
        self.assertEqual(self.run_main("index.html", "packets/manifest.json", "lane.html"), 1)
        self.web.ok(f"{CANON}/lane.html", big)
        self.assertEqual(self.run_main("index.html", "packets/manifest.json", "lane.html"), 0)


if __name__ == "__main__":
    unittest.main()

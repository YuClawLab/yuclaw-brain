"""Bounded disclosure ingestion (DAT boundary, V8-003 §1) — a command-line tool, never imported by the server.

One source at a time: fetch ONE URL from an allow-listed host with a bounded body, no cross-host redirects and an
identifying User-Agent; keep the original bytes and their digest; take EDGAR availability (acceptance time) from the
SEC submissions feed; extract the exact passage by a regular expression over the tag-stripped text; write a source
record the workbench's step 1 can register verbatim, plus a provenance record with the retrieval time kept apart
from availability. Nothing here executes, renders or follows page content; nothing is written outside `--out`.
Rights: EDGAR documents are SEC_PUBLIC_FILING; a company press release is COMPANY_PRESS_RELEASE (excerpt digest only
in exports). Research and education only. Not investment advice.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ALLOW_HOSTS = ("www.sec.gov", "data.sec.gov", "ir.microchip.com")
MAX_BYTES = 8 << 20
TIMEOUT = 60
# SEC fair-access policy: identify the requester. An operator other than the maintainer sets SEC_USER_AGENT to their own
# name and contact address (the same override the v3 EDGAR sources honour); the default identifies the maintainer.
USER_AGENT = os.environ.get("SEC_USER_AGENT", "YUCLAW research workbench (vzhang2099@gmail.com)")
_ACC = re.compile(r"^[0-9]{10}-[0-9]{2}-[0-9]{6}$")


class IngestError(ValueError):
    pass


class _NoCrossHostRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urllib.parse.urlsplit(newurl).netloc != urllib.parse.urlsplit(req.full_url).netloc:
            raise IngestError(f"cross-host redirect refused: {newurl}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _opener():
    return urllib.request.build_opener(_NoCrossHostRedirect())


def fetch(url: str, *, opener=None, max_bytes: int = MAX_BYTES, allow_hosts=ALLOW_HOSTS) -> dict:
    """Bounded GET. Returns {'url','final_url','status','content_type','bytes','sha256','retrieved_at','body'}."""
    u = urllib.parse.urlsplit(url)
    if u.scheme != "https" or u.netloc not in allow_hosts:
        raise IngestError(f"refused: only https on {list(allow_hosts)} (got {url})")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "identity"})
    op = opener or _opener()
    retrieved = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        with op.open(req, timeout=TIMEOUT) as r:
            body = r.read(max_bytes + 1)
            if len(body) > max_bytes:
                raise IngestError(f"refused: body exceeds {max_bytes} bytes")
            final = r.geturl(); status = r.status; ctype = r.headers.get("Content-Type", "")
    except urllib.error.HTTPError as exc:
        raise IngestError(f"HTTP {exc.code} for {url}") from None
    except urllib.error.URLError as exc:
        raise IngestError(f"fetch failed for {url}: {exc.reason}") from None
    if urllib.parse.urlsplit(final).netloc not in allow_hosts:
        raise IngestError(f"refused: final host {final} not allow-listed")
    return {"url": url, "final_url": final, "status": status, "content_type": ctype, "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(), "retrieved_at": retrieved, "body": body}


def strip_text(body: bytes) -> str:
    t = body.decode("utf-8", "replace")
    t = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", t, flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    return html.unescape(re.sub(r"\s+", " ", t)).strip()


def extract_passage(text: str, pattern: str) -> dict:
    m = re.search(pattern, text)
    if not m:
        raise IngestError(f"passage pattern not found: {pattern!r}")
    return {"excerpt": m.group(0).strip(), "start": m.start(), "end": m.end(), "pattern": pattern, "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()}


def edgar_availability(cik: str, accession: str, *, opener=None) -> dict:
    """Filing date, acceptance time (UTC) and form from the SEC submissions feed — the availability basis for EDGAR sources."""
    if not _ACC.match(accession):
        raise IngestError("accession format")
    got = fetch(f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json", opener=opener)
    d = json.loads(got["body"]); r = d["filings"]["recent"]
    for i, acc in enumerate(r["accessionNumber"]):
        if acc == accession:
            acc_dt = r["acceptanceDateTime"][i]                      # e.g. 2025-05-08T20:17:05.000Z
            avail = acc_dt[:19] + "Z" if acc_dt.endswith("Z") else acc_dt
            return {"form": r["form"][i], "filed_at": r["filingDate"][i], "available_as_of": avail, "acceptance_raw": acc_dt, "report_date": r["reportDate"][i], "primary_document": r["primaryDocument"][i],
                    "issuer_name": d.get("name"), "fiscal_year_end": d.get("fiscalYearEnd"), "tickers": d.get("tickers"), "feed_sha256": got["sha256"], "feed_retrieved_at": got["retrieved_at"]}
    raise IngestError(f"accession {accession} not in the recent submissions feed")


def ingest(*, url: str, kind: str, form: str, accession: str, cik: str | None, pattern: str, available_as_of: str | None, availability_basis: str, rights: str, out: Path, label: str, opener=None, filed_at: str | None = None) -> dict:
    got = fetch(url, opener=opener)
    out.mkdir(parents=True, exist_ok=True)
    raw = out / f"{label}.original.{'htm' if 'html' in got['content_type'] else 'bin'}"
    if raw.exists() and hashlib.sha256(raw.read_bytes()).hexdigest() != got["sha256"]:
        # a replay never replaces the original artifact it kept: the publisher's document changed since the first retrieval
        raise IngestError(f"refused: {raw.name} already holds different original bytes (the document at this URL changed since it was first retrieved); the earlier original is kept — use a new --label or --out for this retrieval")
    prior = out / f"{label}.provenance.json"                       # a replay of the same bytes keeps the time the document was FIRST retrieved
    earlier = json.loads(prior.read_text()) if raw.exists() and prior.exists() else {}
    first = earlier.get("first_retrieved_at") or earlier.get("retrieved_at")
    raw.write_bytes(got["body"])
    text = strip_text(got["body"]); passage = extract_passage(text, pattern)
    avail = available_as_of; edgar = None; filed = filed_at
    if kind == "filing":
        if cik is None:
            raise IngestError("cik required for a filing")
        edgar = edgar_availability(cik, accession, opener=opener); avail = edgar["available_as_of"]; filed = edgar["filed_at"]; availability_basis = "EDGAR acceptance time (SEC submissions feed)"
    if kind != "filing" and (not avail or not filed):
        raise IngestError("availability and filed date required for a non-filing source (give --available-as-of and --filed-at)")
    src = {"kind": kind, "form": form, "accession": accession, "url": url, "filed_at": filed, "available_as_of": avail, "excerpt": passage["excerpt"],
           "source_hash": hashlib.sha256(passage["excerpt"].encode("utf-8")).hexdigest(), "fictional": False, "rights": rights}
    prov = {"record": "yuclaw-ingestion/1", "label": label, "retrieved_at": got["retrieved_at"], "first_retrieved_at": first or got["retrieved_at"], "http": {"status": got["status"], "content_type": got["content_type"], "final_url": got["final_url"]},
            "original_bytes": {"file": raw.name, "sha256": got["sha256"], "bytes": got["bytes"]}, "passage": {k: v for k, v in passage.items() if k != "excerpt"}, "availability_basis": availability_basis, "edgar": edgar,
            "observed_at": got["retrieved_at"], "note": "observed_at is the retrieval time of this ingestion; available_as_of is when the source became public; the two are kept apart on every workbench event"}
    (out / f"{label}.source.json").write_text(json.dumps(src, indent=1, ensure_ascii=False) + "\n")
    (out / f"{label}.provenance.json").write_text(json.dumps(prov, indent=1, ensure_ascii=False) + "\n")
    return {"source": src, "provenance": prov}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--url", required=True); ap.add_argument("--kind", choices=("filing", "press_release", "transcript", "other"), required=True); ap.add_argument("--form", required=True)
    ap.add_argument("--accession", required=True, help="EDGAR accession, or PREFIX:publisher:id for a non-filing"); ap.add_argument("--cik"); ap.add_argument("--pattern", required=True, help="regex locating the exact passage in the tag-stripped text")
    ap.add_argument("--available-as-of", help="non-filings only: UTC RFC3339 when the source became public"); ap.add_argument("--filed-at", help="non-filings only: publication date YYYY-MM-DD")
    ap.add_argument("--availability-basis", default="stated by the caller"); ap.add_argument("--rights", choices=("SEC_PUBLIC_FILING", "COMPANY_PRESS_RELEASE", "UNKNOWN"), required=True)
    ap.add_argument("--out", required=True); ap.add_argument("--label", required=True)
    a = ap.parse_args(argv)
    try:
        r = ingest(url=a.url, kind=a.kind, form=a.form, accession=a.accession, cik=a.cik, pattern=a.pattern, available_as_of=a.available_as_of, availability_basis=a.availability_basis, rights=a.rights, out=Path(a.out), label=a.label, filed_at=a.filed_at)
    except IngestError as exc:
        print(f"[ingest] REFUSED: {exc}", file=sys.stderr); return 2
    print(json.dumps({"label": a.label, "sha256": r["provenance"]["original_bytes"]["sha256"], "available_as_of": r["source"]["available_as_of"], "retrieved_at": r["provenance"]["retrieved_at"], "excerpt": r["source"]["excerpt"][:160]}, ensure_ascii=False)); return 0


if __name__ == "__main__":
    sys.exit(main())

"""Composing briefs: template rendering, imported drafts, span links, edits, translations, review resolutions.

Every saved revision is a new immutable version record with a parent reference, a TransformRecord/1 (kind, implementation,
languages, changed-span mapping, review findings) and its own spans. Bytes are prepared in the vault first; the sidecar
record is the commit. A retry with the same op_id is answered by the sidecar (duplicate or conflict), and the version
identifier is derived from the state the operation first ran on, so a retry reproduces the same payload.

Support is decided here, deterministically where it can be: an exact quotation is checked against the registered excerpt
bytes; a template sentence carries its registered calculation; an operator's link of free prose to a claim is ATTRIBUTED
(the assessor is named), never SUPPORTED. On an edit, a parent span is MAPPED only when its exact bytes occur once in the
child; a mapped span keeps its support only if every protected slot still reads the same; anything else is INVALIDATED
with a review finding. Free prose that names a currency, a fiscal period or an accounting basis different from the claim's
produces a PROSE_CONTRADICTS_PROTECTED_FACT finding — within the declared scope of that scan (ISO currency codes, period
labels of the forms FY/Q/H/M + year, the basis words); no semantic contradiction beyond that scope is detected.
"""
from __future__ import annotations

import re
import secrets

from v3.receipts.contracts import ContractError, digest
from v8.workbench.store import Workspace
from v9.brief import contracts, snapshot, templates
from v9.brief.sidecar import Sidecar, now_ts

BRIEF_ID = re.compile(r"^brf-[0-9a-f]{12}$")
SENTENCE_SPLIT = re.compile(r"(?<=[.!?…])\s+(?=[^\s])|\n\n+")
EXTRACTOR = "v9.brief.compose/1 sentence segmentation (terminal punctuation and blank lines); not a claim extractor: it finds sentences, not claims, and misses nothing only in the sense that every byte belongs to some segment"
_CURRENCIES = ("USD", "CAD", "EUR", "GBP", "JPY", "CHF", "AUD", "CNY", "HKD", "SEK", "NOK", "DKK", "MXN", "BRL", "INR", "KRW", "SGD", "NZD")
_PERIOD = re.compile(r"\b(FY|Q[1-4]|H[12]|M(?:0[1-9]|1[0-2]))[\s ]?(20\d{2})\b")
_BASIS = {"GAAP": re.compile(r"(?<!non-)\bGAAP\b"), "IFRS": re.compile(r"\bIFRS\b"), "non-GAAP": re.compile(r"\bnon-GAAP\b")}
SCAN_SCOPE = "scan scope: ISO-4217 codes among a fixed list, fiscal-period labels FY/Qn/Hn/Mnn + year, and the words GAAP / non-GAAP / IFRS, anywhere in the text; semantic contradictions outside this scope are not detected"


def new_brief_id() -> str:
    return "brf-" + secrets.token_hex(6)


# ------------------------------------------------------------------ reading what exists
def versions_of(sc: Sidecar, brief_id: str, recs: list | None = None) -> list[dict]:
    return [r for r in sc.records("BRIEF_VERSION_RECORDED", brief_id, recs) ]


def version(sc: Sidecar, brief_id: str, version_id: str | None = None, recs: list | None = None) -> dict:
    vs = versions_of(sc, brief_id, recs)
    if not vs:
        raise ContractError(f"brief {brief_id!r} does not exist in this workspace")
    if version_id is None:
        return vs[-1]
    v = next((r for r in vs if r["payload"]["version_id"] == version_id), None)
    if v is None:
        raise ContractError(f"brief {brief_id!r} has no version {version_id!r} (versions: {[r['payload']['version_id'] for r in vs]})")
    return v


def text_of(sc: Sidecar, rec: dict) -> bytes:
    return sc.get_bytes(rec["payload"]["text_view"]["view_sha256"])


def snapshot_of(sc: Sidecar, rec: dict) -> dict:
    return sc.get_object(rec["payload"]["snapshot_object"])


def effective_spans(sc: Sidecar, rec: dict, recs: list | None = None) -> list[dict]:
    """The version's base spans with later span links applied (the newest link for the same byte range wins)."""
    p = rec["payload"]; spans = {(s["start"], s["end"]): s for s in p["spans"]}
    for l in sc.records("SPAN_LINK_RECORDED", rec["brief_id"], recs):
        lp = l["payload"]
        if lp["view_sha256"] == p["text_view"]["view_sha256"]:
            spans[(lp["span"]["start"], lp["span"]["end"])] = lp["span"]
    return [spans[k] for k in sorted(spans)]


# ------------------------------------------------------------------ deterministic support decisions
def quotation_support(span_bytes: bytes, snap: dict, claim_id: str | None) -> tuple[str, str, str]:
    """(support, method, limits) for a direct quotation: SUPPORTED when the quoted bytes (quotes stripped) are a verbatim
    substring of a registered excerpt of the linked claim's sources."""
    q = span_bytes.decode("utf-8")
    inner = q
    for a, b in (("“", "”"), ("« ", " »"), ("« ", " »"), ('"', '"')):
        if a in inner and b in inner:
            inner = inner[inner.index(a) + len(a): inner.rindex(b)]
    inner = inner.strip()
    claims = [snap["claims"][claim_id]] if claim_id and claim_id in snap["claims"] else list(snap["claims"].values())
    for c in claims:
        for s in c["sources"].values():
            if inner and inner in s["excerpt"]:
                return "SUPPORTED", "exact_quotation_match/1", f"verbatim substring of registered excerpt {s['source_id']} ({s['source_hash'][:16]}…); a quotation binds bytes, it does not authenticate the publisher"
    return "UNRESOLVED", "exact_quotation_match/1", "the quoted bytes are not a verbatim substring of any registered excerpt of the linked claim"


def scan_protected_contradictions(text: str, claim: dict) -> list[dict]:
    """Free-prose scan within SCAN_SCOPE against one claim's protected facts."""
    findings = []
    cur = claim["currency"]
    for code in sorted(set(re.findall(r"\b[A-Z]{3}\b", text))):
        if code in _CURRENCIES and code != cur:
            findings.append({"reason": "PROSE_CONTRADICTS_PROTECTED_FACT", "detail": f"the text names currency {code}; the claim's currency is {cur}. {SCAN_SCOPE}"})
    plabel = claim["fiscal_period"]["label"]
    for m in _PERIOD.finditer(text):
        lab = (m.group(1) + m.group(2)).replace(" ", "")
        if lab != plabel.replace(" ", ""):
            findings.append({"reason": "PROSE_CONTRADICTS_PROTECTED_FACT", "detail": f"the text names fiscal period {m.group(0)}; the claim's period is {plabel}. {SCAN_SCOPE}"})
    basis = claim["basis"]
    for word, rx in _BASIS.items():
        if rx.search(text) and not basis.startswith(word) and not (word == "GAAP" and basis == "GAAP"):
            if not (word == "non-GAAP" and basis.startswith("non-GAAP")):
                findings.append({"reason": "PROSE_CONTRADICTS_PROTECTED_FACT", "detail": f"the text names accounting basis {word}; the claim's basis is {basis}. {SCAN_SCOPE}"})
    seen, out = set(), []
    for f in findings:
        if f["detail"] not in seen:
            seen.add(f["detail"]); out.append(f)
    return out


def number_set(text: str) -> list[str]:
    return sorted(re.findall(r"\d+(?:[.,]\d+)?", text))


# ------------------------------------------------------------------ segmentation of imported prose (scope stated)
def segment(data: bytes) -> list[tuple[int, int]]:
    text = data.decode("utf-8"); out = []; pos = 0
    for part in SENTENCE_SPLIT.split(text):
        if part is None or not part.strip():
            continue
        i = text.index(part, pos); j = i + len(part)
        pos = j
        bs, be = len(text[:i].encode("utf-8")), len(text[:j].encode("utf-8"))
        s0 = bs + len(part) - len(part.lstrip()); e0 = be - (len(part) - len(part.rstrip()))
        if e0 > s0:
            out.append((s0, e0))
    return out[: contracts.MAX_SPANS]


def _span(data: bytes, start: int, end: int, *, role: str, claim, evidence, calculation, support: str, method: str, assessor: str, limits: str, protected=()) -> dict:
    raw = {"schema": contracts.CLAIM_SPAN, "view_sha256": contracts.sha256_hex(data), "start": start, "end": end, "span_sha256": contracts.span_digest(data, start, end), "role": role,
           "claim": claim, "evidence": evidence, "calculation": calculation, "support": support, "method": method, "assessor": assessor, "limits": limits, "protected": list(protected)}
    return contracts.validate(lambda r: contracts.check_claim_span(r, data), raw, "span")


# ------------------------------------------------------------------ receipts for local productions
def _stamp(prior: dict | None, *path: str) -> str:
    """The timestamp a retried operation reuses so that the same content reproduces the same payload (v8's rule): the prior
    record's value when the op_id was seen before, otherwise now."""
    if prior is not None:
        v = prior.get("payload")
        for k in path:
            v = v.get(k) if isinstance(v, dict) else None
        if isinstance(v, str):
            return v
    return now_ts()


def _local_receipt(*, method: str, inputs: list[str], template: str | None, out_digest: str, raw_digest: str | None, provenance: str, settings: dict | None = None, observed_at: str | None = None) -> dict:
    unknown = {}
    if method != "template_deterministic":
        unknown = {"provider": "not exposed: the text was entered or imported locally; no provider response was observed by this workbench",
                   "model": "not exposed: no model identity accompanies locally entered or imported text",
                   "settings": "not exposed: no generation settings accompany locally entered or imported text"}
    raw = {"schema": contracts.GENERATION_RECEIPT, "origin": "operator_assertion", "recording_method": method, "inputs": inputs, "template": template,
           "prompt_sha256": None, "prompt_disclosure": "unknown" if method != "template_deterministic" else "permitted", "provider": None if method != "template_deterministic" else "local",
           "model": None if method != "template_deterministic" else templates.RENDERER, "settings": settings or {}, "raw_output_sha256": raw_digest, "assembled_output_sha256": out_digest,
           "request_id": None, "issued_at": None, "observed_at": observed_at or now_ts(), "unknown": unknown, "signature_envelope": None}
    rec = contracts.validate(contracts.check_generation_receipt, raw, "generation receipt")
    rec["provenance_note"] = provenance
    return rec


def _transform(kind, parent_view, child_view, implementation, lang_from, lang_to, mapping_method, mapping, findings, actor, provenance, review_status="unreviewed") -> dict:
    raw = {"schema": contracts.TRANSFORM_RECORD, "kind": kind, "parent_view": parent_view, "child_view": child_view, "implementation": implementation, "language_from": lang_from, "language_to": lang_to,
           "mapping_method": mapping_method, "mapping": mapping, "review_findings": findings, "actor": actor, "provenance": provenance, "review_status": review_status}
    return contracts.validate(contracts.check_transform, raw, "transform record")


def _next_version_id(sc: Sidecar, brief_id: str, prior: dict | None) -> str:
    recs = sc.load()["records"]
    if prior is not None:
        recs = [r for r in recs if r["seq"] < prior["seq"]]
    return f"B{len(versions_of(sc, brief_id, recs)) + 1}"


# ------------------------------------------------------------------ 1. create from a template
def create_from_template(ws: Workspace, sc: Sidecar, *, claim_id: str, sections: list[str], lang: str, op_id: str, actor: str, brief_id: str | None = None) -> tuple[dict, bool]:
    snap = snapshot.build(ws, [claim_id])
    data, spans, prod = templates.render(snap, claim_id, sections, lang)
    with ws._locked():
        prior = sc.prior(op_id)
        bid = prior["brief_id"] if prior is not None else (brief_id or new_brief_id())
        if not BRIEF_ID.match(bid):
            raise ContractError("brief id must look like brf-<12 hex>")
        if prior is None and versions_of(sc, bid):
            raise ContractError(f"brief {bid!r} already exists; a change is a new version, never a second creation")
        snap_h = sc.put_object(snap); text_h = sc.put_bytes(data)
        view = contracts.make_text_view(data, source_artifact=None, extraction=templates.RENDERER, normalization="none", language=lang)
        receipt = _local_receipt(method="template_deterministic", inputs=[snap_h], template=prod["template"], out_digest=view["view_sha256"], raw_digest=view["view_sha256"],
                                 provenance="rendered by the deterministic template engine from the recorded snapshot; reproducible", settings=prod["settings"], observed_at=_stamp(prior, "receipt", "observed_at"))
        transform = _transform("template_render", None, view["view_sha256"], templates.RENDERER, None, lang, "identity", [], [], actor, "deterministic rendering from the snapshot")
        payload = {"schema": contracts.BRIEF_VERSION, "brief_id": bid, "version_id": _next_version_id(sc, bid, prior), "parent_version": None, "language": lang,
                   "title": prod["sections"][0] if prod["sections"] else bid, "claim_ids": [claim_id], "text_view": view, "spans": spans, "snapshot_digest": snap["snapshot_digest"],
                   "snapshot_object": snap_h, "v8_tip_at_snapshot": snap["v8_tip"], "production": prod, "receipt": receipt, "transform": transform, "extraction_scope": "template sentences are the statements; every sentence is a span",
                   "objects": [snap_h, text_h]}
        rec, dup = sc._append_unlocked("BRIEF_VERSION_RECORDED", bid, payload, op_id=op_id, actor=actor)
        return rec, dup


# ------------------------------------------------------------------ 2. import a draft
def import_draft(ws: Workspace, sc: Sidecar, *, text: bytes, lang: str, claim_ids: list[str], provenance: str, actor: str, op_id: str, brief_id: str | None = None,
                 origin_receipt: dict | None = None, rights: str = "OPERATOR_OWN_TEXT") -> tuple[dict, bool]:
    if not isinstance(text, (bytes, bytearray)) or not text.strip():
        raise ContractError("draft text is required (UTF-8 bytes)")
    if rights not in contracts.RIGHTS:
        raise ContractError(f"rights must be one of {list(contracts.RIGHTS)}")
    snap = snapshot.build(ws, claim_ids)
    data = bytes(text)
    view = contracts.make_text_view(data, source_artifact=contracts.sha256_hex(data), extraction="imported draft, bytes as supplied", normalization="none", language=lang)
    with ws._locked():
        prior = sc.prior(op_id)
        bid = prior["brief_id"] if prior is not None else (brief_id or new_brief_id())
        if prior is None and versions_of(sc, bid):
            raise ContractError(f"brief {bid!r} already exists")
        snap_h = sc.put_object(snap); text_h = sc.put_bytes(data)
        artifact = contracts.validate(contracts.check_artifact, {"schema": contracts.ARTIFACT, "content_sha256": text_h, "byte_length": len(data), "media_type": "text/plain; charset=utf-8", "encoding": "utf-8",
                                                                  "rights": rights, "collection_method": "imported_file", "asserted_available_as_of": None, "observed_at": _stamp(prior, "artifact", "observed_at"), "label": "imported draft", "parents": []}, "artifact")
        spans = [_span(data, s, e, role="generated_commentary", claim=None, evidence=[], calculation=None, support="NOT_ASSESSED", method="none", assessor=EXTRACTOR,
                       limits="identified by sentence segmentation; link it to a claim or mark its role to assess it") for s, e in segment(data)]
        if origin_receipt is not None:
            receipt = contracts.validate(contracts.check_generation_receipt, dict(origin_receipt, assembled_output_sha256=view["view_sha256"]), "generation receipt")
        else:
            receipt = _local_receipt(method="imported_file", inputs=[snap_h, text_h], template=None, out_digest=view["view_sha256"], raw_digest=text_h, provenance=provenance, observed_at=_stamp(prior, "receipt", "observed_at"))
        transform = _transform("import", None, view["view_sha256"], "imported draft", None, lang, "none", [], [], actor, provenance)
        payload = {"schema": contracts.BRIEF_VERSION, "brief_id": bid, "version_id": _next_version_id(sc, bid, prior), "parent_version": None, "language": lang, "title": f"Imported draft {bid}",
                   "claim_ids": list(dict.fromkeys(claim_ids)), "text_view": view, "spans": spans, "snapshot_digest": snap["snapshot_digest"], "snapshot_object": snap_h, "v8_tip_at_snapshot": snap["v8_tip"],
                   "production": {"renderer": None, "template": None, "language": lang, "imported": True, "deterministic": False}, "receipt": receipt, "transform": transform, "artifact": artifact,
                   "extraction_scope": EXTRACTOR, "objects": [snap_h, text_h]}
        return sc._append_unlocked("BRIEF_VERSION_RECORDED", bid, payload, op_id=op_id, actor=actor)


# ------------------------------------------------------------------ 3. link or correct a span
def link_span(ws: Workspace, sc: Sidecar, *, brief_id: str, version_id: str | None, start: int, end: int, role: str, claim_id: str | None, version_ref: str | None,
              actor: str, note: str, op_id: str) -> tuple[dict, bool]:
    with ws._locked():
        rec = version(sc, brief_id, version_id); data = text_of(sc, rec); snap = snapshot_of(sc, rec)
        problems = contracts.span_problems(data, start, end)
        if problems:
            raise ContractError("span cannot be linked: " + "; ".join(problems))
        if role not in contracts.ROLES:
            raise ContractError(f"role must be one of {list(contracts.ROLES)}")
        claim, evidence = None, []
        if claim_id is not None:
            c = snap["claims"].get(claim_id)
            if c is None:
                raise ContractError(f"claim {claim_id!r} is not in this brief's snapshot ({list(snap['claims'])})")
            vid = version_ref or c["current_version"]
            v = next((x for x in c["versions"] if x["version_id"] == vid), None)
            if v is None:
                raise ContractError(f"version {vid!r} is not a version of {claim_id} in the snapshot")
            claim = {"claim_id": claim_id, "version_id": vid, "claim_digest": v["claim_digest"]}
            evidence = [{"kind": "claim_version", "ref": f"{claim_id}#{vid}", "digest": v["claim_digest"]}] + [{"kind": "source_excerpt", "ref": sid, "digest": s["source_hash"]} for sid, s in c["sources"].items()]
        if role == "direct_quotation":
            support, method, limits = quotation_support(data[start:end], snap, claim_id)
        elif role == "unresolved_claim":
            support, method, limits = "UNRESOLVED", "none", "marked unresolved by the operator: " + (note or "no evidence recorded")
        elif claim is not None:
            support, method, limits = "ATTRIBUTED", "assessor_assertion/1", f"the operator {actor!r} links this sentence to {claim_id}#{claim['version_id']}; this is an attributed suggestion, not a deterministic check. {note}".strip()
        else:
            support, method, limits = "NOT_ASSESSED", "none", note or "role recorded without a claim link"
        sp = _span(data, start, end, role=role, claim=claim, evidence=evidence, calculation=None, support=support, method=method, assessor=f"operator:{actor}", limits=limits)
        payload = {"brief_id": brief_id, "version_id": rec["payload"]["version_id"], "view_sha256": rec["payload"]["text_view"]["view_sha256"], "span": sp, "note": note or "", "objects": []}
        return sc._append_unlocked("SPAN_LINK_RECORDED", brief_id, payload, op_id=op_id, actor=actor)


# ------------------------------------------------------------------ 4. edit / translate → a new version
def _map_spans(parent_spans: list[dict], parent: bytes, child: bytes, snap: dict) -> tuple[list[dict], list[dict], list[dict]]:
    """Exact-bytes-unique mapping with protected-slot validation. Returns (child spans, mapping rows, findings)."""
    spans, mapping, findings = [], [], []
    for ps in parent_spans:
        pb = parent[ps["start"]:ps["end"]]
        n = child.count(pb)
        if n == 1:
            s = child.index(pb); e = s + len(pb)
            prot = [dict(p, start=p["start"] - ps["start"] + s, end=p["end"] - ps["start"] + s) for p in ps["protected"]]
            support, method, limits = ps["support"], ps["method"], ps["limits"]
            if ps["role"] == "direct_quotation":
                support, method, limits = quotation_support(pb, snap, (ps.get("claim") or {}).get("claim_id"))
            spans.append(_span(child, s, e, role=ps["role"], claim=ps["claim"], evidence=ps["evidence"], calculation=ps["calculation"], support=support, method=method,
                               assessor=ps["assessor"], limits=limits, protected=prot))
            mapping.append({"parent_span": ps["record_id"], "child_start": s, "child_end": e, "status": "MAPPED"})
            continue
        # not found verbatim: look for the protected slots to say WHAT changed
        changed = [p for p in ps["protected"] if child.count(p["value"].encode("utf-8")) == 0]
        if ps["protected"] and changed:
            findings.append({"reason": "PROTECTED_FACT_CHANGED", "detail": f"sentence {ps['start']}..{ps['end']} of the parent lost protected slot(s) {[p['slot'] for p in changed]}; its {ps['support']} support does not carry over", "span": ps["record_id"]})
            # the child sentence that still carries most of the remaining protected values inherits the link as INVALIDATED (never the support)
            kept = [p["value"].encode("utf-8") for p in ps["protected"] if p not in changed]
            best, best_n = None, 0
            for cs, ce in segment(child):
                k = sum(1 for v in kept if v in child[cs:ce])
                if k > best_n:
                    best, best_n = (cs, ce), k
            if best is not None and not any(sp["start"] == best[0] and sp["end"] == best[1] for sp in spans):
                spans.append(_span(child, best[0], best[1], role=ps["role"], claim=ps["claim"], evidence=ps["evidence"], calculation=ps["calculation"], support="INVALIDATED", method=ps["method"],
                                   assessor=ps["assessor"], limits=f"protected slot(s) {[p['slot'] for p in changed]} changed in this edit; the parent's {ps['support']} does not carry over; re-link after checking the typed fact"))
                mapping.append({"parent_span": ps["record_id"], "child_start": best[0], "child_end": best[1], "status": "CHANGED"}); continue
        else:
            findings.append({"reason": "SPAN_UNMAPPED", "detail": f"sentence {ps['start']}..{ps['end']} of the parent has no unique verbatim occurrence in the new text ({n} occurrences); link it again if it still appears in other words", "span": ps["record_id"]})
        mapping.append({"parent_span": ps["record_id"], "child_start": None, "child_end": None, "status": "CHANGED" if changed else "UNMAPPED"})
    covered = set()
    for s in spans:
        covered.update(range(s["start"], s["end"]))
    # new sentences in the child that no parent span covers become unassessed statements; text carried over verbatim that was never a
    # statement (headings) stays plain text
    for s, e in segment(child):
        if any(i in covered for i in range(s, e)) or child[s:e] in parent:
            continue
        spans.append(_span(child, s, e, role="generated_commentary", claim=None, evidence=[], calculation=None, support="NOT_ASSESSED", method="none", assessor=EXTRACTOR, limits="new sentence; link or mark it"))
    spans.sort(key=lambda x: x["start"])
    return spans, mapping, findings


def revise(ws: Workspace, sc: Sidecar, *, brief_id: str, parent_version_id: str | None, text: bytes, kind: str, lang_to: str | None, actor: str, provenance: str, op_id: str,
           review_status: str = "unreviewed") -> tuple[dict, bool]:
    if kind not in ("edit", "translate"):
        raise ContractError("kind must be edit or translate")
    if not isinstance(text, (bytes, bytearray)) or not text.strip():
        raise ContractError("the revised text is required")
    with ws._locked():
        prior = sc.prior(op_id)
        parent = version(sc, brief_id, parent_version_id)
        pp = parent["payload"]; pdata = text_of(sc, parent); snap = snapshot_of(sc, parent)
        lang = pp["language"] if kind == "edit" else lang_to
        if kind == "translate" and (lang_to is None or lang_to == pp["language"]):
            raise ContractError("a translation names a target language different from the parent's")
        data = bytes(text)
        if data == pdata:
            raise ContractError("the text is identical to the parent version; changing language or text creates new bytes, nothing changed")
        view = contracts.make_text_view(data, source_artifact=pp["text_view"]["view_sha256"], extraction=f"{kind} by operator", normalization="none", language=lang)
        pspans = effective_spans(sc, parent)
        if kind == "edit":
            spans, mapping, findings = _map_spans(pspans, pdata, data, snap)
            mapping_method = "exact_bytes_unique/1"
            for cid in pp["claim_ids"]:
                c = snap["claims"][cid]; cur = next(v for v in c["versions"] if v["version_id"] == c["current_version"])["claim"]
                findings += scan_protected_contradictions(data.decode("utf-8"), cur)
        else:
            spans = [_span(data, s, e, role="generated_commentary", claim=None, evidence=[], calculation=None, support="NOT_ASSESSED", method="none", assessor=EXTRACTOR,
                           limits="translated sentence; its binding to evidence is not inherited across languages — link it, or re-render the typed template in this language") for s, e in segment(data)]
            mapping = [{"parent_span": ps["record_id"], "child_start": None, "child_end": None, "status": "UNMAPPED"} for ps in pspans]
            mapping_method = "none"
            findings = [{"reason": "SPAN_UNMAPPED", "detail": f"{len(pspans)} parent statement(s) are not bound in the translation; the typed numbers were compared instead", "span": None}]
            pn, cn = number_set(pdata.decode("utf-8")), number_set(data.decode("utf-8"))
            if pn != cn:
                findings.append({"reason": "PROSE_CONTRADICTS_PROTECTED_FACT", "detail": f"the numbers in the translation differ from the parent's: parent {pn} vs translation {cn} (digit sequences compared, language-independent)", "span": None})
            for cid in pp["claim_ids"]:
                c = snap["claims"][cid]; cur = next(v for v in c["versions"] if v["version_id"] == c["current_version"])["claim"]
                findings += scan_protected_contradictions(data.decode("utf-8"), cur)
        text_h = sc.put_bytes(data)
        receipt = _local_receipt(method="operator_entered", inputs=[pp["text_view"]["view_sha256"]], template=None, out_digest=view["view_sha256"], raw_digest=text_h, provenance=provenance, observed_at=_stamp(prior, "receipt", "observed_at"))
        transform = _transform(kind, pp["text_view"]["view_sha256"], view["view_sha256"], f"operator {kind} through the workbench form or CLI", pp["language"], lang, mapping_method, mapping, findings, actor, provenance, review_status)
        payload = {"schema": contracts.BRIEF_VERSION, "brief_id": brief_id, "version_id": _next_version_id(sc, brief_id, prior), "parent_version": pp["version_id"], "language": lang, "title": pp["title"],
                   "claim_ids": pp["claim_ids"], "text_view": view, "spans": spans, "snapshot_digest": pp["snapshot_digest"], "snapshot_object": pp["snapshot_object"], "v8_tip_at_snapshot": pp["v8_tip_at_snapshot"],
                   "production": {"renderer": None, "template": None, "language": lang, "kind": kind, "deterministic": False}, "receipt": receipt, "transform": transform,
                   "extraction_scope": EXTRACTOR, "objects": [pp["snapshot_object"], text_h]}
        return sc._append_unlocked("BRIEF_VERSION_RECORDED", brief_id, payload, op_id=op_id, actor=actor)


def retranslate_template(ws: Workspace, sc: Sidecar, *, brief_id: str, parent_version_id: str | None, lang_to: str, actor: str, op_id: str) -> tuple[dict, bool]:
    """Deterministic translation of a template-rendered version: the same snapshot and sections re-rendered in the other
    language, so every typed statement is bound again (no prose translation is involved)."""
    with ws._locked():
        prior = sc.prior(op_id); parent = version(sc, brief_id, parent_version_id); pp = parent["payload"]
        prod = pp.get("production") or {}
        if not prod.get("deterministic"):
            raise ContractError("only a template-rendered version can be re-rendered in another language; translate an imported or edited text by entering its translation")
        if lang_to == pp["language"]:
            raise ContractError("the version is already in that language")
        snap = snapshot_of(sc, parent)
        data, spans, prod2 = templates.render(snap, prod["claim_id"], prod["settings"]["sections"], lang_to)
        text_h = sc.put_bytes(data)
        view = contracts.make_text_view(data, source_artifact=pp["text_view"]["view_sha256"], extraction=templates.RENDERER, normalization="none", language=lang_to)
        mapping = [{"parent_span": ps["record_id"], "child_start": cs["start"], "child_end": cs["end"], "status": "MAPPED"} for ps, cs in zip(pp["spans"], spans)] if len(pp["spans"]) == len(spans) else []
        receipt = _local_receipt(method="template_deterministic", inputs=[pp["snapshot_object"]], template=prod2["template"], out_digest=view["view_sha256"], raw_digest=view["view_sha256"],
                                 provenance="deterministic re-rendering of the same snapshot in another language", settings=prod2["settings"], observed_at=_stamp(prior, "receipt", "observed_at"))
        transform = _transform("translate", pp["text_view"]["view_sha256"], view["view_sha256"], templates.RENDERER, pp["language"], lang_to, "operator_mapped/1" if mapping else "none", mapping, [], actor,
                               "typed template re-rendered; statement i of the parent corresponds to statement i of the child", "operator_reviewed")
        payload = {"schema": contracts.BRIEF_VERSION, "brief_id": brief_id, "version_id": _next_version_id(sc, brief_id, prior), "parent_version": pp["version_id"], "language": lang_to, "title": prod2["sections"][0],
                   "claim_ids": pp["claim_ids"], "text_view": view, "spans": spans, "snapshot_digest": pp["snapshot_digest"], "snapshot_object": pp["snapshot_object"], "v8_tip_at_snapshot": pp["v8_tip_at_snapshot"],
                   "production": prod2, "receipt": receipt, "transform": transform, "extraction_scope": "template sentences are the statements", "objects": [pp["snapshot_object"], text_h]}
        return sc._append_unlocked("BRIEF_VERSION_RECORDED", brief_id, payload, op_id=op_id, actor=actor)


# ------------------------------------------------------------------ 5. review items
def review_item_id(f: dict) -> str:
    return digest({k: f.get(k) for k in ("reason", "dependency", "version_id", "corrections", "span", "detail")})[:24]


def resolve_review(ws: Workspace, sc: Sidecar, *, brief_id: str, item_id: str, disposition: str, note: str, actor: str, op_id: str) -> tuple[dict, bool]:
    if disposition not in ("REVIEWED_NO_CHANGE", "REVISED", "WITHDRAWN_STATEMENT", "DISPUTED"):
        raise ContractError("disposition must be REVIEWED_NO_CHANGE, REVISED, WITHDRAWN_STATEMENT or DISPUTED")
    if not note or len(note) > contracts.FIELD_MAX:
        raise ContractError("a note is required")
    with ws._locked():
        version(sc, brief_id)
        return sc._append_unlocked("REVIEW_ITEM_RESOLVED", brief_id, {"item_id": item_id, "disposition": disposition, "note": note, "objects": []}, op_id=op_id, actor=actor)

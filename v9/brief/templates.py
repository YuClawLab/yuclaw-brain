"""Deterministic bilingual templates: typed financial statements rendered to exact bytes with their spans attached.

A template renders sentences one by one into one UTF-8 byte string while recording, for every sentence, the half-open byte
offsets it occupies, its role, the claim version and evidence it rests on, the calculation record it states, and the
PROTECTED slots inside it (currency, amounts, period label, basis, accession, percent). Digits are identical in both
languages; only presentation differs (French uses a decimal comma, a narrow no-break space before % and the units word
of the language). Nothing here reads a clock, a file or the network: the same snapshot renders the same bytes.

Three templates ship: `guidance_change` (the acceptance example), `numerical_comparison` (a source-backed comparison of two
ranges with a direct quotation when rights allow it) and `unresolved_interpretation` (an explicitly unresolved causal
sentence beside what evidence would resolve it). A brief may stack several of them as sections.
"""
from __future__ import annotations

from decimal import Decimal

from v3.receipts.contracts import ContractError
from v8.workbench import money
from v9.brief import contracts, finance

RENDERER = "v9.brief.templates/1"
TEMPLATES = ("guidance_change", "numerical_comparison", "unresolved_interpretation")
TEMPLATE_HELP = {
    "guidance_change": ("original and revised guidance, midpoints, absolute and relative change, the later actual against both ranges, and the no-inference limit",
                        "prévisions initiales et révisées, points médians, variation absolue et relative, résultat ultérieur face aux deux fourchettes, et la limite d’inférence"),
    "numerical_comparison": ("a source-backed comparison of the two ranges (ends, widths, overlap) with a direct quotation of the source where rights allow",
                             "une comparaison des deux fourchettes appuyée sur la source (bornes, largeurs, chevauchement) avec une citation directe quand les droits le permettent"),
    "unresolved_interpretation": ("an explicitly unresolved causal interpretation and the evidence that would resolve it", "une interprétation causale explicitement non résolue et les éléments qui la résoudraient"),
}
NBSP, NNBSP = " ", " "
MAX_QUOTE_BYTES = 600


# ------------------------------------------------------------------ presentation helpers (digits identical in both languages)
def fmt_number(s: str, lang: str) -> str:
    """'-4.35' → '-4.35' (en) / '−4,35' (fr, with the real minus sign); integers unchanged."""
    if lang == "fr":
        return s.replace("-", "−").replace(".", ",")
    return s


def amount(value, scale: str, currency: str, lang: str) -> tuple[str, dict]:
    """'USD 110 million' / '110 millions USD' — returns the text and the slot map {currency, amount_in_scale, scale}."""
    v = finance.in_scale(money.parse_amount(value), scale)
    word = finance.SCALE_WORD[lang][scale]
    if lang == "fr":
        txt = f"{fmt_number(v, lang)}{NBSP}{word}{NBSP}{currency}" if word else f"{fmt_number(v, lang)}{NBSP}{currency}"
    else:
        txt = f"{currency} {v} {word}" if word else f"{currency} {v}"
    return txt, {"amount": v, "scale": scale, "currency": currency}


def amount_range(low, high, scale: str, currency: str, lang: str) -> str:
    lo, hi = finance.in_scale(money.parse_amount(low), scale), finance.in_scale(money.parse_amount(high), scale)
    word = finance.SCALE_WORD[lang][scale]
    if lang == "fr":
        return f"{fmt_number(lo, lang)}–{fmt_number(hi, lang)}{NBSP}{word}{NBSP}{currency}" if word else f"{fmt_number(lo, lang)}–{fmt_number(hi, lang)}{NBSP}{currency}"
    return f"{currency} {lo}–{hi} {word}" if word else f"{currency} {lo}–{hi}"


def signed(value, scale: str, lang: str) -> str:
    d = money.parse_amount(value); v = finance.in_scale(d, scale)
    s = v if d < 0 else f"+{v}"
    return fmt_number(s, lang)


def percent(value_percent: str, lang: str) -> str:
    return f"{fmt_number(value_percent, 'fr')}{NNBSP}%" if lang == "fr" else f"{value_percent}%"


def period(p: dict) -> str:
    return p["label"]


# ------------------------------------------------------------------ the renderer
class Render:
    """Accumulates sentences into bytes and spans. Each `sentence()` call becomes one ClaimSpan."""

    def __init__(self, lang: str):
        if lang not in contracts.LANGUAGES:
            raise ContractError("language must be en or fr")
        self.lang = lang; self.buf = bytearray(); self.spans = []; self.sections = []

    def heading(self, text: str):
        if self.buf and not bytes(self.buf).endswith(b"\n\n"):
            self.buf += b"\n\n"
        self.buf += text.encode("utf-8") + b"\n\n"
        self.sections.append(text)

    def para_break(self):
        self.buf += b"\n\n"

    def sentence(self, text: str, *, role: str, claim: dict | None, evidence: list[dict], calculation: dict | None, support: str, method: str, limits: str,
                 protected: list[tuple[str, str]] = (), sep: str = " ") -> dict:
        if self.buf and not bytes(self.buf).endswith(b"\n\n"):
            self.buf += sep.encode("utf-8")
        start = len(self.buf); data = text.encode("utf-8"); self.buf += data; end = len(self.buf)
        prot = []
        for slot, value in protected:
            if not value:
                continue
            off = data.find(value.encode("utf-8"))
            if off < 0:
                raise ContractError(f"template error: protected slot {slot}={value!r} not found in its sentence")
            prot.append({"slot": slot, "value": value, "start": start + off, "end": start + off + len(value.encode("utf-8"))})
        span = {"schema": contracts.CLAIM_SPAN, "view_sha256": None, "start": start, "end": end, "span_sha256": contracts.sha256_hex(data), "role": role, "claim": claim,
                "evidence": evidence, "calculation": calculation, "support": support, "method": method, "assessor": RENDERER, "limits": limits, "protected": prot}
        self.spans.append(span)
        return span

    def finish(self) -> tuple[bytes, list[dict]]:
        data = bytes(self.buf); vd = contracts.sha256_hex(data)
        out = []
        for s in self.spans:
            s = dict(s, view_sha256=vd)
            rec, reasons = contracts.check_claim_span(s, data)
            if reasons:
                raise ContractError("template produced an invalid span: " + "; ".join(reasons))
            out.append(rec)
        return data, out


# ------------------------------------------------------------------ evidence helpers over a snapshot claim entry
def _ver(c: dict, vid: str) -> dict:
    return next(v for v in c["versions"] if v["version_id"] == vid)


def _claim_ref(c: dict, vid: str) -> dict:
    v = _ver(c, vid)
    return {"claim_id": c["claim_id"], "version_id": vid, "claim_digest": v["claim_digest"]}


def _src_ev(c: dict, src: dict) -> dict:
    from v8.workbench import availability
    sid = availability.source_id(src)
    return {"kind": "source_excerpt", "ref": sid, "digest": src["source_hash"]}


def _ver_ev(c: dict, vid: str) -> dict:
    return {"kind": "claim_version", "ref": f"{c['claim_id']}#{vid}", "digest": _ver(c, vid)["claim_digest"]}


def _calc_ev(rec: dict) -> dict:
    return {"kind": "calculation", "ref": rec["kind"], "digest": rec["record_id"]}


def _issuer(cl: dict) -> str:
    return f"{cl['issuer']['name']} ({cl['issuer']['ticker']})"


def _form(src: dict, lang: str) -> str:
    return src["form"]


# ------------------------------------------------------------------ templates
def guidance_change(r: Render, c: dict) -> None:
    lang = r.lang
    vO = _ver(c, c["original_effective_version"]); clO = vO["claim"]; sO = clO["source"]
    if not c["revised_versions"]:
        raise ContractError(f"guidance_change needs a REVISED version of {c['claim_id']}; it has none (use numerical_comparison or an unresolved interpretation instead)")
    vR = _ver(c, c["revised_versions"][-1]); clR = vR["claim"]; sR = clR["source"]
    ok, why = finance.same_scope(clO, clR)
    if not ok:
        raise ContractError("guidance_change refused: the revised version changes the financial scope (" + "; ".join(why) + "); no comparison is rendered across scopes")
    cur, scale, basis, per = clO["currency"], clO["scale_as_stated"], clO["basis"], period(clO["fiscal_period"])
    r.heading({"en": f"Guidance change — {_issuer(clO)}, {clO['metric']} {per}", "fr": f"Révision des prévisions — {_issuer(clO)}, {clO['metric']} {per}"}[lang])
    rngO = amount_range(clO["range"]["low"], clO["range"]["high"], scale, cur, lang)
    t1 = {"en": f"{_issuer(clO)} stated {clO['metric']} guidance for {per} ({basis}) of {rngO} in its {_form(sO, lang)} filed {sO['filed_at']} (accession {sO['accession']}).",
          "fr": f"{_issuer(clO)} a annoncé des prévisions de {clO['metric']} pour {per} ({basis}) de {rngO} dans son {_form(sO, lang)} déposé le {sO['filed_at']} (numéro {sO['accession']})."}[lang]
    r.sentence(t1, role="attributed_source_statement", claim=_claim_ref(c, vO["version_id"]), evidence=[_src_ev(c, sO), _ver_ev(c, vO["version_id"])], calculation=None,
               support="SUPPORTED", method="typed_slot_render/1", limits="the typed claim version restates the source; the quotation of the passage is the evidence, the restatement is the researcher's",
               protected=[("currency", cur), ("period", per), ("basis", basis), ("accession", sO["accession"]), ("range", rngO)])
    rngR = amount_range(clR["range"]["low"], clR["range"]["high"], scale, cur, lang)
    t2 = {"en": f"In its {_form(sR, lang)} filed {sR['filed_at']} (accession {sR['accession']}), the company revised that guidance to {rngR}.",
          "fr": f"Dans son {_form(sR, lang)} déposé le {sR['filed_at']} (numéro {sR['accession']}), la société a révisé ces prévisions à {rngR}."}[lang]
    r.sentence(t2, role="attributed_source_statement", claim=_claim_ref(c, vR["version_id"]), evidence=[_src_ev(c, sR), _ver_ev(c, vR["version_id"])], calculation=None,
               support="SUPPORTED", method="typed_slot_render/1", limits="rendered from the frozen revised version; it does not say why the revision was made",
               protected=[("accession", sR["accession"]), ("range", rngR)])
    g = finance.guidance_change_record(clO, clR)
    m1, _ = amount(g["midpoint_original"], scale, cur, lang); m2, _ = amount(g["midpoint_revised"], scale, cur, lang)
    chg = signed(g["absolute_change"], scale, lang); pct = percent(g["relative_change"]["value_percent"], lang)
    word = finance.SCALE_WORD[lang][scale]
    t3 = {"en": f"The midpoint moved from {m1} to {m2}: a change of {chg} {word} ({pct}, computed as {fmt_number(finance.in_scale(money.parse_amount(g['absolute_change']), scale), lang)} / {fmt_number(finance.in_scale(money.parse_amount(g['midpoint_original']), scale), lang)} × 100 and rounded half-even to two decimals, so approximately).",
          "fr": f"Le point médian est passé de {m1} à {m2} : une variation de {chg}{NBSP}{word} ({pct}, calculée comme {fmt_number(finance.in_scale(money.parse_amount(g['absolute_change']), scale), lang)} / {fmt_number(finance.in_scale(money.parse_amount(g['midpoint_original']), scale), lang)} × 100 et arrondie au pair le plus proche à deux décimales, donc approximativement)."}[lang]
    r.sentence(t3, role="computed_statement", claim=_claim_ref(c, vR["version_id"]), evidence=[_ver_ev(c, vO["version_id"]), _ver_ev(c, vR["version_id"]), _calc_ev(g)], calculation=g,
               support="SUPPORTED", method="registered_arithmetic/1", limits="exact midpoints and difference; the percentage is rounded under the stated rule; agreement of the two ranges is not evidence of accuracy",
               protected=[("midpoint_original", m1), ("midpoint_revised", m2), ("absolute_change", chg), ("relative_change", pct)])
    out = c.get("outcome")
    if out is not None:
        oc = out["outcome"]; sA = oc["source"]
        cO = finance.containment_record(clO, oc, label="original range"); cR = finance.containment_record(clR, oc, label="revised range")
        act, _ = amount(oc["actual"], scale, cur, lang)
        unresolved = cO["result"] in ("IN_RANGE", "OUT_OF_RANGE") and cR["result"] in ("IN_RANGE", "OUT_OF_RANGE")
        if unresolved:
            inside = {"en": {True: "inside", False: "outside"}, "fr": {True: "à l’intérieur de", False: "à l’extérieur de"}}[lang]
            t4 = {"en": f"The later disclosed actual of {act} ({_form(sA, lang)} filed {sA['filed_at']}, accession {sA['accession']}) lies {inside[cO['contains']]} the original range and {inside[cR['contains']]} the revised range.",
                  "fr": f"Le résultat réalisé déclaré ultérieurement, {act} ({_form(sA, lang)} déposé le {sA['filed_at']}, numéro {sA['accession']}), se situe {inside[cO['contains']]} la fourchette initiale et {inside[cR['contains']]} la fourchette révisée."}[lang]
            r.sentence(t4, role="computed_statement", claim=_claim_ref(c, vR["version_id"]), evidence=[_src_ev(c, sA), {"kind": "outcome", "ref": c["claim_id"], "digest": out["outcome_digest"]}, _calc_ev(cO), _calc_ev(cR)],
                       calculation={"calculator": finance.CALCULATOR, "kind": "containment_pair", "original": cO, "revised": cR, "record_id": contracts.digest({"o": cO["record_id"], "r": cR["record_id"]})},
                       support="SUPPORTED", method="registered_arithmetic/1", limits="containment is inclusive (low ≤ actual ≤ high) within one financial scope",
                       protected=[("actual", act), ("accession", sA["accession"])])
        else:
            code = cR["result"] if cR["result"] not in ("IN_RANGE", "OUT_OF_RANGE") else cO["result"]
            t4 = {"en": f"A disclosed figure of {act} is recorded, but it is not comparable with the guidance ({code}); no containment result is stated.",
                  "fr": f"Un chiffre déclaré de {act} est consigné, mais il n’est pas comparable aux prévisions ({code}) ; aucun résultat d’appartenance n’est énoncé."}[lang]
            r.sentence(t4, role="computed_statement", claim=_claim_ref(c, vR["version_id"]), evidence=[_src_ev(c, sA), _calc_ev(cO), _calc_ev(cR)],
                       calculation={"calculator": finance.CALCULATOR, "kind": "containment_pair", "original": cO, "revised": cR, "record_id": contracts.digest({"o": cO["record_id"], "r": cR["record_id"]})},
                       support="SUPPORTED", method="registered_arithmetic/1", limits="an unresolved comparability state is reported as such; nothing is substituted", protected=[("actual", act), ("code", code)])
    else:
        t4 = {"en": "No comparable outcome has been recorded for this period; the comparison with an actual figure remains pending.",
              "fr": "Aucun résultat comparable n’a été consigné pour cette période ; la comparaison avec un chiffre réalisé reste en attente."}[lang]
        r.sentence(t4, role="computed_statement", claim=_claim_ref(c, vR["version_id"]), evidence=[_ver_ev(c, vR["version_id"])], calculation={"calculator": finance.CALCULATOR, "kind": "pending", "result": "PENDING_OUTCOME", "record_id": contracts.digest({"pending": c["claim_id"]})},
                   support="SUPPORTED", method="registered_arithmetic/1", limits="PENDING_OUTCOME is a real state, never replaced by zero")
    t5 = {"en": "That the actual falls inside both ranges — or that they agree in any way — does not by itself establish improved forecast accuracy, forecasting skill or causation.",
          "fr": "Le fait que le résultat se situe dans les deux fourchettes — ou qu’elles concordent de quelque manière — n’établit pas en soi une meilleure précision des prévisions, une compétence prévisionnelle ou une causalité."}[lang]
    r.sentence(t5, role="analyst_interpretation", claim=_claim_ref(c, vR["version_id"]), evidence=[_calc_ev(g)], calculation=None,
               support="SUPPORTED", method="method_statement/1", limits="restates the calculator's declared no-inference rule; it asserts nothing about the issuer")


def numerical_comparison(r: Render, c: dict) -> None:
    lang = r.lang
    vO = _ver(c, c["original_effective_version"]); clO = vO["claim"]; sO = clO["source"]
    if not c["revised_versions"]:
        raise ContractError(f"numerical_comparison needs a REVISED version of {c['claim_id']}")
    vR = _ver(c, c["revised_versions"][-1]); clR = vR["claim"]
    cmp = finance.comparison_record(clO, clR); v8 = cmp["v8_comparison"]
    cur, scale = clO["currency"], clO["scale_as_stated"]; word = finance.SCALE_WORD[lang][scale]
    r.heading({"en": "Numerical comparison of the two ranges", "fr": "Comparaison numérique des deux fourchettes"}[lang])
    if v8["result"] != "COMPARABLE":
        t = {"en": f"The two versions are not comparable ({'; '.join(x['reason'] for x in v8['reasons'])}); no numerical comparison is stated.",
             "fr": f"Les deux versions ne sont pas comparables ({'; '.join(x['reason'] for x in v8['reasons'])}) ; aucune comparaison numérique n’est énoncée."}[lang]
        r.sentence(t, role="computed_statement", claim=_claim_ref(c, vR["version_id"]), evidence=[_calc_ev(cmp)], calculation=cmp, support="SUPPORTED", method="registered_arithmetic/1", limits="INCOMPARABLE is reported, not bridged")
        return
    direction = {"LOWERED": ("lowered", "abaissée"), "RAISED": ("raised", "relevée"), "NARROWED": ("narrowed", "resserrée"), "WIDENED": ("widened", "élargie"), "UNCHANGED": ("unchanged", "inchangée"), "SHIFTED": ("shifted", "déplacée")}[v8["direction"]]
    ld, hd = signed(v8["low_delta"], scale, lang), signed(v8["high_delta"], scale, lang)
    wa, wb = fmt_number(finance.in_scale(money.parse_amount(v8["width_a"]), scale), lang), fmt_number(finance.in_scale(money.parse_amount(v8["width_b"]), scale), lang)
    t1 = {"en": f"Compared with the original range, the revised range is {direction[0]}: the low end moved by {ld} {word} and the high end by {hd} {word}; the width went from {wa} to {wb} {word}.",
          "fr": f"Par rapport à la fourchette initiale, la fourchette révisée est {direction[1]} : la borne basse a varié de {ld}{NBSP}{word} et la borne haute de {hd}{NBSP}{word} ; la largeur est passée de {wa} à {wb}{NBSP}{word}."}[lang]
    r.sentence(t1, role="computed_statement", claim=_claim_ref(c, vR["version_id"]), evidence=[_ver_ev(c, vO["version_id"]), _ver_ev(c, vR["version_id"]), _calc_ev(cmp)], calculation=cmp,
               support="SUPPORTED", method="registered_arithmetic/1", limits="a structural comparison of two stated ranges; explanatory notes are not causal proof",
               protected=[("low_delta", ld), ("high_delta", hd), ("width_a", wa), ("width_b", wb)])
    if v8["overlap"]:
        ov = amount_range(v8["overlap"]["low"], v8["overlap"]["high"], scale, cur, lang)
        t2 = {"en": f"The two ranges overlap between {ov}.", "fr": f"Les deux fourchettes se chevauchent entre {ov}."}[lang]
    else:
        t2 = {"en": "The two ranges do not overlap.", "fr": "Les deux fourchettes ne se chevauchent pas."}[lang]
    r.sentence(t2, role="computed_statement", claim=_claim_ref(c, vR["version_id"]), evidence=[_calc_ev(cmp)], calculation=cmp, support="SUPPORTED", method="registered_arithmetic/1", limits="overlap = [max(lows), min(highs)]",
               protected=[("overlap", ov)] if v8["overlap"] else [])
    # direct quotation of the original source, only when its rights let the bytes travel
    if sO["rights"] in contracts.BUNDLE_RIGHTS:
        q = sO["excerpt"]
        if len(q.encode("utf-8")) > MAX_QUOTE_BYTES:                       # quote a prefix that still matches the source bytes exactly
            cut = q.encode("utf-8")[:MAX_QUOTE_BYTES].decode("utf-8", "ignore").rstrip()
            q = cut
        quoted = {"en": f"The original filing states: “{q}”", "fr": f"Le dépôt initial indique : «{NNBSP}{q}{NNBSP}»"}[lang]
        r.sentence(quoted, role="direct_quotation", claim=_claim_ref(c, vO["version_id"]), evidence=[_src_ev(c, sO)], calculation=None, support="SUPPORTED", method="exact_quotation_match/1",
                   limits="the quoted bytes are a verbatim substring of the registered excerpt; a quotation binds bytes, it does not authenticate the publisher", protected=[("quotation", q)])
    else:
        t3 = {"en": f"The original filing's wording is registered (rights {sO['rights']}); its excerpt is not reproduced here.",
              "fr": f"La formulation du dépôt initial est enregistrée (droits {sO['rights']}) ; son extrait n’est pas reproduit ici."}[lang]
        r.sentence(t3, role="analyst_interpretation", claim=_claim_ref(c, vO["version_id"]), evidence=[_src_ev(c, sO)], calculation=None, support="SUPPORTED", method="method_statement/1", limits="rights rule of the export layer")


def unresolved_interpretation(r: Render, c: dict) -> None:
    lang = r.lang
    vid = c["revised_versions"][-1] if c["revised_versions"] else c["current_version"]
    r.heading({"en": "An interpretation that remains unresolved", "fr": "Une interprétation qui reste non résolue"}[lang])
    t1 = {"en": "Management cut guidance because demand collapsed.", "fr": "La direction a abaissé ses prévisions parce que la demande s’est effondrée."}[lang]
    r.sentence(t1, role="unresolved_claim", claim=_claim_ref(c, vid), evidence=[], calculation=None, support="UNRESOLVED", method="none",
               limits="a causal statement; no source passage attributing the revision to demand is recorded; a citation, a signature or a positive watermark report cannot make it supported")
    t2 = {"en": "Evidence that would support or refute it: a source passage in which management attributes the revision to demand, registered with its availability time.",
          "fr": "Éléments qui l’appuieraient ou la réfuteraient : un passage de source dans lequel la direction attribue la révision à la demande, enregistré avec son heure de disponibilité."}[lang]
    r.sentence(t2, role="analyst_interpretation", claim=_claim_ref(c, vid), evidence=[], calculation=None, support="NOT_ASSESSED", method="none",
               limits="a research note on what evidence is missing; it asserts nothing about the issuer")


RENDERERS = {"guidance_change": guidance_change, "numerical_comparison": numerical_comparison, "unresolved_interpretation": unresolved_interpretation}


def render(snapshot: dict, claim_id: str, sections: list[str], lang: str) -> tuple[bytes, list[dict], dict]:
    """Render the chosen sections for one claim of the snapshot. Returns (bytes, spans, receipt-ish production record)."""
    if claim_id not in snapshot["claims"]:
        raise ContractError(f"claim {claim_id!r} is not in the snapshot")
    bad = [s for s in sections if s not in TEMPLATES]
    if bad or not sections:
        raise ContractError(f"sections must be a non-empty subset of {list(TEMPLATES)} (got {sections})")
    r = Render(lang); c = snapshot["claims"][claim_id]
    r.heading({"en": f"Research brief — {c['claim_id']}", "fr": f"Note de recherche — {c['claim_id']}"}[lang])
    for s in sections:
        RENDERERS[s](r, c)
    data, spans = r.finish()
    production = {"renderer": RENDERER, "template": "+".join(sections), "language": lang, "claim_id": claim_id, "snapshot_digest": snapshot["snapshot_digest"],
                  "deterministic": True, "settings": {"sections": sections, "language": lang}, "sections": r.sections}
    return data, spans, production

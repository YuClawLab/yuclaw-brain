"""Bilingual strings of the v9 brief surfaces (interface labels, explanations, dimension words).

Identifiers, command syntax, schema values, status words (SUPPORTED, NOT_DETECTED, …) and the official mission/vision
sentences are never translated: they are what a user must type or match. Explanatory prose is. The v8 workbench's own
pages stay English; `legacy_note` says so where a v9 page shows beside them.
"""
from __future__ import annotations

LANGS = ("en", "fr")
_S = {
    # --- page titles and navigation
    "brief.title": ("Research briefs", "Notes de recherche"),
    "brief.nav": ("Briefs", "Notes de recherche"),
    "brief.new": ("Create a brief", "Créer une note"),
    "brief.open": ("Open", "Ouvrir"),
    "brief.list.empty": ("No brief yet. Create one from a template over the claims of this workspace, or import a draft.", "Aucune note pour l’instant. Créez-en une à partir d’un modèle sur les engagements de cet espace, ou importez un brouillon."),
    "brief.inspect": ("Sentence inspector", "Inspecteur de phrase"),
    "brief.edit": ("Edit the text", "Modifier le texte"),
    "brief.translate": ("Add a translation", "Ajouter une traduction"),
    "brief.import": ("Import a draft", "Importer un brouillon"),
    "brief.reports": ("Provenance records", "Enregistrements de provenance"),
    "brief.export": ("Export", "Exporter"),
    "brief.verify": ("Verify a brief packet", "Vérifier un paquet de note"),
    "brief.review": ("Review items", "Éléments à examiner"),
    "brief.versions": ("Versions", "Versions"),
    "brief.language": ("Language", "Langue"),
    "brief.template": ("Template", "Modèle"),
    "brief.sections": ("Sections", "Sections"),
    "brief.claims": ("Claims", "Engagements"),
    "brief.legacy_note": ("The surrounding workbench pages (steps 1–7, modules) keep their English labels; this page's explanations follow your language choice.",
                          "Les pages environnantes de l’atelier (étapes 1 à 7, modules) conservent leurs libellés anglais ; les explications de cette page suivent votre choix de langue."),
    "brief.not_advice": ("Research and education only. Not investment advice.", "Recherche et formation uniquement. Aucun conseil en placement."),
    # --- the five dimensions, kept apart on every surface
    "dim.byte_integrity": ("Byte integrity", "Intégrité des octets"),
    "dim.recorded_origin": ("Recorded origin", "Origine consignée"),
    "dim.issuer_trust": ("Issuer trust", "Confiance envers l’émetteur"),
    "dim.substantive_support": ("Substantive support", "Appui sur le fond"),
    "dim.time_scope": ("Time scope", "Portée temporelle"),
    "dim.detector": ("Detector report", "Rapport de détecteur"),
    "dim.note": ("These five answers are independent. None is a confidence percentage, and no overall score is computed from them.",
                 "Ces cinq réponses sont indépendantes. Aucune n’est un pourcentage de confiance et aucun score global n’en est dérivé."),
    # --- inspector areas
    "area.sources": ("Sources and calculations", "Sources et calculs"),
    "area.origin": ("How the text was produced", "Comment le texte a été produit"),
    "area.changes": ("Changes", "Modifications"),
    "area.checks": ("Checks", "Vérifications"),
    # --- status words explained (the codes stay English)
    "support.SUPPORTED": ("Supported by a deterministic check (exact quotation or registered arithmetic).", "Appuyé par une vérification déterministe (citation exacte ou calcul enregistré)."),
    "support.ATTRIBUTED": ("Attributed support: an assessor asserted it; not reproduced deterministically here.", "Appui attribué : un évaluateur l’a affirmé ; non reproduit de manière déterministe ici."),
    "support.UNRESOLVED": ("Unresolved: no evidence supporting this statement is recorded.", "Non résolu : aucun élément probant appuyant cet énoncé n’est consigné."),
    "support.CONTRADICTED": ("Contradicted by recorded evidence.", "Contredit par des éléments probants consignés."),
    "support.NOT_ASSESSED": ("Not assessed.", "Non évalué."),
    "support.INVALIDATED": ("Invalidated: the text or a protected fact changed after the check; the earlier support does not carry over.", "Invalidé : le texte ou un fait protégé a changé après la vérification ; l’appui antérieur ne se transmet pas."),
    "label.generation_record": ("Generation record available", "Journal de génération disponible"),
    "label.generation_record.none": ("No generation record", "Aucun journal de génération"),
    "label.watermark.unavailable": ("Watermark check unavailable", "Vérification du filigrane indisponible"),
    "label.watermark.not_requested": ("Watermark check not requested", "Vérification du filigrane non demandée"),
    "label.watermark.completed": ("Watermark check completed", "Vérification du filigrane effectuée"),
    "label.evidence.incomplete": ("Evidence incomplete", "Éléments probants incomplets"),
    "label.evidence.complete": ("Evidence bound", "Éléments probants liés"),
    "label.review.needed": ("Review needed", "Examen requis"),
    "label.integrity.verified": ("Bytes verified", "Octets vérifiés"),
    "label.integrity.failed": ("Byte binding failed", "Liaison des octets en échec"),
    "label.incomplete": ("Incomplete record (prepared, not committed)", "Enregistrement incomplet (préparé, non validé)"),
    "label.later_information": ("Later information exists", "Des informations ultérieures existent"),
    "label.snapshot_current": ("No later information recorded", "Aucune information ultérieure consignée"),
    "label.signature.none": ("No signature", "Aucune signature"),
    "label.trust.unknown": ("Valid signature, unknown signer", "Signature valide, signataire inconnu"),
    "label.trust.trusted": ("Trusted signer (this workspace's policy)", "Signataire de confiance (politique de cet espace)"),
    "label.trust.revoked": ("Signer revoked here", "Signataire révoqué ici"),
    "label.signature.invalid": ("Signature invalid", "Signature invalide"),
    "label.calibration.NOT_ESTABLISHED": ("Calibration not established", "Étalonnage non établi"),
    "label.calibration.OUT_OF_SCOPE": ("Calibration out of scope", "Étalonnage hors périmètre"),
    "label.calibration.APPLICABLE": ("Calibration applicable (per the enrolled record)", "Étalonnage applicable (selon l’enregistrement inscrit)"),
    "label.provider_reported": ("Provider-reported result; not reproduced or calibrated here", "Résultat déclaré par le fournisseur ; ni reproduit ni étalonné ici"),
    # --- roles
    "role.direct_quotation": ("Direct quotation", "Citation directe"),
    "role.computed_statement": ("Computed statement", "Énoncé calculé"),
    "role.attributed_source_statement": ("Attributed source statement", "Énoncé attribué à une source"),
    "role.analyst_interpretation": ("Analyst interpretation", "Interprétation de l’analyste"),
    "role.generated_commentary": ("Generated commentary", "Commentaire généré"),
    "role.unresolved_claim": ("Unresolved claim", "Affirmation non résolue"),
    "role.note": ("A role describes the statement's function; it does not establish correctness.", "Un rôle décrit la fonction de l’énoncé ; il n’en établit pas l’exactitude."),
    # --- coverage and explanations
    "coverage": ("{mapped} of {total} identified statements have mapped evidence; extraction completeness is not established.",
                 "{mapped} des {total} énoncés identifiés ont des éléments probants associés ; l’exhaustivité de l’extraction n’est pas établie."),
    "never.not_detected": ("NOT_DETECTED does not prove human authorship.", "NOT_DETECTED ne prouve pas une rédaction humaine."),
    "never.percentage": ("A detector score is not the percentage of text written by AI.", "Un score de détecteur n’est pas le pourcentage de texte écrit par une IA."),
    "never.identity": ("A watermark does not establish identity, ownership, responsibility or factual accuracy.", "Un filigrane n’établit ni identité, ni propriété, ni responsabilité, ni exactitude factuelle."),
    "never.timestamp": ("A local receipt is not legal compliance and not an independently anchored timestamp.", "Un reçu local n’est ni une conformité juridique ni un horodatage ancré de manière indépendante."),
    # --- forms
    "form.text": ("Text", "Texte"),
    "form.reason": ("Reason", "Motif"),
    "form.actor": ("Your label (attribution, not authentication)", "Votre libellé (attribution, pas authentification)"),
    "form.file": ("File", "Fichier"),
    "form.submit": ("Submit", "Soumettre"),
    "form.create": ("Create", "Créer"),
    "form.save_version": ("Save as a new version", "Enregistrer comme nouvelle version"),
    "form.translation_of": ("Translation provenance (who or what produced it)", "Provenance de la traduction (qui ou quoi l’a produite)"),
    "form.build_packet": ("Build the packet", "Construire le paquet"),
    "form.resolve": ("Record a resolution", "Consigner une résolution"),
    "form.link": ("Link a span to a claim", "Lier un passage à un engagement"),
    "form.start_byte": ("Start (UTF-8 byte offset)", "Début (décalage en octets UTF-8)"),
    "form.end_byte": ("End (UTF-8 byte offset, exclusive)", "Fin (décalage en octets UTF-8, exclu)"),
    "form.role": ("Role", "Rôle"),
    "form.claim_ref": ("Claim and version", "Engagement et version"),
    "form.kind": ("Record kind", "Type d’enregistrement"),
    # --- misc
    "word.version": ("Version", "Version"),
    "word.parent": ("Parent", "Parent"),
    "word.created": ("Recorded", "Consigné"),
    "word.statement": ("Statement", "Énoncé"),
    "word.result": ("Result", "Résultat"),
    "word.unknown": ("unknown", "inconnu"),
    "word.none": ("none", "aucun"),
    "word.download": ("Download", "Télécharger"),
    "word.html": ("Readable brief (HTML)", "Note lisible (HTML)"),
    "word.packet": ("Verification packet (zip)", "Paquet de vérification (zip)"),
    "word.appendix": ("Methods and limitations appendix", "Annexe méthodes et limites"),
    "word.measurements": ("Operation measurements", "Mesures des opérations"),
}


def t(key: str, lang: str = "en", **kw) -> str:
    pair = _S.get(key)
    if pair is None:
        return key
    s = pair[1] if lang == "fr" else pair[0]
    return s.format(**kw) if kw else s


def all_keys() -> list[str]:
    return sorted(_S)


def coverage_sentence(mapped: int, total: int, lang: str) -> str:
    return t("coverage", lang, mapped=mapped, total=total)

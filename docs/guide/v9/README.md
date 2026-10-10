# YUCLAW v9 — Research briefs · Notes de recherche

Research and education only; not investment advice. · Recherche et formation uniquement ; aucun conseil en placement.
Mission: Make financial AI accountable to evidence. · Vision: Become the Science Trust Layer for Financial AI.

**EN.** YUCLAW v9 adds *briefs* to the v8 workbench: short pieces of financial research text whose individual sentences can be
inspected one by one — which exact source passage, which frozen v8 claim version and which registered calculation each one
rests on, how the text was produced (template, import, edit, translation), what changed since, and which checks could or
could not be run. Everything runs locally beside the v8 workbench, in a separate append-only sidecar inside the same
workspace folder; no API key, model download or hosted service is involved. Every number in the packaged example is
fictional (issuer "Fictional Example Corp", fixture `001_base`).

**FR.** YUCLAW v9 ajoute des *notes* (briefs) à l’atelier v8 : de courts textes de recherche financière dont chaque phrase
peut être inspectée une à une — sur quel passage exact de source, quelle version figée d’engagement v8 et quel calcul
enregistré elle repose, comment le texte a été produit (modèle, import, modification, traduction), ce qui a changé depuis
et quelles vérifications ont pu ou non être effectuées. Tout s’exécute localement, à côté de l’atelier v8, dans un journal
annexe (sidecar) distinct et en ajout seul, à l’intérieur du même dossier d’espace de travail ; aucune clé d’API, aucun
téléchargement de modèle ni service hébergé n’intervient. Tous les chiffres de l’exemple fourni sont fictifs (émetteur
« Fictional Example Corp », fixture `001_base`).

## Software covered · Logiciel couvert

| | |
|---|---|
| Package version · Version du paquet | **9.0.0** (the v9 brief layer ships inside the `yuclaw` package; the layer identifies itself as `v9.brief/1`) |
| Branch · Branche | prepared on `codex/v9-integration` for 9.0.0 (October 2026) · préparé sur `codex/v9-integration` pour 9.0.0 (octobre 2026) |
| Status · Statut | Describes YUCLAW 9.0.0 as frozen for release; the CHANGELOG entry `[9.0.0]` and the GitHub release state whether it is published. · Décrit YUCLAW 9.0.0 tel que figé pour la publication ; l’entrée `[9.0.0]` du CHANGELOG et la publication GitHub indiquent si elle est publiée. |
| Guide edition · Édition du guide | 1.1 — 10 October 2026 · 10 octobre 2026 (compatibility measured against the published 8.0.1 client; see MIGRATION.md §3) |

## Documents

| Document | Contents · Contenu |
|---|---|
| [GUIDE_EN.md](GUIDE_EN.md) | Practical guide (English): installation, the complete fictional example on the command line and in the browser, sentence inspection, imported drafts and span links, edits and translations, review items, provenance records, exports and verification, measurements, troubleshooting. |
| [GUIDE_FR.md](GUIDE_FR.md) | Le même guide en français (mêmes commandes, mêmes identifiants, mêmes mots d’état). |
| [SCHEMA.md](SCHEMA.md) | Developer reference: the eleven record contracts (`yuclaw.artifact-record/1` … `yuclaw.brief-packet/1`), closed vocabularies, byte semantics, allowed report combinations, the signed-body rule, the sidecar line format, the packet manifest, measurement definitions and the reducer's five dimensions. |
| [MIGRATION.md](MIGRATION.md) | Migration and downgrade note: a v8 workspace needs no migration; what v9 creates, what it never touches, what is lost when v9 is removed, recovery semantics. |

## Quick start · Démarrage rapide

The packaged quick start is printed by the software itself (`--lang fr` for French); the guides above expand it.
Le démarrage rapide fourni avec le logiciel s’imprime ainsi (`--lang fr` pour le français) ; les guides ci-dessus le développent.

```
yuclaw workbench brief guide
yuclaw workbench brief guide --lang fr
yuclaw workbench brief selftest
yuclaw workbench brief example --workspace ~/yuclaw-workspaces/research
```

`yuclaw workbench brief …` and `python -m v9.brief …` are the same program. · `yuclaw workbench brief …` et `python -m v9.brief …` sont le même programme.

## Implemented locally in the 9.0 candidate vs deferred · Mis en œuvre localement vs différé

| Implemented in 9.0 (runs locally, no network) · Mis en œuvre dans 9.0 | Deferred — explicitly NOT in 9.0 · Différé — explicitement ABSENT de 9.0 |
|---|---|
| Template briefs from the three deterministic templates (`guidance_change`, `numerical_comparison`, `unresolved_interpretation`) · Notes issues des trois modèles déterministes | Live provider generation or detection connectors (the origin kind `connector_observed` exists in the schema; no connector is configured or shipped) · Connecteurs de génération ou de détection auprès de fournisseurs en direct |
| Imported drafts (hand-written or AI-assisted text, stored as data) · Brouillons importés | A local entropy-controlled sampler or open-weight model integration · Un échantillonneur local à entropie contrôlée ou l’intégration d’un modèle à poids ouverts |
| Span links by UTF-8 byte offsets, with roles · Liens de passages par décalages en octets UTF-8, avec rôles | Detector calibration campaigns (a `CalibrationRecord/1` can be imported; none is produced or measured by YUCLAW) · Campagnes d’étalonnage de détecteurs |
| Edits (parent preserved, exact-bytes span mapping, protected facts) · Modifications | |
| Translations, deterministic (template re-render) and entered (recorded, not certified) · Traductions déterministes et saisies | |
| Dependency review against the live v8 state (source availability corrections, amendments, withdrawals, outcomes) · Examen des dépendances | |
| Import of generation receipts, detector reports and calibration records with receiver-side trust roots · Import de reçus, rapports et enregistrements d’étalonnage avec racines de confiance côté destinataire | |
| Packet export (`yuclaw.brief-packet/1`) and offline verification in a fresh workspace · Export de paquets et vérification hors ligne | |
| Operation measurements with stated definitions · Mesures des opérations avec leurs définitions | |

Two further exclusions, stated so that nobody looks for them · Deux exclusions supplémentaires :

- **No human comprehension study.** Nothing in 9.0 measures whether readers understand the five dimensions better; the
  measurements count software attempts and durations only. · **Aucune étude de compréhension humaine.**
- **No backup/restore feature.** The sidecar is ordinary files inside the workspace folder; copy the folder with your
  usual tools. v9 adds no backup command and restores nothing. · **Aucune fonction de sauvegarde/restauration.**

## Where the behaviour is checked · Où le comportement est vérifié

- `yuclaw workbench brief selftest` — 17 checks of the installed package in a temporary fictional workspace.
- `tests/test_v9_brief_engine.py` (acceptance letters A–M) and `tests/test_v9_brief_web.py` in the repository checkout.

Related: the v8 guide index at [`docs/guide/v8/README.md`](../v8/README.md) describes the released 8.0.1 workbench that v9 sits beside.

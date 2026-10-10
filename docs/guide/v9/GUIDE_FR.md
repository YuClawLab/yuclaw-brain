# YUCLAW v9 — Notes de recherche avec assistance IA traçable : guide d’utilisation

Recherche et formation uniquement. Aucun conseil en placement.
Mission : Make financial AI accountable to evidence. (Rendre l’IA financière redevable envers les éléments probants.)
Vision : Become the Science Trust Layer for Financial AI. (Devenir la couche de confiance scientifique de l’IA financière.)

Logiciel couvert : YUCLAW **9.0.0** (couche `v9.brief/1`), tel que figé pour la publication sur la branche `codex/v9-integration`
en octobre 2026. L’entrée `[9.0.0]` du CHANGELOG et la publication GitHub indiquent si elle est publiée ; ce guide décrit le comportement figé. Chaque commande et chaque extrait de sortie de ce guide a été exécuté sur ce dépôt dans un espace de
travail jetable. **Toutes les données montrées sont fictives** : l’exemple fourni `001_base` décrit « Fictional Example
Corp (ZZFX) », des numéros de dépôt de la forme `0000000000-26-00000x` et des montants inventés pour l’exemple. Les
identifiants tels que `brf-4625e1016814`, `bpk-a3ff4d970a5e16c3`, les empreintes et les horodatages diffèrent à chaque
exécution ; les mots d’état, non.

Les commandes, identifiants, valeurs de schéma et mots d’état restent en anglais : ce sont ce que vous tapez ou faites
correspondre ; ils sont expliqués en français au fil du texte. `yuclaw workbench brief …` et `python -m v9.brief …` sont le
même programme ; ce guide écrit `yuclaw workbench brief`. Les blocs de commandes et de sorties sont identiques à ceux du
guide anglais ; les longs chemins d’espace de travail y sont abrégés en `~/yuclaw-workspaces/…`.

---

## 1. Ce qu’est une note, et ce qui s’exécute où

Une **note** (brief) est un court texte de recherche financière dont chaque phrase peut être inspectée : sur quel passage
exact de source, quelle version figée d’engagement v8 et quel calcul enregistré elle repose, comment le texte a été produit,
ce qui a changé depuis, et quelles vérifications ont pu ou non être effectuées.

Tout ce que décrit ce guide s’exécute **sur votre machine**, dans un dossier d’espace de travail que vous nommez :

| S’exécute localement (v9) | Fourni par le site public et le dépôt |
|---|---|
| Composer des notes à partir de modèles sur les engagements figés de votre espace v8 | Le paquet `yuclaw` (versions PyPI à partir de 9.0.0) |
| Importer des brouillons, lier des phrases à des engagements, modifier, traduire | La documentation, les notes de version, le code source |
| Importer des enregistrements de provenance et tenir vos propres racines de confiance | Rien de votre espace, de vos notes ou de vos paquets : aucune note n’est envoyée nulle part |
| Construire des paquets de vérification et les vérifier dans un espace vierge | |
| Les pages du navigateur à `http://127.0.0.1:8765/brief` (boucle locale seulement) | |

Aucune clé d’API, aucun téléchargement de modèle ni service hébergé n’est nécessaire pour ce qui suit. Rien dans v9 ne
contacte un fournisseur de traduction ou de génération ; une traduction que vous fournissez est consignée comme *saisie*,
avec la provenance que vous déclarez, et n’est pas certifiée.

---

## 2. Installation et prérequis

- Python **3.10 ou plus récent** (`requires-python = ">=3.10"` ; ce guide a été exécuté avec 3.12).
- Le paquet `yuclaw`. La couche de notes v9 fait partie du même paquet que l’atelier v8 et **exige l’atelier v8 dans la même
  installation** : une note est composée sur un espace de travail v8 (`workspace.json`, `commitments.jsonl`) et lit ses
  engagements figés. La dépendance déclarée `cryptography` est nécessaire pour vérifier les enregistrements de provenance
  signés (section 9).

```
python3 -m venv ~/yuclaw-venv && source ~/yuclaw-venv/bin/activate
python -m pip install yuclaw
yuclaw workbench brief --help
yuclaw workbench brief selftest          # checks this installation in a temporary fictional workspace
```

Tant que 9.0 n’est pas publiée, les mêmes commandes s’exécutent depuis un dépôt cloné de la branche avec
`cd <checkout> && PYTHONPATH=. python3 -m v9.brief …`.

`selftest` crée un espace temporaire, exécute le parcours complet puis le supprime. Fin attendue (17 vérifications) :

```
  [ok] packet verifies SUCCESS in a fresh workspace
  [ok] packet carries no private material or local paths
  [ok] one-byte tampering is detected
  [ok] v8 journal untouched by v9 writes
  [ok] relative change rounding rule stated
  not run here: the repository test suite (developers: python -m pytest tests/test_v9_*.py), the browser journeys, live provider connectors (none exist in 9.0), real sources
[brief selftest] PASS — 17/17 checks
```

Le démarrage rapide fourni s’imprime avec `yuclaw workbench brief guide` (`--lang fr` pour le français).

### Codes de sortie

| Code | Signification |
|---|---|
| 0 | succès |
| 1 | l’opération a été exécutée et le résultat est négatif : `verify` MISMATCH, `show --strict` avec des éléments ouverts ou des énoncés non appuyés, `E_OP_CONFLICT` |
| 2 | refus de contrat ou erreur d’usage (`refused: …`) ; rien n’a été écrit |
| 3 | environnement ou état du stockage non pris en charge : `verify` UNSUPPORTED, `E_TORN_TAIL`, `E_WORKSPACE_MISMATCH`, `E_NO_SIDECAR` |

---

## 3. L’exemple fictif complet

### 3.1 En ligne de commande

```
yuclaw workbench brief example --workspace ~/yuclaw-workspaces/research
```

`example` crée l’espace si nécessaire, charge l’exemple fictif `001_base` (idempotent) et compose une note à partir des trois
modèles. La sortie liste chaque énoncé avec son rôle et ses cinq réponses indépendantes :

```
claim ZZFX-FY2026-REV-GUIDE--FIX-COMMIT-001-base
brf-4625e1016814 B1 (en) — Research brief — ZZFX-FY2026-REV-GUIDE--FIX-COMMIT-001-base
status COMPLETE · Evidence bound · snapshot f618f796af628a55… at v8 tip 5b841dfc6e49…
9 of 10 identified statements have mapped evidence; extraction completeness is not established.

[ 1] attributed_source_statement  SUPPORTED    bytes VERIFIED No later information recorded · Watermark check not requested
     Fictional Example Corp (ZZFX) stated revenue guidance for FY2026 (GAAP) of USD 110–120 million in its 8-K (fictional) filed 2026-02-10 (accession 0000000000-26-000001).
[ 2] attributed_source_statement  SUPPORTED    bytes VERIFIED No later information recorded · Watermark check not requested
     In its 8-K (fictional) filed 2026-05-12 (accession 0000000000-26-000002), the company revised that guidance to USD 105–115 million.
[ 3] computed_statement           SUPPORTED    bytes VERIFIED No later information recorded · Watermark check not requested
     The midpoint moved from USD 115 million to USD 110 million: a change of -5 million (-4.35%, computed as -5 / 115 × 100 and rounded half-even to two decimals, so approximately).
[ 4] computed_statement           SUPPORTED    bytes VERIFIED No later information recorded · Watermark check not requested
     The later disclosed actual of USD 112 million (10-K (fictional) filed 2027-02-09, accession 0000000000-26-000003) lies inside the original range and inside the revised range.
[ 5] analyst_interpretation       SUPPORTED    bytes VERIFIED No later information recorded · Watermark check not requested
     That the actual falls inside both ranges — or that they agree in any way — does not by itself establish improved forecast accuracy, forecasting skill or causation.
[ 6] computed_statement           SUPPORTED    bytes VERIFIED No later information recorded · Watermark check not requested
     Compared with the original range, the revised range is lowered: the low end moved by -5 million and the high end by -5 million; the width went from 10 to 10 million.
[ 7] computed_statement           SUPPORTED    bytes VERIFIED No later information recorded · Watermark check not requested
     The two ranges overlap between USD 110–115 million.
[ 8] direct_quotation             SUPPORTED    bytes VERIFIED No later information recorded · Watermark check not requested
     The original filing states: “expects full-year 2026 revenue of $110 million to $120 million”
[ 9] unresolved_claim             UNRESOLVED   bytes VERIFIED No later information recorded · Watermark check not requested
     Management cut guidance because demand collapsed.
[10] analyst_interpretation       NOT_ASSESSED bytes VERIFIED No later information recorded · Watermark check not requested
     Evidence that would support or refute it: a source passage in which management attributes the revision to demand, registered with its availability time.

open review items: 0 · receipts: 1 · reports: 0 · versions: ['B1']
These five answers are independent. None is a confidence percentage, and no overall score is computed from them.
```

Chiffres fictifs, lus comme la note les énonce : prévisions initiales de 110–120 millions USD, révisées à 105–115 millions,
résultat ultérieur de 112 millions. Le point médian passe de 115 à 110 millions : −5 millions, environ −4,35 %
(−5 / 115 × 100, arrondi au pair le plus proche à deux décimales ; la fraction exacte −5 000 000 / 115 000 000 est conservée
dans l’enregistrement). Le résultat se situe dans les deux fourchettes — ce qui, dit la note elle-même, n’établit pas une
meilleure précision des prévisions. La phrase causale « Management cut guidance because demand collapsed. » (la direction a
abaissé ses prévisions parce que la demande s’est effondrée) reste **UNRESOLVED** (non résolue) : aucun élément probant
n’existe pour elle dans l’espace, et ni citation, ni signature, ni résultat de détecteur ne peut la rendre appuyée.

```
yuclaw workbench brief list --workspace ~/yuclaw-workspaces/research
```
```
brf-4625e1016814  B1   en     complete  Research brief — ZZFX-FY2026-REV-GUIDE--FIX-COMMIT-001-base  claims ['ZZFX-FY2026-REV-GUIDE--FIX-COMMIT-001-base']
```

Votre identifiant de note sera différent ; copiez-le depuis `list` dans les commandes qui suivent.

### 3.2 Dans le navigateur

Les pages v9 sont servies par le serveur de l’atelier v8, sur l’interface de boucle locale uniquement :

```
yuclaw workbench serve --workspace ~/yuclaw-workspaces/research
```

Ouvrez ensuite **http://127.0.0.1:8765/brief** (le port est 8765 sauf si vous passez `--port`). Routes :

| Route | Ce qu’elle affiche |
|---|---|
| `/brief` | les notes de l’espace, un formulaire pour créer une note à partir de modèles sur un engagement figé, un formulaire pour importer un brouillon |
| `/brief/<identifiant de note>` | une note : texte, énoncés avec leurs cinq dimensions, éléments à examiner, enregistrements de provenance, versions, et les formulaires modifier / traduire / lier / résoudre / importer un enregistrement / exporter |
| `/brief/<identifiant de note>?s=N` | la même page avec l’**inspecteur de phrase** ouvert sur l’énoncé N (quatre zones, section 4) |
| `/brief/<identifiant de note>/html` | la note lisible en HTML statique, en téléchargement (sans script) |
| `/brief/verify` | téléverser un paquet construit ailleurs et lire les résultats par vérification ; rien n’est importé |
| `/brief/trust` | les racines de confiance de cet espace pour les enregistrements de provenance signés : inscrire, révoquer |
| `…?lang=fr` | explications en français sur chacune de ces pages ; identifiants, commandes et mots d’état restent tels quels |

Les pages utilisent les protections du serveur v8 (liaison à la boucle locale, jeton CSRF, contrôle de l’en-tête Origin,
session). Tant qu’aucun principal n’est configuré, le propriétaire unique de l’espace peut écrire ; une fois des principaux
configurés, écrire exige l’une des capacités `admin`, `review` ou `submit`, et inscrire ou révoquer une racine de confiance
exige `admin`. Les pages v8 environnantes conservent leurs libellés anglais.

---

## 4. Inspecter une phrase : quatre zones, cinq dimensions

```
yuclaw workbench brief show --workspace ~/yuclaw-workspaces/research --brief brf-4625e1016814 --statement 3
```

```
Statement 3 [435:612] role computed_statement
  The midpoint moved from USD 115 million to USD 110 million: a change of -5 million (-4.35%, computed as -5 / 115 × 100 and rounded half-even to two decimals, so approximately).

1. Sources and calculations
   support: SUPPORTED — Supported by a deterministic check (exact quotation or registered arithmetic).
   method: registered_arithmetic/1 · assessor: v9.brief.templates/1
   limits: exact midpoints and difference; the percentage is rounded under the stated rule; agreement of the two ranges is not evidence of accuracy
   claim: {'claim_digest': 'ab1eb46f…', 'claim_id': 'ZZFX-FY2026-REV-GUIDE--FIX-COMMIT-001-base', 'version_id': 'R1'}
   evidence: claim_version ZZFX-FY2026-REV-GUIDE--FIX-COMMIT-001-base#V1 0db93c38ae7130d7
   evidence: claim_version ZZFX-FY2026-REV-GUIDE--FIX-COMMIT-001-base#R1 ab1eb46f659be7ce
   evidence: calculation guidance_change 0a85639ba3b482f7
   calculation: guidance_change — midpoint = (low + high) / 2 (exact); absolute_change = midpoint_revised - midpoint_original (exact); relative_change = absolute_change / midpoint_original * 100
     inputs: {"original_high": 120000000, "original_low": 110000000, "revised_high": 115000000, "revised_low": 105000000}
     midpoint_original: 115000000
     midpoint_revised: 110000000
     absolute_change: -5000000
     relative_change: {"approximate": true, "denominator": 115000000, "formula": "(new - old) / old * 100", "numerator": -5000000, "rounding": {"applies_to": "relative change in percent only; every amount, midpoint and difference is exact", "decimals": 2, "rule": "ROUND_HALF_EVEN"}, "value_percent": "-4.35"}
   recomputed now: {'outcome': 'VERIFIED', 'detail': None}
   protected slots: midpoint_original='USD 115 million', midpoint_revised='USD 110 million', absolute_change='-5', relative_change='-4.35%'

2. How the text was produced
   transform: template_render · implementation: v9.brief.templates/1 · renderer: v9.brief.templates/1 · template: guidance_change+numerical_comparison+unresolved_interpretation · deterministic: True
   receipts: ['1a91e646c83d499f…']
   explicit unknowns: {}

3. Changes
   No later information recorded · snapshot f618f796af628a55… · review items: []

4. Checks
   byte integrity: {'status': 'VERIFIED', 'recorded': '8a317102e2128261…', 'observed': '8a317102e2128261…'}
   issuer trust: no signed record on these bytes
   detector: {'reports': [], 'label': 'Watermark check not requested'}
   These five answers are independent. None is a confidence percentage, and no overall score is computed from them.
```

`[435:612]` sont les **décalages en octets UTF-8** de la phrase dans le texte de la note (intervalle demi-ouvert : l’octet
435 inclus, le 612 exclu). `--json` imprime la même vue sous forme de données ; l’inspecteur du navigateur (`?s=3`) montre
les mêmes quatre zones. Dans la sortie en ligne de commande, les titres des zones restent en anglais (« Sources and
calculations », « How the text was produced », « Changes », « Checks ») ; avec `--lang fr`, les explications des statuts
passent en français.

### Les quatre zones

| Zone | Contenu |
|---|---|
| **1 Sources and calculations** (sources et calculs) | statut d’appui, méthode, évaluateur et limites ; la version d’engagement ; chaque élément probant (extrait de source, version d’engagement, résultat, calcul) avec son empreinte ; le calcul enregistré avec ses entrées, sa formule, sa règle d’arrondi et le résultat *recomputed now* (recalculé maintenant) ; les champs protégés |
| **2 How the text was produced** (comment le texte a été produit) | la transformation (`template_render` / `import` / `edit` / `translate`), son implémentation, son caractère déterministe ou non, les reçus de génération liés à ces octets, et les **inconnues explicites** (chaque quantité qu’un reçu n’a pu exposer, avec la raison) |
| **3 Changes** (modifications) | si des informations ultérieures existent dans l’espace v8 depuis l’instantané, et les éléments à examiner sur les dépendances consignées de cet énoncé |
| **4 Checks** (vérifications) | intégrité des octets (empreinte consignée vs observée), confiance envers l’émetteur pour les enregistrements signés sur ces octets, rapports de détecteur couvrant ces octets |

### Les cinq dimensions indépendantes

Chaque énoncé porte cinq réponses, tenues séparées sur toutes les surfaces (ligne de commande, JSON, navigateur, HTML
exporté). **Il n’existe aucun score global, et aucune des cinq n’est un pourcentage de confiance.**

| Dimension | Mots affichés | Ce qu’elle répond | Ce qu’elle ne répond pas |
|---|---|---|---|
| **Byte integrity** (intégrité des octets) | `VERIFIED` · `FAILED` | les octets de la phrase correspondent-ils encore à l’empreinte consignée dans cette vue de texte exacte ? | rien sur la vérité ou la paternité |
| **Recorded origin** (origine consignée) | `template_render` · `import` · `edit` · `translate`, avec les inconnues explicites | comment le texte a été produit, avec quels réglages connus, et ce qui est inconnu | si le texte est exact |
| **Issuer trust** (confiance envers l’émetteur) | signature `VALID` / `INVALID` ; confiance `TRUSTED` / `UNKNOWN_SIGNER` / `REVOKED_ROOT` ; liaison `BOUND` / `MISMATCH` (enregistrements signés seulement) | qui a signé un enregistrement *sur ces octets*, selon la politique de cet espace | si l’énoncé est appuyé |
| **Substantive support** (appui sur le fond) | `SUPPORTED` · `ATTRIBUTED` · `UNRESOLVED` · `CONTRADICTED` · `NOT_ASSESSED` · `INVALIDATED` | si une vérification déterministe ou l’affirmation d’un évaluateur appuie l’énoncé, par quelle méthode et avec quelles limites | la paternité, l’authenticité de la source |
| **Time scope** (portée temporelle) | « No later information recorded » · « Later information exists » (+ éléments à examiner) | si l’espace v8 a consigné des informations ultérieures sur les dépendances de cet énoncé | si ces informations changent la conclusion |

Une sixième réponse, à part — le **rapport de détecteur** — dit si une vérification de filigrane ou de détecteur a été
demandée, indisponible ou effectuée sur ces octets exacts (section 9). Un signal positif de détecteur ou une signature
valide ne change jamais l’appui sur le fond ; un calcul correct n’authentifie jamais un fournisseur.

---

## 5. Brouillons importés et liens de passages

Un brouillon que vous avez rédigé vous-même, ou produit avec un assistant IA, s’importe comme nouvelle note. Ses phrases sont
repérées par un simple segmenteur de phrases et commencent **NOT_ASSESSED** (non évaluées) jusqu’à ce que vous les liiez.

```
printf 'Fictional Example Corp (ZZFX) guided to USD 110–120 million. Demand was weak in Q2 2026. The filing says “expects full-year 2026 revenue of $110 million to $120 million”. The filing says “expects revenue of $130 million”.\n' > ~/yuclaw-workspaces/draft-2.txt
yuclaw workbench brief import --workspace ~/yuclaw-workspaces/research --file ~/yuclaw-workspaces/draft-2.txt --claim ZZFX-FY2026-REV-GUIDE--FIX-COMMIT-001-base --provenance "hand-written draft for the guide (fictional)"
```
```
[brief] brf-fbc613defe63 B1 imported — 4 statements identified (v9.brief.compose/1 sentence segmentation (terminal punctuation and blank lines); not a claim extractor: it finds sentences, not claims, and misses nothing only in the sense that every byte belongs to some segment); link them with `link`
```

`--claim` nomme l’engagement v8 figé (ou les engagements, option répétable) dont traite le brouillon ; `--provenance` est
votre déclaration, en mots, de l’origine du texte ; `--receipt` peut joindre un JSON `GenerationReceipt/1` décrivant la
production du brouillon (section 9). Le texte est stocké comme donnée et jamais exécuté.

### Calculer les décalages en octets

Les passages sont adressés par **décalages en octets UTF-8, demi-ouverts** (`start` inclus, `end` exclu), jamais par les
décalages de caractères d’un éditeur. Un tiret demi-cadratin (–) ou un guillemet anglais (“) occupe 3 octets ; `é` en occupe
2. Calculez les décalages à partir du texte exact :

```
python3 -c "
text = open('$HOME/yuclaw-workspaces/draft-2.txt', encoding='utf-8').read()
for sentence in ['Fictional Example Corp (ZZFX) guided to USD 110–120 million.', 'Demand was weak in Q2 2026.', 'The filing says “expects full-year 2026 revenue of \$110 million to \$120 million”.', 'The filing says “expects revenue of \$130 million”.']:
    i = text.index(sentence); j = i + len(sentence)
    start = len(text[:i].encode('utf-8')); end = len(text[:j].encode('utf-8'))
    print(start, end, 'chars', i, j)
"
```
```
0 62 chars 0 60
63 90 chars 61 88
91 176 chars 89 170
177 231 chars 171 221
```

La première phrase compte 60 caractères mais 62 octets (le tiret demi-cadratin). `show --json` donne directement `start` et
`end` de chaque énoncé repéré, et `text_view.view_sha256` est l’empreinte du texte entier.

### Lier

```
yuclaw workbench brief link --workspace ~/yuclaw-workspaces/research --brief brf-fbc613defe63 --start 0 --end 62 --role attributed_source_statement --claim ZZFX-FY2026-REV-GUIDE--FIX-COMMIT-001-base --claim-version V1 --note "restates the original guidance"
yuclaw workbench brief link --workspace ~/yuclaw-workspaces/research --brief brf-fbc613defe63 --start 63 --end 90 --role unresolved_claim --note "no source passage about demand is registered"
yuclaw workbench brief link --workspace ~/yuclaw-workspaces/research --brief brf-fbc613defe63 --start 91 --end 176 --role direct_quotation --claim ZZFX-FY2026-REV-GUIDE--FIX-COMMIT-001-base --claim-version V1
yuclaw workbench brief link --workspace ~/yuclaw-workspaces/research --brief brf-fbc613defe63 --start 177 --end 231 --role direct_quotation --claim ZZFX-FY2026-REV-GUIDE--FIX-COMMIT-001-base --claim-version V1
```
```
[brief] span 0..62 → role attributed_source_statement, support ATTRIBUTED (assessor_assertion/1); the operator 'host-operator(cli)' links this sentence to ZZFX-FY2026-REV-GUIDE--FIX-COMMIT-001-base#V1; this is an attributed suggestion, not a deterministic check. restates the original guidance
[brief] span 63..90 → role unresolved_claim, support UNRESOLVED (none); marked unresolved by the operator: no source passage about demand is registered
[brief] span 91..176 → role direct_quotation, support SUPPORTED (exact_quotation_match/1); verbatim substring of registered excerpt 0000000000-26-000001:45b937ee0c849642 (45b937ee0c849642…); a quotation binds bytes, it does not authenticate the publisher
[brief] span 177..231 → role direct_quotation, support UNRESOLVED (exact_quotation_match/1); the quoted bytes are not a verbatim substring of any registered excerpt of the linked claim
```

`show` indique désormais `4 of 4 identified statements have mapped evidence` avec les statuts `ATTRIBUTED`, `UNRESOLVED`,
`SUPPORTED`, `UNRESOLVED`. Un `link` ultérieur sur la même plage d’octets remplace le précédent (le lien le plus récent pour
une plage l’emporte) ; le lien antérieur reste dans le journal.

### Rôles

Un rôle décrit la **fonction** de l’énoncé ; il n’en établit pas l’exactitude.

| Rôle | À utiliser pour | Appui qu’il peut atteindre |
|---|---|---|
| `direct_quotation` (citation directe) | un texte entre guillemets (“ ”, « », ") copié d’une source enregistrée | `SUPPORTED` lorsque les octets cités sont une sous-chaîne littérale d’un extrait enregistré des sources de l’engagement lié (`exact_quotation_match/1`) ; sinon `UNRESOLVED` |
| `computed_statement` (énoncé calculé) | un nombre que la note dérive (point médian, variation, appartenance, comparaison) | `SUPPORTED` par un calcul enregistré (`registered_arithmetic/1`) — phrases de modèle seulement ; votre propre lien d’une prose libre est `ATTRIBUTED` |
| `attributed_source_statement` (énoncé attribué à une source) | une reformulation de ce que dit une source | modèles : `SUPPORTED` (`typed_slot_render/1`) ; votre lien : `ATTRIBUTED` |
| `analyst_interpretation` (interprétation de l’analyste) | votre lecture des faits | `ATTRIBUTED` si lié à un engagement ; `NOT_ASSESSED` sans engagement |
| `generated_commentary` (commentaire généré) | les phrases d’un brouillon importé ou modifié non encore classées (valeur par défaut) | `NOT_ASSESSED` jusqu’au lien |
| `unresolved_claim` (affirmation non résolue) | une affirmation pour laquelle aucun élément probant n’est consigné (par exemple un énoncé causal) | `UNRESOLVED` par définition (le contrat refuse `SUPPORTED` pour ce rôle) |

### Mots d’appui

| Statut | Signification | Comment il survient |
|---|---|---|
| `SUPPORTED` | appuyé par une vérification déterministe | correspondance exacte de citation, calcul enregistré, rendu typé de modèle, ou énoncé de méthode du calculateur — jamais par la seule affirmation d’un évaluateur |
| `ATTRIBUTED` | un évaluateur (vous) a affirmé le lien ; non reproduit de manière déterministe | `link` d’une prose libre vers une version d’engagement |
| `UNRESOLVED` | aucun élément probant appuyant l’énoncé n’est consigné | le rôle `unresolved_claim` ; une citation introuvable dans tout extrait enregistré |
| `CONTRADICTED` | contredit par des éléments probants consignés | un calcul enregistré qui ne se recalcule plus (le réducteur transforme `SUPPORTED` en `CONTRADICTED`) |
| `NOT_ASSESSED` | rien n’a été décidé pour cette phrase | chaque phrase d’un brouillon importé, une phrase nouvelle après une modification, chaque phrase d’une traduction saisie |
| `INVALIDATED` | le texte ou un fait protégé a changé après la vérification ; l’appui antérieur ne se transmet pas | une modification qui a changé un champ protégé ; un échec d’intégrité des octets |

---

## 6. Modifications et traductions

### Modifier

Chaque enregistrement crée une nouvelle version avec un parent ; l’original n’est jamais écrasé.

```
yuclaw workbench brief show --workspace ~/yuclaw-workspaces/research --brief brf-4625e1016814 --json | python3 -c "import sys,json;print(json.load(sys.stdin)['text'])" > ~/yuclaw-workspaces/draft.txt
```

Pour le guide, `draft.txt` a été modifié en deux endroits : `USD 110–120 million` est devenu `CAD 110–120 million` dans la
phrase 1, et la phrase « The company also opened a new office in Montréal. » a été ajoutée après la phrase causale. Puis :

```
yuclaw workbench brief edit --workspace ~/yuclaw-workspaces/research --brief brf-4625e1016814 --file ~/yuclaw-workspaces/draft.txt --provenance "edited by the operator for the guide (fictional)"
```
```
[brief] brf-4625e1016814 B2 saved (parent B1 preserved) — mapped 9/10 statements; findings: PROTECTED_FACT_CHANGED: sentence 130..300 of the parent lost protected slot(s) ['range']; its SUPPORTED support does not carry over; PROSE_CONTRADICTS_PROTECTED_FACT: the text names currency CAD; the claim's currency is USD. scan scope: ISO-4217 codes among a fixed list, fiscal-period labels FY/Qn/Hn/Mnn + year, and the words GAAP / non-GAAP / IFRS, anywhere in the text; semantic contradictions outside this scope are not detected
```

```
yuclaw workbench brief show --workspace ~/yuclaw-workspaces/research --brief brf-4625e1016814 --version B2
```
```
brf-4625e1016814 B2 (en) — Research brief — ZZFX-FY2026-REV-GUIDE--FIX-COMMIT-001-base
status COMPLETE · Evidence incomplete · snapshot f618f796af628a55… at v8 tip 5b841dfc6e49…
8 of 11 identified statements have mapped evidence; extraction completeness is not established.

[ 1] attributed_source_statement  INVALIDATED  bytes VERIFIED No later information recorded · Watermark check not requested
     Fictional Example Corp (ZZFX) stated revenue guidance for FY2026 (GAAP) of CAD 110–120 million in its 8-K (fictional) filed 2026-02-10 (accession 0000000000-26-000001).
[ 2] attributed_source_statement  SUPPORTED    bytes VERIFIED No later information recorded · Watermark check not requested
     In its 8-K (fictional) filed 2026-05-12 (accession 0000000000-26-000002), the company revised that guidance to USD 105–115 million.
…
[ 9] unresolved_claim             UNRESOLVED   bytes VERIFIED No later information recorded · Watermark check not requested
     Management cut guidance because demand collapsed.
[10] generated_commentary         NOT_ASSESSED bytes VERIFIED No later information recorded · Watermark check not requested
     The company also opened a new office in Montréal.
[11] analyst_interpretation       NOT_ASSESSED bytes VERIFIED No later information recorded · Watermark check not requested
     Evidence that would support or refute it: …

open review items: 2 · receipts: 1 · reports: 0 · versions: ['B1', 'B2']
```

Ce qui s’est passé, mécaniquement :

- **Correspondance par octets exacts.** Une phrase du parent est MAPPED (mise en correspondance) avec l’enfant seulement
  lorsque ses octets exacts apparaissent exactement une fois dans le nouveau texte ; neuf sur dix l’ont été et gardent leur
  appui. Une phrase mise en correspondance ne garde son appui que si chaque **champ protégé** (devise, montant ou
  fourchette, période, base, numéro de dépôt, pourcentage, citation) se lit encore à l’identique.
- **Fait protégé modifié.** La phrase 1 a perdu le champ protégé `range` (`USD 110–120 million`). La phrase de l’enfant qui
  porte encore le plus de valeurs protégées restantes hérite du lien comme **INVALIDATED** — jamais de l’appui — et un
  élément à examiner `PROTECTED_FACT_CHANGED` nomme ce qui a changé. L’énoncé 1 de B2 se lit `support: INVALIDATED …
  limits: protected slot(s) ['range'] changed in this edit; the parent's SUPPORTED does not carry over; re-link after
  checking the typed fact`.
- **Balayage de la prose.** Une prose libre nommant une devise, une période fiscale ou une base comptable différente de
  celle de l’engagement produit `PROSE_CONTRADICTS_PROTECTED_FACT`. Le périmètre du balayage est énoncé dans le constat
  lui-même : codes ISO 4217 d’une liste fixe, étiquettes de période des formes FY/Qn/Hn/Mnn + année, et les mots GAAP /
  non-GAAP / IFRS, partout dans le texte. **Aucune contradiction sémantique hors de ce périmètre n’est détectée.**
- **Les phrases nouvelles** (« …office in Montréal. ») deviennent des énoncés `NOT_ASSESSED` à lier ou à qualifier.
- Le parent **B1 est intact** : `show --version B1` montre toujours 0 élément ouvert issu de ses propres constats.

### Éléments à examiner et dispositions

```
yuclaw workbench brief review --workspace ~/yuclaw-workspaces/research --brief brf-4625e1016814 --version B2
```
```
OPEN     d3cf2bbd5d1d191d40f7132d PROTECTED_FACT_CHANGED (this version): sentence 130..300 of the parent lost protected slot(s) ['range']; its SUPPORTED support does not carry over
OPEN     773f24297bfe94e7f1ee32cb PROSE_CONTRADICTS_PROTECTED_FACT (this version): the text names currency CAD; the claim's currency is USD. scan scope: …
```

Une disposition se consigne avec `--resolve <identifiant d’élément> --disposition … --note …` ; la disposition doit être
l’une de `REVIEWED_NO_CHANGE` (examiné, sans changement), `REVISED` (révisé), `WITHDRAWN_STATEMENT` (énoncé retiré),
`DISPUTED` (contesté), et une note est obligatoire :

```
yuclaw workbench brief review --workspace ~/yuclaw-workspaces/research --brief brf-4625e1016814 --version B2 --resolve d3cf2bbd5d1d191d40f7132d --disposition REVIEWED_NO_CHANGE --note "the CAD edit was deliberate for the guide; the statement stays INVALIDATED until re-linked (fictional)"
```
```
resolved d3cf2bbd5d1d191d40f7132d PROTECTED_FACT_CHANGED (this version): …
OPEN     773f24297bfe94e7f1ee32cb PROSE_CONTRADICTS_PROTECTED_FACT (this version): …
```

Résoudre un élément consigne votre décision ; cela ne change pas l’appui de l’énoncé. `show --strict` sort avec le code 1
tant qu’un élément est ouvert ou qu’un énoncé n’est pas `SUPPORTED`/`ATTRIBUTED` — utile avant de publier une version.

### Traduction déterministe (versions issues d’un modèle)

Une version rendue par un modèle peut être rendue à nouveau dans l’autre langue à partir du même instantané, de sorte que
chaque énoncé typé est lié à nouveau. Aucune prose n’est traduite et rien n’est envoyé nulle part.

```
yuclaw workbench brief translate --workspace ~/yuclaw-workspaces/research --brief brf-4625e1016814 --version B1 --to fr
```
```
[brief] brf-4625e1016814 B3 (fr) saved from B1 — mapping operator_mapped/1; findings: none
```
```
yuclaw workbench brief show --workspace ~/yuclaw-workspaces/research --brief brf-4625e1016814 --version B3 --lang fr
```
```
brf-4625e1016814 B3 (fr) — Note de recherche — ZZFX-FY2026-REV-GUIDE--FIX-COMMIT-001-base
status COMPLETE · Éléments probants liés · snapshot f618f796af628a55… at v8 tip 5b841dfc6e49…
9 des 10 énoncés identifiés ont des éléments probants associés ; l’exhaustivité de l’extraction n’est pas établie.

[ 1] attributed_source_statement  SUPPORTED    bytes VERIFIED Aucune information ultérieure consignée · Vérification du filigrane non demandée
     Fictional Example Corp (ZZFX) a annoncé des prévisions de revenue pour FY2026 (GAAP) de 110–120 millions USD dans son 8-K (fictional) déposé le 2026-02-10 (numéro 0000000000-26-000001).
…
[ 3] computed_statement           SUPPORTED    bytes VERIFIED Aucune information ultérieure consignée · Vérification du filigrane non demandée
     Le point médian est passé de 115 millions USD à 110 millions USD : une variation de −5 millions (−4,35 %, calculée comme −5 / 115 × 100 et arrondie au pair le plus proche à deux décimales, donc approximativement).
…
[ 9] unresolved_claim             UNRESOLVED   bytes VERIFIED Aucune information ultérieure consignée · Vérification du filigrane non demandée
     La direction a abaissé ses prévisions parce que la demande s’est effondrée.
```

Les chiffres sont identiques dans les deux langues ; seule la présentation diffère (virgule décimale, espace fine insécable
avant %, vrai signe moins). L’énoncé 3 de B3 porte le même calcul enregistré et `recomputed now: VERIFIED`.

### Traduction saisie (toute version)

```
yuclaw workbench brief translate --workspace ~/yuclaw-workspaces/research --brief brf-4625e1016814 --version B2 --to fr --file ~/yuclaw-workspaces/traduction.txt --provenance "translation entered by the operator; not certified"
```
```
[brief] brf-4625e1016814 B4 (fr) saved from B2 — mapping none; findings: SPAN_UNMAPPED: 11 parent statement(s) are not bound in the translation; the typed numbers were compared instead; PROSE_CONTRADICTS_PROTECTED_FACT: the text names currency CAD; the claim's currency is USD. …
```

Une traduction saisie est consignée avec la provenance que vous déclarez. Toutes ses phrases sont `NOT_ASSESSED` (la liaison
aux éléments probants ne se transmet pas d’une langue à l’autre) ; les séquences de chiffres du parent et de la traduction
sont comparées (indépendamment de la langue), et le balayage des faits protégés s’applique au nouveau texte. Rien n’est
envoyé à un fournisseur de traduction, et rien n’est certifié : la zone 2 de l’inspecteur pour une phrase traduite indique
`transform: translate · implementation: operator translate through the workbench form or CLI · deterministic: False` avec
les inconnues explicites `provider`, `model`, `settings` (« not exposed: the text was entered or imported locally… »).

---

## 7. Corrections de source et examen des dépendances

Une note est composée à partir d’un **instantané** des engagements v8 dont elle dépend (l’empreinte de l’instantané et la
pointe du journal v8 figurent dans chaque `show`). Les événements v8 ultérieurs ne changent jamais l’instantané ; `review`
compare l’état v8 courant avec lui et liste les énoncés dont les *dépendances consignées* sont touchées. Rien n’est inféré
au-delà des liens consignés.

Pour le guide, la disponibilité de la première source fictive a été corrigée côté v8 (la page des sources de l’atelier,
formulaire « correct availability », consigne un événement `SOURCE_AVAILABILITY_CORRECTED` ; voir le guide v8), de
2026-02-10T21:05:00Z à 2026-02-10T21:30:00Z. Puis :

```
yuclaw workbench brief review --workspace ~/yuclaw-workspaces/research --brief brf-4625e1016814 --version B1
```
```
OPEN     95163986d91f0a893efdd0c3 SOURCE_AVAILABILITY_CORRECTED (source:0000000000-26-000001:45b937ee0c849642): effective availability 2026-02-10T21:05:00Z → 2026-02-10T21:30:00Z (corrections ['AC1'])
```
```
yuclaw workbench brief show --workspace ~/yuclaw-workspaces/research --brief brf-4625e1016814 --version B1 --statement 1
```
```
3. Changes
   Later information exists · snapshot f618f796af628a55… · review items: ['95163986d91f0a893efdd0c3']
   - SOURCE_AVAILABILITY_CORRECTED (source:0000000000-26-000001:45b937ee0c849642): effective availability 2026-02-10T21:05:00Z → 2026-02-10T21:30:00Z (corrections ['AC1'])
```

Exactement les énoncés dont les éléments probants citent cette source (énoncés 1 et 8 de B1) indiquent désormais **Later
information exists** (des informations ultérieures existent) ; l’énoncé 3, qui cite des versions d’engagement et un calcul
mais pas cette source, indique toujours « No later information recorded ». L’en-tête de la note passe de `Evidence bound`
(éléments probants liés) à `Evidence incomplete` (éléments probants incomplets) tant qu’un élément est ouvert.

Motifs d’examen possibles : `SOURCE_AVAILABILITY_CORRECTED`, `CLAIM_AMENDED`, `CLAIM_WITHDRAWN`, `OUTCOME_CHANGED` (issus de
l’état v8 courant), `SPAN_UNMAPPED`, `PROTECTED_FACT_CHANGED`, `PROSE_CONTRADICTS_PROTECTED_FACT` (issus d’une modification
ou d’une traduction), `OPERATOR_FLAG`.

**Les exports antérieurs restent des instantanés valides.** Le paquet construit avant la correction (section 10) se
vérifie toujours `SUCCESS` ensuite : il consigne la date limite de recherche (empreinte de l’instantané et pointe v8) sur
laquelle il a été construit, et la vérification contrôle ce que le paquet transporte, non l’espace d’aujourd’hui.

---

## 8. Enregistrements de provenance : ce qu’ils sont, ce qu’ils ne sont pas

Trois types d’enregistrements s’importent avec `import-record --kind receipt | report | calibration --file <json>`. Chacun
est validé selon son contrat, lié à une vue de texte exacte (et, pour un rapport, au passage exact testé), et sa signature
est vérifiée. La section 9 traite des signatures ; SCHEMA.md liste chaque champ.

### Reçus de génération (`GenerationReceipt/1`)

Un reçu dit comment un texte a été produit : origine, méthode d’enregistrement, modèle de rendu ou fournisseur et modèle
d’IA, réglages, empreintes de l’invite et des sorties brute et assemblée, et **inconnues explicites** — chaque quantité que
le reçu ne peut exposer doit en nommer la raison (« not exposed: … »). Un rendu de modèle porte son propre reçu
(`recording_method: template_deterministic`, `provider: local`). Ce reçu fictif décrit B1 comme produit par un
fournisseur :

```
yuclaw workbench brief import-record --workspace ~/yuclaw-workspaces/research --kind receipt --file ~/yuclaw-workspaces/receipt.json --label "fictional provider receipt"
```
```
[brief] receipt aa325501a90cf167 imported — origin operator_assertion; signature NONE / trust NOT_EVALUATED / binding NOT_APPLICABLE; bound to {'brief_id': 'brf-4625e1016814', 'version_id': 'B1', 'language': 'en'}
```

Le reçu se lie par `assembled_output_sha256`, qui doit être égal au `view_sha256` d’une version de note de cet espace ;
sinon il est refusé (`receipt refused: assembled_output_sha256 0000000000000000… is not a text view of any brief version
here; a receipt binds to the exact assembled bytes`).

### Rapports de détecteur (`DetectionReport/1`)

Un rapport tient trois choses séparées :

| Champ | Valeurs | Signification |
|---|---|---|
| `execution` | `NOT_REQUESTED` · `ACCESS_UNAVAILABLE` · `UNSUPPORTED` · `INSUFFICIENT_INPUT` · `COMPLETED` · `FAILED` | si le détecteur s’est exécuté ; toute valeur autre que `NOT_REQUESTED` et `COMPLETED` exige un `failure_reason` |
| `signal` | `DETECTED` · `NOT_DETECTED` · `INCONCLUSIVE` | le résultat — présent **seulement** lorsque l’exécution est `COMPLETED` |
| `calibration` | `APPLICABLE` · `OUT_OF_SCOPE` · `NOT_ESTABLISHED` | ce que le rapport affirme sur l’étalonnage ; `APPLICABLE` exige une exécution `COMPLETED` et un `calibration_ref` |

Les quatre quantités `threshold`, `p_value`, `scored_context_count`, `key_epoch` doivent être fournies (dans `diagnostics`
ou `configuration`) ou déclarées indisponibles sous `unknown` avec une raison ; elles ne sont jamais inférées d’un article.
Le rapport se lie à `view_sha256` plus le passage exact testé (`start`, `end`, `span_sha256`) ; `show --json` donne
l’empreinte de la vue et les décalages de l’énoncé, et l’empreinte du passage est le `sha256` de ces octets exactement :

```
python3 -c "
import hashlib, json
view = json.load(open('show_B1.json'))          # saved from: yuclaw workbench brief show … --json
data = view['text'].encode('utf-8')
s = view['statements'][8]                      # statement 9 (1-based): the unresolved causal sentence
print(view['text_view']['view_sha256'] == hashlib.sha256(data).hexdigest())
print(s['start'], s['end'], hashlib.sha256(data[s['start']:s['end']]).hexdigest())
"
```
```
True
1358 1407 5dba767631f8fb11064804c7e711c0d075ca3d2ed3427f34d5447398761d57a2
```

Deux rapports fictifs sur ce passage — l’un où aucun détecteur n’a pu être joint, l’autre effectué — et un que le contrat
refuse (SCHEMA.md montre le JSON complet de chacun) :

```
yuclaw workbench brief import-record --workspace ~/yuclaw-workspaces/research --kind report --file ~/yuclaw-workspaces/report_unavailable.json --label "fictional detector record 1"
yuclaw workbench brief import-record --workspace ~/yuclaw-workspaces/research --kind report --file ~/yuclaw-workspaces/report_completed.json --label "fictional detector record 2"
yuclaw workbench brief import-record --workspace ~/yuclaw-workspaces/research --kind report --file ~/yuclaw-workspaces/report_bad.json
```
```
[brief] report 302e9f106f7275bb imported — origin operator_assertion; signature NONE / trust NOT_EVALUATED / binding NOT_APPLICABLE; bound to {'brief_id': 'brf-4625e1016814', 'version_id': 'B1', 'language': 'en'}; execution ACCESS_UNAVAILABLE signal None calibration NOT_ESTABLISHED
[brief] report 77bdd65b2c9af9e2 imported — origin operator_assertion; signature NONE / trust NOT_EVALUATED / binding NOT_APPLICABLE; bound to {'brief_id': 'brf-4625e1016814', 'version_id': 'B1', 'language': 'en'}; execution COMPLETED signal NOT_DETECTED calibration NOT_ESTABLISHED
[brief] refused: detection report cannot be recorded: report.signal: must be absent unless execution is COMPLETED (FAILED cannot become NOT_DETECTED); report.calibration: APPLICABLE is meaningless without a COMPLETED execution; report.calibration: APPLICABLE requires calibration_ref (the CalibrationRecord it rests on)
```

L’énoncé 9 de B1 liste désormais les deux rapports dans la zone 4 ; son libellé devient `Watermark check unavailable`
(vérification du filigrane indisponible — le premier rapport couvrant décide du libellé), le rapport effectué est marqué
`Provider-reported result; not reproduced or calibrated here` (résultat déclaré par le fournisseur ; ni reproduit ni
étalonné ici), et son appui sur le fond reste `UNRESOLVED`. Un rapport couvre exactement le passage testé d’une vue de
texte ; il ne s’applique pas à d’autres octets, versions ou langues.

### Enregistrements d’étalonnage (`CalibrationRecord/1`)

Un enregistrement d’étalonnage décrit les taux d’erreur mesurés d’un détecteur : corpus, provenance des étiquettes,
langues, domaines, strates de longueur, unité de test, règle de sélection, partition, plan de taux d’erreur, comptes de la
matrice de confusion, méthode d’intervalle, strates manquantes. Un rapport qui affirme `calibration: APPLICABLE` n’est
montré applicable **que** si l’enregistrement d’étalonnage référencé est présent, dans le périmètre (même détecteur, même
version, même configuration, même portée de clé, et la langue de la vue parmi les langues étalonnées), **et** signé par un
émetteur auquel cet espace fait confiance. Une affirmation d’étalonnage importée par l’opérateur reste `NOT_ESTABLISHED` :

```
yuclaw workbench brief import-record --workspace ~/yuclaw-workspaces/research --kind calibration --file ~/yuclaw-workspaces/calibration.json
yuclaw workbench brief import-record --workspace ~/yuclaw-workspaces/research --kind report --file ~/yuclaw-workspaces/report_applicable.json --label "fictional detector record 3 (claims APPLICABLE)"
```
```
[brief] calibration 8fc00981097616d7 imported — origin operator_assertion; signature NONE / trust NOT_EVALUATED / binding NOT_APPLICABLE; bound to workspace
[brief] report 0977b46d62b172e8 imported — … execution COMPLETED signal NOT_DETECTED calibration APPLICABLE
```

et dans `show --json`, la `calibration` de ce rapport se lit :

```
"calibration_claimed": "APPLICABLE",
"calibration": {
 "applicability": "NOT_ESTABLISHED",
 "claimed": "APPLICABLE",
 "calibration_record": "8fc00981097616d7…",
 "reason": "the calibration record is operator_assertion (signature NONE, trust NOT_EVALUATED); an imported assertion is not independently measured calibration"
}
```

### Types d’origine

| `origin` | Signification | Exigence |
|---|---|---|
| `operator_assertion` | vous avez saisi ou importé l’enregistrement ; il consigne ce qui a été fourni | aucune au-delà du contrat |
| `connector_observed` | une réponse observée par un connecteur configuré | `recording_method: connector_observed` ; **aucun connecteur n’existe dans 9.0** — le type est réservé pour qu’un résultat de connecteur puisse être importé plus tard sans changement de schéma |
| `issuer_signed` | une déclaration signée cryptographiquement par un émetteur | un `signature_envelope` valide (section 9) ; sinon l’import est refusé |

**Un nom de fichier, une capture d’écran, un identifiant de requête ou un horodatage n’est pas une signature de
fournisseur.** Un reçu dont `origin` indique `issuer_signed` sans enveloppe est refusé pour exactement ce motif :

```
[brief] refused: generation receipt cannot be recorded: receipt.origin: issuer_signed requires a signature_envelope (a filename, screenshot or request id is not a provider signature)
```

### Les quatre énoncés « jamais »

Ils figurent sur chaque page de note, dans chaque paquet et dans l’annexe (texte anglais du produit, traduction entre
parenthèses) :

- NOT_DETECTED does not prove human authorship. (NOT_DETECTED ne prouve pas une rédaction humaine.)
- A detector score is not the percentage of text written by AI. (Un score de détecteur n’est pas le pourcentage de texte écrit par une IA.)
- A watermark does not establish identity, ownership, responsibility or factual accuracy. (Un filigrane n’établit ni identité, ni propriété, ni responsabilité, ni exactitude factuelle.)
- A local receipt is not legal compliance and not an independently anchored timestamp. (Un reçu local n’est ni une conformité juridique ni un horodatage ancré de manière indépendante.)

---

## 9. Signatures et racines de confiance

Un enregistrement signé porte un `signature_envelope` (`yuclaw.signed-record/1`) : Ed25519 sur une entrée à séparation de
domaine qui inclut le type d’enregistrement (`brief.generation_receipt`, `brief.detection_report`,
`brief.calibration_record`) et le JSON canonique du corps signé. Quatre réponses sont rapportées séparément et jamais
fusionnées :

| Réponse | Valeurs | Question |
|---|---|---|
| **signature** | `NONE` · `VALID` · `INVALID` · `UNVERIFIABLE` | les octets se vérifient-ils sous la clé que nomme l’enveloppe ? |
| **trust** (confiance) | `NOT_EVALUATED` · `TRUSTED` · `UNKNOWN_SIGNER` · `REVOKED_ROOT` | cette clé est-elle une racine que l’administrateur de *cet* espace a inscrite, et non révoquée ? |
| **binding** (liaison) | `NOT_APPLICABLE` · `BOUND` · `MISMATCH` | le corps à l’intérieur de l’enveloppe est-il le même enregistrement que celui présenté avec elle ? |
| **révocation** | partie de la confiance : `REVOKED_ROOT` | la racine a-t-elle été révoquée ici (une révocation apparaît immédiatement dans chaque vue) |

Les racines de confiance sont **celles du destinataire** : il n’y a pas de confiance au premier usage, et un paquet
n’inscrit jamais son propre signataire. Pour le guide, une clé Ed25519 fictive a signé un rapport de détecteur
(`origin: issuer_signed`) :

```
yuclaw workbench brief import-record --workspace ~/yuclaw-workspaces/research --kind report --file ~/yuclaw-workspaces/report_signed.json --label "signed fictional report"
```
```
[brief] report ba1ab1a47e52f54e imported — origin issuer_signed; signature VALID / trust UNKNOWN_SIGNER / binding BOUND; bound to {'brief_id': 'brf-4625e1016814', 'version_id': 'B1', 'language': 'en'}; execution COMPLETED signal NOT_DETECTED calibration NOT_ESTABLISHED
```

Une signature valide d’un signataire inconnu n’est pas une signature malformée ; l’enregistrement est conservé avec
`UNKNOWN_SIGNER`. Inscrivez la clé (clé publique Ed25519 brute de 32 octets, en base64) et le même enregistrement se lit
`TRUSTED` :

```
yuclaw workbench brief trust --workspace ~/yuclaw-workspaces/research enroll --public-key aAEMoJmJ7OrLpSg9IcPmBVJfErPlP2EU+RGdNXcBn2A= --label "fictional detector vendor key" --issuer "Fictional Detector Vendor"
yuclaw workbench brief trust --workspace ~/yuclaw-workspaces/research list
```
```
{
 "key_id": "aa89f0dc1d354af4e81ba4571823001b",
 "kind": "TRUST_ROOT_ENROLLED",
 "duplicate": false
}
{
 "aa89f0dc1d354af4e81ba4571823001b": {
  "public_key": "aAEMoJmJ7OrLpSg9IcPmBVJfErPlP2EU+RGdNXcBn2A=",
  "label": "fictional detector vendor key",
  "revoked": false,
  "enrolled_at": "2026-10-10T04:06:29.208476Z",
  "issuer": "Fictional Detector Vendor"
 }
}
```

La zone 4 de l’énoncé 9 montre alors `'signature': 'VALID', 'trust': 'TRUSTED', 'key_id': 'aa89f0dc…', 'binding': 'BOUND'`.
L’évaluation est faite selon les racines *courantes* du destinataire à chaque rendu d’une vue ; ainsi, après

```
yuclaw workbench brief trust --workspace ~/yuclaw-workspaces/research revoke --key-id aa89f0dc1d354af4e81ba4571823001b --reason "key retired (fictional)"
```

le même enregistrement se lit `'trust': 'REVOKED_ROOT'` tandis que sa signature reste `VALID` et sa liaison `BOUND`. Une
racine révoquée n’est jamais réactivée (`refused: key aa89f0dc… is already enrolled (a revoked root is never revived; enroll
a new key)`).

Un enregistrement modifié après signature est refusé — la signature est valide pour le corps à l’intérieur de l’enveloppe,
mais ce corps n’est pas l’enregistrement présenté :

```
[brief] refused: report refused: the signature verifies for the body inside the envelope, but that body differs from the record presented with it (payload mismatch: a valid signature on different bytes)
```

Un signataire de confiance peut tout de même formuler une affirmation financière non appuyée : rien dans cette section ne
change l’**appui sur le fond**. L’énoncé 9 reste `UNRESOLVED` avec un rapport signé `TRUSTED` sur ses octets.

---

## 10. Exports et vérification

```
yuclaw workbench brief export --workspace ~/yuclaw-workspaces/research --brief brf-4625e1016814 --version B1
```
```
[brief] packet bpk-a3ff4d970a5e16c3 → ~/yuclaw-workspaces/research/exports/bpk-a3ff4d970a5e16c3.zip (39038 bytes, sha256 f7698355281d6fce…); members: brief.html, brief.json, records.json, snapshot.json, appendix.md, text/, VERIFY.md
```

### Membres du paquet

| Membre | Contenu |
|---|---|
| `BRIEF_MANIFEST.json` | format `yuclaw.brief-packet/1`, identifiant du paquet, note et version, langue, identités logicielles, empreinte de l’instantané, date limite de recherche (pointe v8, empreinte de l’instantané, date de construction), la liste des fichiers avec empreintes et tailles, l’empreinte de contenu, les composants omis, les limites |
| `VERIFY.md` | comment vérifier, le tableau des fichiers, les composants omis, les limites |
| `brief.html` | la note lisible : HTML statique avec une balise meta Content-Security-Policy et **sans script** |
| `brief.json` | la vue du réducteur pour la version exportée, champs privés retirés |
| `records.json` | chaque version avec ses passages, sa transformation et son reçu ; reçus, rapports et étalonnages importés ; résolutions d’examen ; libellés des racines de confiance de l’auteur ; mesures ; date limite de recherche |
| `snapshot.json` | l’instantané des éléments probants, filtré selon les droits |
| `text/<view_sha256>.txt` | les octets exacts du texte de **chaque** version de la note (quatre membres dans l’exemple : B1 à B4) |
| `appendix.md` | l’annexe méthodes et limites générée à partir des enregistrements |

**Filtrage selon les droits.** Les extraits de source ne voyagent que pour les classes de droits `FICTIONAL`,
`SEC_PUBLIC_FILING` et `OPERATOR_OWN_TEXT` ; pour les autres classes, l’empreinte voyage et l’extrait est retenu, ce qui
rend les vérifications qui en dépendent `NOT_RECOMPUTABLE`, jamais un échec. Les invites et les réponses brutes de
fournisseur ne figurent jamais dans un enregistrement (seulement leurs empreintes) ; les octets bruts conservés restent dans
le coffre privé. Clés d’API, secrets de signature et chemins d’espace de travail ne voyagent jamais. La liste `omitted` du
manifeste nomme chaque composant retenu et son effet (vide dans l’exemple fictif).

### Vérifier dans un espace vierge

```
yuclaw workbench brief verify ~/yuclaw-workspaces/research/exports/bpk-a3ff4d970a5e16c3.zip --workspace ~/yuclaw-workspaces/fresh
```
```
[brief verify] SUCCESS — every recomputable binding and calculation reproduced; non-recomputable and report-only components are listed, not assumed; nothing here establishes truth, authorship or approval
  zip sha256 f7698355281d6fce9744adfee0d2d510563b3ced3057482edb33c010a54c67ea
  outcomes {'VERIFIED': 49, 'FAILED': 0, 'NOT_RECOMPUTABLE': 0, 'REPORT_ONLY': 5, 'UNSUPPORTED': 0, 'NOT_APPLICABLE': 6}
  summary {'versions': 4, 'spans': 46, 'calculations': 12, 'reports': 5, 'omitted': []}
```

`--workspace` nomme l’espace **destinataire** : ses racines de confiance jugent les signatures du paquet, et un
enregistrement `PACKET_VERIFIED` y est écrit (`status --workspace ~/yuclaw-workspaces/fresh` le montre ; `briefs: []` — la
vérification n’installe ni note, ni engagement, ni racine, ni politique). Sans `--workspace`, les vérifications s’exécutent
de la même façon et la confiance est `NOT_EVALUATED`. `--json` liste chaque vérification ; la page `/brief/verify` du
navigateur montre le même tableau.

### Résultats des vérifications

| Résultat | Signification |
|---|---|
| `VERIFIED` | recalculé à partir du matériel du paquet et reproduit : empreintes et longueurs des membres, empreinte de contenu, forme JSON canonique, empreinte de l’instantané, empreinte de chaque membre texte, chaque liaison de passage, chaque calcul enregistré, chaque citation face à son extrait, le lien parent et la liaison du reçu de chaque version, la liaison de chaque rapport à son passage, chaque signature, la cohérence interne des mesures, la sûreté du HTML |
| `FAILED` | non reproduit ; le premier échec est nommé dans `first_discrepancy` et le résultat est `MISMATCH` |
| `NOT_RECOMPUTABLE` | une entrée a été retenue pour des raisons de droits (extrait, invite) ; listée, non supposée, pas un échec |
| `REPORT_ONLY` | un résultat de détecteur ne peut être réexécuté ici ; consigné tel que déclaré |
| `UNSUPPORTED` | un type de calcul inconnu de ce vérificateur |
| `NOT_APPLICABLE` | un enregistrement non signé (affirmation de l’opérateur) n’a pas de signature à vérifier ; un calcul `pending` n’a pas d’arithmétique |

**Ce que la vérification établit :** que les octets du paquet sont ceux que son manifeste déclare, que le passage de chaque
énoncé correspond encore à son empreinte consignée dans le texte empaqueté, que chaque calcul enregistré se recalcule à
partir de ses entrées typées, que chaque citation est une sous-chaîne de son extrait empaqueté, et la situation de chaque
signature selon les racines du destinataire. **Ce qu’elle n’établit pas :** l’authenticité des sources, la vérité
factuelle, la paternité humaine, un examen indépendant, la conformité juridique ou une approbation de publication. Une
empreinte de manifeste ou un badge ne remplace jamais les résultats par vérification.

### Résultats négatifs

Un paquet dont un octet d’un membre texte a été altéré :

```
[brief verify] MISMATCH — byte mismatch at text/1739c5a93a813faf….txt
  outcomes {'VERIFIED': 11, 'FAILED': 1, …}
```

Un fichier qui n’est pas un paquet, et un export v8 (qui a son propre vérificateur) :

```
[brief verify] UNSUPPORTED — refused: not a zip archive
[brief verify] UNSUPPORTED — this is a v8 export (EXPORT_MANIFEST.json present, no BRIEF_MANIFEST.json); verify it with the v8 verifier (`yuclaw workbench verify-export`), which stays unchanged — this reader never reinterprets it
```

Inversement, `yuclaw workbench verify-export` sur un paquet v9 répond `MISMATCH — incomplete packet: missing
['EXPORT_MANIFEST.json']` : aucun des deux vérificateurs ne réinterprète le format de l’autre.

---

## 11. Ce qui est mesuré, affirmé, vérifié indépendamment, ou indisponible

| | Exemples dans ce guide | Où c’est énoncé |
|---|---|---|
| **Mesuré par le logiciel** | empreintes des octets de chaque vue et passage ; arithmétique enregistrée recalculée à partir des entrées typées (points médians 115 et 110 millions, −5 millions, −4,35 %) ; correspondance exacte des citations ; présence unique des octets d’une phrase dans un texte modifié ; comptes et durées des opérations | zones 1 et 4 ; `recomputed now` ; `measure` |
| **Affirmé par une personne ou un enregistrement importé** | votre texte `--provenance` ; un lien `ATTRIBUTED` ; tout le contenu d’un reçu, rapport ou enregistrement d’étalonnage `operator_assertion` ; le résultat de détecteur d’un fournisseur (`Provider-reported result; not reproduced or calibrated here`) | zone 2 ; l’`origin` de l’enregistrement |
| **Vérifié indépendamment** | une signature sous une racine inscrite dans cet espace (`VALID` / `TRUSTED` / `BOUND`) ; le périmètre et l’authentification d’un enregistrement d’étalonnage | zone 4 ; `trust list` |
| **Indisponible, et dit comme tel** | les inconnues explicites d’un reçu ou d’un rapport (« not exposed: … ») ; `ACCESS_UNAVAILABLE` avec son motif ; `NOT_RECOMPUTABLE` pour un extrait retenu ; `REPORT_ONLY` pour un résultat de détecteur ; la phrase « extraction completeness is not established » (l’exhaustivité de l’extraction n’est pas établie) sur chaque note | l’enregistrement lui-même ; `verify` ; la phrase de couverture |

Mesures des opérations :

```
yuclaw workbench brief measure --workspace ~/yuclaw-workspaces/research
```
```
operations 24 · attempts 24 · retries 0 · outcomes {'COMMITTED': 21, 'REFUSED': 3} · durations {'n': 24, 'sum_ms': 402, 'median_ms': 15, 'max_ms': 46} · missing {'corrupt_lines': 0, 'missing_duration': 0}
per task: { "create_brief": {…}, "edit_brief": {…}, "export_packet": {…}, … }
definitions: {
 "operation": "one logical operation = one op_id; counted once however many times it was attempted",
 "attempt": "one measured run of an operation (a line in v9/operations.jsonl); retries are additional attempts of the same operation",
 "retries": "attempts − operations, over operations with ≥ 1 attempt",
 "outcome": "per attempt: COMMITTED | DUPLICATE | CONFLICT | REFUSED | FAILED | READ — …",
 "elapsed_ms": "wall-clock milliseconds of the software attempt, from entering the operation to leaving it; not labour time, not cognitive effort",
 "eligible_denominator": "all attempts recorded by this workspace's v9 surfaces since measurement began; nothing earlier is reconstructed",
 "exclusions": "v8 workbench operations (recorded in the v8 journal, not measured here); operations of other workspaces",
 "missingness": "an attempt whose line is corrupt or lacks finished_at is listed under missing, not estimated"
}
```

Les durées mesurent le programme, non le travail ni l’effort cognitif d’une personne. Les tentatives refusées ou en échec
restent dans les comptes. Le même agrégat voyage dans chaque paquet (`records.json` → `measurements`) et dans l’annexe.

---

## 12. En cas de problème

Chaque mot ci-dessous est imprimé par le logiciel ; le code de sortie est entre crochets.

| Vous voyez | Signification | Que faire |
|---|---|---|
| `[brief] refused: …` [2] | refus de contrat ; **rien n’a été écrit**. Exemples : `span: start offset 19 is inside a multi-byte UTF-8 sequence` ; `span: offsets 1500..1700 outside the view of 1560 bytes` ; `span: half-open range needs start < end (got 10..5)` ; `sections must be a non-empty subset of […]` ; `disposition must be REVIEWED_NO_CHANGE, REVISED, WITHDRAWN_STATEMENT or DISPUTED` ; `detection report cannot be recorded: …` | corrigez le champ ou le décalage nommé (section 5 pour les décalages en octets) et relancez |
| `E_OP_CONFLICT: op_id '…' was already used for a different operation; a retry must repeat the same content` [1] | le même `--op-id` a été réutilisé avec un contenu différent | une reprise doit répéter exactement le même contenu (elle est alors servie par l’enregistrement existant : `DUPLICATE`) ; sinon prenez un nouvel identifiant d’opération |
| `E_TORN_TAIL: the v9 sidecar has a torn tail; run \`brief recover\` before writing (nothing durable is lost)` [3] | une écriture interrompue a laissé des octets sans saut de ligne final ; `status` indique `"integrity": "TORN_TAIL"` et les lectures fonctionnent toujours | `yuclaw workbench brief recover --workspace …` conserve les octets dans `v9/brief.jsonl.torn.<empreinte>` et ajoute un enregistrement `RECOVERY` ; un second `recover` répond `"recovered": false, "reason": "no torn tail"` |
| `INCOMPLETE` sur une version (`list`, `show`, navigateur) | les objets préparés de la version (texte, instantané) manquent dans le coffre | la version n’est jamais affichée ni exportée comme complète ; `export` la refuse (`this version is INCOMPLETE (prepared objects missing); an incomplete brief is never exported as complete`) ; recréez la version à partir de son parent |
| `orphans` liste des objets | des objets du coffre préparés qu’aucun enregistrement ne valide (une opération s’est interrompue entre la préparation des octets et la validation de son enregistrement) | lister ne supprime rien ; `--remove` ne supprime **que** ceux-là, revérifiés sous le verrou (`"removed": […], "kept_referenced_or_unknown": []`) |
| `E_WORKSPACE_MISMATCH: sidecar belongs to workspace ws-… but this is ws-… (a sidecar is never read against another workspace's journal)` [3] | un dossier `v9/` a été copié dans un autre espace de travail | remettez le journal annexe à côté de son propre `workspace.json` ; ne mélangez jamais les dossiers |
| `E_NO_SIDECAR: this workspace has no v9 sidecar yet (nothing v9 was recorded here)` [3] | `status`, `recover`, `orphans` ou `measure` sur un espace où v9 n’a jamais écrit | rien à réparer ; `example`, `create` ou `import` crée le journal annexe |
| `E_MISSING: store does not exist` [2] | le chemin `--workspace` n’est pas du tout un espace de travail | vérifiez le chemin |
| `[brief verify] UNSUPPORTED — …` [3] | pas un paquet v9 que ce vérificateur comprend : `refused: not a zip archive`, `this is a v8 export (EXPORT_MANIFEST.json present …)`, un format inconnu | utilisez le bon vérificateur (`yuclaw workbench verify-export` pour un export v8) ; rien n’a été réinterprété |
| `[brief verify] MISMATCH — <première divergence>` [1] | au moins une liaison ou un calcul ne s’est pas reproduit ; le premier est nommé (`byte mismatch at text/….txt`, `incomplete packet: missing …`, `version B2: span 0..5 binding failed`, …) | le paquet n’est pas celui qui a été construit, ou a été altéré ; procurez-vous-le de nouveau |
| `show --strict` sort avec le code 1 | des éléments à examiner sont ouverts ou un énoncé n’est pas `SUPPORTED`/`ATTRIBUTED` | résolvez ou révisez, puis relancez |
| un formulaire du navigateur répond `E_SIGN_IN` / `E_FORBIDDEN` | des principaux sont configurés et votre session n’a pas `admin`, `review` ou `submit` (les racines de confiance exigent `admin`) | connectez-vous avec un principal doté de la capacité |

### Référence : la famille de commandes

Extrait de `yuclaw workbench brief --help` :

```
example        load the fictional fixture (idempotent) and compose the acceptance brief from all three templates
create         compose a brief from deterministic templates over one frozen claim
import         import an AI-assisted or hand-written draft as a new brief (sentences become unassessed statements to link)
list           briefs of this workspace
show           the brief and its statements (the reducer view); --statement N opens the inspector's four areas
edit           save edited text as a new version (parent preserved; spans re-mapped; protected facts validated)
translate      add a translation: deterministic re-render for a template version, or --file with an entered translation
link           link a byte span to a claim version and role (manual span selection / link correction)
review         review items of a brief (live dependency review + transform findings); --resolve records a disposition
import-record  import a generation receipt, detector report or calibration record (validated, bound, signature-checked)
trust          this workspace's trust roots for signed provenance records: enroll | revoke | list
export         build the readable HTML brief, JSON records and the verification packet (zip)
verify         verify a brief packet offline (exit 0 SUCCESS / 1 MISMATCH / 3 UNSUPPORTED); --workspace records the verification in that fresh workspace
measure        operation measurements with their definitions
status         sidecar status (integrity, briefs, v8 binding)
recover        recover a torn sidecar tail (preserves the bytes; records a RECOVERY record)
orphans        list prepared vault objects that no record commits; --remove deletes only those
schema         the v9 record contracts and vocabularies (developer reference)
selftest       bounded self-check from the installed package in a temporary fictional workspace
guide          print the packaged v9 quick start (--lang fr for French)
```

Chaque écriture accepte `--actor` (un libellé d’attribution consigné avec l’écriture — pas une authentification) et
`--op-id` (une reprise avec le même identifiant et le même contenu est idempotente ; par défaut un nouvel identifiant
`cli:<24 hex>`). `create` prend `--sections`, une liste séparée par des virgules parmi `guidance_change`,
`numerical_comparison`, `unresolved_interpretation` :

```
yuclaw workbench brief create --workspace ~/yuclaw-workspaces/research --claim ZZFX-FY2026-REV-GUIDE--FIX-COMMIT-001-base --sections guidance_change --lang fr
```
```
[brief] brf-8e4f44bfb327 B1 created — 1194 bytes, 5 statements
```

Références pour les développeurs : [SCHEMA.md](SCHEMA.md) (contrats, vocabulaires, sémantique des octets, manifeste du
paquet) et [MIGRATION.md](MIGRATION.md) (ce que v9 crée dans un espace, ce qu’il ne touche jamais, la récupération).

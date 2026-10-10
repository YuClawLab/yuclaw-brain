# YUCLAW v9 — notes de recherche avec assistance IA traçable : démarrage rapide

Recherche et formation uniquement. Aucun conseil en placement.
Mission : Make financial AI accountable to evidence. Vision : Become the Science Trust Layer for Financial AI.

Une **note** (brief) est un court texte de recherche financière dont chaque phrase peut être inspectée : sur quel passage
exact de source, quelle version figée d’engagement v8 et quel calcul enregistré elle repose, comment le texte a été
produit, ce qui a changé depuis, et quelles vérifications ont pu ou non être effectuées. Tout s’exécute localement, à côté
de l’atelier v8. Aucune clé d’API, aucun téléchargement de modèle ni service hébergé n’est nécessaire pour le parcours
complet ci-dessous. Les commandes, identifiants, valeurs de schéma et mots d’état restent en anglais : ce sont ce que vous
tapez ou faites correspondre.

## 1. Installer (le même paquet que l’atelier v8)

```
python3 -m venv ~/yuclaw-venv && source ~/yuclaw-venv/bin/activate
python -m pip install yuclaw
yuclaw workbench brief --help
yuclaw workbench brief selftest          # vérifie cette installation dans un espace fictif temporaire
```

Windows PowerShell : utilisez `& "$HOME\yuclaw-venv\Scripts\python.exe" -m v9.brief …` pour chaque commande ci-dessous
(`python -m v9.brief` et `yuclaw workbench brief` sont le même programme).

## 2. L’exemple fictif complet en une commande

```
yuclaw workbench brief example --workspace ~/yuclaw-workspaces/research --lang fr
```

Cette commande charge l’exemple fictif fourni `001_base` (émetteur « Fictional Example Corp », prévisions initiales de
110–120 millions USD, révisées à 105–115 millions, résultat ultérieur de 112 millions — données synthétiques, jamais des
données de marché) et compose une note à partir des trois modèles déterministes. La sortie liste chaque énoncé avec son
rôle et ses cinq réponses indépendantes :

| Réponse | Mots affichés |
|---|---|
| Intégrité des octets | VERIFIED · FAILED |
| Origine consignée | template_render · import · edit · translate, avec les inconnues explicites |
| Confiance envers l’émetteur (enregistrements signés) | signature VALID / INVALID · TRUSTED / UNKNOWN_SIGNER / REVOKED_ROOT |
| Appui sur le fond | SUPPORTED · ATTRIBUTED · UNRESOLVED · CONTRADICTED · NOT_ASSESSED · INVALIDATED |
| Portée temporelle | « Aucune information ultérieure consignée » · « Des informations ultérieures existent » (+ éléments à examiner) |

Le point médian passe de 115 millions USD à 110 millions USD : −5 millions, environ −4,35 % (−5 / 115 × 100, arrondi au
pair le plus proche à deux décimales ; la fraction exacte est conservée). Le résultat se situe dans les deux fourchettes —
ce qui, dit la note, n’établit pas une meilleure précision des prévisions. La phrase « La direction a abaissé ses
prévisions parce que la demande s’est effondrée. » reste **UNRESOLVED** : aucun élément probant pour cette affirmation
causale n’existe dans l’espace, et ni citation, ni signature, ni résultat de détecteur ne peut la rendre appuyée.

## 3. Inspecter une phrase

```
yuclaw workbench brief list --workspace ~/yuclaw-workspaces/research
yuclaw workbench brief show --workspace ~/yuclaw-workspaces/research --brief brf-… --statement 3 --lang fr
```

L’inspecteur comporte quatre zones : **1 Sources et calculs** (extrait, localisateur, dates, périmètre, formule, entrées,
arrondi, recalcul immédiat), **2 Comment le texte a été produit** (modèle / import / modification / traduction, réglages
connus, inconnues explicites), **3 Modifications** (versions parentes, éléments à examiner sur les dépendances de cet
énoncé), **4 Vérifications** (liaison des octets, signatures et confiance, portée du rapport de détecteur). `--json`
imprime la même vue ; la page du navigateur affiche la même chose.

## 4. Modifier, traduire, examiner

```
yuclaw workbench brief show --workspace … --brief brf-… --json | python3 -c "import sys,json;print(json.load(sys.stdin)['text'])" > brouillon.txt
# modifiez brouillon.txt, puis :
yuclaw workbench brief edit --workspace … --brief brf-… --file brouillon.txt
yuclaw workbench brief translate --workspace … --brief brf-… --version B1 --to fr        # nouveau rendu déterministe d’une version issue d’un modèle
yuclaw workbench brief translate --workspace … --brief brf-… --to fr --file traduction.txt  # traduction saisie (sa provenance est consignée)
yuclaw workbench brief review --workspace … --brief brf-… --lang fr
```

Chaque enregistrement crée une nouvelle version avec un parent ; l’original n’est jamais écrasé. Une phrase dont les
octets exacts survivent à la modification garde sa liaison ; une phrase qui a perdu un fait protégé (devise, montant,
période, base, numéro de dépôt) devient **INVALIDATED** et un élément à examiner nomme ce qui a changé. Une devise, une
période ou une base en prose libre qui contredit l’engagement produit un élément à examiner, dans le périmètre déclaré
du balayage. Lorsqu’une source v8 est corrigée ou un engagement amendé après l’instantané de la note, `review` liste les
énoncés dont les dépendances consignées demandent un examen ; les exports antérieurs restent valides comme instantanés
historiques.

## 5. Importer un brouillon ou un enregistrement de provenance

```
yuclaw workbench brief import --workspace … --file brouillon.txt --claim ZZFX-FY2026-REV-GUIDE--FIX-COMMIT-001-base --lang fr
yuclaw workbench brief link --workspace … --brief brf-… --start 0 --end 57 --role direct_quotation --claim ZZFX-…-001-base --claim-version V1
yuclaw workbench brief import-record --workspace … --kind report --file rapport.json
yuclaw workbench brief trust --workspace … enroll --public-key <Ed25519 en base64> --label "émetteur X"
```

Les phrases d’un brouillon importé commencent **NOT_ASSESSED** ; vous liez des passages par décalages en octets UTF-8.
Une citation directe est vérifiée contre les octets de l’extrait enregistré ; le lien d’une prose libre vers un engagement
vous est **ATTRIBUTED**, jamais SUPPORTED. Un rapport de détecteur doit être lié aux octets exacts testés ; ses dimensions
`execution` (NOT_REQUESTED / ACCESS_UNAVAILABLE / UNSUPPORTED / INSUFFICIENT_INPUT / COMPLETED / FAILED), `signal`
(seulement si COMPLETED) et `calibration` (APPLICABLE / OUT_OF_SCOPE / NOT_ESTABLISHED) sont tenues séparées.
NOT_DETECTED ne prouve jamais une rédaction humaine ; un score n’est pas un pourcentage de texte IA ; un filigrane n’établit
ni identité ni exactitude.

## 6. Exporter et vérifier ailleurs

```
yuclaw workbench brief export --workspace ~/yuclaw-workspaces/research --brief brf-… --lang fr
yuclaw workbench brief verify ~/yuclaw-workspaces/research/exports/bpk-….zip --workspace ~/yuclaw-workspaces/fresh
```

Le paquet contient la note lisible `brief.html` (sans script), `brief.json`, `records.json`, l’instantané, le texte de
chaque version, une annexe méthodes et limites et `VERIFY.md`. La vérification déclare chaque contrôle séparément :
VERIFIED, FAILED, NOT_RECOMPUTABLE (une entrée a été retenue pour des raisons de droits), REPORT_ONLY (un résultat de
détecteur ne peut être réexécuté), UNSUPPORTED, NOT_APPLICABLE. Les signatures sont jugées selon les racines de confiance
de l’espace destinataire ; un paquet n’inscrit jamais son signataire.

## 7. En cas de problème

- `refused: …` avec code 2 — refus de contrat ; rien n’a été écrit. Corrigez le champ nommé.
- `E_OP_CONFLICT` avec code 1 — le même `--op-id` a été réutilisé avec un contenu différent ; prenez un nouvel identifiant.
- `E_TORN_TAIL` — écriture interrompue ; `yuclaw workbench brief recover --workspace …` conserve les octets et le consigne.
- `INCOMPLETE` sur une version — ses objets préparés manquent ; elle n’est jamais affichée ni exportée comme complète.
- `orphans` liste les objets préparés qu’aucun enregistrement ne valide ; `--remove` ne supprime que ceux-là.
- `measure` imprime les comptes d’opérations avec leurs définitions (un op_id = une opération ; tentatives et reprises comptées à part).

Guide complet, référence des schémas et note de migration : `docs/guide/v9/` dans le dépôt.

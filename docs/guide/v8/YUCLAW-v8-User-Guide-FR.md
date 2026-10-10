# YUCLAW Version 8 — Guide utilisateur

*Édition française • YUCLAW 8.0.1*

Téléchargements: [PDF](YUCLAW-v8-User-Guide-FR.pdf) · [DOCX (modifiable)](YUCLAW-v8-User-Guide-FR.docx) · [Index du guide (bilingue)](README.md)  
English version: [User Guide (EN)](YUCLAW-v8-User-Guide-EN.md)

> Cette édition Markdown est produite à partir du même fichier `guide_content.json` que les éditions PDF et DOCX (`render_markdown.py`). Les renvois aux pages du PDF correspondent aux sections numérotées ci-dessous.

D’une déclaration financière à un engagement traçable, examinable et reproductible.

### Mission

Rendre l’IA financière responsable de ses affirmations au regard des éléments probants.

Texte officiel : Make financial AI accountable to evidence.

### Vision

Devenir la couche de confiance scientifique de l’IA financière.

Texte officiel : Become the Science Trust Layer for Financial AI.

Un manuel pratique destiné aux chercheurs, aux réviseurs et aux responsables d’espaces de travail locaux. Il couvre le parcours en sept étapes, SHD, EVO, COM, PRC, les exports de recherche et le site public.

**Version du logiciel :** 8.0.1. **Édition du guide :** 1.1, 9 octobre 2026. Ces instructions concernent cette version ; les libellés et comportements peuvent évoluer.

Recherche et formation uniquement. Aucun conseil en placement. L’atelier consigne et vérifie des travaux de recherche ; il ne passe pas d’ordres et ne publie pas votre espace de travail.

- [yuclaw.ca](https://yuclaw.ca)

## Table des matières

1. [1 Se repérer](#1-se-repérer)
2. [2 Installer YUCLAW](#2-installer-yuclaw)
3. [3 Réaliser un premier parcours](#3-réaliser-un-premier-parcours)
4. [4 Enregistrer une source](#4-enregistrer-une-source)
5. [5 Créer et figer un engagement](#5-créer-et-figer-un-engagement)
6. [6 Comparer et calculer](#6-comparer-et-calculer)
7. [7 Lire un historique sans recul indu](#7-lire-un-historique-sans-recul-indu)
8. [8 Consigner des notes et un examen](#8-consigner-des-notes-et-un-examen)
9. [9 Données et rejeu scientifique](#9-données-et-rejeu-scientifique)
10. [10 Exporter et vérifier la recherche](#10-exporter-et-vérifier-la-recherche)
11. [11 Configurer les comptes locaux](#11-configurer-les-comptes-locaux)
12. [12 SHD admission protégée](#12-shd-admission-protégée)
13. [13 EVO audit de réutilisation](#13-evo-audit-de-réutilisation)
14. [14 COM file de révision à capacité limitée](#14-com-file-de-révision-à-capacité-limitée)
15. [15 PRC tenter avant de comparer](#15-prc-tenter-avant-de-comparer)
16. [16 Exporter les enregistrements des modules](#16-exporter-les-enregistrements-des-modules)
17. [17 Ingestion facultative de documents](#17-ingestion-facultative-de-documents)
18. [18 Dépanner en préservant l’historique](#18-dépanner-en-préservant-lhistorique)
19. [19 Référence des commandes et routes](#19-référence-des-commandes-et-routes)
20. [20 Termes et documentation source](#20-termes-et-documentation-source)

## 1 Se repérer

Consultez le site public pour explorer les éléments probants publiés. Installez l’atelier local pour créer vos sources, engagements, examens et paquets reproductibles. Une page boursière du site public n’alimente pas automatiquement votre espace local.

| Votre objectif | À consulter |
|---|---|
| Comprendre le produit et lire les données publiques | Cette section |
| Installer le logiciel et suivre un premier exemple fictif | Sections [2](#2-installer-yuclaw)–[3](#3-réaliser-un-premier-parcours) |
| Enregistrer des sources et figer un engagement financier | Sections [4](#4-enregistrer-une-source)–[5](#5-créer-et-figer-un-engagement) |
| Comparer les fourchettes et interpréter les résultats | Section [6](#6-comparer-et-calculer) |
| Reconstituer l’historique et corriger une heure de disponibilité | Section [7](#7-lire-un-historique-sans-recul-indu) |
| Consigner des notes, un examen et des données scientifiques | Sections [8](#8-consigner-des-notes-et-un-examen)–[9](#9-données-et-rejeu-scientifique) |
| Exporter et vérifier hors de l’espace d’origine | Section [10](#10-exporter-et-vérifier-la-recherche) |
| Configurer les rôles locaux et utiliser les quatre modules | Sections [11](#11-configurer-les-comptes-locaux)–[16](#16-exporter-les-enregistrements-des-modules) |
| Récupérer un document avec l’outil d’ingestion facultatif | Section [17](#17-ingestion-facultative-de-documents) |
| Résoudre une erreur ou trouver une commande | Sections [18](#18-dépanner-en-préservant-lhistorique)–[19](#19-référence-des-commandes-et-routes) |
| Consulter les termes et la documentation source | Section [20](#20-termes-et-documentation-source) |

### Lire le site public

Sur `https://yuclaw.ca`, commencez par Explorer ou une vue sectorielle, puis ouvrez les éléments probants et les sources d’un titre. Forward Tracking présente les résultats consignés ; Evidence Scoreboard, la couverture des attestations ; Methodology, les définitions. Vérifiez la date, le périmètre et l’exhaustivité de chaque document avant toute comparaison.

Les signaux sont des classifications de recherche. Un score n’est pas un rendement attendu ; la couverture documentaire n’est pas une probabilité. Un aperçu ou une liste plafonnée ne constitue pas un historique complet. Lisez les limites indiquées à côté des scores de référence.

### Ce que la version 8 apporte

L’atelier local relie les sources aux exports : versions immuables, calculs exacts, historique temporel et examen. Quatre modules expérimentaux ajoutent une admission protégée, un audit de réutilisation des évaluations, une file de révision à capacité limitée et une pratique où la tentative précède la comparaison. Ils ne certifient pas la vérité et n’autorisent aucun déploiement externe.

Les libellés anglais tels que **Source**, **Build export** et `IN_RANGE` correspondent à l’interface. Les exemples fictifs ne décrivent aucun émetteur réel.

## 2 Installer YUCLAW

Utilisez Python 3.10 ou ultérieur et un environnement virtuel distinct. Une connexion Internet est nécessaire pour télécharger le paquet. Le parcours fictif utilise ensuite des données incluses ; il n’exige ni base de production ni flux de dépôts en direct.

### macOS ou Linux

```bash
python3 -m venv ~/yuclaw-venv
source ~/yuclaw-venv/bin/activate
python -m pip install "yuclaw==8.0.1"
python -m pip show yuclaw
yuclaw workbench --help
```

### Windows PowerShell

Appelez directement l’interpréteur de l’environnement : aucune modification de la politique d’activation PowerShell n’est nécessaire. Ajustez la sélection du lanceur Python si plusieurs versions sont installées.

```powershell
py -3 -m venv "$HOME\yuclaw-venv"
& "$HOME\yuclaw-venv\Scripts\python.exe" -m pip install "yuclaw==8.0.1"
& "$HOME\yuclaw-venv\Scripts\python.exe" -m pip show yuclaw
& "$HOME\yuclaw-venv\Scripts\python.exe" -m v8.workbench --help
```

### Vérifier cette installation une fois

```bash
yuclaw workbench selftest
yuclaw workbench guide
```

Sous Windows, remplacez `yuclaw workbench` dans les commandes suivantes par la forme `python.exe -m v8.workbench` ci-dessus. Sous macOS ou Linux, activez l’environnement dans chaque terminal, ou utilisez le chemin complet de l’exécutable. Les commandes prolongées par une barre oblique inverse utilisent la syntaxe macOS/Linux ; dans PowerShell, saisissez la commande sur une seule ligne en supprimant ces barres de continuation.

**Résultat attendu :** la version affichée est 8.0.1 et l’aide liste les commandes. Le selftest facultatif crée des espaces fictifs temporaires, contrôle calculs, exports et refus, puis supprime son dossier temporaire. Il vérifie cette installation, pas toute la suite de développement.

### Différences entre plateformes

Les parcours principaux et les autres modules fonctionnent sans admission SHD. Cette admission protégée exige un mécanisme d’isolation Linux pris en charge et une sonde réussie sur l’hôte. Sous macOS et Windows, elle reste fermée ; cela ne signifie pas que l’installation de l’atelier a échoué.

Les commandes Windows sont l’équivalent, via l’interpréteur, de la CLI fournie. Ce guide ne prétend pas que chaque combinaison de système, noyau et matériel a été testée indépendamment.

## 3 Réaliser un premier parcours

### Démarrer un espace de recherche

Dans le premier terminal, avec l’environnement virtuel activé :

```bash
yuclaw workbench serve --workspace ~/yuclaw-workspaces/research --port 8765
```

Dans un second terminal, activez le même environnement et démarrez un autre espace :

```bash
yuclaw workbench serve --workspace ~/yuclaw-workspaces/fresh --port 8766
```

Sous Windows, utilisez des chemins absolus entre guillemets, par exemple `"$HOME\yuclaw-workspaces\research"`. Chaque dossier est créé au premier usage. Placez-le hors d’un répertoire web publié. Chaque serveur doit utiliser un dossier distinct.

### Suivre l’exemple fictif

- Ouvrez `http://127.0.0.1:8765/`. Dans **Load a fictional fixture**, sélectionnez `001_base`, puis **Load fixture**.
- Ouvrez `ZZFX-FY2026-REV-GUIDE--FIX-COMMIT-001-base` (le chargeur ajoute l’identifiant de l’exemple à l’identifiant de l’engagement, afin qu’une démonstration chargée ne soit jamais confondue avec un engagement saisi à la main). Parcourez les étapes 1 à 6 : source, engagement typé, comparaison, calcul, historique et adjudication.
- Vérifiez la fourchette initiale de 110–120 millions, la révision de 105–115 millions et le résultat déclaré de 112 millions. Les deux calculs doivent afficher `IN_RANGE`.
- À l’étape 7, choisissez **Build export**, puis téléchargez le ZIP. Conservez l’empreinte indiquée avec le fichier.
- Ouvrez `http://127.0.0.1:8766/verify` dans l’espace vierge. Sélectionnez le ZIP et soumettez-le. Le résultat attendu est `SUCCESS`, accompagné des valeurs recalculées.

Il s’agit d’un exemple fictif rétrospectif, y compris son résultat daté dans le futur. Il illustre le logiciel sans établir de précision prédictive réelle. Un espace vierge n’est pas une deuxième personne indépendante.

### Arrêter et reprendre

Appuyez sur **Ctrl+C** dans chaque terminal serveur. Relancez la même commande, avec le même dossier et le même port, pour reprendre. Les actions déjà consignées restent dans le journal. Rechargez les formulaires après un redémarrage : leurs jetons dépendent de la session du serveur.

```bash
yuclaw workbench status --workspace ~/yuclaw-workspaces/research
```

Le serveur écoute sur `127.0.0.1`. Ouvrir yuclaw.ca ne le démarre pas. Fermer un onglet n’arrête pas le processus du terminal. Aucun dépôt ni résultat n’arrive automatiquement dans cet espace local.

## 4 Enregistrer une source

Ouvrez **1 Source**, à `/source`. Partez du passage exact que l’engagement citera. L’enregistrement conserve ce passage et son empreinte ; une reformulation appartient aux notes de recherche, pas à l’extrait source.

| Champ ou notion | Contenu attendu |
|---|---|
| Type et formulaire | Le vrai type de document et son formulaire. Ne qualifiez pas un communiqué de dépôt réglementaire pour satisfaire la validation. |
| Identifiant du dépôt ou de l’éditeur | Le véritable numéro EDGAR, ou l’identifiant d’éditeur pris en charge par le formulaire. |
| URL et date de dépôt | L’emplacement du document et sa date déclarée. Une URL ne remplace pas le passage probant. |
| Extrait exact | Les mots de la source, avec montants, unités et contexte préservés. |
| Available as of | L’heure de disponibilité publique. Utilisez une date UTC conforme, par exemple 2026-02-10T21:05:00Z. |
| Heure d’observation | Quand cet espace a observé la source, indépendamment de sa disponibilité publique. |
| Droits et statut fictif | Choisissez les droits applicables et signalez les données de démonstration. Ne présumez pas les droits de réutilisation. |

Soumettez le formulaire et vérifiez la présence de la source, de ses heures et de l’empreinte du passage. Le serveur attribue lui-même l’heure d’enregistrement. Sélectionnez cette source lors de la création de l’engagement.

### À partir d’un enregistrement d’ingestion

Choisissez **Register from an ingestion record**. Collez `original.source.json` et utilisez la valeur `retrieved_at` du fichier de provenance comme heure d’observation. La procédure d’ingestion réseau facultative figure en section [17](#17-ingestion-facultative-de-documents).

### Source incomplète ou incorrecte

Une disponibilité inconnue ne doit pas être inventée. Si le mauvais passage a été cité, enregistrez le bon et créez un amendement `CORRECTED_SOURCE`. Si seule l’heure est erronée, suivez la correction liée de la section [7](#7-lire-un-historique-sans-recul-indu). Ne modifiez jamais manuellement une source stockée ou le journal.

**À vérifier :** le passage, l’identité du document, les droits et les trois heures sont compréhensibles sans votre mémoire. Des empreintes concordantes prouvent une cohérence des octets, pas l’authenticité de l’éditeur ni la vérité du texte.

## 5 Créer et figer un engagement

Ouvrez **2 Typed claim**, à `/claim/new`. Un engagement typé explicite la comparaison financière avant toute interprétation. Sélectionnez la source enregistrée et remplissez tous les champs de comparabilité.

| Information requise | Exemple fictif ou règle |
|---|---|
| Identité de l’engagement et de l’émetteur | Un nouvel identifiant stable, avec le nom et les identifiants exacts de l’émetteur. |
| Indicateur et déclaration | Chiffre d’affaires ; préservez le sens de l’engagement de la source. |
| Bornes en unités | Pour 110–120 millions USD, saisissez 110000000 et 120000000, et non 110 et 120. |
| Devise, unité et échelle | USD ; USD ; millions dans le texte. L’échelle décrit l’énoncé, mais les montants sont saisis en unités. |
| Base comptable | GAAP, IFRS ou autre base prise en charge, selon la source. Ne confondez pas mesures ajustées et non ajustées. |
| Période comptable | Libellé, type, début et fin exacts. FY2026 dans l’exemple va du 2026-01-01 au 2026-12-31. |
| Règle de résolution et source | La règle prise en charge qui définit le test du résultat, avec le passage enregistré. |
| Statut fictif | Signalez explicitement la fiction. N’utilisez pas ses identifiants pour une société réelle. |

### Figer en connaissance de cause

Vérifiez l’échelle, la base, la période et la source. Le gel crée la version `V1` et son empreinte. **Le gel est irréversible.** Toute correction ou modification ultérieure crée un enregistrement sans écraser cette version.

### Réviser ou retirer un engagement

Dans la page de l’engagement, utilisez **Create an amendment**. Choisissez le type, modifiez les champs justifiés par la nouvelle source et indiquez le motif. `REVISED` décrit un engagement modifié ; `CORRECTED_SOURCE`, une correction de source. Les versions et empreintes antérieures restent visibles.

Utilisez l’action de retrait si l’engagement a été retiré, avec sa source et son motif. Le retrait est un événement, pas un engagement de remplacement ; il ne constitue pas automatiquement un échec. Examinez sa chronologie par rapport au résultat.

Dans les champs numériques, utilisez la syntaxe décimale attendue, sans séparateurs de milliers. La virgule décimale française ne remplace pas le point exigé par un champ numérique.

## 6 Comparer et calculer

**3 Comparison** présente les engagements initial et révisé. **4 Calculation** évalue le résultat déclaré pour chaque fourchette applicable. Enregistrez d’abord sa source, puis utilisez **Record the disclosed outcome**.

Saisissez le montant réalisé en unités, la devise, l’indicateur, la base et la période. La case de comparabilité est une déclaration : le calculateur contrôle quand même les champs. Le résultat n’a de sens que dans le cadre pris en charge.

### Exemple fictif détaillé

| Grandeur | Initial | Révisé |
|---|---|---|
| Fourchette en millions USD | 110–120 | 105–115 |
| Point médian | 115 | 110 |
| Montant réalisé | 112 | 112 |
| Réalisé moins point médian | −3 millions | +2 millions |
| Résultat d’appartenance | IN_RANGE | IN_RANGE |

Les bornes sont incluses : **borne basse ≤ réalisé ≤ borne haute**. Le point médian est `(low + high) / 2` ; l’écart est `actual − midpoint`. Les deux fourchettes contiennent le même montant. Cet accord ne prouve ni une amélioration de précision ni un effet causal de la révision.

### Interpréter les états non résolus

| Résultat | Sens et action suivante |
|---|---|
| IN_RANGE / OUT_OF_RANGE | Un résultat compatible se trouve dans/hors de la fourchette. Consultez aussi la source et la règle. |
| PENDING_OUTCOME | Aucun résultat déclaré applicable n’est enregistré. Ne remplacez pas une absence par zéro. |
| INCOMPARABLE | La comparaison des versions est impossible. Lisez tous les motifs ; n’en déduisez aucun écart comparatif. |
| INCOMPATIBLE_BASIS / UNIT_MISMATCH | Vérifiez les définitions, la base comptable et les unités. |
| PERIOD_MISMATCH / METRIC_MISMATCH | Périodes ou indicateurs différents. Corrigez les données justifiées au moyen de l’action enregistrée appropriée. |
| WITHDRAWN_BEFORE_OUTCOME | Un retrait qualifié dans le temps, pas un échec prédictif calculé. |

Une règle non prise en charge ou un résultat déclaré non comparable reste également non résolu. Ne changez pas une définition uniquement pour obtenir une réussite.

## 7 Lire un historique sans recul indu

Ouvrez **5 History**, saisissez une date limite UTC et sélectionnez **Replay**. Comparez cette vue avec la vue actuelle pour déterminer ce que les enregistrements étayaient à chaque moment. Les vues historiques des modules utilisent les heures d’action enregistrées.

| Heure | Question traitée |
|---|---|
| Disponibilité | Quand la source est déclarée accessible publiquement. |
| Observation | Quand l’espace l’a observée. |
| Enregistrement | Quand le serveur a consigné l’action ou la correction. |

Un dépôt ancien saisi aujourd’hui ne prouve pas que cet espace le détenait à sa date de dépôt. Le statut rétrospectif reste explicite. Une information ultérieure ne doit pas être interprétée comme une connaissance antérieure.

### Corriger une heure de disponibilité

- Ouvrez **1 Source → Correct a source’s availability time**, à `/source#availability`, et sélectionnez la source.
- Saisissez l’heure UTC corrigée, le motif, une référence probante et votre libellé d’acteur. Cette référence est du texte consigné ; le serveur ne la récupère pas.
- Soumettez. Vérifiez le nouvel événement `SOURCE_AVAILABILITY_CORRECTED`, qui relie anciennes et nouvelles valeurs. Le passage, son empreinte et l’heure d’observation restent inchangés.
- Examinez la **corrected view** de chaque engagement concerné, à côté du résultat enregistré. Consultez **Needs review** si le temps, le statut rétrospectif ou une adjudication antérieure est affecté.

### Effet sur les dates limites

Avant l’heure d’enregistrement de la correction, l’ancienne valeur reste applicable ; la correction apparaît comme une connaissance ultérieure. À partir de cette heure, la vue corrigée s’applique. Une correction peut rendre un enregistrement rétrospectif, mais jamais transformer un enregistrement rétrospectif en engagement contemporain.

Si une autre correction a été consignée depuis l’ouverture du formulaire, rechargez-le. Si votre examen modifie l’adjudication, ajoutez-en une nouvelle avec **Disputed** et un motif, sans effacer le jugement antérieur.

**À vérifier :** l’historique explique ce qui a changé et quand l’espace l’a appris. Les exports transportent la chaîne de corrections pour permettre le même recalcul ailleurs.

## 8 Consigner des notes et un examen

### Notes de recherche

Utilisez **Research notes** sur l’engagement ou `/notes`. Consignez la question non résolue, une explication possible, les éléments supplémentaires nécessaires et leur utilité. Les notes structurent la recherche sans modifier les engagements figés, les calculs ou les passages sources.

Une note utile nomme précisément l’incertitude. Exemple : « La déclaration révisée utilise une base ajustée. Obtenir le rapprochement avant de la comparer à l’objectif GAAP initial. » Elle définit une prochaine action sans affirmer une causalité.

Corrigez une note erronée par une note corrective. Conservez le texte précédent dans son historique. Si l’engagement financier change, créez plutôt un amendement.

### Étape 6 Adjudication

- Lisez les sources, le calcul exact et les motifs de non-comparabilité avant de choisir un libellé.
- Indiquez le libellé du réviseur, la règle, les références probantes, le motif et les conflits pertinents.
- Si votre jugement diffère du calcul, cochez **Disputed** et expliquez pourquoi. Le désaccord reste visible ; il ne remplace pas le calcul.
- Après soumission, vérifiez que jugement et résultat calculé sont distincts. Réexaminez l’historique lorsqu’un amendement ou une correction de disponibilité affecte la décision.

### Attribution et authentification

Le nom d’un réviseur ou d’un acteur dans le parcours principal est un libellé d’attribution. Il ne prouve ni identité authentifiée, ni indépendance, ni qualification. Après configuration des comptes locaux, les actions des modules utilisent leurs identifiants ; ceux-ci ne prouvent pas davantage une identité réelle.

### Préparer une transmission utile

Fournissez l’identifiant, la version et l’empreinte de l’engagement ; les sources ; la période, l’indicateur et la base ; le calcul ; les questions ouvertes et le motif du réviseur. Créez l’export correspondant selon la section [10](#10-exporter-et-vérifier-la-recherche) pour permettre au destinataire de contrôler le calcul enregistré.

Une adjudication est un jugement documenté selon une règle. Ce n’est ni une recommandation de placement ni une permission de publier des données privées.

## 9 Données et rejeu scientifique

### Examiner la couverture des données

Ouvrez `/dataset` ; `/dataset.json` en fournit la vue exploitable par machine. Une ligne par engagement figé est dérivée des enregistrements locaux : versions, filiation des sources, résultats, désaccords, droits, notes et motifs non résolus.

- Contrôlez les nombres de données fictives et réelles, les statuts rétrospectifs, les résultats absents, les cas incomparables et les extraits retenus pour raisons de droits.
- Lisez **Coverage gaps and known omissions** avant tout agrégat. Un espace vide ne prouve pas une couverture complète.
- Choisissez **Build dataset snapshot export**. Conservez l’empreinte de l’instantané. Les précédents restent disponibles ; leur comparaison indique les changements.

L’identité de l’instantané dépend des enregistrements et de la méthode, pas de l’instant du clic. Elle décrit la collection locale, et non un jeu de données validé sur tout le marché ou un échantillon automatique représentatif.

### Rejouer un journal scientifique compatible

Ouvrez `/sci`. Commencez par un exemple exploratoire fictif fourni, via le sélecteur de la page. Examinez manifeste et journal, lancez le rejeu, puis ouvrez l’enregistrement produit, par exemple `/sci/S1`. Il présente le rapport recalculé ou un refus explicite.

Le moteur respecte un contrat statistique défini : prévisions probabilistes appariées, amélioration du score de Brier et comptabilisation séquentielle des éléments probants. Avant votre propre journal, vérifiez indicateur, unité, appariement et budget d’erreur dans le manifeste. Une fourchette monétaire n’est pas une paire de probabilités.

| Entrée ou état | Interprétation |
|---|---|
| Journal exploratoire fourni | Démonstration fictive du logiciel ; aucun bénéfice financier établi. |
| Exemple prospectif avec une unité en attente | Démonstration du traitement d’un état incomplet, pas une expérience achevée. |
| Montants utilisés comme probabilités | Refus : hors du contrat d’entrée pris en charge. |
| Indicateur inconnu ou paire manquante | Corriger le protocole ou les entrées sans transformer le refus en réussite. |

Le rejeu recalcule ce que le journal décrit. Il ne prouve ni collecte honnête, ni enregistrement préalable d’une expérience, ni amélioration d’un système d’IA. Distinguez toujours exemples fictifs et recherche réelle.

## 10 Exporter et vérifier la recherche

### Créer un paquet de recherche

À l’étape 7 d’un engagement, **Build export** crée un ZIP filtré selon les droits. Pour toute la collection, utilisez l’export d’instantané. Téléchargez le paquet complet et conservez son empreinte et son identité en octets.

Le paquet d’engagement comprend schéma, versions, références et extraits autorisés, événements, méthodes, résultats et enregistrements connexes. Certains extraits peuvent être retenus. Les modules nécessitent un autre type de paquet, décrit en section [16](#16-exporter-les-enregistrements-des-modules).

### Vérifier dans un espace vierge

- Ouvrez `http://127.0.0.1:8766/verify` sur le serveur distinct. Sélectionnez le ZIP inchangé et soumettez-le.
- Lisez le résultat et la première divergence éventuelle. Le vérificateur redérive les empreintes et recalcule les contenus pris en charge, sans se fier au résultat affiché par l’expéditeur.
- Notez l’identité du paquet, le résultat, la version du logiciel et l’heure. Ne présentez pas un autre fichier comme couvert par cette vérification.

### Vérification en ligne de commande

Remplacez `research-export.zip` par le chemin du fichier. Cette commande vérifie un export d’engagement ou de jeu de données ; utilisez l’interface de vérification des modules pour leurs options de confiance et de point de contrôle.

```bash
yuclaw workbench verify-export research-export.zip --json
```

| Résultat | Code | Action |
|---|---|---|
| SUCCESS | 0 | Contenu compatible, cohérent et recalculé. Lire provenance et limites. |
| MISMATCH | 1 | Examiner la première divergence ; obtenir le paquet inchangé ou faire résoudre le défaut par son producteur. |
| UNSUPPORTED | 3 | Format ou entrée hors contrat. Vérifier le type de paquet et la version du logiciel. |

### Portée de la vérification

Elle établit la cohérence du paquet pris en charge et de ses calculs. Elle ne prouve ni authenticité des sources, ni vérité factuelle, ni examen humain indépendant, ni autorisation de publication. L’export de recherche n’est pas une sauvegarde de l’espace ni une procédure de restauration démontrée.

Conservez le ZIP original inchangé. Pour examiner une corruption, travaillez sur une copie distincte et gardez l’identité de l’original.

## 11 Configurer les comptes locaux

Le parcours principal peut être exploré avant la configuration des comptes. Les quatre modules exigent des capacités locales. Le premier administrateur est créé depuis la ligne de commande de l’hôte, jamais par auto-inscription dans le navigateur.

```bash
yuclaw workbench principals init --workspace ~/yuclaw-workspaces/research
```

Le secret d’accès n’est affiché qu’une fois. Conservez-le de manière sûre, jamais dans les notes ou exports. Il n’existe aucun mot de passe par défaut. Ensuite, toutes les pages demandent une connexion à `/login` ; **Setup**, à `/setup`, gère la configuration.

| Capacité | Fonction |
|---|---|
| admin | Gérer comptes, confiance, politiques, approbations, budgets, dérogations et résolutions consignées. |
| submit | Soumettre des lots probants et des paquets de révision selon les règles configurées. |
| review | Examiner les travaux admissibles, lancer les évaluations autorisées et préparer les tâches de pratique. |
| practice | Pratiquer. Un compte limité à cette capacité n’accède qu’à Practice, Modules, Help et à ses propres exports. |

### Attribuer les seules capacités nécessaires

Utilisez Setup ou la CLI de l’hôte. Cet exemple crée un compte réservé à la pratique ; remplacez l’identifiant par un nouvel identifiant local.

```bash
yuclaw workbench principals add --workspace ~/yuclaw-workspaces/research \
  --id learner1 --caps practice
yuclaw workbench principals list --workspace ~/yuclaw-workspaces/research
```

Une rotation émet un nouveau secret. La révocation du compte est définitive. Déconnexion, redémarrage, rotation et révocation terminent les sessions. Rechargez les formulaires après reconnexion.

### Préserver les séparations de rôle

Utilisez des profils de navigateur distincts. Le déposant SHD ne peut approuver son lot ; le réviseur EVO ne doit pas avoir amélioré la lignée ; le réviseur COM ne doit pas avoir contribué au groupe ; le praticien ne peut être le préparateur de sa tâche.

Un identifiant local établit quel compte a agi, pas que deux comptes représentent deux personnes. Qui contrôle le compte système et le dossier de travail reste l’opérateur de l’hôte et peut administrer les comptes par la CLI. Les capacités du navigateur ne limitent pas cet opérateur.

```bash
yuclaw workbench modules --workspace ~/yuclaw-workspaces/research
```

## 12 SHD admission protégée

**SHD — Distillation Shield**, à `/shd`, contrôle un lot probant par une voie approuvée et restreinte. Vérifiez d’abord la sonde d’isolation dans Setup. Si aucun mécanisme n’est disponible, l’admission reste fermée.

### Format d’entrée

Utilisez un ZIP conforme à `yuclaw.shd-bundle/1` : un manifeste `bundle.json` et les fichiers probants listés sous `evidence/`. Le manifeste précise une finalité, les SHA-256 complets, les tailles en octets et la charge utile typée. Ce n’est pas un formulaire de téléversement de documents quelconques. Limites : 8 Mio, 64 membres, plus des plafonds par membre et après décompression.

Finalités prises en charge : `evidence.reference`, `com.packets`, `evo.evaluations`. Pour construire un lot, suivez le schéma et le validateur versionnés cités en section [20](#20-termes-et-documentation-source). N’inventez ni champ ni approbation.

### Soumettre et obtenir une décision

- Comme déposant, téléversez le lot préparé et relevez son empreinte. Le téléversement stocke les octets sans les admettre.
- Un autre administrateur ouvre `/shd/trust`, sélectionne le lot, contrôle indépendamment les empreintes attendues et consigne finalité et expiration. L’approbation vise ces octets et cet espace précis.
- Demandez une décision. Le processus restreint ouvre et contrôle le lot ; l’approbation est revérifiée au moment de consigner la décision.
- Lisez les quatre réponses : intégrité, approbation, adjudication factuelle et permission de publication. Une admission peut alimenter COM ou EVO tant que l’approbation reste applicable.

| Refus | Action suivante |
|---|---|
| REFUSED_NO_APPROVAL | Obtenir l’approbation applicable d’un autre administrateur. |
| REFUSED_APPROVAL_EXPIRED / REVOKED | Résoudre l’état d’approbation ; l’ancienne ne peut être réutilisée. |
| REFUSED_SELF_APPROVAL | Utiliser un compte approbateur distinct. |
| REFUSED_BUNDLE_REJECTED | Lire le motif de structure ou d’empreinte ; corriger le lot comme de nouveaux octets. |
| REFUSED_ISOLATION_UNAVAILABLE | Utiliser un hôte Linux pris en charge dont la sonde réussit ; ne pas contourner la fermeture. |

**ADMITTED ne signifie pas vrai.** L’adjudication factuelle reste `NOT_ASSESSED` et la permission de publication `NONE`. L’isolation bubblewrap ou Landlock, vérifiée par sonde, ne constitue pas une certification de sécurité indépendante. Landlock n’est pas un conteneur complet.

## 13 EVO audit de réutilisation

**EVO — Evolution Evidence Audit**, à `/evo`, consigne les changements d’un système d’IA et l’applicabilité de ses évaluations antérieures. Il ne modifie pas le système et ne contrôle pas son déploiement.

### Configurer des mesures réelles

Un administrateur enregistre la configuration JSON : répertoires absolus existants `roots`, modes des composants, dépendances, protocoles et listes d’autorité. Le schéma versionné définit les champs exacts. Tout chemin doit rester dans une racine configurée.

| Clés de composants | Représentation |
|---|---|
| model, agent_code, tool_policy, memory | Mode path pour les fichiers mesurables ; declared pour une déclaration attribuée ; unknown si non mesuré. |
| data, grader, evaluation_data | Expliciter les données d’évaluation et l’identité du correcteur ; leurs changements peuvent invalider la réutilisation. |
| runtime | Mode runtime pour mesurer l’environnement, ou autre mode compatible décrivant fidèlement les éléments disponibles. |
| Composant non applicable | not_applicable avec justification, jamais une omission inexpliquée. |

Chaque protocole indique son périmètre, une tâche compatible (`policy_conformance` ou `json_wellformed`) et sa durée de validité. `depends_on` exprime les dépendances. Les listes d’autorité nomment auteurs du correcteur, producteurs d’éléments probants, autorisateurs de publication et lecteurs des tests protégés. Toute modification arrête la réutilisation ; les expositions antérieures aux tests restent consignées.

### Enregistrer et évaluer

- Choisissez **Measure and register**, avec un nouvel identifiant et un parent si nécessaire. Distinguez états mesuré, déclaré, inconnu et non applicable.
- Un réviseur n’ayant pas amélioré cette lignée lance l’évaluation autorisée. Le moteur vérifie l’identité et exécute le périmètre compatible sur une copie privée immuable.
- Si les fichiers actuels diffèrent, enregistrez une nouvelle version. Ne réutilisez pas l’ancienne étiquette pour de nouveaux octets.
- Lisez `REUSE` ou `REEVALUATE` par protocole, les dépendances, échecs ouverts, examens et expositions. Utilisez une date limite pour une décision historique.

Les échecs restent ouverts jusqu’à une résolution administrative étayée. Une évaluation importée par SHD est `DECLARED_IMPORT`, pas une exécution locale autorisée. Les engagements financiers liés restent séparés par devise.

**À vérifier :** la réutilisation repose sur identité et périmètre enregistrés. La ligne d’admissibilité n’autorise aucune publication externe.

## 14 COM file de révision à capacité limitée

**COM — Research Commons Guard**, à `/com`, regroupe les paquets liés et distribue un budget de révision consigné. Un administrateur définit d’abord la période, les minutes de révision, une réserve distincte de pratique, le plafond de paquets par compte et le maximum de tâches ouvertes.

### Soumettre et regrouper

Depuis un engagement, choisissez **submit a review packet about it**, ou utilisez COM. Confirmez la version et le contrat financier sélectionnés. Un lot admis par SHD offre une autre voie d’entrée.

Même version, indicateur, devise, unité, échelle, base, période et racines sources connues : les paquets forment un groupe et une tâche. Tous les contributeurs restent visibles. Plusieurs paquets ne constituent pas automatiquement plusieurs éléments indépendants.

### Traiter les doublons explicitement

Des passages aux octets identiques correspondent à une racine unique. Un réviseur ou administrateur peut déclarer un alias dans **Source aliases**, avec un motif ; la rétractation préserve les deux événements. Il n’y a pas de détection de similarité sémantique : un rendu différent reste distinct tant que le lien n’est pas consigné. Un litige sur un alias affecte les groupes appuyés sur le même document.

### Traiter une tâche

- Un réviseur non contributeur prend la tâche avec **Take (reserves the cost)**. Son coût prévisionnel est réservé sous verrou de l’espace.
- Utilisez **start**, **pause**, **resume**, **finish** ou **release**. L’expiration d’une réservation remet la tâche en file avec ses secondes observées.
- Lisez le motif d’attente : les petites tâches peuvent passer ; une tâche ancienne peut réserver la capacité restante ; une tâche trop grande est signalée pour arbitrage.
- Une priorité urgente ne crée pas de minutes. Si le budget est réduit sous l’usage enregistré, le dépassement reste visible.

### Litiges et appels

Un réviseur ou administrateur peut consigner un litige, retrait ou correction de source. Les groupes concernés sont mis en quarantaine jusqu’à résolution administrative. C’est un état de traitement, pas un constat de faute. Tout compte connecté peut faire appel ; motif et décision restent consignés.

L’estimation du déposant est une proposition ; le coût de planification est fixé par le réviseur ou l’administrateur. La comparaison de files affichée utilise des arrivées synthétiques fixes : c’est une simulation, pas la preuve d’un gain de productivité réel.

## 15 PRC tenter avant de comparer

**PRC — Independent Practice**, à `/prc`, conserve une tentative initiale avant de révéler une référence. Ce parcours local facultatif ne recrute personne, ne contacte personne et ne lance aucune étude.

### Préparer une tâche

Un réviseur fige question, engagement éventuel, périmètre des sources, libellés autorisés et référence de comparaison. Indiquez sa provenance : référence non adjugée, réponse de modèle ou référence déclarée examinée par le préparateur. Cette déclaration ne constitue pas une validation indépendante.

Le serveur garde la comparaison non révélée en privé ; le journal ne conserve qu’une empreinte salée. Configurez la réserve de pratique avant les sessions qui la nécessitent. Le praticien doit être distinct du préparateur de la tâche.

### Effectuer une session

- Connectez-vous avec le compte du praticien. La seule capacité practice limite les routes accessibles à la pratique et à ses propres exports.
- Ouvrez une session et déclarez honnêtement aide reçue et exposition antérieure. Les réponses sont acceptées et étiquetées ; les déclarations n’effacent pas la tentative.
- Lisez les éléments figés. Validez un jugement, un raisonnement et les sources utilisées. Choisissez `UNRESOLVED` si nécessaire et indiquez ce qui permettrait de conclure.
- Après validation seulement, choisissez **Open the comparison**. Examinez la provenance de la référence et ses différences avec votre tentative.
- Ajoutez une réflexion. Un réviseur peut consigner un retour ultérieur. Ce sont de nouveaux enregistrements ; la tentative initiale reste intacte.

### Confinement et confidentialité

Un praticien doté d’autres capacités porte le libellé `NOT_CONFINED` : d’autres routes peuvent lui révéler des informations. La référence n’est pas secrète pour l’opérateur de l’hôte, le préparateur ou l’administrateur. Le logiciel ne peut empêcher une aide extérieure ou une réponse trouvée ailleurs.

Une correction de source ou un amendement apparaît dans l’interprétation actuelle. Les suivis sont des échéances locales, pas des messages envoyés. La page de session permet de créer son paquet pour conserver ou partager le contenu pris en charge.

**À vérifier :** la tentative précède la révélation enregistrée. Cette séquence ne prouve ni rédaction humaine, ni absence d’aide, ni originalité, ni compréhension, ni progrès. Aucun classement de personnes n’est produit.

## 16 Exporter les enregistrements des modules

Ouvrez **Module evidence export and verification**, à `/modx`. L’export d’un engagement ne transporte pas les événements des modules. Sélectionnez les modules et sessions de pratique que votre compte peut exporter.

### Prévisualiser avant de créer

- Choisissez SHD, EVO ou COM et les sessions PRC autorisées. Un praticien peut exporter ses propres sessions et utiliser l’option de retrait du texte.
- Cliquez sur **Preview** : le contenu prévu est affiché sans créer d’export. Examinez les identifiants et les informations divulguées.
- Créez puis téléchargez le paquet. Conservez son empreinte et, le cas échéant, un point de contrôle émis séparément.

| Inclus selon le périmètre | Exclus |
|---|---|
| Événements compatibles, squelette du journal, objets privés sélectionnés et vues dérivées | Secrets d’accès, leurs empreintes de stockage et clés privées de signature |
| Tentatives, réflexions, retours et comparaisons déjà révélées dans les sessions choisies | Octets des lots en attente, extraits d’inspection et comparaisons non révélées |
| Identifiants des comptes et provenance | Toute prétention à l’anonymat du paquet |

### Vérifier dans un espace vierge

Utilisez la page de vérification et le parcours des paquets de modules. Fournissez un point de contrôle si disponible. Le vérificateur contrôle liens et objets, recalcule COM, EVO et SHD, puis évalue les signatures selon les racines de confiance propres à l’espace destinataire. Il n’importe rien dans l’état opérationnel des modules.

Une signature structurellement valide d’un signataire inconnu reste inconnue. L’autorisation actuelle est inconnue hors ligne ; un instantané ancien de confiance ne prouve pas qu’une approbation est encore valable. N’ajoutez pas une clé à la confiance sur la seule demande d’un paquet non fiable.

### Rôle du point de contrôle

Un administrateur peut émettre un checkpoint depuis Practice. Il signe une position et la dernière empreinte du journal. Conserver ce fichier séparément puis le fournir à la vérification permet de détecter une troncature ou une modification par rapport à cette position. Ce n’est ni une sauvegarde ni un mécanisme de restauration.

Un paquet valide permet de reproduire les opérations consignées. Il ne rend pas une affirmation vraie, ne transforme pas deux comptes en personnes indépendantes et ne prouve aucun progrès issu de la pratique.

## 17 Ingestion facultative de documents

Le serveur local ne récupère pas lui-même les dépôts. La CLI d’ingestion distincte peut télécharger un document depuis un hôte autorisé et en extraire un passage. Utilisez-la lorsque document, passage recherché et droits sont connus.

### Définir votre identité de requête SEC

Chaque exécution `--kind filing` contacte la SEC. Remplacez les deux valeurs fictives par votre nom et votre adresse de contact. Aucune identité n’est fournie à votre place.

```bash
export SEC_USER_AGENT="Your Name your.address@example.org"
```

Affectation équivalente dans PowerShell :

```powershell
$env:SEC_USER_AGENT = "Your Name your.address@example.org"
```

Une identité absente ou fictive entraîne un refus avant la requête. Elle est envoyée uniquement dans les en-têtes destinés aux hôtes SEC, jamais dans les sources ou exports. Les exemples fictifs et la vérification hors ligne n’en ont pas besoin.

### Compléter la commande pour un document

Ce modèle macOS/Linux n’est pas une requête réelle prête à exécuter. Remplacez chaque valeur entre chevrons. Utilisez le Python de l’environnement ; sous PowerShell, son chemin complet et tous les arguments sur une ligne.

```bash
python -m v8.workbench.ingest \
  --url '<https URL>' --kind filing --form '8-K EX-99.1' \
  --accession '<EDGAR accession>' --cik '<CIK>' \
  --pattern '<regex locating the passage>' \
  --rights SEC_PUBLIC_FILING \
  --out ~/yuclaw-ingest --label original
```

### Examiner et enregistrer

En cas de succès, inspectez `original.source.json`, `original.provenance.json` et les octets conservés. Vérifiez que l’extrait contient la déclaration voulue dans son contexte. Dans **1 Source → Register from an ingestion record**, collez le JSON et utilisez `retrieved_at` comme heure d’observation.

En cas de refus, lisez `[ingest] REFUSED: …`. Le code 2 signifie qu’aucun enregistrement source n’a été écrit. Corrigez le champ indiqué. Trouver du texte avec une expression régulière ne prouve pas qu’il étaye votre engagement.

Pour les autres types de sources et options, consultez `python -m v8.workbench.ingest --help`. N’attribuez pas `SEC_PUBLIC_FILING` à un contenu soumis à d’autres droits.

## 18 Dépanner en préservant l’historique

| Symptôme | Action |
|---|---|
| Commande absente ou mauvaise version | Utiliser l’exécutable du bon environnement et python -m pip show yuclaw avec le même interpréteur. |
| 127.0.0.1 inaccessible | Laisser serve actif. Lire l’erreur du terminal et vérifier le port ; en choisir un autre s’il est occupé, puis adapter l’URL. |
| Échec après redémarrage | Se reconnecter et recharger le formulaire ; ne pas réutiliser un ancien jeton. |
| Operation already recorded, HTTP 409 | Identifiant d’opération déjà utilisé avec un autre contenu. Rouvrir le formulaire, resélectionner le fichier et soumettre. Pas de récupération nécessaire. |
| Gel ou résultat refusé | Lire les champs cités : source, heure UTC, indicateur, période, unité, échelle, base et règle. |
| PENDING_OUTCOME ou INCOMPARABLE | Un élément absent ou incompatible est un état réel. Fournir des données justifiées ou garder cet état. |
| Isolation SHD indisponible | Consulter Setup. Admission fermée sous macOS/Windows ; sous Linux, une sonde réussie reste nécessaire. |
| Sélection périmée ou fichiers EVO modifiés | Recharger et sélectionner l’objet actuel ; enregistrer les fichiers modifiés comme nouvelle version EVO. |
| Permission de module refusée | Contrôler compte, capacités, approbation, séparation des contributeurs et budget. |
| Export MISMATCH ou UNSUPPORTED | Vérifier identité et type ; lire la première divergence sans modifier l’original. |

### Page Workspace integrity

Une écriture interrompue peut laisser un fragment final sans fin de ligne. Si la page diagnostique ce torn tail, **Run recovery** en conserve les octets séparément, retire uniquement le fragment et consigne la récupération. Répétez ensuite l’action interrompue.

```bash
yuclaw workbench recover --workspace ~/yuclaw-workspaces/research
```

Cette récupération vise le fragment diagnostiqué, pas toute erreur. Pour `E_HASH`, `E_CHAIN`, `E_SEQ` ou `E_CORRUPT_LINE`, arrêtez le serveur, préservez le dossier et examinez la cause. Ne supprimez pas de lignes pour faire réussir le contrôle.

La gestion des interruptions de processus ne garantit pas la survie à toute panne électrique. Un export interrompu n’est pas marqué complet : recréez-le. Une erreur d’intégrité doit rester visible jusqu’à compréhension de sa cause.

## 19 Référence des commandes et routes

Avec l’environnement activé, `yuclaw workbench …` et `python -m v8.workbench …` appellent le même programme. Adaptez chemins et identifiants. `--help` ne démarre aucun serveur.

### Commandes courantes

```bash
yuclaw workbench --help
yuclaw workbench guide
yuclaw workbench selftest --json
yuclaw workbench serve --workspace ~/yuclaw-workspaces/research --port 8765
yuclaw workbench status --workspace ~/yuclaw-workspaces/research
yuclaw workbench modules --workspace ~/yuclaw-workspaces/research
yuclaw workbench build-export --workspace ~/yuclaw-workspaces/research \
  --claim ZZFX-FY2026-REV-GUIDE--FIX-COMMIT-001-base
yuclaw workbench verify-export research-export.zip --json
```

### Gestion des accès par l’opérateur de l’hôte

```bash
yuclaw workbench principals rotate --workspace ~/yuclaw-workspaces/research \
  --id learner1
yuclaw workbench principals revoke --workspace ~/yuclaw-workspaces/research \
  --id learner1 --reason "Access ended"
```

Ces commandes agissent : la rotation émet un nouveau secret et la révocation est définitive. Pour consulter les comptes, utilisez `principals list`.

| Route locale | Fonction |
|---|---|
| /  ·  /source  ·  /claim/new | Espace, sources, nouvel engagement typé |
| /claim/\<claim id\> | Comparaison, calcul, historique, notes, examen et export |
| /notes  ·  /dataset  ·  /dataset.json | Notes et couverture de la collection |
| /sci  ·  /journal  ·  /help | Rejeu scientifique, événements et guide intégré |
| /modules  ·  /setup  ·  /login | Modules, configuration et connexion locale |
| /shd  ·  /shd/trust  ·  /evo | Admission, administration de la confiance et audit de réutilisation |
| /com  ·  /prc  ·  /modx  ·  /verify | Révision, pratique, export des modules et vérification |

Ces routes sont relatives au serveur local, normalement `http://127.0.0.1:8765`. L’espace vierge de l’exemple utilise le port 8766. Il ne s’agit pas de routes publiques promises sur yuclaw.ca.

Le paquet YUCLAW comprend aussi des commandes d’accès aux éléments publics et d’intégration. Consultez `yuclaw --help` pour votre version ; leurs services requis sont distincts de ce parcours local hors ligne.

## 20 Termes et documentation source

| Terme | Sens dans ce guide |
|---|---|
| Source / engagement / résultat | Le passage probant ; l’engagement typé ; le résultat déclaré séparément. |
| Gel / amendement | Préserver une version ; ajouter une version liée sans l’écraser. |
| Empreinte | Hachage identifiant des octets ou un contenu canonique ; l’égalité ne prouve pas la vérité. |
| Journal | Suite ordonnée d’actions liées par empreintes. L’accès au système de fichiers dépasse les rôles du navigateur. |
| Rétrospectif | Consigné avec recul ou connaissance ultérieure, sans contemporanéité établie. |
| Adjudication | Jugement enregistré avec règle, éléments et motif, distinct du calcul automatique. |
| Principal | Compte local doté de capacités, pas une personne réelle vérifiée. |
| Racine source | Identité documentaire utilisée pour regrouper ; un alias n’ajoute pas de corroboration indépendante. |
| Paquet de recherche ou de modules | Formats et périmètres différents ; la vérification doit correspondre au type. |
| Point de contrôle | Position signée du journal permettant de tester sa continuité, pas de le restaurer. |

### Références versionnées

Instructions fondées sur le guide opérateur, la CLI, le dictionnaire de données et les modules 8.0.1, recoupés avec l’exemple fictif fourni. La page d’accueil publique a été consultée pendant la préparation. Ce manuel n’est ni une nouvelle version du logiciel ni un audit de sécurité indépendant.

- [YUCLAW 8.0.1 sur PyPI](https://pypi.org/project/yuclaw/8.0.1/)
- [Publication YUCLAW 8.0.1](https://github.com/YuClawLab/yuclaw-brain/releases/tag/v8.0.1)
- [Guide opérateur versionné](https://github.com/YuClawLab/yuclaw-brain/blob/v8.0.1/v8/workbench/resources/OPERATOR_GUIDE.md)
- [Dictionnaire de données et fiche du jeu de données](https://github.com/YuClawLab/yuclaw-brain/blob/v8.0.1/v8/workbench/resources/DATA_DICTIONARY.md)
- [Code de la CLI et des modules](https://github.com/YuClawLab/yuclaw-brain/tree/v8.0.1/v8/workbench)
- [Contrat de validation des lots SHD](https://github.com/YuClawLab/yuclaw-brain/blob/v8.0.1/v8/workbench/modules/shield_worker.py)
- [Contrat de configuration EVO](https://github.com/YuClawLab/yuclaw-brain/blob/v8.0.1/v8/workbench/modules/evolution.py)

Pour signaler un problème, indiquez version, système, action exacte, résultat attendu, résultat obtenu et reproduction fictive minimale. Retirez secrets et éléments privés. Utilisez le canal disponible du dépôt ; l’envoi reste une action distincte que vous choisissez.

Les deux éditions couvrent la même version et gardent des exemples de commandes exécutables identiques. Elles ne modifient ni règles, ni permissions, ni enregistrements du logiciel.

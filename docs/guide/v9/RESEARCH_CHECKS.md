# Research verification corrections — development branch

Research and education only. Not investment advice.

These changes are not in the published 9.0.0 wheel. They require the corrected
checkout or an artifact built from it. The existing v9 brief workflow is described
in [English](GUIDE_EN.md) and [French](GUIDE_FR.md).

## English

The revised replay command checks all fields in the core expected statistical
tables, nonempty daily anchors, leaf membership and forward analysis scores
against ledger leaves. A matching bundle remains an internal reproduction.
Obtain the public ledger separately and obtain its SHA-256 from a trusted,
independent channel before requesting external verification:

```sh
yuclaw replay-lab lab_replay_bundle.json
yuclaw replay-lab lab_replay_bundle.json \
  --ledger verified_research_ledger.jsonl \
  --ledger-sha256 INDEPENDENTLY_OBTAINED_SHA256 \
  --require-external-ledger
```

Exit 0: requested checks passed. Exit 1: invalid input or mismatch. Exit 2:
usage error. Exit 3: bundle fetch failed. Exit 4: required external coverage is
incomplete. The legacy public bundle includes additional intraday snapshots
outside one daily anchor. This is reported, not repaired by rewriting history.
Vendor-derived returns and in-sample reconstruction are not independently
authenticated by the signal ledger.

For a point-in-time dataset, download a complete history and its matching
manifest. The export refuses previews, mixed builds and dates outside the corpus:

```sh
yuclaw research-export --ticker DELL --as-of 2026-08-01 \
  --history DELL.history.json --manifest history_manifest.json \
  --out dell-as-of-2026-08-01
```

The output directory must not exist. It contains CSV, exact JSON, a data dictionary,
source files and a manifest with file hashes. Date-only cutoffs mean end-of-day
UTC. CSV protects formula-like cells; JSON retains exact strings and nulls.
Recorded availability is not necessarily the filing's publication time.

The Why pages distinguish event objects from distinct accessions and disclose
missing accessions. These counts do not estimate independent information or a
system failure rate. Component anatomy reports normalized confidence-weighted
contributions when recorded inputs exist. Legacy weights are labelled as a
current-configuration reconciliation; missing inputs yield INCOMPLETE.

An earnings-comparison screen checks whether the published excerpt explicitly
mentions a comparison with expectations. TEXTUAL_COMPARISON_ONLY is not independent
verification. The prospective SourceLock R10 rule rejects an unsupported beat/miss
classification; ordinary results use EARNINGS_RESULT. This changes future admission
criteria and must be recorded at deployment before collecting a new evaluation
window. Historical event classifications, signal scores, packets and registry
records are retained. The Suncor display carries a correction; its profitability
excerpt does not establish an expectations comparison.

The mobile gate now serves the docs directory explicitly and checks HTTP status
and response bytes before measuring layout. A fitting error page cannot pass.

## Français

La commande de réplication corrigée contrôle tous les champs des tableaux
statistiques principaux attendus, la présence des ancrages quotidiens, leurs
feuilles et la correspondance des scores utilisés avec les feuilles du registre.
Une réplication interne ne prouve pas la provenance externe. Obtenez séparément
le registre public et son SHA-256 par un canal indépendant de confiance, puis
utilisez les mêmes commandes ci-dessus avec `--require-external-ledger`.

Codes de sortie : 0, contrôles demandés réussis ; 1, entrée invalide ou divergence ;
2, erreur d’utilisation ; 3, téléchargement impossible ; 4, couverture externe
requise incomplète. Le paquet historique contient des instantanés intrajournaliers
supplémentaires hors d’un ancrage quotidien. Cette limite est signalée sans
réécriture de l’historique. Le registre n’authentifie pas indépendamment les
rendements dérivés des fournisseurs ni la reconstruction rétrospective.

`research-export` produit un ensemble d’information à date fixe à partir d’un
historique complet et de son manifeste correspondant. La commande ci-dessus est
identique en français. Elle refuse les aperçus, les constructions incohérentes et
les dates hors du corpus. Le répertoire cible doit être nouveau. Il contient le
CSV, le JSON exact, le dictionnaire, les fichiers sources et un manifeste avec
leurs empreintes. Une date seule signifie la fin de cette journée en UTC. Le CSV
neutralise les cellules ressemblant à des formules ; le JSON conserve les chaînes
et valeurs nulles exactes. La disponibilité enregistrée peut être postérieure à
la publication du dépôt.

Les pages Why distinguent objets événementiels et numéros de dépôt uniques,
signalent les numéros manquants et ne présentent pas ces comptes comme des
observations indépendantes ou un taux de défaillance. L’anatomie du score présente
les contributions normalisées par la confiance lorsque les entrées enregistrées
existent. Les poids issus de la configuration actuelle restent identifiés comme
tels ; les entrées manquantes donnent INCOMPLETE.

Le contrôle des résultats exige une comparaison explicite avec les attentes dans
l’extrait. TEXTUAL_COMPARISON_ONLY ne vaut pas vérification indépendante. La règle
prospective SourceLock R10 refuse les classifications beat/miss non étayées ; un
résultat ordinaire utilise EARNINGS_RESULT. Le changement des critères d’admission
doit être consigné au déploiement avant une nouvelle fenêtre d’évaluation.
Les classifications historiques, scores, paquets et registres sont conservés.
L’exemple Suncor comporte une correction : l’extrait de rentabilité ne démontre
pas une comparaison avec les attentes.

Enfin, le contrôle d’affichage sert explicitement le dossier docs et vérifie le
statut HTTP ainsi que les octets reçus. Une page d’erreur ne peut plus réussir le
contrôle uniquement parce qu’elle tient dans la fenêtre.

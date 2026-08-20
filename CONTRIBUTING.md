# Contribuer à France Transparence

Merci de vouloir aider. Ce document explique comment signaler une erreur,
proposer une source, installer le projet et soumettre du code. Il explique
surtout le **pourquoi** des règles : sur un site dont l'honnêteté est le
principe produit, la plupart des refus ne portent pas sur la qualité du code,
mais sur ce que le code fait dire aux données. Lire ce document avant d'ouvrir
une proposition de fusion évite du travail perdu des deux côtés.

Trois portes d'entrée, par ordre de probabilité :

1. **Une donnée affichée est fausse** → [§ 1](#1-signaler-une-erreur-de-donnée--le-cas-le-plus-probable), gabarit d'issue « Erreur dans une donnée affichée ».
2. **Une source mériterait d'être ingérée** → gabarit « Proposition de source » (lire d'abord la règle licence, [§ 4](#4-les-règles-non-négociables)).
3. **Un bogue de code, une amélioration** → gabarit « Bogue », ou proposition de fusion ([§ 2](#2-installer-et-vérifier) et suivants).

Une faille de sécurité ne passe **jamais** par une issue publique :
[SECURITY.md](SECURITY.md).

---

## 1. Signaler une erreur de donnée — le cas le plus probable

C'est la contribution la plus utile, et celle qui demande le raisonnement le
plus précis. Point de départ obligatoire : **une issue** avec le gabarit
« Erreur dans une donnée affichée », toujours accompagnée d'une **source
officielle** (URL du producteur : data.gouv.fr, HATVP, DILA, assemblées,
CNCCFP…). Sans source opposable, personne ne peut trancher entre « le site se
trompe » et « le site déplaît ».

Pourquoi une issue et pas une correction directe : **aucune donnée ne vit dans
ce dépôt**. La base `data/france.db` est gitignorée et entièrement reconstruite
par `make ingest` depuis les sources amont ; le site public est rebâti chaque
matin sur cette base neuve. Modifier un chiffre « à la main » est donc
matériellement impossible — et ce serait contraire au principe du projet :
aucun chiffre fabriqué, même pour corriger.

L'issue sert à établir le diagnostic, qui n'a que deux issues possibles :

- **La valeur affichée diffère de ce que publie la source amont** → c'est un
  bogue de pipeline (encodage, dédoublonnage, jointure, unité) ou
  d'affichage. Il se corrige ici, dans le code, avec un test qui fige le cas
  dans `pipelines/tests/fixtures/`.
- **La valeur affichée est conforme à la source amont, mais l'amont est
  faux** → corriger le site ne servirait à rien : la prochaine ingestion
  réécrirait l'erreur. Le signalement doit remonter au producteur de la
  donnée (la plupart des jeux data.gouv.fr ont un canal de discussion). Le
  dépôt peut, au mieux, documenter la limite — jamais « rectifier » une
  donnée officielle de sa propre autorité, ce qui reviendrait à fabriquer un
  chiffre.

Une demande qui concerne une **personne** (rectification de données vous
concernant) n'a pas à être rendue publique : elle passe par le canal privé
indiqué sur la page [/donnees-personnelles](https://francetransparence.fr/donnees-personnelles/)
du site.

## 2. Installer et vérifier

Prérequis : `python3.14`, Node.js ≥ 24, `make` (voir le
[README](README.md), qui fait foi pour le démarrage rapide).

```bash
make venv         # crée .venv et installe requests, duckdb, pytest
make test         # suite pytest complète
make ingest       # reconstruit data/france.db depuis les sources amont
make app-install  # npm install dans app/
make dev          # http://localhost:3620
```

Précisions utiles à un contributeur :

- **Les tests d'abord, l'ingestion ensuite.** `make test` tourne sans base et
  sans réseau pour l'essentiel : les tests de transformation travaillent sur
  des extraits réels figés dans `pipelines/tests/fixtures/` (pièges
  d'encodage inclus) et sur des bases temporaires jetables. Les tests
  d'intégration qui téléchargent réellement les sources portent le marqueur
  `reseau` — pour itérer vite : `.venv/bin/pytest pipelines/tests -m 'not reseau'`.
- **`make ingest` télécharge beaucoup** (les volumes et durées indicatifs
  sont dans le README) et met les bruts en cache dans `data/raw/` : la
  commande est rejouable à volonté. Pour ne rejouer qu'un pipeline :
  `make ingest-<source>`, la liste des `<source>` valides étant la variable
  `PIPELINES` du `Makefile` — c'est elle qui fait autorité, pas la
  documentation.
- **Travaillez toujours sur une base à vous**, produite par votre propre
  `make ingest`. Par défaut tout passe par `data/france.db` ; pour désigner
  une autre base : `FT_DB_PATH` côté pipelines et tests, `FRANCE_DB_PATH`
  côté app. Ne pointez jamais un test ou un pipeline vers une base servie
  en production : les pipelines écrivent en remplaçant leurs tables.
- **Build de l'app** : `make build` (serveur Next) ou `make build-static`
  (export statique `FT_EXPORT=1`, la forme réellement servie en production).
  Une modification de l'app doit au minimum passer `make build`.

La CI (`.github/workflows/publication.yml`) rejoue la chaîne — ingestion
(complète, ou depuis la base en cache si son schéma correspond), tests, build
statique, contrôles de santé — sur chaque proposition de fusion, **avant**
`main` : c'est `main` qui alimente le serveur de production, rien
d'expérimental ne doit l'atteindre.

## 3. Proposer du code

- **Une proposition de fusion = un sujet.** Les correctifs mêlés sont plus
  longs à relire et bloquent la partie acceptable derrière la partie
  discutée.
- Pour tout changement non trivial, **ouvrez une issue d'abord** : le
  périmètre du projet est délibérément étroit (voir § 5), et il serait
  dommage de développer une fonctionnalité qui sera refusée par principe.
- Un correctif de pipeline s'accompagne d'un **test** qui reproduit le cas —
  de préférence hors ligne, sur un extrait figé dans
  `pipelines/tests/fixtures/`.
- Indiquez dans la proposition **ce que vous avez réellement joué** (`make
  test`, `make build`…) : le gabarit le demande, et la revue commence par là.
- Le français est la langue du dépôt : code commenté en français, messages de
  commit en français, expliquant le pourquoi.

## 4. Les règles non négociables

Elles font refuser du code par ailleurs correct, parce qu'elles **sont** le
produit : ce site n'a de valeur que si ce qu'il affiche est exactement aussi
solide que ce qu'il prétend.

1. **Une donnée manquante s'affiche comme manquante, jamais comme un zéro.**
   Un zéro est une affirmation (« il n'y a rien ») ; une absence est un fait
   (« la source ne le dit pas »). Les confondre fabrique un chiffre. Un champ
   absent reste NULL en base, et l'interface dit « non publié » ou « non
   disponible ».
2. **Aucune source portant une clause de partage à l'identique n'est ingérée**
   (ODbL, CC BY-SA…). Les agrégats du site sont réutilisables sous la
   promesse de la Licence Ouverte 2.0 ; mêler dans la même base une source
   share-alike contaminerait cette promesse pour tout le monde. Une telle
   source peut être **citée et liée**, jamais ingérée.
3. **Aucun superlatif, aucune affirmation d'inexistence ou d'antériorité**
   (« le plus gros contrat », « jamais publié ailleurs », « premier site
   à… ») : invérifiables par construction, ces phrases engagent le site sur
   ce qu'il ne mesure pas.
4. **Le mot « en direct » est banni.** Aucune source publique ne le permet ;
   la formule honnête est la date réelle des données, affichée.
5. **Chaque module date ses données.** Le badge « Données au JJ/MM/AAAA ·
   source · fréquence » vient de la table `meta_sources`, alimentée à chaque
   ingestion réussie : la fraîcheur est une donnée de premier rang, jamais un
   texte décoratif. Un nouveau module ou une nouvelle source sans ligne
   `meta_sources` sera refusé.
6. **Deux grandeurs de nature différente ne sont jamais juxtaposées comme
   comparables** — un maximum contractuel d'accord-cadre n'est pas une
   dépense, un budget voté n'est pas une exécution, une fourchette déclarée
   n'est pas un montant. Les mettre côte à côte dans un même graphique ou un
   même total suggère une comparaison que la donnée ne porte pas.
7. **Aucune donnée personnelle au-delà de ce qu'énumère la page
   [/donnees-personnelles](https://francetransparence.fr/donnees-personnelles/)**
   du site. Cette page est l'engagement public du projet (catégories de
   données, exclusions — dont le contenu des déclarations de patrimoine,
   pénalement protégé) ; tout code qui publierait une catégorie
   supplémentaire le briserait, quelle que soit la licéité de la source.

En cas de doute sur l'esprit d'une règle : `docs/SOURCES.md` (le périmètre et
les pièges des sources) et `docs/ARCHITECTURE.md` (le flux de données et ses
invariants) sont les références.

## 5. Ce qui sera refusé

- Toute violation d'une règle du § 4, même élégamment codée.
- **Une correction de donnée par modification directe d'une valeur** (voir
  § 1 : les données ne vivent pas dans le dépôt).
- Un chiffre écrit en dur dans la documentation ou l'interface alors qu'il
  dérive à chaque ingestion : la seule valeur qui fait foi est celle que le
  site calcule et date lui-même.
- Une dépendance runtime qui appelle un service externe depuis l'app : l'app
  ne lit que `data/france.db`, c'est la condition d'une fraîcheur honnête.
- Du scraping de sites qui l'interdisent ou le bloquent (Légifrance,
  budget.gouv.fr… — voir `docs/SOURCES.md` § 0) : on passe par les jeux de
  données, pas par le HTML.
- Toute forme d'éditorialisation politique : le site publie des données
  sourcées et leurs règles de calcul, pas des opinions. Les alertes elles-
  mêmes citent leur règle et leur base légale.
- Une contribution sans `Signed-off-by` (§ 6), après demande restée sans
  suite.

## 6. Certificat d'origine (DCO)

Chaque commit d'une contribution doit porter une ligne :

```
Signed-off-by: Prénom Nom <adresse@exemple.org>
```

que `git commit -s` ajoute automatiquement. Elle vaut certification du
[Developer Certificate of Origin 1.1](https://developercertificate.org/) : vous
affirmez avoir le droit de soumettre ce code sous la licence du projet.

Pourquoi cette exigence, et pourquoi elle suffit : le dépôt est sous
**AGPL-3.0-or-later**, et les contributions sont acceptées **sous la même
licence** — entrant = sortant, personne ne cède rien de plus que ce que la
licence donne déjà à tous. Il n'y a donc pas de contrat de cession (CLA) à
signer ; le DCO est la trace légère et suffisante que l'origine du code est
saine. Un commit oublié se répare par `git commit --amend -s` (ou un rebase)
suivi d'un push forcé sur votre branche.

## 7. Sécurité

Une vulnérabilité se signale en **privé**, jamais par issue ni proposition de
fusion publiques : [SECURITY.md](SECURITY.md).

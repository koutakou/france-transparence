# France Transparence

Site d'information sur l'argent public et la vie politique en France, en ligne sur **https://francetransparence.fr**. Il rassemble des publications de l'État, des assemblées et des autorités indépendantes, et affiche pour chacune son producteur, sa licence et la date réelle de ses données.

Les données viennent de **sources publiques officielles, plus quelques consolidations reconnues et créditées**. Elles sont étiquetées comme telles sur la page [`/donnees`](https://francetransparence.fr/donnees/) (voir « D'où viennent les données »).

Le site publie des données et leurs règles de calcul. Il ne porte aucun jugement sur les personnes. Un indicateur dit ce qu'il mesure, avec sa règle et sa base légale, et rien de plus.

## Ce que montre le site

Onze onglets, dans l'ordre de la navigation (`app/src/components/MainNav.tsx`) :

| Route | Onglet | Contenu |
|---|---|---|
| `/` | Accueil | Synthèse des modules, chaque bloc daté par sa source |
| `/depenses` | Dépenses | Exécution mensuelle du budget de l'État (DGFiP), structure du projet de loi de finances, agrégats des administrations publiques |
| `/recettes` | Recettes | Recettes nettes du budget général, impôt sur le revenu par territoire, prélèvements obligatoires |
| `/marches` | Marchés publics | Marchés notifiés, appels d'offres en cours (BOAMP), achats à venir, sanctions de l'Autorité de la concurrence dans un bloc séparé |
| `/elus` | Élus & Institutions | Répertoire national des élus, députés, sénateurs, annuaire et fiches |
| `/lobbying` | Lobbying | Répertoire HATVP des représentants d'intérêts, et registre de transparence de l'Union européenne dans un bloc séparé |
| `/financement` | Financement | Comptes des partis et comptes de campagne (CNCCFP) |
| `/frais` | Frais | Barèmes et contrôles publiés, et ce que la loi ne publie pas |
| `/collectivites` | Finances locales | Comptes des collectivités (OFGL), dotations, fiscalité directe locale |
| `/documents` | Documents | Textes des derniers Journaux officiels, dossiers législatifs |
| `/donnees` | Données | Catalogue des sources, fraîcheur mesurée, licences, exports JSON |

Hors navigation : `/alertes` (indicateurs calculés, chacun avec sa règle), `/comprendre` (comment lire ces publications), `/elus/annuaire/` et les fiches `/elus/<id>/`, `/documents/dossiers/`, `/mentions-legales` et `/donnees-personnelles`.

Les volumes (nombre d'élus, de marchés, de textes) changent à chaque ingestion. Ils ne sont pas recopiés ici : la seule valeur qui fait foi est celle que le site affiche, avec la date de ses données.

## D'où viennent les données

**44 sources**, une ligne chacune dans la table `meta_sources` de la base et dans le catalogue de [`/donnees`](https://francetransparence.fr/donnees/), reconstruit à chaque publication. Le référentiel (périmètre, pièges, limites de chaque source) est [docs/SOURCES.md](docs/SOURCES.md).

Producteurs principaux : DILA (Journal officiel, BOAMP, dossiers législatifs), Assemblée nationale, Sénat, HATVP, ministère de l'Intérieur (Répertoire national des élus), DGFiP, OFGL, CNCCFP, CADA, INSEE, DREES, Eurostat, Autorité de la concurrence, registre de transparence de l'Union européenne.

Trois sources ne sont pas des publications officielles au sens strict. `/donnees` le dit à côté de chacune (`app/src/lib/nature-sources.ts`) :

| Source | Étiquette sur `/donnees` | Ce que c'est |
|---|---|---|
| S1 | Consolidation reconnue, non officielle | Consolidation des données essentielles des marchés publics (DECP) par le projet `decp-processing` de Colin Maudry |
| S7 (Datan) | Consolidation reconnue, non officielle | Scores calculés par l'association Datan à partir des données de l'Assemblée nationale, affichés à côté du taux calculé par le site |
| S31 | Officielle, recopiée à la main | Chiffres recopiés de documents officiels (textes, rapports, PDF publics), sans jeu de données ouvert lisible par machine, chacun cité avec son adresse |

Rien n'est mis à jour « en direct » : aucune source publique ne le permet. Chaque page dit la date de ses données, et la fraîcheur de chaque source est mesurée contre un seuil (`app/src/lib/fraicheur.ts`).

## Comment c'est construit et publié

1. `pipelines/` (Python) télécharge les sources dans `data/raw/` et les transforme. Chaque pipeline est une cible `make ingest-<nom>`. La liste fait autorité dans la variable `PIPELINES` du `Makefile` (`make pipelines` l'affiche).
2. Tout aboutit dans une seule base SQLite, `data/france.db`, qui n'est pas versionnée. Chaque ingestion réussie écrit sa ligne dans `meta_sources` (date des données, licence, fréquence).
3. L'application Next.js (`app/`) lit cette base en lecture seule et produit un **export statique** (`FT_EXPORT=1`) : toutes les pages sont écrites au build, sans appel réseau à l'exécution.
4. En production, **nginx sert cet export**. Aucun processus Node ne tourne.

**Publication.** Le serveur reconstruit le site chaque nuit vers 05:17, heure de Paris (minuterie systemd `ft-deploy.timer`, décalage aléatoire de 10 minutes au plus). Le script `ft-deploy` met le dépôt à jour, vérifie l'identité de déploiement, ingère toutes les sources, joue les tests, construit l'export, le contrôle, puis bascule le lien `current` vers la nouvelle version. Si une étape échoue, rien ne bascule : la version précédente reste servie et une alerte part. Ces scripts vivent sur le serveur et ne sont pas versionnés ici. Leur description publique est le [RUNBOOK](docs/deploiement/RUNBOOK.md).

**Validation.** La CI GitHub (`.github/workflows/publication.yml`) ne publie rien. Chaque jour à 04:45 UTC, donc après le cycle du serveur, elle rejoue la chaîne complète dans une base neuve : ingestion, tests, lint, types, build, contrôles. Sur chaque proposition de fusion, elle joue les mêmes étapes avant que le code n'atteigne `main`, en réutilisant la base en cache quand l'empreinte des pipelines n'a pas changé. Un second workflow, `vigie.yml`, lit le site en ligne une fois par jour et ouvre une issue s'il est figé.

L'ancienne adresse GitHub Pages ne porte plus qu'une page de redirection vers le domaine (`pages-redirection/`).

## Reproduire en local

Prérequis : Python 3.14 (celui du `Makefile`, de la CI et du serveur), Node.js 24 ou plus (celui de la CI), `make`.

```bash
make venv          # crée .venv avec les versions figées de requirements.txt
make ingest        # télécharge toutes les sources et construit data/france.db
make app-install   # installe les dépendances de app/
make dev           # http://localhost:3620
```

`make ingest` télécharge beaucoup et prend du temps : les fichiers bruts restent en cache dans `data/raw/`, et la commande se rejoue sans risque. Un seul pipeline : `make ingest-<nom>`.

La forme servie en production se reproduit ainsi :

```bash
make build-static  # export statique dans app/out/
make serve-static  # le sert sur http://localhost:3620
```

Pour publier sous une autre adresse, poser `NEXT_PUBLIC_SITE_URL` et les variables `NEXT_PUBLIC_HEBERGEUR_*` au build (`app/src/lib/hebergeur.ts`) : aucune source n'est à modifier.

## Tests

```bash
make test                                         # pipelines, suite pytest complète
.venv/bin/pytest pipelines/tests -m 'not reseau'  # sans les tests qui touchent le réseau
cd app && npm test && npm run lint && npm run typecheck
```

Les tests de transformation tournent hors ligne sur des fixtures figées dans `pipelines/tests/fixtures/`. La CI joue aussi les tests des pipelines sous Python 3.10 (job `tests-python-3-10`).

## Licences

- **Code** : AGPL-3.0-or-later ([LICENSE](LICENSE)).
- **Données** : chaque source garde la licence de son producteur, pour l'essentiel la Licence Ouverte 2.0 (Etalab). La licence de chaque source est affichée sur `/donnees`. S31 n'a pas de licence ouverte : ce sont des chiffres cités de documents officiels. Détails : [LICENSES.md](LICENSES.md).

## Signaler une erreur, contribuer

- **Une donnée affichée est fausse** : ouvrir une issue avec le gabarit « Erreur dans une donnée affichée », en joignant la source officielle. Aucune donnée ne vit dans le dépôt : la correction passe par le pipeline, ou par un signalement au producteur si c'est l'amont qui se trompe.
- **Une demande qui vous concerne personnellement** : jamais par issue publique, par le canal indiqué sur [/donnees-personnelles](https://francetransparence.fr/donnees-personnelles/).
- **Une faille de sécurité** : en privé, voir [SECURITY.md](SECURITY.md).
- **Du code, une source à proposer** : [CONTRIBUTING.md](CONTRIBUTING.md), qui donne aussi les règles qui font refuser une contribution.

## Documentation

- [STATUS.md](STATUS.md) : état courant. [JOURNAL.md](JOURNAL.md) : décisions datées.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) : flux de données et invariants. [docs/SCHEMA-DB.md](docs/SCHEMA-DB.md) : schéma de la base.
- [docs/deploiement/RUNBOOK.md](docs/deploiement/RUNBOOK.md) : exploitation du serveur. [docs/deploiement/DECISION.md](docs/deploiement/DECISION.md) : choix d'hébergement.
- [docs/ACTIONS-HUMAINES.md](docs/ACTIONS-HUMAINES.md) : ce qui demande un geste sur le serveur ou sur GitHub.
- [docs/REDIRECTIONS-ELUS.md](docs/REDIRECTIONS-ELUS.md) : redirections des fiches d'élus fusionnées.
- [docs/RAPPORT-MISSION.md](docs/RAPPORT-MISSION.md) : journal de construction des 19 et 20/08/2026, daté et non réécrit.

"""P3 — DECP marchés publics : ingestion du parquet consolidé (source S1).

Source (docs/SOURCES.md, fiche S1 ; détail docs/recherche/02-commande-publique.md) :
consolidation communautaire des Données Essentielles de la Commande Publique
au format tabulaire (projet `decp-processing`, Colin Maudry), ~53 sources
officielles, parquet ~243 Mo mis à jour quotidiennement sur data.gouv.fr.
Mode nominal : parquet local lu par DuckDB (l'API tabulaire, en bêta, n'est
qu'un raccourci de secours — non utilisée ici). Licence Ouverte 2.0, crédit
de la consolidation obligatoire à l'affichage.

Exécution : `python -m pipelines.ingest_decp`
(FT_DB_PATH redirige la base pour les épreuves ; défaut data/france.db).

Tables produites (module UI « Commande publique » + carte de France + Accueil) :

- decp_marches — 1 ligne par marché (uid), notifiés sur les 24 derniers mois
  (date de la notification INITIALE, cf. règle de datation plus bas),
  attributs pris sur la version courante (donneesActuelles = true,
  dédoublonnage uid) :
  uid (PK), id, objet, montant (brut), montant_rationalise,
  montant_retenu (= montant_rationalise sinon montant — valeur à afficher),
  montant_anomalie ('suspect'/'aberrant'/NULL, classification de la source),
  montant_suspect (0/1, cf. règle d'écrêtage), acheteur_siret, acheteur_nom,
  acheteur_departement_code, acheteur_departement_nom, titulaire_siret,
  titulaire_nom (titulaire principal = plus petit SIRET, déterministe),
  nb_titulaires, titulaires_json (JSON [{siret, nom}, …] trié par SIRET),
  date_notification (ISO — notification initiale, cf. règle de datation),
  duree_mois, procedure, nature, type_marche
  (Travaux/Services/Fournitures), techniques (chaîne source, multi-valeurs
  séparées par des virgules — contient « Accord-cadre » quand le montant est
  un maximum, l'UI doit le mentionner), code_cpv (libellé CPV non fourni par
  S1), lieu_execution_code, lieu_execution_typecode (libellé non fourni par
  S1 ; granularité mixte — la carte utilise acheteur_departement_code).
  NB : depuis le schéma réglementaire 2022, nature vaut « Marché » pour la
  quasi-totalité des lignes récentes ; le caractère accord-cadre se lit dans
  techniques (~132 k marchés sur 12 mois), pas dans nature.

- decp_agg_departement — agrégat CARTE, 12 derniers mois, marchés dont
  l'acheteur a un département connu : departement_code (PK), departement_nom,
  nb_marches, montant_total (somme des montants retenus ÉCRÊTÉS — jamais
  écrasable par une saisie aberrante), nb_marches_ecretes.

- decp_agg_mois — série mensuelle, 36 derniers mois civils :
  mois (PK, 'YYYY-MM'), nb_marches, montant_total (écrêté).

- decp_top_acheteurs / decp_top_titulaires — 12 derniers mois, top 50,
  regroupés par ENTREPRISE (SIREN = 9 premiers chiffres du SIRET) et non par
  établissement : rang (PK), siren, nom, categorie (titulaires seulement,
  PME/ETI/GE si connue), nb_etablissements (SIRET distincts regroupés),
  nb_marches (marchés DISTINCTS — un marché ne compte qu'une fois même si
  deux établissements du même SIREN y sont co-titulaires), montant_total
  (écrêté ; pour les titulaires, montant du marché divisé par le nombre de
  co-titulaires). POURQUOI par entreprise : agrégé par établissement, un
  groupe à réseau local est émietté en autant de lignes qu'il a de SIRET —
  aucune ne franchit le seuil d'entrée, et le groupe disparaît du classement
  dont il serait pourtant le premier. Seuls les identifiants CONFORMES
  (exactement 14 chiffres) entrent au classement ; les autres sont écartés
  ET comptés (cf. decp_titulaires_qualite). `nom` et `categorie` sont les
  libellés DÉCLARÉS dans le DECP, choisis de façon déterministe (le plus
  fréquent parmi les lignes du SIREN, ex æquo départagés par ordre
  alphabétique) : ce sont des REPLIS, le libellé de référence Sirene est
  joint côté requête et non écrit ici — nommer depuis ce pipeline créerait
  un couplage d'écriture entre pipelines.

- decp_titulaires_qualite — UNE ligne (id = 1), même fenêtre 12 mois : ce que
  le regroupement par entreprise retient et ce qu'il écarte. nb_marches (par
  construction égal à decp_qualite_montants.nb_marches),
  nb_marches_avec_titulaire, nb_lignes (couples marché × titulaire),
  nb_lignes_identifiables / nb_lignes_ecartees et les deux montants
  correspondants, nb_identifiants_ecartes, nb_sirets, nb_sirens,
  nb_sirens_multi_etab (SIREN portant plus d'un SIRET titulaire). Invariants
  publiés avec la table : nb_lignes = identifiables + écartées, et de même
  pour les montants ; nb_sirets + nb_identifiants_ecartes = nombre
  d'identifiants titulaires distincts de la fenêtre. Sert à dire au lecteur
  combien de titulaires le classement ne peut pas nommer, au lieu de les
  laisser figurer sous un identifiant-rebut sans nom.

- decp_acheteurs_qualite — UNE ligne (id = 1), même fenêtre 12 mois : le
  pendant de la précédente pour les acheteurs. nb_marches (même source, donc
  même valeur, que decp_qualite_montants.nb_marches),
  nb_marches_avec_acheteur (acheteur renseigné, conforme ou non),
  nb_marches_identifiables / nb_marches_ecartes et les deux montants
  correspondants, nb_identifiants_ecartes, nb_sirets, nb_sirens,
  nb_sirens_multi_etab. POURQUOI cette table est PLUS COURTE que celle des
  titulaires, et non son décalque : un marché n'a qu'UN acheteur
  (`acheteur_siret` est scalaire à la source), le couple marché × acheteur
  n'existe donc pas — l'unité de compte est le MARCHÉ, et inventer une ligne
  « couple » par symétrie ferait croire à un dénombrement qui n'a pas d'objet.
  Invariant publié avec la table : nb_marches_avec_acheteur =
  identifiables + écartés (et NON nb_marches, dont il se distingue des
  marchés sans acheteur renseigné), et de même pour les montants.
  POURQUOI une table à part plutôt que des colonnes de plus dans
  decp_titulaires_qualite : y loger des compteurs d'acheteurs ferait mentir
  son nom. Et pourquoi la tenir alors que les acheteurs écartés se comptent
  sur les doigts, quand les titulaires écartés se comptent par milliers : la
  règle « on écarte et on compte » ne se mesure pas à l'ampleur du phénomène
  — ce qui est interdit, c'est la disparition sans compteur. Le jour où ce
  nombre grossit, le compteur existe déjà.

- decp_repartition — 12 derniers mois : dimension ('procedure'|'nature'),
  valeur (libellé le plus fréquent après normalisation casse/accents ;
  NULL = non renseigné à la source), nb_marches, montant_total (écrêté).

- decp_qualite_montants — UNE ligne (id = 1), même fenêtre 12 mois et même
  vue `recents` que decp_repartition : nb_marches, montant_total (écrêté),
  nb_ecretes / montant_ecretes (marchés au-delà du plafond, tous acheteurs —
  à ne pas confondre avec SUM(nb_marches_ecretes) de decp_agg_departement,
  qui n'en couvre que les acheteurs à département connu), nb_suspects /
  montant_suspects, montant_hors_suspects, montant_brut (sans écrêtage),
  nb_sans_montant, plafond. Sert à dire au lecteur ce que vaut le total
  affiché : quelle part vient d'un plafond arbitraire, quelle part d'un
  montant marqué suspect. montant_hors_suspects est une BORNE BASSE — le
  drapeau montant_suspect n'a pas été audité ligne à ligne.

- decp_derniers_marches — flux « derniers marchés notifiés » : les 200 plus
  récents de decp_marches, colonnes identiques précédées de rang (PK).

- decp_publication_qualite / decp_publication_annees /
  decp_publication_acheteurs — respect du délai légal de publication, sur
  TOUTE la profondeur du parquet et non sur une fenêtre glissante (cf. règle
  de mesure du délai plus bas).

Règle de mesure du délai de publication (les trois tables decp_publication_*) :
1. Population = tous les uid du parquet, sans borne de date : la question est
   historique, elle se lit d'une année sur l'autre. Ces trois tables sont donc
   calculées par une passe SÉPARÉE, qui ne partage aucune table intermédiaire
   avec les agrégats ci-dessus — ceux-ci sont bornés (détail, agrégats, série)
   et donneraient des taux calculés sur un reste arbitraire.
2. notification = min(dateNotification) sur toutes les lignes du uid (la
   notification INITIALE, même règle que pour les autres tables) ;
   publication = min(datePublicationDonnees) sur toutes les lignes (la
   PREMIÈRE mise en ligne — une republication lors d'un avenant ne défait pas
   une publication faite à temps) ; délai = écart en jours entre les deux.
3. Publié dans le délai légal ⇔ publication <= notification + 2 MOIS
   calendaires. Écrit en mois et non en « 60 jours » : voir DELAI_LEGAL_MOIS.
4. Un marché n'est RETENU que si ses deux dates existent, tiennent dans
   [BORNE_DATE_MIN, BORNE_DATE_MAX] et sont dans l'ordre. Les autres sont
   classés en catégories EXCLUSIVES (sans notification, sans publication,
   dates hors bornes, publication antérieure à la notification) et comptés
   dans decp_publication_qualite : la somme des cinq classes recompose
   exactement la population de départ. Aucun n'est repêché avec un délai de
   zéro — un défaut de saisie n'est pas une publication à l'heure.
5. Une cohorte annuelle n'est CLOSE qu'au bout de DECALAGE_COHORTE_CLOSE
   années ; les cohortes ouvertes sont publiées avec cohorte_close = 0, leur
   dénominateur étant incomplet. La ventilation par catégorie d'acheteur ne
   porte que sur les cohortes closes, et seulement sur les marchés dont la
   catégorie est renseignée — les autres sont comptés dans nb_sans_categorie.

Règle d'écrêtage des montants (documentée aussi en colonne montant_suspect) :
1. montant_retenu = montant_rationalise si présent, sinon montant. La source
   ne corrige que la classe 'aberrant' (ex. réel : 100 Md€ → 115 k€) ; la
   classe 'suspect' conserve son montant (maximums d'accords-cadres énergie
   observés jusqu'à 12,3 Md€ sur 12 mois).
2. Tout agrégat somme least(montant_retenu, 100 000 000 €) — plafond fixe
   PLAFOND_ECRETAGE_EUR = 100 M€, choisi au-dessus du p99,9 des montants
   retenus sur 12 mois (~140 M€ mesuré le 19/08/2026 : seuls ~0,1 % des
   marchés sont touchés, quasi exclusivement des maximums d'accords-cadres
   ou des saisies erronées). Un département ne peut donc plus être écrasé
   par un marché à 4 Md€ saisi en erreur. Les montants NULL restent NULL
   (comptés dans nb_marches, exclus des sommes) — aucune donnée inventée.
3. montant_suspect = 1 si montant_anomalie non NULL (classification source)
   OU montant_retenu > plafond. Le détail (decp_marches) conserve les
   montants NON écrêtés + le drapeau : l'écrêtage ne s'applique qu'aux
   agrégats.

Règle de datation d'un marché (paramètre de méthode, repris dans le champ
notes de meta_sources — seul canal par lequel /donnees l'apprend) :
1. La date retenue est celle de la notification INITIALE, pas celle du
   dernier avenant. POURQUOI : à la source, un marché tient en n lignes
   (titulaires, modifications) ; la ligne d'un AVENANT porte comme
   dateNotification la date de l'avenant, et donneesActuelles ne vaut que
   sur la dernière modification. Lire la date sur la ligne courante date
   donc le marché de son dernier avenant.
2. La clé de date est min(dateNotification) sur TOUTES les lignes du uid,
   calculée AVANT le filtre donneesActuelles. min() global plutôt que « la
   valeur à modification_id = 0 », ligne qui manque à 12 278 uid.
3. Toutes les fenêtres portent sur cette date : détail 24 mois, agrégats
   12 mois, série 36 mois, et le « 30 jours » que l'UI calcule sur
   decp_marches.date_notification.
4. Les ATTRIBUTS (montant, montant_rationalise, titulaires, objet,
   procédure…) restent lus sur la ligne COURANTE — « marché notifié le
   jour J, montant connu à ce jour ».
Mesuré le 21/08/2026 sur le parquet du 20/08 (3 240 022 lignes,
1 827 781 uid) : dater les marchés à leur ligne courante décale la date de
314 173 d'entre eux, toujours vers le futur (0 vers le passé), dont 307 517
(97,9 %) vers un autre mois. À cette date, la fenêtre 36 mois compte
777 054 marchés et les 12 mois 213 283 ; datés à leur ligne courante, ces
mêmes marchés en donneraient respectivement 861 849 (dont 217 827, soit
25,3 %, rangés dans le mauvais mois) et 297 323.

Autres règles héritées de la fiche S1 : le dédoublonnage se fait par GROUP BY
uid ; marchés sans aucune date de notification, ou dont la notification
initiale est future, écartés ; montants d'accords-cadres = maximums, pas du
dépensé (mention UI) ; latence légale de publication jusqu'à 2 mois
(fenêtres récentes structurellement incomplètes).

Échec (téléchargement, parquet invalide, build cassé) → exit ≠ 0, la base
n'est pas modifiée (transaction unique DELETE/INSERT + rollback).
"""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

import duckdb

from pipelines import db
from pipelines.common import (
    assainir_texte_integral,
    obtenir_logger,
    reparer_mojibake,
    telecharger,
)

log = obtenir_logger("ingest_decp")

SOURCE_ID = "S1"
URL_PARQUET = "https://www.data.gouv.fr/api/1/datasets/r/11cea8e8-df3e-4ed1-932b-781e2635e432"
URL_PAGE = (
    "https://www.data.gouv.fr/datasets/"
    "donnees-essentielles-de-la-commande-publique-consolidees-format-tabulaire"
)
FICHIER_RAW = "decp.parquet"
CACHE_HEURES = 24.0

# Fenêtres (mois) et tailles — documentées dans la docstring.
MOIS_DETAIL = 24
MOIS_AGGREGATS = 12
MOIS_SERIE = 36
NB_TOP = 50
NB_DERNIERS = 200

# Plafond d'écrêtage des agrégats (cf. règle en docstring, point 2).
PLAFOND_ECRETAGE_EUR = 100_000_000.0

# Délai légal de publication des données essentielles : DEUX MOIS CALENDAIRES
# à compter de la notification. POURQUOI l'écrire en mois et non en « 60
# jours » : un mois calendaire n'a pas de longueur fixe, et l'écart n'est pas
# théorique — un marché notifié le 11 mars a jusqu'au 11 mai, soit 61 jours,
# qu'une règle « 60 jours » déclarerait hors délai ; un marché notifié le
# 31 décembre a jusqu'au 28 février, soit 59 jours, qu'elle déclarerait dans
# les temps. Le décompte suit donc le texte, pas une approximation en jours.
DELAI_LEGAL_MOIS = 2

# Première année de la série annuelle de qualité de publication. Avant 2018,
# les effectifs sont résiduels et la série n'y veut rien dire : mesuré le
# 21/08/2026 sur data/raw/decp.parquet, 92 marchés retenus en 2015, 377 en
# 2016, 834 en 2017, contre 20 000 en 2018 et plus de 100 000 par an ensuite.
ANNEE_MIN_PUBLICATION = 2018

# Ventilation par catégorie d'acheteur : première année retenue. C'est
# DÉLIBÉRÉMENT la même que celle de la série annuelle. POURQUOI le dire plutôt
# que d'écrire la constante deux fois : deux fenêtres différentes obligeraient
# le lecteur à comprendre pourquoi, et la mesure ne fournit aucune raison de
# les séparer. Écarter 2018 de la seule ventilation a été mesuré le 21/08/2026
# sur data/raw/decp.parquet : 2018 pèse 1,25 % de la population ventilée, ne
# déplace aucun taux de catégorie de plus de 0,5 point, et le seul changement
# de rang qu'il provoque départage deux catégories à égalité au dixième près.
# Une fenêtre unique, expliquée une fois, vaut mieux qu'un écart sans cause.
ANNEE_MIN_COHORTE = ANNEE_MIN_PUBLICATION

# Une cohorte annuelle n'est CLOSE qu'au bout de deux ans. POURQUOI deux :
# le 9ᵉ décile du délai de publication se compte en centaines de jours
# (558 jours mesurés le 21/08/2026) ; dans une cohorte plus récente, les
# marchés notifiés mais encore non publiés MANQUENT AU DÉNOMINATEUR, ce qui
# rend le taux optimiste par construction. Les cohortes ouvertes restent
# publiées, marquées `cohorte_close = 0` pour que la lecture en tienne compte.
DECALAGE_COHORTE_CLOSE = 2

# Bornes de plausibilité des dates. La source livre des sentinelles
# (0001-01-01) et des saisies à quatre chiffres fantaisistes ; hors de cet
# intervalle, une date ne décrit pas un marché public réel. Le marché n'est
# pas corrigé ni remplacé par zéro : il est écarté du calcul et compté à part.
BORNE_DATE_MIN = "1980-01-01"
BORNE_DATE_MAX = "2030-01-01"

# Seuil du retard « de plus d'un an », en jours.
JOURS_RETARD_LONG = 365

# Garde-fous « build cassé » (SOURCES.md S1, plan B/C1) : en deçà, on refuse
# d'écraser les tables (le parquet consolidé fait ~3,2 M de lignes).
MIN_LIGNES_PARQUET = 1_000_000
MAX_RETARD_JOURS = 60

# Écrêtage SQL d'un montant : NULL reste NULL (least() DuckDB IGNORE les
# NULL — sans ce garde, un montant manquant « deviendrait » le plafond).
_SQL_ECRETE = "CASE WHEN {col} IS NULL THEN NULL ELSE least({col}, {plafond}) END"

# Test « publié dans le délai légal », isolé ici pour n'exister qu'à un seul
# endroit : c'est la définition dont dépendent les trois tables de qualité de
# publication, et la seule chose qui sépare le décompte en mois calendaires
# d'un décompte en jours (cf. DELAI_LEGAL_MOIS).
_SQL_DANS_DELAI = "{publication} <= {notification} + INTERVAL {mois} MONTH"

# Normalisation d'un libellé pour regroupement (casse, accents, apostrophes) :
# « Appel d'offres ouvert » et « Appel d offres ouvert » → même clé.
_SQL_CLE_LIBELLE = (
    "trim(regexp_replace(strip_accents(lower("
    "replace(replace({col}, chr(8217), ' '), '''', ' ')"
    ")), '\\s+', ' ', 'g'))"
)

# Identifiant d'établissement CONFORME : exactement 14 caractères, tous des
# chiffres. POURQUOI un filtre plutôt qu'une tolérance : la source livre des
# identifiants-rebut (numéros internes, chaînes tronquées, sigles) qui ne
# désignent aucun établissement ; leurs 9 premiers caractères ne sont pas un
# SIREN, et les regrouper fabriquerait une entreprise qui n'existe pas. Un tel
# identifiant a déjà été servi dans les tout premiers rangs des titulaires,
# sans nom, en agrégeant des marchés sans rapport entre eux. Doctrine maison :
# on ÉCARTE et on COMPTE (decp_titulaires_qualite) — jamais de valeur par
# défaut à la place, jamais de disparition silencieuse.
# POURQUOI '[0-9]+' plus le test de longueur, et non '[0-9]{14}' : ce fragment
# est interpolé dans des f-strings, où les accolades devraient être doublées ;
# la forme retenue dit exactement la même chose sans piège de relecture.
_SQL_IDENTIFIANT_CONFORME = (
    "({col} IS NOT NULL AND length({col}) = 14 "
    "AND regexp_full_match({col}, '[0-9]+'))"
)

# SIREN de l'entreprise = les 9 premiers chiffres du SIRET de l'établissement
# (les 5 suivants sont le NIC, propre à l'établissement). Écrit une fois pour
# que les titulaires et les acheteurs ne puissent pas diverger de règle.
_SQL_SIREN = "substr({col}, 1, 9)"

# ---------------------------------------------------------------------------
# Schéma SQLite (CREATE TABLE IF NOT EXISTS — réécriture idempotente ensuite)
# ---------------------------------------------------------------------------

_COLONNES_MARCHE = """
    uid                       TEXT PRIMARY KEY,
    id                        TEXT,
    objet                     TEXT,
    montant                   REAL,
    montant_rationalise       REAL,
    montant_retenu            REAL,
    montant_anomalie          TEXT,
    montant_suspect           INTEGER NOT NULL DEFAULT 0,
    acheteur_siret            TEXT,
    acheteur_nom              TEXT,
    acheteur_departement_code TEXT,
    acheteur_departement_nom  TEXT,
    titulaire_siret           TEXT,
    titulaire_nom             TEXT,
    nb_titulaires             INTEGER NOT NULL DEFAULT 0,
    titulaires_json           TEXT,
    date_notification         TEXT NOT NULL,
    duree_mois                INTEGER,
    procedure                 TEXT,
    nature                    TEXT,
    type_marche               TEXT,
    techniques                TEXT,
    code_cpv                  TEXT,
    lieu_execution_code       TEXT,
    lieu_execution_typecode   TEXT
"""

_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS decp_marches ({_COLONNES_MARCHE});
CREATE INDEX IF NOT EXISTS idx_decp_marches_date  ON decp_marches(date_notification);
CREATE INDEX IF NOT EXISTS idx_decp_marches_ach   ON decp_marches(acheteur_siret);
CREATE INDEX IF NOT EXISTS idx_decp_marches_tit   ON decp_marches(titulaire_siret);
CREATE INDEX IF NOT EXISTS idx_decp_marches_dep   ON decp_marches(acheteur_departement_code);

CREATE TABLE IF NOT EXISTS decp_agg_departement (
    departement_code   TEXT PRIMARY KEY,
    departement_nom    TEXT,
    nb_marches         INTEGER NOT NULL,
    montant_total      REAL,
    nb_marches_ecretes INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS decp_agg_mois (
    mois          TEXT PRIMARY KEY,
    nb_marches    INTEGER NOT NULL,
    montant_total REAL
);

CREATE TABLE IF NOT EXISTS decp_top_acheteurs (
    rang              INTEGER PRIMARY KEY,
    siren             TEXT,
    nom               TEXT,
    nb_etablissements INTEGER NOT NULL,
    nb_marches        INTEGER NOT NULL,
    montant_total     REAL
);

CREATE TABLE IF NOT EXISTS decp_top_titulaires (
    rang              INTEGER PRIMARY KEY,
    siren             TEXT,
    nom               TEXT,
    categorie         TEXT,
    nb_etablissements INTEGER NOT NULL,
    nb_marches        INTEGER NOT NULL,
    montant_total     REAL
);

CREATE TABLE IF NOT EXISTS decp_titulaires_qualite (
    id                        INTEGER PRIMARY KEY CHECK (id = 1),
    nb_marches                INTEGER NOT NULL,
    nb_marches_avec_titulaire INTEGER NOT NULL,
    nb_lignes                 INTEGER NOT NULL,
    nb_lignes_identifiables   INTEGER NOT NULL,
    nb_lignes_ecartees        INTEGER NOT NULL,
    montant_identifiable      REAL,
    montant_ecarte            REAL,
    nb_identifiants_ecartes   INTEGER NOT NULL,
    nb_sirets                 INTEGER NOT NULL,
    nb_sirens                 INTEGER NOT NULL,
    nb_sirens_multi_etab      INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS decp_acheteurs_qualite (
    id                       INTEGER PRIMARY KEY CHECK (id = 1),
    nb_marches               INTEGER NOT NULL,
    nb_marches_avec_acheteur INTEGER NOT NULL,
    nb_marches_identifiables INTEGER NOT NULL,
    nb_marches_ecartes       INTEGER NOT NULL,
    montant_identifiable     REAL,
    montant_ecarte           REAL,
    nb_identifiants_ecartes  INTEGER NOT NULL,
    nb_sirets                INTEGER NOT NULL,
    nb_sirens                INTEGER NOT NULL,
    nb_sirens_multi_etab     INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS decp_qualite_montants (
    id                    INTEGER PRIMARY KEY CHECK (id = 1),
    nb_marches            INTEGER NOT NULL,
    montant_total         REAL,
    nb_ecretes            INTEGER NOT NULL,
    montant_ecretes       REAL,
    nb_suspects           INTEGER NOT NULL,
    montant_suspects      REAL,
    montant_hors_suspects REAL,
    montant_brut          REAL,
    nb_sans_montant       INTEGER NOT NULL,
    plafond               REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS decp_publication_qualite (
    id                        INTEGER PRIMARY KEY CHECK (id = 1),
    nb_marches_source         INTEGER NOT NULL,
    nb_retenus                INTEGER NOT NULL,
    nb_sans_notification      INTEGER NOT NULL,
    nb_sans_publication       INTEGER NOT NULL,
    nb_dates_hors_bornes      INTEGER NOT NULL,
    nb_publication_anterieure INTEGER NOT NULL,
    nb_sans_categorie         INTEGER NOT NULL,
    delai_q1                  INTEGER,
    delai_median              INTEGER,
    delai_q3                  INTEGER,
    delai_d9                  INTEGER,
    delai_legal_mois          INTEGER NOT NULL,
    cohorte_min               INTEGER NOT NULL,
    cohorte_max               INTEGER NOT NULL,
    date_observation_max      TEXT
);

CREATE TABLE IF NOT EXISTS decp_publication_annees (
    annee           INTEGER PRIMARY KEY,
    nb_marches      INTEGER NOT NULL,
    nb_dans_delai   INTEGER NOT NULL,
    taux_dans_delai REAL,
    delai_median    INTEGER,
    nb_plus_un_an   INTEGER NOT NULL,
    cohorte_close   INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS decp_publication_acheteurs (
    categorie       TEXT PRIMARY KEY,
    nb_marches      INTEGER NOT NULL,
    nb_dans_delai   INTEGER NOT NULL,
    taux_dans_delai REAL,
    delai_median    INTEGER,
    nb_plus_un_an   INTEGER NOT NULL,
    taux_plus_un_an REAL
);

CREATE TABLE IF NOT EXISTS decp_repartition (
    dimension     TEXT NOT NULL,
    valeur        TEXT,
    nb_marches    INTEGER NOT NULL,
    montant_total REAL
);
CREATE INDEX IF NOT EXISTS idx_decp_repartition_dim ON decp_repartition(dimension);

CREATE TABLE IF NOT EXISTS decp_derniers_marches (
    rang INTEGER PRIMARY KEY,
    {_COLONNES_MARCHE.replace("uid                       TEXT PRIMARY KEY",
                              "uid                       TEXT NOT NULL")}
);
"""

# Ordre des colonnes partagé entre les SELECT DuckDB et les INSERT SQLite.
_CHAMPS_MARCHE = [
    "uid", "id", "objet", "montant", "montant_rationalise", "montant_retenu",
    "montant_anomalie", "montant_suspect", "acheteur_siret", "acheteur_nom",
    "acheteur_departement_code", "acheteur_departement_nom", "titulaire_siret",
    "titulaire_nom", "nb_titulaires", "titulaires_json", "date_notification",
    "duree_mois", "procedure", "nature", "type_marche", "techniques",
    "code_cpv", "lieu_execution_code", "lieu_execution_typecode",
]

# ---------------------------------------------------------------------------
# Transformation (pure : parquet + date de référence → tables temp DuckDB)
# ---------------------------------------------------------------------------


def _sql_libelle_dominant(source: str, cle: str, colonne: str) -> str:
    """SQL du libellé DOMINANT d'un groupe : le plus fréquent, ex æquo alphabétiques.

    POURQUOI pas `any_value()`, qui suffisait tant qu'un groupe valait un
    établissement : un SIREN peut réunir deux cents établissements aux
    libellés déclarés différents, et `any_value()` en rend un ARBITRAIRE, qui
    peut changer d'un passage à l'autre sans qu'aucune donnée ait bougé — le
    classement cesse alors d'être rejouable à l'identique, ce qui est
    précisément ce qu'on demande à un pipeline pur.
    POURQUOI un départage alphabétique : sans lui, deux libellés à égalité de
    fréquence laisseraient le résultat indéterminé, et le problème reviendrait
    intact sur les groupes à deux établissements.
    Les NULL NE VOTENT PAS — un libellé absent n'est pas un libellé, et le
    compter ferait gagner « rien » face à un nom réel. Un groupe sans aucun
    libellé ne ressort donc pas de cette sous-requête : la jointure EXTERNE de
    l'appelant y laisse NULL, ce qui dit « non renseigné » sans rien inventer.
    """
    return f"""
        SELECT {cle}, {colonne} FROM (
            SELECT {cle}, {colonne},
                   row_number() OVER (
                       PARTITION BY {cle}
                       ORDER BY count(*) DESC, {colonne}) AS rang_libelle
            FROM {source}
            WHERE {colonne} IS NOT NULL
            GROUP BY {cle}, {colonne}
        ) WHERE rang_libelle = 1
    """


def transformer(
    chemin_parquet: str | Path, date_ref: date
) -> tuple[duckdb.DuckDBPyConnection, dict]:
    """Construit les tables temporaires `t_*` dans une connexion DuckDB.

    Pure et rejouable : ne touche ni au réseau ni à SQLite ; testable sur une
    fixture parquet. Retourne (connexion duckdb, stats) où stats contient
    lignes_parquet, nb_marches, date_max (ISO ou None), nb_suspects.
    """
    chemin = str(Path(chemin_parquet))
    duck = duckdb.connect()
    duck.execute("SET threads TO 4")
    p = {
        "plafond": PLAFOND_ECRETAGE_EUR,
        "date_ref": date_ref.isoformat(),
    }

    lignes_parquet = duck.execute(
        "SELECT count(*) FROM read_parquet(?)", [chemin]
    ).fetchone()[0]

    # Date de notification du marché = celle de la notification INITIALE,
    # calculée sur TOUTES les lignes du uid, donc AVANT le filtre
    # `donneesActuelles`. POURQUOI : à la source, la ligne d'un avenant porte
    # comme dateNotification la date de l'AVENANT, et donneesActuelles ne
    # vaut que sur la dernière modification. Lire la date sur la seule ligne
    # courante date le marché de son dernier avenant. Exemple réel, parquet
    # du 20/08/2026, uid 200094332000182023S00686_63724310 : ses 4 lignes
    # sont notifiées 2023-01-18, 2024-12-02, 2025-12-19 et 2026-08-19, la
    # dernière seule portant donneesActuelles — marché notifié en janvier
    # 2023, daté d'août 2026.
    # Mesuré le 21/08/2026 sur ce parquet (3 240 022 lignes, 1 827 781 uid) :
    # 314 173 marchés voyaient leur date réécrite, tous vers le futur (0 vers
    # le passé), dont 307 517 (97,9 %) changeaient de mois ; sur la fenêtre
    # 36 mois alors servie (861 849 marchés), 217 827 (25,3 %) étaient rangés
    # dans le mauvais mois.
    # POURQUOI min() global et non « la valeur à modification_id = 0 » :
    # 12 278 uid n'ont aucune ligne modification_id = 0 (même mesure) ;
    # min() les couvre sans cas particulier.
    # POURQUOI une table à part et non une fenêtre sur toutes les colonnes :
    # le parquet est colonnaire, cette passe ne lit que uid et
    # dateNotification (2 colonnes sur 64) ; le HAVING borne d'emblée la
    # population à la plus large fenêtre (série 36 mois), et la jointure
    # ci-dessous reste donc un filtre précoce.
    duck.execute(
        f"""
        CREATE TEMP TABLE t_date_initiale AS
        SELECT uid, min(dateNotification) AS date_initiale
        FROM read_parquet('{chemin}')
        WHERE dateNotification IS NOT NULL
        GROUP BY uid
        HAVING min(dateNotification) <= DATE '{p['date_ref']}'
           AND min(dateNotification) >  DATE '{p['date_ref']}' - INTERVAL {MOIS_SERIE} MONTH
        """
    )

    # Lignes retenues : versions courantes des marchés de la fenêtre, dotées
    # de leur date de notification initiale. Les ATTRIBUTS (montant,
    # titulaires, objet, procédure…) restent lus sur la ligne COURANTE —
    # « marché notifié le jour J, montant connu à ce jour ».
    duck.execute(
        f"""
        CREATE TEMP VIEW lignes AS
        SELECT l.*, i.date_initiale
        FROM read_parquet('{chemin}') l
        JOIN t_date_initiale i USING (uid)
        WHERE l.donneesActuelles
        """
    )

    # Titulaires dédoublonnés par marché (1 marché = n lignes à la source).
    duck.execute(
        """
        CREATE TEMP TABLE t_titulaires AS
        SELECT uid, titulaire_id,
               any_value(titulaire_nom)       AS nom,
               any_value(titulaire_categorie) AS categorie
        FROM lignes
        WHERE titulaire_id IS NOT NULL
        GROUP BY uid, titulaire_id
        """
    )

    # 1 ligne par marché (uid) sur 36 mois — base commune : la série
    # mensuelle en a besoin ; le détail est ensuite réduit à 24 mois.
    duck.execute(
        f"""
        CREATE TEMP TABLE t_marches_36 AS
        WITH par_uid AS (
            SELECT uid,
                   any_value(id)                                  AS id,
                   any_value(objet)                               AS objet,
                   max(montant)                                   AS montant,
                   max(montant_rationalise)                       AS montant_rationalise,
                   max(coalesce(montant_rationalise, montant))    AS montant_retenu,
                   max(montant_anomalie)                          AS montant_anomalie,
                   any_value(acheteur_id)                         AS acheteur_siret,
                   any_value(acheteur_nom)                        AS acheteur_nom,
                   any_value(acheteur_departement_code)           AS acheteur_departement_code,
                   any_value(acheteur_departement_nom)            AS acheteur_departement_nom,
                   -- Date de la notification INITIALE (cf. t_date_initiale),
                   -- constante par uid : toutes les fenêtres construites
                   -- plus bas (24 mois, 12 mois, série mensuelle) et le
                   -- « 30 jours » calculé par l'UI portent sur ELLE, pas sur
                   -- la date de la ligne courante.
                   CAST(any_value(date_initiale) AS VARCHAR)      AS date_notification,
                   -- POURQUOI ce CASE : la source livre des durées
                   -- impossibles (négatives, ou 32 000 mois = 2 666 ans).
                   -- On ne devine rien — la valeur invraisemblable est
                   -- remplacée par NULL, qui dit « non renseigné » sans
                   -- mentir. Borne haute très large (600 mois = 50 ans),
                   -- au-delà du plus long marché public concevable : aucune
                   -- valeur légitime n'est perdue. Mesuré le 20/08/2026 sur
                   -- la base de production : 22 durées < 0 et 119 > 600 sur
                   -- 585 503 marchés (§ M3 de QUALITE-DONNEES.md).
                   CASE WHEN any_value(dureeMois) BETWEEN 0 AND 600
                        THEN any_value(dureeMois) END               AS duree_mois,
                   any_value("procedure")                         AS procedure,
                   any_value(nature)                              AS nature,
                   any_value("type")                              AS type_marche,
                   any_value(techniques)                          AS techniques,
                   any_value(codeCPV)                             AS code_cpv,
                   any_value(lieuExecution_code)                  AS lieu_execution_code,
                   any_value(lieuExecution_typeCode)              AS lieu_execution_typecode
            FROM lignes
            GROUP BY uid
        ),
        tit AS (
            SELECT uid,
                   count(*)                                       AS nb_titulaires,
                   min(titulaire_id)                              AS titulaire_siret,
                   arg_min(nom, titulaire_id)                     AS titulaire_nom,
                   to_json(list(struct_pack(siret := titulaire_id, nom := nom)
                                ORDER BY titulaire_id))           AS titulaires_json
            FROM t_titulaires
            GROUP BY uid
        )
        SELECT m.uid, m.id, m.objet, m.montant, m.montant_rationalise,
               m.montant_retenu, m.montant_anomalie,
               CAST(coalesce(m.montant_anomalie IS NOT NULL
                             OR m.montant_retenu > {p['plafond']},
                             FALSE) AS INTEGER)               AS montant_suspect,
               m.acheteur_siret, m.acheteur_nom,
               m.acheteur_departement_code, m.acheteur_departement_nom,
               t.titulaire_siret, t.titulaire_nom,
               coalesce(t.nb_titulaires, 0)                          AS nb_titulaires,
               t.titulaires_json,
               m.date_notification, m.duree_mois, m.procedure, m.nature,
               m.type_marche, m.techniques, m.code_cpv,
               m.lieu_execution_code, m.lieu_execution_typecode
        FROM par_uid m
        LEFT JOIN tit t USING (uid)
        """
    )

    # Détail servi à l'UI : 24 derniers mois.
    duck.execute(
        f"""
        CREATE TEMP TABLE t_marches AS
        SELECT * FROM t_marches_36
        WHERE date_notification
              > CAST(DATE '{p['date_ref']}' - INTERVAL {MOIS_DETAIL} MONTH AS VARCHAR)
        """
    )

    # Vue « 12 derniers mois » avec montant écrêté (base de tous les agrégats).
    duck.execute(
        f"""
        CREATE TEMP VIEW recents AS
        SELECT *,
               {_SQL_ECRETE.format(col='montant_retenu', plafond=p['plafond'])} AS montant_ecrete,
               coalesce(montant_retenu > {p['plafond']}, FALSE)                 AS ecrete
        FROM t_marches
        WHERE date_notification > CAST(DATE '{p['date_ref']}' - INTERVAL {MOIS_AGGREGATS} MONTH AS VARCHAR)
        """
    )

    # Carte : agrégat par département de l'acheteur (fiche S1 : lieuExecution
    # est à granularité mixte, le département acheteur est fiable et géocodé).
    duck.execute(
        """
        CREATE TEMP TABLE t_agg_departement AS
        SELECT acheteur_departement_code            AS departement_code,
               any_value(acheteur_departement_nom)  AS departement_nom,
               count(*)                             AS nb_marches,
               sum(montant_ecrete)                  AS montant_total,
               count(*) FILTER (ecrete)             AS nb_marches_ecretes
        FROM recents
        WHERE acheteur_departement_code IS NOT NULL
        GROUP BY departement_code
        ORDER BY departement_code
        """
    )

    # Série mensuelle : 36 derniers mois civils.
    duck.execute(
        f"""
        CREATE TEMP TABLE t_agg_mois AS
        SELECT strftime(CAST(date_notification AS DATE), '%Y-%m') AS mois,
               count(*)                                           AS nb_marches,
               sum({_SQL_ECRETE.format(col='montant_retenu',
                                       plafond=p['plafond'])})    AS montant_total
        FROM t_marches_36
        WHERE CAST(date_notification AS DATE)
              >= date_trunc('month', DATE '{p['date_ref']}') - INTERVAL {MOIS_SERIE - 1} MONTH
        GROUP BY mois
        ORDER BY mois
        """
    )

    # Population du classement des acheteurs : les marchés de la fenêtre 12
    # mois dont l'acheteur est RENSEIGNÉ, avec leur SIREN et le verdict de
    # conformité de l'identifiant. Même dispositif que pour les titulaires :
    # UNE table de population, dont le classement ET les compteurs de qualité
    # dérivent par des filtres strictement COMPLÉMENTAIRES — la partition est
    # ainsi vraie par CONSTRUCTION, et non par concordance de deux comptes
    # écrits séparément.
    # L'unité est ici le MARCHÉ et non un couple : `acheteur_siret` est
    # scalaire à la source, un marché n'a qu'un acheteur. `recents` portant
    # déjà UNE ligne par marché, count(*) y est un compte de marchés.
    duck.execute(
        f"""
        CREATE TEMP TABLE t_acheteurs_marches AS
        SELECT uid,
               acheteur_siret,
               {_SQL_SIREN.format(col='acheteur_siret')}                AS siren,
               acheteur_nom                                             AS nom,
               {_SQL_IDENTIFIANT_CONFORME.format(col='acheteur_siret')} AS identifiable,
               montant_ecrete
        FROM recents
        WHERE acheteur_siret IS NOT NULL
        """
    )

    duck.execute(
        """
        CREATE TEMP VIEW acheteurs_conformes AS
        SELECT * FROM t_acheteurs_marches WHERE identifiable
        """
    )

    # Top acheteurs par ENTREPRISE (SIREN), comme les titulaires. POURQUOI
    # aligner les deux alors que l'effet est bien plus faible ici — la plupart
    # des acheteurs publics n'ont qu'un établissement acheteur : servir un
    # classement par entreprise d'un côté et par établissement de l'autre
    # serait une différence de définition invisible à l'écran et
    # inexplicable au lecteur. Une même règle, énoncée une fois.
    duck.execute(
        f"""
        CREATE TEMP TABLE t_top_acheteurs AS
        WITH par_siren AS (
            SELECT siren,
                   count(DISTINCT acheteur_siret) AS nb_etablissements,
                   count(*)                       AS nb_marches,
                   sum(montant_ecrete)            AS montant_total
            FROM acheteurs_conformes
            GROUP BY siren
        ),
        noms AS ({_sql_libelle_dominant('acheteurs_conformes', 'siren', 'nom')})
        SELECT row_number() OVER (ORDER BY p.montant_total DESC NULLS LAST,
                                  p.siren)   AS rang,
               p.siren, n.nom,
               p.nb_etablissements, p.nb_marches, p.montant_total
        FROM par_siren p
        LEFT JOIN noms n USING (siren)
        ORDER BY rang
        LIMIT {NB_TOP}
        """
    )

    # Population des titulaires de la fenêtre 12 mois : un couple (marché ×
    # titulaire) par ligne, avec sa part de montant et le verdict de
    # conformité de l'identifiant.
    # POURQUOI UNE SEULE table pour le classement ET pour les compteurs de
    # qualité : un compteur de défauts ne se vérifie que par RECOMPOSITION de
    # la population de départ. Retenus et écartés sont ici deux filtres
    # strictement COMPLÉMENTAIRES (`identifiable` / `NOT identifiable`) sur
    # les mêmes lignes, et non deux comptes écrits séparément qui pourraient
    # dériver l'un de l'autre sans que rien ne le signale. `identifiable` ne
    # vaut jamais NULL — un identifiant absent est déjà exclu de t_titulaires,
    # et le test de nullité ouvre de toute façon la conjonction : sans cela la
    # partition fuirait par le milieu.
    # Convention de montant, la même que partout ailleurs : montant écrêté au
    # plafond, puis divisé par le nombre de co-titulaires (le montant DECP est
    # celui du marché entier, la source ne le ventile pas). Un montant absent
    # reste NULL et n'entre dans aucune somme.
    duck.execute(
        f"""
        CREATE TEMP TABLE t_titulaires_lignes AS
        SELECT t.uid,
               t.titulaire_id,
               {_SQL_SIREN.format(col='t.titulaire_id')}                AS siren,
               t.nom,
               t.categorie,
               {_SQL_IDENTIFIANT_CONFORME.format(col='t.titulaire_id')} AS identifiable,
               r.montant_ecrete / r.nb_titulaires                       AS montant_part
        FROM t_titulaires t
        JOIN recents r USING (uid)
        """
    )

    duck.execute(
        """
        CREATE TEMP VIEW titulaires_conformes AS
        SELECT * FROM t_titulaires_lignes WHERE identifiable
        """
    )

    # Top titulaires par ENTREPRISE (SIREN). POURQUOI : agrégé par
    # établissement, un groupe à réseau local voit ses marchés répartis sur
    # ses dizaines ou centaines de SIRET ; aucun n'atteint le seuil d'entrée
    # du top 50, et le groupe est absent d'un classement dont il serait le
    # premier. Le croisement lobbying × marchés du site joint déjà sur le
    # SIREN : le classement s'aligne sur la même unité, l'entreprise.
    # POURQUOI count(DISTINCT uid) et non count(*) : deux établissements d'un
    # même SIREN peuvent être CO-TITULAIRES du même marché — ce marché ne doit
    # être compté qu'une fois, sans quoi la colonne annoncerait plus de
    # marchés qu'il n'en existe. Le montant, lui, additionne bien les deux
    # parts : c'est ce que le groupe a emporté.
    duck.execute(
        f"""
        CREATE TEMP TABLE t_top_titulaires AS
        WITH par_siren AS (
            SELECT siren,
                   count(DISTINCT titulaire_id) AS nb_etablissements,
                   count(DISTINCT uid)          AS nb_marches,
                   sum(montant_part)            AS montant_total
            FROM titulaires_conformes
            GROUP BY siren
        ),
        noms AS ({_sql_libelle_dominant('titulaires_conformes', 'siren', 'nom')}),
        cats AS ({_sql_libelle_dominant('titulaires_conformes', 'siren', 'categorie')})
        SELECT row_number() OVER (ORDER BY p.montant_total DESC NULLS LAST,
                                  p.siren)   AS rang,
               p.siren, n.nom, c.categorie,
               p.nb_etablissements, p.nb_marches, p.montant_total
        FROM par_siren p
        LEFT JOIN noms n USING (siren)
        LEFT JOIN cats c USING (siren)
        ORDER BY rang
        LIMIT {NB_TOP}
        """
    )

    # Répartition procédure / nature (libellés hétérogènes à la source :
    # « Marché »/« MARCHE » → regroupés, libellé le plus fréquent affiché).
    parties = []
    for dim, col in (("procedure", "procedure"), ("nature", "nature")):
        cle = _SQL_CLE_LIBELLE.format(col=col)
        parties.append(
            f"""
            SELECT '{dim}' AS dimension,
                   mode({col})            AS valeur,
                   count(*)               AS nb_marches,
                   sum(montant_ecrete)    AS montant_total
            FROM recents
            GROUP BY {cle}
            """
        )
    duck.execute(
        "CREATE TEMP TABLE t_repartition AS "
        + " UNION ALL ".join(parties)
        + " ORDER BY dimension, nb_marches DESC"
    )

    # Qualité des montants de la MÊME fenêtre 12 mois que decp_repartition :
    # le chiffre héros (« montant notifié, écrêté ») ne dit pas à lui seul
    # quelle part vient d'un plafond arbitraire ou d'un montant marqué
    # suspect. Ces parts sont calculées ICI, dans le pipeline, parce que la
    # coupe des 12 mois n'est stockée nulle part en base : elle dépend de
    # date_ref (jour de l'ingestion), et max(date_notification) — antérieur
    # de quelques jours — la retrouverait décalée. Une seule ligne (id = 1).
    duck.execute(
        f"""
        CREATE TEMP TABLE t_qualite_montants AS
        SELECT 1                                              AS id,
               count(*)                                       AS nb_marches,
               sum(montant_ecrete)                            AS montant_total,
               count(*) FILTER (ecrete)                       AS nb_ecretes,
               sum(montant_ecrete) FILTER (ecrete)            AS montant_ecretes,
               count(*) FILTER (montant_suspect = 1)          AS nb_suspects,
               sum(montant_ecrete) FILTER (montant_suspect = 1) AS montant_suspects,
               sum(montant_ecrete) FILTER (montant_suspect = 0) AS montant_hors_suspects,
               sum(montant_retenu)                            AS montant_brut,
               count(*) FILTER (montant_retenu IS NULL)       AS nb_sans_montant,
               CAST({p['plafond']} AS DOUBLE)                 AS plafond
        FROM recents
        """
    )

    # Qualité du regroupement par entreprise : ce que le classement retient et
    # ce qu'il écarte, sur la MÊME fenêtre 12 mois. Calculée ICI, dénominateurs
    # compris, pour la raison qui vaut déjà pour t_qualite_montants : la coupe
    # des 12 mois dépend du jour d'ingestion et n'est stockée nulle part en
    # base, une requête d'affichage ne saurait pas la retrouver.
    # TOUS les compteurs de lignes sortent d'un SEUL parcours de
    # t_titulaires_lignes, avec des filtres complémentaires : la table est donc
    # cohérente PAR CONSTRUCTION — nb_lignes = identifiables + écartées, et de
    # même pour les montants. Les deux compteurs d'identifiants distincts
    # partagent la même propriété : nb_sirets + nb_identifiants_ecartes = les
    # identifiants titulaires distincts de la fenêtre.
    # nb_marches vient de `recents`, la source exacte de
    # decp_qualite_montants.nb_marches : les deux tables affichent le même
    # dénominateur parce qu'elles le lisent au même endroit, non parce que
    # deux calculs se trouvent tomber juste.
    duck.execute(
        """
        CREATE TEMP TABLE t_titulaires_qualite AS
        SELECT 1                                     AS id,
               (SELECT count(*) FROM recents)        AS nb_marches,
               count(DISTINCT uid)                   AS nb_marches_avec_titulaire,
               count(*)                              AS nb_lignes,
               count(*) FILTER (identifiable)        AS nb_lignes_identifiables,
               count(*) FILTER (NOT identifiable)    AS nb_lignes_ecartees,
               sum(montant_part) FILTER (identifiable)     AS montant_identifiable,
               sum(montant_part) FILTER (NOT identifiable) AS montant_ecarte,
               count(DISTINCT titulaire_id) FILTER (NOT identifiable)
                                                     AS nb_identifiants_ecartes,
               count(DISTINCT titulaire_id) FILTER (identifiable) AS nb_sirets,
               count(DISTINCT siren) FILTER (identifiable)        AS nb_sirens,
               (SELECT count(*) FROM (
                    SELECT siren FROM titulaires_conformes
                    GROUP BY siren
                    HAVING count(DISTINCT titulaire_id) > 1))
                                                     AS nb_sirens_multi_etab
        FROM t_titulaires_lignes
        """
    )

    # Qualité du regroupement par entreprise, côté ACHETEURS. Même dispositif
    # que t_titulaires_qualite, et volontairement PLUS COURT : l'unité de
    # compte est le marché, pas un couple qui n'existe pas ici.
    # nb_marches sort de `recents`, la source exacte de
    # decp_qualite_montants.nb_marches et de t_titulaires_qualite.nb_marches :
    # trois tables ne peuvent pas afficher trois dénominateurs pour une même
    # fenêtre, parce qu'elles le lisent au même endroit.
    # Le dénominateur de la PARTITION, lui, est nb_marches_avec_acheteur, plus
    # petit dès qu'un marché de la fenêtre n'a aucun acheteur renseigné : les
    # confondre ferait passer un défaut de saisie amont pour un identifiant
    # écarté par nous.
    duck.execute(
        """
        CREATE TEMP TABLE t_acheteurs_qualite AS
        SELECT 1                                     AS id,
               (SELECT count(*) FROM recents)         AS nb_marches,
               count(*)                               AS nb_marches_avec_acheteur,
               count(*) FILTER (identifiable)         AS nb_marches_identifiables,
               count(*) FILTER (NOT identifiable)     AS nb_marches_ecartes,
               sum(montant_ecrete) FILTER (identifiable)     AS montant_identifiable,
               sum(montant_ecrete) FILTER (NOT identifiable) AS montant_ecarte,
               count(DISTINCT acheteur_siret) FILTER (NOT identifiable)
                                                      AS nb_identifiants_ecartes,
               count(DISTINCT acheteur_siret) FILTER (identifiable) AS nb_sirets,
               count(DISTINCT siren) FILTER (identifiable)          AS nb_sirens,
               (SELECT count(*) FROM (
                    SELECT siren FROM acheteurs_conformes
                    GROUP BY siren
                    HAVING count(DISTINCT acheteur_siret) > 1))
                                                      AS nb_sirens_multi_etab
        FROM t_acheteurs_marches
        """
    )

    duck.execute(
        f"""
        CREATE TEMP TABLE t_derniers_marches AS
        SELECT row_number() OVER (ORDER BY date_notification DESC, uid) AS rang, *
        FROM t_marches
        ORDER BY date_notification DESC, uid
        LIMIT {NB_DERNIERS}
        """
    )

    # -----------------------------------------------------------------
    # Qualité de PUBLICATION : l'obligation légale est-elle respectée ?
    # -----------------------------------------------------------------
    # Passe SÉPARÉE sur le parquet, et non un dérivé des tables ci-dessus.
    # POURQUOI : tout ce qui précède est borné à une fenêtre glissante
    # (t_date_initiale coupe à MOIS_SERIE par son HAVING, `recents` à
    # MOIS_AGGREGATS), or la question posée ici est historique — le
    # respect du délai se compare d'une année sur l'autre depuis le début
    # de l'obligation. Réutiliser ces tables tronquerait la population et
    # donnerait des taux calculés sur un reste arbitraire.
    # POURQUOI c'est abordable : le parquet est colonnaire et cette passe
    # ne lit que 4 colonnes sur 64 (uid, dateNotification,
    # datePublicationDonnees, acheteur_categorie) ; mesuré le 21/08/2026
    # sur data/raw/decp.parquet (3 240 022 lignes), moins d'une seconde.
    # Agrégation par uid d'abord, toujours : une ligne du parquet est un
    # couple marché × titulaire × modification, pas un marché.
    #   notification = min(dateNotification) — la notification INITIALE,
    #     même règle et même raison que t_date_initiale ;
    #   publication  = min(datePublicationDonnees) — la PREMIÈRE mise en
    #     ligne, celle que le délai légal vise ; une republication tardive
    #     lors d'un avenant ne défait pas une publication faite à temps.
    # `acheteur_categorie` est un attribut de l'acheteur, donc constant sur
    # les lignes d'un uid : max() le prend de façon déterministe en
    # ignorant les lignes où il manque.
    duck.execute(
        f"""
        CREATE TEMP TABLE t_publication_marches AS
        SELECT uid,
               min(dateNotification)       AS notification,
               min(datePublicationDonnees) AS publication,
               max(acheteur_categorie)     AS categorie
        FROM read_parquet('{chemin}')
        GROUP BY uid
        """
    )

    # Classement des marchés en catégories EXCLUSIVES, dans cet ordre. Un
    # marché qui cumule deux défauts (ni notification ni publication, date
    # sentinelle ET publication antérieure) ne doit être compté qu'une fois,
    # sans quoi la somme des écarts dépasse la population et le lecteur ne
    # peut plus rien recomposer. L'ordre va du défaut le plus radical au
    # plus fin : sans date, on ne peut rien dire ; hors bornes, la date
    # existe mais ne décrit rien ; publication antérieure, les deux dates
    # sont plausibles mais leur ordre est impossible.
    # Ces marchés écartés sont COMPTÉS, jamais remplacés par un délai de 0 :
    # un défaut de saisie ne se raconte pas comme une publication à l'heure.
    dans_delai = _SQL_DANS_DELAI.format(
        publication="publication", notification="notification", mois=DELAI_LEGAL_MOIS
    )
    duck.execute(
        f"""
        CREATE TEMP TABLE t_publication_classee AS
        SELECT uid,
               notification,
               publication,
               -- Une catégorie vide est une absence, pas un libellé : elle
               -- est ramenée à NULL ici pour n'avoir qu'un seul cas à
               -- traiter en aval (la ventilation l'exclut, le compteur
               -- nb_sans_categorie la retient).
               nullif(trim(categorie), '')                 AS categorie,
               CASE
                   WHEN notification IS NULL THEN 'sans_notification'
                   WHEN publication  IS NULL THEN 'sans_publication'
                   WHEN notification NOT BETWEEN DATE '{BORNE_DATE_MIN}'
                                             AND DATE '{BORNE_DATE_MAX}'
                     OR publication  NOT BETWEEN DATE '{BORNE_DATE_MIN}'
                                             AND DATE '{BORNE_DATE_MAX}'
                        THEN 'dates_hors_bornes'
                   WHEN publication < notification THEN 'publication_anterieure'
                   ELSE 'retenu'
               END                                         AS classe,
               date_diff('day', notification, publication) AS delai,
               year(notification)                          AS annee,
               {dans_delai}                                AS dans_delai
        FROM t_publication_marches
        """
    )

    duck.execute(
        """
        CREATE TEMP VIEW publies AS
        SELECT * FROM t_publication_classee WHERE classe = 'retenu'
        """
    )

    cohorte_max = date_ref.year - DECALAGE_COHORTE_CLOSE

    # Série annuelle par année de NOTIFICATION (pas de publication) : la
    # question est « les marchés notifiés cette année-là ont-ils été publiés
    # à temps ? ». Ranger par année de publication mélangerait dans une même
    # colonne les marchés à l'heure et les rattrapages de retard.
    duck.execute(
        f"""
        CREATE TEMP TABLE t_publication_annees AS
        SELECT annee,
               count(*)                                        AS nb_marches,
               count(*) FILTER (dans_delai)                    AS nb_dans_delai,
               100.0 * count(*) FILTER (dans_delai) / count(*) AS taux_dans_delai,
               CAST(quantile_disc(delai, 0.5) AS INTEGER)      AS delai_median,
               count(*) FILTER (delai > {JOURS_RETARD_LONG})   AS nb_plus_un_an,
               CAST(annee <= {cohorte_max} AS INTEGER)         AS cohorte_close
        FROM publies
        WHERE annee >= {ANNEE_MIN_PUBLICATION}
        GROUP BY annee
        ORDER BY annee
        """
    )

    # Ventilation par catégorie d'acheteur, restreinte aux cohortes CLOSES :
    # comparer l'État à une commune sur une cohorte encore ouverte
    # avantagerait mécaniquement celui qui publie vite : à la date de
    # l'ingestion, les retards de l'autre restent hors d'observation.
    # Les marchés sans catégorie ne forment PAS une catégorie « inconnue » :
    # les agréger en ligne fabriquerait un acteur qui n'existe pas. Ils sont
    # comptés à part (nb_sans_categorie) pour que la page puisse dire quelle
    # part de la population la ventilation laisse de côté.
    duck.execute(
        f"""
        CREATE TEMP TABLE t_publication_acheteurs AS
        SELECT categorie,
               count(*)                                             AS nb_marches,
               count(*) FILTER (dans_delai)                         AS nb_dans_delai,
               100.0 * count(*) FILTER (dans_delai) / count(*)      AS taux_dans_delai,
               CAST(quantile_disc(delai, 0.5) AS INTEGER)           AS delai_median,
               count(*) FILTER (delai > {JOURS_RETARD_LONG})        AS nb_plus_un_an,
               100.0 * count(*) FILTER (delai > {JOURS_RETARD_LONG})
                     / count(*)                                     AS taux_plus_un_an
        FROM publies
        WHERE categorie IS NOT NULL
          AND annee BETWEEN {ANNEE_MIN_COHORTE} AND {cohorte_max}
        GROUP BY categorie
        ORDER BY taux_dans_delai DESC, categorie
        """
    )

    # Ce que vaut la série : population de départ, écarts par motif, forme de
    # la distribution des délais. Une seule ligne (id = 1), même facture que
    # t_qualite_montants. Les quantiles sont DISCRETS : un délai est un
    # nombre entier de jours effectivement observé sur un marché ; interpoler
    # entre deux marchés produirait une demi-journée que personne n'a
    # attendue. Ils portent sur les seuls retenus — les écartés n'ont pas de
    # délai calculable, et leur en prêter un fausserait la médiane.
    duck.execute(
        f"""
        CREATE TEMP TABLE t_publication_qualite AS
        SELECT 1                                                  AS id,
               count(*)                                           AS nb_marches_source,
               count(*) FILTER (classe = 'retenu')                AS nb_retenus,
               count(*) FILTER (classe = 'sans_notification')     AS nb_sans_notification,
               count(*) FILTER (classe = 'sans_publication')      AS nb_sans_publication,
               count(*) FILTER (classe = 'dates_hors_bornes')     AS nb_dates_hors_bornes,
               count(*) FILTER (classe = 'publication_anterieure') AS nb_publication_anterieure,
               count(*) FILTER (classe = 'retenu' AND categorie IS NULL
                                AND annee BETWEEN {ANNEE_MIN_COHORTE}
                                            AND {cohorte_max})    AS nb_sans_categorie,
               CAST(quantile_disc(delai, 0.25)
                    FILTER (classe = 'retenu') AS INTEGER)        AS delai_q1,
               CAST(quantile_disc(delai, 0.50)
                    FILTER (classe = 'retenu') AS INTEGER)        AS delai_median,
               CAST(quantile_disc(delai, 0.75)
                    FILTER (classe = 'retenu') AS INTEGER)        AS delai_q3,
               CAST(quantile_disc(delai, 0.90)
                    FILTER (classe = 'retenu') AS INTEGER)        AS delai_d9,
               {DELAI_LEGAL_MOIS}                                 AS delai_legal_mois,
               {ANNEE_MIN_COHORTE}                                AS cohorte_min,
               {cohorte_max}                                      AS cohorte_max,
               CAST(max(publication) FILTER (classe = 'retenu')
                    AS VARCHAR)                                   AS date_observation_max
        FROM t_publication_classee
        """
    )

    nb_marches, date_max, nb_suspects = duck.execute(
        "SELECT count(*), max(date_notification), "
        "count(*) FILTER (montant_suspect = 1) FROM t_marches"
    ).fetchone()
    stats = {
        "lignes_parquet": lignes_parquet,
        "nb_marches": nb_marches,
        "date_max": date_max,
        "nb_suspects": nb_suspects,
    }
    return duck, stats


# ---------------------------------------------------------------------------
# Chargement SQLite (transaction unique : DELETE + INSERT, rollback si échec)
# ---------------------------------------------------------------------------

_TABLES = {
    "decp_marches": ("t_marches", _CHAMPS_MARCHE),
    "decp_agg_departement": (
        "t_agg_departement",
        ["departement_code", "departement_nom", "nb_marches",
         "montant_total", "nb_marches_ecretes"],
    ),
    "decp_agg_mois": ("t_agg_mois", ["mois", "nb_marches", "montant_total"]),
    "decp_top_acheteurs": (
        "t_top_acheteurs",
        ["rang", "siren", "nom", "nb_etablissements", "nb_marches",
         "montant_total"],
    ),
    "decp_top_titulaires": (
        "t_top_titulaires",
        ["rang", "siren", "nom", "categorie", "nb_etablissements",
         "nb_marches", "montant_total"],
    ),
    "decp_repartition": (
        "t_repartition",
        ["dimension", "valeur", "nb_marches", "montant_total"],
    ),
    "decp_qualite_montants": (
        "t_qualite_montants",
        ["id", "nb_marches", "montant_total", "nb_ecretes", "montant_ecretes",
         "nb_suspects", "montant_suspects", "montant_hors_suspects",
         "montant_brut", "nb_sans_montant", "plafond"],
    ),
    "decp_titulaires_qualite": (
        "t_titulaires_qualite",
        ["id", "nb_marches", "nb_marches_avec_titulaire", "nb_lignes",
         "nb_lignes_identifiables", "nb_lignes_ecartees",
         "montant_identifiable", "montant_ecarte", "nb_identifiants_ecartes",
         "nb_sirets", "nb_sirens", "nb_sirens_multi_etab"],
    ),
    "decp_acheteurs_qualite": (
        "t_acheteurs_qualite",
        ["id", "nb_marches", "nb_marches_avec_acheteur",
         "nb_marches_identifiables", "nb_marches_ecartes",
         "montant_identifiable", "montant_ecarte", "nb_identifiants_ecartes",
         "nb_sirets", "nb_sirens", "nb_sirens_multi_etab"],
    ),
    "decp_publication_qualite": (
        "t_publication_qualite",
        ["id", "nb_marches_source", "nb_retenus", "nb_sans_notification",
         "nb_sans_publication", "nb_dates_hors_bornes",
         "nb_publication_anterieure", "nb_sans_categorie", "delai_q1",
         "delai_median", "delai_q3", "delai_d9", "delai_legal_mois",
         "cohorte_min", "cohorte_max", "date_observation_max"],
    ),
    "decp_publication_annees": (
        "t_publication_annees",
        ["annee", "nb_marches", "nb_dans_delai", "taux_dans_delai",
         "delai_median", "nb_plus_un_an", "cohorte_close"],
    ),
    "decp_publication_acheteurs": (
        "t_publication_acheteurs",
        ["categorie", "nb_marches", "nb_dans_delai", "taux_dans_delai",
         "delai_median", "nb_plus_un_an", "taux_plus_un_an"],
    ),
    "decp_derniers_marches": ("t_derniers_marches", ["rang"] + _CHAMPS_MARCHE),
}


# Colonnes texte assainies au moment du transfert DuckDB → SQLite.
# POURQUOI ici et pas en SQL : la réparation du mojibake exige un
# aller-retour d'encodage octet par octet, hors de portée de DuckDB comme de
# SQLite. POURQUOI ces colonnes-là : ce sont les seules chaînes DECP servies
# à l'écran ou indexées.
#
# CHIFFRES RE-MESURÉS LE 30/08/2026 sur la base SERVIE (les précédents
# dataient du 20/08 et annonçaient 585 503 objets pour une table qui en
# compte 496 861 — c'est le compteur ajouté ci-dessous qui les tient
# désormais à jour, faute de quoi rien ne les recompte) :
# `decp_marches` = 496 861 lignes, `objet` non NULL sur 496 861, dont
# 1 460 portent au moins un contrôle C1 (U+0080-U+009F) et 19 un U+0002 ;
# les deux populations sont DISJOINTES (total `Cc` = 1 479).
# `acheteur_nom` (493 195 valeurs) et `titulaire_nom` (469 706) n'en portent
# AUCUN : tout le bénéfice de l'hygiène C1 porte sur `objet` seule, et c'est
# la raison d'être de la ventilation PAR COLONNE du bilan.
_COLONNES_ASSAINIES = frozenset({"objet", "acheteur_nom", "titulaire_nom"})
# `titulaires_json` est du JSON : on y répare le mojibake (qui n'affecte que
# le contenu des chaînes) mais on n'y touche PAS aux espaces, qui font partie
# de la syntaxe sérialisée. Il ne bascule donc PAS sur
# `assainir_texte_integral`, qui applique `normaliser_espaces`.
_COLONNES_MOJIBAKE_SEUL = frozenset({"titulaires_json"})


def _assainir_lot(
    lot: list[tuple],
    champs: list[str],
    bilan: dict[str, int] | None = None,
) -> list[tuple]:
    """Applique l'hygiène des chaînes aux colonnes texte d'un lot de lignes.

    Rendu tel quel si aucune colonne du lot n'est concernée : le pipeline
    DECP transfère ~600 000 lignes, on ne paye le coût que là où il sert.

    POURQUOI `assainir_texte_integral` ET PAS L'ÉDITION NATURELLE. Le code
    d'origine composait `normaliser_espaces(reparer_mojibake(v))`, qui ne
    répare PAS les contrôles C1 : `reparer_mojibake` sort immédiatement sur
    une chaîne sans « Ã », « Â » ni « â€ », et la donnée fautive de DECP est
    « â » + U+0080 + U+0093 **brute**, où l'« € » est encore l'octet 0x80.
    Le maillon était donc présent et inopérant. L'édition naturelle — ajouter
    `reparer_controles_cp1252` EN QUEUE de l'expression existante — fait bien
    tomber le compteur de C1 de 1 460 à 1, mais en FABRIQUANT du mojibake
    VISIBLE (« Hp 7488 â€“ mission de moe ») : elle matérialise l'« € » APRÈS
    le seul passage capable de le consommer. Mesuré le 30/08/2026 sur les
    1 460 lignes réelles : 147 en portent un marqueur visible sous cette
    édition contre 1 sous celle retenue, soit 146 FABRIQUÉES.
    **L'ordre gouverne, et il est figé une seule fois, dans
    `assainir_texte_integral`.**

    Le `or None` n'est pas décoratif : `assainir_texte_integral` rend `""` là
    où l'ancienne composition rendait `None`, et `objet` est une colonne
    nullable sans DEFAULT écrite sans garde au site d'appel. Sans lui, la
    bascule introduirait une régression `NULL → ''` invisible en base.

    `bilan` est un ACCUMULATEUR facultatif {colonne: valeurs changées},
    alimenté en place, et portant les colonnes DE CE LOT seulement —
    l'appelant le préfixe par sa table (cf. `charger`). POURQUOI un paramètre
    et pas un second membre de retour : le contrat « rendu tel quel » repose
    sur l'IDENTITÉ de l'objet (`_assainir_lot(lot, champs) is lot`), que
    verrouille `test_assainir_lot_laisse_passer_un_lot_sans_colonne_texte`.
    POURQUOI ventilé par colonne : un total global masquerait que la bascule
    est INERTE sur `acheteur_nom` et `titulaire_nom`, donc indiscernable d'un
    remède qui aurait porté sur les trois.
    """
    indices_pleins = [i for i, c in enumerate(champs) if c in _COLONNES_ASSAINIES]
    indices_moji = [i for i, c in enumerate(champs) if c in _COLONNES_MOJIBAKE_SEUL]
    if not indices_pleins and not indices_moji:
        return lot
    sorties = []
    for ligne in lot:
        cellules = list(ligne)
        for i in indices_pleins:
            v = cellules[i]
            if isinstance(v, str):
                cellules[i] = assainir_texte_integral(v) or None
                if bilan is not None and cellules[i] != v:
                    bilan[champs[i]] = bilan.get(champs[i], 0) + 1
        for i in indices_moji:
            v = cellules[i]
            if isinstance(v, str):
                cellules[i] = reparer_mojibake(v)
                if bilan is not None and cellules[i] != v:
                    bilan[champs[i]] = bilan.get(champs[i], 0) + 1
        sorties.append(tuple(cellules))
    return sorties


def _bilan_hygiene_neuf(champs: list[str]) -> dict[str, int]:
    """Accumulateur amorcé à ZÉRO sur les colonnes assainies de `champs`.

    C'est l'amorce qui rend le journal lisible : un compteur qui ne
    mentionnerait que les colonnes effectivement modifiées tairait les
    colonnes saines, et un remède débranché rendrait alors exactement la même
    sortie qu'une donnée propre. Une table sans colonne texte rend un
    accumulateur vide, donc n'écrit rien au journal.
    """
    traitees = _COLONNES_ASSAINIES | _COLONNES_MOJIBAKE_SEUL
    return {c: 0 for c in champs if c in traitees}


def _reconcilier_schema(conn: sqlite3.Connection) -> list[str]:
    """Supprime les tables decp_* dont les colonnes ne sont plus celles attendues.

    POURQUOI ce filet est nécessaire : `CREATE TABLE IF NOT EXISTS` ne touche
    PAS une table déjà présente. En intégration continue, la base est NEUVE à
    chaque passage — les tables y naissent au schéma courant et tout passe. La
    base SERVIE, elle, survit d'un déploiement à l'autre (le déploiement
    nettoie l'arbre de travail, pas les données) et porte donc encore
    l'ANCIEN schéma, parfois complété au fil du temps par des ALTER TABLE.
    Un changement de colonnes y ferait échouer l'INSERT (« has no column
    named … ») ; l'ingestion étant tout-ou-rien, c'est le déploiement ENTIER
    qui tombe — sur un défaut que l'intégration continue ne peut pas voir.

    POURQUOI un contrôle GÉNÉRAL, sur toutes les tables de `_TABLES`, plutôt
    qu'une migration écrite pour celle qui change aujourd'hui : le piège se
    reproduira au prochain changement de schéma, tout aussi invisible en
    intégration continue. Un filet qui vaut une fois vaut d'être posé une
    fois pour toutes.

    POURQUOI un DROP et non un ALTER : ces tables sont INTÉGRALEMENT
    recalculées à chaque passe (DELETE puis INSERT, juste après) — un DROP n'y
    perd aucune donnée, là où un ALTER devrait inventer de quoi remplir la
    colonne apparue et deviner quoi faire de celle qui disparaît.

    Une table ABSENTE n'est pas une discordance : `_SCHEMA` la créera. Le
    rejeu de `_SCHEMA` par l'appelant doit suivre CET appel, car le DROP
    emporte aussi les index de la table, et c'est `_SCHEMA` qui les repose.

    LIMITE assumée : la comparaison porte sur les NOMS de colonnes, seuls à
    pouvoir faire échouer l'INSERT. Un changement de type ou de contrainte à
    jeu de colonnes constant passerait à travers — il n'empêche pas
    l'écriture, et le rattraper demanderait de comparer du DDL à du DDL.
    Retourne la liste des tables supprimées (vide au régime nominal).
    """
    discordantes = []
    for table, (_, champs) in _TABLES.items():
        # PRAGMA table_info : (cid, name, type, notnull, dflt_value, pk).
        reelles = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        if reelles and reelles != set(champs):
            discordantes.append(table)
    for table in discordantes:
        conn.execute(f"DROP TABLE {table}")
        log.info("migration : %s supprimée (colonnes obsolètes), sera recréée", table)
    return discordantes


def charger(conn: sqlite3.Connection, duck: duckdb.DuckDBPyConnection) -> dict[str, int]:
    """Réécrit les 13 tables decp_* depuis les tables temp DuckDB.

    Contrôle de schéma, CREATE TABLE IF NOT EXISTS, puis DELETE/INSERT dans la
    transaction en cours (aucun commit ici — l'appelant commet, cf. main, ou
    annule). Les colonnes texte sont assainies au passage (cf.
    `_assainir_lot`) et le bilan de cette hygiène est journalisé
    INCONDITIONNELLEMENT, zéro compris, ventilé par table et par colonne.
    Retourne {table: lignes insérées}.
    """
    # Ordre imposé : contrôle → DROP des tables discordantes → `_SCHEMA` (qui
    # les recrée AVEC leurs index) → DELETE/INSERT. Cf. `_reconcilier_schema`
    # pour le pourquoi : la base servie est persistante et migrée, celle de
    # l'intégration continue est neuve, et seul le premier cas casse.
    _reconcilier_schema(conn)
    conn.executescript(_SCHEMA)  # idempotent, ne détruit rien
    # Bilan d'hygiène AMORCÉ À ZÉRO, et ventilé par TABLE.COLONNE. Trois
    # raisons, toutes mesurées le 30/08/2026 : (1) un total global masquerait
    # que la bascule est INERTE sur `acheteur_nom` et `titulaire_nom`, donc
    # indiscernable d'un remède qui aurait porté sur les trois ; (2) `objet`
    # est assaini dans `decp_marches` ET dans `decp_derniers_marches`, qui en
    # dérive et qui est la SEULE des deux réellement affichée — les agréger
    # sous une clé unique rendrait un nombre que personne ne peut recomposer ;
    # (3) une colonne saine doit apparaître avec son `0`, faute de quoi un
    # remède redevenu inopérant serait indiscernable d'une donnée propre.
    # C'est exactement le défaut que cette tranche corrige : le maillon était
    # présent et muet depuis le 20/08.
    bilan_hygiene: dict[str, int] = {}
    comptes: dict[str, int] = {}
    for table, (source, champs) in _TABLES.items():
        conn.execute(f"DELETE FROM {table}")
        colonnes = ", ".join(champs)
        marqueurs = ", ".join("?" for _ in champs)
        curseur = duck.execute(f"SELECT {colonnes} FROM {source}")
        bilan_table = _bilan_hygiene_neuf(champs)
        total = 0
        while True:
            lot = curseur.fetchmany(50_000)
            if not lot:
                break
            conn.executemany(
                f"INSERT INTO {table} ({colonnes}) VALUES ({marqueurs})",
                _assainir_lot(lot, champs, bilan_table),
            )
            total += len(lot)
        comptes[table] = total
        bilan_hygiene.update({f"{table}.{c}": n for c, n in bilan_table.items()})
    log.info(
        "hygiène des chaînes : %d valeur(s) assainie(s) (mojibake, contrôles "
        "C1 cp1252, espaces) — %s",
        sum(bilan_hygiene.values()),
        ", ".join(f"{c}={n}" for c, n in sorted(bilan_hygiene.items())),
    )
    return comptes


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------


def main() -> int:
    date_ref = date.today()
    try:
        parquet = telecharger(URL_PARQUET, FICHIER_RAW, max_age_heures=CACHE_HEURES)
        duck, stats = transformer(parquet, date_ref)

        # Garde-fous « build cassé » : on refuse d'écraser des tables saines.
        if stats["lignes_parquet"] < MIN_LIGNES_PARQUET:
            raise RuntimeError(
                f"parquet suspect : {stats['lignes_parquet']} lignes "
                f"(< {MIN_LIGNES_PARQUET}) — base non modifiée"
            )
        if stats["date_max"] is None or date.fromisoformat(stats["date_max"]) < (
            date_ref - timedelta(days=MAX_RETARD_JOURS)
        ):
            raise RuntimeError(
                f"données trop anciennes (notification max : {stats['date_max']}) "
                f"— base non modifiée"
            )

        conn = db.init_db()
    except Exception:
        log.exception("échec avant écriture — base intacte")
        return 1

    try:
        comptes = charger(conn, duck)
        db.upsert_meta(  # commet la transaction (DELETE/INSERT compris)
            conn,
            source_id=SOURCE_ID,
            nom="DECP consolidées au format tabulaire (marchés publics)",
            url=URL_PAGE,
            licence="Licence Ouverte 2.0",
            frequence="quotidienne",
            date_donnees=stats["date_max"],
            lignes=comptes["decp_marches"],
            notes=(
                f"consolidation communautaire decp-processing (Colin Maudry), "
                f"à créditer ; la date retenue est celle de la notification "
                f"initiale du marché — min(dateNotification) sur toutes ses "
                f"lignes, avenants compris — et non celle du dernier avenant ; "
                f"les fenêtres portent sur elle, les montants et titulaires "
                f"sur la version courante ; les classements titulaires et "
                f"acheteurs sont regroupés par ENTREPRISE (SIREN), les "
                f"identifiants non conformes en étant écartés et comptés à "
                f"part ; fenêtres : détail {MOIS_DETAIL} "
                f"mois, agrégats {MOIS_AGGREGATS} mois, série {MOIS_SERIE} "
                f"mois ; agrégats écrêtés à {PLAFOND_ECRETAGE_EUR:.0f} € "
                f"({stats['nb_suspects']} marchés suspects marqués) ; montants "
                f"d'accords-cadres = maximums ; latence légale de publication "
                f"jusqu'à 2 mois ; {stats['lignes_parquet']} lignes au parquet"
            ),
        )
    except Exception:
        conn.rollback()
        log.exception("échec pendant l'écriture — transaction annulée")
        return 1
    finally:
        conn.close()
        duck.close()

    log.info(
        "OK — %s ; notification max %s",
        json.dumps(comptes, ensure_ascii=False),
        stats["date_max"],
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

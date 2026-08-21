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

- decp_top_acheteurs / decp_top_titulaires — 12 derniers mois, top 50 :
  rang (PK), siret, nom, nb_marches, montant_total (écrêté ; pour les
  titulaires, montant du marché divisé par le nombre de co-titulaires,
  et catégorie PME/ETI/GE si connue).

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
777 054 marchés, les 12 mois 213 283 et les 30 derniers jours 5 894 ; datés
à leur ligne courante, ces mêmes marchés en donneraient respectivement
861 849 (dont 217 827, soit 25,3 %, rangés dans le mauvais mois), 297 323
et 16 065.

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
    normaliser_espaces,
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

# Garde-fous « build cassé » (SOURCES.md S1, plan B/C1) : en deçà, on refuse
# d'écraser les tables (le parquet consolidé fait ~3,2 M de lignes).
MIN_LIGNES_PARQUET = 1_000_000
MAX_RETARD_JOURS = 60

# Écrêtage SQL d'un montant : NULL reste NULL (least() DuckDB IGNORE les
# NULL — sans ce garde, un montant manquant « deviendrait » le plafond).
_SQL_ECRETE = "CASE WHEN {col} IS NULL THEN NULL ELSE least({col}, {plafond}) END"

# Normalisation d'un libellé pour regroupement (casse, accents, apostrophes) :
# « Appel d'offres ouvert » et « Appel d offres ouvert » → même clé.
_SQL_CLE_LIBELLE = (
    "trim(regexp_replace(strip_accents(lower("
    "replace(replace({col}, chr(8217), ' '), '''', ' ')"
    ")), '\\s+', ' ', 'g'))"
)

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
    rang          INTEGER PRIMARY KEY,
    siret         TEXT,
    nom           TEXT,
    nb_marches    INTEGER NOT NULL,
    montant_total REAL
);

CREATE TABLE IF NOT EXISTS decp_top_titulaires (
    rang          INTEGER PRIMARY KEY,
    siret         TEXT,
    nom           TEXT,
    categorie     TEXT,
    nb_marches    INTEGER NOT NULL,
    montant_total REAL
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

    duck.execute(
        f"""
        CREATE TEMP TABLE t_top_acheteurs AS
        SELECT row_number() OVER (ORDER BY sum(montant_ecrete) DESC NULLS LAST,
                                  acheteur_siret) AS rang,
               acheteur_siret                     AS siret,
               any_value(acheteur_nom)            AS nom,
               count(*)                           AS nb_marches,
               sum(montant_ecrete)                AS montant_total
        FROM recents
        WHERE acheteur_siret IS NOT NULL
        GROUP BY acheteur_siret
        ORDER BY rang
        LIMIT {NB_TOP}
        """
    )

    # Top titulaires : montant écrêté du marché réparti à parts égales entre
    # co-titulaires (convention documentée — le montant DECP est celui du
    # marché entier, pas de ventilation à la source).
    duck.execute(
        f"""
        CREATE TEMP TABLE t_top_titulaires AS
        SELECT row_number() OVER (ORDER BY sum(r.montant_ecrete / r.nb_titulaires)
                                  DESC NULLS LAST, t.titulaire_id) AS rang,
               t.titulaire_id                                      AS siret,
               any_value(t.nom)                                    AS nom,
               any_value(t.categorie)                              AS categorie,
               count(*)                                            AS nb_marches,
               sum(r.montant_ecrete / r.nb_titulaires)             AS montant_total
        FROM t_titulaires t
        JOIN recents r USING (uid)
        GROUP BY t.titulaire_id
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

    duck.execute(
        f"""
        CREATE TEMP TABLE t_derniers_marches AS
        SELECT row_number() OVER (ORDER BY date_notification DESC, uid) AS rang, *
        FROM t_marches
        ORDER BY date_notification DESC, uid
        LIMIT {NB_DERNIERS}
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
        ["rang", "siret", "nom", "nb_marches", "montant_total"],
    ),
    "decp_top_titulaires": (
        "t_top_titulaires",
        ["rang", "siret", "nom", "categorie", "nb_marches", "montant_total"],
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
    "decp_derniers_marches": ("t_derniers_marches", ["rang"] + _CHAMPS_MARCHE),
}


# Colonnes texte assainies au moment du transfert DuckDB → SQLite.
# POURQUOI ici et pas en SQL : la réparation du mojibake exige un
# aller-retour d'encodage octet par octet, hors de portée de DuckDB comme de
# SQLite. POURQUOI ces colonnes-là : ce sont les seules chaînes DECP servies
# à l'écran ou indexées. Mesuré le 20/08/2026 sur la base de production
# (585 503 objets) : 308 objets porteurs de mojibake → 5 irréparables,
# 0 régression ; 77 306 objets porteurs d'espaces parasites (insécables,
# retours ligne, bords).
_COLONNES_ASSAINIES = frozenset({"objet", "acheteur_nom", "titulaire_nom"})
# `titulaires_json` est du JSON : on y répare le mojibake (qui n'affecte que
# le contenu des chaînes) mais on n'y touche PAS aux espaces, qui font partie
# de la syntaxe sérialisée.
_COLONNES_MOJIBAKE_SEUL = frozenset({"titulaires_json"})


def _assainir_lot(lot: list[tuple], champs: list[str]) -> list[tuple]:
    """Applique l'hygiène des chaînes aux colonnes texte d'un lot de lignes.

    Rendu tel quel si aucune colonne du lot n'est concernée : le pipeline
    DECP transfère ~600 000 lignes, on ne paye le coût que là où il sert.
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
                cellules[i] = normaliser_espaces(reparer_mojibake(v)) or None
        for i in indices_moji:
            v = cellules[i]
            if isinstance(v, str):
                cellules[i] = reparer_mojibake(v)
        sorties.append(tuple(cellules))
    return sorties


def charger(conn: sqlite3.Connection, duck: duckdb.DuckDBPyConnection) -> dict[str, int]:
    """Réécrit les 8 tables decp_* depuis les tables temp DuckDB.

    CREATE TABLE IF NOT EXISTS puis DELETE/INSERT dans la transaction en
    cours (aucun commit ici — l'appelant commet, cf. main, ou annule).
    Les colonnes texte sont assainies au passage (cf. `_assainir_lot`).
    Retourne {table: lignes insérées}.
    """
    conn.executescript(_SCHEMA)  # idempotent, ne détruit rien
    comptes: dict[str, int] = {}
    for table, (source, champs) in _TABLES.items():
        conn.execute(f"DELETE FROM {table}")
        colonnes = ", ".join(champs)
        marqueurs = ", ".join("?" for _ in champs)
        curseur = duck.execute(f"SELECT {colonnes} FROM {source}")
        total = 0
        while True:
            lot = curseur.fetchmany(50_000)
            if not lot:
                break
            conn.executemany(
                f"INSERT INTO {table} ({colonnes}) VALUES ({marqueurs})",
                _assainir_lot(lot, champs),
            )
            total += len(lot)
        comptes[table] = total
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
                f"sur la version courante ; fenêtres : détail {MOIS_DETAIL} "
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

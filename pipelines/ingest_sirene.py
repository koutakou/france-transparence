"""S18 — Stock Sirene (INSEE) : référentiel des unités légales citées en base.

Ce que cette source apporte, et pourquoi elle ne fait PAS ce qu'on croit
-----------------------------------------------------------------------
L'intuition première est qu'un référentiel Sirene sert à donner un nom aux
SIREN. C'est faux ici, et la mesure le dit : sur les 164 414 SIREN cités par
l'ensemble des tables, 418 seulement (0,25 %) n'ont aucun nom nulle part.
Le nom, les autres sources le fournissent déjà.

Ce qui manque réellement, mesuré sur la base du 21/08/2026 :

1. **Les attributs.** Deux tiers des SIREN cités (108 739 sur 164 414, 66 %)
   n'ont ni catégorie juridique, ni code d'activité, ni état administratif,
   ni appartenance à l'économie sociale et solidaire. Les 55 675 qui en ont
   ne le doivent qu'à `subventions_associations`, dont le champ d'état est
   par ailleurs inexploitable (il concatène état et date, et charrie des
   dates sérielles Excel non converties).
2. **La stabilité du nom.** 2 536 SIREN titulaires de marchés portent 6 437
   libellés distincts dans les DECP — la même entreprise écrite de deux ou
   trois façons. Sans dénomination de référence, tout dénombrement ou tout
   classement par nom éclate une entreprise en plusieurs.
3. **La validité de l'identifiant.** 7 406 lignes DECP portent un SIRET
   malformé (numéros de TVA intracommunautaire, `00001`, `999999999`…).

D'où le périmètre retenu : un référentiel d'ATTRIBUTS, restreint aux SIREN
que la base cite réellement.

Pourquoi restreindre (et pas ingérer le stock entier)
-----------------------------------------------------
Le fichier compte 29 922 486 unités légales. La base n'en cite que 164 414,
soit 0,55 %. Mesuré sur un proxy local (`subventions_associations`, mêmes
champs Sirene), le coût est de 155 octets par ligne : 24 Mio pour le
référentiel restreint contre 5,8 Gio pour le stock complet, index non
compris, sur une base qui pèse 470 Mio et une partition unique de 39 Go.
Charger 238 fois plus de données pour un usage identique n'a pas de contre-
partie : le stock entier n'apporterait que des unités légales que rien dans
la base ne mentionne.

Conséquence assumée : ce pipeline DÉPEND des tables des autres. Il doit donc
passer en dernier dans `PIPELINES` (Makefile). Sur une base neuve, il refuse
d'écrire plutôt que de produire un référentiel vide (cf. MIN_SIREN_CITES).

Données personnelles — ce qui n'est délibérément PAS ingéré
------------------------------------------------------------
`StockUniteLegale` décrit aussi les entrepreneurs individuels : nom de
naissance, nom d'usage, quatre prénoms, prénom usuel, pseudonyme, sexe.
Ce sont des données à caractère personnel, et 6 924 des SIREN cités par la
base en relèvent.

Deux règles, tenues par la requête d'extraction elle-même :

- **aucun nom, prénom, pseudonyme ni sexe n'est lu du fichier.** Ces
  colonnes ne figurent pas dans le SELECT : une personne physique entre au
  référentiel avec sa catégorie juridique, son activité et son état, jamais
  avec son identité. `denomination` reste NULL, `est_personne_physique` vaut 1.
- **`statutDiffusionUniteLegale` est respecté** : les unités non diffusibles
  (969 des SIREN cités) sont écartées, c'est l'expression du droit
  d'opposition prévu par l'article A123-96 du code de commerce.

La minimisation n'est pas ici une précaution de façade : le référentiel sert
à qualifier des personnes morales attributaires de marchés ou subventions,
et cet usage n'a besoin d'aucune identité de personne physique.

Format et outil
---------------
Le parquet (705 Mo) plutôt que le CSV zippé (971 Mo) : lecture colonnaire —
seules 13 des 35 colonnes sont lues —, et la semi-jointure sur les SIREN
cités s'exécute en moins d'une seconde contre 159 s de parcours CSV en
Python. DuckDB est déjà une dépendance du projet (`ingest_decp`).

Sources et pièges
-----------------
- Les URL `static.data.gouv.fr` sont horodatées et changent à chaque
  millésime : la ressource est re-résolue par l'API dataset à chaque
  exécution (même piège que S17/RNE et S38/CADA).
- L'ancien chemin `files.data.gouv.fr/insee-sirene/` ne sert plus les fichiers.
  Attention à la formulation, vérifiée le 21/08/2026 : le RÉPERTOIRE répond
  200 — il ne contient plus qu'un `migration-fichiers-sirene.txt` de 215
  octets qui renvoie vers data.gouv.fr —, ce sont les FICHIERS qui répondent
  404. Un contrôle de vie qui se contenterait d'interroger le répertoire
  conclurait donc que la source va bien.
- `categorieJuridiqueUniteLegale` est un entier dans le parquet alors que
  c'est un code de nomenclature à quatre chiffres. Il est converti en texte,
  et l'intérêt est là : conservé en entier, il ne se joindrait plus à la
  nomenclature INSEE, qui est textuelle. Le `lpad` sur quatre positions qui
  l'accompagne est, lui, purement défensif : sur trois millions de lignes
  réelles échantillonnées, tous les codes font déjà quatre chiffres. Il ne
  répare aucun cas connu, il empêche seulement qu'un code à zéro initial
  arrive un jour amputé.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import duckdb
import requests

from pipelines import db
from pipelines.common import obtenir_logger, session_http, telecharger

log = obtenir_logger("ingest_sirene")

SOURCE_ID = "S18"
SOURCE_NOM = "Stock Sirene — unités légales (INSEE via data.gouv.fr)"
SOURCE_URL = (
    "https://www.data.gouv.fr/datasets/"
    "base-sirene-des-entreprises-et-de-leurs-etablissements-siren-siret"
)
SOURCE_LICENCE = "Licence Ouverte 2.0"
SOURCE_FREQUENCE = "mensuelle"

URL_DATASET_API = (
    "https://www.data.gouv.fr/api/1/datasets/5b7ffc618b4c4169d30727e0/"
)
# Sélection de la ressource : le titre porte « StockUniteLegale - 01 août 2026
# (format parquet) ». On exige les deux marqueurs et on EXCLUT « Historique »,
# qui est un autre fichier dont le titre contient aussi « StockUniteLegale ».
MARQUEUR_RESSOURCE = "stockunitelegale"
MARQUEUR_FORMAT = "parquet"
MARQUEUR_EXCLU = "historique"

FICHIER_RAW = "sirene/StockUniteLegale.parquet"
# Millésime mensuel : re-télécharger 705 Mo par jour n'apporterait rien et
# pèserait sur l'amont. 30 jours de cache restent en deçà de la cadence.
# NB : ce TTL n'a d'effet que si la purge quotidienne de `data/raw` épargne
# ce fichier (voir /etc/france-transparence/cache-long.conf côté serveur).
CACHE_HEURES = 30 * 24.0

# Garde-fous « build cassé » : en deçà, on refuse d'écraser la table.
# Le stock compte ~29,9 M d'unités légales ; un fichier tronqué ou une
# ressource remplacée par un extrait doit échouer, pas s'ingérer.
MIN_LIGNES_PARQUET = 20_000_000
# Nombre minimal de SIREN cités par le reste de la base. Une base neuve (ou
# un `make ingest-sirene` lancé seul avant les autres pipelines) en compte
# zéro : mieux vaut un échec franc qu'un référentiel vide écrit en silence.
MIN_SIREN_CITES = 50_000
# Taux d'appariement plancher. Mesuré à 99,80 % le 21/08/2026 ; sous 90 %,
# c'est le signe d'un fichier ou d'un format changé, pas d'une dérive.
TAUX_APPARIEMENT_MIN = 0.90

_DDL = """
CREATE TABLE IF NOT EXISTS sirene_unites_legales (
    siren                      TEXT PRIMARY KEY,
    denomination               TEXT,      -- NULL pour les personnes physiques
    sigle                      TEXT,
    est_personne_physique      INTEGER NOT NULL DEFAULT 0,
    categorie_juridique        TEXT,      -- code INSEE à 4 chiffres
    activite_principale        TEXT,      -- code NAF
    nomenclature_activite      TEXT,      -- NAFRev2, NAP…
    tranche_effectifs          TEXT,
    annee_effectifs            INTEGER,
    categorie_entreprise       TEXT,      -- PME / ETI / GE
    etat_administratif         TEXT,      -- A (active) / C (cessée)
    date_creation              TEXT,
    economie_sociale_solidaire INTEGER,   -- 1 / 0 / NULL (non renseigné)
    societe_mission            INTEGER
);
CREATE INDEX IF NOT EXISTS idx_sirene_cat_juridique
    ON sirene_unites_legales(categorie_juridique);
CREATE INDEX IF NOT EXISTS idx_sirene_activite
    ON sirene_unites_legales(activite_principale);
CREATE INDEX IF NOT EXISTS idx_sirene_etat
    ON sirene_unites_legales(etat_administratif);
"""

# Les SIREN cités par le reste de la base. Chaque terme est filtré sur le
# format (GLOB) : les identifiants malformés n'ont rien à chercher dans
# Sirene, et les laisser passer gonflerait le taux de non-appariement d'un
# bruit qui n'est pas une anomalie d'appariement.
_G9 = "[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]"
_G14 = _G9 + "[0-9][0-9][0-9][0-9][0-9]"

SQL_SIREN_CITES = f"""
WITH cotitulaires AS (
    SELECT json_extract(j.value, '$.siret') AS siret
    FROM decp_marches m, json_each(m.titulaires_json) j
    WHERE m.titulaires_json IS NOT NULL AND m.titulaires_json <> ''
)
SELECT substr(siret, 1, 9) FROM cotitulaires WHERE siret GLOB '{_G14}'
UNION SELECT substr(titulaire_siret, 1, 9) FROM decp_marches
    WHERE titulaire_siret GLOB '{_G14}'
UNION SELECT substr(acheteur_siret, 1, 9) FROM decp_marches
    WHERE acheteur_siret GLOB '{_G14}'
UNION SELECT siren FROM subventions_associations WHERE siren GLOB '{_G9}'
UNION SELECT identifiant_national FROM lobby_entites
    WHERE type_identifiant = 'SIREN' AND identifiant_national GLOB '{_G9}'
UNION SELECT acheteur_siren FROM marches_a_venir
    WHERE acheteur_siren GLOB '{_G9}'
UNION SELECT siren FROM entites WHERE siren GLOB '{_G9}'
UNION SELECT siren FROM collectivites_communes_series WHERE siren GLOB '{_G9}'
UNION SELECT siren FROM collectivites_communes_top200 WHERE siren GLOB '{_G9}'
UNION SELECT siren FROM collectivites_conseils_departementaux
    WHERE siren GLOB '{_G9}'
UNION SELECT siren FROM collectivites_regions WHERE siren GLOB '{_G9}'
UNION SELECT substr(siret, 1, 9) FROM decp_top_acheteurs WHERE siret GLOB '{_G14}'
UNION SELECT substr(siret, 1, 9) FROM decp_top_titulaires WHERE siret GLOB '{_G14}'
"""

# Extraction DuckDB. Le SELECT est la garantie de minimisation : ni
# nomUniteLegale, ni nomUsageUniteLegale, ni prenom*, ni prenomUsuel, ni
# pseudonyme, ni sexe n'y figurent — voir la docstring du module.
SQL_EXTRACTION = """
SELECT
    s.siren,
    nullif(trim(coalesce(s.denominationUniteLegale, '')), '')      AS denomination,
    nullif(trim(coalesce(s.sigleUniteLegale, '')), '')             AS sigle,
    CASE WHEN s.categorieJuridiqueUniteLegale = 1000 THEN 1 ELSE 0 END
                                                                   AS est_personne_physique,
    lpad(CAST(s.categorieJuridiqueUniteLegale AS VARCHAR), 4, '0')  AS categorie_juridique,
    nullif(trim(coalesce(s.activitePrincipaleUniteLegale, '')), '') AS activite_principale,
    nullif(trim(coalesce(s.nomenclatureActivitePrincipaleUniteLegale, '')), '')
                                                                   AS nomenclature_activite,
    nullif(trim(coalesce(s.trancheEffectifsUniteLegale, '')), '')   AS tranche_effectifs,
    s.anneeEffectifsUniteLegale                                     AS annee_effectifs,
    nullif(trim(coalesce(s.categorieEntreprise, '')), '')           AS categorie_entreprise,
    nullif(trim(coalesce(s.etatAdministratifUniteLegale, '')), '')  AS etat_administratif,
    CAST(s.dateCreationUniteLegale AS VARCHAR)                      AS date_creation,
    CASE s.economieSocialeSolidaireUniteLegale
         WHEN 'O' THEN 1 WHEN 'N' THEN 0 ELSE NULL END              AS economie_sociale_solidaire,
    CASE s.societeMissionUniteLegale
         WHEN 'O' THEN 1 WHEN 'N' THEN 0 ELSE NULL END              AS societe_mission
FROM retenues s
WHERE s.statutDiffusionUniteLegale = 'O'
ORDER BY s.siren
"""


# ---------------------------------------------------------------------------
# Résolution de la ressource amont
# ---------------------------------------------------------------------------


def resoudre_ressource(session: requests.Session | None = None,
                       timeout: int = 60) -> dict[str, str]:
    """Interroge l'API data.gouv.fr et retourne la ressource parquet du stock.

    Retourne `{"url", "titre", "derniere_modification", "octets"}`.
    Lève RuntimeError si la ressource a disparu : mieux vaut un échec franc
    qu'un repli silencieux sur un autre fichier du même dataset (le jeu en
    compte 24, dont trois autres stocks).
    """
    s = session or session_http()
    reponse = s.get(URL_DATASET_API, timeout=timeout)
    reponse.raise_for_status()
    dataset = reponse.json()
    for ressource in dataset.get("resources", []):
        titre = (ressource.get("title") or "").strip()
        minuscules = titre.lower()
        if (MARQUEUR_RESSOURCE in minuscules
                and MARQUEUR_FORMAT in minuscules
                and MARQUEUR_EXCLU not in minuscules):
            return {
                "url": ressource["url"],
                "titre": titre,
                "derniere_modification": (ressource.get("last_modified") or "")[:10],
                "octets": str(ressource.get("filesize") or ""),
            }
    titres = [r.get("title") for r in dataset.get("resources", [])]
    raise RuntimeError(
        f"ressource « {MARQUEUR_RESSOURCE} / {MARQUEUR_FORMAT} » absente du "
        f"dataset Sirene ; présentes : {titres}"
    )


# ---------------------------------------------------------------------------
# Lecture des SIREN cités
# ---------------------------------------------------------------------------


def siren_cites(conn: sqlite3.Connection) -> list[str]:
    """SIREN bien formés cités par le reste de la base, dédoublonnés.

    Sur une base neuve, la requête échoue dès la première table absente
    (`decp_marches`) et l'erreur est retraduite en RuntimeError lisible : on
    n'atteint donc PAS le message de MIN_SIREN_CITES, qui ne sert qu'au cas
    où les tables existent mais sont vides ou presque. C'est voulu — la
    tolérance table par table demanderait treize requêtes séparées pour un
    seul gain de confort, alors que les deux chemins mènent au même endroit :
    échec franc, base intacte, et un message qui dit de lancer `make ingest`.
    """
    try:
        lignes = conn.execute(SQL_SIREN_CITES).fetchall()
    except sqlite3.OperationalError as erreur:
        raise RuntimeError(
            f"lecture des SIREN cités impossible ({erreur}) — ce pipeline "
            "suppose les autres déjà passés ; lancer `make ingest`"
        ) from erreur
    return [ligne[0] for ligne in lignes]


# ---------------------------------------------------------------------------
# Transformation (pure : parquet + liste de SIREN → lignes)
# ---------------------------------------------------------------------------


def transformer(chemin_parquet: str | Path,
                sirens: list[str]) -> tuple[list[tuple], dict]:
    """Extrait du parquet les unités légales des `sirens`, sans réseau ni SQLite.

    Retourne (lignes, stats) où stats porte lignes_parquet, siren_cites,
    apparies, taux, date_donnees, personnes_physiques, ecartes_non_diffusibles.
    """
    chemin = str(Path(chemin_parquet))
    duck = duckdb.connect()
    duck.execute("SET threads TO 4")

    lignes_parquet = duck.execute(
        "SELECT count(*) FROM read_parquet(?)", [chemin]
    ).fetchone()[0]
    if lignes_parquet < MIN_LIGNES_PARQUET:
        raise RuntimeError(
            f"parquet Sirene suspect : {lignes_parquet} lignes "
            f"(< {MIN_LIGNES_PARQUET}) — base non modifiée"
        )

    # `unnest` d'une liste passée en paramètre : une seule instruction, là où
    # un executemany insère ligne à ligne (mesuré : 164 414 SIREN en 0,2 s
    # contre plusieurs minutes).
    duck.execute(
        "CREATE TEMP TABLE cites AS SELECT DISTINCT unnest(?) AS siren",
        [sirens],
    )

    # Une seule passe sur les 705 Mo : le parquet restreint aux SIREN cités
    # est matérialisé une fois, puis relu pour l'extraction et les compteurs.
    # Relire `read_parquet` à chaque question coûtait 4 minutes par ingestion.
    duck.execute(
        """
        CREATE TEMP TABLE retenues AS
        SELECT s.* FROM read_parquet(?) s JOIN cites c ON c.siren = s.siren
        """,
        [chemin],
    )

    lignes = duck.execute(SQL_EXTRACTION).fetchall()

    # Millésime : date du dernier traitement des unités RETENUES, pas la date
    # de publication du dataset (db.upsert_meta l'exige explicitement).
    date_donnees = duck.execute(
        """
        SELECT CAST(max(dateDernierTraitementUniteLegale) AS DATE)
        FROM retenues WHERE statutDiffusionUniteLegale = 'O'
        """
    ).fetchone()[0]

    non_diffusibles = duck.execute(
        "SELECT count(*) FROM retenues WHERE statutDiffusionUniteLegale <> 'O'"
    ).fetchone()[0]
    duck.close()

    cites = len(set(sirens))
    # Doublon de SIREN dans le stock : impossible en principe (une unité
    # légale par SIREN), mais `siren` est PRIMARY KEY côté SQLite et un
    # executemany échouerait à mi-parcours. Le dire ici donne un message
    # utile plutôt qu'une IntegrityError sans contexte.
    if len({ligne[0] for ligne in lignes}) != len(lignes):
        raise RuntimeError(
            f"{len(lignes) - len({l[0] for l in lignes})} SIREN en double dans "
            "le stock amont — hypothèse « une unité légale par SIREN » rompue, "
            "base non modifiée"
        )

    # Le taux mesure L'APPARIEMENT, donc les unités TROUVÉES dans le stock —
    # diffusibles ou non. Le rapporter aux seules unités retenues mélangerait
    # deux phénomènes sans rapport : un format amont qui change (ce que ce
    # garde-fou doit voir) et des personnes qui exercent leur droit
    # d'opposition à la diffusion (ce qui est normal et hors de notre main).
    trouves = len(lignes) + non_diffusibles
    stats = {
        "lignes_parquet": lignes_parquet,
        "siren_cites": cites,
        "apparies": len(lignes),
        "trouves": trouves,
        "taux": (trouves / cites) if cites else 0.0,
        "date_donnees": date_donnees.isoformat() if date_donnees else None,
        "personnes_physiques": sum(1 for l in lignes if l[3] == 1),
        "ecartes_non_diffusibles": non_diffusibles,
    }
    return lignes, stats


# ---------------------------------------------------------------------------
# Écriture
# ---------------------------------------------------------------------------


def charger(conn: sqlite3.Connection, lignes: list[tuple]) -> int:
    """Réécrit `sirene_unites_legales` en une transaction (tout ou rien)."""
    conn.executescript(_DDL)
    conn.commit()
    with conn:
        conn.execute("DELETE FROM sirene_unites_legales")
        conn.executemany(
            """
            INSERT INTO sirene_unites_legales
                (siren, denomination, sigle, est_personne_physique,
                 categorie_juridique, activite_principale, nomenclature_activite,
                 tranche_effectifs, annee_effectifs, categorie_entreprise,
                 etat_administratif, date_creation, economie_sociale_solidaire,
                 societe_mission)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            lignes,
        )
    return len(lignes)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def executer(chemin_db: str | Path | None = None,
             max_age_heures: float | None = CACHE_HEURES,
             chemin_parquet: str | Path | None = None,
             session: requests.Session | None = None) -> dict:
    """Pipeline complet : résout la ressource, télécharge, extrait, écrit.

    `chemin_parquet` court-circuite le réseau (tests, rejeu sur un extrait).
    """
    conn = db.init_db(chemin=chemin_db)
    try:
        sirens = siren_cites(conn)
        if len(sirens) < MIN_SIREN_CITES:
            raise RuntimeError(
                f"{len(sirens)} SIREN cités (< {MIN_SIREN_CITES}) : les autres "
                "pipelines n'ont pas encore tourné — ce référentiel est "
                "dérivé, il doit passer en dernier (`make ingest`)"
            )
        log.info("%d SIREN cités par la base", len(sirens))

        if chemin_parquet is None:
            ressource = resoudre_ressource(session=session)
            log.info("ressource : %s (%s, %s o)", ressource["titre"],
                     ressource["derniere_modification"], ressource["octets"])
            chemin_parquet = telecharger(
                ressource["url"], FICHIER_RAW,
                max_age_heures=max_age_heures, session=session,
            )

        lignes, stats = transformer(chemin_parquet, sirens)
        if stats["taux"] < TAUX_APPARIEMENT_MIN:
            raise RuntimeError(
                f"appariement de {stats['taux']:.1%} seulement "
                f"({stats['trouves']}/{stats['siren_cites']} SIREN cités "
                "retrouvés dans le stock) — format amont probablement changé, "
                "base non modifiée"
            )
        if not stats["date_donnees"]:
            raise RuntimeError("aucune date de traitement lisible — base non modifiée")

        nb = charger(conn, lignes)
        log.info(
            "%d unités légales (%.2f %% des SIREN cités) ; %d personnes "
            "physiques sans identité ingérée ; %d unités non diffusibles écartées",
            nb, stats["taux"] * 100, stats["personnes_physiques"],
            stats["ecartes_non_diffusibles"],
        )

        db.upsert_meta(
            conn,
            source_id=SOURCE_ID,
            nom=SOURCE_NOM,
            url=SOURCE_URL,
            licence=SOURCE_LICENCE,
            frequence=SOURCE_FREQUENCE,
            date_donnees=stats["date_donnees"],
            lignes=nb,
            notes=(
                f"référentiel d'attributs restreint aux {stats['siren_cites']} "
                f"SIREN cités par les autres tables, dont {stats['taux']:.1%} "
                f"retrouvés dans un stock de {stats['lignes_parquet']} unités "
                f"légales ; {stats['ecartes_non_diffusibles']} unités non "
                "diffusibles écartées ; aucun nom de personne physique ingéré"
            ),
        )
        return stats
    finally:
        conn.close()


def main() -> int:
    try:
        executer()
    except Exception:
        log.exception("échec de l'ingestion S18 — base laissée intacte")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

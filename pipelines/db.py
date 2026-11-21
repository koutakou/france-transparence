"""Accès à la base servie data/france.db et socle du schéma.

Tables noyau créées ici (idempotent) :
- meta_sources : fraîcheur et traçabilité de chaque source (donnée de
  premier rang, affichée dans l'UI) ;
- entites : référentiel des personnes morales (ministères, institutions,
  collectivités, partis, organismes) ;
- elus : référentiel des personnes physiques élues.

Chaque pipeline crée ses propres tables métier puis appelle `upsert_meta()`.
"""

from __future__ import annotations

import os
import re
import sqlite3
from collections.abc import Iterable, Sequence
from datetime import datetime, timezone
from pathlib import Path

from pipelines.common import DATA_DIR

CHEMIN_DB = DATA_DIR / "france.db"


def _chemin_db() -> Path:
    """Chemin de la base : FT_DB_PATH (env) sinon data/france.db.

    FT_DB_PATH sert aux épreuves des pipelines sur base jetable ; la base
    servie n'est remplie que par `make ingest`.
    """
    env = os.environ.get("FT_DB_PATH")
    return Path(env) if env else CHEMIN_DB

# ---------------------------------------------------------------------------
# Schéma noyau
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta_sources (
    source_id      TEXT PRIMARY KEY,          -- ex. 'S13', 'S1'
    nom            TEXT NOT NULL,             -- libellé humain de la source
    url            TEXT NOT NULL,             -- URL de référence (page ou endpoint)
    licence        TEXT NOT NULL,             -- ex. 'Licence Ouverte 2.0', 'ODbL'
    frequence      TEXT NOT NULL,             -- ex. 'quotidienne', 'mensuelle'
    date_donnees   TEXT NOT NULL,             -- ISO : date de la donnée la plus récente
    date_ingestion TEXT NOT NULL,             -- ISO : dernier passage du pipeline
    lignes         INTEGER NOT NULL DEFAULT 0,
    notes          TEXT
);

CREATE TABLE IF NOT EXISTS entites (
    id          TEXT PRIMARY KEY,
    type        TEXT NOT NULL CHECK (type IN
                  ('ministere','institution','collectivite','parti','organisme')),
    nom         TEXT NOT NULL,
    sigle       TEXT,
    siren       TEXT,
    departement TEXT
);
CREATE INDEX IF NOT EXISTS idx_entites_type  ON entites(type);
CREATE INDEX IF NOT EXISTS idx_entites_siren ON entites(siren);

CREATE TABLE IF NOT EXISTS elus (
    id              TEXT PRIMARY KEY,
    nom             TEXT NOT NULL,
    prenom          TEXT,
    sexe            TEXT,
    date_naissance  TEXT,
    profession      TEXT,
    uid_an          TEXT,                     -- id acteur AN (PAxxxx)
    matricule_senat TEXT,
    hatvp_flag      INTEGER NOT NULL DEFAULT 0,
    mandats         TEXT CHECK (mandats IS NULL OR json_valid(mandats))
);
CREATE INDEX IF NOT EXISTS idx_elus_nom    ON elus(nom, prenom);
CREATE INDEX IF NOT EXISTS idx_elus_uid_an ON elus(uid_an);
"""


def connexion(chemin: str | Path | None = None) -> sqlite3.Connection:
    """Connexion SQLite avec réglages sains (WAL, FK, timeout)."""
    chemin = Path(chemin) if chemin is not None else _chemin_db()
    chemin.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(chemin, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def init_db(conn: sqlite3.Connection | None = None,
            chemin: str | Path | None = None) -> sqlite3.Connection:
    """Crée les tables noyau si absentes. Idempotent, rejouable à volonté.

    Ouvre (et retourne) une connexion sur `chemin` si `conn` n'est pas fournie.
    """
    if conn is None:
        conn = connexion(chemin)
    conn.executescript(_SCHEMA)
    conn.commit()
    return conn


def assurer_date_fait_alertes(conn: sqlite3.Connection) -> None:
    """Pose la colonne `alertes.date_fait` si elle manque. Idempotent.

    `date_calcul` est l'instant du cycle qui a recalculé l'alerte, pas la date
    du fait : avant cette colonne, une décision CNCCFP de 2025 sortait datée du
    jour de l'ingestion. `date_fait` porte la date du fait telle que la source
    la donne, et reste NULL quand la source ne la donne pas (jamais la date du
    cycle à sa place). La table `alertes` est partagée par trois pipelines,
    chacun avec son `CREATE TABLE IF NOT EXISTS` : la colonne se pose ici, à
    l'écriture, par ceux qui la remplissent. Un `ALTER TABLE` est
    transactionnel en SQLite et se greffe sur la transaction de l'appelant.
    """
    colonnes = {r[1] for r in conn.execute("PRAGMA table_info(alertes)")}
    if colonnes and "date_fait" not in colonnes:
        conn.execute("ALTER TABLE alertes ADD COLUMN date_fait TEXT")


def assurer_date_detection_alertes(conn: sqlite3.Connection) -> None:
    """Pose la colonne `alertes.date_detection` si elle manque. Idempotent.

    Migration douce de la table partagée, comme `assurer_date_fait_alertes`.
    Les lignes déjà en base au moment de la migration restent à NULL : le
    premier cycle qui les réécrit via `remplacer_alertes` leur donne sa date.
    """
    colonnes = {r[1] for r in conn.execute("PRAGMA table_info(alertes)")}
    if colonnes and "date_detection" not in colonnes:
        conn.execute("ALTER TABLE alertes ADD COLUMN date_detection TEXT")


_JOUR_ISO = re.compile(r"\d{4}-\d{2}-\d{2}")


def remplacer_alertes(conn: sqlite3.Connection, types: Sequence[str],
                      colonnes: Sequence[str], lignes: Iterable[Sequence],
                      jour_cycle: str) -> int:
    """Remplace les alertes des `types` d'un pipeline par `lignes`, en gardant
    leur date de détection. Seul chemin d'écriture de la table `alertes`.

    `date_detection` est le jour (AAAA-MM-JJ) du premier cycle qui a vu
    l'alerte, par son `id`. Elle est relue AVANT la purge des `types`, puis
    réécrite telle quelle pour chaque `id` encore présent. Une alerte nouvelle
    prend `jour_cycle`. Une alerte qui disparaît d'un cycle puis revient est
    un fait nouveau : sa ligne a été purgée entre-temps, elle prend le jour
    du cycle où elle revient. Une ligne antérieure à la colonne (NULL) prend
    aussi `jour_cycle`.

    Pourquoi : la base persiste d'un cycle à l'autre sur le serveur, alors que
    `date_calcul` change à chaque cycle et que la date d'une source change à
    chaque fichier. Seule cette date ne bouge pas, c'est elle qui date les
    entrées du flux Atom des alertes. Une CI qui part d'une base neuve date
    tout du jour de son cycle, ce qui est juste pour cette base.

    `colonnes` nomme les colonnes des tuples de `lignes` (`id` compris,
    `date_detection` exclue). Ne touche à aucune ligne d'un autre type : la
    table est partagée. Ne valide pas : la transaction reste à l'appelant.
    Retourne le nombre de lignes écrites.
    """
    if not _JOUR_ISO.fullmatch(jour_cycle or ""):
        raise ValueError(f"jour_cycle attendu au format AAAA-MM-JJ : {jour_cycle!r}")
    colonnes = list(colonnes)
    if "id" not in colonnes or "date_detection" in colonnes:
        raise ValueError("colonnes : `id` requise, `date_detection` posée ici")
    types = list(types)
    if not types:
        raise ValueError("types : au moins un type d'alerte")
    assurer_date_fait_alertes(conn)
    assurer_date_detection_alertes(conn)
    marqueurs = ",".join("?" for _ in types)
    deja_vues = {
        r[0]: r[1] for r in conn.execute(
            f"SELECT id, date_detection FROM alertes WHERE type IN ({marqueurs})",
            types)
    }
    conn.execute(f"DELETE FROM alertes WHERE type IN ({marqueurs})", types)
    i_id = colonnes.index("id")
    a_ecrire = [
        (*ligne, deja_vues.get(ligne[i_id]) or jour_cycle) for ligne in lignes
    ]
    noms = ", ".join([*colonnes, "date_detection"])
    conn.executemany(
        f"INSERT INTO alertes ({noms}) VALUES "
        f"({','.join('?' for _ in range(len(colonnes) + 1))})",
        a_ecrire)
    return len(a_ecrire)


def instructions_sql(script: str) -> list[str]:
    """Découpe un script SQL en instructions, à passer UNE À UNE à
    `conn.execute` dans une transaction ouverte.

    POURQUOI pas `executescript` : il VALIDE implicitement la transaction en
    cours avant de lancer son script, et exécute celui-ci hors transaction.
    Un `DROP TABLE` qu'il porte part donc sur disque d'emblée, et aucun
    `rollback()` ne le reprend. Passées une à une, les mêmes instructions
    restent dans la transaction : SQLite fait du DDL transactionnel.

    `sqlite3.complete_statement` (l'outil du shell `sqlite3`) plutôt qu'un
    `split(";")` : il ignore les points-virgules des commentaires `--`.
    Même découpage que `instructions_schema` de P7 et P15, qui gardent leur
    copie documentée.

    Lève `ValueError` sur un script qui se termine hors instruction : mieux
    vaut un échec bruyant avant la première écriture qu'un schéma appliqué à
    moitié.
    """
    instructions: list[str] = []
    tampon = ""
    for ligne in script.splitlines(keepends=True):
        tampon += ligne
        if sqlite3.complete_statement(tampon):
            instructions.append(tampon.strip())
            tampon = ""
    reste = [l for l in tampon.splitlines()
             if l.strip() and not l.strip().startswith("--")]
    if reste:
        raise ValueError(
            "script SQL mal formé : la dernière instruction n'est pas terminée "
            f"par « ; » — {reste[0].strip()[:60]!r}")
    return instructions


def upsert_meta(
    conn: sqlite3.Connection,
    source_id: str,
    nom: str,
    url: str,
    licence: str,
    frequence: str,
    date_donnees: str,
    lignes: int,
    notes: str | None = None,
    date_ingestion: str | None = None,
    commit: bool = True,
) -> None:
    """Insère ou met à jour la ligne de fraîcheur d'une source.

    `date_donnees` : date ISO de la donnée la plus récente réellement ingérée
    (jamais la date de modification du dataset — cf. SOURCES.md §0.2).
    `date_ingestion` : par défaut, maintenant (UTC, ISO, à la seconde).
    `commit` : vrai par défaut (comportement historique des 31 pipelines).
    `commit=False` laisse la ligne dans la transaction de l'appelant, qui la
    valide avec ses tables ou l'annule avec elles — un pipeline qui écrit
    plusieurs lignes meta ne peut pas, sinon, être atomique.
    """
    if date_ingestion is None:
        date_ingestion = datetime.now(timezone.utc).isoformat(timespec="seconds")
    conn.execute(
        """
        INSERT INTO meta_sources
            (source_id, nom, url, licence, frequence,
             date_donnees, date_ingestion, lignes, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_id) DO UPDATE SET
            nom            = excluded.nom,
            url            = excluded.url,
            licence        = excluded.licence,
            frequence      = excluded.frequence,
            date_donnees   = excluded.date_donnees,
            date_ingestion = excluded.date_ingestion,
            lignes         = excluded.lignes,
            notes          = excluded.notes
        """,
        (source_id, nom, url, licence, frequence,
         date_donnees, date_ingestion, lignes, notes),
    )
    if commit:
        conn.commit()


def publication_precedente(
    conn: sqlite3.Connection, table: str, source_id: str
) -> tuple[int, str] | None:
    """(lignes de `table`, date_donnees de `source_id`) laissées par le
    dernier cycle réussi, ou None s'il n'y a rien à reprendre.

    Sert au secours « serveur amont injoignable » : le pipeline n'écrit
    RIEN, ni sa table ni sa ligne meta_sources. La table reste celle du
    cycle précédent, et la ligne meta garde la date de la donnée la plus
    récente réellement ingérée et la date de cette ingestion : la fraîcheur
    affichée reste vraie, et le seuil de fraîcheur finit par alerter si la
    panne dure. Sans table remplie ET datée (base neuve), il n'y a rien
    d'honnête à servir : le pipeline doit échouer.
    """
    presentes = {
        r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
            " AND name IN (?, 'meta_sources')", (table,),
        )
    }
    if presentes != {table, "meta_sources"}:
        return None
    # `table` est un nom de table EXISTANT (vérifié ci-dessus), pas une
    # chaîne arbitraire : l'interpolation ne peut rien injecter.
    lignes = conn.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]
    meta = conn.execute(
        "SELECT date_donnees FROM meta_sources WHERE source_id = ?",
        (source_id,),
    ).fetchone()
    if not lignes or meta is None or not meta[0]:
        return None
    return lignes, meta[0]

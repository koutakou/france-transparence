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
import sqlite3
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
) -> None:
    """Insère ou met à jour la ligne de fraîcheur d'une source.

    `date_donnees` : date ISO de la donnée la plus récente réellement ingérée
    (jamais la date de modification du dataset — cf. SOURCES.md §0.2).
    `date_ingestion` : par défaut, maintenant (UTC, ISO, à la seconde).
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

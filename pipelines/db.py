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
    servie n'est remplie que par l'orchestrateur (`make ingest`).
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

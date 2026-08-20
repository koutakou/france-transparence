"""Tests du socle : init_db (idempotence, contraintes) et upsert_meta."""

import sqlite3

import pytest

from pipelines import db


@pytest.fixture()
def conn(tmp_path):
    """Base temporaire initialisée, fermée en fin de test."""
    c = db.init_db(chemin=tmp_path / "test.db")
    yield c
    c.close()


def test_init_db_cree_les_tables_noyau(conn):
    tables = {
        r["name"]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    assert {"meta_sources", "entites", "elus"} <= tables


def test_init_db_est_idempotent(tmp_path):
    chemin = tmp_path / "test.db"
    c1 = db.init_db(chemin=chemin)
    c1.execute(
        "INSERT INTO entites (id, type, nom) VALUES ('MIN-ECO', 'ministere', 'Ministère de l''Économie')"
    )
    c1.commit()
    c1.close()
    # Second passage sur la même base : ne détruit rien, ne lève rien.
    c2 = db.init_db(chemin=chemin)
    n = c2.execute("SELECT count(*) AS n FROM entites").fetchone()["n"]
    assert n == 1
    c2.close()


def test_entites_type_contraint(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO entites (id, type, nom) VALUES ('X', 'licorne', 'Type hors référentiel')"
        )


def test_elus_mandats_doit_etre_json_valide(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO elus (id, nom, mandats) VALUES ('E1', 'Nom', 'pas du json')"
        )
    conn.execute(
        'INSERT INTO elus (id, nom, mandats) VALUES (\'E2\', \'Nom\', \'[{"mandat": "maire"}]\')'
    )
    conn.commit()


def test_upsert_meta_insere_puis_met_a_jour(conn):
    db.upsert_meta(
        conn,
        source_id="S13",
        nom="Situations mensuelles budgétaires (DGFiP)",
        url="https://data.economie.gouv.fr/explore/dataset/situations-mensuelles-budgetaires-series-longues/",
        licence="Licence Ouverte 2.0",
        frequence="mensuelle",
        date_donnees="2026-06-30",
        lignes=26,
        notes="export CSV complet",
    )
    ligne = conn.execute(
        "SELECT * FROM meta_sources WHERE source_id = 'S13'"
    ).fetchone()
    assert ligne["lignes"] == 26
    assert ligne["date_donnees"] == "2026-06-30"
    assert ligne["date_ingestion"]  # auto-rempli, ISO

    # Upsert : même source_id → mise à jour, pas de doublon.
    db.upsert_meta(
        conn,
        source_id="S13",
        nom="Situations mensuelles budgétaires (DGFiP)",
        url="https://data.economie.gouv.fr/explore/dataset/situations-mensuelles-budgetaires-series-longues/",
        licence="Licence Ouverte 2.0",
        frequence="mensuelle",
        date_donnees="2026-07-31",
        lignes=26,
        date_ingestion="2026-08-19T06:00:00+00:00",
    )
    lignes = conn.execute("SELECT * FROM meta_sources").fetchall()
    assert len(lignes) == 1
    assert lignes[0]["date_donnees"] == "2026-07-31"
    assert lignes[0]["date_ingestion"] == "2026-08-19T06:00:00+00:00"
    assert lignes[0]["notes"] is None  # écrasé par l'upsert (None transmis)

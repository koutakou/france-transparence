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


# ---------------------------------------------------------------------------
# telecharger_ressource : le cache tombe quand la ressource amont a changé
# ---------------------------------------------------------------------------


def _cache_vieux_d_une_heure(chemin, contenu=b"ancien"):
    import os
    import time
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_bytes(contenu)
    il_y_a_une_heure = time.time() - 3600
    os.utime(chemin, (il_y_a_une_heure, il_y_a_une_heure))


def _iso(decalage_heures: float) -> str:
    from datetime import datetime, timedelta, timezone
    return (datetime.now(timezone.utc) + timedelta(hours=decalage_heures)).isoformat()


@pytest.mark.parametrize(
    "modifiee_le, telecharge",
    [
        (_iso(-2), False),   # ressource antérieure à la copie : cache servi
        (_iso(0), True),     # ressource modifiée APRÈS la copie : re-téléchargée
        ("", True),          # date inconnue : rien ne prouve que le cache est à jour
        ("pas une date", True),
    ],
)
def test_telecharger_ressource_invalide_le_cache_perime(tmp_path, modifiee_le, telecharge):
    from pipelines.common import telecharger_ressource
    from pipelines.tests.session_factice import SessionFactice

    dest = tmp_path / "x" / "courant.zip"
    _cache_vieux_d_une_heure(dest)
    session = SessionFactice({"https://exemple.invalid/nouveau.zip": b"nouveau"})
    chemin = telecharger_ressource(
        "https://exemple.invalid/nouveau.zip", dest, modifiee_le,
        max_age_heures=7 * 24, session=session,
    )
    assert chemin == dest
    assert (session.appels != []) is telecharge
    assert dest.read_bytes() == (b"nouveau" if telecharge else b"ancien")


def test_telecharger_ressource_sans_cache_telecharge(tmp_path):
    from pipelines.common import telecharger_ressource
    from pipelines.tests.session_factice import SessionFactice

    session = SessionFactice({"https://exemple.invalid/a.csv": b"a"})
    dest = tmp_path / "a.csv"
    telecharger_ressource("https://exemple.invalid/a.csv", dest, _iso(-48),
                          max_age_heures=24, session=session)
    assert session.appels == ["https://exemple.invalid/a.csv"] and dest.read_bytes() == b"a"


def test_publication_precedente_exige_une_table_remplie_et_datee(conn):
    """Le secours « amont injoignable » ne reprend que ce qu'un cycle réussi
    a laissé : table présente ET non vide ET ligne meta datée."""
    assert db.publication_precedente(conn, "jorf_textes", "S3") is None
    conn.execute("CREATE TABLE jorf_textes (texte_id TEXT)")
    assert db.publication_precedente(conn, "jorf_textes", "S3") is None
    db.upsert_meta(conn, "S3", "DILA", "https://echanges.dila.gouv.fr/",
                   "fr-lo", "quotidienne", date_donnees="2026-10-03", lignes=0)
    # Table vide sous une ligne meta : rien d'honnête à servir.
    assert db.publication_precedente(conn, "jorf_textes", "S3") is None
    conn.execute("INSERT INTO jorf_textes VALUES ('JORFTEXT000054708438')")
    assert db.publication_precedente(conn, "jorf_textes", "S3") == (1, "2026-10-03")
    # Table remplie sans ligne meta pour CETTE source : rien non plus.
    assert db.publication_precedente(conn, "jorf_textes", "S43") is None

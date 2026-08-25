"""Archive des lignes qui sortent d'une fenêtre glissante.

Pas de zip amont. Fixtures SQLite jetables. Les tables d'archive sont
nouvelles : on n'ALTER pas `votes_recents`.
"""

from __future__ import annotations

from datetime import date

import pytest

from pipelines import db
from pipelines.archive_fenetre import archiver_sortie_fenetre
from pipelines.ingest_boamp import SCHEMA as SCHEMA_BOAMP
from pipelines.ingest_boamp import archiver_annonces_hors_fenetre
from pipelines.ingest_jorf import _SCHEMA as SCHEMA_JORF
from pipelines.ingest_jorf import archiver_et_purger_jorf
from pipelines.ingest_parlement import (
    _SCHEMA_P9,
    archiver_votes_recents_sous_seuil,
    archiver_votes_senat_hors_cles,
    ingerer_dosleg,
)
from pipelines.tests.test_parlement import _zip_dosleg


def test_helper_copie_seulement_ce_qui_sort(tmp_path):
    conn = db.init_db(chemin=tmp_path / "t.db")
    conn.executescript(
        """
        CREATE TABLE src (id TEXT PRIMARY KEY, n INTEGER);
        CREATE TABLE src_archive (id TEXT PRIMARY KEY, n INTEGER, archive_le TEXT NOT NULL);
        """
    )
    conn.executemany("INSERT INTO src VALUES (?, ?)", [("a", 1), ("b", 2), ("c", 3)])
    n = archiver_sortie_fenetre(
        conn,
        source="src",
        archive="src_archive",
        colonnes=("id", "n"),
        where="n < ?",
        params=(3,),
        archive_le="2026-08-25",
    )
    assert n == 2
    restant = {r["id"] for r in conn.execute("SELECT id FROM src")}
    assert restant == {"a", "b", "c"}  # le helper ne DELETE pas
    arch = {r["id"]: r["archive_le"] for r in conn.execute("SELECT * FROM src_archive")}
    assert arch == {"a": "2026-08-25", "b": "2026-08-25"}


def test_helper_ignore_la_cle_deja_archivee(tmp_path):
    conn = db.init_db(chemin=tmp_path / "t.db")
    conn.executescript(
        """
        CREATE TABLE src (id TEXT PRIMARY KEY, n INTEGER);
        CREATE TABLE src_archive (id TEXT PRIMARY KEY, n INTEGER, archive_le TEXT NOT NULL);
        """
    )
    conn.execute("INSERT INTO src VALUES ('a', 1)")
    conn.execute(
        "INSERT INTO src_archive VALUES ('a', 1, '2026-08-01')"
    )
    n = archiver_sortie_fenetre(
        conn,
        source="src",
        archive="src_archive",
        colonnes=("id", "n"),
        where="n < ?",
        params=(9,),
        archive_le="2026-08-25",
    )
    assert n == 0
    assert conn.execute("SELECT archive_le FROM src_archive").fetchone()[0] == "2026-08-01"


def test_helper_refuse_un_identifiant_injecte(tmp_path):
    conn = db.init_db(chemin=tmp_path / "t.db")
    with pytest.raises(ValueError, match="identifiant"):
        archiver_sortie_fenetre(
            conn,
            source="src; DROP TABLE src",
            archive="src_archive",
            colonnes=("id",),
            where="1=1",
            archive_le="2026-08-25",
        )


def test_votes_recents_archive_avant_purge(tmp_path):
    conn = db.init_db(chemin=tmp_path / "t.db")
    conn.executescript(_SCHEMA_P9)
    conn.executemany(
        """INSERT INTO votes_recents
             (scrutin_uid, scrutin_numero, uid_an, position, par_delegation)
           VALUES (?, ?, ?, ?, 0)""",
        [
            ("VT1", 1, "PA1", "pour"),
            ("VT2", 2, "PA1", "contre"),
            ("VT100", 100, "PA1", "pour"),
        ],
    )
    n = archiver_votes_recents_sous_seuil(conn, 2, "2026-08-25")
    assert n == 1
    conn.execute("DELETE FROM votes_recents WHERE scrutin_numero < ?", (2,))
    assert conn.execute("SELECT count(*) FROM votes_recents").fetchone()[0] == 2
    row = conn.execute("SELECT * FROM votes_recents_archive").fetchone()
    assert tuple(row)[:4] == ("VT1", 1, "PA1", "pour")
    assert row["archive_le"] == "2026-08-25"


def test_ingerer_dosleg_archive_les_votes_hors_100(tmp_path, monkeypatch):
    """Un scrutin déjà en table, absent du dump, sort vers l'archive."""
    conn = db.init_db(chemin=tmp_path / "t.db")
    conn.executescript(_SCHEMA_P9)
    conn.executemany(
        """INSERT INTO senateurs (matricule, nom, date_debut_mandat)
           VALUES (?, ?, ?)""",
        [
            ("21071F", "Aeschlimann", "2020-10-01"),
            ("19489J", "Kerrouche", "2020-10-01"),
            ("01008M", "Del", "2020-10-01"),
            ("98046X", "Nonvotant", "2020-10-01"),
            ("99999Z", "Absent", "2020-10-01"),
            ("88888Y", "Nouveau", "2026-08-01"),
        ],
    )
    conn.execute(
        """INSERT INTO votes_senat
             (sesann, numero, matricule, position, par_delegation)
           VALUES (2023, 99, '21071F', 'pour', 0)"""
    )
    conn.commit()
    zip_path = _zip_dosleg(tmp_path)
    monkeypatch.setattr(
        "pipelines.ingest_parlement.telecharger", lambda *a, **k: zip_path
    )
    ingerer_dosleg(conn, session=None)

    assert conn.execute(
        "SELECT count(*) FROM votes_senat WHERE sesann = 2023"
    ).fetchone()[0] == 0
    arch = conn.execute(
        "SELECT sesann, numero, matricule, archive_le FROM votes_senat_archive"
    ).fetchone()
    assert tuple(arch) == (2023, 99, "21071F", date.today().isoformat())
    assert conn.execute("SELECT count(*) FROM votes_senat").fetchone()[0] == 12


def test_archiver_votes_senat_hors_cles_garde_la_fenetre(tmp_path):
    conn = db.init_db(chemin=tmp_path / "t.db")
    conn.executescript(_SCHEMA_P9)
    conn.executemany(
        """INSERT INTO votes_senat
             (sesann, numero, matricule, position, par_delegation)
           VALUES (?, ?, ?, 'pour', 0)""",
        [(2025, 1, "A"), (2025, 2, "A"), (2025, 2, "B")],
    )
    n = archiver_votes_senat_hors_cles(conn, {(2025, 2)}, "2026-08-25")
    assert n == 1
    assert conn.execute("SELECT count(*) FROM votes_senat").fetchone()[0] == 3
    assert conn.execute(
        "SELECT numero FROM votes_senat_archive"
    ).fetchone()[0] == 1


def test_jorf_archive_avant_purge(tmp_path):
    conn = db.init_db(chemin=tmp_path / "t.db")
    conn.executescript(SCHEMA_JORF)
    conn.execute(
        """INSERT INTO jorf_textes
             (texte_id, date_publi, titre, is_nomination, lien_legifrance)
           VALUES ('JORFTEXT_OLD', '2026-06-01', 'vieux', 0, 'https://x'),
                  ('JORFTEXT_NEW', '2026-08-25', 'récent', 0, 'https://x')"""
    )
    n = archiver_et_purger_jorf(conn, "2026-07-21", "2026-08-25")
    assert n == 1
    ids = {r[0] for r in conn.execute("SELECT texte_id FROM jorf_textes")}
    assert ids == {"JORFTEXT_NEW"}
    arch = conn.execute("SELECT texte_id, archive_le FROM jorf_textes_archive").fetchone()
    assert tuple(arch) == ("JORFTEXT_OLD", "2026-08-25")


def test_annonces_archive_hors_30j_sans_toucher_la_fenetre(tmp_path):
    conn = db.init_db(chemin=tmp_path / "t.db")
    conn.executescript(SCHEMA_BOAMP)
    conn.executemany(
        """INSERT INTO annonces_recentes (idweb, date_parution)
           VALUES (?, ?)""",
        [("old", "2026-07-01"), ("in", "2026-08-01")],
    )
    n = archiver_annonces_hors_fenetre(conn, "2026-07-26", "2026-08-25")
    assert n == 1
    ids = {r[0] for r in conn.execute("SELECT idweb FROM annonces_recentes")}
    assert ids == {"old", "in"}
    assert conn.execute(
        "SELECT idweb FROM annonces_recentes_archive"
    ).fetchone()[0] == "old"

"""Tests de db.remplacer_alertes : date de détection stable d'un cycle à l'autre.

La base persiste sur le serveur (ft-deploy ingère dans la base du cycle
précédent), une CI peut partir d'une base neuve. `date_detection` est la seule
date d'une alerte qui ne bouge pas : elle date les entrées du flux Atom.
"""

from __future__ import annotations

import sqlite3

import pytest

from pipelines import db

COLONNES = ("id", "type", "gravite", "titre", "date_calcul")


@pytest.fixture()
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    # Schéma ancien, sans date_fait ni date_detection : la migration est douce.
    c.execute("CREATE TABLE alertes (id TEXT PRIMARY KEY, type TEXT NOT NULL,"
              " gravite TEXT NOT NULL, titre TEXT NOT NULL, detail TEXT,"
              " regle TEXT, base_legale TEXT, source_url TEXT,"
              " date_calcul TEXT NOT NULL)")
    yield c
    c.close()


def _ligne(id_, type_="t_a", jour="2026-11-01"):
    return (id_, type_, "info", f"titre {id_}", f"{jour}T04:00:00+00:00")


def _dates(conn):
    return {r["id"]: r["date_detection"]
            for r in conn.execute("SELECT id, date_detection FROM alertes")}


def test_premier_cycle_date_du_jour_puis_gardee(conn):
    n = db.remplacer_alertes(conn, ["t_a"], COLONNES,
                             [_ligne("A"), _ligne("B")], "2026-11-01")
    assert n == 2
    assert _dates(conn) == {"A": "2026-11-01", "B": "2026-11-01"}
    # Cycle suivant : A et B gardent leur date, C est nouvelle.
    db.remplacer_alertes(conn, ["t_a"], COLONNES,
                         [_ligne("A", jour="2026-11-02"), _ligne("B", jour="2026-11-02"),
                          _ligne("C", jour="2026-11-02")], "2026-11-02")
    assert _dates(conn) == {"A": "2026-11-01", "B": "2026-11-01", "C": "2026-11-02"}
    # date_calcul, elle, suit le cycle : seule date_detection est stable.
    assert conn.execute("SELECT date_calcul FROM alertes WHERE id = 'A'"
                        ).fetchone()[0].startswith("2026-11-02")


def test_alerte_disparue_puis_revenue_prend_une_date_neuve(conn):
    db.remplacer_alertes(conn, ["t_a"], COLONNES, [_ligne("A")], "2026-11-01")
    db.remplacer_alertes(conn, ["t_a"], COLONNES, [], "2026-11-02")
    assert _dates(conn) == {}
    db.remplacer_alertes(conn, ["t_a"], COLONNES, [_ligne("A")], "2026-11-03")
    assert _dates(conn) == {"A": "2026-11-03"}


def test_ne_touche_pas_les_autres_types(conn):
    db.remplacer_alertes(conn, ["t_b"], COLONNES, [_ligne("X", "t_b")], "2026-10-01")
    db.remplacer_alertes(conn, ["t_a"], COLONNES, [_ligne("A")], "2026-11-01")
    db.remplacer_alertes(conn, ["t_a"], COLONNES, [], "2026-11-02")
    assert _dates(conn) == {"X": "2026-10-01"}


def test_migration_douce_et_lignes_anterieures(conn):
    conn.execute("INSERT INTO alertes (id, type, gravite, titre, date_calcul)"
                 " VALUES ('A', 't_a', 'info', 'ancien', '2026-10-30')")
    db.remplacer_alertes(conn, ["t_a"], COLONNES, [_ligne("A")], "2026-11-01")
    colonnes = {r[1] for r in conn.execute("PRAGMA table_info(alertes)")}
    assert {"date_fait", "date_detection"} <= colonnes
    # Ligne d'avant la colonne (NULL) : prend le jour du premier cycle qui la voit.
    assert _dates(conn) == {"A": "2026-11-01"}
    # Rejouable : la colonne n'est pas posée deux fois.
    db.remplacer_alertes(conn, ["t_a"], COLONNES, [_ligne("A")], "2026-11-02")
    assert _dates(conn) == {"A": "2026-11-01"}


def test_colonnes_nommees_quelle_que_soit_leur_position(conn):
    db.remplacer_alertes(conn, ["t_a"], ("titre", "id", "type", "gravite", "date_calcul"),
                         [("t", "A", "t_a", "info", "2026-11-01")], "2026-11-01")
    ligne = conn.execute("SELECT * FROM alertes").fetchone()
    assert (ligne["id"], ligne["titre"], ligne["date_detection"]) == ("A", "t", "2026-11-01")


@pytest.mark.parametrize("jour", ["", "2026-11-01T04:00:00", "01/11/2026", None])
def test_jour_du_cycle_au_format_iso(conn, jour):
    with pytest.raises(ValueError):
        db.remplacer_alertes(conn, ["t_a"], COLONNES, [_ligne("A")], jour)


def test_colonnes_invalides(conn):
    with pytest.raises(ValueError):
        db.remplacer_alertes(conn, ["t_a"], ("type", "titre"), [], "2026-11-01")
    with pytest.raises(ValueError):
        db.remplacer_alertes(conn, ["t_a"], (*COLONNES, "date_detection"), [], "2026-11-01")
    with pytest.raises(ValueError):
        db.remplacer_alertes(conn, [], COLONNES, [], "2026-11-01")

"""Tests du pipeline P18 — déficit public des APU au sens de Maastricht (S42).

Les fixtures `eurostat_gov_10dd_edpt1_*_mini.json` sont des JSON-stat
MINIMAUX INVENTÉS (−1000/−1100 MIO_EUR, −4,0/−4,5 % PIB). Elles ne
reprennent aucune valeur live d'Eurostat : les garde-fous d'ampleur
(`controler_ampleur`) se testent à part, sur des ordres de grandeur,
jamais sur un déficit du jour.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from pipelines import db
from pipelines.ingest_deficit_maastricht import (
    SOURCE_ID,
    assembler,
    controler_ampleur,
    date_fin_annee,
    ecrire_db,
    extraire,
    mio_en_md,
)

FIXTURE_MIO = (
    Path(__file__).parent / "fixtures" / "eurostat_gov_10dd_edpt1_mio_mini.json"
)
FIXTURE_PC = (
    Path(__file__).parent / "fixtures" / "eurostat_gov_10dd_edpt1_pc_mini.json"
)


def _payload_mio() -> dict:
    return json.loads(FIXTURE_MIO.read_text(encoding="utf-8"))


def _payload_pc() -> dict:
    return json.loads(FIXTURE_PC.read_text(encoding="utf-8"))


def _muter_dimension(payload: dict, nom: str, code: str) -> dict:
    payload["dimension"][nom]["category"]["index"] = {code: 0}
    payload["dimension"][nom]["category"]["label"] = {code: code}
    return payload


@pytest.fixture()
def obs_mio():
    return extraire(_payload_mio(), "MIO_EUR")


@pytest.fixture()
def obs_pc():
    return extraire(_payload_pc(), "PC_GDP")


@pytest.fixture()
def observations(obs_mio, obs_pc):
    return assembler(obs_mio, obs_pc)


@pytest.fixture()
def conn(tmp_path, observations):
    c = db.init_db(chemin=tmp_path / "deficit.db")
    ecrire_db(c, observations)
    yield c
    c.close()


# ---------------------------------------------------------------------------
# Conversion et calendrier — invariants, pas une valeur live
# ---------------------------------------------------------------------------


def test_md_egal_mio_divise_par_mille():
    for mio in (-1000.0, -1100.0, 1.0, -152511.0):
        md = mio_en_md(mio)
        assert md == mio / 1000.0
        assert md * 1000.0 == mio


def test_date_fin_annee():
    assert date_fin_annee(2025) == "2025-12-31"
    assert date_fin_annee(1995) == "1995-12-31"


def test_date_fin_annee_refuse_hors_plage():
    with pytest.raises(ValueError):
        date_fin_annee(999)
    with pytest.raises(ValueError):
        date_fin_annee(2025.0)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# JSON-stat : dimensions exactes, jointure, date ≠ updated
# ---------------------------------------------------------------------------


def test_extraire_la_fixture_inventee(obs_mio, obs_pc):
    assert [(o["annee"], o["valeur_mio_eur"], o["statut"]) for o in obs_mio] == [
        (2024, -1000.0, None),
        (2025, -1100.0, "p"),
    ]
    assert [(o["annee"], o["valeur_pc_gdp"], o["statut"]) for o in obs_pc] == [
        (2024, -4.0, None),
        (2025, -4.5, "p"),
    ]
    for o in obs_mio + obs_pc:
        assert o["geo"] == "FR"
        assert o["sector"] == "S13"
        assert o["na_item"] == "B9"


def test_assembler_joint_sur_annee(observations):
    assert [(o["annee"], o["valeur_mio_eur"], o["valeur_pc_gdp"], o["statut"]) for o in observations] == [
        (2024, -1000.0, -4.0, None),
        (2025, -1100.0, -4.5, "p"),
    ]


def test_date_donnees_vient_du_time_max_pas_de_updated(observations):
    payload = _payload_mio()
    assert payload["updated"].startswith("2026-01-01")
    time_max = max(o["annee"] for o in observations)
    assert date_fin_annee(time_max) == "2025-12-31"
    assert str(time_max) != payload["updated"][:4]


@pytest.mark.parametrize(
    "nom, code",
    [
        ("na_item", "GD"),
        ("sector", "S1311"),
        ("geo", "DE"),
        ("unit", "PC_GDP"),
        ("freq", "Q"),
    ],
)
def test_refuse_une_dimension_hors_extrait_mio(nom, code):
    with pytest.raises(ValueError, match=nom):
        extraire(_muter_dimension(_payload_mio(), nom, code), "MIO_EUR")


def test_assembler_refuse_si_time_max_sans_pc(obs_mio, obs_pc):
    obs_pc_tronque = [o for o in obs_pc if o["annee"] != 2025]
    with pytest.raises(ValueError, match="TIME max"):
        assembler(obs_mio, obs_pc_tronque)


def test_controler_ampleur_refuse_la_fixture_minimale(observations):
    """La fixture a 2 points à ~1e3 MIO_EUR : hors bornes d'une série réelle."""
    with pytest.raises(ValueError):
        controler_ampleur(observations)


def test_controler_ampleur_accepte_un_ordre_de_grandeur_d_unite():
    serie = [
        {
            "annee": 1995 + i,
            "valeur_mio_eur": -8e4 - i,
            "valeur_pc_gdp": -3.0 - (i % 5) * 0.1,
            "statut": None,
        }
        for i in range(30)
    ]
    serie[-1]["statut"] = "p"
    controler_ampleur(serie)


# ---------------------------------------------------------------------------
# Écriture : idempotence, CHECK SQL, meta, cloisonnement
# ---------------------------------------------------------------------------


def test_ecrire_db_idempotent(conn, observations):
    n1 = conn.execute("SELECT count(*) AS n FROM deficit_apu_maastricht").fetchone()["n"]
    ecrire_db(conn, observations)
    ecrire_db(conn, observations)
    n2 = conn.execute("SELECT count(*) AS n FROM deficit_apu_maastricht").fetchone()["n"]
    assert n1 == n2 == 2


def test_check_sql_refuse_un_encours_gd(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO deficit_apu_maastricht "
            "(geo, sector, na_item, annee, valeur_mio_eur, valeur_pc_gdp, statut) "
            "VALUES ('FR', 'S13', 'GD', 2024, -1000.0, -4.0, NULL)"
        )


def test_meta_s42_licence_et_frequence(conn):
    ligne = conn.execute(
        "SELECT * FROM meta_sources WHERE source_id = ?", (SOURCE_ID,)
    ).fetchone()
    assert ligne is not None
    assert ligne["source_id"] == "S42"
    assert "2011/833" in ligne["licence"]
    assert "CC BY" not in ligne["licence"]
    assert ligne["frequence"] == "annuelle"
    assert ligne["date_donnees"] == "2025-12-31"
    assert ligne["lignes"] == 2
    assert ligne["url"] == "https://doi.org/10.2908/GOV_10DD_EDPT1"
    assert "S41" not in ligne["notes"] or "stock GD" in ligne["notes"]


def test_aucune_colonne_population_par_habitant_ni_seuil_trois(conn):
    colonnes = {
        r["name"].lower()
        for r in conn.execute("PRAGMA table_info(deficit_apu_maastricht)")
    }
    for interdite in ("population", "par_habitant", "habitants", "seuil_3", "trois_pct"):
        assert interdite not in colonnes
    notes = conn.execute(
        "SELECT notes FROM meta_sources WHERE source_id = ?", (SOURCE_ID,)
    ).fetchone()["notes"]
    assert "3 %" in notes  # la mention d'exclusion
    assert "seuil de 3" in notes


def test_n_ecrit_que_deficit_apu_maastricht_et_meta_sources(conn):
    tables = {
        r["name"]
        for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    noyau = {"meta_sources", "entites", "elus"}
    assert noyau <= tables
    metier = tables - noyau - {"sqlite_sequence"}
    assert metier == {"deficit_apu_maastricht"}
    assert "dette_apu_maastricht" not in tables
    assert not any(t.startswith("budget_") for t in metier)

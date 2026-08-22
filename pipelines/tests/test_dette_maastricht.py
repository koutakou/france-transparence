"""Tests du pipeline P17 — encours de dette des APU au sens de Maastricht (S41).

La fixture `eurostat_gov_10q_ggdebt_mini.json` est un JSON-stat MINIMAL
INVENTÉ (1000,0 et 1100,0 MIO_EUR). Elle ne reprend aucune valeur live
d'Eurostat : les garde-fous d'ampleur (`controler_ampleur`) se testent à
part, sur des ordres de grandeur, jamais sur un encours du jour.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from pipelines import db
from pipelines.ingest_dette_maastricht import (
    SOURCE_ID,
    controler_ampleur,
    date_fin_trimestre,
    ecrire_db,
    extraire,
    mio_en_md,
)

FIXTURE = (
    Path(__file__).parent / "fixtures" / "eurostat_gov_10q_ggdebt_mini.json"
)


def _payload() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _muter_dimension(nom: str, code: str) -> dict:
    payload = _payload()
    payload["dimension"][nom]["category"]["index"] = {code: 0}
    payload["dimension"][nom]["category"]["label"] = {code: code}
    return payload


@pytest.fixture()
def observations():
    return extraire(_payload())


@pytest.fixture()
def conn(tmp_path, observations):
    c = db.init_db(chemin=tmp_path / "dette.db")
    ecrire_db(c, observations)
    yield c
    c.close()


# ---------------------------------------------------------------------------
# Conversion et calendrier — invariants, pas une valeur live
# ---------------------------------------------------------------------------


def test_md_egal_mio_divise_par_mille():
    for mio in (1000.0, 1100.0, 1.0, 2500.5):
        md = mio_en_md(mio)
        assert md == mio / 1000.0
        assert md * 1000.0 == mio


def test_date_fin_trimestre():
    assert date_fin_trimestre("2026-Q1") == "2026-03-31"
    assert date_fin_trimestre("2026-Q2") == "2026-06-30"
    assert date_fin_trimestre("2026-Q3") == "2026-09-30"
    assert date_fin_trimestre("2026-Q4") == "2026-12-31"


def test_date_fin_trimestre_refuse_un_motif_hors_qn():
    with pytest.raises(ValueError):
        date_fin_trimestre("2026-Q5")
    with pytest.raises(ValueError):
        date_fin_trimestre("2026")


# ---------------------------------------------------------------------------
# JSON-stat : dimensions exactes, trous sautés, date ≠ updated
# ---------------------------------------------------------------------------


def test_extraire_la_fixture_inventee(observations):
    assert [(o["trimestre"], o["valeur_mio_eur"], o["statut"]) for o in observations] == [
        ("2025-Q4", 1000.0, None),
        ("2026-Q1", 1100.0, "p"),
    ]
    for o in observations:
        assert o["geo"] == "FR"
        assert o["sector"] == "S13"
        assert o["na_item"] == "GD"
        assert o["unit"] == "MIO_EUR"


def test_date_donnees_vient_du_time_max_pas_de_updated(observations):
    payload = _payload()
    assert payload["updated"].startswith("2026-01-01")
    time_max = max(o["trimestre"] for o in observations)
    assert date_fin_trimestre(time_max) == "2026-03-31"
    assert time_max != payload["updated"][:10]


@pytest.mark.parametrize(
    "nom, code",
    [
        ("na_item", "B9"),
        ("sector", "S1311"),
        ("geo", "DE"),
        ("unit", "PC_GDP"),
    ],
)
def test_refuse_une_dimension_hors_extrait(nom, code):
    with pytest.raises(ValueError, match=nom):
        extraire(_muter_dimension(nom, code))


def test_controler_ampleur_refuse_la_fixture_minimale(observations):
    """La fixture a 2 points à ~1e3 MIO_EUR : hors bornes d'une série réelle."""
    with pytest.raises(ValueError):
        controler_ampleur(observations)


def test_controler_ampleur_accepte_un_ordre_de_grandeur_d_unite():
    serie = [
        {
            "trimestre": f"2000-Q{((i % 4) + 1)}",
            "valeur_mio_eur": 2e6 + i,
            "statut": None,
        }
        for i in range(80)
    ]
    serie[-1]["trimestre"] = "2020-Q4"
    serie[-1]["statut"] = "p"
    controler_ampleur(serie)


# ---------------------------------------------------------------------------
# Écriture : idempotence, CHECK SQL, meta, cloisonnement
# ---------------------------------------------------------------------------


def test_ecrire_db_idempotent(conn, observations):
    n1 = conn.execute("SELECT count(*) AS n FROM dette_apu_maastricht").fetchone()["n"]
    ecrire_db(conn, observations)
    ecrire_db(conn, observations)
    n2 = conn.execute("SELECT count(*) AS n FROM dette_apu_maastricht").fetchone()["n"]
    assert n1 == n2 == 2


def test_check_sql_refuse_un_deficit_b9(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO dette_apu_maastricht "
            "(geo, sector, na_item, unit, trimestre, valeur_mio_eur, statut) "
            "VALUES ('FR', 'S13', 'B9', 'MIO_EUR', '2024-Q1', 1000.0, NULL)"
        )


def test_meta_s41_licence_et_frequence(conn):
    ligne = conn.execute(
        "SELECT * FROM meta_sources WHERE source_id = ?", (SOURCE_ID,)
    ).fetchone()
    assert ligne is not None
    assert ligne["source_id"] == "S41"
    assert "2011/833" in ligne["licence"]
    assert "CC BY" not in ligne["licence"]
    assert ligne["frequence"] == "trimestrielle"
    assert ligne["date_donnees"] == "2026-03-31"
    assert ligne["lignes"] == 2
    assert ligne["url"] == "https://doi.org/10.2908/GOV_10Q_GGDEBT"


def test_aucune_colonne_population_pib_par_habitant(conn):
    colonnes = {
        r["name"].lower()
        for r in conn.execute("PRAGMA table_info(dette_apu_maastricht)")
    }
    for interdite in ("population", "pib", "par_habitant", "pc_gdp", "habitants"):
        assert interdite not in colonnes


def test_n_ecrit_que_dette_apu_maastricht_et_meta_sources(conn):
    tables = {
        r["name"]
        for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    noyau = {"meta_sources", "entites", "elus"}
    assert noyau <= tables
    metier = tables - noyau - {"sqlite_sequence"}
    assert metier == {"dette_apu_maastricht"}
    assert not any(t.startswith("budget_") for t in metier)

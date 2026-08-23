"""Tests du pipeline P20 — recettes et dépenses des APU (S44, gov_10a_main).

Les fixtures `eurostat_gov_10a_main_*_mini.json` sont des JSON-stat
MINIMAUX INVENTÉS (TE 1000/1100, TR 900/950 MIO_EUR). Elles ne
reprennent aucune valeur live d'Eurostat : les garde-fous d'ampleur
(`controler_ampleur`) se testent à part, sur des ordres de grandeur,
jamais sur un total du jour.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from pipelines import db
from pipelines.ingest_agregats_apu import (
    SOURCE_ID,
    assembler,
    controler_ampleur,
    date_fin_annee,
    ecrire_db,
    extraire,
    fusionner,
    mio_en_md,
    url_api,
)

FIX = Path(__file__).parent / "fixtures"


def _payload(na_item: str, unit: str) -> dict:
    nom = f"eurostat_gov_10a_main_{na_item.lower()}_{'mio' if unit == 'MIO_EUR' else 'pc'}_mini.json"
    return json.loads((FIX / nom).read_text(encoding="utf-8"))


def _muter_dimension(payload: dict, nom: str, code: str) -> dict:
    payload["dimension"][nom]["category"]["index"] = {code: 0}
    payload["dimension"][nom]["category"]["label"] = {code: code}
    return payload


@pytest.fixture()
def te_mio():
    return extraire(_payload("TE", "MIO_EUR"), "TE", "MIO_EUR")


@pytest.fixture()
def te_pc():
    return extraire(_payload("TE", "PC_GDP"), "TE", "PC_GDP")


@pytest.fixture()
def tr_mio():
    return extraire(_payload("TR", "MIO_EUR"), "TR", "MIO_EUR")


@pytest.fixture()
def tr_pc():
    return extraire(_payload("TR", "PC_GDP"), "TR", "PC_GDP")


@pytest.fixture()
def observations(te_mio, te_pc, tr_mio, tr_pc):
    return fusionner({
        "TE": assembler(te_mio, te_pc, "TE"),
        "TR": assembler(tr_mio, tr_pc, "TR"),
    })


@pytest.fixture()
def conn(tmp_path, observations):
    c = db.init_db(chemin=tmp_path / "agregats.db")
    ecrire_db(c, observations)
    yield c
    c.close()


def test_md_egal_mio_divise_par_mille():
    for mio in (1000.0, 1714137.2, 1.0):
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


def test_url_api_pince_te_tr_seulement():
    assert "na_item=TE" in url_api("TE", "MIO_EUR")
    assert "na_item=TR" in url_api("TR", "PC_GDP")
    assert "gov_10a_main" in url_api("TE", "MIO_EUR")
    with pytest.raises(ValueError):
        url_api("B9", "MIO_EUR")
    with pytest.raises(ValueError):
        url_api("GD", "MIO_EUR")
    with pytest.raises(ValueError):
        url_api("TE", "EUR")


def test_extraire_la_fixture_inventee(te_mio, te_pc, tr_mio, tr_pc):
    assert [(o["annee"], o["valeur_mio_eur"], o["statut"]) for o in te_mio] == [
        (2024, 1000.0, None),
        (2025, 1100.0, "p"),
    ]
    assert [(o["annee"], o["valeur_pc_gdp"]) for o in te_pc] == [
        (2024, 50.0),
        (2025, 51.0),
    ]
    assert [(o["annee"], o["valeur_mio_eur"]) for o in tr_mio] == [
        (2024, 900.0),
        (2025, 950.0),
    ]
    for o in te_mio + tr_mio:
        assert o["geo"] == "FR"
        assert o["sector"] == "S13"
    assert {o["na_item"] for o in te_mio} == {"TE"}
    assert {o["na_item"] for o in tr_mio} == {"TR"}


def test_assembler_joint_sur_annee(te_mio, te_pc):
    jointes = assembler(te_mio, te_pc, "TE")
    assert [(o["annee"], o["valeur_mio_eur"], o["valeur_pc_gdp"], o["statut"]) for o in jointes] == [
        (2024, 1000.0, 50.0, None),
        (2025, 1100.0, 51.0, "p"),
    ]


def test_date_donnees_vient_du_time_max_pas_de_updated(observations):
    payload = _payload("TE", "MIO_EUR")
    assert payload["updated"].startswith("2026-01-01")
    time_max = max(o["annee"] for o in observations)
    assert date_fin_annee(time_max) == "2025-12-31"
    assert str(time_max) != payload["updated"][:4]


@pytest.mark.parametrize(
    "nom, code",
    [
        ("na_item", "B9"),
        ("na_item", "GD"),
        ("sector", "S1311"),
        ("geo", "DE"),
        ("unit", "PC_GDP"),
        ("freq", "Q"),
    ],
)
def test_refuse_une_dimension_hors_extrait_te_mio(nom, code):
    with pytest.raises(ValueError, match=nom):
        extraire(_muter_dimension(_payload("TE", "MIO_EUR"), nom, code), "TE", "MIO_EUR")


def test_extraire_refuse_une_valeur_nulle_ou_negative():
    payload = _payload("TE", "MIO_EUR")
    payload["value"]["1"] = 0.0
    with pytest.raises(ValueError, match="≤ 0"):
        extraire(payload, "TE", "MIO_EUR")


def test_assembler_refuse_si_time_max_sans_pc(te_mio, te_pc):
    obs_pc_tronque = [o for o in te_pc if o["annee"] != 2025]
    with pytest.raises(ValueError, match="TIME max"):
        assembler(te_mio, obs_pc_tronque, "TE")


def test_fusionner_refuse_des_time_max_divergents(te_mio, te_pc, tr_mio, tr_pc):
    te = assembler(te_mio, te_pc, "TE")
    tr = assembler(tr_mio, tr_pc, "TR")
    tr_tronque = [o for o in tr if o["annee"] != 2025]
    with pytest.raises(ValueError, match="TIME max"):
        fusionner({"TE": te, "TR": tr_tronque})


def test_controler_ampleur_refuse_la_fixture_minimale(observations):
    """La fixture a 2 points à ~1e3 MIO_EUR : hors bornes d'une série réelle."""
    with pytest.raises(ValueError):
        controler_ampleur(observations)


def test_controler_ampleur_accepte_un_ordre_de_grandeur_d_unite():
    serie = []
    for item, base_mio, base_pc in (("TE", 1.6e6, 57.0), ("TR", 1.5e6, 52.0)):
        for i in range(30):
            serie.append({
                "na_item": item,
                "annee": 1996 + i,
                "valeur_mio_eur": base_mio + i * 1e3,
                "valeur_pc_gdp": base_pc + (i % 5) * 0.1,
                "statut": "p" if i == 29 else None,
            })
    controler_ampleur(serie)


def test_ecrire_db_idempotent(conn, observations):
    n1 = conn.execute("SELECT count(*) AS n FROM agregats_apu_esa").fetchone()["n"]
    ecrire_db(conn, observations)
    ecrire_db(conn, observations)
    n2 = conn.execute("SELECT count(*) AS n FROM agregats_apu_esa").fetchone()["n"]
    assert n1 == n2 == 4


def test_check_sql_refuse_un_b9_et_un_gd(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO agregats_apu_esa "
            "(geo, sector, na_item, annee, valeur_mio_eur, valeur_pc_gdp, statut) "
            "VALUES ('FR', 'S13', 'B9', 2024, 1000.0, 50.0, NULL)"
        )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO agregats_apu_esa "
            "(geo, sector, na_item, annee, valeur_mio_eur, valeur_pc_gdp, statut) "
            "VALUES ('FR', 'S13', 'GD', 2024, 1000.0, 50.0, NULL)"
        )


def test_check_sql_refuse_un_total_negatif_ou_nul(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO agregats_apu_esa "
            "(geo, sector, na_item, annee, valeur_mio_eur, valeur_pc_gdp, statut) "
            "VALUES ('FR', 'S13', 'TE', 1990, 0.0, 50.0, NULL)"
        )


def test_meta_s44_licence_et_frequence(conn):
    ligne = conn.execute(
        "SELECT * FROM meta_sources WHERE source_id = ?", (SOURCE_ID,)
    ).fetchone()
    assert ligne is not None
    assert ligne["source_id"] == "S44"
    assert "2011/833" in ligne["licence"]
    assert "CC BY" not in ligne["licence"]
    assert ligne["frequence"] == "annuelle"
    assert ligne["date_donnees"] == "2025-12-31"
    assert ligne["lignes"] == 4
    assert ligne["url"] == "https://doi.org/10.2908/GOV_10A_MAIN"
    assert "S42" in ligne["notes"]
    assert "B9 non recalculé" in ligne["notes"]
    assert "Maastricht" in ligne["notes"]
    assert "sondage" not in ligne["notes"].lower()
    assert "baromètre" not in ligne["notes"].lower()


def test_aucune_colonne_population_par_habitant_ni_b9(conn):
    colonnes = {
        r["name"].lower()
        for r in conn.execute("PRAGMA table_info(agregats_apu_esa)")
    }
    for interdite in ("population", "par_habitant", "habitants", "b9", "deficit"):
        assert interdite not in colonnes
    notes = conn.execute(
        "SELECT notes FROM meta_sources WHERE source_id = ?", (SOURCE_ID,)
    ).fetchone()["notes"]
    assert "par habitant" in notes


def test_n_ecrit_que_agregats_apu_esa_et_meta_sources(conn):
    tables = {
        r["name"]
        for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    noyau = {"meta_sources", "entites", "elus"}
    assert noyau <= tables
    metier = tables - noyau - {"sqlite_sequence"}
    assert metier == {"agregats_apu_esa"}
    assert "deficit_apu_maastricht" not in tables
    assert "dette_apu_maastricht" not in tables
    assert not any(t.startswith("budget_") for t in metier)


def test_ecrire_refuse_un_seul_na_item(te_mio, te_pc, tmp_path):
    te = assembler(te_mio, te_pc, "TE")
    c = db.init_db(chemin=tmp_path / "incomplet.db")
    with pytest.raises(ValueError, match="incomplète"):
        ecrire_db(c, te)
    c.close()

"""Tests du pipeline P26 — dépenses des APU par fonction (S49, gov_10a_exp).

Les fixtures `eurostat_gov_10a_exp_te_*_mini.json` sont des JSON-stat
MINIMAUX INVENTÉS (TOTAL 1000/1100, dix divisions 100/110 MIO_EUR).
Elles ne reprennent aucune valeur live d'Eurostat : les garde-fous
d'ampleur (`controler_ampleur`) se testent à part, sur des ordres de
grandeur, jamais sur un total du jour.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from pipelines import db
from pipelines.ingest_cofog_apu import (
    CODES,
    DIVISIONS,
    SOURCE_ID,
    assembler,
    controler_additivite,
    controler_ampleur,
    controler_couverture,
    date_fin_annee,
    ecrire_db,
    extraire,
    mio_en_md,
    url_api,
)

FIX = Path(__file__).parent / "fixtures"


def _payload(unit: str) -> dict:
    nom = f"eurostat_gov_10a_exp_te_{'mio' if unit == 'MIO_EUR' else 'pc'}_mini.json"
    return json.loads((FIX / nom).read_text(encoding="utf-8"))


def _muter_dimension(payload: dict, nom: str, code: str) -> dict:
    payload["dimension"][nom]["category"]["index"] = {code: 0}
    payload["dimension"][nom]["category"]["label"] = {code: code}
    return payload


@pytest.fixture()
def mio():
    return extraire(_payload("MIO_EUR"), "MIO_EUR")


@pytest.fixture()
def pc():
    return extraire(_payload("PC_GDP"), "PC_GDP")


@pytest.fixture()
def observations(mio, pc):
    return assembler(mio, pc)


@pytest.fixture()
def conn(tmp_path, observations):
    c = db.init_db(chemin=tmp_path / "cofog.db")
    ecrire_db(c, observations)
    yield c
    c.close()


def test_md_egal_mio_divise_par_mille():
    for mio in (1000.0, 1671793.8, 1.0):
        md = mio_en_md(mio)
        assert md == mio / 1000.0
        assert md * 1000.0 == mio


def test_date_fin_annee():
    assert date_fin_annee(2024) == "2024-12-31"
    assert date_fin_annee(1995) == "1995-12-31"


def test_date_fin_annee_refuse_hors_plage():
    with pytest.raises(ValueError):
        date_fin_annee(999)
    with pytest.raises(ValueError):
        date_fin_annee(2024.0)  # type: ignore[arg-type]


def test_url_api_pince_te_et_onze_codes():
    url = url_api("MIO_EUR")
    assert "gov_10a_exp" in url
    assert "na_item=TE" in url
    assert "sector=S13" in url
    assert "geo=FR" in url
    for code in CODES:
        assert f"cofog99={code}" in url
    assert "GF0101" not in url
    assert "na_item=TR" not in url
    assert "na_item=B9" not in url
    with pytest.raises(ValueError):
        url_api("EUR")


def test_extraire_la_fixture_inventee(mio, pc):
    totaux_mio = [o for o in mio if o["cofog99"] == "TOTAL"]
    assert [(o["annee"], o["valeur_mio_eur"], o["statut"]) for o in totaux_mio] == [
        (2023, 1000.0, None),
        (2024, 1100.0, "p"),
    ]
    totaux_pc = [o for o in pc if o["cofog99"] == "TOTAL"]
    assert [(o["annee"], o["valeur_pc_gdp"]) for o in totaux_pc] == [
        (2023, 50.0),
        (2024, 51.0),
    ]
    assert {o["cofog99"] for o in mio} == set(CODES)
    for o in mio:
        assert o["geo"] == "FR"
        assert o["sector"] == "S13"
        assert "sondage" not in o["libelle"].lower()
        assert "baromètre" not in o["libelle"].lower()


def test_assembler_joint_sur_code_et_annee(mio, pc):
    jointes = assembler(mio, pc)
    totaux = [o for o in jointes if o["cofog99"] == "TOTAL"]
    assert [
        (o["annee"], o["valeur_mio_eur"], o["valeur_pc_gdp"], o["statut"])
        for o in totaux
    ] == [
        (2023, 1000.0, 50.0, None),
        (2024, 1100.0, 51.0, "p"),
    ]
    assert len(jointes) == 11 * 2


def test_date_donnees_vient_du_time_max_pas_de_updated(observations):
    payload = _payload("MIO_EUR")
    assert payload["updated"].startswith("2026-01-01")
    assert "2025" in payload["dimension"]["time"]["category"]["index"]
    latest = [
        a["title"]
        for a in payload["extension"]["annotation"]
        if a.get("type") == "OBS_PERIOD_OVERALL_LATEST"
    ]
    assert latest == ["2025"]
    time_max = max(o["annee"] for o in observations if o["cofog99"] == "TOTAL")
    assert time_max == 2024
    assert 2025 not in {o["annee"] for o in observations}
    assert date_fin_annee(time_max) == "2024-12-31"
    assert str(time_max) != payload["updated"][:4]
    assert str(time_max) != latest[0]


@pytest.mark.parametrize(
    "nom, code",
    [
        ("na_item", "B9"),
        ("na_item", "TR"),
        ("na_item", "P2"),
        ("sector", "S1311"),
        ("geo", "DE"),
        ("unit", "PC_GDP"),
        ("freq", "Q"),
    ],
)
def test_refuse_une_dimension_hors_extrait_te_mio(nom, code):
    with pytest.raises(ValueError, match=nom):
        extraire(_muter_dimension(_payload("MIO_EUR"), nom, code), "MIO_EUR")


def test_refuse_un_groupe_cofog():
    payload = _payload("MIO_EUR")
    payload["dimension"]["cofog99"]["category"]["index"]["GF0101"] = 11
    payload["dimension"]["cofog99"]["category"]["label"]["GF0101"] = "groupe"
    with pytest.raises(ValueError, match="hors contrat"):
        extraire(payload, "MIO_EUR")


def test_refuse_un_libelle_fr_divergent():
    payload = _payload("MIO_EUR")
    payload["dimension"]["cofog99"]["category"]["label"]["GF10"] = "Social protection"
    with pytest.raises(ValueError, match="libellé"):
        extraire(payload, "MIO_EUR")


def test_extraire_refuse_une_valeur_nulle_ou_negative():
    payload = _payload("MIO_EUR")
    payload["value"]["1"] = 0.0
    with pytest.raises(ValueError, match="≤ 0"):
        extraire(payload, "MIO_EUR")


def test_assembler_refuse_si_time_max_total_sans_pc(mio, pc):
    obs_pc_tronque = [
        o for o in pc if not (o["cofog99"] == "TOTAL" and o["annee"] == 2024)
    ]
    with pytest.raises(ValueError, match="TIME max"):
        assembler(mio, obs_pc_tronque)


def test_controler_ampleur_refuse_la_fixture_minimale(observations):
    with pytest.raises(ValueError):
        controler_ampleur(observations)


def test_controler_ampleur_accepte_un_ordre_de_grandeur_d_unite():
    serie = []
    for i in range(30):
        annee = 1995 + i
        serie.append({
            "cofog99": "TOTAL",
            "annee": annee,
            "valeur_mio_eur": 1.6e6 + i * 1e3,
            "valeur_pc_gdp": 57.0 + (i % 5) * 0.1,
            "statut": "p" if i == 29 else None,
        })
        for code in DIVISIONS:
            serie.append({
                "cofog99": code,
                "annee": annee,
                "valeur_mio_eur": 1.0e5,
                "valeur_pc_gdp": 5.0,
                "statut": None,
            })
    controler_ampleur(serie)


def test_controler_couverture_refuse_une_annee_sans_division(observations):
    tronque = [
        o for o in observations
        if not (o["annee"] == 2024 and o["cofog99"] == "GF10")
    ]
    with pytest.raises(ValueError, match="incomplète"):
        controler_couverture(tronque)


def test_controler_additivite_accepte_la_fixture(observations):
    controler_additivite(observations)


def test_controler_additivite_refuse_un_trou():
    serie = [
        {
            "cofog99": "TOTAL",
            "annee": 2024,
            "valeur_mio_eur": 1000.0,
            "valeur_pc_gdp": 50.0,
            "statut": None,
        }
    ]
    for code in DIVISIONS:
        serie.append({
            "cofog99": code,
            "annee": 2024,
            "valeur_mio_eur": 90.0,
            "valeur_pc_gdp": 4.5,
            "statut": None,
        })
    with pytest.raises(ValueError, match="GF01"):
        controler_additivite(serie)


def test_ecrire_db_idempotent(conn, observations):
    n1 = conn.execute("SELECT count(*) AS n FROM cofog_apu_esa").fetchone()["n"]
    ecrire_db(conn, observations)
    ecrire_db(conn, observations)
    n2 = conn.execute("SELECT count(*) AS n FROM cofog_apu_esa").fetchone()["n"]
    assert n1 == n2 == 22


def test_check_sql_refuse_un_groupe_et_un_s1311(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO cofog_apu_esa "
            "(geo, sector, cofog99, libelle, annee, valeur_mio_eur, valeur_pc_gdp, statut) "
            "VALUES ('FR', 'S13', 'GF0101', 'groupe', 2024, 100.0, 1.0, NULL)"
        )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO cofog_apu_esa "
            "(geo, sector, cofog99, libelle, annee, valeur_mio_eur, valeur_pc_gdp, statut) "
            "VALUES ('FR', 'S1311', 'TOTAL', 'Total', 2024, 1000.0, 50.0, NULL)"
        )


def test_check_sql_refuse_un_total_negatif_ou_nul(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO cofog_apu_esa "
            "(geo, sector, cofog99, libelle, annee, valeur_mio_eur, valeur_pc_gdp, statut) "
            "VALUES ('FR', 'S13', 'TOTAL', 'Total', 1990, 0.0, 50.0, NULL)"
        )


def test_meta_s49_licence_et_frequence(conn):
    ligne = conn.execute(
        "SELECT * FROM meta_sources WHERE source_id = ?", (SOURCE_ID,)
    ).fetchone()
    assert ligne is not None
    assert ligne["source_id"] == "S49"
    assert "2011/833" in ligne["licence"]
    assert "CC BY" not in ligne["licence"]
    assert ligne["frequence"] == "annuelle"
    assert ligne["date_donnees"] == "2024-12-31"
    assert ligne["lignes"] == 22
    assert ligne["url"] == "https://doi.org/10.2908/GOV_10A_EXP"
    assert "S44" in ligne["notes"]
    assert "S45" in ligne["notes"]
    assert "sondage" not in ligne["notes"].lower()
    assert "baromètre" not in ligne["notes"].lower()
    assert "dette de l'État" not in ligne["notes"]
    assert "dette de l'Etat" not in ligne["notes"]


def test_aucune_colonne_population_par_habitant_ni_b9(conn):
    colonnes = {
        r["name"].lower()
        for r in conn.execute("PRAGMA table_info(cofog_apu_esa)")
    }
    for interdite in ("population", "par_habitant", "habitants", "b9", "deficit"):
        assert interdite not in colonnes
    notes = conn.execute(
        "SELECT notes FROM meta_sources WHERE source_id = ?", (SOURCE_ID,)
    ).fetchone()["notes"]
    assert "par habitant" in notes


def test_n_ecrit_que_cofog_apu_esa_et_meta_sources(conn):
    tables = {
        r["name"]
        for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    noyau = {"meta_sources", "entites", "elus"}
    assert noyau <= tables
    metier = tables - noyau - {"sqlite_sequence"}
    assert metier == {"cofog_apu_esa"}
    assert "agregats_apu_esa" not in tables
    assert "protection_sociale_prestations" not in tables


def test_ecrire_refuse_sans_total(mio, pc, tmp_path):
    jointes = [o for o in assembler(mio, pc) if o["cofog99"] != "TOTAL"]
    c = db.init_db(chemin=tmp_path / "incomplet.db")
    with pytest.raises(ValueError, match="incomplète"):
        ecrire_db(c, jointes)
    c.close()

"""Tests du pipeline P21 — bilan patrimonial de l'État (S22, CGE).

La fixture `cge_bilan_cdr_solde.xlsx` EST la pièce de synthèse officielle
(SHA-256 0f9567ec…, 92 411 o, jeu balances_des_comptes_etat). Elle porte
le piège d'unité réel : 2024 en euros, 2023 en millions. Les garde-fous
d'ampleur se testent aussi sur une série inventée hors bornes.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from pipelines import db
from pipelines.ingest_cge import (
    SOURCE_ID,
    controler_ampleur,
    controler_identite,
    controler_licence,
    date_fin_annee,
    detecter_unite,
    ecrire_db,
    en_euros,
    euros_en_md,
    extraire,
    url_piece_synthese,
)

FIX = Path(__file__).parent / "fixtures" / "cge_bilan_cdr_solde.xlsx"


@pytest.fixture()
def observations():
    return extraire(FIX)


@pytest.fixture()
def conn(tmp_path, observations):
    c = db.init_db(chemin=tmp_path / "cge.db")
    ecrire_db(c, observations)
    yield c
    c.close()


def test_md_egal_euros_divise_par_milliard():
    for euros in (1e9, 1_317_885_543_575.8, -1_987_192_129_076.46):
        md = euros_en_md(euros)
        assert md == euros / 1e9


def test_date_fin_annee():
    assert date_fin_annee(2024) == "2024-12-31"
    with pytest.raises(ValueError):
        date_fin_annee(999)
    with pytest.raises(ValueError):
        date_fin_annee(2024.0)  # type: ignore[arg-type]


def test_detecter_unite_par_ordre_de_grandeur_pas_par_entete():
    assert detecter_unite(1_317_885_543_575.8) == "EUR"
    assert detecter_unite(1_294_468) == "MIO_EUR"
    assert detecter_unite(-1_875_100) == "MIO_EUR"
    with pytest.raises(ValueError):
        detecter_unite("pas un nombre")


def test_en_euros_normalise_les_deux_unites():
    assert en_euros(1_317_885_543_575.8, "EUR") == 1_317_885_543_575.8
    assert en_euros(1_294_468, "MIO_EUR") == 1_294_468 * 1e6


def test_extraire_la_piece_officielle_identite_et_unites_mixtes(observations):
    par = {(o["annee"], o["poste"]): o for o in observations}
    assert (2024, "actif") in par
    assert (2023, "actif") in par
    # 2024 stocké en euros, 2023 en millions — même ordre de grandeur après conversion.
    a24 = par[(2024, "actif")]
    a23 = par[(2023, "actif")]
    assert a24["unite_source"] == "EUR"
    assert a23["unite_source"] == "MIO_EUR"
    assert 1.2e12 < a24["valeur_euros"] < 1.4e12
    assert 1.2e12 < a23["valeur_euros"] < 1.4e12
    # I − II = III déjà exigé par extraire() ; on fige les totaux 2024.
    assert abs(a24["valeur_euros"] - 1_317_885_543_575.8) < 1.0
    sn24 = par[(2024, "situation_nette")]["valeur_euros"]
    assert sn24 < 0
    assert abs(sn24 - (-1_987_192_129_076.46)) < 1.0
    assert {o["poste"] for o in observations} == {
        "actif",
        "passif_hors_sn",
        "situation_nette",
        "dettes_financieres",
        "solde_exercice",
    }
    annees = {o["annee"] for o in observations}
    assert min(annees) == 2006
    assert max(annees) == 2024
    # Aucun millésime 2025 : la pièce s'arrête à 2024.
    assert 2025 not in annees
    s24 = par[(2024, "solde_exercice")]
    assert s24["unite_source"] == "EUR"
    assert abs(s24["valeur_euros"] - (-123_703_947_751.28)) < 1.0
    s23 = par[(2023, "solde_exercice")]
    assert s23["unite_source"] == "EUR" or s23["unite_source"] == "MIO_EUR"
    assert -2e11 < s23["valeur_euros"] < -5e10


def test_date_donnees_vient_du_millesime_pas_de_modified(observations):
    # Le catalogue porte modified=2026-04-22 ; la pièce s'arrête à 2024.
    assert date_fin_annee(max(o["annee"] for o in observations)) == "2024-12-31"


def test_controler_ampleur_refuse_une_serie_trop_courte(observations):
    courte = [o for o in observations if o["annee"] >= 2023]
    with pytest.raises(ValueError, match="années"):
        controler_ampleur(courte)


def test_controler_ampleur_refuse_un_actif_en_millions_non_converti():
    serie = []
    for i in range(16):
        an = 2009 + i
        serie.extend(
            [
                {"annee": an, "poste": "actif", "valeur_euros": 1_294_468.0, "unite_source": "EUR"},
                {"annee": an, "poste": "passif_hors_sn", "valeur_euros": 3_169_568.0, "unite_source": "EUR"},
                {"annee": an, "poste": "situation_nette", "valeur_euros": -1_875_100.0, "unite_source": "EUR"},
                {"annee": an, "poste": "dettes_financieres", "valeur_euros": 2_476_836.0, "unite_source": "EUR"},
                {"annee": an, "poste": "solde_exercice", "valeur_euros": -123_704.0, "unite_source": "EUR"},
            ]
        )
    with pytest.raises(ValueError, match="unité"):
        controler_ampleur(serie)


def test_controler_ampleur_accepte_la_piece_officielle(observations):
    controler_ampleur(observations)


def test_controler_identite_refuse_un_ecart():
    obs = [
        {"annee": 2024, "poste": "actif", "valeur_euros": 100.0, "unite_source": "EUR"},
        {"annee": 2024, "poste": "passif_hors_sn", "valeur_euros": 40.0, "unite_source": "EUR"},
        {"annee": 2024, "poste": "situation_nette", "valeur_euros": 50.0, "unite_source": "EUR"},
    ]
    with pytest.raises(ValueError, match="I − II"):
        controler_identite(obs)


def test_ecrire_db_idempotent(conn, observations):
    n1 = conn.execute("SELECT count(*) AS n FROM cge_bilan_etat").fetchone()["n"]
    ecrire_db(conn, observations)
    ecrire_db(conn, observations)
    n2 = conn.execute("SELECT count(*) AS n FROM cge_bilan_etat").fetchone()["n"]
    assert n1 == n2 == len(observations)


def test_meta_s22_licence_et_date(conn):
    row = conn.execute(
        "SELECT source_id, licence, frequence, date_donnees, url, notes FROM meta_sources"
    ).fetchone()
    assert row["source_id"] == SOURCE_ID == "S22"
    assert "Licence Ouverte 2.0" in row["licence"]
    assert "CC BY" not in row["licence"]
    assert row["frequence"] == "annuelle"
    assert row["date_donnees"] == "2024-12-31"
    assert "balances_des_comptes_etat" in row["url"]
    assert "S13" in row["notes"]
    assert "dette de l'État" in row["notes"]
    assert "2025" in row["notes"]
    assert "sondage" not in row["notes"].lower()
    assert "baromètre" not in row["notes"].lower()


def test_n_ecrit_que_cge_bilan_etat_et_noyau(conn):
    tables = {
        r["name"]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    }
    assert "cge_bilan_etat" in tables
    # Noyau db.py
    assert {"meta_sources", "entites", "elus"} <= tables
    assert "dette_apu_maastricht" not in tables
    assert "agregats_apu_esa" not in tables
    assert "budget_mensuel" not in tables


def test_check_sql_refuse_un_poste_hors_liste(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO cge_bilan_etat (annee, poste, valeur_euros, unite_source) "
            "VALUES (2024, 'total_invente', 1.0, 'EUR')"
        )


def test_source_id_est_s22_jamais_s13():
    assert SOURCE_ID == "S22"
    assert SOURCE_ID != "S13"


def test_url_piece_synthese_prend_le_xlsx_bilan():
    meta = {
        "attachments": [
            {"title": "Guide-de-lecture.pdf", "url": "https://x/guide", "mimetype": "application/pdf"},
            {
                "title": "2006-2024 Bilan, CDR, solde.xlsx",
                "url": "https://x/bilan.xlsx",
                "mimetype": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            },
        ]
    }
    assert url_piece_synthese(meta) == "https://x/bilan.xlsx"
    with pytest.raises(ValueError, match="synthèse"):
        url_piece_synthese({"attachments": []})


def test_controler_licence_refuse_une_licence_autre():
    controler_licence({"metas": {"default": {"license": "Licence Ouverte v2.0 (Etalab)"}}})
    with pytest.raises(ValueError, match="licence"):
        controler_licence({"metas": {"default": {"license": "CC BY 4.0"}}})


def test_aucune_fonction_de_somme_des_balances():
    import pipelines.ingest_cge as mod

    noms = [n for n in dir(mod) if "sum" in n.lower() or "somme" in n.lower()]
    assert noms == []

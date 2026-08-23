"""Tests du pipeline P22 — prestations de protection sociale (S45, DREES).

La fixture `drees_protection_sociale_mini.json` est MINIMALE INVENTÉE
(totaux 800/900 M€). Elle ne reprend aucune valeur live. Les garde-fous
d'ampleur se testent à part, sur des ordres de grandeur, jamais sur un
total du jour. Deux lignes de niveau 2 (maladie, CNAV) doivent être
ignorées : les ingérer double-compterait.
"""

from __future__ import annotations

import copy
import json
import sqlite3
from pathlib import Path

import pytest

from pipelines import db
from pipelines.ingest_protection_sociale import (
    SOURCE_ID,
    controler_ampleur,
    date_fin_annee,
    ecrire_db,
    extraire,
    mio_en_md,
)

FIX = Path(__file__).parent / "fixtures" / "drees_protection_sociale_mini.json"


def _payload() -> list:
    return json.loads(FIX.read_text(encoding="utf-8"))


@pytest.fixture()
def lignes():
    return extraire(_payload())


@pytest.fixture()
def conn(tmp_path, lignes):
    c = db.init_db(chemin=tmp_path / "protection.db")
    ecrire_db(c, lignes)
    yield c
    c.close()


def test_md_egal_mio_divise_par_mille():
    for mio in (1000.0, 932548.27, 1.0):
        md = mio_en_md(mio)
        assert md == mio / 1000.0
        assert md * 1000.0 == pytest.approx(mio)


def test_date_fin_annee():
    assert date_fin_annee(2024) == "2024-12-31"
    assert date_fin_annee(1959) == "1959-12-31"


def test_date_fin_annee_refuse_hors_plage():
    with pytest.raises(ValueError):
        date_fin_annee(999)
    with pytest.raises(ValueError):
        date_fin_annee(2024.0)  # type: ignore[arg-type]


def test_extraire_ignore_niveaux_2(lignes):
    codes = {(o["annee"], o["grain"], o["code"]) for o in lignes}
    assert (2024, "risque", "E11-11") not in codes
    assert (2024, "regime", "CNAV") not in codes
    # le niveau 2 S13141 ne doit pas remplacer ni s'ajouter au niveau 1
    regimes_2024 = [o for o in lignes if o["annee"] == 2024 and o["grain"] == "regime"]
    assert {o["code"] for o in regimes_2024} == {"S13141", "S13111", "S15"}


def test_extraire_recompose_les_deux_annees(lignes):
    for annee, total in ((2023, 800.0), (2024, 900.0)):
        t = next(o for o in lignes if o["annee"] == annee and o["grain"] == "total")
        assert t["val_mio_eur"] == total
        risques = [o for o in lignes if o["annee"] == annee and o["grain"] == "risque"]
        regimes = [o for o in lignes if o["annee"] == annee and o["grain"] == "regime"]
        assert {o["code"] for o in risques} == {
            "E11-1", "E11-2", "E11-3", "E11-4", "E11-5", "E11-6",
        }
        assert sum(o["val_mio_eur"] for o in risques) == pytest.approx(total)
        assert sum(o["val_mio_eur"] for o in regimes) == pytest.approx(total)


def test_extraire_refuse_time_max_sans_regime_general():
    payload = copy.deepcopy(_payload())
    for row in payload:
        if row["annee"] == "2024" and row.get("si_code") == "S13141":
            row["si_code"] = "S13142"
            row["si_nom"] = "Autres organismes dépendants des assurances sociales"
    with pytest.raises(ValueError, match="S13141"):
        extraire(payload)


def test_extraire_refuse_risques_qui_ne_recomposent_pas():
    payload = _payload()
    for row in payload:
        if row["annee"] == "2024" and row["ps_code"] == "E11-1":
            row["val"] = 1.0
    with pytest.raises(ValueError, match="risques"):
        extraire(payload)


def test_controler_ampleur_rejette_la_fixture(lignes):
    with pytest.raises(ValueError, match="totaux"):
        controler_ampleur(lignes)


def _serie_dans_les_bornes() -> list[dict]:
    """Série synthétique : 20 totaux, TIME max dans ]200 Md€, 2 000 Md€[."""
    lignes = []
    for annee in range(2005, 2025):
        total = 400_000.0 if annee < 2024 else 900_000.0
        lignes.append({
            "annee": annee,
            "grain": "total",
            "code": "S1",
            "libelle": "Total tous régimes",
            "val_mio_eur": total,
        })
    parts_risque = {
        "E11-1": 330_000.0,
        "E11-2": 280_000.0,
        "E11-3": 90_000.0,
        "E11-4": 80_000.0,
        "E11-5": 60_000.0,
        "E11-6": 60_000.0,
    }
    assert sum(parts_risque.values()) == 900_000.0
    for code, val in parts_risque.items():
        lignes.append({
            "annee": 2024,
            "grain": "risque",
            "code": code,
            "libelle": code,
            "val_mio_eur": val,
        })
    parts_regime = {
        "S13141": 550_000.0,
        "S13111": 220_000.0,
        "S15": 130_000.0,
    }
    assert sum(parts_regime.values()) == 900_000.0
    for code, val in parts_regime.items():
        lignes.append({
            "annee": 2024,
            "grain": "regime",
            "code": code,
            "libelle": code,
            "val_mio_eur": val,
        })
    return lignes


def test_controler_ampleur_accepte_une_serie_dans_les_bornes():
    controler_ampleur(_serie_dans_les_bornes())


def test_controler_ampleur_rejette_un_total_hors_borne():
    serie = _serie_dans_les_bornes()
    for o in serie:
        if o["grain"] == "total" and o["annee"] == 2024:
            o["val_mio_eur"] = 50.0
    with pytest.raises(ValueError, match="unité"):
        controler_ampleur(serie)


def test_ecrire_db_idempotent_et_meta(conn):
    n1 = conn.execute(
        "SELECT count(*) FROM protection_sociale_prestations"
    ).fetchone()[0]
    ecrire_db(conn, extraire(_payload()))
    n2 = conn.execute(
        "SELECT count(*) FROM protection_sociale_prestations"
    ).fetchone()[0]
    assert n1 == n2 == 20  # 2 totaux + 12 risques + 6 régimes
    meta = conn.execute(
        "SELECT source_id, licence, date_donnees, url FROM meta_sources WHERE source_id = ?",
        (SOURCE_ID,),
    ).fetchone()
    assert meta[0] == "S45"
    assert "Licence Ouverte 2.0" in meta[1]
    assert "2011/833" not in meta[1]
    assert "CC BY" not in meta[1]
    assert meta[2] == "2024-12-31"
    assert "last_update" not in (meta[3] or "")
    assert "data.gouv.fr/datasets/les-comptes-de-la-protection-sociale" in meta[3]


def test_date_donnees_n_est_pas_la_maj_catalogue(conn):
    date = conn.execute(
        "SELECT date_donnees FROM meta_sources WHERE source_id = 'S45'"
    ).fetchone()[0]
    assert date == "2024-12-31"
    assert date != "2025-12-18"


def test_check_refuse_un_grain_inconnu(tmp_path, lignes):
    c = db.init_db(chemin=tmp_path / "check.db")
    ecrire_db(c, lignes)
    with pytest.raises(sqlite3.IntegrityError):
        c.execute(
            """INSERT INTO protection_sociale_prestations
               (annee, grain, code, libelle, val_mio_eur)
               VALUES (2024, 'recette', 'X', 'X', 1)"""
        )
    c.close()


def test_n_ecrit_que_protection_sociale_prestations_et_noyau(conn):
    metier = {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' "
            "AND name NOT IN ('meta_sources', 'entites', 'elus')"
        )
    }
    assert metier == {"protection_sociale_prestations"}
    n_s45 = conn.execute(
        "SELECT count(*) FROM protection_sociale_prestations"
    ).fetchone()[0]
    assert n_s45 == 20


def test_extrait_reel_2024_recompose_et_ignore_le_niveau_2():
    """Extrait daté des 16 lignes exclusives 2024 + 1 piège niveau 2.

    L'invariant est la recomposition, pas le millésime qui dérivera.
    """
    payload = json.loads(
        (Path(__file__).parent / "fixtures" / "drees_protection_sociale_2024_exclusif.json")
        .read_text(encoding="utf-8")
    )
    lignes = extraire(payload)
    totaux = [o for o in lignes if o["grain"] == "total"]
    assert len(totaux) == 1
    total = totaux[0]["val_mio_eur"]
    risques = [o for o in lignes if o["grain"] == "risque"]
    regimes = [o for o in lignes if o["grain"] == "regime"]
    assert {o["code"] for o in risques} == set(
        ("E11-1", "E11-2", "E11-3", "E11-4", "E11-5", "E11-6")
    )
    assert len(regimes) == 9
    assert "S13141" in {o["code"] for o in regimes}
    assert sum(1 for o in regimes if o["code"] == "S13141") == 1
    assert sum(o["val_mio_eur"] for o in risques) == pytest.approx(total)
    assert sum(o["val_mio_eur"] for o in regimes) == pytest.approx(total)
    assert all(o["code"] != "E11-11" for o in lignes)


def test_pas_de_colonne_par_habitant_ni_pib():
    from pipelines.ingest_protection_sociale import NOTES, _DDL
    source = Path(__file__).resolve().parents[1] / "ingest_protection_sociale.py"
    ddl_src = source.read_text(encoding="utf-8").lower()
    assert "pc_gdp" not in _DDL.lower()
    assert "habitant" not in _DDL.lower()
    assert "eur_hab" not in _DDL.lower()
    assert "sondage" not in ddl_src
    assert "baromètre" not in ddl_src and "barometre" not in ddl_src
    assert "par habitant" in NOTES  # l'interdit est nommé, pas une colonne

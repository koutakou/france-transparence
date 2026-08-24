"""Tests du pipeline P23 — recettes du budget général au PLF (S46).

La fixture `plf25_recettes_mini.csv` est MINIMALE INVENTÉE (totaux
en euros, pas en milliards). Elle ne reprend aucune valeur live.
Les garde-fous d'ampleur se testent à part, sur des ordres de
grandeur, jamais sur un total du jour. Un zéro publié (2199) doit
rester un zéro, pas un NULL.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from pipelines import db
from pipelines.ingest_recettes_plf import (
    CODES_PARTICIPATIONS,
    SOURCE_ID,
    TYPES_INTERNES,
    controler_ampleur,
    date_publication,
    ecrire_db,
    euros_en_md,
    extraire,
)

FIX = Path(__file__).parent / "fixtures" / "plf25_recettes_mini.csv"


@pytest.fixture()
def lignes():
    return extraire(FIX)


@pytest.fixture()
def conn(tmp_path, lignes):
    c = db.init_db(chemin=tmp_path / "recettes_plf.db")
    ecrire_db(c, lignes)
    yield c
    c.close()


def test_md_egal_euros_divise_par_1e9():
    for euros in (1e9, 20_548_548_212.0, 1.0):
        md = euros_en_md(euros)
        assert md == euros / 1e9
        assert md * 1e9 == pytest.approx(euros)


def test_date_publication_2025_est_le_11_octobre_pas_le_depot_an():
    # Dépôt AN = 10/10/2024 (texte n° 324). Open data recettes = 11/10/2024.
    assert date_publication(2025) == "2024-10-11"
    assert date_publication(2025) != "2024-10-10"


def test_date_publication_refuse_millesime_inconnu():
    with pytest.raises(ValueError, match="DATES_PUBLICATION"):
        date_publication(2026)


def test_extraire_lit_le_bom_et_le_point_virgule(lignes):
    assert len(lignes) == 7
    assert {o["type_recette"] for o in lignes} == TYPES_INTERNES


def test_extraire_code_entier_malgre_le_point_zero(lignes):
    assert {o["code"] for o in lignes} >= {1101, 2110, 2116, 2199, 3201}


def test_extraire_conserve_le_zero_publie(lignes):
    zero = next(o for o in lignes if o["code"] == 2199)
    assert zero["montant_euros"] == 0.0
    assert zero["montant_euros"] is not None


def test_extraire_refuse_un_type_inconnu(tmp_path):
    p = tmp_path / "mauvais.csv"
    p.write_text(
        "annee;type_de_recettes;code_ligne_recettes;libelle;montant_recettes_plf\n"
        "2025;Recettes martiennes;9999.0;Inventé;1.0\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="type_de_recettes inconnu"):
        extraire(p)


def test_extraire_refuse_un_negatif(tmp_path):
    p = tmp_path / "neg.csv"
    p.write_text(
        "annee;type_de_recettes;code_ligne_recettes;libelle;montant_recettes_plf\n"
        "2025;Recettes fiscales;1101.0;Inventé;-1.0\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="négatif"):
        extraire(p)


def test_extraire_refuse_un_doublon(tmp_path):
    p = tmp_path / "dup.csv"
    p.write_text(
        "annee;type_de_recettes;code_ligne_recettes;libelle;montant_recettes_plf\n"
        "2025;Recettes fiscales;1101.0;A;1.0\n"
        "2025;Recettes fiscales;1101.0;B;2.0\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="dupliqué"):
        extraire(p)


def _ligne(annee, type_recette, code, montant, libelle="x"):
    return {
        "annee": annee,
        "type_recette": type_recette,
        "code": code,
        "libelle": libelle,
        "montant_euros": montant,
    }


def _catalogue_plausible(n_filler: int = 100) -> list[dict]:
    """Catalogue à l'échelle live, inventé, pour controler_ampleur."""
    lignes = [
        _ligne(2025, "fiscales", 1101, 400e9, "IR inventé"),
        _ligne(2025, "non_fiscales", 2110, 1.5e9, "participations financières"),
        _ligne(2025, "non_fiscales", 2116, 4.5e9, "participations non financières"),
        _ligne(2025, "non_fiscales", 2199, 0.0, "autres dividendes"),
        _ligne(2025, "psr_collectivites", 3101, 27e9, "DGF"),
        _ligne(2025, "psr_ue", 3201, 23e9, "PSR UE"),
    ]
    # non fiscales supplémentaires pour rester dans 5–50 Md€
    restant_nf = 14e9
    lignes.append(_ligne(2025, "non_fiscales", 2501, restant_nf, "amendes"))
    code = 4000
    while len(lignes) < n_filler:
        lignes.append(_ligne(2025, "fiscales", code, 1.0, f"filler {code}"))
        code += 1
    return lignes


def test_controler_ampleur_accepte_un_catalogue_plausible():
    controler_ampleur(_catalogue_plausible())


def test_controler_ampleur_refuse_une_fixture_trop_petite(lignes):
    with pytest.raises(ValueError, match="lignes"):
        controler_ampleur(lignes)


def test_controler_ampleur_refuse_un_millesime_sans_date_ecrite():
    cat = _catalogue_plausible()
    for o in cat:
        o["annee"] = 2026
    with pytest.raises(ValueError, match="DATES_PUBLICATION"):
        controler_ampleur(cat)


def test_controler_ampleur_refuse_participations_manquantes():
    cat = [o for o in _catalogue_plausible() if o["code"] != 2110]
    cat.append(_ligne(2025, "fiscales", 4999, 1.0, "remplace 2110"))
    with pytest.raises(ValueError, match="participations manquants"):
        controler_ampleur(cat)


def test_controler_ampleur_refuse_non_fiscales_en_millions_pris_pour_euros():
    cat = _catalogue_plausible()
    for o in cat:
        if o["type_recette"] == "non_fiscales":
            o["montant_euros"] = o["montant_euros"] / 1e6  # erreur d'unité
    with pytest.raises(ValueError, match="unité"):
        controler_ampleur(cat)


def test_ecrire_db_meta_s46_et_date_publication(conn):
    meta = conn.execute(
        "SELECT source_id, date_donnees, lignes FROM meta_sources WHERE source_id = ?",
        (SOURCE_ID,),
    ).fetchone()
    assert tuple(meta) == ("S46", "2024-10-11", 7)


def test_ecrire_db_ne_prend_pas_le_31_decembre(conn):
    date = conn.execute(
        "SELECT date_donnees FROM meta_sources WHERE source_id = 'S46'"
    ).fetchone()[0]
    assert date != "2025-12-31"


def test_ecrire_db_zero_conserve(conn):
    val = conn.execute(
        "SELECT montant_euros FROM recettes_plf_etat_a WHERE code = 2199"
    ).fetchone()[0]
    assert val == 0.0


def test_ecrire_db_quatre_types(conn):
    types = {
        r[0]
        for r in conn.execute(
            "SELECT DISTINCT type_recette FROM recettes_plf_etat_a"
        )
    }
    assert types == TYPES_INTERNES


def test_ecrire_db_idempotente(tmp_path, lignes):
    c = db.init_db(chemin=tmp_path / "idem.db")
    ecrire_db(c, lignes)
    ecrire_db(c, lignes)
    n = c.execute("SELECT COUNT(*) FROM recettes_plf_etat_a").fetchone()[0]
    assert n == 7
    c.close()


def test_ecrire_db_echec_laisse_la_base_intacte(tmp_path, lignes):
    c = db.init_db(chemin=tmp_path / "intact.db")
    ecrire_db(c, lignes)
    mauvais = [dict(o) for o in lignes]
    mauvais[0]["type_recette"] = "invente"
    with pytest.raises((ValueError, sqlite3.IntegrityError)):
        ecrire_db(c, mauvais)
    n = c.execute("SELECT COUNT(*) FROM recettes_plf_etat_a").fetchone()[0]
    assert n == 7
    sid = c.execute(
        "SELECT source_id FROM meta_sources WHERE source_id = 'S46'"
    ).fetchone()[0]
    assert sid == "S46"
    c.close()


def test_codes_participations_fermes():
    assert CODES_PARTICIPATIONS == (2110, 2116, 2199)

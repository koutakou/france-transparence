"""Tests du pipeline P19 — dossiers législatifs DILA (S43).

Les fixtures XML sont MINIMALES et INVENTÉES (législatures 98/99, ids FAKE).
Aucune valeur live du Freemium n'y figure : les garde-fous d'ampleur se
testent à part, sur des ordres de grandeur, jamais sur un stock du jour.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pipelines import db
from pipelines.ingest_dole import (
    LICENCE,
    SOURCE_ID,
    TYPES_NAVETTE,
    controler_ampleur,
    ecrire_db,
    est_en_navette,
    legislature_courante,
    lister_index,
    parse_dossier,
)

FIX = Path(__file__).parent / "fixtures" / "dole"


def _xml(nom: str) -> bytes:
    return (FIX / nom).read_bytes()


def _dossiers():
    noms = [
        "projet_leg99.xml",
        "loi_publiée_leg99.xml",
        "projet_leg98.xml",
        "sans_type.xml",
    ]
    out = []
    for nom in noms:
        d = parse_dossier(_xml(nom))
        assert d is not None, nom
        out.append(d)
    return out


@pytest.fixture()
def dossiers():
    return _dossiers()


@pytest.fixture()
def conn(tmp_path, dossiers):
    c = db.init_db(chemin=tmp_path / "dole.db")
    ecrire_db(c, dossiers)
    yield c
    c.close()


# ---------------------------------------------------------------------------
# Index : Freemium le plus récent, incréments strictement postérieurs
# ---------------------------------------------------------------------------


def test_lister_index_prend_le_freemium_le_plus_recent_et_ecarte_lanterieur():
    html = (FIX / "index.html").read_text(encoding="utf-8")
    plan = lister_index(html)
    assert plan.freemium == "Freemium_dole_global_20250713-140000.tar.gz"
    assert "Freemium_dole_global_20240101-000000.tar.gz" not in plan.freemium
    assert plan.increments == (
        "DOLE_20250715-205701.tar.gz",
        "DOLE_20260820-220411.tar.gz",
    )
    # L'incrément du 11/07 est ANTÉRIEUR au Freemium du 13/07 : déjà dans le stock.
    assert "DOLE_20250711-212007.tar.gz" not in plan.increments


def test_lister_index_ecarte_les_pdf():
    html = (FIX / "index.html").read_text(encoding="utf-8")
    plan = lister_index(html)
    assert all(n.endswith(".tar.gz") for n in (plan.freemium, *plan.increments))
    assert all("Presentation" not in n for n in (plan.freemium, *plan.increments))


def test_lister_index_sans_freemium_refuse():
    with pytest.raises(ValueError, match="Freemium"):
        lister_index('<a href="DOLE_20260820-220411.tar.gz">x</a>')


# ---------------------------------------------------------------------------
# Parseur : métadonnées, pas l'exposé ; TYPE vide conservé
# ---------------------------------------------------------------------------


def test_parse_derniere_etape_est_le_dernier_lien_direct_pas_le_rapport_niche():
    d = parse_dossier(_xml("projet_leg99.xml"))
    assert d is not None
    assert d.derniere_etape.startswith("Texte adopté en 1ère lecture par le Sénat")
    assert "Rapport" not in d.derniere_etape
    assert d.derniere_etape_url == "https://example.test/senat"


def test_parse_ne_porte_pas_lexpose_des_motifs():
    d = parse_dossier(_xml("projet_leg99.xml"))
    assert d is not None
    assert "ne doit pas être ingéré" not in d.titre
    assert not any("exposé" in f for f in d.__dataclass_fields__)


def test_parse_type_vide_reste_vide():
    d = parse_dossier(_xml("sans_type.xml"))
    assert d is not None
    assert d.type == ""
    # On ne déduit PAS LOI_PUBLIEE du titre « Loi n° ».
    assert d.type not in TYPES_NAVETTE
    assert d.type != "LOI_PUBLIEE"


def test_parse_sans_id_ou_titre_est_ecarte():
    sans_id = _xml("projet_leg99.xml").replace(
        b"<ID>JORFDOLEFAKE000000001</ID>", b"<ID></ID>"
    )
    assert parse_dossier(sans_id) is None
    sans_titre = _xml("projet_leg99.xml").replace(
        b"<TITRE>Projet de loi fictif de test</TITRE>", b"<TITRE></TITRE>"
    )
    assert parse_dossier(sans_titre) is None


def test_parse_refuse_un_xml_qui_n_est_pas_un_dossier():
    assert parse_dossier(b"<JO><ID>x</ID></JO>") is None
    assert parse_dossier(b"pas de xml") is None


def test_lien_legifrance_construit_sur_lid():
    d = parse_dossier(_xml("projet_leg99.xml"))
    assert d is not None
    assert d.lien_legifrance == (
        "https://www.legifrance.gouv.fr/dossierlegislatif/JORFDOLEFAKE000000001"
    )


# ---------------------------------------------------------------------------
# Navette = type ouvert × législature courante, pas le TYPE seul
# ---------------------------------------------------------------------------


def test_legislature_courante_est_le_numero_max_pas_un_17_en_dur(dossiers):
    num, lib = legislature_courante(dossiers)
    assert num == "99"
    assert "fictive" in lib
    assert num != "17"


def test_projet_dune_legislature_close_n_est_pas_en_navette(dossiers):
    num, _ = legislature_courante(dossiers)
    par_id = {d.dossier_id: d for d in dossiers}
    actuel = par_id["JORFDOLEFAKE000000001"]
    clos = par_id["JORFDOLEFAKE000000003"]
    publie = par_id["JORFDOLEFAKE000000002"]
    sans_type = par_id["JORFDOLEFAKE000000004"]
    assert actuel.type == "PROJET_LOI" and est_en_navette(actuel, num)
    assert clos.type == "PROJET_LOI" and not est_en_navette(clos, num)
    assert publie.type == "LOI_PUBLIEE" and not est_en_navette(publie, num)
    assert sans_type.type == "" and not est_en_navette(sans_type, num)


# ---------------------------------------------------------------------------
# Écriture : S43, date_donnees métier, pas jorf_*, idempotence
# ---------------------------------------------------------------------------


def test_date_donnees_est_le_max_des_date_modif_pas_une_horloge(conn):
    ligne = conn.execute(
        "SELECT date_donnees, source_id, lignes, licence FROM meta_sources WHERE source_id = ?",
        (SOURCE_ID,),
    ).fetchone()
    assert ligne["source_id"] == "S43"
    assert ligne["date_donnees"] == "2026-06-15"  # max des 4 fixtures
    assert ligne["lignes"] == 4
    assert "Licence Ouverte" in ligne["licence"]
    assert "2.0" in ligne["licence"]
    assert "CC BY" not in ligne["licence"]


def test_meta_n_ecrit_pas_s35_ni_s3(conn):
    ids = {
        r[0]
        for r in conn.execute("SELECT source_id FROM meta_sources").fetchall()
    }
    assert ids == {"S43"}


def test_n_ecrit_aucune_table_jorf(conn):
    noms = {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert "dole_dossiers" in noms
    assert not any(n.startswith("jorf_") for n in noms)


def test_colonnes_pas_dexpose_motif(conn):
    cols = {
        r[1]
        for r in conn.execute("PRAGMA table_info(dole_dossiers)").fetchall()
    }
    assert "expose_motif" not in cols
    assert "contenu" not in cols
    assert {"dossier_id", "titre", "type", "date_modif", "lien_legifrance"} <= cols


def test_idempotence_delete_insert(tmp_path, dossiers):
    c = db.init_db(chemin=tmp_path / "dole2.db")
    ecrire_db(c, dossiers)
    ecrire_db(c, dossiers)
    n = c.execute("SELECT count(*) FROM dole_dossiers").fetchone()[0]
    assert n == 4
    c.close()


def test_type_vide_persiste_en_base(conn):
    t = conn.execute(
        "SELECT type FROM dole_dossiers WHERE dossier_id = 'JORFDOLEFAKE000000004'"
    ).fetchone()[0]
    assert t == ""


def test_controler_ampleur_refuse_un_stock_tronque():
    with pytest.raises(ValueError, match="hors bornes"):
        controler_ampleur(12)
    with pytest.raises(ValueError, match="hors bornes"):
        controler_ampleur(50000)
    controler_ampleur(3000)  # ordre de grandeur inventé, pas le stock du jour


def test_ecrire_db_refuse_une_liste_vide(tmp_path):
    c = db.init_db(chemin=tmp_path / "vide.db")
    with pytest.raises(ValueError, match="aucun dossier"):
        ecrire_db(c, [])
    c.close()

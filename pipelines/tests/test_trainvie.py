"""Tests du pipeline P13 (frais & train de vie — faits sourcés).

Garanties éprouvées ici :
- chaque fait a une source (URL http non vide), une valeur > 0 et une
  catégorie du référentiel ; les 7 catégories du module sont toutes servies ;
- chaque opacité est complète (sujet, manque, base du refus, source) ;
- volumes minimaux (≥ 25 faits, ≥ 5 opacités) et valeurs clés du rapport 05 ;
- idempotence (rejouer ne duplique rien) et ligne meta_sources S31 ;
- test réseau (marqueur `reseau`) : 3 URLs sources officielles répondent.
"""

import pytest
import requests

from pipelines import db
from pipelines.ingest_trainvie import CATEGORIES, SOURCE_ID, ingester


@pytest.fixture()
def conn(tmp_path):
    """Base jetable initialisée + P13 ingéré, fermée en fin de test."""
    c = db.init_db(chemin=tmp_path / "test_trainvie.db")
    ingester(conn=c)
    yield c
    c.close()


# ---------------------------------------------------------------------------
# Faits
# ---------------------------------------------------------------------------


def test_chaque_fait_est_source_et_positif(conn):
    faits = conn.execute("SELECT * FROM trainvie_faits").fetchall()
    assert faits, "aucun fait ingéré"
    for f in faits:
        assert f["source_url"] and f["source_url"].startswith("http"), f["id"]
        assert f["source_nom"], f["id"]
        assert f["date_source"], f["id"]
        assert f["valeur"] > 0, f["id"]
        assert f["libelle"], f["id"]
        assert f["unite"], f["id"]
        assert f["periode"], f["id"]
        assert f["institution"], f["id"]


def test_categories_valides_et_toutes_servies(conn):
    presentes = {
        r["categorie"]
        for r in conn.execute("SELECT DISTINCT categorie FROM trainvie_faits")
    }
    assert presentes <= set(CATEGORIES)          # rien hors référentiel
    assert presentes == set(CATEGORIES)          # les 7 volets du module servis


def test_volumes_minimaux(conn):
    nb_faits = conn.execute("SELECT count(*) AS n FROM trainvie_faits").fetchone()["n"]
    nb_opacites = conn.execute(
        "SELECT count(*) AS n FROM trainvie_opacites"
    ).fetchone()["n"]
    assert nb_faits >= 25
    assert nb_opacites >= 5


def test_valeurs_cles_du_rapport_05(conn):
    """Verrou anti-doigt-qui-glisse sur les chiffres de tête du module."""
    attendu = {
        "ip-total-brut": 7637.39,           # indemnité parlementaire brute
        "dfp-metropole": 7238.04,           # DFP député métropole 2026
        "afm-senat": 6600.0,                # AFM sénateur
        "ctrl-an-total-reversements": 276335.0,
        "elysee-deplacements-cout-2024": 20100000.0,
        "lfi2026-mission-total": 1140179221.0,
        "cab-isp-total": 27361062.0,
        "local-maire-100000-plus": 5960.26,
    }
    for fait_id, valeur in attendu.items():
        ligne = conn.execute(
            "SELECT valeur FROM trainvie_faits WHERE id = ?", (fait_id,)
        ).fetchone()
        assert ligne is not None, fait_id
        assert ligne["valeur"] == pytest.approx(valeur), fait_id


# ---------------------------------------------------------------------------
# Opacités
# ---------------------------------------------------------------------------


def test_chaque_opacite_est_documentee(conn):
    opacites = conn.execute("SELECT * FROM trainvie_opacites").fetchall()
    assert opacites, "aucune opacité ingérée"
    for o in opacites:
        assert o["sujet"], o["id"]
        assert o["ce_qui_manque"], o["id"]
        assert o["base_du_refus"], o["id"]
        assert o["source_nom"], o["id"]
        assert o["source_url"] and o["source_url"].startswith("http"), o["id"]
        assert o["date"], o["id"]


def test_opacites_couvrent_les_manques_du_rapport(conn):
    ids = {r["id"] for r in conn.execute("SELECT id FROM trainvie_opacites")}
    assert {
        "justificatifs-parlementaires",
        "frais-representation-ministres",
        "remunerations-cabinets",
        "indemnites-locales-versees",
        "contraste-elus-locaux-communicables",
    } <= ids


# ---------------------------------------------------------------------------
# Idempotence et méta
# ---------------------------------------------------------------------------


def test_ingestion_idempotente(conn):
    avant = (
        conn.execute("SELECT count(*) AS n FROM trainvie_faits").fetchone()["n"],
        conn.execute("SELECT count(*) AS n FROM trainvie_opacites").fetchone()["n"],
    )
    ingester(conn=conn)  # second passage sur la même base
    apres = (
        conn.execute("SELECT count(*) AS n FROM trainvie_faits").fetchone()["n"],
        conn.execute("SELECT count(*) AS n FROM trainvie_opacites").fetchone()["n"],
    )
    assert avant == apres
    doublons = conn.execute(
        "SELECT count(*) AS n FROM (SELECT id FROM trainvie_faits "
        "GROUP BY id HAVING count(*) > 1)"
    ).fetchone()["n"]
    assert doublons == 0


def test_meta_source_s31(conn):
    meta = conn.execute(
        "SELECT * FROM meta_sources WHERE source_id = ?", (SOURCE_ID,)
    ).fetchone()
    assert meta is not None
    nb = conn.execute(
        "SELECT (SELECT count(*) FROM trainvie_faits) "
        "+ (SELECT count(*) FROM trainvie_opacites) AS n"
    ).fetchone()["n"]
    assert meta["lignes"] == nb
    assert meta["date_donnees"] == "2026-05-13"  # rapport déontologue AN, le plus récent
    assert meta["date_ingestion"]


# ---------------------------------------------------------------------------
# Réseau (sources officielles vivantes)
# ---------------------------------------------------------------------------

URLS_SENTINELLES = (
    # Une par pilier du module : barème parlementaire, frais de mandat Sénat,
    # audit Cour des comptes de l'Élysée.
    "https://www.assemblee-nationale.fr/dyn/synthese/deputes-groupes-parlementaires/"
    "la-situation-materielle-du-depute",
    "https://www.senat.fr/connaitre-le-senat/role-et-fonctionnement/"
    "les-frais-de-mandat.html",
    "https://www.ccomptes.fr/fr/publications/les-comptes-et-la-gestion-des-services-"
    "de-la-presidence-de-la-republique-exercice-2024",
)


@pytest.mark.reseau
@pytest.mark.parametrize("url", URLS_SENTINELLES)
def test_urls_sources_vivantes(url):
    try:
        r = requests.head(
            url,
            timeout=3,
            allow_redirects=False,
            headers={"User-Agent": "FranceTransparence/1.0 (projet open data personnel)"},
        )
    except (requests.ConnectionError, requests.Timeout):
        pytest.skip("réseau indisponible ou source trop lente (> 3 s)")
    assert r.status_code in (200, 301, 302), url

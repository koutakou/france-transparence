"""Tests P4/P5 (BOAMP + APProch) : parsing d'enregistrements RÉELS captés le
19/08/2026 (fixtures/annonces_reelles.json, aucune valeur modifiée) et tests
d'intégration réseau (@pytest.mark.reseau) qui vérifient que le contrat des
API tient toujours."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from pipelines import ingest_approch, ingest_boamp

FIXTURE = Path(__file__).parent / "fixtures" / "annonces_reelles.json"


@pytest.fixture(scope="module")
def reels() -> dict:
    """Enregistrements réels BOAMP (AO JOUE, AO FNS, attribution) + APProch."""
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Import / surface des modules
# ---------------------------------------------------------------------------


def test_modules_importables_et_executables():
    for module in (ingest_boamp, ingest_approch):
        assert callable(module.main)
        assert module.SOURCE_ID in ("S2", "S9")
    assert ingest_boamp.SOURCE_ID == "S2"
    assert ingest_approch.SOURCE_ID == "S9"


# ---------------------------------------------------------------------------
# BOAMP — extraction du montant (JSON `donnees`, schémas hétérogènes)
# ---------------------------------------------------------------------------


def test_extraire_montant_eforms_niveau_avis(reels):
    # 26-81222 : eForms avec montant global 168 000 € au niveau avis et
    # 0.00 au niveau lot — le montant global doit gagner, jamais le 0.
    montant, devise = ingest_boamp.extraire_montant(reels["boamp_ao_joue"]["donnees"])
    assert montant == pytest.approx(168000.0)
    assert devise == "EUR"


def test_extraire_montant_fns_valeur_estimee(reels):
    # 26-81510 : schéma FNS, valeurEstimee 220 000 €.
    montant, devise = ingest_boamp.extraire_montant(reels["boamp_ao_fns"]["donnees"])
    assert montant == pytest.approx(220000.0)
    assert devise == "EUR"


def test_extraire_montant_absent_reste_null(reels):
    # Attribution réelle sans montant estimé + entrées dégénérées :
    # jamais de montant inventé.
    assert ingest_boamp.extraire_montant(
        reels["boamp_attribution"]["donnees"]
    ) == (None, None)
    assert ingest_boamp.extraire_montant(None) == (None, None)
    assert ingest_boamp.extraire_montant("") == (None, None)
    assert ingest_boamp.extraire_montant("pas du json") == (None, None)


# ---------------------------------------------------------------------------
# BOAMP — parsing des annonces
# ---------------------------------------------------------------------------


def test_parser_ao_enregistrement_reel(reels):
    ligne = ingest_boamp.parser_ao(reels["boamp_ao_joue"])
    assert ligne is not None
    assert ligne["idweb"] == "26-81222"
    assert ligne["acheteur"] == "GHT DU CHER"
    assert ligne["objet"]
    assert ligne["nature"] == "APPEL_OFFRE"
    assert ligne["date_parution"].startswith("2026-")
    assert ligne["date_limite_reponse"] > ligne["date_parution"]
    assert ligne["montant_estime"] == pytest.approx(168000.0)
    assert ligne["url_avis"].startswith("https://www.boamp.fr/")
    # Champs multivalués stockés en JSON valide.
    assert isinstance(json.loads(ligne["type_marche"]), list)
    assert isinstance(json.loads(ligne["departements"]), list)


def test_parser_ao_sans_date_limite_est_ecarte(reels):
    tronque = dict(reels["boamp_ao_joue"], datelimitereponse=None)
    assert ingest_boamp.parser_ao(tronque) is None


def test_parser_annonce_attribution_reelle(reels):
    ligne = ingest_boamp.parser_annonce(reels["boamp_attribution"])
    assert ligne is not None
    assert ligne["nature"] == "ATTRIBUTION"
    titulaires = json.loads(ligne["titulaires"])
    assert titulaires == ["ATMOS"]
    # Une attribution n'a pas de date limite de réponse : NULL, pas inventée.
    assert ligne["date_limite_reponse"] is None


def test_indexer_liens_annulation_et_dernier_rectificatif():
    # Formes réelles constatées : annonce_lie = liste d'idweb d'origine.
    liens = [
        {"idweb": "26-1", "nature": "ANNULATION", "annonce_lie": ["26-100"],
         "dateparution": "2026-08-10"},
        {"idweb": "26-2", "nature": "RECTIFICATIF", "annonce_lie": ["26-200"],
         "dateparution": "2026-08-01"},
        {"idweb": "26-3", "nature": "RECTIFICATIF", "annonce_lie": ["26-200"],
         "dateparution": "2026-08-15"},
        {"idweb": "26-4", "nature": "RECTIFICATIF", "annonce_lie": None,
         "dateparution": "2026-08-15"},
    ]
    annules, rectifs = ingest_boamp.indexer_liens(liens)
    assert annules == {"26-100"}
    assert rectifs == {"26-200": "26-3"}  # le plus récent gagne


# ---------------------------------------------------------------------------
# APProch — parsing d'un projet réel
# ---------------------------------------------------------------------------


def test_parser_projet_reel(reels):
    ligne = ingest_approch.parser_projet(reels["approch_projet"])
    assert ligne is not None
    # L'export livre code et SIREN en entiers : re-typés/re-paddés.
    assert ligne["code"] == "64516"
    assert ligne["acheteur_siren"] == "110014016"
    assert len(ligne["acheteur_siren"]) == 9
    assert ligne["intitule"].startswith("06 – MENTON")
    assert ligne["montant_estime_tranche"] == "1M - 5M€"  # texte, pas de somme
    assert ligne["date_prev_publication"] == "2027-01-09"
    assert ligne["duree_prev_mois"] == 24
    deps = json.loads(ligne["departements"])
    assert "2A" in deps and "" not in deps
    # Champs réellement absents → NULL.
    assert ligne["type_procedure"] is None
    assert ligne["lien_consultation"] is None


def test_parser_projet_siren_reppade_et_cdl():
    rec = dict(
        code=7, date_previsionnelle_de_publication="2026-12-01",
        siren_de_l_entite_acheteuse=1401252,  # zéros de tête perdus par l'export
        montant_estime_du_marche="CDL",       # remplissage data.economie = null
    )
    ligne = ingest_approch.parser_projet(rec)
    assert ligne["acheteur_siren"] == "001401252"
    assert ligne["montant_estime_tranche"] is None


def test_parser_projet_sans_date_est_ecarte():
    assert ingest_approch.parser_projet({"code": 1}) is None


# ---------------------------------------------------------------------------
# Intégration réseau (contrat des API, appels légers)
# ---------------------------------------------------------------------------


@pytest.mark.reseau
def test_boamp_api_contrat_ao_en_cours():
    from pipelines.common import session_http

    r = session_http().get(
        "https://boamp-datadila.opendatasoft.com"
        "/api/explore/v2.1/catalog/datasets/boamp/records",
        params={
            "where": "datelimitereponse>now() AND nature='APPEL_OFFRE'",
            "select": ingest_boamp.CHAMPS_AO,
            "limit": 3,
        },
        timeout=60,
    )
    r.raise_for_status()
    corps = r.json()
    assert corps["total_count"] > 1000  # ~9 000 constatés le 19/08/2026
    maintenant = datetime.now(timezone.utc).isoformat()
    for rec in corps["results"]:
        ligne = ingest_boamp.parser_ao(rec)
        assert ligne is not None
        assert ligne["date_limite_reponse"] > maintenant


@pytest.mark.reseau
def test_approch_api_contrat_projets_futurs():
    from pipelines.common import session_http

    aujourdhui = date.today().isoformat()
    r = session_http().get(
        "https://data.economie.gouv.fr"
        "/api/explore/v2.1/catalog/datasets/projets-dachats-publics/records",
        params={
            "where": f"date_previsionnelle_de_publication>=date'{aujourdhui}'",
            "limit": 3,
        },
        timeout=60,
    )
    r.raise_for_status()
    corps = r.json()
    assert corps["total_count"] > 100  # 4 060 constatés le 19/08/2026
    for rec in corps["results"]:
        ligne = ingest_approch.parser_projet(rec)
        assert ligne is not None
        assert ligne["date_prev_publication"] >= aujourdhui


# ---------------------------------------------------------------------------
# Garde-fou sur la date limite de réponse (§ M2 de doc/QUALITE-DONNEES.md)
# ---------------------------------------------------------------------------


def test_limite_plausible_accepte_les_ecarts_reels():
    """Cas réels relevés en production : tout doit passer.

    Le 15 ans pile est le SAD paru le 03/08/2025 et ouvert jusqu'au
    01/09/2040 — un avis parfaitement légitime, qui se trouvait exactement
    sur l'ancien couperet de 15 ans. Le 18 ans garde la marge rendue par
    ECART_MAX_LIMITE_ANNEES : un SAD n'a pas de durée maximale légale, le
    prochain peut aller plus loin sans cesser d'être valable.
    """
    assert ingest_boamp._limite_plausible("2025-06-26", "2025-07-23")
    assert ingest_boamp._limite_plausible("2024-03-24", "2034-04-15")  # 10 ans
    assert ingest_boamp._limite_plausible("2025-08-03", "2040-09-01")  # 15 ans, cas réel
    assert ingest_boamp._limite_plausible("2025-08-03", "2043-09-01")  # 18 ans


def test_limite_plausible_rejette_les_millesimes_fautifs():
    """Cas réels relevés dans la base de production le 20/08/2026."""
    assert not ingest_boamp._limite_plausible("2017-06-23", "7017-07-24")
    assert not ingest_boamp._limite_plausible("2024-03-24", "2924-04-15")
    assert not ingest_boamp._limite_plausible("2025-02-28", "2099-03-02")


def test_limite_plausible_ne_rejette_pas_sur_un_format_illisible():
    """On ne rejette que sur une preuve, jamais sur une incertitude."""
    assert ingest_boamp._limite_plausible("2025-06-26", "")
    assert ingest_boamp._limite_plausible("", "2025-07-23")
    assert ingest_boamp._limite_plausible("date inconnue", "2025-07-23")


def test_parser_ao_ecarte_l_avis_a_echeance_impossible():
    rec = {
        "idweb": "17-88555",
        "dateparution": "2017-06-23",
        "datelimitereponse": "7017-07-24",
        "nomacheteur": "Mairie Saint-Cyprien",
    }
    assert ingest_boamp.parser_ao(rec) is None
    # Même avis, échéance corrigée : il est ingéré.
    rec_sain = dict(rec, datelimitereponse="2017-07-24")
    assert ingest_boamp.parser_ao(rec_sain)["idweb"] == "17-88555"

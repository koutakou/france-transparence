"""Tests du pipeline P12 (référentiels & géo) et du module sirene.

Fixtures : structures RÉELLES réduites (extraits d'appels du 19/08/2026) —
jamais de schéma inventé. Un seul test touche le réseau, marqué `reseau`.
"""

import json

import pytest

from pipelines import sirene
from pipelines.ingest_referentiels import (
    _departement_du_code,
    _slug,
    construire_geojson_departements,
    construire_villes,
    extraire_institutions,
    extraire_ministeres,
    parser_prefecture,
    valider_geojson_departements,
)

# ---------------------------------------------------------------------------
# GeoJSON (fixture réduite, mêmes propriétés que le fichier réel)
# ---------------------------------------------------------------------------


def _feature(code, nom, geometrie=None):
    return {
        "type": "Feature",
        "properties": {"code": code, "nom": nom},
        "geometry": geometrie
        or {"type": "Polygon", "coordinates": [[[4.78, 46.17], [4.9, 46.2], [4.8, 46.3], [4.78, 46.17]]]},
    }


def test_valider_geojson_ok():
    collection = {
        "type": "FeatureCollection",
        "features": [_feature("01", "Ain"), _feature("973", "Guyane")],
    }
    assert valider_geojson_departements(collection, minimum=2, maximum=5) == 2


def test_valider_geojson_rejette_les_invalides():
    with pytest.raises(ValueError):  # pas une FeatureCollection
        valider_geojson_departements({"type": "Topology"}, minimum=1, maximum=5)
    with pytest.raises(ValueError):  # feature sans propriété code
        valider_geojson_departements(
            {"type": "FeatureCollection",
             "features": [{"type": "Feature", "properties": {"nom": "Ain"},
                           "geometry": {"type": "Polygon", "coordinates": [[[0, 45]]]}}]},
            minimum=1, maximum=5,
        )
    with pytest.raises(ValueError):  # code en double
        valider_geojson_departements(
            {"type": "FeatureCollection",
             "features": [_feature("01", "Ain"), _feature("01", "Bis")]},
            minimum=1, maximum=5,
        )
    with pytest.raises(ValueError):  # hors bornes de comptage
        valider_geojson_departements(
            {"type": "FeatureCollection", "features": [_feature("01", "Ain")]},
            minimum=2, maximum=5,
        )


def test_construire_geojson_fusionne_metropole_et_drom():
    metropole = {
        "type": "FeatureCollection",
        "features": [_feature(f"{i:02d}", f"Dép {i}") for i in range(1, 97)],
    }
    etalab = {
        "type": "FeatureCollection",
        "features": [
            _feature(code, f"DROM {code}")
            for code in ("971", "972", "973", "974", "975", "976", "977")
        ],
    }
    fusion = construire_geojson_departements(metropole, etalab)
    codes = [f["properties"]["code"] for f in fusion["features"]]
    assert len(codes) == 101  # 96 métropole + 5 DROM (975/977 exclus)
    assert {"971", "972", "973", "974", "976"} <= set(codes)
    assert "975" not in codes and "977" not in codes
    assert codes == sorted(codes)
    # Propriétés normalisées à {code, nom}
    assert all(set(f["properties"]) == {"code", "nom"} for f in fusion["features"])


def test_construire_geojson_echoue_sans_drom():
    metropole = {
        "type": "FeatureCollection",
        "features": [_feature(f"{i:02d}", f"Dép {i}") for i in range(1, 97)],
    }
    with pytest.raises(ValueError):
        construire_geojson_departements(metropole, {"features": []})


# ---------------------------------------------------------------------------
# Préfectures (fiche annuaire réelle réduite — appel du 19/08/2026)
# ---------------------------------------------------------------------------

FICHE_PREFECTURE_VAUCLUSE = {
    "nom": "Préfecture - Vaucluse",
    "code_insee_commune": "84007",
    "siren": "178400016",
    "adresse": json.dumps(
        [
            {
                "type_adresse": "Adresse postale",
                "numero_voie": "2 avenue de la Folie",
                "code_postal": "84905",
                "nom_commune": "Avignon Cedex 9",
                "longitude": "",
                "latitude": "",
            },
            {
                "type_adresse": "Adresse",
                "numero_voie": "2 avenue de la Folie",
                "code_postal": "84000",
                "nom_commune": "Avignon",
                "longitude": "4.82173",
                "latitude": "43.948117",
            },
        ]
    ),
}


def test_parser_prefecture_extrait_coordonnees_et_codes():
    p = parser_prefecture(FICHE_PREFECTURE_VAUCLUSE)
    assert p is not None
    assert p["code_insee"] == "84007"
    assert p["departement"] == "84"
    assert p["nom_commune"] == "Avignon"
    assert p["lat"] == pytest.approx(43.948117)
    assert p["lon"] == pytest.approx(4.82173)
    assert p["siren"] == "178400016"


def test_parser_prefecture_sans_coordonnees_rend_none():
    fiche = dict(FICHE_PREFECTURE_VAUCLUSE)
    fiche["adresse"] = json.dumps(
        [{"type_adresse": "Adresse", "nom_commune": "X", "longitude": "", "latitude": ""}]
    )
    assert parser_prefecture(fiche) is None
    assert parser_prefecture({"code_insee_commune": "", "adresse": "[]"}) is None


def test_departement_du_code():
    assert _departement_du_code("84007") == "84"
    assert _departement_du_code("2A004") == "2A"
    assert _departement_du_code("97502") == "975"
    assert _departement_du_code("97611") == "976"


def test_parser_prefecture_ramene_l_arrondissement_a_la_commune():
    """L'annuaire localise la préfecture du Rhône dans Lyon 3e (69383) :
    la ligne doit porter le code commune COG (69123), pas l'arrondissement."""
    fiche = {
        "nom": "Préfecture - Rhône",
        "code_insee_commune": "69383",
        "siren": "176906913",
        "adresse": json.dumps(
            [{"type_adresse": "Adresse", "nom_commune": "Lyon",
              "longitude": "4.8467", "latitude": "45.7681"}]
        ),
    }
    p = parser_prefecture(fiche)
    assert p["code_insee"] == "69123"
    assert p["departement"] == "69"


def test_construire_villes_prefectures_et_seuil():
    communes = [
        {"code": "84007", "nom": "Avignon", "population": 90330,
         "codeDepartement": "84",
         "centre": {"type": "Point", "coordinates": [4.8055, 43.9425]}},
        {"code": "69123", "nom": "Lyon", "population": 519127,
         "codeDepartement": "69",
         "centre": {"type": "Point", "coordinates": [4.8351, 45.758]}},
        {"code": "04070", "nom": "Digne-les-Bains", "population": 16460,
         "codeDepartement": "04",
         "centre": {"type": "Point", "coordinates": [6.2352, 44.0937]}},
    ]
    villes = construire_villes(communes, [FICHE_PREFECTURE_VAUCLUSE], seuil=50_000)
    par_code = {v["code_insee"]: v for v in villes}
    # Lyon : grande ville non préfecture dans cette fixture (centroïde geo.api)
    assert par_code["69123"]["est_prefecture"] == 0
    assert par_code["69123"]["lat"] == pytest.approx(45.758)
    # Avignon : préfecture ET > 50 000 hab → une seule ligne, point annuaire
    assert par_code["84007"]["est_prefecture"] == 1
    assert par_code["84007"]["lat"] == pytest.approx(43.948117)
    assert par_code["84007"]["population"] == 90330
    # Digne-les-Bains : sous le seuil et pas préfecture dans la fixture
    assert "04070" not in par_code
    assert len(villes) == 2


# ---------------------------------------------------------------------------
# Entités (services RefOrgaAdminEtat réels réduits — flux du 19/08/2026)
# ---------------------------------------------------------------------------

SERVICES_REFORGA = [
    {"nom": "Ministère de l'Intérieur",
     "type_organisme": "Administration centrale (ou Ministère)",
     "siren": "", "sigle": ""},
    {"nom": "Ministère de la Culture",
     "type_organisme": "Administration centrale (ou Ministère)",
     "siren": "", "sigle": ""},
    {"nom": "Premier ministre",
     "type_organisme": "Administration centrale (ou Ministère)",
     "siren": "", "sigle": ""},
    # À EXCLURE : ministre délégué (portefeuille), bureau, cabinet
    {"nom": "Ministre délégué auprès du ministre de l'Intérieur",
     "type_organisme": "Administration centrale (ou Ministère)",
     "siren": "", "sigle": ""},
    {"nom": "Bureau de coordination stratégique",
     "type_organisme": "Administration centrale (ou Ministère)",
     "siren": "", "sigle": ""},
    {"nom": "Ministère imaginaire du mauvais type",
     "type_organisme": "Établissement public", "siren": "", "sigle": ""},
    # Institutions
    {"nom": "Présidence de la République", "type_organisme": "Institution",
     "siren": "100000017", "sigle": ""},
    {"nom": "Commission nationale des comptes de campagne et des financements"
            " politiques (CNCCFP)",
     "type_organisme": "Autorité administrative indépendante",
     "siren": "", "sigle": ""},
]


def test_extraire_ministeres_filtre_et_enrichit():
    ministeres = extraire_ministeres(SERVICES_REFORGA)
    noms = [m["nom"] for m in ministeres]
    assert "Ministère de l'Intérieur" in noms
    assert "Ministère de la Culture" in noms
    assert "Premier ministre" in noms
    assert len(ministeres) == 3  # délégués, bureaux, EP exclus
    interieur = next(m for m in ministeres if "Intérieur" in m["nom"])
    assert interieur["siren"] == "110014016"  # documenté rapport 09 §1.1


def test_extraire_institutions_liste_fixe_et_siren():
    institutions = extraire_institutions(SERVICES_REFORGA)
    assert len(institutions) == 7
    par_id = {i["id"]: i for i in institutions}
    assert par_id["inst-presidence-republique"]["siren"] == "100000017"
    assert par_id["inst-hatvp"]["sigle"] == "HATVP"
    # correspondance par préfixe : le nom RefOrga porte « (CNCCFP) » en plus
    assert par_id["inst-cnccfp"]["nom"].startswith("Commission nationale")
    # sans référentiel : la liste reste complète, SIREN simplement absents
    assert len(extraire_institutions([])) == 7


def test_slug_stable():
    assert _slug("Ministère de l'Intérieur") == "ministere-de-l-interieur"
    assert _slug("Premier ministre") == "premier-ministre"


# ---------------------------------------------------------------------------
# sirene.resolve_siret — mocké (payload réel du 19/08/2026) + 1 test réseau
# ---------------------------------------------------------------------------

REPONSE_RECHERCHE_ENTREPRISES = {
    "results": [
        {
            "siren": "110014016",
            "nom_complet": "MINISTERE DE L'INTERIEUR",
            "nom_raison_sociale": "MINISTERE DE L'INTERIEUR ",
            "nature_juridique": "7113",
            "categorie_entreprise": "GE",
            "siege": {"siret": "11001401600015", "libelle_commune": "PARIS 08"},
            "matching_etablissements": [
                {"siret": "11001401600015", "libelle_commune": "PARIS 08"}
            ],
        }
    ],
    "total_results": 1,
}


class _FausseReponse:
    def __init__(self, corps, statut=200):
        self._corps = corps
        self.status_code = statut

    def json(self):
        return self._corps

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class _FausseSession:
    def __init__(self, corps):
        self._corps = corps
        self.appels = []

    def get(self, url, params=None, timeout=None):
        self.appels.append((url, params))
        return _FausseReponse(self._corps)


def test_resolve_siret_mocke():
    session = _FausseSession(REPONSE_RECHERCHE_ENTREPRISES)
    fiche = sirene.resolve_siret("11001401600015", session=session)
    assert fiche == {
        "siret": "11001401600015",
        "siren": "110014016",
        "nom": "MINISTERE DE L'INTERIEUR",
        "categorie_juridique": "7113",
        "categorie_entreprise": "GE",
        "commune": "PARIS 08",
    }
    url, params = session.appels[0]
    assert params["q"] == "11001401600015"


def test_resolve_siret_tolere_espaces_et_rejette_l_invalide():
    session = _FausseSession(REPONSE_RECHERCHE_ENTREPRISES)
    fiche = sirene.resolve_siret("110 014 016 00015", session=session)
    assert fiche["siren"] == "110014016"
    with pytest.raises(ValueError):
        sirene.resolve_siret("123", session=session)
    with pytest.raises(ValueError):
        sirene.resolve_siret("1100140160001X", session=session)


def test_resolve_siret_inconnu_rend_none():
    session = _FausseSession({"results": [], "total_results": 0})
    assert sirene.resolve_siret("99999999999999", session=session) is None


@pytest.mark.reseau
def test_resolve_siret_reseau_reel_ministere_interieur():
    """Appel réel : SIRET du siège du ministère de l'Intérieur (rapport 09)."""
    fiche = sirene.resolve_siret("11001401600015")
    assert fiche is not None
    assert "INTERIEUR" in fiche["nom"].upper()
    assert fiche["siren"] == "110014016"
    assert fiche["commune"] and fiche["commune"].upper().startswith("PARIS")

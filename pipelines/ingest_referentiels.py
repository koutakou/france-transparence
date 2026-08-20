"""P12 — Référentiels & géo : départements, villes-points, entités, fond de carte.

Tables produites (base FT_DB_PATH sinon data/france.db) :
- ref_departements : code (PK, INSEE '01'…'976'), nom, code_region,
  nom_region, population (population municipale PMUN, référence 2023 en
  vigueur au 01/01/2026) ;
- ref_villes : code_insee (PK), nom, departement, lat, lon, population,
  est_prefecture (1 = préfecture, coordonnées du bâtiment issues de
  l'annuaire DILA ; 0 = commune > 50 000 hab., centroïde geo.api.gouv.fr) ;
- entites (table noyau, cf. pipelines/db.py) : les ministères ACTUELS
  (gouvernement Lecornu II) type 'ministere' — extraits du référentiel de
  l'organisation administrative de l'État (RefOrgaAdminEtat, DILA, flux
  quotidien), à défaut liste vérifiée du rapport 03 (décret du 26/02/2026,
  Légifrance JORFTEXT000053586369) — et 7 institutions clés type
  'institution' (Présidence, AN, Sénat, Conseil constitutionnel, HATVP,
  CNCCFP, Cour des comptes).

Fichier produit (servi au front, commité — data/geo/ n'est pas gitignoré) :
- data/geo/departements.geojson : FeatureCollection de 101 départements,
  propriétés {code, nom} — contours métropole france-geojson simplifiés
  (millésime 2018, stables) + les 5 DROM depuis les contours Etalab 2025
  (100 m). Projection recommandée côté front : d3-geo
  geoConicConformalFrance (cf. docs/recherche/09-referentiels.md §2.2).

Sources (fiches SOURCES.md) : S27 (geo.api.gouv.fr, INSEE populations de
référence 2023, france-geojson + contours Etalab), S11 (annuaire de
l'administration DILA), S35 (RefOrgaAdminEtat DILA). Licences : Licence
Ouverte 2.0 / fr-lo / mention DILA. Aucune donnée inventée : tout vient de
ces sources ; en mode secours ministères, la liste du rapport 03 est citée
dans meta_sources.notes.

Usage :
    python -m pipelines.ingest_referentiels
    FT_DB_PATH=data/tmp/test.db python -m pipelines.ingest_referentiels

Idempotent : tables référentiel en remplacement complet (DELETE + INSERT
dans une transaction), entités par type remplacées/upsertées, GeoJSON
réécrit atomiquement. Échec (réseau, validation) → exit ≠ 0, base intacte.
"""

from __future__ import annotations

import csv
import io
import json
import sys
import unicodedata
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path

import requests

from pipelines import db
from pipelines.common import DATA_DIR, obtenir_logger, session_http, telecharger

log = obtenir_logger("referentiels")

# ---------------------------------------------------------------------------
# Sources (URLs testées le 19/08/2026 — docs/recherche/09-referentiels.md
# et 07-documents-juridique.md)
# ---------------------------------------------------------------------------

URL_GEO_DEPARTEMENTS = (
    "https://geo.api.gouv.fr/departements?fields=nom,code,codeRegion,region"
)
URL_GEO_COMMUNES = (
    "https://geo.api.gouv.fr/communes"
    "?fields=nom,code,centre,population,codeDepartement"
)
URL_INSEE_POPULATIONS = (
    "https://www.insee.fr/fr/statistiques/fichier/8680726/ensemble.zip"
)
URL_FRANCE_GEOJSON_DEPARTEMENTS = (
    "https://raw.githubusercontent.com/gregoiredavid/france-geojson/master/"
    "departements-version-simplifiee.geojson"
)
# Le fichier simplifié ne couvre que la métropole (96 features) : les 5 DROM
# proviennent des contours Etalab millésimés 2025 (Licence Ouverte, 09 §2.2).
URL_ETALAB_DEPARTEMENTS_100M = (
    "https://etalab-datasets.geo.data.gouv.fr/contours-administratifs/2025/"
    "geojson/departements-100m.geojson"
)
URL_ANNUAIRE_RECORDS = (
    "https://api-lannuaire.service-public.fr/api/explore/v2.1/catalog/"
    "datasets/api-lannuaire-administration/records"
)
URL_REFORGA_LATEST = (
    "https://echanges.dila.gouv.fr/OPENDATA/RefOrgaAdminEtat/"
    "FluxAnneeCourante/dila_refOrga_admin_Etat_fr_latest.zip"
)

CHEMIN_GEOJSON = DATA_DIR / "geo" / "departements.geojson"

SEUIL_GRANDE_VILLE = 50_000
CODES_DROM = {"971", "972", "973", "974", "976"}

# SIREN institutionnels documentés par les rapports (jamais devinés) :
# - Ministère de l'Intérieur : 110014016 (09-referentiels.md §1.1, appel réel
#   recherche-entreprises du 19/08/2026) ;
# la Présidence de la République (100000017) est portée par RefOrgaAdminEtat.
SIREN_DOCUMENTES = {
    "ministere de l'interieur": "110014016",
}

# Institutions clés (id stable, nom canonique, sigle) — SIREN complété
# depuis RefOrgaAdminEtat quand le référentiel le porte.
INSTITUTIONS_CLES = [
    ("inst-presidence-republique", "Présidence de la République", None),
    ("inst-assemblee-nationale", "Assemblée nationale", None),
    ("inst-senat", "Sénat", None),
    ("inst-conseil-constitutionnel", "Conseil constitutionnel", None),
    (
        "inst-hatvp",
        "Haute Autorité pour la transparence de la vie publique",
        "HATVP",
    ),
    (
        "inst-cnccfp",
        "Commission nationale des comptes de campagne et des financements"
        " politiques",
        "CNCCFP",
    ),
    ("inst-cour-des-comptes", "Cour des comptes", None),
]

# Liste de SECOURS des ministères (uniquement si RefOrgaAdminEtat est
# indisponible/aberrant) : intitulés exacts du gouvernement Lecornu II
# vérifiés par docs/recherche/03-parlement.md §1 (décret du 26/02/2026,
# Légifrance JORFTEXT000053586369, croisé info.gouv.fr) — PAS une invention.
MINISTERES_RAPPORT_03 = [
    "Premier ministre, chargé de la Planification écologique et énergétique",
    "Ministère de l'Intérieur",
    "Ministère des Armées et des Anciens combattants",
    "Ministère du Travail et des Solidarités",
    "Ministère de la Transition écologique, de la Biodiversité et des"
    " Négociations internationales sur le climat et la nature",
    "Ministère de la Justice",
    "Ministère de l'Économie, des Finances et de la Souveraineté"
    " industrielle, énergétique et numérique",
    "Ministère des Petites et Moyennes Entreprises, du Commerce, de"
    " l'Artisanat, du Tourisme et du Pouvoir d'achat",
    "Ministère de l'Agriculture, de l'Agro-alimentaire et de la Souveraineté"
    " alimentaire",
    "Ministère de l'Éducation nationale",
    "Ministère de l'Europe et des Affaires étrangères",
    "Ministère de la Santé, des Familles, de l'Autonomie et des Personnes"
    " handicapées",
    "Ministère de la Culture",
    "Ministère des Outre-mer",
    "Ministère de l'Aménagement du territoire et de la Décentralisation",
    "Ministère de l'Action et des Comptes publics",
    "Ministère de l'Enseignement supérieur, de la Recherche et de l'Espace",
    "Ministère des Sports, de la Jeunesse et de la Vie associative",
    "Ministère des Transports",
    "Ministère de la Ville et du Logement",
]

# Zones plausibles (lat_min, lat_max, lon_min, lon_max) : métropole, DROM,
# COM (Atlantique + Pacifique) — garde-fou contre une coordonnée aberrante.
_ZONES_FRANCE = [
    (41.0, 51.5, -5.8, 10.0),      # métropole (Corse incluse)
    (13.5, 18.5, -64.0, -59.5),    # Antilles (971, 972, 977, 978)
    (2.0, 6.5, -55.5, -51.0),      # Guyane (973)
    (-21.6, -20.6, 55.0, 56.0),    # La Réunion (974)
    (-13.2, -12.4, 44.8, 45.5),    # Mayotte (976)
    (46.5, 47.3, -56.6, -56.0),    # Saint-Pierre-et-Miquelon (975)
    (-23.5, -17.0, 163.0, 168.5),  # Nouvelle-Calédonie (988)
    (-28.0, -7.0, -155.0, -134.0), # Polynésie française (987)
    (-14.5, -13.0, -178.5, -176.0),# Wallis-et-Futuna (986)
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normaliser(texte: str) -> str:
    """Minuscules sans accents, apostrophes unifiées, espaces réduits."""
    texte = unicodedata.normalize("NFD", texte or "")
    texte = "".join(c for c in texte if not unicodedata.combining(c))
    texte = texte.replace("’", "'").replace("‘", "'")
    return " ".join(texte.lower().split())


def _slug(texte: str) -> str:
    """Identifiant lisible et déterministe ('Ministère de l'X' → ministere-de-l-x)."""
    norm = _normaliser(texte)
    morceaux = []
    mot = []
    for c in norm:
        if c.isalnum():
            mot.append(c)
        elif mot:
            morceaux.append("".join(mot))
            mot = []
    if mot:
        morceaux.append("".join(mot))
    return "-".join(morceaux)


def _departement_du_code(code_insee: str) -> str:
    """Code département déduit d'un code commune ('84007'→'84', '97502'→'975')."""
    if code_insee.startswith(("97", "98")):
        return code_insee[:3]
    return code_insee[:2]


def _commune_de_rattachement(code_insee: str) -> str:
    """Commune COG pour un code d'arrondissement municipal (Paris/Lyon/
    Marseille). L'annuaire localise certaines préfectures par arrondissement
    (constaté le 19/08/2026 : Rhône → 69383, Bouches-du-Rhône → 13203) alors
    que geo.api et le front raisonnent par commune."""
    if len(code_insee) == 5 and code_insee.isdigit():
        if "75101" <= code_insee <= "75120":
            return "75056"  # Paris
        if "13201" <= code_insee <= "13216":
            return "13055"  # Marseille
        if "69381" <= code_insee <= "69389":
            return "69123"  # Lyon
    return code_insee


def _coords_en_france(lat: float, lon: float) -> bool:
    return any(
        la0 <= lat <= la1 and lo0 <= lon <= lo1
        for la0, la1, lo0, lo1 in _ZONES_FRANCE
    )


def _api_json(session: requests.Session, url: str, **kwargs) -> dict | list:
    reponse = session.get(url, timeout=120, **kwargs)
    reponse.raise_for_status()
    return reponse.json()


# ---------------------------------------------------------------------------
# 1. Départements (geo.api.gouv.fr + populations INSEE)
# ---------------------------------------------------------------------------


def recuperer_departements(session: requests.Session) -> list[dict]:
    """101 départements : code, nom, code_region, nom_region (geo.api)."""
    brut = _api_json(session, URL_GEO_DEPARTEMENTS)
    departements = []
    for d in brut:
        region = d.get("region") or {}
        departements.append(
            {
                "code": d["code"],
                "nom": d["nom"],
                "code_region": d.get("codeRegion") or region.get("code"),
                "nom_region": region.get("nom"),
            }
        )
    if len(departements) != 101:
        raise ValueError(
            f"geo.api /departements : 101 attendus, {len(departements)} reçus"
        )
    return departements


def charger_populations_departements(chemin_zip: Path) -> dict[str, int]:
    """PMUN par code département depuis le zip INSEE (donnees_departements.csv).

    Le CSV d'ensemble ne contient PAS Mayotte (976) — recensement distinct :
    complété plus loin par la somme des populations communales geo.api.
    """
    with zipfile.ZipFile(chemin_zip) as z:
        with z.open("donnees_departements.csv") as f:
            texte = io.TextIOWrapper(f, encoding="utf-8-sig")
            lignes = list(csv.DictReader(texte, delimiter=";"))
    pops = {}
    for ligne in lignes:
        dep = (ligne.get("DEP") or "").strip()
        pmun = (ligne.get("PMUN") or "")
        for espace in (" ", "\u00a0", "\u202f"):  # espaces (in)sécables, SOURCES.md §0.5
            pmun = pmun.replace(espace, "")
        if dep and pmun.isdigit():
            pops[dep] = int(pmun)
    if len(pops) < 96:
        raise ValueError(
            f"INSEE donnees_departements.csv : {len(pops)} départements lus"
            " (≥ 96 attendus)"
        )
    return pops


def completer_populations(
    departements: list[dict],
    pops_insee: dict[str, int],
    communes: list[dict],
) -> list[str]:
    """Affecte la population à chaque département ; retourne les codes
    complétés par somme communale geo.api (PMUN absent du CSV, ex. 976)."""
    par_departement: dict[str, int] = {}
    for c in communes:
        pop = c.get("population")
        if pop:
            dep = c.get("codeDepartement") or _departement_du_code(c["code"])
            par_departement[dep] = par_departement.get(dep, 0) + int(pop)

    completes = []
    for d in departements:
        pop = pops_insee.get(d["code"])
        if pop is None:
            pop = par_departement.get(d["code"])
            if pop:
                completes.append(d["code"])
        d["population"] = pop
    manquants = [d["code"] for d in departements if not d.get("population")]
    if manquants:
        raise ValueError(f"Population départementale introuvable : {manquants}")
    return completes


# ---------------------------------------------------------------------------
# 2. Fond de carte GeoJSON (france-geojson simplifié + 5 DROM Etalab 2025)
# ---------------------------------------------------------------------------


def valider_geojson_departements(
    objet: dict, minimum: int = 100, maximum: int = 110
) -> int:
    """Valide une FeatureCollection de départements ; retourne le nb de features.

    Exigences : type FeatureCollection ; chaque feature a une géométrie
    (Multi)Polygon non vide et une propriété `code` non vide, unique.
    Lève ValueError sinon (aucun fichier invalide ne doit être servi).
    """
    if not isinstance(objet, dict) or objet.get("type") != "FeatureCollection":
        raise ValueError("GeoJSON : type FeatureCollection attendu")
    features = objet.get("features")
    if not isinstance(features, list) or not features:
        raise ValueError("GeoJSON : liste de features vide")
    codes = set()
    for f in features:
        if f.get("type") != "Feature":
            raise ValueError("GeoJSON : entrée non-Feature")
        code = (f.get("properties") or {}).get("code")
        if not code:
            raise ValueError("GeoJSON : feature sans propriété 'code'")
        if code in codes:
            raise ValueError(f"GeoJSON : code département en double : {code}")
        codes.add(code)
        geometrie = f.get("geometry") or {}
        if geometrie.get("type") not in ("Polygon", "MultiPolygon"):
            raise ValueError(f"GeoJSON : géométrie invalide pour {code}")
        if not geometrie.get("coordinates"):
            raise ValueError(f"GeoJSON : géométrie vide pour {code}")
    if not (minimum <= len(features) <= maximum):
        raise ValueError(
            f"GeoJSON : {len(features)} features hors bornes"
            f" [{minimum}, {maximum}]"
        )
    return len(features)


def construire_geojson_departements(
    simplifie: dict, etalab: dict
) -> dict:
    """Fusionne métropole simplifiée (96) + DROM Etalab (5) → 101 features.

    Propriétés normalisées à {code, nom} ; features triées par code.
    """
    def _feature(code: str, nom: str, geometrie: dict) -> dict:
        return {
            "type": "Feature",
            "properties": {"code": code, "nom": nom},
            "geometry": geometrie,
        }

    par_code: dict[str, dict] = {}
    for f in etalab.get("features", []):
        props = f.get("properties") or {}
        code = props.get("code")
        if code in CODES_DROM:
            par_code[code] = _feature(code, props.get("nom"), f.get("geometry"))
    drom_manquants = CODES_DROM - set(par_code)
    if drom_manquants:
        raise ValueError(f"Contours Etalab : DROM manquants {sorted(drom_manquants)}")
    for f in simplifie.get("features", []):
        props = f.get("properties") or {}
        code = props.get("code")
        if code:
            par_code[code] = _feature(code, props.get("nom"), f.get("geometry"))
    fusion = {
        "type": "FeatureCollection",
        "features": [par_code[c] for c in sorted(par_code)],
    }
    valider_geojson_departements(fusion, minimum=100, maximum=110)
    return fusion


def ecrire_geojson(objet: dict, destination: Path = CHEMIN_GEOJSON) -> int:
    """Écrit le GeoJSON compact, atomiquement ; retourne la taille (octets)."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    contenu = json.dumps(objet, ensure_ascii=False, separators=(",", ":"))
    temporaire = destination.with_suffix(destination.suffix + ".part")
    temporaire.write_text(contenu, encoding="utf-8")
    temporaire.replace(destination)
    return destination.stat().st_size


# ---------------------------------------------------------------------------
# 3. Villes-points (préfectures annuaire DILA + communes > 50 000 hab.)
# ---------------------------------------------------------------------------


def recuperer_prefectures(session: requests.Session) -> list[dict]:
    """Fiches préfectures de l'annuaire de l'administration (~107)."""
    fiches: list[dict] = []
    decalage = 0
    while True:
        page = _api_json(
            session,
            URL_ANNUAIRE_RECORDS,
            params={
                "where": 'pivot LIKE "prefecture"',
                "select": "nom,code_insee_commune,adresse,siren",
                "limit": 100,
                "offset": decalage,
            },
        )
        resultats = page.get("results") or []
        fiches.extend(resultats)
        decalage += len(resultats)
        if not resultats or decalage >= int(page.get("total_count") or 0):
            break
    if len(fiches) < 95:
        raise ValueError(f"Annuaire : {len(fiches)} préfectures (≥ 95 attendues)")
    return fiches


def parser_prefecture(fiche: dict) -> dict | None:
    """Extrait (nom_commune, code_insee, departement, lat, lon, siren) d'une
    fiche annuaire. `adresse` est une liste sérialisée en JSON ; on prend la
    première adresse géolocalisée (type « Adresse » en priorité). Les codes
    d'arrondissement municipal sont ramenés à la commune (69383 → 69123).

    Retourne None si la fiche n'a ni code commune ni coordonnées exploitables.
    """
    code = _commune_de_rattachement((fiche.get("code_insee_commune") or "").strip())
    if not code:
        return None
    adresses = fiche.get("adresse") or "[]"
    if isinstance(adresses, str):
        try:
            adresses = json.loads(adresses)
        except json.JSONDecodeError:
            return None

    def _coords(entree: dict) -> tuple[float, float] | None:
        try:
            lat = float(entree.get("latitude") or "")
            lon = float(entree.get("longitude") or "")
        except ValueError:
            return None
        return (lat, lon)

    geolocalisees = sorted(
        (a for a in adresses if isinstance(a, dict) and _coords(a)),
        key=lambda a: 0 if a.get("type_adresse") == "Adresse" else 1,
    )
    if not geolocalisees:
        return None
    retenue = geolocalisees[0]
    lat, lon = _coords(retenue)
    return {
        "nom_annuaire": (fiche.get("nom") or "").strip(),
        "nom_commune": (retenue.get("nom_commune") or "").strip(),
        "code_insee": code,
        "departement": _departement_du_code(code),
        "lat": lat,
        "lon": lon,
        "siren": (fiche.get("siren") or "").strip() or None,
    }


def construire_villes(
    communes: list[dict],
    prefectures: list[dict],
    seuil: int = SEUIL_GRANDE_VILLE,
) -> list[dict]:
    """Lignes ref_villes : communes > seuil (centroïde geo.api) + préfectures
    (lat/lon du bâtiment, annuaire DILA). Une ligne par code INSEE ; une
    préfecture > seuil garde le point préfecture et est_prefecture = 1."""
    index_communes = {c["code"]: c for c in communes}
    lignes: dict[str, dict] = {}

    for c in communes:
        population = c.get("population")
        if not population or population <= seuil:
            continue
        centre = (c.get("centre") or {}).get("coordinates") or []
        if len(centre) != 2:
            log.warning("commune %s sans centroïde, ignorée", c.get("code"))
            continue
        lon, lat = float(centre[0]), float(centre[1])
        lignes[c["code"]] = {
            "code_insee": c["code"],
            "nom": c["nom"],
            "departement": c.get("codeDepartement")
            or _departement_du_code(c["code"]),
            "lat": lat,
            "lon": lon,
            "population": int(population),
            "est_prefecture": 0,
        }

    ecartees = 0
    for fiche in prefectures:
        p = parser_prefecture(fiche)
        if p is None:
            ecartees += 1
            log.warning(
                "préfecture sans code/coordonnées écartée : %r",
                (fiche.get("nom") or "?"),
            )
            continue
        commune = index_communes.get(p["code_insee"])
        existante = lignes.get(p["code_insee"])
        population = None
        if commune and commune.get("population"):
            population = int(commune["population"])
        elif existante:
            population = existante["population"]
        lignes[p["code_insee"]] = {
            "code_insee": p["code_insee"],
            "nom": (commune or {}).get("nom") or p["nom_commune"] or p["nom_annuaire"],
            "departement": (commune or {}).get("codeDepartement") or p["departement"],
            "lat": p["lat"],
            "lon": p["lon"],
            "population": population,
            "est_prefecture": 1,
        }
    if ecartees > 5:
        raise ValueError(f"{ecartees} fiches préfecture inexploitables (> 5)")

    aberrantes = [
        v["code_insee"]
        for v in lignes.values()
        if not _coords_en_france(v["lat"], v["lon"])
    ]
    if aberrantes:
        raise ValueError(f"Coordonnées hors zones France : {aberrantes}")
    return sorted(lignes.values(), key=lambda v: v["code_insee"])


# ---------------------------------------------------------------------------
# 4. Entités : ministères (RefOrgaAdminEtat) + institutions clés
# ---------------------------------------------------------------------------


def charger_reforga(chemin_zip: Path) -> tuple[list[dict], str]:
    """Services du référentiel RefOrgaAdminEtat + date du flux (AAAA-MM-JJ),
    lue dans le nom du fichier interne (dila_refOrga_admin_Etat_fr_YYYYMMDD)."""
    with zipfile.ZipFile(chemin_zip) as z:
        noms = [n for n in z.namelist() if n.endswith(".json")]
        if not noms:
            raise ValueError("RefOrgaAdminEtat : aucun JSON dans le zip")
        with z.open(noms[0]) as f:
            donnees = json.load(f)
    services = donnees.get("service")
    if not isinstance(services, list) or not services:
        raise ValueError("RefOrgaAdminEtat : clé 'service' absente ou vide")
    date_flux = datetime.now(timezone.utc).date().isoformat()
    tige = Path(noms[0]).stem
    horodatage = tige.rsplit("_", 1)[-1]
    if len(horodatage) == 8 and horodatage.isdigit():
        date_flux = f"{horodatage[:4]}-{horodatage[4:6]}-{horodatage[6:]}"
    return services, date_flux


def extraire_ministeres(services: list[dict]) -> list[dict]:
    """Ministères de plein exercice + Premier ministre depuis RefOrgaAdminEtat.

    Critère : type_organisme « Administration centrale (ou Ministère) » ET
    nom commençant par « Ministère  » (les « Ministre délégué… » sont des
    portefeuilles rattachés, pas des ministères) OU nom exact
    « Premier ministre ».
    """
    ministeres: dict[str, dict] = {}
    for service in services:
        if service.get("type_organisme") != "Administration centrale (ou Ministère)":
            continue
        nom = (service.get("nom") or "").strip()
        norme = _normaliser(nom)
        if not (norme.startswith("ministere ") or norme == "premier ministre"):
            continue
        siren = (service.get("siren") or "").strip() or None
        if siren is None:
            siren = SIREN_DOCUMENTES.get(norme)
        ministeres[norme] = {
            "nom": nom,
            "sigle": (service.get("sigle") or "").strip() or None,
            "siren": siren,
        }
    return sorted(ministeres.values(), key=lambda m: _normaliser(m["nom"]))


def extraire_institutions(services: list[dict]) -> list[dict]:
    """Les 7 institutions clés, enrichies (SIREN) par RefOrgaAdminEtat."""
    index = {_normaliser(s.get("nom") or ""): s for s in services}

    def _fiche(nom: str) -> dict:
        norme = _normaliser(nom)
        if norme in index:
            return index[norme]
        for cle, service in index.items():  # ex. « … (CNCCFP) » suffixé
            if cle.startswith(norme):
                return service
        return {}

    institutions = []
    for id_entite, nom, sigle in INSTITUTIONS_CLES:
        fiche = _fiche(nom)
        institutions.append(
            {
                "id": id_entite,
                "nom": nom,
                "sigle": sigle or (fiche.get("sigle") or "").strip() or None,
                "siren": (fiche.get("siren") or "").strip() or None,
            }
        )
    return institutions


# ---------------------------------------------------------------------------
# Écriture en base
# ---------------------------------------------------------------------------

_SCHEMA_REFERENTIELS = """
CREATE TABLE IF NOT EXISTS ref_departements (
    code        TEXT PRIMARY KEY,     -- code INSEE ('01'…'95', '2A', '971'…)
    nom         TEXT NOT NULL,
    code_region TEXT NOT NULL,
    nom_region  TEXT NOT NULL,
    population  INTEGER               -- PMUN, populations de référence 2023
);

CREATE TABLE IF NOT EXISTS ref_villes (
    code_insee     TEXT PRIMARY KEY,
    nom            TEXT NOT NULL,
    departement    TEXT NOT NULL,
    lat            REAL NOT NULL,
    lon            REAL NOT NULL,
    population     INTEGER,
    est_prefecture INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_ref_villes_departement ON ref_villes(departement);
"""


def ecrire_en_base(
    conn,
    departements: list[dict],
    villes: list[dict],
    ministeres: list[dict],
    institutions: list[dict],
) -> None:
    """Remplacement complet des référentiels, en une transaction."""
    conn.executescript(_SCHEMA_REFERENTIELS)
    with conn:  # transaction : tout ou rien
        conn.execute("DELETE FROM ref_departements")
        conn.executemany(
            """INSERT INTO ref_departements
               (code, nom, code_region, nom_region, population)
               VALUES (:code, :nom, :code_region, :nom_region, :population)""",
            departements,
        )
        conn.execute("DELETE FROM ref_villes")
        conn.executemany(
            """INSERT INTO ref_villes
               (code_insee, nom, departement, lat, lon, population,
                est_prefecture)
               VALUES (:code_insee, :nom, :departement, :lat, :lon,
                       :population, :est_prefecture)""",
            villes,
        )
        # Le pipeline possède le type 'ministere' : remplacement complet
        # (un remaniement change intitulés et périmètres).
        conn.execute("DELETE FROM entites WHERE type = 'ministere'")
        conn.executemany(
            """INSERT INTO entites (id, type, nom, sigle, siren)
               VALUES (:id, 'ministere', :nom, :sigle, :siren)""",
            [{**m, "id": "min-" + _slug(m["nom"])} for m in ministeres],
        )
        conn.executemany(
            """INSERT INTO entites (id, type, nom, sigle, siren)
               VALUES (:id, 'institution', :nom, :sigle, :siren)
               ON CONFLICT(id) DO UPDATE SET
                   nom = excluded.nom,
                   sigle = excluded.sigle,
                   siren = excluded.siren""",
            institutions,
        )


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


def main() -> int:
    debut = datetime.now(timezone.utc)
    session = session_http()
    aujourd_hui = date.today().isoformat()

    try:
        # ------------------------------------------------ collecte (réseau)
        departements = recuperer_departements(session)
        chemin_communes = telecharger(
            URL_GEO_COMMUNES, "geo_communes.json",
            max_age_heures=24, session=session,
        )
        communes = json.loads(chemin_communes.read_text(encoding="utf-8"))
        chemin_insee = telecharger(
            URL_INSEE_POPULATIONS, "insee_populations_reference_2023.zip",
            max_age_heures=24 * 30, session=session,  # millésime annuel
        )
        pops_insee = charger_populations_departements(chemin_insee)
        deps_completes = completer_populations(departements, pops_insee, communes)
        if deps_completes:
            log.info(
                "population par somme communale geo.api pour : %s "
                "(absents du CSV INSEE, ex. Mayotte)", deps_completes,
            )

        chemin_simplifie = telecharger(
            URL_FRANCE_GEOJSON_DEPARTEMENTS,
            "france_geojson_departements_simplifie.geojson",
            max_age_heures=24 * 7, session=session,
        )
        chemin_etalab = telecharger(
            URL_ETALAB_DEPARTEMENTS_100M,
            "etalab_departements_100m_2025.geojson",
            max_age_heures=24 * 30, session=session,
        )
        geojson = construire_geojson_departements(
            json.loads(chemin_simplifie.read_text(encoding="utf-8")),
            json.loads(chemin_etalab.read_text(encoding="utf-8")),
        )

        prefectures = recuperer_prefectures(session)
        villes = construire_villes(communes, prefectures)

        chemin_reforga = telecharger(
            URL_REFORGA_LATEST, "dila_reforga_admin_etat_latest.zip",
            max_age_heures=12, session=session,  # flux quotidien
        )
        source_ministeres = "RefOrgaAdminEtat (DILA)"
        try:
            services, date_reforga = charger_reforga(chemin_reforga)
            ministeres = extraire_ministeres(services)
            institutions = extraire_institutions(services)
            if not 12 <= len(ministeres) <= 30:
                raise ValueError(
                    f"{len(ministeres)} ministères extraits : hors plage"
                    " plausible [12, 30]"
                )
        except (ValueError, KeyError, json.JSONDecodeError, zipfile.BadZipFile) as exc:
            log.warning(
                "RefOrgaAdminEtat inexploitable (%s) → liste vérifiée du"
                " rapport 03 (décret du 26/02/2026)", exc,
            )
            source_ministeres = (
                "liste vérifiée docs/recherche/03-parlement.md"
                " (décret du 26/02/2026, Légifrance JORFTEXT000053586369)"
            )
            date_reforga = "2026-02-26"
            ministeres = [
                {"nom": nom,
                 "sigle": None,
                 "siren": SIREN_DOCUMENTES.get(_normaliser(nom))}
                for nom in MINISTERES_RAPPORT_03
            ]
            institutions = extraire_institutions([])

        # ------------------------------------------------ écritures
        octets_geojson = ecrire_geojson(geojson)
        log.info(
            "GeoJSON écrit : %s (%d features, %.0f Ko)",
            CHEMIN_GEOJSON, len(geojson["features"]), octets_geojson / 1024,
        )

        conn = db.init_db()
        try:
            ecrire_en_base(conn, departements, villes, ministeres, institutions)

            nb_prefectures = sum(v["est_prefecture"] for v in villes)
            nb_grandes = sum(
                1 for v in villes
                if (v["population"] or 0) > SEUIL_GRANDE_VILLE
            )
            db.upsert_meta(
                conn, "S27-geo-api", "geo.api.gouv.fr (départements, communes)",
                "https://geo.api.gouv.fr", "Licence Ouverte 2.0", "continue",
                date_donnees="2026-01-01", lignes=len(departements) + len(villes),
                notes="COG et populations de référence 2023 en vigueur au"
                      " 01/01/2026 ; centroïdes des communes > 50 000 hab."
                      " pour ref_villes ; population de Mayotte par somme"
                      " communale (absente du CSV INSEE).",
            )
            db.upsert_meta(
                conn, "S27-insee-populations",
                "INSEE — populations de référence 2023 (ensemble.zip)",
                URL_INSEE_POPULATIONS, "Licence Ouverte 2.0", "annuelle",
                date_donnees="2023-01-01", lignes=len(pops_insee),
                notes="PMUN par département (décret n° 2025-1362 du"
                      " 26/12/2025, en vigueur au 01/01/2026) ; Mayotte"
                      " absente du fichier d'ensemble.",
            )
            db.upsert_meta(
                conn, "S27-france-geojson",
                "Fond de carte départements (france-geojson + DROM Etalab 2025)",
                URL_FRANCE_GEOJSON_DEPARTEMENTS, "Licence Ouverte (IGN/Etalab)",
                "statique",
                date_donnees="2025-01-01", lignes=len(geojson["features"]),
                notes="Métropole : france-geojson simplifié (millésime 2018,"
                      " contours stables) ; DROM 971/972/973/974/976 :"
                      f" contours Etalab 2025 (100 m) — {octets_geojson} octets"
                      " écrits dans data/geo/departements.geojson.",
            )
            db.upsert_meta(
                conn, "S11-annuaire-administration",
                "Annuaire de l'administration (DILA) — préfectures",
                URL_ANNUAIRE_RECORDS, "Open data DILA (mention DILA)",
                "quotidienne",
                date_donnees=aujourd_hui, lignes=nb_prefectures,
                notes="Fiches pivot 'prefecture' : lat/lon du bâtiment pour"
                      " les points préfecture de ref_villes. Codes"
                      " d'arrondissement (Lyon 3e, Marseille 3e) ramenés à la"
                      " commune ; Paris n'a aucune fiche sous ce pivot"
                      " (préfecture de police à part) → Paris reste une"
                      " grande ville non marquée préfecture.",
            )
            db.upsert_meta(
                conn, "S35-reforga-admin-etat",
                "Référentiel de l'organisation administrative de l'État (DILA)",
                URL_REFORGA_LATEST, "Licence Ouverte (fr-lo)", "quotidienne",
                date_donnees=date_reforga,
                lignes=len(ministeres) + len(institutions),
                notes="Ministères du gouvernement Lecornu II (type"
                      f" 'ministere') — source : {source_ministeres} ;"
                      " institutions clés (type 'institution') enrichies"
                      " (SIREN Présidence : RefOrgaAdminEtat ; SIREN"
                      " Intérieur : rapport 09 §1.1).",
            )

            log.info(
                "OK — ref_departements: %d ; ref_villes: %d (%d préfectures,"
                " %d villes > %d hab.) ; entites: %d ministères + %d"
                " institutions ; ministères depuis : %s",
                len(departements), len(villes), nb_prefectures, nb_grandes,
                SEUIL_GRANDE_VILLE, len(ministeres), len(institutions),
                source_ministeres,
            )
        finally:
            conn.close()
    except Exception:
        log.exception("échec du pipeline référentiels")
        return 1

    log.info("durée : %.1f s", (datetime.now(timezone.utc) - debut).total_seconds())
    return 0


if __name__ == "__main__":
    sys.exit(main())

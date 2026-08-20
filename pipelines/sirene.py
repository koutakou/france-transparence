"""Résolution ponctuelle de SIRET via l'API Recherche d'entreprises (S10).

API : https://recherche-entreprises.api.gouv.fr/search?q=<SIRET>
(sans authentification, données Sirene/RNE mises à jour quotidiennement,
Licence Ouverte 2.0 — cf. docs/recherche/09-referentiels.md §1.1).

Contrainte officielle : **7 requêtes/seconde/IP maximum** (HTTP 429 au-delà).
Ce module s'auto-limite à ~6 req/s (intervalle minimal entre appels) et
réessaie avec backoff en cas de 429 résiduel.

Usage (autres pipelines) :
    from pipelines.sirene import resolve_siret
    fiche = resolve_siret("11001401600015")
    # → {"siret": "11001401600015", "siren": "110014016",
    #    "nom": "MINISTERE DE L'INTERIEUR",
    #    "categorie_juridique": "7113",      # catégorie juridique INSEE niv. 3
    #    "categorie_entreprise": "GE",       # PME / ETI / GE (peut être None)
    #    "commune": "PARIS 08"}              # commune de l'établissement
    # → None si le SIRET est inconnu de l'API.

C'est une API de *recherche*, pas d'extraction massive : PAS d'ingestion du
stock Sirene (705 Mo) ici — réservé à la résolution unitaire (trous, fiches).
"""

from __future__ import annotations

import re
import time

import requests

from pipelines.common import obtenir_logger, session_http

log = obtenir_logger("sirene")

API_URL = "https://recherche-entreprises.api.gouv.fr/search"

# 7 req/s max par IP (OpenAPI officielle) → on vise ~6 req/s.
_INTERVALLE_MIN_S = 0.16
_dernier_appel = 0.0

# Backoff local si un 429 franchit les retries de la session.
_TENTATIVES_429 = 3
_PAUSE_429_S = 2.0

_session_partagee: requests.Session | None = None


def _session() -> requests.Session:
    """Session HTTP partagée du module (retries 429/5xx via common)."""
    global _session_partagee
    if _session_partagee is None:
        _session_partagee = session_http()
    return _session_partagee


def _respecter_cadence() -> None:
    """Espace les appels d'au moins _INTERVALLE_MIN_S (limite 7 req/s)."""
    global _dernier_appel
    maintenant = time.monotonic()
    attente = _INTERVALLE_MIN_S - (maintenant - _dernier_appel)
    if attente > 0:
        time.sleep(attente)
    _dernier_appel = time.monotonic()


def _etablissement_correspondant(resultat: dict, siret: str) -> dict:
    """Retourne l'établissement du résultat qui porte exactement ce SIRET.

    Ordre de recherche : `matching_etablissements`, puis le siège ; à défaut,
    dict vide (le nom de l'unité légale reste renseigné, la commune non).
    """
    for etab in resultat.get("matching_etablissements") or []:
        if etab.get("siret") == siret:
            return etab
    siege = resultat.get("siege") or {}
    if siege.get("siret") == siret:
        return siege
    return {}


def resolve_siret(
    siret: str, session: requests.Session | None = None
) -> dict | None:
    """Résout un SIRET en (nom, catégories, commune) via recherche-entreprises.

    - `siret` : 14 chiffres (les espaces/points sont tolérés et retirés) ;
      toute autre forme lève ValueError — on ne devine jamais.
    - Respecte la limite de 7 req/s (cadence + backoff sur 429).
    - Retourne None si l'API ne connaît pas ce SIRET (résultats vides),
      sinon un dict : siret, siren, nom, categorie_juridique (code INSEE
      niveau 3, ex. '7113' = ministère), categorie_entreprise (PME/ETI/GE
      ou None), commune (libellé de la commune de l'établissement, ou None).

    Erreurs réseau/HTTP non récupérables : exception requests (au appelant
    de décider ; les pipelines doivent alors sortir avec un code ≠ 0).
    """
    siret = re.sub(r"[\s.]", "", str(siret))
    if not re.fullmatch(r"\d{14}", siret):
        raise ValueError(f"SIRET invalide (14 chiffres attendus) : {siret!r}")

    s = session or _session()
    reponse = None
    for tentative in range(1, _TENTATIVES_429 + 1):
        _respecter_cadence()
        reponse = s.get(
            API_URL,
            params={"q": siret, "per_page": 1, "page": 1},
            timeout=30,
        )
        if reponse.status_code != 429:
            break
        pause = _PAUSE_429_S * tentative
        log.warning("429 recherche-entreprises (tentative %d), pause %.1f s",
                    tentative, pause)
        time.sleep(pause)
    reponse.raise_for_status()

    resultats = (reponse.json() or {}).get("results") or []
    if not resultats:
        log.info("SIRET %s inconnu de recherche-entreprises", siret)
        return None

    unite = resultats[0]
    etab = _etablissement_correspondant(unite, siret)
    nom = (unite.get("nom_complet") or unite.get("nom_raison_sociale") or "").strip()
    if not nom:
        return None
    return {
        "siret": siret,
        "siren": unite.get("siren"),
        "nom": nom,
        "categorie_juridique": unite.get("nature_juridique"),
        "categorie_entreprise": unite.get("categorie_entreprise"),
        "commune": etab.get("libelle_commune"),
    }

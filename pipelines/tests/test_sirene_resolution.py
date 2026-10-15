"""Tests de `pipelines/sirene.py` (S10, résolution unitaire d'un SIRET).

Les tests historiques du module (réponse réelle du 19/08/2026, mockée) sont
dans test_referentiels.py ; on en réutilise la réponse et la fausse session.
Ce fichier porte la garde de cohérence SIREN/SIRET et la cadence injectable.
"""

from __future__ import annotations

import copy

from pipelines import sirene
from pipelines.tests.test_referentiels import (
    REPONSE_RECHERCHE_ENTREPRISES,
    _FausseSession,
)


def _sans_cadence() -> None:
    """Cadence neutre : une fausse session n'a pas de limite de débit."""


def test_un_resultat_d_une_autre_unite_legale_rend_none():
    """recherche-entreprises est une API de RECHERCHE : elle peut renvoyer en
    tête une unité légale qui n'est pas celle du SIRET demandé. La réponse
    réelle du ministère de l'Intérieur (SIREN 110014016), servie pour un
    SIRET d'un autre SIREN, ne doit pas être attribuée à ce SIRET : la
    docstring promet None pour un SIRET inconnu, et le code acceptait
    `results[0]` sans contrôle."""
    session = _FausseSession(REPONSE_RECHERCHE_ENTREPRISES)
    assert sirene.resolve_siret(
        "13002526500013", session=session, cadence=_sans_cadence) is None


def test_un_resultat_sans_siren_rend_none():
    reponse = copy.deepcopy(REPONSE_RECHERCHE_ENTREPRISES)
    del reponse["results"][0]["siren"]
    session = _FausseSession(reponse)
    assert sirene.resolve_siret(
        "11001401600015", session=session, cadence=_sans_cadence) is None


def test_le_bon_siren_est_toujours_resolu_et_la_cadence_est_appelee():
    appels = []
    session = _FausseSession(REPONSE_RECHERCHE_ENTREPRISES)
    fiche = sirene.resolve_siret(
        "11001401600015", session=session, cadence=lambda: appels.append(1))
    assert fiche["siren"] == "110014016"
    assert appels == [1]

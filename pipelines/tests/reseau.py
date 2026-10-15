"""Outils communs aux tests réseau (marqueur `reseau`) qui lisent un code HTTP.

Un test « source vivante » vérifie qu'une URL officielle répond. Un 503, un 429,
un 502 ou un 504 ne disent rien de tel : le serveur (ou son frontal) est
momentanément indisponible ou limite le débit, et la même page répond 200
quelques minutes plus tard. Les traiter comme une URL morte faisait échouer la
CI pour une cause amont passagère — le 15/10/2026, l'Assemblée nationale a
renvoyé 503 au runner GitHub sur une page qui répondait 200, ce qui a fait
échouer la CI de main et de deux PR. Ces tests sautaient déjà sur un délai
dépassé ; une indisponibilité temporaire est le même cas et saute de même.

Un 404, un 410, un 403 durable ou tout autre code reste un échec : c'est le
signal que le test existe pour donner.
"""

from __future__ import annotations

import pytest

# 429 Too Many Requests, 502 Bad Gateway, 503 Service Unavailable,
# 504 Gateway Timeout : indisponibilités temporaires par définition (RFC 9110
# § 15.6, RFC 6585 § 4). 500 n'en fait pas partie : c'est une erreur du
# serveur, pas un état passager annoncé.
CODES_INDISPONIBILITE_TEMPORAIRE = frozenset({429, 502, 503, 504})


def sauter_si_indisponible(reponse, url: str) -> None:
    """Saute le test (pytest.skip) si `reponse` porte un code d'indisponibilité
    temporaire ; ne fait rien sinon, l'assertion du test reste juge."""
    code = reponse.status_code
    if code in CODES_INDISPONIBILITE_TEMPORAIRE:
        pytest.skip(f"source temporairement indisponible : HTTP {code} sur {url}")

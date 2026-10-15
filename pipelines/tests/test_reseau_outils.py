"""Tests sans réseau de pipelines/tests/reseau.py et des tests « sources
vivantes » qui s'en servent : une fausse réponse remplace l'appel HTTP."""

from __future__ import annotations

import pytest

from pipelines.tests import reseau
from pipelines.tests import test_hatvp_declarations, test_trainvie


def _sans_saut(appel, *args):
    """Joue `appel` ; un pytest.skip levé dedans devient un ÉCHEC. Sans cela,
    un saut à tort serait rapporté « skipped » par pytest, pas « failed »."""
    try:
        return appel(*args)
    except pytest.skip.Exception as saut:
        pytest.fail(f"saut à tort : {saut}")


class _FausseReponse:
    def __init__(self, statut: int, entetes: dict | None = None):
        self.status_code = statut
        self.headers = entetes or {}


@pytest.mark.parametrize("code", [429, 502, 503, 504])
def test_indisponibilite_temporaire_saute_avec_le_code(code):
    with pytest.raises(pytest.skip.Exception) as saut:
        reseau.sauter_si_indisponible(_FausseReponse(code), "https://exemple.invalid/p")
    assert f"HTTP {code}" in str(saut.value)
    assert "https://exemple.invalid/p" in str(saut.value)


@pytest.mark.parametrize("code", [200, 301, 302, 403, 404, 410, 500])
def test_autres_codes_laissent_l_assertion_juger(code):
    assert _sans_saut(reseau.sauter_si_indisponible, _FausseReponse(code),
                      "https://x.invalid") is None


# --- Les tests réseau eux-mêmes, joués contre une fausse réponse -----------


def _head_fixe(statut):
    def head(*_a, **_k):
        return _FausseReponse(statut)
    return head


def test_trainvie_503_saute(monkeypatch):
    monkeypatch.setattr(test_trainvie.requests, "head", _head_fixe(503))
    with pytest.raises(pytest.skip.Exception, match="HTTP 503"):
        test_trainvie.test_urls_sources_vivantes(test_trainvie.URLS_SENTINELLES[0])


@pytest.mark.parametrize("code", [403, 404, 410])
def test_trainvie_url_morte_echoue_toujours(monkeypatch, code):
    monkeypatch.setattr(test_trainvie.requests, "head", _head_fixe(code))
    with pytest.raises(AssertionError, match="https://"):
        _sans_saut(test_trainvie.test_urls_sources_vivantes,
                   test_trainvie.URLS_SENTINELLES[0])


class _FausseSession:
    def __init__(self, statuts: dict[str, int]):
        self._statuts = statuts

    def head(self, url, **_k):
        return _FausseReponse(self._statuts[url], {"Content-Length": "60000000"})


_ANCIENNE = "https://www.hatvp.fr/livraison/opendata/declarations.xml"


def _session_hatvp(monkeypatch, actuelle: int, ancienne: int):
    import pipelines.common
    session = _FausseSession({test_hatvp_declarations.p15.URL_DECLARATIONS: actuelle,
                              _ANCIENNE: ancienne})
    monkeypatch.setattr(pipelines.common, "session_http", lambda: session)
    monkeypatch.setattr(test_hatvp_declarations.p15, "date_derniere_modification",
                        lambda *_a: "2026-10-15")


@pytest.mark.parametrize("actuelle, ancienne", [(503, 404), (200, 502)])
def test_hatvp_indisponibilite_saute(monkeypatch, actuelle, ancienne):
    _session_hatvp(monkeypatch, actuelle, ancienne)
    with pytest.raises(pytest.skip.Exception):
        test_hatvp_declarations.test_reseau_url_reelle_et_ancienne_url_morte()


@pytest.mark.parametrize("actuelle, ancienne", [(404, 404), (200, 200), (410, 404)])
def test_hatvp_ecart_durable_echoue_toujours(monkeypatch, actuelle, ancienne):
    _session_hatvp(monkeypatch, actuelle, ancienne)
    with pytest.raises(AssertionError, match="status_code|== 404|== 200"):
        _sans_saut(test_hatvp_declarations.test_reseau_url_reelle_et_ancienne_url_morte)

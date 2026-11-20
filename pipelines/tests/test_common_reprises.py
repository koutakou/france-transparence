"""Reprises de `telecharger` après une panne de transport amont."""
from __future__ import annotations

import pytest
import requests

from pipelines import common


class _Reponse:
    def __init__(self, morceaux=(b"abc",), statut=200, coupure=None):
        self.morceaux, self.status_code, self.coupure = morceaux, statut, coupure

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}", response=self)

    def iter_content(self, chunk_size):
        yield from self.morceaux
        if self.coupure:
            raise self.coupure


class _Session:
    def __init__(self, *reponses):
        self.reponses, self.appels = list(reponses), 0

    def get(self, url, **k):
        self.appels += 1
        return self.reponses.pop(0)


@pytest.fixture
def pauses(monkeypatch):
    faites = []
    monkeypatch.setattr(common, "PAUSES_REPRISE_S", (30, 120))
    monkeypatch.setattr(common.time, "sleep", faites.append)
    return faites


def test_un_flux_coupe_est_repris_et_le_fichier_est_entier(tmp_path, pauses):
    coupure = requests.exceptions.ChunkedEncodingError("IncompleteRead(3 Mo lus, 27 attendus)")
    session = _Session(_Reponse((b"deb",), coupure=coupure), _Reponse((b"tout", b"bien")))
    dest = common.telecharger("https://amont/x.zip", tmp_path / "x.zip", session=session)
    assert dest.read_bytes() == b"toutbien"
    assert session.appels == 2 and pauses == [30]
    assert not (tmp_path / "x.zip.part").exists()


@pytest.mark.parametrize("statut", [429, 500, 503])
def test_un_statut_transitoire_persistant_est_repris_deux_fois_puis_leve(tmp_path, pauses, statut):
    session = _Session(*(_Reponse(statut=statut) for _ in range(3)))
    with pytest.raises(requests.HTTPError):
        common.telecharger("https://amont/x.csv", tmp_path / "x.csv", session=session)
    assert session.appels == 3 and pauses == [30, 120]
    assert not (tmp_path / "x.csv").exists()


@pytest.mark.parametrize("panne", [
    requests.ConnectionError("Connection reset by peer"),
    requests.exceptions.ReadTimeout("read timeout=300"),
])
def test_une_connexion_coupee_puis_retablie(tmp_path, pauses, panne):
    class _Coupee(_Session):
        def get(self, url, **k):
            self.appels += 1
            if self.appels == 1:
                raise panne
            return _Reponse((b"ok",))
    session = _Coupee()
    common.telecharger("https://amont/s.parquet", tmp_path / "s.parquet", session=session)
    assert (tmp_path / "s.parquet").read_bytes() == b"ok" and pauses == [30]


@pytest.mark.parametrize("statut", [403, 404, 410, 499])
def test_un_refus_amont_n_est_jamais_repris(tmp_path, pauses, statut):
    session = _Session(_Reponse(statut=statut))
    with pytest.raises(requests.HTTPError):
        common.telecharger("https://amont/x", tmp_path / "x", session=session)
    assert session.appels == 1 and pauses == []


def test_une_erreur_de_code_n_est_jamais_reprise(tmp_path, pauses):
    session = _Session(_Reponse(coupure=ValueError("bogue")))
    with pytest.raises(ValueError):
        common.telecharger("https://amont/x", tmp_path / "x", session=session)
    assert session.appels == 1 and pauses == []

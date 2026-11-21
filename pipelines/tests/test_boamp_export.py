"""Export BOAMP illisible : retéléchargé avant d'échouer."""
from __future__ import annotations

import json

import pytest

from pipelines import common, ingest_boamp


def _faux_telecharger(tmp_path, contenus):
    appels = []

    def telecharger(url, dest, max_age_heures=None):
        chemin = tmp_path / f"export-{len(appels)}.json"
        chemin.write_text(contenus[len(appels)], encoding="utf-8")
        appels.append(url)
        return chemin
    return telecharger, appels


@pytest.fixture
def pauses(monkeypatch):
    faites = []
    monkeypatch.setattr(common, "PAUSES_REPRISE_S", (7, 11))
    monkeypatch.setattr(ingest_boamp.time, "sleep", faites.append)
    return faites


def test_un_export_mal_forme_est_retelecharge_une_fois(tmp_path, monkeypatch, pauses):
    faux, appels = _faux_telecharger(tmp_path, ['[{"a": 1} {"b"', '[{"a": 1}]'])
    monkeypatch.setattr(ingest_boamp, "telecharger", faux)
    assert ingest_boamp._exporter("w", "s", "boamp/x.json") == [{"a": 1}]
    assert len(set(appels)) == 1 and len(appels) == 2 and pauses == [7]


def test_un_export_toujours_mal_forme_leve_apres_deux_reprises(tmp_path, monkeypatch, pauses):
    faux, appels = _faux_telecharger(tmp_path, ["[{"] * 3)
    monkeypatch.setattr(ingest_boamp, "telecharger", faux)
    with pytest.raises(json.JSONDecodeError):
        ingest_boamp._exporter("w", "s", "boamp/x.json")
    assert len(set(appels)) == 1 and len(appels) == 3 and pauses == [7, 11]


def test_un_export_lisible_mais_pas_une_liste_echoue_sans_reprise(tmp_path, monkeypatch, pauses):
    faux, appels = _faux_telecharger(tmp_path, ['{"a": 1}'])
    monkeypatch.setattr(ingest_boamp, "telecharger", faux)
    with pytest.raises(RuntimeError, match="pas une liste"):
        ingest_boamp._exporter("w", "s", "boamp/x.json")
    assert len(appels) == 1 and pauses == []


def test_un_export_a_l_encodage_casse_est_retelecharge(tmp_path, monkeypatch, pauses):
    appels = []

    def telecharger(url, dest, max_age_heures=None):
        chemin = tmp_path / f"export-{len(appels)}.json"
        chemin.write_bytes(b'[{"a": "\xff"}]' if not appels else b'[{"a": 1}]')
        appels.append(url)
        return chemin
    monkeypatch.setattr(ingest_boamp, "telecharger", telecharger)
    assert ingest_boamp._exporter("w", "s", "boamp/x.json") == [{"a": 1}]
    assert len(appels) == 2 and pauses == [7]

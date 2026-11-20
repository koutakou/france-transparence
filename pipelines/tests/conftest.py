"""Configuration pytest locale aux pipelines."""


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "reseau: test d'intégration qui télécharge les sources réelles "
        "(exclure avec -m 'not reseau')",
    )


import pytest


@pytest.fixture(autouse=True)
def _reprises_de_telechargement_sans_pause(monkeypatch):
    """Les tests qui simulent une session coupée ne doivent pas attendre 2 min 30."""
    from pipelines import common
    monkeypatch.setattr(common, "PAUSES_REPRISE_S", (0, 0))

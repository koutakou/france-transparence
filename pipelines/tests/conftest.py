"""Configuration pytest locale aux pipelines."""


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "reseau: test d'intégration qui télécharge les sources réelles "
        "(exclure avec -m 'not reseau')",
    )

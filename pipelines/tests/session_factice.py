"""Session HTTP factice pour les tests de cache (aucun réseau).

Sert des réponses fixées par URL et note chaque GET, pour vérifier qu'un
téléchargement a eu lieu — ou non."""

from __future__ import annotations

import json


class _Reponse:
    def __init__(self, contenu: bytes):
        self._contenu = contenu

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def raise_for_status(self) -> None:
        pass

    def json(self):
        return json.loads(self._contenu)

    def iter_content(self, chunk_size: int = 1 << 20):
        for i in range(0, len(self._contenu), chunk_size):
            yield self._contenu[i:i + chunk_size]


class SessionFactice:
    def __init__(self, reponses: dict[str, bytes | dict]):
        self.reponses = {
            url: json.dumps(v).encode() if isinstance(v, dict) else v
            for url, v in reponses.items()
        }
        self.appels: list[str] = []

    def get(self, url, **kwargs):
        self.appels.append(url)
        return _Reponse(self.reponses[url])

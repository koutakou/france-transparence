"""Utilitaires communs à tous les pipelines d'ingestion.

Fournit :
- une session HTTP avec User-Agent projet et retries (3 tentatives, backoff) ;
- `telecharger()` : téléchargement atomique avec cache dans data/raw/ ;
- des helpers de log horodatés.

Aucune donnée fictive : ces utilitaires ne fabriquent rien, ils rapatrient.
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Racine du dépôt (= parent de pipelines/)
RACINE = Path(__file__).resolve().parent.parent
DATA_DIR = RACINE / "data"
RAW_DIR = DATA_DIR / "raw"

USER_AGENT = "FranceTransparence/1.0 (projet open data personnel)"

# ---------------------------------------------------------------------------
# Log
# ---------------------------------------------------------------------------

_FORMAT = "%(asctime)s %(levelname)-7s [%(name)s] %(message)s"


def obtenir_logger(nom: str) -> logging.Logger:
    """Logger nommé (un par pipeline), format horodaté, sortie stderr."""
    logger = logging.getLogger(nom)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter(_FORMAT, datefmt="%Y-%m-%d %H:%M:%S"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger


log = obtenir_logger("pipelines")

# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------


def session_http(total_retries: int = 3, backoff: float = 1.0) -> requests.Session:
    """Session requests avec UA projet et retries sur erreurs transitoires.

    Retries sur 429/5xx (GET/HEAD uniquement), backoff exponentiel.
    """
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    retry = Retry(
        total=total_retries,
        backoff_factor=backoff,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "HEAD"),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s


def telecharger(
    url: str,
    dest: str | Path,
    max_age_heures: float | None = None,
    session: requests.Session | None = None,
    timeout: int = 300,
) -> Path:
    """Télécharge `url` vers data/raw/`dest` (ou `dest` si chemin absolu).

    - Cache : si le fichier existe déjà et que `max_age_heures` est fourni,
      il n'est re-téléchargé que s'il est plus vieux que ce délai.
      `max_age_heures=None` force le re-téléchargement (données du jour).
    - Écriture atomique : flux vers `<dest>.part` puis rename, jamais de
      fichier tronqué en cas d'interruption.
    - Suit les redirections (302 static.data.gouv.fr, etc.).

    Retourne le chemin local du fichier.
    """
    dest = Path(dest)
    if not dest.is_absolute():
        dest = RAW_DIR / dest
    dest.parent.mkdir(parents=True, exist_ok=True)

    if dest.exists() and max_age_heures is not None:
        age_h = (time.time() - dest.stat().st_mtime) / 3600.0
        if age_h < max_age_heures:
            log.info("cache: %s (age %.1f h < %.1f h)", dest.name, age_h, max_age_heures)
            return dest

    s = session or session_http()
    log.info("téléchargement: %s", url)
    tmp = dest.with_suffix(dest.suffix + ".part")
    try:
        with s.get(url, stream=True, timeout=timeout, allow_redirects=True) as r:
            r.raise_for_status()
            octets = 0
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 20):
                    if chunk:
                        f.write(chunk)
                        octets += len(chunk)
        tmp.replace(dest)
    finally:
        tmp.unlink(missing_ok=True)
    log.info("écrit: %s (%.1f Mo)", dest, octets / 1_048_576)
    return dest

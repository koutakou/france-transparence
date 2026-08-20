"""Utilitaires communs à tous les pipelines d'ingestion.

Fournit :
- une session HTTP avec User-Agent projet et retries (3 tentatives, backoff) ;
- `telecharger()` : téléchargement atomique avec cache dans data/raw/ ;
- des helpers de log horodatés ;
- `reparer_mojibake` / `normaliser_espaces` / `assainir_texte` : hygiène des
  chaînes, partagée parce que le MÊME défaut (UTF-8 relu en cp1252) touche
  au moins quatre sources indépendantes — DECP, jaune budgétaire, comptes de
  campagne, AGORA. Une copie par pipeline aurait divergé.

Aucune donnée fictive : ces utilitaires ne fabriquent rien, ils rapatrient.
"""

from __future__ import annotations

import logging
import re
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


# ---------------------------------------------------------------------------
# Qualité des chaînes — mojibake et espaces
# ---------------------------------------------------------------------------

# Un mojibake « UTF-8 relu en cp1252 » se reconnaît à sa tête d'octet :
#   - U+00C0..U+00FF (é, à, ô, ç…) → C3 xx → « Ã » + 1 caractère ;
#   - U+0080..U+00BF (°, ©, «, µ…) → C2 xx → « Â » + 1 caractère ;
#   - U+2000..U+203F (’, –, —, …)  → E2 80 xx → « â€ » + 1 caractère.
# L'alternance est ORDONNÉE : le motif à trois caractères doit être tenté
# avant celui à deux, sinon « â€™ » ne serait jamais reconnu.
_MOJIBAKE_RE = re.compile(r"â€.|[ÃÂ].")


def reparer_mojibake(texte: str) -> str:
    """Répare le double encodage UTF-8 relu en cp1252 (« ErgÃ¼n » → « Ergün »).

    POURQUOI paire par paire, et jamais sur la chaîne entière : les sources
    mélangent, DANS LA MÊME CHAÎNE, des accents légitimement cp1252 et des
    séquences doublement encodées (« déjÃ\xa0 enregistrée »). Un
    `texte.encode('cp1252').decode('utf-8')` global échouerait sur la
    première et perdrait tout. Ici, seule une séquence dont l'aller-retour
    cp1252→UTF-8 est VALIDE est re-décodée ; tout le reste est rendu à
    l'identique. Conséquence voulue : la fonction ne perd jamais rien, et
    laisse intacts les mojibakes irréparables (« PHOTOVOLTAÃQUE », où
    l'octet 0x8F n'existe pas en cp1252, ou « Ã » suivi d'une espace
    ordinaire, l'insécable d'origine ayant déjà été normalisée en amont).

    Ce garde-fou protège aussi le texte français légitime : « BÂTIMENT »,
    « CHÂTEAU », « PLÂTRERIE » contiennent bien un « Â », mais la lettre
    qui suit est une majuscule ASCII — octet 0x41..0x5A, qui n'est pas une
    continuation UTF-8 valide — donc le décodage échoue et le mot est rendu
    tel quel. Vérifié sur les 585 503 objets DECP : aucune régression.
    """
    if "Ã" not in texte and "Â" not in texte and "â€" not in texte:
        return texte

    def _reparer(m: "re.Match[str]") -> str:
        sequence = m.group(0)
        try:
            return sequence.encode("cp1252").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            return sequence

    return _MOJIBAKE_RE.sub(_reparer, texte)


def normaliser_espaces(texte: str) -> str:
    """Insécables (U+00A0/U+202F), retours ligne et espaces multiples → une
    espace simple ; bords rognés.

    POURQUOI : les exports Chorus, BOAMP et DECP transportent des insécables
    et des espaces de bord invisibles à l'écran mais qui cassent les tris,
    les GROUP BY et les recherches plein texte (« CROIX ROUGE » ≠ « CROIX
    ROUGE » si l'un porte U+00A0). Le CONTENU n'est jamais modifié.
    """
    return re.sub(r"\s+", " ", texte.replace(" ", " ").replace(" ", " ")).strip()


def assainir_texte(valeur: str | None) -> str | None:
    """`reparer_mojibake` + `normaliser_espaces`, tolérant au None/non-str.

    Retourne None sur une chaîne vide après nettoyage : une chaîne vide est
    une absence de valeur, pas une valeur.
    """
    if not isinstance(valeur, str):
        return valeur
    propre = normaliser_espaces(reparer_mojibake(valeur))
    return propre or None

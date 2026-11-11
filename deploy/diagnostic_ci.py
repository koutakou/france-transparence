"""Dire POURQUOI un run de validation est tombé, à partir du journal du job.

Du 22/10 au 11/11/2026, vingt et un cycles planifiés ont échoué d'affilée et
l'issue d'échec a reçu vingt commentaires identiques. Huit de ces runs
étaient pourtant tombés pour une AUTRE raison que les treize autres (cinq
pipelines différents, quatre serveurs amont) : rien ne distinguait « même
panne » de « nouvelle panne ».

Ce module lit le journal brut d'un job GitHub Actions (celui que rend
`GET /repos/{depot}/actions/jobs/{id}/logs`) et en tire trois choses :

- la CIBLE `make` tombée (`ingest-parlement`, `test`…), lue dans la ligne
  `make: *** [Makefile:N: cible]` ;
- la PREMIÈRE ligne d'erreur de l'étape tombée — souvent la cause ;
- la DERNIÈRE — souvent l'exception qui a traversé.

Il ne devine rien : un champ qu'il ne trouve pas reste vide, et l'appelant
l'écrit comme tel. Le NOM de l'étape n'est pas dans le journal ; l'appelant
le lit dans l'API des jobs.

Usage : python3 deploy/diagnostic_ci.py JOURNAL  → un objet JSON sur stdout.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# Une ligne recopiée dans un commentaire d'issue : assez pour nommer la
# panne, pas assez pour y verser une trace entière.
LONGUEUR_MAX = 300

_HORODATAGE = re.compile(r"^\ufeff?\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?Z ?")
_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_DEBUT_ETAPE = "##[group]Run "
_ANNOTATION_ERREUR = "##[error]"
_CIBLE = re.compile(r"^make(?:\[\d+\])?: \*\*\* \[[^\]:]*:\d+: ([A-Za-z0-9_.-]+)\]")
# Ce qui compte comme « ligne d'erreur » : le niveau ERROR du journal des
# pipelines, le verdict et le détail de pytest, une exception Python nommée,
# une annotation d'erreur du runner.
_ERREUR = re.compile(
    r"\bERROR\b|^FAILED |^E {2,}\S|\b\w*(?:Error|Exception): \S|ÉCHEC|^##\[error\]"
)
# Lignes d'erreur qui ne disent rien de la cause : elles closent toute étape
# en échec, quelle que soit la panne.
_GENERIQUE = re.compile(
    r"^##\[error\]Process completed with exit code|^make(?:\[\d+\])?: \*\*\*"
)


def _nettoyer(ligne: str) -> str:
    """Retire l'horodatage du runner, la marque d'ordre d'octets et les couleurs."""
    return _ANSI.sub("", _HORODATAGE.sub("", ligne.rstrip("\r\n")))


def _citer(ligne: str) -> str:
    """Rend une ligne citable dans un bloc de code Markdown, bornée."""
    texte = " ".join(ligne.replace("`", "'").split())
    if texte.startswith(_ANNOTATION_ERREUR):
        texte = texte[len(_ANNOTATION_ERREUR):]
    if len(texte) > LONGUEUR_MAX:
        texte = texte[: LONGUEUR_MAX - 1] + "…"
    return texte


def etape_en_echec(lignes: list[str]) -> list[str]:
    """Les lignes de la première étape tombée, de son `Run` à sa dernière erreur.

    Les étapes qui suivent un échec sont sautées : la première annotation
    d'erreur du journal appartient donc à l'étape fautive. Sans annotation
    (job interrompu, journal tronqué), la liste est vide.
    """
    premiere = next(
        (i for i, l in enumerate(lignes) if l.startswith(_ANNOTATION_ERREUR)), None
    )
    if premiere is None:
        return []
    debut = max(
        (i for i in range(premiere) if lignes[i].startswith(_DEBUT_ETAPE)), default=0
    )
    fin = premiere
    for i in range(premiere + 1, len(lignes)):
        if lignes[i].startswith(_DEBUT_ETAPE):
            break
        if lignes[i].startswith(_ANNOTATION_ERREUR):
            fin = i
    return lignes[debut : fin + 1]


def diagnostiquer(journal: str) -> dict[str, str]:
    """Cible `make`, première et dernière ligne d'erreur de l'étape tombée."""
    etape = etape_en_echec([_nettoyer(l) for l in journal.splitlines()])
    cible = ""
    for ligne in etape:
        trouve = _CIBLE.match(ligne)
        if trouve:
            cible = trouve.group(1)
    erreurs = [l for l in etape if _ERREUR.search(l) and not _GENERIQUE.search(l)]
    if not erreurs:
        # Aucune ligne reconnue : la dernière ligne écrite avant l'échec vaut
        # mieux que rien, et elle est donnée pour ce qu'elle est.
        utiles = [l for l in etape[1:] if l.strip() and not _GENERIQUE.search(l)
                  and not l.startswith("##[")]
        erreurs = utiles[-1:]
    return {
        "cible": cible,
        "premiere": _citer(erreurs[0]) if erreurs else "",
        "derniere": _citer(erreurs[-1]) if erreurs else "",
    }


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__.strip().splitlines()[-1], file=sys.stderr)
        return 2
    journal = Path(argv[1]).read_text(encoding="utf-8", errors="replace")
    print(json.dumps(diagnostiquer(journal), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

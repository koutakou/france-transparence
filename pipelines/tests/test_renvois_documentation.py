"""Hygiène : tout document `.md` cité dans le code des pipelines existe.

POURQUOI : douze renvois à `doc/QUALITE-DONNEES.md` (§ M2 à M8) ont vécu
dans le code et les tests depuis le premier commit public (20/08/2026), sans
que ce fichier ait jamais existé dans le dépôt ni dans son historique
(`git log --all -- '*QUALITE-DONNEES*'` est vide, mesuré le 15/10/2026). Un
lecteur qui suivait le renvoi ne trouvait rien.

Règle : un chemin cité (`docs/SOURCES.md`, `doc/X.md`) doit exister depuis
la racine du dépôt ; un nom nu (`SOURCES.md`, `05-frais-indemnites.md`) doit
désigner au moins un document de ce nom, à la racine ou sous `docs/`.

Un document tenu HORS du dépôt (la documentation d'exploitation du
serveur) se cite par son chemin absolu sur le serveur, et seulement s'il est
nommé dans `DOCUMENTS_HORS_DEPOT` : un lecteur sait alors qu'il ne le
trouvera pas dans l'arbre, au lieu de chercher un fichier absent.

La liste des renvois cassés tolérés, ouverte par l'introduction de ce test,
est vide depuis le 15/10/2026 : tout renvoi cassé fait échouer le test.
"""

from __future__ import annotations

import re
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
PIPELINES = RACINE / "pipelines"

_RENVOI_RE = re.compile(r"[A-Za-z0-9_./-]*[A-Za-z0-9_-]+\.md\b")

# Documents cités par le code mais tenus hors du dépôt, sur le serveur
# (docs/deploiement/RUNBOOK.md : « la doc du serveur fait foi »).
DOCUMENTS_HORS_DEPOT = {
    "/srv/france-transparence/doc/EXPLOITATION.md",
}


def _noms_documents() -> set[str]:
    """Noms des documents `.md` du dépôt : racine et `docs/` (récursif)."""
    return ({p.name for p in RACINE.glob("*.md")}
            | {p.name for p in (RACINE / "docs").rglob("*.md")})


def renvois_casses_dans(texte: str, noms: set[str]) -> set[str]:
    """Renvois `.md` de `texte` qui ne désignent aucun document connu."""
    casses = set()
    for renvoi in set(_RENVOI_RE.findall(texte)):
        if renvoi in DOCUMENTS_HORS_DEPOT:
            continue
        existe = ((RACINE / renvoi).is_file() if "/" in renvoi
                  else renvoi in noms)
        if not existe:
            casses.add(renvoi)
    return casses


def renvois_casses() -> set[tuple[str, str]]:
    noms = _noms_documents()
    casses = set()
    for fichier in sorted(PIPELINES.rglob("*.py")):
        if fichier == Path(__file__).resolve():
            continue  # ce fichier cite des renvois cassés en exemple
        texte = fichier.read_text(encoding="utf-8")
        for renvoi in renvois_casses_dans(texte, noms):
            casses.add((str(fichier.relative_to(RACINE)), renvoi))
    return casses


def test_aucun_renvoi_vers_un_document_inexistant():
    casses = renvois_casses()
    assert not casses, sorted(casses)


def test_l_instrument_voit_un_renvoi_casse():
    """Contre-épreuve : l'instrument n'est pas muet. Il voit les renvois
    cassés qu'a portés le dépôt (chemin `doc/` sans « s », nom nu d'un
    document inexistant, document du serveur cité sans son chemin) et
    laisse passer les renvois justes."""
    noms = _noms_documents()
    assert renvois_casses_dans(
        "§ M5 de doc/QUALITE-DONNEES.md", noms) == {"doc/QUALITE-DONNEES.md"}
    assert renvois_casses_dans(
        "(§ M7 QUALITE-DONNEES.md)", noms) == {"QUALITE-DONNEES.md"}
    assert renvois_casses_dans(
        "EXPLOITATION.md § 9.6", noms) == {"EXPLOITATION.md"}
    assert renvois_casses_dans("(task/SOURCES.md)", noms) == {"task/SOURCES.md"}
    assert not renvois_casses_dans(
        "docs/SCHEMA-DB.md, SOURCES.md, 05-frais-indemnites.md, "
        "/srv/france-transparence/doc/EXPLOITATION.md", noms)
    assert (RACINE / "docs" / "SOURCES.md").is_file()
    assert not (RACINE / "doc").exists()

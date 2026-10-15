"""Hygiène : tout document `.md` cité dans le code des pipelines existe.

POURQUOI : douze renvois à `doc/QUALITE-DONNEES.md` (§ M2 à M8) ont vécu
dans le code et les tests depuis le premier commit public (20/08/2026), sans
que ce fichier ait jamais existé dans le dépôt ni dans son historique
(`git log --all -- '*QUALITE-DONNEES*'` est vide, mesuré le 15/10/2026). Un
lecteur qui suivait le renvoi ne trouvait rien.

Règle : un chemin cité (`docs/SOURCES.md`, `doc/X.md`) doit exister depuis
la racine du dépôt ; un nom nu (`SOURCES.md`, `05-frais-indemnites.md`) doit
désigner au moins un document de ce nom, à la racine ou sous `docs/`.

Les renvois cassés qui restent vivent dans des fichiers que cette
proposition ne touche pas ; ils sont NOMMÉS ci-dessous, un par un, et le
test refuse tout renvoi cassé qui n'y figure pas. Une entrée se retire de
la liste dès que son renvoi est corrigé.
"""

from __future__ import annotations

import re
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
PIPELINES = RACINE / "pipelines"

_RENVOI_RE = re.compile(r"[A-Za-z0-9_./-]*[A-Za-z0-9_-]+\.md\b")

# (fichier relatif à la racine, renvoi tel qu'écrit) — à corriger dans le lot
# qui possède le fichier, puis à retirer d'ici.
RENVOIS_CASSES_CONNUS = {
    ("pipelines/ingest_decp.py", "QUALITE-DONNEES.md"),
    ("pipelines/ingest_financement.py", "QUALITE-DONNEES.md"),
    ("pipelines/ingest_financement.py", "doc/QUALITE-DONNEES.md"),
    ("pipelines/ingest_integrite.py", "EXPLOITATION.md"),
    ("pipelines/ingest_parlement.py", "task/SOURCES.md"),
    ("pipelines/tests/test_annonces.py", "doc/QUALITE-DONNEES.md"),
    ("pipelines/tests/test_decp.py", "doc/QUALITE-DONNEES.md"),
    ("pipelines/tests/test_financement.py", "QUALITE-DONNEES.md"),
    ("pipelines/tests/test_financement.py", "doc/QUALITE-DONNEES.md"),
    ("pipelines/tests/test_integrite.py", "doc/QUALITE-DONNEES.md"),
}


def _noms_documents() -> set[str]:
    """Noms des documents `.md` du dépôt : racine et `docs/` (récursif)."""
    return ({p.name for p in RACINE.glob("*.md")}
            | {p.name for p in (RACINE / "docs").rglob("*.md")})


def renvois_casses() -> set[tuple[str, str]]:
    noms = _noms_documents()
    casses = set()
    for fichier in sorted(PIPELINES.rglob("*.py")):
        if fichier == Path(__file__).resolve():
            continue  # ce fichier cite des renvois cassés en exemple
        texte = fichier.read_text(encoding="utf-8")
        for renvoi in set(_RENVOI_RE.findall(texte)):
            existe = ((RACINE / renvoi).is_file() if "/" in renvoi
                      else renvoi in noms)
            if not existe:
                casses.add((str(fichier.relative_to(RACINE)), renvoi))
    return casses


def test_aucun_nouveau_renvoi_vers_un_document_inexistant():
    nouveaux = renvois_casses() - RENVOIS_CASSES_CONNUS
    assert not nouveaux, sorted(nouveaux)


def test_l_instrument_voit_un_renvoi_casse():
    """Contre-épreuve : l'instrument n'est pas muet (il voit les renvois
    cassés connus qui restent, et le chemin `doc/` sans « s »)."""
    casses = renvois_casses()
    assert casses, "aucun renvoi cassé vu : l'instrument est-il débranché ?"
    assert all(r.endswith(".md") for _, r in casses)
    assert (RACINE / "docs" / "SOURCES.md").is_file()
    assert not (RACINE / "doc").exists()

"""La documentation vivante ne doit pas contredire la liste des pipelines.

La variable `PIPELINES` du `Makefile` fait autorité. Le README en recopiait
une liste, annoncée « 24 cibles », restée telle quand la variable est passée
à 31 noms (constaté le 15/10/2026) : sept pipelines étaient absents de la
seule liste qu'un nouveau contributeur lit. La copie est retirée (le README
renvoie à `make pipelines`) ; ce test empêche qu'un compte écrit en dur dans
les documents qui décrivent l'état COURANT redevienne faux.

Les comptes rendus datés (JOURNAL, RAPPORT-MISSION, révisions successives de
SOURCES.md, audits) ne sont pas lus : leurs nombres sont vrais à leur date,
et la règle du dépôt est de ne jamais les réécrire.

Hors réseau, sans base : ne lit que des fichiers du dépôt.
"""

from __future__ import annotations

import re
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]

# Documents qui décrivent l'état courant et citent le nombre de pipelines.
DOCUMENTS_VIVANTS = (
    "README.md",
    "CONTRIBUTING.md",
    "docs/ARCHITECTURE.md",
    "docs/deploiement/RUNBOOK.md",
    "docs/deploiement/DECISION.md",
)

# « 31 pipelines », « les 31 pipelines », « (24 cibles » : un nombre suivi
# immédiatement de « pipelines » ou « cibles ». « les 21 pipelines en aval »
# désigne une partie de la chaîne, pas sa taille : écarté explicitement.
MOTIF_COMPTE = re.compile(r"\b(\d+)\s+(pipelines|cibles)\b(?!\s+en\s+aval)")


def lire_pipelines_makefile() -> list[str]:
    """Noms de la variable PIPELINES, dans l'ordre, continuations comprises."""
    texte = (RACINE / "Makefile").read_text(encoding="utf-8")
    m = re.search(r"^PIPELINES\s*:=\s*((?:.*\\\n)*.*)$", texte, re.MULTILINE)
    assert m, "variable PIPELINES introuvable dans le Makefile"
    return m.group(1).replace("\\\n", " ").split()


def comptes_annonces(texte: str) -> list[tuple[int, str]]:
    return [(int(n), mot) for n, mot in MOTIF_COMPTE.findall(texte)]


def test_chaque_pipeline_a_son_module_et_reciproquement():
    noms = lire_pipelines_makefile()
    modules = {p.stem.removeprefix("ingest_") for p in (RACINE / "pipelines").glob("ingest_*.py")}
    assert len(noms) == len(set(noms)), "un pipeline est déclaré deux fois"
    assert set(noms) == modules


def test_les_documents_vivants_n_annoncent_que_le_vrai_nombre_de_pipelines():
    attendu = len(lire_pipelines_makefile())
    faux = []
    for chemin in DOCUMENTS_VIVANTS:
        texte = (RACINE / chemin).read_text(encoding="utf-8")
        for n, mot in comptes_annonces(texte):
            if n != attendu:
                faux.append(f"{chemin} : « {n} {mot} » (PIPELINES en compte {attendu})")
    assert not faux, "\n".join(faux)


def test_le_motif_reconnait_les_formes_reelles_du_depot():
    # Formes relevées dans le dépôt le 15/10/2026 (README avant correctif,
    # ARCHITECTURE, RUNBOOK) : le test documentaire ne vaut que s'il les voit.
    assert comptes_annonces("qui fait autorité (24 cibles, dans cet ordre)") == [(24, "cibles")]
    assert comptes_annonces("État courant : **31 pipelines**, **44 sources**") == [(31, "pipelines")]
    assert comptes_annonces("`ft-deploy` complet, qui rejoue les 31 pipelines.") == [(31, "pipelines")]
    assert comptes_annonces("une levée arrête les 21 pipelines en aval") == []

"""Une version publiée en amont ne doit pas entrer dans la chaîne sans passer par une PR.

`requirements.txt` portait des bornes basses (`duckdb>=1.3`) : chaque venv
neuve installait la dernière version publiée. DuckDB 2.0 (21/10/2026) a retiré
`fetchone()` des relations ; la CI, qui reconstruit sa venv à chaque run, l'a
installé d'elle-même, et chaque cycle de `main` a échoué à partir du 22/10
sans qu'une ligne du dépôt ait changé. Le même fichier aurait installé une
autre version sur un serveur en Python 3.10, où DuckDB 2 n'a pas de roue : la
CI et la production ne testaient plus le même logiciel.

Ces tests verrouillent trois choses :
1. chaque ligne de `requirements.txt` est figée à une version exacte (`==`) ;
2. le fichier est fermé : toute dépendance d'un paquet installé y figure
   (sinon une montée Dependabot qui introduit un paquet le laisserait flotter) ;
3. la venv qui joue les tests est celle que décrit le fichier : ce qui est
   testé est ce qui est figé.

Hors réseau, sans base : lit le fichier du dépôt et les métadonnées de la venv.
"""

from __future__ import annotations

from importlib import metadata
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

FICHIER = Path(__file__).resolve().parents[2] / "requirements.txt"


def lire_exigences(texte: str) -> list[Requirement]:
    """Une `Requirement` par ligne utile (commentaires et lignes vides ignorés)."""
    exigences = []
    for ligne in texte.splitlines():
        ligne = ligne.split("#", 1)[0].strip()
        if ligne:
            exigences.append(Requirement(ligne))
    return exigences


def version_figee(exigence: Requirement) -> str | None:
    """La version exacte si l'exigence est `nom==x.y.z`, sinon None."""
    specs = list(exigence.specifier)
    if len(specs) == 1 and specs[0].operator == "==" and "*" not in specs[0].version:
        return specs[0].version
    return None


def applicables(exigences: list[Requirement]) -> list[Requirement]:
    """Les exigences dont le marqueur vaut pour l'interpréteur courant."""
    return [e for e in exigences if e.marker is None or e.marker.evaluate()]


EXIGENCES = lire_exigences(FICHIER.read_text(encoding="utf-8"))


def test_chaque_dependance_est_figee_a_une_version_exacte():
    non_figees = [str(e) for e in EXIGENCES if version_figee(e) is None]
    assert EXIGENCES, "requirements.txt ne déclare aucune dépendance"
    assert non_figees == [], (
        f"dépendances non figées (attendu `nom==version`) : {non_figees}"
    )


def test_le_controle_refuse_les_formes_qui_flottent():
    # Contre-épreuve sur l'ANCIEN contenu réel du fichier (jusqu'au 11/11/2026)
    # et sur les autres formes qui laissent pip choisir.
    for ligne in ("duckdb>=1.3", "requests>=2.32", "pytest>=8.3", "duckdb",
                  "duckdb==1.*", "duckdb~=1.5", "duckdb>=1.5,<2", "duckdb!=2.0.0"):
        assert version_figee(Requirement(ligne)) is None, ligne
    assert version_figee(Requirement("duckdb==1.5.6")) == "1.5.6"
    assert version_figee(Requirement('tomli==2.5.0 ; python_version < "3.11"')) == "2.5.0"


def test_le_fichier_ne_declare_chaque_paquet_qu_une_fois():
    noms = [canonicalize_name(e.name) for e in EXIGENCES]
    assert len(noms) == len(set(noms)), sorted(n for n in noms if noms.count(n) > 1)


def test_toute_dependance_transitive_installee_est_figee():
    figes = {canonicalize_name(e.name) for e in EXIGENCES}
    manquantes = set()
    for exigence in applicables(EXIGENCES):
        try:
            requises = metadata.requires(exigence.name) or []
        except metadata.PackageNotFoundError:
            continue  # paquet absent : c'est le test de la venv qui le signale
        for brute in requises:
            dependance = Requirement(brute)
            # Les dépendances d'une option (`extra == "socks"`) ne sont pas
            # installées : le marqueur est évalué sans option.
            if dependance.marker is not None and not dependance.marker.evaluate({"extra": ""}):
                continue
            if canonicalize_name(dependance.name) not in figes:
                manquantes.add(f"{dependance.name} (requise par {exigence.name})")
    assert manquantes == set(), (
        f"dépendances installées mais absentes de requirements.txt : {sorted(manquantes)}"
    )


def test_la_venv_des_tests_est_celle_que_decrit_le_fichier():
    ecarts = []
    for exigence in applicables(EXIGENCES):
        attendue = version_figee(exigence)
        try:
            installee = metadata.version(exigence.name)
        except metadata.PackageNotFoundError:
            installee = None
        if installee != attendue:
            ecarts.append(f"{exigence.name} : figée {attendue}, installée {installee}")
    assert ecarts == [], (
        "la venv ne correspond pas à requirements.txt (refaire `make venv`) : "
        + " ; ".join(ecarts)
    )

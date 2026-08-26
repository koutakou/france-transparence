"""La table de correspondance des fiches fusionnées, et ce qu'on en engendre.

Cette table (`deploy/redirections-elus.tsv`) est la SOURCE DE VÉRITÉ d'une
règle nginx qui vit hors du dépôt, dans `/etc/nginx/snippets/`. Une faute de
frappe n'y serait vue par personne : le générateur ne valide rien de sémantique,
`nginx -t` accepterait volontiers une redirection vers une fiche inexistante, et
le défaut ne se manifesterait que par un 301 vers un 404, sur des URL dont
l'audience humaine mesurée est nulle. D'où ces contrôles.

Ils ne vérifient PAS que les identifiants existent en base : la table est
mesurée sur l'état de `elus` du jour, pas sur celui de l'intégration continue,
dont la base naît neuve. Voir `docs/REDIRECTIONS-ELUS.md`.
"""

import re
import subprocess
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]
TABLE = RACINE / "deploy" / "redirections-elus.tsv"
GENERATEUR = RACINE / "deploy" / "gen-redirections-elus.sh"


def lignes_utiles():
    for brute in TABLE.read_text(encoding="utf-8").splitlines():
        if not brute.strip() or brute.lstrip().startswith("#"):
            continue
        yield brute


@pytest.fixture(scope="module")
def couples():
    return [ligne.split("\t") for ligne in lignes_utiles()]


def test_la_table_est_bien_formee(couples):
    assert couples, "table vide : la règle nginx serait engendrée sans contenu"
    for champs in couples:
        assert len(champs) == 3, f"3 colonnes attendues, {len(champs)} : {champs}"
        retire, conserve, personne = champs
        assert re.fullmatch(r"rne-[0-9a-f]{16}", retire), retire
        assert personne.strip(), f"{retire} sans libellé de personne"


def test_on_ne_redirige_jamais_vers_une_fiche_rne(couples):
    """La cible est toujours une fiche de l'Assemblée ou du Sénat.

    Rediriger vers une autre fiche `rne-*` serait poser une chaîne de
    redirections dont le maillon suivant est lui-même candidat à la
    suppression : le 301 finirait en 404 au cycle d'après.
    """
    for retire, conserve, _ in couples:
        assert re.fullmatch(r"(PA\d+|SEN-[0-9A-Za-z]+)", conserve), \
            f"{retire} -> {conserve} : cible qui n'est ni AN ni Sénat"


def test_aucun_identifiant_retire_deux_fois_ni_cible_de_lui_meme(couples):
    """Un doublon dans la colonne de gauche engendrerait deux `location =`
    identiques — nginx refuserait la configuration entière au rechargement."""
    retires = [c[0] for c in couples]
    assert len(retires) == len(set(retires)), \
        f"identifiants en double : {sorted({i for i in retires if retires.count(i) > 1})}"
    cibles = {c[1] for c in couples}
    assert not (set(retires) & cibles), "une fiche est à la fois retirée et cible"


def test_le_generateur_rend_deux_blocs_par_fiche(couples):
    """Les deux formes sont NÉCESSAIRES, et le suffixe doit être préservé.

    Le préfixe `^~ …/` couvre la page et les charges RSC du routeur Next ;
    l'exact `= …` couvre la forme sans barre finale, qui retomberait sinon sur
    la canonicalisation générique du vhost et rendrait 404 dès que le
    répertoire a disparu. Le `$1` du `rewrite` est ce qui empêche une charge
    RSC de recevoir du HTML.
    """
    rendu = subprocess.run([str(GENERATEUR)], capture_output=True, text=True,
                           check=True).stdout
    for retire, conserve, _ in couples:
        assert f"location ^~ /elus/{retire}/ {{" in rendu
        assert (f"rewrite ^/elus/{retire}/(.*)$ "
                f"https://francetransparence.fr/elus/{conserve}/$1 permanent;") in rendu
        # `$is_args$args` : `return 301` ne reporte pas la chaîne de requête,
        # là où `rewrite` la conserve. Sans lui, `/elus/<id>?_rsc=…` — une
        # charge RSC — atterrirait sur la page HTML de la jumelle.
        assert (f"location = /elus/{retire} {{ return 301 "
                f"https://francetransparence.fr/elus/{conserve}/$is_args$args; }}") in rendu
    assert rendu.count("location ") == 2 * len(couples)

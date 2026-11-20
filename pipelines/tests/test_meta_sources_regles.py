"""Règles de structure des lignes `meta_sources` écrites par les pipelines.

Audit du 20/11/2026 :
- C5 : la date de donnée est celle de la donnée la plus récente, jamais la
  date du jour (db.upsert_meta, SOURCES.md §0.2). S11 écrivait la date du
  jour à chaque cycle, S14 y retombait sans en-tête Last-Modified ;
- C6 : 12 libellés pour 2 licences sur /api/meta.json.

Tests de structure (AST) : ils lisent le code des pipelines sans l'exécuter.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from pipelines import common

RACINE_PIPELINES = Path(__file__).resolve().parents[1]
MODULES = sorted(RACINE_PIPELINES.glob("*.py"))

# (fichier, fonction) → motif. Chaque exception est nommée et motivée.
EXCEPTIONS_DATE_DU_JOUR: dict[tuple[str, str], str] = {}


def _derive_du_jour(expr: ast.AST, noms: set[str]) -> bool:
    """Vrai si la VALEUR de l'expression est la date du jour, directement ou
    par une méthode (`aujourd_hui.isoformat()`, `x.date()`). Une date passée
    en argument d'une autre fonction ne la rend pas « du jour » : la fonction
    peut s'en servir de borne, pas de valeur (`date_s14_sans_last_modified`)."""
    if isinstance(expr, ast.Name):
        return expr.id in noms
    if isinstance(expr, ast.Attribute):
        return _derive_du_jour(expr.value, noms)
    if isinstance(expr, ast.Call):
        f = expr.func
        if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name):
            if (f.value.id, f.attr) in (("date", "today"), ("datetime", "now"),
                                        ("datetime", "utcnow")):
                return True
        return isinstance(f, ast.Attribute) and _derive_du_jour(f.value, noms)
    if isinstance(expr, (ast.IfExp, ast.BoolOp)):
        valeurs = ([expr.body, expr.orelse] if isinstance(expr, ast.IfExp)
                   else expr.values)
        return any(_derive_du_jour(v, noms) for v in valeurs)
    return False


def _noms_affectes_depuis_le_jour(fonction: ast.AST) -> set[str]:
    noms: set[str] = set()
    affectations = [n for n in ast.walk(fonction) if isinstance(n, ast.Assign)]
    while True:
        avant = len(noms)
        for n in affectations:
            if _derive_du_jour(n.value, noms):
                noms.update(c.id for c in n.targets if isinstance(c, ast.Name))
        if len(noms) == avant:
            return noms


def _appels_upsert_meta(fonction: ast.AST):
    for n in ast.walk(fonction):
        if isinstance(n, ast.Call):
            nom = n.func.attr if isinstance(n.func, ast.Attribute) else getattr(n.func, "id", None)
            if nom == "upsert_meta":
                yield n


def _argument(appel: ast.Call, nom: str, position: int) -> ast.AST | None:
    for kw in appel.keywords:
        if kw.arg == nom:
            return kw.value
    if len(appel.args) > position:
        return appel.args[position]
    return None


def violations_date_du_jour(source: str, fichier: str) -> list[str]:
    arbre = ast.parse(source)
    trouvees = []
    for fonction in ast.walk(arbre):
        if not isinstance(fonction, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        noms = _noms_affectes_depuis_le_jour(fonction)
        for appel in _appels_upsert_meta(fonction):
            # signature : (conn, source_id, nom, url, licence, frequence, date_donnees, …)
            expr = _argument(appel, "date_donnees", 6)
            if expr is None or not _derive_du_jour(expr, noms):
                continue
            if (fichier, fonction.name) in EXCEPTIONS_DATE_DU_JOUR:
                continue
            trouvees.append(f"{fichier}:{appel.lineno} ({fonction.name})")
    return trouvees


def test_le_detecteur_voit_la_date_du_jour_directe_et_par_variable():
    code = (
        "def f(conn):\n"
        "    aujourd_hui = date.today().isoformat()\n"
        "    db.upsert_meta(conn, 'S', 'n', 'u', 'l', 'q', date_donnees=aujourd_hui, lignes=1)\n"
        "    db.upsert_meta(conn, 'S', 'n', 'u', 'l', 'q', datetime.now().date().isoformat(), 1)\n"
        "    db.upsert_meta(conn, 'S', 'n', 'u', 'l', 'q', date_donnees=derniere, lignes=1)\n"
        # repli sur le jour par une seconde affectation (ancien S14)
        "    j = date.today()\n"
        "    d = lire_en_tete()\n"
        "    if not d:\n"
        "        d = j.isoformat()\n"
        "    db.upsert_meta(conn, 'S', 'n', 'u', 'l', 'q', date_donnees=d, lignes=1)\n"
        # le jour passé en BORNE à une fonction n'est pas la valeur écrite
        "    e = date_sans_en_tete(conn, j)\n"
        "    db.upsert_meta(conn, 'S', 'n', 'u', 'l', 'q', date_donnees=e, lignes=1)\n"
    )
    assert violations_date_du_jour(code, "x.py") == [
        "x.py:3 (f)", "x.py:4 (f)", "x.py:10 (f)"]


def test_aucune_date_de_donnee_n_est_la_date_du_jour():
    trouvees = []
    for chemin in MODULES:
        trouvees += violations_date_du_jour(chemin.read_text("utf-8"), chemin.name)
    assert trouvees == [], (
        "date_donnees dérivée de la date du jour (règle db.upsert_meta) : "
        f"{trouvees}")


# ---------------------------------------------------------------------------
# Licences canoniques (C6)
# ---------------------------------------------------------------------------


def _licences_ecrites(source: str) -> list[tuple[int, ast.AST]]:
    arbre = ast.parse(source)
    sorties = []
    for appel in _appels_upsert_meta(arbre):
        expr = _argument(appel, "licence", 4)
        if expr is not None:
            sorties.append((appel.lineno, expr))
    return sorties


def _valeurs_constantes(arbre: ast.Module) -> dict[str, str]:
    """Constantes de module `NOM = "texte"` ou `NOM = common.LICENCE_…`."""
    valeurs = {}
    for n in arbre.body:
        if isinstance(n, ast.Assign) and len(n.targets) == 1 \
                and isinstance(n.targets[0], ast.Name):
            v = _evaluer(n.value, valeurs)
            if v is not None:
                valeurs[n.targets[0].id] = v
    return valeurs


def _evaluer(expr: ast.AST, constantes: dict[str, str]) -> str | None:
    if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
        return expr.value
    if isinstance(expr, ast.Name):
        if hasattr(common, expr.id):
            return getattr(common, expr.id)
        return constantes.get(expr.id)
    if isinstance(expr, ast.Attribute) and isinstance(expr.value, ast.Name) \
            and expr.value.id == "common":
        return getattr(common, expr.attr, None)
    return None


def test_toute_licence_ecrite_appartient_a_la_table_canonique():
    hors_table, illisibles = [], []
    for chemin in MODULES:
        source = chemin.read_text("utf-8")
        constantes = _valeurs_constantes(ast.parse(source))
        for ligne, expr in _licences_ecrites(source):
            valeur = _evaluer(expr, constantes)
            if valeur is None:
                illisibles.append(f"{chemin.name}:{ligne}")
            elif valeur not in common.LICENCES_CANONIQUES:
                hors_table.append(f"{chemin.name}:{ligne} « {valeur} »")
    assert hors_table == [], f"licence hors table canonique : {hors_table}"
    assert illisibles == [], (
        "licence non lisible statiquement (utiliser une constante de "
        f"common.LICENCES_CANONIQUES) : {illisibles}")


def test_deux_libelles_pour_la_licence_ouverte():
    ouvertes = {l for l in common.LICENCES_CANONIQUES if l.startswith("Licence Ouverte")}
    assert ouvertes == {common.LICENCE_OUVERTE_2, common.LICENCE_OUVERTE_SANS_VERSION}


def test_le_controle_des_licences_voit_un_libelle_hors_table():
    code = ("LICENCE = 'Licence Ouverte (fr-lo)'\n"
            "def f(conn):\n"
            "    db.upsert_meta(conn, 'S', 'n', 'u', LICENCE, 'q', '2026-01-01', 1)\n"
            "    db.upsert_meta(conn, 'S', 'n', 'u', licence='Licence Ouverte 2.0',"
            " frequence='q', date_donnees='2026-01-01', lignes=1)\n")
    arbre = ast.parse(code)
    valeurs = [_evaluer(e, _valeurs_constantes(arbre)) for _, e in _licences_ecrites(code)]
    assert valeurs == ["Licence Ouverte (fr-lo)", "Licence Ouverte 2.0"]
    assert [v in common.LICENCES_CANONIQUES for v in valeurs] == [False, True]


# ---------------------------------------------------------------------------
# Dates de donnée des sources revues le 20/11/2026 (C5)
# ---------------------------------------------------------------------------


def test_s11_date_de_la_fiche_modifiee_la_plus_recente():
    from pipelines.ingest_referentiels import date_donnees_annuaire
    fiches = [  # valeurs au format réel de l'API (relevé du 20/11/2026)
        {"nom": "Préfecture - Vaucluse",
         "date_modification_datetime": "2026-07-07T10:11:51+00:00"},
        {"nom": "Préfecture - X", "date_modification_datetime": "2026-11-03T08:00:00+00:00"},
        {"nom": "Préfecture - Y", "date_modification_datetime": None},
    ]
    assert date_donnees_annuaire(fiches) == "2026-11-03"
    with pytest.raises(ValueError, match="date de donnée inconnue"):
        date_donnees_annuaire([{"nom": "Préfecture - Y"}])


def test_s27_geo_api_doit_servir_le_millesime_annonce():
    from pipelines import ingest_referentiels as ref
    pops = {f"{i:02d}": 1000 + i for i in range(1, 97)}
    communes = [{"code": f"{d}001", "codeDepartement": d, "population": p}
                for d, p in pops.items()]
    assert ref.controler_millesime_geo(communes, pops) == 96
    # le millésime suivant : une commune change de population, le cycle lève
    communes[0] = {**communes[0], "population": communes[0]["population"] + 7}
    with pytest.raises(ValueError, match=f"millésime {ref.MILLESIME_POPULATIONS}"):
        ref.controler_millesime_geo(communes, pops)
    assert ref.EN_VIGUEUR_POPULATIONS == f"{ref.MILLESIME_POPULATIONS + 3}-01-01"
    assert f"/{ref.MILLESIME_CONTOURS}/" in ref.URL_ETALAB_DEPARTEMENTS_100M


def _base_s14(tmp_path, precedente):
    from pipelines import db
    conn = db.init_db(chemin=tmp_path / "s14.db")
    if precedente:
        db.upsert_meta(conn, "S14", "HATVP", "u", common.LICENCE_OUVERTE_SANS_VERSION,
                       "hebdomadaire", date_donnees=precedente, lignes=1)
    return conn


def test_s14_sans_en_tete_garde_la_date_connue_jamais_le_jour(tmp_path):
    from datetime import date
    from pipelines import ingest_integrite as p7
    jour = date(2026, 11, 20)
    dossiers = [{"date_depot": "2026-11-05", "date_publication": ""},
                {"date_depot": "2027-02-01", "date_publication": "2026-12-24"}]
    # le cycle précédent est plus récent que le contenu : on le garde
    conn = _base_s14(tmp_path, "2026-11-12")
    assert p7.date_s14_sans_last_modified(conn, dossiers, jour) == "2026-11-12"
    conn.close()
    # base neuve : le dépôt le plus récent, les dates futures écartées
    (tmp_path / "neuve").mkdir()
    conn = _base_s14(tmp_path / "neuve", None)
    assert p7.date_s14_sans_last_modified(conn, dossiers, jour) == "2026-11-05"
    # rien de vrai à écrire : lève plutôt que d'écrire le jour
    with pytest.raises(RuntimeError, match="pas de date de donnée vraie"):
        p7.date_s14_sans_last_modified(conn, [{"date_depot": ""}], jour)
    conn.close()


def test_s37_date_du_dernier_decret_inscrit():
    from pipelines import ingest_financement as fin
    assert all(d.get("date_decret") for d in fin.DECRETS_AIDE_PUBLIQUE)
    for d in fin.DECRETS_AIDE_PUBLIQUE:
        assert d["date_decret"][:4] == str(d["annee"])
    source = (RACINE_PIPELINES / "ingest_financement.py").read_text("utf-8")
    assert 'date_donnees=dernier_decret["date_decret"]' in source

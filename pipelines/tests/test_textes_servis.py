"""Textes que les pipelines écrivent pour le site (notes de `meta_sources`,
textes d'alerte, notes de faits) : ni référence interne, ni négation qui
vieillit sans date, ni libellé qui juge.

Audit des pages du 20/11/2026 :
- R4 : « jamais publiée en données », « toujours en vigueur en 2026 »
  deviennent faux sans que personne ne relise la phrase. Une négation sur
  l'amont est datée du jour de sa vérification (« au JJ/MM/AAAA ») ;
- R8 : « suspect », « plus dépensiers », « verrous » jugent au lieu de décrire
  (décision du propriétaire du 20/11/2026, Ton) ;
- R11 : « (SOURCES.md §4, alerte A5) », « détection du texte par P6/S3 »,
  « Légifrance anti-bot », `partis_comptes` étaient publiés sur /alertes et
  /financement. Le lecteur n'a ni ces fichiers, ni ces tables.

Test de structure (AST) : il lit le code des pipelines sans l'exécuter. Un
texte « servi » est ici toute chaîne en prose (au moins trois espaces) qui
n'est ni une docstring, ni un message de journal ou d'exception, ni du SQL.
Le filet est large exprès : une phrase de travail qui y tombe à tort se
reformule, elle n'a rien à faire dans une chaîne du code de production.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

RACINE_PIPELINES = Path(__file__).resolve().parents[1]
MODULES = sorted(RACINE_PIPELINES.glob("*.py"))

METHODES_JOURNAL = {"debug", "info", "warning", "warn", "error", "exception",
                    "critical", "log"}
LISTES_DE_CONTROLE = {"problemes", "erreurs", "anomalies"}
SQL = re.compile(r"\b(SELECT|INSERT|CREATE|UPDATE|DELETE|PRAGMA|ALTER|DROP|"
                 r"REPLACE INTO|WITH)\b")
DATE_FR = re.compile(r"\d{2}/\d{2}/\d{4}")

# R4 : négations et affirmations sur l'amont qui vieillissent. Elles restent
# permises si une date de vérification les suit de près.
QUI_VIEILLISSENT = re.compile(
    r"jamais publiée|jamais suivie|toujours en vigueur|aucun équivalent"
    r"|non publiée|uniquement en PDF",
    re.IGNORECASE,
)
FENETRE_DATE = 80

# R8 et R11 : motifs interdits dans tout texte servi.
INTERDITS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"SOURCES\.md"), "fichier interne du dépôt"),
    (re.compile(r"\bP\d+/S\d+\b"), "repère interne de planification"),
    (re.compile(r"\balerte A\d+\b"), "code interne d'alerte, absent du site"),
    (re.compile(r"anti-?bot", re.IGNORECASE), "note d'exploitation"),
    (re.compile(r"à déclencher", re.IGNORECASE), "consigne d'exploitation"),
    (re.compile(r"\bmitigation\b|10-critique", re.IGNORECASE), "document de travail"),
    (re.compile(r"dépensi(er|ère)", re.IGNORECASE), "libellé qui juge"),
    (re.compile(r"(?<![\w_])suspect(e|s|es)?(?![\w_])", re.IGNORECASE),
     "libellé qui juge : « montant signalé »"),
    (re.compile(r"(?<!\w)verrous?(?!\w)", re.IGNORECASE), "libellé qui juge"),
    (re.compile(r"boîte noire", re.IGNORECASE), "libellé qui juge"),
    (re.compile(r"retard de versement", re.IGNORECASE),
     "un écart de publication n'est pas un retard imputable"),
]

CREATION = re.compile(
    r"CREATE\s+(?:TABLE|VIEW)\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-z0-9]+_[a-z0-9_]+)",
    re.IGNORECASE,
)


def _texte(noeud: ast.AST) -> str | None:
    if isinstance(noeud, ast.Constant) and isinstance(noeud.value, str):
        return noeud.value
    if isinstance(noeud, ast.JoinedStr):
        return "".join(
            v.value if isinstance(v, ast.Constant) and isinstance(v.value, str) else "{}"
            for v in noeud.values
        )
    return None


def _docstrings(arbre: ast.AST) -> set[int]:
    ids: set[int] = set()
    for n in ast.walk(arbre):
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            corps = n.body
            if corps and isinstance(corps[0], ast.Expr) and _texte(corps[0].value) is not None:
                ids.add(id(corps[0].value))
    return ids


def _hors_service(arbre: ast.AST) -> set[int]:
    """Nœuds sous un appel de journal, un `raise`, un `assert` ou un `print`."""
    ids: set[int] = set()
    for n in ast.walk(arbre):
        exclu = isinstance(n, (ast.Raise, ast.Assert))
        if isinstance(n, ast.Call):
            f = n.func
            exclu = (isinstance(f, ast.Attribute) and f.attr in METHODES_JOURNAL) or (
                isinstance(f, ast.Name) and f.id in {"print", "exit"}
            ) or (
                # Contrôles de vraisemblance : la liste finit dans un
                # RuntimeError du cycle, jamais sur le site.
                isinstance(f, ast.Attribute) and f.attr == "append"
                and isinstance(f.value, ast.Name) and f.value.id in LISTES_DE_CONTROLE
            )
        if exclu:
            ids.update(id(s) for s in ast.walk(n))
    return ids


def _chaines(source: str) -> list[tuple[int, str]]:
    """Chaînes d'un module hors docstrings, journal, exceptions et SQL."""
    arbre = ast.parse(source)
    exclus = _docstrings(arbre) | _hors_service(arbre)
    vus: set[int] = set()
    out: list[tuple[int, str]] = []
    for n in ast.walk(arbre):
        if id(n) in exclus or id(n) in vus:
            continue
        if isinstance(n, ast.JoinedStr):
            vus.update(id(v) for v in n.values)
        t = _texte(n)
        if t is None or SQL.search(t):
            continue
        out.append((n.lineno, t))
    return out


def textes_servis(source: str) -> list[tuple[int, str]]:
    """Chaînes en prose d'un module (au moins trois espaces), avec leur ligne."""
    return [(l, t) for l, t in _chaines(source) if t.count(" ") >= 3]


def libelles_courts(source: str) -> list[tuple[int, str]]:
    """Chaînes de moins de trois espaces : libellés de colonne, de tableau ou
    de titre (« Montant suspect »). Elles échappaient au contrôle des mots
    interdits, qui s'y applique seul : une clé ou un identifiant n'a ni date
    ni négation à porter."""
    return [(l, t) for l, t in _chaines(source) if t.count(" ") < 3]


def mots_interdits_dans(texte: str) -> list[str]:
    return [f"« {m.group(0)} » ({pourquoi})"
            for motif, pourquoi in INTERDITS if (m := motif.search(texte))]


def tables_du_schema() -> set[str]:
    tables: set[str] = set()
    for m in MODULES:
        tables.update(t.lower() for t in CREATION.findall(m.read_text(encoding="utf-8")))
    return tables


def fautes_dans(texte: str, tables: set[str]) -> list[str]:
    fautes = mots_interdits_dans(texte)
    for m in QUI_VIEILLISSENT.finditer(texte):
        if not DATE_FR.search(texte[m.end():m.end() + FENETRE_DATE]):
            fautes.append(f"« {m.group(0)} » sans date de vérification")
    for t in sorted(tables):
        if re.search(rf"(?<![\w.]){re.escape(t)}(?!\w)", texte):
            fautes.append(f"nom de table « {t} »")
    return fautes


def test_aucun_texte_servi_ne_porte_de_reference_interne_ni_de_negation_non_datee():
    tables = tables_du_schema()
    assert "partis_comptes" in tables
    relevees = []
    for m in MODULES:
        for ligne, texte in textes_servis(m.read_text(encoding="utf-8")):
            for faute in fautes_dans(texte, tables):
                relevees.append(f"{m.name}:{ligne} : {faute}")
    assert relevees == []


def test_aucun_libelle_court_ne_porte_de_mot_interdit():
    relevees = []
    for m in MODULES:
        for ligne, texte in libelles_courts(m.read_text(encoding="utf-8")):
            for faute in mots_interdits_dans(texte):
                relevees.append(f"{m.name}:{ligne} : {faute}")
    assert relevees == []


def test_le_controle_voit_les_libelles_courts():
    source = 'COLONNES = {"montant": "Montant suspect", "cle": "montant_suspect"}\n'
    courts = dict((t, l) for l, t in libelles_courts(source))
    assert "Montant suspect" in courts and textes_servis(source) == []
    assert mots_interdits_dans("Montant suspect")
    assert mots_interdits_dans("Plus dépensiers")
    assert mots_interdits_dans("montant_suspect") == []


def test_le_controle_voit_chaque_defaut_de_l_audit():
    tables = {"partis_comptes"}
    for texte in [
        "Indicateur de structure (SOURCES.md §4, alerte A4).",
        "Traitement manuel annuel (détection du texte par P6/S3), voilà.",
        "Tableau dans le corps du décret, Légifrance anti-bot, non ingéré.",
        "L'aide perçue par parti figure dans partis_comptes (exercices 2021-2024).",
        "pas la LFI promulguée le 19/02/2026 (jamais publiée en données)",
        "Valeur au 01/01/2024, toujours en vigueur en 2026 ; identique.",
        "Les dix collectivités les plus dépensières par habitant.",
        "Marchés au montant suspect, à vérifier.",
        "La liste est publiée uniquement en PDF au JO.",
        "Le barème est non publiée en données à ce jour, voir le décret.",
    ]:
        assert fautes_dans(texte, tables), texte


def test_une_negation_datee_et_un_nom_de_colonne_restent_permis():
    tables = {"partis_comptes"}
    assert fautes_dans(
        "pas la LFI promulguée le 19/02/2026 (non publiée en données sur "
        "data.economie.gouv.fr au 21/11/2026)", tables) == []
    assert fautes_dans(
        "jamais publiée en données sur data.economie.gouv.fr (vérifié le 21/11/2026)",
        tables) == []
    # `montant_suspect` est un nom de colonne, pas un libellé.
    assert fautes_dans("filtre sur la colonne montant_suspect des marchés", tables) == []


def test_journal_exception_docstring_et_sql_ne_sont_pas_des_textes_servis():
    source = (
        '"""Module : voir SOURCES.md §4 pour la règle."""\n'
        "import logging\n"
        "log = logging.getLogger(__name__)\n"
        "def f(x):\n"
        '    """Lit partis_comptes, voir SOURCES.md."""\n'
        '    log.info("ordre de grandeur suspect pour %s ici", x)\n'
        '    if x:\n'
        '        raise ValueError(f"parquet suspect : {x} lignes lues")\n'
        '    return "SELECT a FROM partis_comptes WHERE b = 1"\n'
        'NOTE = "Texte servi au lecteur, voir SOURCES.md §4."\n'
    )
    servis = [t for _, t in textes_servis(source)]
    assert servis == ["Texte servi au lecteur, voir SOURCES.md §4."]

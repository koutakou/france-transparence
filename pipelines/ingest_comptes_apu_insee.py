"""P27 — Comptes des APU (S50, INSEE, Insee Résultats 8988845).

Source : tableaux xlsx 3.201, 3.202, 3.203, 3.205, 3.212 (totaux de
dépenses et de recettes par secteur) et 3.216 (prélèvements
obligatoires). Page : https://www.insee.fr/fr/statistiques/8988845
?sommaire=8988934. Cube Melodi homologue : DD_CNA_APU.

Licence : Licence Ouverte 2.0 (Etalab) — catalogue INSEE
https://www.insee.fr/fr/information/8184173 (les jeux du catalogue
Melodi) ; texte légal relu
https://www.data.gouv.fr/pages/legal/licences/etalab-2.0/ (25/08/2026).
Ce n'est PAS la décision 2011/833/UE (Eurostat).

CE PIPELINE N'EST PAS LA SOURCE S13, NI S44, NI S42, NI S49
----------------------------------------------------------
Le secteur ESA **S13** = administrations publiques.
La source France Transparence **S13** = situations mensuelles
budgétaires DGFiP (flux de l'État, budget général, cumul YTD).
La source **S44** = totaux TE/TR Eurostat `gov_10a_main` (S13 seul).
La source **S42** = B9 Maastricht Eurostat. La source **S49** = CFAP
`gov_10a_exp`. `source_id` ici = **S50**, jamais `'S13'` ni `'S44'`
ni `'S42'` ni `'S49'`.

N'ingère PAS le solde B9NF (ce serait republier S42). N'ingère PAS
Maastricht, PAS la CFAP, PAS taxag. Les totaux S13 de 3.201 sont une
présentation INSEE (dépenses et recettes, flux monétaires, imputés
limités) : on ne les affiche pas comme un second TE/TR, on ne
« ventile » pas S44. Les sous-secteurs ne s'additionnent pas au S13
(consolidations distinctes — note INSEE 3.215).

Unité native des xlsx : **milliards d'euros** (et % du PIB pour le
bloc PC de 3.216). Stockée telle quelle. Jamais × 1000 ni ÷ 1e9.

`date_donnees` = 31 décembre de l'année max observée (2025 →
2025-12-31), jamais `modified` Melodi (2026-06-08) ni la date de
parution Insee Résultats (29/05/2026).

Exécution : python -m pipelines.ingest_comptes_apu_insee
Base : FT_DB_PATH sinon data/france.db. Réécriture idempotente
(DELETE puis INSERT dans une transaction), puis upsert_meta('S50', …).
Échec → exit ≠ 0, base intacte.
"""

from __future__ import annotations

import re
import sys
import unicodedata
import zipfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

from pipelines import db
from pipelines.common import obtenir_logger, telecharger

log = obtenir_logger("comptes_apu_insee")

SOURCE_ID = "S50"
NOM_SOURCE = (
    "Comptes des APU (INSEE, dépenses et recettes par sous-secteur "
    "et prélèvements obligatoires)"
)
URL_PAGE = (
    "https://www.insee.fr/fr/statistiques/8988845?sommaire=8988934"
)
URL_FICHIER = (
    "https://www.insee.fr/fr/statistiques/fichier/8988845/{fichier}"
)
LICENCE = "Licence Ouverte 2.0 (Etalab)"
FREQUENCE = "annuelle"
CACHE_HEURES = 7 * 24

TABLEAUX_DEP_REC = (
    ("3.201", "t_3201_fr.xlsx", "S13"),
    ("3.202", "t_3202_fr.xlsx", "S1311"),
    ("3.203", "t_3203_fr.xlsx", "S13111"),
    ("3.205", "t_3205_fr.xlsx", "S1313"),
    ("3.212", "t_3212_fr.xlsx", "S1314"),
)
FICHIER_PO = "t_3216_fr.xlsx"
TABLEAU_PO = "3.216"

SECTEURS = (
    "S13",
    "S1311",
    "S13111",
    "S13112",
    "S1313",
    "S1314",
    "S212",
    "S13_S212",
)
POSTES = ("DEP_TOTAL", "REC_TOTAL", "PO", "PO_IMPOTS", "PO_COTIS")
UNITES = ("MdEUR", "PC_PIB")

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
COL_RE = re.compile(r"^([A-Z]+)(\d+)$")
ANNEE_RE = re.compile(r"^(19|20)\d{2}$")

BORNE_MIN_MD = 200.0
BORNE_MAX_MD = 4000.0
BORNE_MIN_PC = 20.0
BORNE_MAX_PC = 70.0
N_ANNEES_MIN = 25

NOTES = (
    "comptes nationaux base 2020, présentation dépenses et recettes "
    "(Insee Résultats 8988845, tableaux 3.201/3.202/3.203/3.205/3.212 "
    "et 3.216) ; unité native Md€ (et % du PIB pour le PO) ; "
    "date_donnees = 31/12 de l'année max, jamais modified Melodi ni "
    "date de parution ; distinct de S13 (SMB DGFiP, budget de l'État), "
    "de S44 (TE/TR gov_10a_main, table distincte), de S42 (B9 Maastricht, "
    "non ingéré ici), de S49 (CFAP) ; pas taxag ; pas une ventilation "
    "de S44 ; sous-secteurs non additifs au S13 (consolidations) ; "
    "S1311 n'est pas « la dette de l'État » ni le budget général ; "
    "S1314 n'est pas « la Sécu » ; cube Melodi DD_CNA_APU homologue"
)

_DDL = """
CREATE TABLE IF NOT EXISTS comptes_apu_insee (
    tableau     TEXT NOT NULL,
    secteur     TEXT NOT NULL CHECK (secteur IN (
                    'S13','S1311','S13111','S13112',
                    'S1313','S1314','S212','S13_S212'
                )),
    poste       TEXT NOT NULL CHECK (poste IN (
                    'DEP_TOTAL','REC_TOTAL','PO','PO_IMPOTS','PO_COTIS'
                )),
    libelle     TEXT NOT NULL,
    annee       INTEGER NOT NULL,
    valeur_md   REAL NOT NULL CHECK (valeur_md > 0),
    unite       TEXT NOT NULL CHECK (unite IN ('MdEUR','PC_PIB')),
    PRIMARY KEY (tableau, secteur, poste, annee, unite)
);
"""

# S13111 / S13112 avant S1311 : le préfixe le plus long gagne.
_PO_SECTEUR_PREFIXES = (
    ("s13 et s212", "S13_S212"),
    ("s13111", "S13111"),
    ("s13112", "S13112"),
    ("s1311", "S1311"),
    ("s1313", "S1313"),
    ("s1314", "S1314"),
    ("s212", "S212"),
)


def date_fin_annee(annee: int) -> str:
    """31 décembre de l'année des comptes : 2025 → 2025-12-31."""
    if not isinstance(annee, int) or annee < 1900 or annee > 2100:
        raise ValueError(f"année hors plage : {annee!r}")
    return f"{annee}-12-31"


def compact(texte: str) -> str:
    return " ".join((texte or "").split()).strip()


def cle_libelle(texte: str) -> str:
    """Minuscule, sans accents, espaces collapsés — pour matcher un libellé INSEE."""
    t = unicodedata.normalize("NFKD", texte or "")
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.replace("'", "'").replace("'", "'").replace("'", "'")
    return compact(t).lower()


def _col_row(ref: str) -> tuple[str, int]:
    m = COL_RE.match(ref)
    if not m:
        raise ValueError(f"référence de cellule hors motif : {ref!r}")
    return m.group(1), int(m.group(2))


def _shared_strings(z: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in z.namelist():
        return []
    racine = ET.fromstring(z.read("xl/sharedStrings.xml"))
    out: list[str] = []
    for si in racine.findall(f"{NS}si"):
        out.append("".join(t.text or "" for t in si.findall(f".//{NS}t")))
    return out


def _valeur_cellule(c: ET.Element, shared: list[str]):
    t = c.attrib.get("t")
    if t == "inlineStr":
        is_el = c.find(f"{NS}is")
        if is_el is None:
            return None
        return "".join(x.text or "" for x in is_el.findall(f".//{NS}t"))
    v = c.find(f"{NS}v")
    if v is None or v.text is None:
        return None
    if t == "s":
        return shared[int(v.text)]
    if t == "b":
        return v.text == "1"
    try:
        return float(v.text)
    except ValueError:
        return v.text


def _lire_feuille(chemin: Path) -> dict[int, dict[str, object]]:
    with zipfile.ZipFile(chemin) as z:
        shared = _shared_strings(z)
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        cibles = {}
        for rel in rels:
            rid = rel.attrib.get("Id")
            cible = rel.attrib.get("Target")
            if rid and cible:
                cibles[rid] = (
                    "xl/" + cible.lstrip("/")
                    if not cible.startswith("xl/")
                    else cible
                )
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        sheet = wb.find(f"{NS}sheets/{NS}sheet")
        if sheet is None:
            raise ValueError(f"xlsx sans feuille : {chemin}")
        rid = sheet.attrib.get(
            "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
        )
        cible = cibles.get(rid or "")
        if not cible:
            raise ValueError(f"feuille introuvable dans {chemin}")
        racine = ET.fromstring(z.read(cible))
        lignes: dict[int, dict[str, object]] = defaultdict(dict)
        for c in racine.findall(f".//{NS}c"):
            ref = c.attrib.get("r")
            if not ref:
                continue
            col, row = _col_row(ref)
            val = _valeur_cellule(c, shared)
            if val is not None:
                lignes[row][col] = val
        return lignes


def _annee_cellule(val) -> int | None:
    if isinstance(val, float) and val == int(val):
        an = int(val)
        return an if 1900 <= an <= 2100 else None
    if isinstance(val, str) and ANNEE_RE.match(val.strip()):
        return int(val.strip())
    return None


def _colonnes_annees(lignes: dict[int, dict[str, object]]) -> dict[str, int]:
    meilleur: dict[str, int] = {}
    for _row, ligne in lignes.items():
        mapping: dict[str, int] = {}
        for col, val in ligne.items():
            if col in ("A", "B"):
                continue
            an = _annee_cellule(val)
            if an is not None:
                mapping[col] = an
        if len(mapping) > len(meilleur):
            meilleur = mapping
    if len(meilleur) < 2:
        raise ValueError("aucune ligne d'années (au moins deux millésimes)")
    return meilleur


def _libelle_ligne(ligne: dict[str, object]) -> str:
    for col in ("B", "A"):
        v = ligne.get(col)
        if isinstance(v, str) and compact(v):
            return compact(v)
    return ""


def _observations_annee(
    *,
    tableau: str,
    secteur: str,
    poste: str,
    libelle: str,
    ligne: dict[str, object],
    annees: dict[str, int],
    unite: str,
) -> list[dict]:
    out: list[dict] = []
    for col, annee in annees.items():
        val = ligne.get(col)
        if val is None or isinstance(val, str):
            continue
        try:
            nombre = float(val)
        except (TypeError, ValueError):
            continue
        if nombre <= 0:
            continue
        out.append(
            {
                "tableau": tableau,
                "secteur": secteur,
                "poste": poste,
                "libelle": libelle,
                "annee": annee,
                "valeur_md": nombre,
                "unite": unite,
            }
        )
    return out


def extraire_dep_rec(
    chemin: Path, tableau: str, secteur: str
) -> list[dict]:
    """Totaux de dépenses et de recettes seulement — pas B9, pas les 'dont'."""
    if secteur not in SECTEURS:
        raise ValueError(f"secteur hors contrat : {secteur}")
    lignes = _lire_feuille(chemin)
    annees = _colonnes_annees(lignes)
    out: list[dict] = []
    for ligne in lignes.values():
        lab = _libelle_ligne(ligne)
        cle = cle_libelle(lab)
        if cle == "total des depenses":
            poste = "DEP_TOTAL"
        elif cle == "total des recettes":
            poste = "REC_TOTAL"
        else:
            continue
        out.extend(
            _observations_annee(
                tableau=tableau,
                secteur=secteur,
                poste=poste,
                libelle=lab,
                ligne=ligne,
                annees=annees,
                unite="MdEUR",
            )
        )
    postes = {o["poste"] for o in out}
    if postes != {"DEP_TOTAL", "REC_TOTAL"}:
        raise ValueError(
            f"{tableau} : postes lus {sorted(postes)}, "
            "DEP_TOTAL et REC_TOTAL attendus"
        )
    return out


def _secteur_po(cle: str) -> str | None:
    for prefixe, code in _PO_SECTEUR_PREFIXES:
        if cle.startswith(prefixe):
            return code
    return None


def extraire_po(chemin: Path) -> list[dict]:
    """Tableau 3.216 : PO en Md€ et en % du PIB. Pas B9."""
    lignes = _lire_feuille(chemin)
    annees = _colonnes_annees(lignes)
    out: list[dict] = []
    unite = "MdEUR"
    dernier_secteur: str | None = None
    for num in sorted(lignes):
        ligne = lignes[num]
        lab = _libelle_ligne(ligne)
        if not lab:
            continue
        cle = cle_libelle(lab)
        if cle.startswith("en milliards"):
            unite = "MdEUR"
            dernier_secteur = None
            continue
        if "produit interieur brut" in cle or cle.startswith("en %"):
            unite = "PC_PIB"
            dernier_secteur = None
            continue
        if cle.startswith("source") or cle.startswith("n.d") or cle.startswith("("):
            continue
        if "milliards d'euros" in cle or "milliards d euros" in cle:
            continue
        secteur = _secteur_po(cle)
        if secteur is not None:
            dernier_secteur = secteur
            poste = "PO"
        elif "cotisations sociales" in cle:
            if dernier_secteur not in ("S13111", "S1314"):
                continue
            secteur = dernier_secteur
            poste = "PO_COTIS"
        elif cle.lstrip("- ").startswith("impots"):
            if dernier_secteur not in ("S13111", "S1314"):
                continue
            secteur = dernier_secteur
            poste = "PO_IMPOTS"
        else:
            continue
        out.extend(
            _observations_annee(
                tableau=TABLEAU_PO,
                secteur=secteur,
                poste=poste,
                libelle=lab,
                ligne=ligne,
                annees=annees,
                unite=unite,
            )
        )
    if not any(
        o["secteur"] == "S13_S212" and o["poste"] == "PO" and o["unite"] == "MdEUR"
        for o in out
    ):
        raise ValueError("3.216 : PO S13 et S212 en Md€ introuvable")
    if not any(
        o["secteur"] == "S13_S212" and o["poste"] == "PO" and o["unite"] == "PC_PIB"
        for o in out
    ):
        raise ValueError("3.216 : PO S13 et S212 en % du PIB introuvable")
    return out


def extraire_tout(chemins: dict[str, Path]) -> list[dict]:
    out: list[dict] = []
    for tableau, _fichier, secteur in TABLEAUX_DEP_REC:
        out.extend(extraire_dep_rec(chemins[tableau], tableau, secteur))
    out.extend(extraire_po(chemins[TABLEAU_PO]))
    interdits = ("b9", "besoin de financement", "epargne brute", "épargne brute")
    for o in out:
        lab = cle_libelle(o["libelle"])
        if any(m in lab for m in interdits):
            raise ValueError(f"solde B9 ou épargne ingéré : {o['libelle']!r}")
        if o["poste"] not in POSTES or o["secteur"] not in SECTEURS:
            raise ValueError(f"observation hors contrat : {o}")
    return out


def controler_ampleur(observations: list[dict]) -> None:
    """Bornes d'unité sur le TIME max, pas la fixture."""
    def serie(secteur: str, poste: str, unite: str) -> list[dict]:
        return [
            o
            for o in observations
            if o["secteur"] == secteur
            and o["poste"] == poste
            and o["unite"] == unite
        ]

    dep_s13 = serie("S13", "DEP_TOTAL", "MdEUR")
    if len(dep_s13) < N_ANNEES_MIN:
        raise ValueError(
            f"S13 DEP_TOTAL : {len(dep_s13)} années, {N_ANNEES_MIN} attendues"
        )
    dernier_dep = max(dep_s13, key=lambda o: o["annee"])
    v = dernier_dep["valeur_md"]
    if not (BORNE_MIN_MD < v < BORNE_MAX_MD):
        raise ValueError(
            "ordre de grandeur suspect (erreur d'unité ?) : "
            f"S13 DEP_TOTAL {dernier_dep['annee']} = {v} Md€ "
            f"hors ]{BORNE_MIN_MD:g}, {BORNE_MAX_MD:g}["
        )
    po_md = serie("S13_S212", "PO", "MdEUR")
    if not po_md:
        raise ValueError("PO S13 et S212 (Md€) absent")
    dernier_po = max(po_md, key=lambda o: o["annee"])
    vpo = dernier_po["valeur_md"]
    if not (BORNE_MIN_MD < vpo < BORNE_MAX_MD):
        raise ValueError(
            "ordre de grandeur suspect (PO) : "
            f"{dernier_po['annee']} = {vpo} Md€ "
            f"hors ]{BORNE_MIN_MD:g}, {BORNE_MAX_MD:g}["
        )
    po_pc = serie("S13_S212", "PO", "PC_PIB")
    dernier_pc = max(po_pc, key=lambda o: o["annee"])
    vpc = dernier_pc["valeur_md"]
    if not (BORNE_MIN_PC < vpc < BORNE_MAX_PC):
        raise ValueError(
            "ordre de grandeur suspect (PO % PIB) : "
            f"{dernier_pc['annee']} = {vpc} "
            f"hors ]{BORNE_MIN_PC:g}, {BORNE_MAX_PC:g}["
        )
    tableaux = {o["tableau"] for o in observations}
    attendus = {t for t, _, _ in TABLEAUX_DEP_REC} | {TABLEAU_PO}
    if tableaux != attendus:
        raise ValueError(f"tableaux lus {sorted(tableaux)}, attendus {sorted(attendus)}")
    annee = dernier_dep["annee"]
    annee_po = dernier_po["annee"]
    if annee != annee_po:
        raise ValueError(
            f"millésime DEP S13 ({annee}) ≠ PO ({annee_po}) — "
            "une seule date_donnees, les deux séries doivent coïncider"
        )
    for secteur in ("S1311", "S1313", "S1314"):
        ss = serie(secteur, "DEP_TOTAL", "MdEUR")
        if not ss:
            raise ValueError(f"{secteur} DEP_TOTAL absent")
        vss = max(ss, key=lambda o: o["annee"])
        if vss["annee"] != annee:
            raise ValueError(
                f"{secteur} DEP_TOTAL millésime {vss['annee']} ≠ {annee}"
            )
        if not (vss["valeur_md"] < v):
            raise ValueError(
                f"{secteur} DEP_TOTAL {vss['valeur_md']} ≮ S13 {v} "
                "(câblage de tableau ?)"
            )


def ecrire_db(conn, observations: list[dict]) -> str:
    """DELETE+INSERT en transaction, puis upsert_meta S50. Retourne date_donnees."""
    if not observations:
        raise ValueError("écriture vide")
    tableaux = {o["tableau"] for o in observations}
    attendus = {t for t, _, _ in TABLEAUX_DEP_REC} | {TABLEAU_PO}
    if tableaux != attendus:
        raise ValueError(f"écriture incomplète : {sorted(tableaux)}")
    date_donnees = date_fin_annee(max(o["annee"] for o in observations))
    conn.executescript(_DDL)
    with conn:
        conn.execute("DELETE FROM comptes_apu_insee")
        conn.executemany(
            """INSERT INTO comptes_apu_insee
               (tableau, secteur, poste, libelle, annee, valeur_md, unite)
               VALUES (:tableau, :secteur, :poste, :libelle,
                       :annee, :valeur_md, :unite)""",
            observations,
        )
    db.upsert_meta(
        conn,
        source_id=SOURCE_ID,
        nom=NOM_SOURCE,
        url=URL_PAGE,
        licence=LICENCE,
        frequence=FREQUENCE,
        date_donnees=date_donnees,
        lignes=len(observations),
        notes=NOTES,
    )
    return date_donnees


def main() -> int:
    try:
        chemins: dict[str, Path] = {}
        for tableau, fichier, _secteur in TABLEAUX_DEP_REC:
            brut = telecharger(
                URL_FICHIER.format(fichier=fichier),
                f"insee/cna_apu/{fichier}",
                max_age_heures=CACHE_HEURES,
            )
            chemins[tableau] = Path(brut)
        brut_po = telecharger(
            URL_FICHIER.format(fichier=FICHIER_PO),
            f"insee/cna_apu/{FICHIER_PO}",
            max_age_heures=CACHE_HEURES,
        )
        chemins[TABLEAU_PO] = Path(brut_po)
        observations = extraire_tout(chemins)
        controler_ampleur(observations)
        conn = db.init_db()
        date_donnees = ecrire_db(conn, observations)
        conn.close()
        log.info(
            "comptes_apu_insee: %d observations, données au %s (année max %s)",
            len(observations),
            date_donnees,
            max(o["annee"] for o in observations),
        )
        return 0
    except Exception:
        log.exception("échec de l'ingestion S50 — base laissée intacte")
        return 1


if __name__ == "__main__":
    sys.exit(main())

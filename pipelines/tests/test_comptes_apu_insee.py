"""Tests S50 — comptes des APU INSEE.

Les xlsx de fixture sont INVENTÉS (deux millésimes, totaux hors bornes
d'ampleur). Aucune valeur live de l'Insee Résultats 8988845.
"""

from __future__ import annotations

import sqlite3
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

import pytest

from pipelines import db
from pipelines.ingest_comptes_apu_insee import (
    SOURCE_ID,
    TABLEAU_PO,
    TABLEAUX_DEP_REC,
    URL_PAGE,
    controler_ampleur,
    date_fin_annee,
    ecrire_db,
    extraire_dep_rec,
    extraire_po,
    extraire_tout,
)


def _col(n: int) -> str:
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def ecrire_xlsx(chemin: Path, titre: str, annees: list[int], lignes: list[tuple[str, list[float | None]]]) -> None:
    """Classeur minimal (une feuille, shared strings) pour extraire()."""
    strings = [titre] + [lab for lab, _ in lignes]
    index = {s: i for i, s in enumerate(strings)}

    def cell_s(ref: str, texte: str) -> str:
        return f'<c r="{ref}" t="s"><v>{index[texte]}</v></c>'

    def cell_n(ref: str, val: float) -> str:
        return f'<c r="{ref}"><v>{val}</v></c>'

    sheet_cells = [cell_s("A1", titre)]
    for i, an in enumerate(annees):
        sheet_cells.append(cell_n(f"{_col(3 + i)}3", float(an)))
    row0 = 5
    for k, (lab, vals) in enumerate(lignes):
        r = row0 + k
        sheet_cells.append(cell_s(f"B{r}", lab))
        for i, v in enumerate(vals):
            if v is None:
                continue
            sheet_cells.append(cell_n(f"{_col(3 + i)}{r}", float(v)))
    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        "<sheetData>"
        f'<row r="1">{cell_s("A1", titre)}</row>'
        f'<row r="3">{"".join(cell_n(f"{_col(3 + i)}3", float(an)) for i, an in enumerate(annees))}</row>'
        + "".join(
            f'<row r="{row0 + k}">{cell_s(f"B{row0 + k}", lab)}'
            + "".join(
                cell_n(f"{_col(3 + i)}{row0 + k}", float(v))
                for i, v in enumerate(vals)
                if v is not None
            )
            + "</row>"
            for k, (lab, vals) in enumerate(lignes)
        )
        + "</sheetData></worksheet>"
    )
    sst = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
        f' count="{len(strings)}" uniqueCount="{len(strings)}">'
        + "".join(f"<si><t>{escape(s)}</t></si>" for s in strings)
        + "</sst>"
    )
    wb = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
        ' xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="t" sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    rels_wb = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1"'
        ' Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"'
        ' Target="worksheets/sheet1.xml"/>'
        '<Relationship Id="rId2"'
        ' Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings"'
        ' Target="sharedStrings.xml"/>'
        "</Relationships>"
    )
    rels_pkg = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1"'
        ' Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"'
        ' Target="xl/workbook.xml"/>'
        "</Relationships>"
    )
    ctypes = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml"'
        ' ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml"'
        ' ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '<Override PartName="/xl/sharedStrings.xml"'
        ' ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>'
        "</Types>"
    )
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(chemin, "w") as z:
        z.writestr("[Content_Types].xml", ctypes)
        z.writestr("_rels/.rels", rels_pkg)
        z.writestr("xl/workbook.xml", wb)
        z.writestr("xl/_rels/workbook.xml.rels", rels_wb)
        z.writestr("xl/worksheets/sheet1.xml", sheet_xml)
        z.writestr("xl/sharedStrings.xml", sst)


def _dep_rec_xlsx(chemin: Path, tableau: str) -> None:
    ecrire_xlsx(
        chemin,
        f"{tableau} Dépenses et recettes",
        [2024, 2025],
        [
            ("Total des dépenses", [10.0, 11.0]),
            ("Capacité (+) ou besoin (-) de financement (B9NF)", [-1.5, -1.2]),
            ("Total des recettes", [8.5, 9.0]),
            ("Épargne brute (B8g)", [0.1, 0.2]),
        ],
    )


def _po_xlsx(chemin: Path) -> None:
    ecrire_xlsx(
        chemin,
        "3.216 Prélèvements obligatoires",
        [2024, 2025],
        [
            ("En milliards d'euros", [None, None]),
            ("S13 et S212 - Prélèvements obligatoires", [12.0, 13.0]),
            ("S1311 - Administration publique centrale", [4.0, 4.5]),
            ("S13111 - État", [3.5, 4.0]),
            ("            - Impôts (*)", [3.0, 3.4]),
            ("            - Cotisations sociales (**)", [0.5, 0.6]),
            ("S13112 - Organismes divers d'administration centrale", [0.5, 0.5]),
            ("S1313 - Administrations publiques locales", [2.0, 2.1]),
            ("S1314 - Administrations de sécurité sociale", [5.8, 6.1]),
            ("          - Impôts (*)", [2.0, 2.1]),
            ("          - Cotisations sociales (**)", [3.8, 4.0]),
            ("S212 - Institutions et organes de l'Union européenne", [0.2, 0.3]),
            ("En % du produit intérieur brut", [None, None]),
            ("S13 et S212 - Prélèvements obligatoires", [42.0, 43.0]),
            ("S1311 - Administration publique centrale", [12.0, 12.5]),
            ("S1313 - Administrations publiques locales", [6.0, 6.1]),
            ("S1314 - Administrations de sécurité sociale", [23.8, 24.1]),
            ("S212 - Institutions et organes de l'Union européenne", [0.2, 0.3]),
        ],
    )


@pytest.fixture
def chemins(tmp_path: Path) -> dict[str, Path]:
    out: dict[str, Path] = {}
    for tableau, fichier, _secteur in TABLEAUX_DEP_REC:
        p = tmp_path / fichier
        _dep_rec_xlsx(p, tableau)
        out[tableau] = p
    p_po = tmp_path / "t_3216_fr.xlsx"
    _po_xlsx(p_po)
    out[TABLEAU_PO] = p_po
    return out


@pytest.fixture
def observations(chemins):
    return extraire_tout(chemins)


@pytest.fixture
def conn(tmp_path, observations):
    c = db.init_db(chemin=tmp_path / "france.db")
    ecrire_db(c, observations)
    yield c
    c.close()


def test_date_fin_annee():
    assert date_fin_annee(2025) == "2025-12-31"
    with pytest.raises(ValueError):
        date_fin_annee(1800)


def test_extraire_ignore_b9_et_epargne(chemins):
    obs = extraire_dep_rec(chemins["3.201"], "3.201", "S13")
    postes = {o["poste"] for o in obs}
    assert postes == {"DEP_TOTAL", "REC_TOTAL"}
    for o in obs:
        assert "B9" not in o["libelle"]
        assert "épargne" not in o["libelle"].lower()
        assert "besoin" not in o["libelle"].lower()


def test_extraire_po_deux_unites(chemins):
    obs = extraire_po(chemins[TABLEAU_PO])
    po = [
        o
        for o in obs
        if o["secteur"] == "S13_S212" and o["poste"] == "PO" and o["annee"] == 2025
    ]
    unites = {o["unite"] for o in po}
    assert unites == {"MdEUR", "PC_PIB"}
    md = next(o for o in po if o["unite"] == "MdEUR")
    pc = next(o for o in po if o["unite"] == "PC_PIB")
    assert md["valeur_md"] == 13.0
    assert pc["valeur_md"] == 43.0
    assert any(o["poste"] == "PO_IMPOTS" and o["secteur"] == "S13111" for o in obs)
    assert any(o["poste"] == "PO_COTIS" and o["secteur"] == "S1314" for o in obs)
    assert any(
        o["secteur"] == "S212" and o["poste"] == "PO" and o["unite"] == "MdEUR"
        for o in obs
    )
    assert any(o["secteur"] == "S1311" and o["poste"] == "PO" for o in obs)
    assert any(o["secteur"] == "S1313" and o["poste"] == "PO" for o in obs)


def test_sous_secteurs_non_sommes_au_s13(observations):
    def v(secteur: str) -> float:
        return next(
            o["valeur_md"]
            for o in observations
            if o["secteur"] == secteur
            and o["poste"] == "DEP_TOTAL"
            and o["annee"] == 2025
        )

    # Dans la fixture, tous les totaux DEP valent 11 : les additionner
    # recoudrait le piège 3.215. On verrouille que trois sous-secteurs
    # sont bien là, sans les sommer dans le pipeline.
    assert v("S13") == 11.0
    assert v("S1311") == 11.0
    assert v("S1313") == 11.0
    assert v("S1314") == 11.0


def test_controler_ampleur_refuse_la_fixture(observations):
    with pytest.raises(ValueError, match="années"):
        controler_ampleur(observations)


def test_controler_ampleur_accepte_une_serie_inventee():
    obs = []
    for i in range(30):
        an = 1996 + i
        obs.append(
            {
                "tableau": "3.201",
                "secteur": "S13",
                "poste": "DEP_TOTAL",
                "libelle": "Total des dépenses",
                "annee": an,
                "valeur_md": 1600.0 + i,
                "unite": "MdEUR",
            }
        )
        obs.append(
            {
                "tableau": "3.201",
                "secteur": "S13",
                "poste": "REC_TOTAL",
                "libelle": "Total des recettes",
                "annee": an,
                "valeur_md": 1500.0 + i,
                "unite": "MdEUR",
            }
        )
    for tableau, _f, secteur in TABLEAUX_DEP_REC:
        if tableau == "3.201":
            continue
        obs.append(
            {
                "tableau": tableau,
                "secteur": secteur,
                "poste": "DEP_TOTAL",
                "libelle": "Total des dépenses",
                "annee": 2025,
                "valeur_md": 400.0,
                "unite": "MdEUR",
            }
        )
        obs.append(
            {
                "tableau": tableau,
                "secteur": secteur,
                "poste": "REC_TOTAL",
                "libelle": "Total des recettes",
                "annee": 2025,
                "valeur_md": 350.0,
                "unite": "MdEUR",
            }
        )
    obs.append(
        {
            "tableau": "3.216",
            "secteur": "S13_S212",
            "poste": "PO",
            "libelle": "S13 et S212 - Prélèvements obligatoires",
            "annee": 2025,
            "valeur_md": 1300.0,
            "unite": "MdEUR",
        }
    )
    obs.append(
        {
            "tableau": "3.216",
            "secteur": "S13_S212",
            "poste": "PO",
            "libelle": "S13 et S212 - Prélèvements obligatoires",
            "annee": 2025,
            "valeur_md": 43.6,
            "unite": "PC_PIB",
        }
    )
    controler_ampleur(obs)


def test_ecrire_db_idempotent(conn, observations):
    n1 = conn.execute("SELECT count(*) AS n FROM comptes_apu_insee").fetchone()["n"]
    ecrire_db(conn, observations)
    ecrire_db(conn, observations)
    n2 = conn.execute("SELECT count(*) AS n FROM comptes_apu_insee").fetchone()["n"]
    assert n1 == n2 == len(observations)


def test_check_sql_refuse_un_b9_comme_poste(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO comptes_apu_insee "
            "(tableau, secteur, poste, libelle, annee, valeur_md, unite) "
            "VALUES ('3.201','S13','B9NF','solde',2025,1.0,'MdEUR')"
        )


def test_check_sql_refuse_un_zero(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO comptes_apu_insee "
            "(tableau, secteur, poste, libelle, annee, valeur_md, unite) "
            "VALUES ('3.201','S13','DEP_TOTAL','Total des dépenses',1990,0.0,'MdEUR')"
        )


def test_meta_s50_licence_et_date(conn):
    ligne = conn.execute(
        "SELECT * FROM meta_sources WHERE source_id = ?", (SOURCE_ID,)
    ).fetchone()
    assert ligne is not None
    assert ligne["source_id"] == "S50"
    assert "Licence Ouverte 2.0" in ligne["licence"]
    assert "2011/833" not in ligne["licence"]
    assert ligne["frequence"] == "annuelle"
    assert ligne["date_donnees"] == "2025-12-31"
    assert ligne["url"] == URL_PAGE
    notes = ligne["notes"].lower()
    assert "s44" in notes
    assert "taxag" in notes
    assert "b9" in notes
    assert "sondage" not in notes
    assert "baromètre" not in notes
    assert "dette de l'état" in notes or "dette de l'etat" in notes


def test_n_ecrit_que_comptes_apu_insee_et_meta_sources(conn):
    tables = {
        r["name"]
        for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    noyau = {"meta_sources", "entites", "elus"}
    assert noyau <= tables
    metier = tables - noyau - {"sqlite_sequence"}
    assert metier == {"comptes_apu_insee"}
    assert "agregats_apu_esa" not in tables
    assert "cofog_apu_esa" not in tables
    assert "deficit_apu_maastricht" not in tables


def test_ecrire_refuse_un_tableau_manquant(tmp_path, observations):
    tronque = [o for o in observations if o["tableau"] != "3.216"]
    c = db.init_db(chemin=tmp_path / "incomplet.db")
    with pytest.raises(ValueError, match="incomplète"):
        ecrire_db(c, tronque)
    c.close()


def test_aucune_colonne_population_ni_b9(conn):
    colonnes = {
        r["name"].lower()
        for r in conn.execute("PRAGMA table_info(comptes_apu_insee)")
    }
    for interdite in ("population", "par_habitant", "habitants", "b9", "deficit"):
        assert interdite not in colonnes
    assert "poste" in colonnes
    postes = {
        r["poste"]
        for r in conn.execute("SELECT DISTINCT poste FROM comptes_apu_insee")
    }
    assert "B9NF" not in postes
    assert "DEP_TOTAL" in postes
    assert "PO" in postes

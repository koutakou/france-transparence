"""Tests S51 — dépenses et recettes des ODAC INSEE (tableau 3.204).

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
from pipelines.ingest_odac_insee import (
    SOURCE_ID,
    TABLEAU,
    URL_PAGE,
    controler_ampleur,
    ecrire_db,
    extraire,
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


def _dep_rec_xlsx(chemin: Path) -> None:
    ecrire_xlsx(
        chemin,
        "3.204 Dépenses et recettes des organismes divers d'administration centrale (S13112)",
        [2024, 2025],
        [
            ("Total des dépenses", [10.0, 11.0]),
            ("dont (a) - Cotisations sociales imputées (D122)", [0.5, 0.6]),
            ("Dépenses hors éléments imputés (a, b et c)", [9.5, 10.4]),
            ("Capacité (+) ou besoin (-) de financement (B9NF)", [-1.5, -1.2]),
            ("Total des recettes", [8.5, 9.0]),
            ("dont (a) - Cotisations sociales imputées (D612)", [0.3, 0.4]),
            ("Recettes hors éléments imputés (a,b et c')", [8.2, 8.6]),
            ("Épargne brute (B8g)", [0.1, 0.2]),
        ],
    )


def _obs(poste: str, annee: int, valeur: float, **extra) -> dict:
    libelle = (
        extra.pop("libelle", None)
        or ("Total des dépenses" if poste == "DEP_TOTAL" else "Total des recettes")
    )
    return {
        "tableau": extra.pop("tableau", TABLEAU),
        "secteur": extra.pop("secteur", "S13112"),
        "poste": poste,
        "libelle": libelle,
        "annee": annee,
        "valeur_md": valeur,
        "unite": extra.pop("unite", "MdEUR"),
        **extra,
    }


def _serie_inventee(*, dep_max: float = 80.0, rec_max: float = 75.0) -> list[dict]:
    """30 millésimes, totaux dans ]20, 400[ — pas des valeurs live."""
    out: list[dict] = []
    for i in range(30):
        an = 1996 + i
        out.append(_obs("DEP_TOTAL", an, dep_max - (29 - i) * 0.5))
        out.append(_obs("REC_TOTAL", an, rec_max - (29 - i) * 0.5))
    return out


@pytest.fixture
def xlsx(tmp_path: Path) -> Path:
    p = tmp_path / "t_3204_fr.xlsx"
    _dep_rec_xlsx(p)
    return p


@pytest.fixture
def observations(xlsx: Path):
    return extraire(xlsx)


@pytest.fixture
def conn(tmp_path, observations):
    c = db.init_db(chemin=tmp_path / "france.db")
    ecrire_db(c, observations)
    yield c
    c.close()


def test_extraire_ignore_b9_epargne_et_dont(observations):
    for o in observations:
        lab = o["libelle"].lower()
        assert "b9" not in lab
        assert "épargne" not in lab
        assert "epargne" not in lab
        assert "besoin" not in lab
        assert not lab.startswith("dont")
        assert "dont (" not in lab
        assert "hors" not in lab


def test_extraire_dep_rec_s13112_tableau_3204(observations):
    postes = {o["poste"] for o in observations}
    assert postes == {"DEP_TOTAL", "REC_TOTAL"}
    assert {o["tableau"] for o in observations} == {"3.204"}
    assert {o["secteur"] for o in observations} == {"S13112"}
    assert {o["unite"] for o in observations} == {"MdEUR"}
    assert {o["annee"] for o in observations} == {2024, 2025}
    dep = {
        o["annee"]: o["valeur_md"]
        for o in observations
        if o["poste"] == "DEP_TOTAL"
    }
    rec = {
        o["annee"]: o["valeur_md"]
        for o in observations
        if o["poste"] == "REC_TOTAL"
    }
    assert dep == {2024: 10.0, 2025: 11.0}
    assert rec == {2024: 8.5, 2025: 9.0}


def test_ecrire_db_meta_s51_date_fin_annee_max(conn, observations):
    n = conn.execute("SELECT count(*) AS n FROM comptes_odac_insee").fetchone()["n"]
    assert n == len(observations)
    ligne = conn.execute(
        "SELECT * FROM meta_sources WHERE source_id = ?", (SOURCE_ID,)
    ).fetchone()
    assert ligne is not None
    assert ligne["source_id"] == "S51"
    assert "Licence Ouverte 2.0" in ligne["licence"]
    assert ligne["frequence"] == "annuelle"
    assert ligne["date_donnees"] == "2025-12-31"
    assert ligne["url"] == URL_PAGE
    notes = ligne["notes"].lower()
    assert "s50" in notes
    assert "s13" in notes
    assert "s39" in notes
    assert "s44" in notes
    assert "s42" in notes
    assert "3.204" in notes
    assert "opérateur" in notes or "operateur" in notes
    assert "sondage" not in notes
    assert "baromètre" not in notes
    assert "barometre" not in notes
    assert "dette de l'état" not in notes
    assert "dette de l'etat" not in notes
    assert "la sécu" not in notes
    assert "la secu" not in notes
    tables = {
        r["name"]
        for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert "comptes_odac_insee" in tables
    assert "comptes_apu_insee" not in tables


def test_controler_ampleur_refuse_dep_hors_bornes():
    obs = _serie_inventee(dep_max=11.0, rec_max=80.0)
    with pytest.raises(ValueError, match=r"DEP_TOTAL .* hors \]20, 400\["):
        controler_ampleur(obs)


def test_controler_ampleur_refuse_si_b9_se_glisse():
    obs = _serie_inventee()
    obs.append(
        _obs(
            "DEP_TOTAL",
            2025,
            2.0,
            libelle="Capacité (+) ou besoin (-) de financement (B9NF)",
        )
    )
    with pytest.raises(ValueError, match="B9"):
        controler_ampleur(obs)


def test_controler_ampleur_accepte_une_serie_inventee():
    controler_ampleur(_serie_inventee())


def test_check_sql_refuse_un_b9_comme_poste(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO comptes_odac_insee "
            "(tableau, secteur, poste, libelle, annee, valeur_md, unite) "
            "VALUES ('3.204','S13112','B9NF','solde',2025,1.0,'MdEUR')"
        )


def test_check_sql_refuse_un_zero(conn):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO comptes_odac_insee "
            "(tableau, secteur, poste, libelle, annee, valeur_md, unite) "
            "VALUES ('3.204','S13112','DEP_TOTAL','Total des dépenses',1990,0.0,'MdEUR')"
        )


def test_ecrire_db_idempotent(conn, observations):
    n1 = conn.execute("SELECT count(*) AS n FROM comptes_odac_insee").fetchone()["n"]
    ecrire_db(conn, observations)
    ecrire_db(conn, observations)
    n2 = conn.execute("SELECT count(*) AS n FROM comptes_odac_insee").fetchone()["n"]
    assert n1 == n2 == len(observations)

"""Tests du pipeline P24 — IRCOM (S47).

La fixture xlsx est MINIMALE INVENTÉE (milliers d'euros, pas des
valeurs live). Elle porte : un Total Ain, un Total Paris 1er
(arrondissement), un Total n.c. (secret statistique), un Total
négatif (restitution), un Total Corse-du-Sud, un Total B31 Autres
(hors carte), et une ligne de tranche qui ne doit PAS être ingérée.
Les garde-fous d'ampleur se testent à part.
"""

from __future__ import annotations

import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

import pytest

from pipelines import db
from pipelines.ingest_ircom import (
    SOURCE_ID,
    controler_ampleur,
    date_fin_annee,
    departement_carte,
    ecrire_db,
    euros_en_md,
    extraire,
    milliers_en_euros,
    xlsx_communes_dans_zip,
)


def _xlsx_inline(chemin: Path, lignes: list[list[tuple[str, str]]]) -> Path:
    """xlsx à une feuille, cellules en inlineStr ou nombre.

    `lignes` : liste de lignes, chaque ligne = liste de (col, valeur).
    Une valeur commençant par '#' est écrite comme nombre (sans le #).
    """
    cells_xml = []
    for i, row in enumerate(lignes, start=1):
        parts = []
        for col, val in row:
            ref = f"{col}{i}"
            if val.startswith("#"):
                parts.append(
                    f'<c r="{ref}"><v>{escape(val[1:])}</v></c>'
                )
            else:
                parts.append(
                    f'<c r="{ref}" t="inlineStr"><is><t>{escape(val)}</t></is></c>'
                )
        cells_xml.append(
            f'<row r="{i}">' + "".join(parts) + "</row>"
        )
    sheet = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        "<sheetData>" + "".join(cells_xml) + "</sheetData></worksheet>"
    )
    wb = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="ListeCommune" sheetId="1" r:id="rId1"/></sheets>'
        "</workbook>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/>'
        "</Relationships>"
    )
    ctypes = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        "</Types>"
    )
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/>'
        "</Relationships>"
    )
    with zipfile.ZipFile(chemin, "w") as z:
        z.writestr("[Content_Types].xml", ctypes)
        z.writestr("_rels/.rels", root_rels)
        z.writestr("xl/workbook.xml", wb)
        z.writestr("xl/_rels/workbook.xml.rels", rels)
        z.writestr("xl/worksheets/sheet1.xml", sheet)
    return chemin


def _fixture(tmp_path: Path) -> Path:
    """6 Total + 1 tranche (ignorée). Unités : milliers d'euros."""
    return _xlsx_inline(
        tmp_path / "ircom_mini.xlsx",
        [
            [("B", "DESF")],
            [],
            [("E", "IRCOM revenus 2024")],
            [("N", "Montants en milliers d'euros (exceptés ceux des RFR par tranche)")],
            [],
            [
                ("B", "Dép."),
                ("C", "Commune"),
                ("D", "Libellé de la commune"),
                ("E", "Revenu fiscal de référence par tranche (en euros)"),
                ("F", "Nombre de foyers fiscaux"),
                ("H", "Impôt net (total)*"),
                ("I", "Nombre de foyers fiscaux imposés"),
            ],
            [],
            # Ain, Total — 1 000 k€ = 1 000 000 €
            [
                ("B", "010"),
                ("C", "001"),
                ("D", "L'Abergement-Clémenciat"),
                ("E", "Total"),
                ("F", "#480"),
                ("H", "#1000"),
                ("I", "#200"),
            ],
            # Tranche — NE DOIT PAS entrer
            [
                ("B", "010"),
                ("C", "004"),
                ("D", "Ambérieu-en-Bugey"),
                ("E", "0 à 10 000"),
                ("F", "#10"),
                ("H", "#99999"),
                ("I", "#1"),
            ],
            # Paris 1er (B=754, C=101) → dép. 75
            [
                ("B", "754"),
                ("C", "101"),
                ("D", "Paris 1er Arrondissement"),
                ("E", "Total"),
                ("F", "#1000"),
                ("H", "#2000"),
                ("I", "#500"),
            ],
            # Secret statistique
            [
                ("B", "020"),
                ("C", "129"),
                ("D", "Bruys"),
                ("E", "Total"),
                ("F", "#11"),
                ("H", "n.c."),
                ("I", "n.c."),
            ],
            # Restitution (négatif)
            [
                ("B", "020"),
                ("C", "534"),
                ("D", "Muscourt"),
                ("E", "Total"),
                ("F", "#20"),
                ("H", "#-1.5"),
                ("I", "#0"),
            ],
            # Corse-du-Sud
            [
                ("B", "2A0"),
                ("C", "004"),
                ("D", "Ajaccio"),
                ("E", "Total"),
                ("F", "#100"),
                ("H", "#50"),
                ("I", "#40"),
            ],
            # Hors carte (DINR / Autres)
            [
                ("B", "B31"),
                ("C", "999"),
                ("D", "Autres"),
                ("E", "Total"),
                ("F", "#5"),
                ("H", "#10"),
                ("I", "#3"),
            ],
        ],
    )


@pytest.fixture()
def xlsx(tmp_path):
    return _fixture(tmp_path)


@pytest.fixture()
def extrait(xlsx):
    return extraire(xlsx)


def test_milliers_en_euros_fois_mille():
    assert milliers_en_euros(1542.261) == pytest.approx(1_542_261.0)
    assert euros_en_md(milliers_en_euros(91_678_599.659)) == pytest.approx(
        91.678599659
    )


def test_md_egal_euros_divise_par_1e9():
    for euros in (1e9, 91_678_599_659.0, 1.0):
        assert euros_en_md(euros) == euros / 1e9


def test_date_fin_annee_31_decembre_des_revenus():
    assert date_fin_annee(2024) == "2024-12-31"
    # Ce n'est PAS la publication data.gouv du 26/05/2026.
    assert date_fin_annee(2024) != "2026-05-26"


def test_departement_carte_ain_paris_corse_b31():
    assert departement_carte("010", "001") == "01"
    assert departement_carte("754", "101") == "75"
    assert departement_carte("757", "116") == "75"
    assert departement_carte("131", "201") == "13"
    assert departement_carte("690", "381") == "69"
    assert departement_carte("2A0", "004") == "2A"
    assert departement_carte("2B0", "033") == "2B"
    assert departement_carte("971", "001") == "971"
    assert departement_carte("B31", "999") is None
    assert departement_carte("330", "063") == "33"


def test_extraire_lit_lannee_et_ignore_les_tranches(extrait):
    annee, lignes = extrait
    assert annee == 2024
    assert len(lignes) == 6
    assert all(o["libelle"] != "Ambérieu-en-Bugey" for o in lignes)
    assert {o["libelle"] for o in lignes} == {
        "L'Abergement-Clémenciat",
        "Paris 1er Arrondissement",
        "Bruys",
        "Muscourt",
        "Ajaccio",
        "Autres",
    }


def test_extraire_convertit_les_milliers_et_garde_le_nc(extrait):
    _annee, lignes = extrait
    par = {o["libelle"]: o for o in lignes}
    assert par["L'Abergement-Clémenciat"]["impot_net_euros"] == 1_000_000.0
    assert par["Paris 1er Arrondissement"]["dep_carte"] == "75"
    assert par["Bruys"]["impot_net_euros"] is None
    assert par["Bruys"]["n_foyers_imposes"] is None
    assert par["Muscourt"]["impot_net_euros"] == pytest.approx(-1_500.0)
    assert par["Ajaccio"]["dep_carte"] == "2A"
    assert par["Autres"]["dep_carte"] is None
    assert par["Autres"]["impot_net_euros"] == 10_000.0


def test_extraire_refuse_un_doublon(tmp_path):
    p = _xlsx_inline(
        tmp_path / "dup.xlsx",
        [
            [("E", "IRCOM revenus 2024")],
            [
                ("B", "010"),
                ("C", "001"),
                ("D", "A"),
                ("E", "Total"),
                ("F", "#1"),
                ("H", "#1"),
                ("I", "#1"),
            ],
            [
                ("B", "010"),
                ("C", "001"),
                ("D", "A"),
                ("E", "Total"),
                ("F", "#2"),
                ("H", "#2"),
                ("I", "#2"),
            ],
        ],
    )
    with pytest.raises(ValueError, match="dupliqu"):
        extraire(p)


def test_controler_ampleur_refuse_une_fixture_trop_petite(extrait):
    annee, lignes = extrait
    with pytest.raises(ValueError, match="communes Total"):
        controler_ampleur(annee, lignes)


def test_ecrire_db_agrege_et_metadonnees(tmp_path, extrait):
    annee, lignes = extrait
    conn = db.init_db(chemin=tmp_path / "ircom.db")
    date = ecrire_db(conn, annee, lignes)
    assert date == "2024-12-31"
    nat = conn.execute("SELECT * FROM ircom_national").fetchone()
    assert nat["n_communes"] == 6
    assert nat["n_communes_nc"] == 1
    # 1 000 000 + 2 000 000 + 0 (nc) + (-1 500) + 50 000 + 10 000
    assert nat["impot_net_euros"] == pytest.approx(3_058_500.0)
    assert nat["n_foyers"] == 480 + 1000 + 11 + 20 + 100 + 5
    paris = conn.execute(
        "SELECT * FROM ircom_departements WHERE dep_carte = '75'"
    ).fetchone()
    assert paris["impot_net_euros"] == 2_000_000.0
    hors = conn.execute(
        "SELECT COUNT(*) FROM ircom_departements WHERE dep_carte IS NULL"
    ).fetchone()[0]
    assert hors == 0
    meta = conn.execute(
        "SELECT source_id, date_donnees, lignes FROM meta_sources"
    ).fetchone()
    assert meta["source_id"] == SOURCE_ID
    assert meta["date_donnees"] == "2024-12-31"
    assert meta["lignes"] == 6
    conn.close()


def test_notes_et_ddl_sans_mots_interdits():
    from pipelines import ingest_ircom as m
    src = Path(m.__file__).read_text(encoding="utf-8").lower()
    assert "sondage" not in src
    assert "baromètre" not in src and "barometre" not in src
    assert "sondage" not in m.NOTES.lower()
    assert "baromètre" not in m.NOTES.lower()


def test_xlsx_communes_dans_zip_refuse_lambiguite(tmp_path, xlsx):
    zpath = tmp_path / "ircom.zip"
    with zipfile.ZipFile(zpath, "w") as z:
        z.write(xlsx, "ircom_2025_revenus_2024/ircom_communes_complet_revenus_2024.xlsx")
    dest = tmp_path / "out.xlsx"
    out = xlsx_communes_dans_zip(zpath, dest)
    annee, lignes = extraire(out)
    assert annee == 2024
    assert len(lignes) == 6

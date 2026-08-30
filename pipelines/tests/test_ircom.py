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
            # Secret statistique (F, H et I n.c. — mesuré live : Bruys)
            [
                ("B", "020"),
                ("C", "129"),
                ("D", "Bruys"),
                ("E", "Total"),
                ("F", "n.c."),
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
            # Contrôle C1 U+009C : cas RÉEL de la base servie au 30/08/2026
            # (« Cœuvres-et-Valsery », Aisne, dep_source 020 com_source 201).
            [
                ("B", "020"),
                ("C", "201"),
                ("D", "C\u009cuvres-et-Valsery"),
                ("E", "Total"),
                ("F", "#30"),
                ("H", "#60"),
                ("I", "#12"),
            ],
            # Contrôle C1 U+0092 : cas RÉEL, hors carte (B31 326).
            [
                ("B", "B31"),
                ("C", "326"),
                ("D", "C\u00f4te d\u0092Ivoire"),
                ("E", "Total"),
                ("F", "#7"),
                ("H", "#14"),
                ("I", "#4"),
            ],
        ],
    )


def _fixture_saine(tmp_path: Path) -> Path:
    """Même forme, mais AUCUN caractère à réparer.

    Contre-épreuve du compteur : sans elle, un compteur figé sur une constante
    non nulle passerait le test de valeur.
    """
    return _xlsx_inline(
        tmp_path / "ircom_sain.xlsx",
        [
            [("E", "IRCOM revenus 2024")],
            [
                ("B", "010"),
                ("C", "001"),
                ("D", "L'Abergement-Clémenciat"),
                ("E", "Total"),
                ("F", "#480"),
                ("H", "#1000"),
                ("I", "#200"),
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
    annee, lignes, _n = extrait
    assert annee == 2024
    assert len(lignes) == 8
    assert all(o["libelle"] != "Ambérieu-en-Bugey" for o in lignes)
    assert {o["libelle"] for o in lignes} == {
        "L'Abergement-Clémenciat",
        "Paris 1er Arrondissement",
        "Bruys",
        "Muscourt",
        "Ajaccio",
        "Autres",
        # RÉPARÉS : l'assertion porte sur la sortie propre, pas sur l'entrée.
        "Cœuvres-et-Valsery",
        "Côte d’Ivoire",
    }


def test_extraire_convertit_les_milliers_et_garde_le_nc(extrait):
    _annee, lignes, _n = extrait
    par = {o["libelle"]: o for o in lignes}
    assert par["L'Abergement-Clémenciat"]["impot_net_euros"] == 1_000_000.0
    assert par["Paris 1er Arrondissement"]["dep_carte"] == "75"
    assert par["Bruys"]["impot_net_euros"] is None
    assert par["Bruys"]["n_foyers"] is None
    assert par["Bruys"]["n_foyers_imposes"] is None
    assert par["Muscourt"]["impot_net_euros"] == pytest.approx(-1_500.0)
    assert par["Ajaccio"]["dep_carte"] == "2A"
    assert par["Autres"]["dep_carte"] is None
    assert par["Autres"]["impot_net_euros"] == 10_000.0


# ---------------------------------------------------------------------------
# Hygiène des libellés — contrôles C1 (30/08/2026)
#
# Mesure qui motive ces tests, sur la base SERVIE `app/data/france.db` :
# `ircom_communes.libelle` portait 114 lignes sur 35 156 à contrôle C1, un par
# ligne, 105 × U+009C + 4 × U+008C + 5 × U+0092 = 114. Les deux cas de la
# fixture sont RÉELS et pris dans ces 114.
#
# Épreuves de mutation que ce bloc doit tuer :
#   M1  `assainir_texte_integral` -> `assainir_texte`   -> test_..._repare_les_controles_c1
#   M2  `n_assainies += 1` retiré                       -> test_..._compte_..._par_leur_valeur
#   M3  `n_assainies` figé à une constante non nulle    -> test_..._fixture_saine
#   M4  `if libelle != brut` -> `if True`               -> test_..._compte_..._par_leur_valeur
#   M5  garde « ligne Total incomplète » retiré         -> test_..._refuse_un_libelle_vide
# ---------------------------------------------------------------------------

# Les deux libellés SOURCES, tels que l'amont les publie.
BRUT_COEUVRES = "C\u009cuvres-et-Valsery"
BRUT_IVOIRE = "C\u00f4te d\u0092Ivoire"


def test_extraire_repare_les_controles_c1_du_libelle(extrait):
    """M1. `assainir_texte` ne répare PAS les C1 : avec lui, ces deux
    assertions tombent, et c'est tout l'objet du changement."""
    _annee, lignes, _n = extrait
    par_cle = {(o["dep_source"], o["com_source"]): o["libelle"] for o in lignes}
    assert par_cle[("020", "201")] == "Cœuvres-et-Valsery"
    assert par_cle[("B31", "326")] == "Côte d\u2019Ivoire"
    # Et il n'en reste aucun, nulle part : le remède n'est pas partiel.
    assert not [
        o["libelle"]
        for o in lignes
        if any(0x80 <= ord(c) <= 0x9F for c in o["libelle"])
    ]


def test_extraire_compte_les_libelles_assainis_par_leur_valeur(extrait):
    """M2/M4. Le compteur se teste par sa VALEUR, jamais par `>= 0` : un
    compteur débranché rendrait 0 et passerait une telle assertion.

    Preuve de CHAÎNAGE, pour que la valeur ne soit pas un nombre magique :
    chaque ligne majore le compteur de 1 au plus, exactement deux lignes de la
    fixture diffèrent de leur source, et 2 est le total. Si le compteur
    comptait toutes les lignes (`if True`), il rendrait 8.
    """
    _annee, lignes, n_assainies = extrait
    brut_par_cle = {("020", "201"): BRUT_COEUVRES, ("B31", "326"): BRUT_IVOIRE}
    modifiees = [
        o
        for o in lignes
        if o["libelle"]
        != brut_par_cle.get((o["dep_source"], o["com_source"]), o["libelle"])
    ]
    assert len(modifiees) == 2
    assert n_assainies == 2
    assert n_assainies < len(lignes) == 8


def test_extraire_ne_compte_aucun_libelle_sur_une_fixture_saine(tmp_path):
    """M3. CONTRE-ÉPREUVE : sur du texte sain le compteur rend 0. Sans elle,
    un compteur figé sur 2 passerait le test précédent."""
    _annee, lignes, n_assainies = extraire(_fixture_saine(tmp_path))
    assert [o["libelle"] for o in lignes] == ["L'Abergement-Clémenciat"]
    assert n_assainies == 0


def test_extraire_refuse_un_libelle_vide(tmp_path):
    """M5. La SECONDE différence d'`assainir_texte_integral` est qu'elle rend
    `""` là où `assainir_texte` rendait `None`. Ce test fixe que le garde
    tout-ou-rien s'en moque : un libellé vide échoue toujours, et l'ingestion
    de la nuit ne peut pas écrire une commune sans nom."""
    p = _xlsx_inline(
        tmp_path / "vide.xlsx",
        [
            [("E", "IRCOM revenus 2024")],
            [
                ("B", "010"),
                ("C", "001"),
                ("D", "   "),
                ("E", "Total"),
                ("F", "#1"),
                ("H", "#1"),
                ("I", "#1"),
            ],
        ],
    )
    with pytest.raises(ValueError, match="ligne Total incomplète"):
        extraire(p)


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
    annee, lignes, _n = extrait
    with pytest.raises(ValueError, match="communes Total"):
        controler_ampleur(annee, lignes)


def test_ecrire_db_agrege_et_metadonnees(tmp_path, extrait):
    annee, lignes, _n = extrait
    conn = db.init_db(chemin=tmp_path / "ircom.db")
    date = ecrire_db(conn, annee, lignes)
    assert date == "2024-12-31"
    nat = conn.execute("SELECT * FROM ircom_national").fetchone()
    assert nat["n_communes"] == 8
    assert nat["n_communes_nc"] == 1
    # 1 000 000 + 2 000 000 + 0 (nc) + (-1 500) + 50 000 + 10 000
    #   + 60 000 (Cœuvres) + 14 000 (Côte d’Ivoire)
    assert nat["impot_net_euros"] == pytest.approx(3_132_500.0)
    assert nat["n_foyers"] == 480 + 1000 + 20 + 100 + 5 + 30 + 7
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
    assert meta["lignes"] == 8
    # Le libellé RÉPARÉ atteint bien la table : l'hygiène n'est pas perdue
    # entre `extraire` et `ecrire_db`.
    assert conn.execute(
        "SELECT libelle FROM ircom_communes "
        "WHERE dep_source = '020' AND com_source = '201'"
    ).fetchone()["libelle"] == "Cœuvres-et-Valsery"
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
    annee, lignes, _n = extraire(out)
    assert annee == 2024
    assert len(lignes) == 8

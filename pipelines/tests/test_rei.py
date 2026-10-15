"""Tests du pipeline P25 — REI (S48).

La fixture CSV est MINIMALE INVENTÉE (euros, pas des valeurs live).
Elle porte : une commune de l'Ain avec TFPB ; une occultée (E13 vide) ;
une Corse-du-Sud ; un Saint-Barthélemy hors carte ; deux communes de
la même région pour IFERREG répliqué ; P33_1 et F23 qui NE doivent PAS
s'ajouter aux totaux CFE / TEOM.
Les garde-fous d'ampleur se testent à part.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

import pytest

from pipelines import db
from pipelines.ingest_rei import (
    SOURCE_ID,
    controler_ampleur,
    csv_dans_zip,
    date_fin_annee,
    departement_carte,
    ecrire_db,
    euros_en_md,
    extraire,
)


def _csv(chemin: Path, lignes: list[dict]) -> Path:
    champs = [
        "DEP", "COM", "LIBCOM", "LIBREG",
        "E13", "E23", "E33", "F13", "F23",
        "P13", "P23", "P33", "P33_1", "P33_2",
        "B13", "H13THS", "H13LV",
        "TASCOMcom", "TASCOMgfp",
        "TIEOMC", "TIEOMS", "TIEOMG",
        "IFERCOM", "IFERGFP", "IFERDEP", "IFERREG",
        "E53", "P53TSC",
    ]
    with chemin.open("w", encoding="latin-1", newline="") as f:
        f.write(";".join(champs) + "\n")
        for o in lignes:
            f.write(";".join(str(o.get(c, "")) for c in champs) + "\n")
    return chemin


def _fixture(tmp_path: Path) -> Path:
    return _csv(
        tmp_path / "REI_2025.csv",
        [
            {
                "DEP": "01", "COM": "001", "LIBCOM": "L'Abergement",
                "LIBREG": "AUVERGNE-RHONE-ALPES",
                "E13": "1000", "E23": "10", "E33": "20",
                "F13": "80", "F23": "70",
                "P13": "5", "P23": "0", "P33": "50", "P33_1": "50", "P33_2": "0",
                "B13": "3", "H13THS": "7", "H13LV": "1",
                "TASCOMcom": "2", "TASCOMgfp": "8",
                "TIEOMG": "4",
                "IFERCOM": "1", "IFERREG": "1000",
            },
            {
                "DEP": "01", "COM": "002", "LIBCOM": "Occultée",
                "LIBREG": "AUVERGNE-RHONE-ALPES",
                "E13": "", "F13": "10", "F23": "10",
                "P33": "10", "P33_1": "10",
                "IFERREG": "1000",
            },
            {
                "DEP": "2A", "COM": "001", "LIBCOM": "Ajaccio",
                "LIBREG": "CORSE",
                "E13": "200", "F13": "30", "P33": "15",
                "IFERREG": "40",
            },
            {
                "DEP": "977", "COM": "7", "LIBCOM": "Saint-Barthelemy",
                "LIBREG": "SAINT-BARTHELEMY",
                "E13": "50", "F13": "5", "P33": "1",
                "IFERREG": "0",
            },
        ],
    )


@pytest.fixture
def csv_path(tmp_path):
    return _fixture(tmp_path)


@pytest.fixture
def extrait(csv_path):
    return extraire(csv_path, 2025)


def test_departement_carte():
    assert departement_carte("01") == "01"
    assert departement_carte("2A") == "2A"
    assert departement_carte("974") == "974"
    assert departement_carte("977") is None
    assert departement_carte("978") is None


def test_euros_en_md_divise_par_1e9_pas_1000():
    assert euros_en_md(1_000_000_000) == 1.0
    assert date_fin_annee(2025) == "2025-12-31"


def test_extraire_somme_et_pieges(extrait):
    lignes, ifer_reg = extrait
    par = {o["libelle"]: o for o in lignes}
    # TFPB = E13+E23+E33, pas une autre colonne
    assert par["L'Abergement"]["tfpb"] == 1030.0
    assert par["L'Abergement"]["teom"] == 80.0  # F13, PAS F23=70
    assert par["L'Abergement"]["_teomi"] == 4.0  # part de F13, pas en plus
    assert par["L'Abergement"]["cfe"] == 55.0  # P13+P23+P33, PAS P33_1
    assert par["L'Abergement"]["tascom"] == 10.0
    assert par["Occultée"]["tfpb"] is None
    assert par["Occultée"]["dep_carte"] == "01"
    assert par["Ajaccio"]["dep_carte"] == "2A"
    assert par["Saint-Barthelemy"]["dep_carte"] is None
    # IFER régional : une valeur par région, pas 2×1000
    assert ifer_reg["AUVERGNE-RHONE-ALPES"] == 1000.0
    assert ifer_reg["CORSE"] == 40.0
    assert ifer_reg["SAINT-BARTHELEMY"] == 0.0
    assert len(lignes) == 4


def test_extraire_refuse_un_doublon(tmp_path):
    p = _csv(
        tmp_path / "dup.csv",
        [
            {"DEP": "01", "COM": "001", "LIBCOM": "A", "E13": "1",
             "F13": "1", "P33": "1", "IFERREG": "0", "LIBREG": "X"},
            {"DEP": "01", "COM": "001", "LIBCOM": "A", "E13": "2",
             "F13": "1", "P33": "1", "IFERREG": "0", "LIBREG": "X"},
        ],
    )
    with pytest.raises(ValueError, match="dupliqu"):
        extraire(p, 2025)


def test_iferreg_divergent_refuse(tmp_path):
    p = _csv(
        tmp_path / "div.csv",
        [
            {"DEP": "01", "COM": "001", "LIBCOM": "A", "E13": "1",
             "F13": "1", "P33": "1", "IFERREG": "10", "LIBREG": "X"},
            {"DEP": "01", "COM": "002", "LIBCOM": "B", "E13": "1",
             "F13": "1", "P33": "1", "IFERREG": "11", "LIBREG": "X"},
        ],
    )
    with pytest.raises(ValueError, match="IFERREG divergent"):
        extraire(p, 2025)


def test_controler_ampleur_refuse_une_fixture_trop_petite(extrait):
    lignes, ifer_reg = extrait
    with pytest.raises(ValueError, match="communes REI"):
        controler_ampleur(2025, lignes, ifer_reg)


def test_ecrire_db_agrege_et_metadonnees(tmp_path, extrait):
    lignes, ifer_reg = extrait
    conn = db.init_db(chemin=tmp_path / "rei.db")
    date = ecrire_db(conn, 2025, lignes, ifer_reg)
    assert date == "2025-12-31"
    nat = conn.execute("SELECT * FROM rei_national").fetchone()
    assert nat["n_communes"] == 4
    assert nat["n_tfpb_nc"] == 1
    # 1030 + 0 (nc) + 200 + 50
    assert nat["tfpb"] == pytest.approx(1280.0)
    assert nat["teom"] == pytest.approx(80 + 10 + 30 + 5)
    assert nat["cfe"] == pytest.approx(55 + 10 + 15 + 1)
    assert nat["teomi"] == pytest.approx(4.0)
    # Le contrat UI (TEOMI hors du total FDL) se vérifie sur rei.ts même :
    # test_contrat_ui_total_fdl_exclut_teomi.
    assert nat["ifer_reg"] == pytest.approx(1040.0)  # 1000 + 40 + 0
    ain = conn.execute(
        "SELECT * FROM rei_departements WHERE dep_carte = '01'"
    ).fetchone()
    assert ain["n_communes"] == 2
    assert ain["n_tfpb_nc"] == 1
    assert ain["tfpb"] == pytest.approx(1030.0)
    hors = conn.execute(
        "SELECT COUNT(*) FROM rei_departements WHERE dep_carte IS NULL"
    ).fetchone()[0]
    assert hors == 0
    meta = conn.execute(
        "SELECT source_id, date_donnees, lignes FROM meta_sources"
    ).fetchone()
    assert meta["source_id"] == SOURCE_ID
    assert meta["date_donnees"] == "2025-12-31"
    assert meta["lignes"] == 4
    conn.close()


def test_notes_et_source_sans_mots_interdits():
    from pipelines import ingest_rei as m
    src = Path(m.__file__).read_text(encoding="utf-8").lower()
    assert "sondage" not in src
    assert "baromètre" not in src and "barometre" not in src
    assert "sondage" not in m.NOTES.lower()
    assert m.SOURCE_ID == "S48"


def test_csv_dans_zip_refuse_lambiguite(tmp_path, csv_path):
    zpath = tmp_path / "rei.zip"
    with zipfile.ZipFile(zpath, "w") as z:
        z.write(csv_path, "REI_2025.csv")
        z.writestr("REI_2024.csv", "DEP;COM\n")
    dest = tmp_path / "out.csv"
    with pytest.raises(ValueError, match="candidat"):
        csv_dans_zip(zpath, dest, 2025)


def test_csv_dans_zip_extrait(tmp_path, csv_path):
    zpath = tmp_path / "rei.zip"
    with zipfile.ZipFile(zpath, "w") as z:
        z.write(csv_path, "Notice.pdf")  # mauvais nom, ignoré
        z.write(csv_path, "REI_2025.csv")
    dest = tmp_path / "out.csv"
    out = csv_dans_zip(zpath, dest, 2025)
    assert out.exists()
    lignes, _ifer = extraire(out, 2025)
    assert len(lignes) == 4


def test_un_nouveau_millesime_n_est_pas_masque_par_le_cache(tmp_path, monkeypatch):
    """Constat de l'audit du 15/10/2026 : le zip REI 2025 en cache (< 7 j)
    et l'API qui annonce REI-2026. L'ancien code resservait le zip 2025 et
    levait « année CSV 2025 ≠ année zip 2026 » : `main()` rendait 1 et
    arrêtait toute l'ingestion jusqu'à expiration du cache."""
    import io
    import os
    import time
    from datetime import datetime, timezone

    import pipelines.common as common
    import pipelines.ingest_rei as rei
    from pipelines.tests.session_factice import SessionFactice

    def zip_avec(nom_csv: str) -> bytes:
        tampon = io.BytesIO()
        with zipfile.ZipFile(tampon, "w") as z:
            z.writestr(nom_csv, "DEP;COM\n")
        return tampon.getvalue()

    monkeypatch.setattr(common, "RAW_DIR", tmp_path / "raw")
    cache = tmp_path / "raw" / rei.FICHIER_ZIP
    cache.parent.mkdir(parents=True)
    cache.write_bytes(zip_avec("REI_2025.csv"))
    il_y_a_une_heure = time.time() - 3600
    os.utime(cache, (il_y_a_une_heure, il_y_a_une_heure))

    url_2026 = "https://exemple.invalid/rei_2026_fichier_notice_trace_zip"
    session = SessionFactice({
        rei.URL_API_DATASET: {"resources": [{
            "title": "REI-2026-fichier-notice-trace.zip", "format": "zip",
            "url": url_2026,
            "last_modified": datetime.now(timezone.utc).isoformat(),
        }]},
        url_2026: zip_avec("REI_2026.csv"),
    })
    monkeypatch.setattr(rei, "session_http", lambda: session)
    lu = {}
    monkeypatch.setattr(rei, "extraire", lambda chemin, annee: lu.update(
        chemin=chemin, annee=annee) or ([], {}))
    monkeypatch.setattr(rei, "controler_ampleur", lambda *a: None)
    monkeypatch.setattr(rei, "ecrire_db", lambda *a: "2026-12-31")
    monkeypatch.setattr(rei.db, "init_db", lambda: sqlite3_memoire())

    assert rei.main() == 0
    assert url_2026 in session.appels
    assert lu["annee"] == 2026 and lu["chemin"].name == "REI_2026.csv"


def sqlite3_memoire():
    import sqlite3
    return sqlite3.connect(":memory:")


# ---------------------------------------------------------------------------
# Contrat avec l'interface : le total « FDL » de rei.ts
# ---------------------------------------------------------------------------

REI_TS = Path(__file__).resolve().parents[2] / "app" / "src" / "lib" / "queries" / "rei.ts"


def _champs_nat(source: str, nom: str) -> set[str]:
    """Colonnes `nat.<x>` sommées dans `const <nom> = … ;`, en développant
    les constantes locales (`ifer`, `additionnelles`) qu'elle référence."""
    m = re.search(rf"const {nom}\s*=\s*(.*?);", source, re.S)
    assert m, f"`const {nom}` introuvable dans rei.ts"
    expr = m.group(1)
    champs = set(re.findall(r"\bnat\.(\w+)", expr))
    sans_nat = re.sub(r"\bnat\.\w+", "", expr)
    for locale in set(re.findall(r"\b([A-Za-z_]\w*)\b", sans_nat)):
        champs |= _champs_nat(source, locale)
    return champs


def test_contrat_ui_total_fdl_exclut_teomi(tmp_path, extrait):
    """TEOMI (TIEOM*) est une PART de F13 (CGI 1522 bis), pas une taxe en
    plus : le total « FDL » que rei.ts affiche somme les 14 postes de
    `rei_national` sauf `teomi`.

    L'ancienne version de ce contrôle recalculait la somme en Python et la
    comparait à elle-même (x == t + (x − t)) : vraie pour toute valeur, elle
    ne lisait pas rei.ts. Celui-ci lit l'expression réellement compilée ; il
    tue la mutation qui ajoute `nat.teomi` à `totalFdl` (ou à
    `additionnelles`) et celle qui en retire un poste."""
    source = REI_TS.read_text(encoding="utf-8")
    sommes = _champs_nat(source, "totalFdl")
    conn = db.init_db(chemin=tmp_path / "rei.db")
    ecrire_db(conn, 2025, *extrait)  # crée rei_national avec son vrai schéma
    colonnes = {
        r[1] for r in conn.execute("PRAGMA table_info(rei_national)")
        if r[2] == "REAL"
    }
    conn.close()
    assert "teomi" not in sommes
    assert sommes == colonnes - {"teomi"}
    assert len(sommes) == 14

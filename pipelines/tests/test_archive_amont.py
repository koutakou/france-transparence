"""Copies datées d'amont : hors data/raw, hors Sirene, hors zip réel.

Fixtures jetables de quelques octets. Pas de Scrutins.json.zip de 26 Mo.
"""

from __future__ import annotations

import gzip
from pathlib import Path

import pytest

from pipelines.archive_amont import (
    DEST_DEFAUT,
    SOURCES,
    SourceAmont,
    archiver_sources,
    main,
)


def _raw_minimal(tmp_path: Path) -> Path:
    raw = tmp_path / "raw"
    (raw / "parlement").mkdir(parents=True)
    (raw / "cada").mkdir(parents=True)
    (raw / "parlement" / "Scrutins.json.zip").write_bytes(b"PK\x03\x04scrutins-v1")
    (raw / "parlement" / "dosleg.zip").write_bytes(b"PK\x03\x04dosleg-v1")
    (raw / "cada" / "cada-consolide.csv").write_text("avis;texte\n1;hello\n", encoding="utf-8")
    (raw / "parlement" / "datan_deputes-active.csv").write_text(
        "mpId,score\nPA1,0.5\n", encoding="utf-8"
    )
    return raw


def test_copie_les_quatre_hors_du_cache(tmp_path):
    raw = _raw_minimal(tmp_path)
    dest = tmp_path / "amont"
    resultats = archiver_sources(raw, dest, horodatage="20260825-160000")
    assert {r.identifiant: r.action for r in resultats} == {
        "S5-SCRUTINS": "copie",
        "S6-DOSLEG": "copie",
        "S38-CADA": "copie",
        "S7-DATAN": "copie",
    }
    assert (dest / "S5-SCRUTINS" / "20260825-160000.zip").is_file()
    assert (dest / "S6-DOSLEG" / "20260825-160000.zip").is_file()
    cada = dest / "S38-CADA" / "20260825-160000.csv.gz"
    assert cada.is_file()
    with gzip.open(cada, "rb") as f:
        assert b"avis;texte" in f.read()
    assert (dest / "S7-DATAN" / "20260825-160000.csv").read_text(encoding="utf-8").startswith("mpId")
    # Hors du cache : rien écrit sous raw/.
    archives_dans_raw = list(raw.rglob("*.sha256"))
    assert archives_dans_raw == []


def test_inchange_si_meme_contenu(tmp_path):
    raw = _raw_minimal(tmp_path)
    dest = tmp_path / "amont"
    archiver_sources(raw, dest, horodatage="20260825-160000")
    second = archiver_sources(raw, dest, horodatage="20260825-170000")
    assert all(r.action == "inchange" for r in second)
    assert not (dest / "S5-SCRUTINS" / "20260825-170000.zip").exists()
    assert len(list((dest / "S5-SCRUTINS").glob("*.zip"))) == 1


def test_nouvelle_generation_si_le_contenu_change(tmp_path):
    raw = _raw_minimal(tmp_path)
    dest = tmp_path / "amont"
    archiver_sources(raw, dest, horodatage="20260825-160000")
    (raw / "parlement" / "Scrutins.json.zip").write_bytes(b"PK\x03\x04scrutins-v2")
    second = archiver_sources(raw, dest, horodatage="20260825-170000")
    actions = {r.identifiant: r.action for r in second}
    assert actions["S5-SCRUTINS"] == "copie"
    assert actions["S6-DOSLEG"] == "inchange"
    assert (dest / "S5-SCRUTINS" / "20260825-170000.zip").read_bytes().endswith(b"v2")
    assert (dest / "S5-SCRUTINS" / "20260825-160000.zip").is_file()


def test_retention_purge_les_plus_anciennes(tmp_path):
    raw = tmp_path / "raw"
    (raw / "x").mkdir(parents=True)
    dest = tmp_path / "amont"
    source = SourceAmont("T", "x/f.bin", generations=2)
    fichier = raw / "x" / "f.bin"
    for i, stamp in enumerate(("20260801-010000", "20260802-010000", "20260803-010000")):
        fichier.write_bytes(f"v{i}".encode())
        archiver_sources(raw, dest, (source,), horodatage=stamp)
    restants = sorted(p.name for p in (dest / "T").glob("*.bin"))
    assert restants == ["20260802-010000.bin", "20260803-010000.bin"]
    assert not (dest / "T" / "20260801-010000.bin").exists()
    assert not (dest / "T" / "20260801-010000.sha256").exists()


def test_refuse_d_ecrire_dans_data_raw(tmp_path):
    raw = _raw_minimal(tmp_path)
    with pytest.raises(ValueError, match="cache brut"):
        archiver_sources(raw, raw / "archives")


def test_destination_par_defaut_sur_le_volume_data():
    """Le disque racine fait 39 Go ; /data en fait 427, presque vide."""
    assert DEST_DEFAUT == Path("/data/france-transparence/amont")
    assert not str(DEST_DEFAUT).startswith("/var/backups")
    assert "data/raw" not in str(DEST_DEFAUT)


def test_sirene_n_est_pas_dans_le_manifeste():
    relatifs = {s.relatif for s in SOURCES}
    assert "parlement/Scrutins.json.zip" in relatifs
    assert "parlement/dosleg.zip" in relatifs
    assert "cada/cada-consolide.csv" in relatifs
    assert "parlement/datan_deputes-active.csv" in relatifs
    assert not any("sirene" in s.relatif.lower() for s in SOURCES)
    assert not any("decp" in s.relatif.lower() for s in SOURCES)
    assert not any("AMO10" in s.relatif for s in SOURCES)


def test_sirene_present_n_est_pas_copie(tmp_path):
    raw = _raw_minimal(tmp_path)
    (raw / "sirene").mkdir()
    (raw / "sirene" / "StockUniteLegale.parquet").write_bytes(b"PARQUET-FAKE")
    dest = tmp_path / "amont"
    archiver_sources(raw, dest, horodatage="20260825-160000")
    noms = {p.name for p in dest.iterdir()}
    assert "S5-SCRUTINS" in noms
    assert not any("sirene" in n.lower() for n in noms)
    assert list((raw / "sirene").glob("*"))  # le parquet n'a pas bougé


def test_fichier_absent_ne_fait_pas_echouer_les_autres(tmp_path):
    raw = _raw_minimal(tmp_path)
    (raw / "parlement" / "datan_deputes-active.csv").unlink()
    dest = tmp_path / "amont"
    resultats = archiver_sources(raw, dest, horodatage="20260825-160000")
    actions = {r.identifiant: r.action for r in resultats}
    assert actions["S7-DATAN"] == "absent"
    assert actions["S5-SCRUTINS"] == "copie"


def test_fichier_vide_saute(tmp_path):
    raw = _raw_minimal(tmp_path)
    (raw / "parlement" / "dosleg.zip").write_bytes(b"")
    dest = tmp_path / "amont"
    resultats = archiver_sources(raw, dest, horodatage="20260825-160000")
    assert {r.identifiant: r.action for r in resultats}["S6-DOSLEG"] == "vide"
    assert not list((dest / "S6-DOSLEG").glob("*.zip"))


def test_sans_place_saute(tmp_path):
    raw = _raw_minimal(tmp_path)
    dest = tmp_path / "amont"
    resultats = archiver_sources(
        raw, dest, horodatage="20260825-160000",
        marge_octets=1_000, libre_octets=10,
    )
    assert all(r.action == "sans-place" for r in resultats)
    assert not any(dest.rglob("*.sha256"))


def test_dest_absente_sans_creer_est_un_noop(tmp_path):
    raw = _raw_minimal(tmp_path)
    dest = tmp_path / "inexistant"
    assert archiver_sources(raw, dest, creer_dest=False) == []
    assert not dest.exists()


def test_fichiers_d_archive_sont_0600(tmp_path):
    raw = _raw_minimal(tmp_path)
    dest = tmp_path / "amont"
    archiver_sources(raw, dest, horodatage="20260825-160000")
    cible = dest / "S5-SCRUTINS" / "20260825-160000.zip"
    mode = cible.stat().st_mode & 0o777
    assert mode == 0o600
    assert (dest.stat().st_mode & 0o777) == 0o700


def test_cli_refuse_dest_dans_raw(tmp_path):
    raw = _raw_minimal(tmp_path)
    assert main(["--raw", str(raw), "--dest", str(raw / "x")]) == 2


def test_cli_copie(tmp_path):
    raw = _raw_minimal(tmp_path)
    dest = tmp_path / "amont"
    assert main(["--raw", str(raw), "--dest", str(dest)]) == 0
    assert (dest / "S5-SCRUTINS").is_dir()


def test_empreinte_vide_ne_crash_pas_on_recopie(tmp_path):
    raw = _raw_minimal(tmp_path)
    dest = tmp_path / "amont"
    archiver_sources(raw, dest, horodatage="20260825-160000")
    (dest / "S5-SCRUTINS" / "20260825-160000.sha256").write_text("", encoding="ascii")
    second = archiver_sources(raw, dest, horodatage="20260825-170000")
    actions = {r.identifiant: r.action for r in second}
    assert actions["S5-SCRUTINS"] == "copie"

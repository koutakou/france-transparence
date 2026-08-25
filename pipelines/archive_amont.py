"""Copies datées des payloads amont que `make ingest` ne peut plus reconstruire.

`data/raw` est un cache : la purge 23 h (et le TTL de cache-long) **remplace**
le fichier, elle ne le versionne pas. Deux snapshots de `france.db` sur le
même disque photographient un état déjà roulé. Si le zip 404 ou si le
producteur s'arrête, la reconstruction réimporte le trou.

Ce module copie hors de `data/raw` **seulement** les dumps qui peuvent
mourir et qui ne sont pas reconstructibles autrement :

- S5-SCRUTINS (`Scrutins.json.zip`) — déjà vu tronqué en transfert ;
- S6-DOSLEG (`dosleg.zip`) — le dump porte tout `votsen` ;
- S38-CADA (`cada-consolide.csv`) — corpus cumulatif, 198 Mo, lots ;
- S7-DATAN (`datan_deputes-active.csv`) — producteur communautaire fragile.

Une nouvelle copie n'est prise que si le SHA-256 change. Pas Sirene
(705 Mo/nuit). Pas le parquet DECP. Pas le hors-site. Pas une page
`/archives`, pas un 12ᵉ onglet. Destination par défaut : le coffre
`/data/france-transparence/amont` (volume data, 0600). Pas le
disque racine (39 Go) : `data/raw` et les releases y vivent déjà.

Si la destination n'existe pas et n'est pas créable (CI, poste de
dev), on se tait et on sort 0 : l'archivage est un filet de production,
pas une étape d'ingestion.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import os
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pipelines.common import RAW_DIR, obtenir_logger

log = obtenir_logger("archive_amont")

DEST_DEFAUT = Path("/data/france-transparence/amont")
MARGE_DISQUE_OCTETS = 3 * 1024 * 1024 * 1024  # 3 Gio, même ordre que ft-sauvegarde
CHUNK = 1 << 20


@dataclass(frozen=True)
class SourceAmont:
    identifiant: str
    relatif: str
    generations: int
    compresser: bool = False


# XOR explicite : pas Sirene, pas DECP, pas AMO10/ODSEN (même producteur
# que Scrutins/Dosleg, hors consigne de cette sous-tranche).
SOURCES: tuple[SourceAmont, ...] = (
    SourceAmont("S5-SCRUTINS", "parlement/Scrutins.json.zip", generations=14),
    SourceAmont("S6-DOSLEG", "parlement/dosleg.zip", generations=14),
    SourceAmont("S38-CADA", "cada/cada-consolide.csv", generations=3, compresser=True),
    SourceAmont("S7-DATAN", "parlement/datan_deputes-active.csv", generations=30),
)


@dataclass(frozen=True)
class Resultat:
    identifiant: str
    action: str
    octets: int = 0
    sha256: str = ""
    archive: Path | None = None


def _sha256_fichier(chemin: Path) -> str:
    h = hashlib.sha256()
    with chemin.open("rb") as f:
        for chunk in iter(lambda: f.read(CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def _hors_du_cache(dest: Path, raw: Path) -> None:
    """Refuse d'écrire l'archive dans data/raw (ce serait la purge 23 h)."""
    dest_r = dest.resolve()
    raw_r = raw.resolve()
    if dest_r == raw_r or raw_r in dest_r.parents:
        raise ValueError(
            f"destination {dest} est dans le cache brut {raw} — "
            "l'archive doit vivre hors de data/raw"
        )


def _suffixe_archive(source: SourceAmont) -> str:
    suffixe = Path(source.relatif).suffix or ".bin"
    if source.compresser:
        return suffixe + ".gz"
    return suffixe


def _lire_dernier_hash(dossier: Path) -> str | None:
    empreintes = sorted(dossier.glob("*.sha256"))
    if not empreintes:
        return None
    texte = empreintes[-1].read_text(encoding="ascii").strip()
    if not texte:
        return None
    return texte.split()[0]


def _purger_generations(dossier: Path, garder: int) -> list[str]:
    empreintes = sorted(dossier.glob("*.sha256"))
    if len(empreintes) <= garder:
        return []
    purges: list[str] = []
    for ancienne in empreintes[: len(empreintes) - garder]:
        racine = ancienne.with_suffix("")
        for reste in dossier.glob(racine.name + ".*"):
            reste.unlink(missing_ok=True)
        purges.append(racine.name)
    return purges


def _assez_de_place(dest: Path, besoin: int, marge: int, libre: int | None) -> bool:
    if libre is None:
        libre = shutil.disk_usage(dest).free
    return libre >= besoin + marge


def _ecrire_copie(source_fichier: Path, cible: Path, compresser: bool) -> None:
    tmp = cible.with_name(cible.name + ".part")
    try:
        if compresser:
            with source_fichier.open("rb") as src, gzip.open(tmp, "wb", compresslevel=6) as dst:
                shutil.copyfileobj(src, dst, length=CHUNK)
        else:
            shutil.copyfile(source_fichier, tmp)
        tmp.replace(cible)
    finally:
        tmp.unlink(missing_ok=True)


def _ecrire_empreinte(chemin: Path, sha: str, nom_origine: str) -> None:
    tmp = chemin.with_name(chemin.name + ".part")
    try:
        tmp.write_text(f"{sha}  {nom_origine}\n", encoding="ascii")
        tmp.replace(chemin)
    finally:
        tmp.unlink(missing_ok=True)


def _chmod_coffre(chemin: Path) -> None:
    os.chmod(chemin, 0o600)


def archiver_sources(
    raw: Path,
    dest: Path,
    sources: tuple[SourceAmont, ...] = SOURCES,
    *,
    horodatage: str | None = None,
    marge_octets: int = MARGE_DISQUE_OCTETS,
    libre_octets: int | None = None,
    creer_dest: bool = True,
) -> list[Resultat]:
    """Copie chaque source si le SHA-256 diffère de la dernière génération.

    `creer_dest=False` et dest absente → liste vide (no-op CI). `creer_dest=True`
    tente le mkdir ; un OSError est relancé sauf si dest n'existait pas encore
    (alors no-op, même motif que la CI).
    """
    _hors_du_cache(dest, raw)
    if not dest.exists():
        if not creer_dest:
            log.info("archivage amont sauté : %s absent", dest)
            return []
        try:
            dest.mkdir(parents=True, mode=0o700)
        except OSError as e:
            log.info("archivage amont sauté : %s (%s)", dest, e)
            return []
    else:
        dest.mkdir(parents=True, exist_ok=True)

    os.chmod(dest, 0o700)
    stamp = horodatage or datetime.now().strftime("%Y%m%d-%H%M%S")
    resultats: list[Resultat] = []

    for source in sources:
        chemin = raw / source.relatif
        if not chemin.is_file():
            log.warning("%s : fichier absent (%s), sauté", source.identifiant, chemin)
            resultats.append(Resultat(source.identifiant, "absent"))
            continue
        octets = chemin.stat().st_size
        if octets == 0:
            log.warning("%s : fichier vide, sauté", source.identifiant)
            resultats.append(Resultat(source.identifiant, "vide"))
            continue
        if not _assez_de_place(dest, octets, marge_octets, libre_octets):
            log.warning(
                "%s : disque insuffisant (%d o à copier, marge %d o), sauté",
                source.identifiant, octets, marge_octets,
            )
            resultats.append(Resultat(source.identifiant, "sans-place", octets=octets))
            continue

        sha = _sha256_fichier(chemin)
        dossier = dest / source.identifiant
        dossier.mkdir(parents=True, exist_ok=True)
        os.chmod(dossier, 0o700)
        dernier = _lire_dernier_hash(dossier)
        if dernier == sha:
            log.info("%s : inchangé (sha256=%s)", source.identifiant, sha[:12])
            resultats.append(Resultat(source.identifiant, "inchange", octets, sha))
            continue

        suffixe = _suffixe_archive(source)
        cible = dossier / f"{stamp}{suffixe}"
        empreinte = dossier / f"{stamp}.sha256"
        _ecrire_copie(chemin, cible, source.compresser)
        _ecrire_empreinte(empreinte, sha, chemin.name)
        _chmod_coffre(cible)
        _chmod_coffre(empreinte)
        purges = _purger_generations(dossier, source.generations)
        log.info(
            "%s : copie %d o sha256=%s → %s%s",
            source.identifiant, octets, sha[:12], cible.name,
            f" (purge {', '.join(purges)})" if purges else "",
        )
        resultats.append(Resultat(source.identifiant, "copie", octets, sha, cible))

    return resultats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Copies datées des dumps amont hors data/raw (pas Sirene, pas hors-site)."
    )
    parser.add_argument(
        "--dest",
        type=Path,
        default=Path(os.environ.get("FT_AMONT_ARCHIVE", str(DEST_DEFAUT))),
        help="répertoire d'archive (défaut : FT_AMONT_ARCHIVE ou le coffre local)",
    )
    parser.add_argument(
        "--raw",
        type=Path,
        default=RAW_DIR,
        help="répertoire data/raw à photographier",
    )
    parser.add_argument(
        "--exiger-dest",
        action="store_true",
        help="échec si la destination n'est pas créable (production) ; sinon no-op",
    )
    args = parser.parse_args(argv)

    try:
        resultats = archiver_sources(
            args.raw,
            args.dest,
            creer_dest=True,
        )
    except ValueError as e:
        log.error("%s", e)
        return 2

    if not resultats:
        if args.exiger_dest:
            log.error("archivage amont : destination inutilisable (%s)", args.dest)
            return 1
        return 0

    copies = sum(1 for r in resultats if r.action == "copie")
    absents = [r.identifiant for r in resultats if r.action == "absent"]
    log.info(
        "bilan amont : %d copie(s), %d inchangé(s), %d sauté(s)",
        copies,
        sum(1 for r in resultats if r.action == "inchange"),
        len(resultats) - copies - sum(1 for r in resultats if r.action == "inchange"),
    )
    # Un fichier manquant n'est pas fatal (une source en panne n'empêche
    # pas d'archiver les autres). Zéro source connue et dest exigée : si.
    if args.exiger_dest and absents and copies == 0 and not any(
        r.action == "inchange" for r in resultats
    ):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

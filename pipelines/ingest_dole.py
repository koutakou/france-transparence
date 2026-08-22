"""P19 — Dossiers législatifs DILA (S43, fonds DOLE).

Source : dumps XML sur https://echanges.dila.gouv.fr/OPENDATA/DOLE/
(index Apache, sans authentification). Catalogue data.gouv :
`dole-les-dossiers-legislatifs`, organisation « Premier ministre »,
licence `fr-lo`. La fiche producteur (PDF DILA, 18/10/2018) dit
« licence ouverte v2.0 » et impose la mention de paternité DILA.

CE PIPELINE N'EST PAS S35
-------------------------
S35 reste le seau « autres fonds DILA non ingérés » (LEGI, Debats,
RefOrgaAdminEtat). DOLE est détaché sous **S43**. Ne pas écrire
`source_id='S35'`. Ne pas élargir `jorf_textes` (fenêtre 30 JO) : un
dossier législatif vit des mois et serait purgé.

Modèle stock + incréments, rejouable parce que le Freemium pèse ~19 Mo
(pas 1 Go comme JORF) : à chaque run, Freemium le plus récent puis tous
les incréments de stamp STRICTEMENT postérieur, last-write-wins par
`dossier_id`. Les tarballs sont immuables (cache long).

`date_donnees` = max(DATE_DERNIERE_MODIFICATION) des dossiers écrits,
jamais le `last_update` data.gouv (catalogue en retard sur l'index DILA).

N'ingère PAS l'exposé des motifs ni les HTML d'échéancier : métadonnées
+ dernière étape de l'arborescence (LIEN directs de ARBORESCENCE).

TYPE n'est PAS « en navette aujourd'hui ». Un PROJET_LOI d'une
législature close reste typé projet dans le fichier. La navette affichée
est : type ∈ {PROJET_LOI, PROPOSITION_LOI, PROJET_ORDONNANCE} ET
législature = max(legislature_num). Ne pas coder le numéro 17 en dur.

Exécution : python -m pipelines.ingest_dole
Échec réseau ou archive illisible → exit 1, base intacte.
"""

from __future__ import annotations

import re
import sys
import tarfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import requests

from pipelines import db
from pipelines.common import obtenir_logger, session_http, telecharger

log = obtenir_logger("dole")

SOURCE_ID = "S43"
NOM_SOURCE = "DILA — dossiers législatifs (DOLE)"
URL_INDEX = "https://echanges.dila.gouv.fr/OPENDATA/DOLE/"
URL_CATALOGUE = "https://www.data.gouv.fr/datasets/dole-les-dossiers-legislatifs"
LICENCE = "Licence Ouverte 2.0"
FREQUENCE = "quotidienne"
LIEN_LEGIFRANCE = "https://www.legifrance.gouv.fr/dossierlegislatif/{id}"

# Freemium annuel (~19 Mo) : 30 j, ET entrée cache-long.conf (sinon la
# purge 23 h de ft-deploy annule ce TTL). Incréments immuables.
CACHE_FREEMIUM_H = 30 * 24
CACHE_IMMUABLE_H = 24 * 365 * 100

# Le stock DILA depuis ~2002 tient en milliers de dossiers, pas en dizaines.
N_MIN = 2000
N_MAX = 20000

TYPES_NAVETTE = frozenset({"PROJET_LOI", "PROPOSITION_LOI", "PROJET_ORDONNANCE"})

RE_FREEMIUM = re.compile(
    r'href="(Freemium_dole_global_(\d{8})-(\d{6})\.tar\.gz)"'
)
RE_INCREMENT = re.compile(r'href="(DOLE_(\d{8})-(\d{6})\.tar\.gz)"')

NOTES = (
    "stock DILA DOLE (Freemium + incréments, last-write-wins) ; "
    "métadonnées seulement, pas l'exposé des motifs ; "
    "TYPE n'est pas clôturé en fin de législature — la navette affichée "
    "est restreinte à la législature de numéro max ; "
    "distinct de S3 (JORFSIMPLE, fenêtre 30 JO) et de S35 (autres fonds) ; "
    "date_donnees = max(DATE_DERNIERE_MODIFICATION), jamais last_update "
    "data.gouv ; paternité DILA, Licence Ouverte 2.0"
)

_DDL = """
CREATE TABLE IF NOT EXISTS dole_dossiers (
    dossier_id           TEXT PRIMARY KEY,
    titre                TEXT NOT NULL,
    type                 TEXT NOT NULL DEFAULT '',
    date_creation        TEXT,
    date_modif           TEXT,
    legislature_num      TEXT NOT NULL DEFAULT '',
    legislature_libelle  TEXT NOT NULL DEFAULT '',
    derniere_etape       TEXT NOT NULL DEFAULT '',
    derniere_etape_url   TEXT NOT NULL DEFAULT '',
    lien_legifrance      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_dole_dossiers_type  ON dole_dossiers(type);
CREATE INDEX IF NOT EXISTS idx_dole_dossiers_leg   ON dole_dossiers(legislature_num);
CREATE INDEX IF NOT EXISTS idx_dole_dossiers_modif ON dole_dossiers(date_modif);
"""


@dataclass(frozen=True)
class Dossier:
    dossier_id: str
    titre: str
    type: str
    date_creation: str
    date_modif: str
    legislature_num: str
    legislature_libelle: str
    derniere_etape: str
    derniere_etape_url: str
    lien_legifrance: str


@dataclass(frozen=True)
class PlanTelechargement:
    freemium: str
    increments: tuple[str, ...]


def stamp_fichier(aaaammjj: str, hhmmss: str) -> str:
    """Stamp lexicographique AAAAMMJJHHMMSS — le tri est chronologique."""
    if len(aaaammjj) != 8 or len(hhmmss) != 6:
        raise ValueError(f"stamp illisible : {aaaammjj!r}-{hhmmss!r}")
    if not aaaammjj.isdigit() or not hhmmss.isdigit():
        raise ValueError(f"stamp non numérique : {aaaammjj!r}-{hhmmss!r}")
    return aaaammjj + hhmmss


def lister_index(html: str) -> PlanTelechargement:
    """Freemium le plus récent + incréments de stamp STRICTEMENT postérieur.

    Écarte PDF, DTD, incréments antérieurs au Freemium (le stock les
    contient déjà). Plusieurs Freemium : on garde le stamp max.
    """
    freemiums = [
        (nom, stamp_fichier(jour, heure))
        for nom, jour, heure in RE_FREEMIUM.findall(html)
    ]
    if not freemiums:
        raise ValueError("aucun Freemium DOLE dans l'index (format changé ?)")
    freemium_nom, freemium_stamp = max(freemiums, key=lambda x: x[1])

    increments: list[tuple[str, str]] = []
    vus: set[str] = set()
    for nom, jour, heure in RE_INCREMENT.findall(html):
        if nom in vus:
            continue
        vus.add(nom)
        st = stamp_fichier(jour, heure)
        if st > freemium_stamp:
            increments.append((nom, st))
    increments.sort(key=lambda x: x[1])
    return PlanTelechargement(
        freemium=freemium_nom,
        increments=tuple(n for n, _ in increments),
    )


def _texte(el: ET.Element | None, tag: str) -> str:
    if el is None:
        return ""
    return (el.findtext(tag) or "").strip()


def parse_dossier(xml_bytes: bytes) -> Dossier | None:
    """Métadonnées d'un DOSSIER_LEGISLATIF. None si ID ou titre manquant.

    La dernière étape est le dernier LIEN *direct* de ARBORESCENCE, pas un
    lien niché dans un NIVEAU (rapports, débats). TYPE vide est conservé
    vide : trois lois 2008 n'ont pas de TYPE dans le fichier, on ne le
    déduit pas du titre.
    """
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return None
    if root.tag != "DOSSIER_LEGISLATIF":
        return None
    comm = root.find("META/META_COMMUN")
    mdl = root.find("META/META_DOSSIER_LEGISLATIF")
    dossier_id = _texte(comm, "ID")
    titre = _texte(mdl, "TITRE")
    if not dossier_id or not titre:
        return None
    leg = mdl.find("LEGISLATURE") if mdl is not None else None
    arb = root.find("CONTENU/ARBORESCENCE")
    last_lib, last_url = "", ""
    if arb is not None:
        directs = [c for c in arb if c.tag == "LIEN"]
        if directs:
            last_lib = (directs[-1].get("libelle") or "").strip()
            last_url = (directs[-1].get("lien") or "").strip()
    return Dossier(
        dossier_id=dossier_id,
        titre=titre,
        type=_texte(mdl, "TYPE"),
        date_creation=_texte(mdl, "DATE_CREATION"),
        date_modif=_texte(mdl, "DATE_DERNIERE_MODIFICATION"),
        legislature_num=_texte(leg, "NUMERO"),
        legislature_libelle=_texte(leg, "LIBELLE"),
        derniere_etape=last_lib,
        derniere_etape_url=last_url,
        lien_legifrance=LIEN_LEGIFRANCE.format(id=dossier_id),
    )


def appliquer_tarball(chemin: Path, corpus: dict[str, Dossier]) -> int:
    """Applique un tar.gz DOLE : last-write-wins par dossier_id. Retourne n XML lus."""
    lus = 0
    with tarfile.open(chemin, "r:gz") as tf:
        for membre in tf.getmembers():
            if not membre.isfile() or not membre.name.endswith(".xml"):
                continue
            f = tf.extractfile(membre)
            if f is None:
                continue
            lus += 1
            dossier = parse_dossier(f.read())
            if dossier is None:
                continue
            corpus[dossier.dossier_id] = dossier
    return lus


def legislature_courante(dossiers: list[Dossier]) -> tuple[str, str]:
    """Législature de numéro max parmi les numéros entièrement numériques.

    Ne code pas « 17 ». Un dossier sans numéro (3 ordonnances 2024) est ignoré.
    """
    meilleures: list[tuple[int, str, str]] = []
    for d in dossiers:
        if d.legislature_num.isdigit():
            meilleures.append(
                (int(d.legislature_num), d.legislature_num, d.legislature_libelle)
            )
    if not meilleures:
        raise ValueError("aucune législature numérotée dans le corpus")
    _, num, lib = max(meilleures, key=lambda x: x[0])
    return num, lib


def est_en_navette(d: Dossier, legislature_num: str) -> bool:
    """Navette = type ouvert ET législature courante. Pas un TYPE seul."""
    return d.type in TYPES_NAVETTE and d.legislature_num == legislature_num


def controler_ampleur(n: int) -> None:
    if not (N_MIN <= n <= N_MAX):
        raise ValueError(
            f"volume DOLE hors bornes ({n}, attendu {N_MIN}–{N_MAX}) : "
            " Freemium manquant ou index incomplet"
        )


def ecrire_db(conn, dossiers: list[Dossier]) -> None:
    """DDL + DELETE/INSERT transactionnel + meta S43. N'écrit aucune table jorf_*."""
    if not dossiers:
        raise ValueError("aucun dossier à écrire")
    dates = [d.date_modif for d in dossiers if d.date_modif]
    if not dates:
        raise ValueError("aucune DATE_DERNIERE_MODIFICATION : date_donnees impossible")
    date_donnees = max(dates)

    conn.executescript(_DDL)
    with conn:
        conn.execute("DELETE FROM dole_dossiers")
        conn.executemany(
            """
            INSERT INTO dole_dossiers (
                dossier_id, titre, type, date_creation, date_modif,
                legislature_num, legislature_libelle,
                derniere_etape, derniere_etape_url, lien_legifrance
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    d.dossier_id,
                    d.titre,
                    d.type,
                    d.date_creation or None,
                    d.date_modif or None,
                    d.legislature_num,
                    d.legislature_libelle,
                    d.derniere_etape,
                    d.derniere_etape_url,
                    d.lien_legifrance,
                )
                for d in dossiers
            ],
        )

    db.upsert_meta(
        conn,
        source_id=SOURCE_ID,
        nom=NOM_SOURCE,
        url=URL_INDEX,
        licence=LICENCE,
        frequence=FREQUENCE,
        date_donnees=date_donnees,
        lignes=len(dossiers),
        notes=NOTES,
    )


def _telecharger_plan(
    plan: PlanTelechargement, session: requests.Session
) -> tuple[Path, list[Path]]:
    freemium = telecharger(
        URL_INDEX + plan.freemium,
        f"dole/{plan.freemium}",
        max_age_heures=CACHE_FREEMIUM_H,
        session=session,
    )
    incs: list[Path] = []
    for nom in plan.increments:
        incs.append(
            telecharger(
                URL_INDEX + nom,
                f"dole/{nom}",
                max_age_heures=CACHE_IMMUABLE_H,
                session=session,
            )
        )
    return freemium, incs


def main() -> int:
    session = session_http()
    try:
        log.info("index: %s", URL_INDEX)
        r = session.get(URL_INDEX, timeout=60)
        r.raise_for_status()
        # L'index Apache est annoncé charset=ISO-8859-1 ; les noms de
        # fichiers sont ASCII, le décodage ne change rien au listage.
        html = r.content.decode("iso-8859-1", errors="replace")
        plan = lister_index(html)
    except (requests.RequestException, ValueError) as exc:
        log.error("échec sur l'index DOLE: %s", exc)
        return 1

    log.info(
        "Freemium %s + %d incréments (%s → %s)",
        plan.freemium,
        len(plan.increments),
        plan.increments[0] if plan.increments else "—",
        plan.increments[-1] if plan.increments else "—",
    )

    try:
        chemin_free, chemins_inc = _telecharger_plan(plan, session)
    except requests.RequestException as exc:
        log.error("échec réseau: %s", exc)
        return 1

    corpus: dict[str, Dossier] = {}
    try:
        n_free = appliquer_tarball(chemin_free, corpus)
        n_inc = 0
        for chemin in chemins_inc:
            n_inc += appliquer_tarball(chemin, corpus)
    except (tarfile.TarError, OSError) as exc:
        log.error("archive illisible: %s", exc)
        return 1

    dossiers = list(corpus.values())
    try:
        controler_ampleur(len(dossiers))
    except ValueError as exc:
        log.error("%s", exc)
        return 1

    conn = db.init_db()
    try:
        ecrire_db(conn, dossiers)
    except Exception as exc:
        log.error("écriture refusée: %s", exc)
        conn.close()
        return 1

    leg_num, leg_lib = legislature_courante(dossiers)
    n_navette = sum(1 for d in dossiers if est_en_navette(d, leg_num))
    date_donnees = max(d.date_modif for d in dossiers if d.date_modif)
    log.info(
        "terminé: %d XML Freemium, %d XML incréments, %d dossiers uniques, "
        "navette %s (%s) = %d, date_donnees=%s",
        n_free,
        n_inc,
        len(dossiers),
        leg_lib or leg_num,
        leg_num,
        n_navette,
        date_donnees,
    )
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

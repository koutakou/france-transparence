"""P6 — Journal officiel « Lois et décrets » (source S3, dumps DILA JORFSIMPLE).

Alimente le module UI « Documents/JO » : flux quotidien des textes publiés au
JO, filtre nominations, sparkline par jour et par nature.

Source (docs/SOURCES.md S3, docs/recherche/07-documents-juridique.md) :
- index HTML `https://echanges.dila.gouv.fr/OPENDATA/JORFSIMPLE/` (sans auth,
  Licence Ouverte fr-lo) ; l'URL des tarballs n'est PAS prédictible → on parse
  l'index ;
- deux livraisons par jour : la nocturne (~00h20-00h45, 76-440 Ko) contient le
  JO du jour, celle du soir (~21h-22h45, 2,8-13 Mo) réécrit l'historique et
  est IGNORÉE ici ; des correctifs isolés tombent en matinée ou en début
  d'après-midi et réécrivent des textes de n'importe quelle année : IGNORÉS
  aussi (règle : heure < HEURE_MAX_NOCTURNE, une livraison par jour) ;
  jours sans JO possibles ;
- un tarball nocturne = 1 sommaire `JORFCONT*.xml` + N textes `JORFTEXT*.xml`
  autocontenus (UTF-8), sous `<stamp>/jorf/simple/JORF/CONT/…`.

Tables créées (CREATE TABLE IF NOT EXISTS, réexécution sans doublons) :

- jorf_textes — un texte publié au JO (fenêtre : les ~30 derniers JO parus).
  Un texte n'entre que s'il paraît au JO du jour de sa livraison (ou de la
  veille) : un texte ancien réécrit ne peut pas élargir la fenêtre.
  Les textes hors fenêtre sont copiés vers jorf_textes_archive (table
  NOUVELLE, non servie) avant le DELETE.
- jorf_textes_archive — même grain + archive_le ; pas un ALTER de
  jorf_textes.
    texte_id        TEXT PK   id JORFTEXT… (clé d'idempotence)
    conteneur_id    TEXT      id JORFCONT… du JO porteur
    num_jo          TEXT      numéro du JO (ex. '0192')
    date_publi      TEXT      date de publication ISO (ex. '2026-08-19')
    date_texte      TEXT      date de signature du texte (ISO, nullable)
    nature          TEXT      LOI / DECRET / ARRETE / DECISION / AVIS / …
    nor             TEXT      numéro NOR (nullable)
    titre           TEXT      titre complet (TITREFULL)
    ministere       TEXT      ministère/émetteur (XML texte, sinon sommaire)
    rubrique        TEXT      chemin du sommaire officiel, ex. « Décrets,
                              arrêtés, circulaires > Mesures nominatives >
                              Premier ministre » (nullable)
    is_nomination   INTEGER   1 si la rubrique contient « Mesures nominatives »
    lien_legifrance TEXT      https://www.legifrance.gouv.fr/jorf/id/{texte_id}
    id_eli          TEXT      URL ELI fournie par la DILA (souvent absente)
    num_sequence    INTEGER   ordre du texte dans le JO (nullable)

- jorf_par_jour_nature — agrégat sparkline, reconstruit à chaque run
    date_publi TEXT, nature TEXT, nb INTEGER   (PK date_publi+nature)

- jorf_nominations_ministere — nominations par ministère sur la fenêtre,
  reconstruit à chaque run
    ministere TEXT PK, nb INTEGER

meta_sources : source_id 'S3', date_donnees = date du JO le plus récent ingéré.

Exécution : `python -m pipelines.ingest_jorf [--jours 30]`
Échec réseau ou archive illisible → exit 1 (aucune donnée inventée).
"""

from __future__ import annotations

import argparse
import re
import sys
import tarfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

from pipelines import db
from pipelines.archive_fenetre import archiver_sortie_fenetre
from pipelines.common import obtenir_logger, session_http, telecharger

log = obtenir_logger("jorf")

URL_JORFSIMPLE = "https://echanges.dila.gouv.fr/OPENDATA/JORFSIMPLE/"
LIEN_LEGIFRANCE = "https://www.legifrance.gouv.fr/jorf/id/{id}"

# Nom exact des tarballs de livraison (index Apache, filenames ASCII).
RE_LIVRAISON = re.compile(r'href="(JORFSIMPLE_(\d{8})-(\d{6})\.tar\.gz)"')

# Livraison nocturne (~00h20-00h45 constaté, parfois jusqu'à 04h) = JO du jour.
# Livraison du soir (~21h-22h45) = réécritures rétroactives, à ignorer.
# Index relu le 15/10/2026 : aucune nocturne après 04h21 depuis juillet 2025,
# et des correctifs isolés à 07h04, 10h14, 10h49, 10h54, 12h29…
# Celui du 01/10/2026 à 10h54 réécrivait un décret paru au JO du 27/11/2007 :
# admis par l'ancien seuil de 12 h, il avait reculé la fenêtre de dix-neuf ans.
HEURE_MAX_NOCTURNE = 6

# Un texte livré la nuit du jour J paraît au JO du jour J (mesuré sur les 30
# nocturnes du 12/09 au 15/10/2026 : aucune exception). La veille est tolérée ;
# plus ancien, c'est une réécriture, écartée et comptée.
JOURS_TOLERES_AVANT_LIVRAISON = 1

# Les tarballs publiés sont immuables : présent en cache = jamais retéléchargé.
CACHE_IMMUABLE_H = 24 * 365 * 100

RUBRIQUE_NOMINATIONS = "mesures nominatives"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jorf_textes (
    texte_id        TEXT PRIMARY KEY,
    conteneur_id    TEXT,
    num_jo          TEXT,
    date_publi      TEXT NOT NULL,
    date_texte      TEXT,
    nature          TEXT,
    nor             TEXT,
    titre           TEXT NOT NULL,
    ministere       TEXT,
    rubrique        TEXT,
    is_nomination   INTEGER NOT NULL DEFAULT 0,
    lien_legifrance TEXT NOT NULL,
    id_eli          TEXT,
    num_sequence    INTEGER
);
CREATE INDEX IF NOT EXISTS idx_jorf_textes_date       ON jorf_textes(date_publi);
CREATE INDEX IF NOT EXISTS idx_jorf_textes_nature     ON jorf_textes(nature);
CREATE INDEX IF NOT EXISTS idx_jorf_textes_nomination ON jorf_textes(is_nomination);

CREATE TABLE IF NOT EXISTS jorf_textes_archive (
    texte_id        TEXT PRIMARY KEY,
    conteneur_id    TEXT,
    num_jo          TEXT,
    date_publi      TEXT NOT NULL,
    date_texte      TEXT,
    nature          TEXT,
    nor             TEXT,
    titre           TEXT NOT NULL,
    ministere       TEXT,
    rubrique        TEXT,
    is_nomination   INTEGER NOT NULL DEFAULT 0,
    lien_legifrance TEXT NOT NULL,
    id_eli          TEXT,
    num_sequence    INTEGER,
    archive_le      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_jorf_textes_archive_date
    ON jorf_textes_archive(date_publi);

CREATE TABLE IF NOT EXISTS jorf_par_jour_nature (
    date_publi TEXT NOT NULL,
    nature     TEXT NOT NULL,
    nb         INTEGER NOT NULL,
    PRIMARY KEY (date_publi, nature)
);

CREATE TABLE IF NOT EXISTS jorf_nominations_ministere (
    ministere TEXT PRIMARY KEY,
    nb        INTEGER NOT NULL
);
"""

# ---------------------------------------------------------------------------
# Index des livraisons
# ---------------------------------------------------------------------------


def livraisons_nocturnes(html: str) -> list[str]:
    """Noms des tarballs de livraison nocturne (JO du jour), ordre chronologique.

    Écarte les livraisons du soir et les correctifs de matinée ou de
    mi-journée (heure >= HEURE_MAX_NOCTURNE), les Freemium et les PDF : seule
    la livraison de la nuit du jour J contient le JO du jour J (fiche S3).
    Une seule livraison par jour, la plus précoce : chaque nocturne compte
    pour un JO dans la fenêtre de `--jours`.
    """
    par_jour: dict[str, str] = {}
    for nom, aaaammjj, hhmmss in RE_LIVRAISON.findall(html):
        if int(hhmmss[:2]) >= HEURE_MAX_NOCTURNE:
            continue
        # Le stamp AAAAMMJJ-HHMMSS rend le tri lexicographique chronologique.
        if aaaammjj not in par_jour or nom < par_jour[aaaammjj]:
            par_jour[aaaammjj] = nom
    return sorted(par_jour.values())


def jour_de_livraison(nom_tarball: str) -> date:
    """Date du stamp d'un tarball JORFSIMPLE_AAAAMMJJ-HHMMSS.tar.gz."""
    m = re.fullmatch(r"JORFSIMPLE_(\d{8})-\d{6}\.tar\.gz", nom_tarball)
    if not m:
        raise ValueError(f"nom de livraison illisible : {nom_tarball!r}")
    return datetime.strptime(m.group(1), "%Y%m%d").date()


# ---------------------------------------------------------------------------
# Parseurs XML (fichiers autocontenus JORFSIMPLE)
# ---------------------------------------------------------------------------


@dataclass
class SommaireJO:
    """Sommaire officiel d'un JO (fichier JORFCONT*.xml, racine <JO>)."""

    conteneur_id: str
    num_jo: str | None
    date_publi: str | None
    titre: str | None
    # id JORFTEXT → chemin des rubriques (TITRE_TM niv >= 2), ordre du sommaire
    rubriques: dict[str, list[str]] = field(default_factory=dict)


def _texte_ou_none(racine: ET.Element, balise: str) -> str | None:
    v = racine.findtext(balise)
    v = (v or "").strip()
    return v or None


def parser_sommaire(xml_octets: bytes) -> SommaireJO:
    """Parse un JORFCONT*.xml : métadonnées du JO + rubrique de chaque texte."""
    racine = ET.fromstring(xml_octets)
    som = SommaireJO(
        conteneur_id=_texte_ou_none(racine, "ID") or "",
        num_jo=_texte_ou_none(racine, "NUM"),
        date_publi=_texte_ou_none(racine, "DATE_PUBLI"),
        titre=_texte_ou_none(racine, "TITRE"),
    )

    def _descendre(tm: ET.Element, chemin: list[str]) -> None:
        titre_tm = (tm.findtext("TITRE_TM") or "").strip()
        # Le TM niv="1" est l'ombrelle « Journal officiel "Lois et Décrets" » :
        # la rubrique utile commence au niveau 2.
        niv = tm.get("niv")
        if titre_tm and (niv is None or niv != "1"):
            chemin = chemin + [titre_tm]
        for enfant in tm:
            if enfant.tag == "LIEN_TXT":
                idtxt = enfant.get("idtxt")
                if idtxt:
                    som.rubriques[idtxt] = chemin
            elif enfant.tag == "TM":
                _descendre(enfant, chemin)

    structure = racine.find("STRUCTURE_TXT")
    if structure is not None:
        for tm in structure.findall("TM"):
            _descendre(tm, [])
    return som


def parser_texte(xml_octets: bytes) -> dict | None:
    """Parse un JORFTEXT*.xml autocontenu (racine <TEXTE>) → dict de champs.

    Retourne None si la racine n'est pas <TEXTE> ou si l'ID manque.
    """
    racine = ET.fromstring(xml_octets)
    if racine.tag != "TEXTE":
        return None
    texte_id = _texte_ou_none(racine, "ID")
    if not texte_id:
        return None
    origine = racine.find("ORIGINE_PUBLI")
    num_seq = _texte_ou_none(racine, "NUM_SEQUENCE")
    return {
        "texte_id": texte_id,
        "conteneur_id": origine.get("id") if origine is not None else None,
        "num_jo": _texte_ou_none(racine, "NUM_PARUTION"),
        "date_publi": _texte_ou_none(racine, "DATE_PUBLI"),
        "date_texte": _texte_ou_none(racine, "DATE_TEXTE"),
        "nature": _texte_ou_none(racine, "NATURE"),
        "nor": _texte_ou_none(racine, "NOR"),
        "titre": _texte_ou_none(racine, "TITREFULL")
        or _texte_ou_none(racine, "TITRE"),
        "ministere": _texte_ou_none(racine, "MINISTERE"),
        "id_eli": _texte_ou_none(racine, "ID_ELI"),
        "num_sequence": int(num_seq) if num_seq and num_seq.isdigit() else None,
    }


def est_nomination(chemin: list[str]) -> bool:
    """Vrai si le chemin de rubriques passe par « Mesures nominatives »."""
    return any(RUBRIQUE_NOMINATIONS == c.strip().lower() for c in chemin)


def ministere_du_chemin(chemin: list[str]) -> str | None:
    """Ministère porté par le sommaire : composant suivant « Mesures nominatives »."""
    for i, c in enumerate(chemin):
        if c.strip().lower() == RUBRIQUE_NOMINATIONS and i + 1 < len(chemin):
            return chemin[i + 1]
    return None


def construire_lien(texte_id: str) -> str:
    """Lien Légifrance public d'un texte (la collecte y est bloquée, pas la consultation)."""
    return LIEN_LEGIFRANCE.format(id=texte_id)


# ---------------------------------------------------------------------------
# Ingestion d'un tarball
# ---------------------------------------------------------------------------

_UPSERT = """
INSERT INTO jorf_textes
    (texte_id, conteneur_id, num_jo, date_publi, date_texte, nature, nor,
     titre, ministere, rubrique, is_nomination, lien_legifrance, id_eli,
     num_sequence)
VALUES (:texte_id, :conteneur_id, :num_jo, :date_publi, :date_texte, :nature,
        :nor, :titre, :ministere, :rubrique, :is_nomination, :lien_legifrance,
        :id_eli, :num_sequence)
ON CONFLICT(texte_id) DO UPDATE SET
    conteneur_id    = excluded.conteneur_id,
    num_jo          = excluded.num_jo,
    date_publi      = excluded.date_publi,
    date_texte      = excluded.date_texte,
    nature          = excluded.nature,
    nor             = excluded.nor,
    titre           = excluded.titre,
    ministere       = excluded.ministere,
    rubrique        = excluded.rubrique,
    is_nomination   = excluded.is_nomination,
    lien_legifrance = excluded.lien_legifrance,
    id_eli          = excluded.id_eli,
    num_sequence    = excluded.num_sequence
"""


def _est_xml_cont(nom: str) -> bool:
    return "/jorf/simple/JORF/CONT/" in nom and nom.endswith(".xml")


def ingerer_tarball(chemin_tar: Path, conn) -> tuple[int, list[str]]:
    """Ingère un tarball JORFSIMPLE dans jorf_textes (upsert, clé JORFTEXT).

    Retourne (nb de textes upsertés, dates de publication des JO retenus).
    Lecture en mémoire membre par membre : rien n'est extrait sur disque.

    Seuls entrent les JO parus le jour du stamp de la livraison, ou la veille
    (JOURS_TOLERES_AVANT_LIVRAISON). Un sommaire ou un texte plus ancien est
    une réécriture : écarté, compté et journalisé à chaque appel, zéro compris.
    C'est ce qui borne la fenêtre, quel que soit le filtre horaire en amont.
    """
    jour = jour_de_livraison(chemin_tar.name)
    plancher = (jour - timedelta(days=JOURS_TOLERES_AVANT_LIVRAISON)).isoformat()
    plafond = jour.isoformat()

    def _dans_la_livraison(d: str | None) -> bool:
        return d is not None and plancher <= d <= plafond

    sommaires: dict[str, SommaireJO] = {}   # conteneur_id → sommaire
    rubriques: dict[str, list[str]] = {}    # idtxt → chemin de rubriques
    textes: list[dict] = []

    with tarfile.open(chemin_tar, "r:gz") as tar:
        membres = [
            m for m in tar.getmembers() if m.isfile() and _est_xml_cont(m.name)
        ]
        # Les sommaires d'abord : ils portent la rubrique de chaque texte.
        for m in sorted(
            membres,
            key=lambda m: not m.name.rsplit("/", 1)[-1].startswith("JORFCONT"),
        ):
            flux = tar.extractfile(m)
            if flux is None:
                continue
            octets = flux.read()
            base = m.name.rsplit("/", 1)[-1]
            if base.startswith("JORFCONT"):
                som = parser_sommaire(octets)
                if som.conteneur_id:
                    sommaires[som.conteneur_id] = som
                    rubriques.update(som.rubriques)
            elif base.startswith("JORFTEXT"):
                t = parser_texte(octets)
                if t is not None:
                    textes.append(t)

    dates_jo = sorted(
        {s.date_publi for s in sommaires.values() if _dans_la_livraison(s.date_publi)}
    )
    hors_livraison: list[str] = []

    lignes = []
    for t in textes:
        chemin = rubriques.get(t["texte_id"], [])
        som = sommaires.get(t["conteneur_id"] or "")
        # Repli sur le sommaire pour les champs absents du XML texte —
        # toujours de la donnée source, jamais fabriquée.
        if not t["date_publi"] and som:
            t["date_publi"] = som.date_publi
        if not t["num_jo"] and som:
            t["num_jo"] = som.num_jo
        if not t["date_publi"]:
            log.warning("texte sans date de publication, écarté: %s", t["texte_id"])
            continue
        if not t["titre"]:
            log.warning("texte sans titre, écarté: %s", t["texte_id"])
            continue
        if not _dans_la_livraison(t["date_publi"]):
            hors_livraison.append(f'{t["texte_id"]} (JO du {t["date_publi"]})')
            continue
        t["rubrique"] = " > ".join(chemin) if chemin else None
        t["is_nomination"] = 1 if est_nomination(chemin) else 0
        if not t["ministere"]:
            t["ministere"] = ministere_du_chemin(chemin)
        t["lien_legifrance"] = construire_lien(t["texte_id"])
        lignes.append(t)

    log.info(
        "%s : %d texte(s) hors du JO de la livraison (%s → %s) écarté(s)%s",
        chemin_tar.name, len(hors_livraison), plancher, plafond,
        f" : {', '.join(hors_livraison)}" if hors_livraison else "",
    )
    conn.executemany(_UPSERT, lignes)
    conn.commit()
    return len(lignes), dates_jo


# ---------------------------------------------------------------------------
# Agrégats et fenêtre
# ---------------------------------------------------------------------------


COLONNES_JORF_TEXTES = (
    "texte_id", "conteneur_id", "num_jo", "date_publi", "date_texte",
    "nature", "nor", "titre", "ministere", "rubrique", "is_nomination",
    "lien_legifrance", "id_eli", "num_sequence",
)


def archiver_et_purger_jorf(conn, debut_fenetre: str, archive_le: str) -> int:
    """Copie puis DELETE les textes dont date_publi < début de fenêtre."""
    n = archiver_sortie_fenetre(
        conn,
        source="jorf_textes",
        archive="jorf_textes_archive",
        colonnes=COLONNES_JORF_TEXTES,
        where="date_publi < ?",
        params=(debut_fenetre,),
        archive_le=archive_le,
    )
    conn.execute(
        "DELETE FROM jorf_textes WHERE date_publi < ?", (debut_fenetre,)
    )
    return n


def reconstruire_agregats(conn) -> None:
    """Reconstruit les deux tables d'agrégats depuis jorf_textes (déterministe)."""
    conn.execute("DELETE FROM jorf_par_jour_nature")
    conn.execute(
        """
        INSERT INTO jorf_par_jour_nature (date_publi, nature, nb)
        SELECT date_publi, COALESCE(nature, ''), count(*)
        FROM jorf_textes GROUP BY date_publi, COALESCE(nature, '')
        """
    )
    conn.execute("DELETE FROM jorf_nominations_ministere")
    conn.execute(
        """
        INSERT INTO jorf_nominations_ministere (ministere, nb)
        SELECT ministere, count(*)
        FROM jorf_textes
        WHERE is_nomination = 1 AND ministere IS NOT NULL
        GROUP BY ministere
        """
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Ingestion du Journal officiel (dumps DILA JORFSIMPLE)."
    )
    ap.add_argument(
        "--jours",
        type=int,
        default=30,
        help="nombre de JO (livraisons nocturnes) à conserver (défaut : 30)",
    )
    args = ap.parse_args(argv)

    session = session_http()
    try:
        log.info("index: %s", URL_JORFSIMPLE)
        r = session.get(URL_JORFSIMPLE, timeout=60)
        r.raise_for_status()
    except requests.RequestException as exc:
        log.error("échec réseau sur l'index JORFSIMPLE: %s", exc)
        return 1

    nocturnes = livraisons_nocturnes(r.text)
    if not nocturnes:
        log.error("aucune livraison nocturne trouvée dans l'index (format changé ?)")
        return 1
    selection = nocturnes[-args.jours:]
    log.info(
        "%d livraisons nocturnes à l'index, %d retenues (%s → %s)",
        len(nocturnes), len(selection), selection[0], selection[-1],
    )

    conn = db.init_db()
    conn.executescript(_SCHEMA)
    conn.commit()

    total, toutes_dates = 0, []
    for nom in selection:
        try:
            chemin = telecharger(
                URL_JORFSIMPLE + nom,
                f"jorf/{nom}",
                max_age_heures=CACHE_IMMUABLE_H,  # tarballs immuables
                session=session,
            )
        except requests.RequestException as exc:
            log.error("échec réseau sur %s: %s", nom, exc)
            conn.close()
            return 1
        try:
            n, dates_jo = ingerer_tarball(chemin, conn)
        except (tarfile.TarError, ET.ParseError, OSError) as exc:
            log.error("archive illisible %s: %s", nom, exc)
            conn.close()
            return 1
        total += n
        toutes_dates.extend(dates_jo)
        log.info("%s: %d textes (JO du %s)", nom, n, ", ".join(dates_jo) or "?")

    if not toutes_dates:
        log.error("aucun JO ingéré : rien à publier")
        conn.close()
        return 1

    # Fenêtre glissante : la table ne garde que les JO couverts par ce run.
    debut_fenetre = min(toutes_dates)
    n_arch = archiver_et_purger_jorf(
        conn, debut_fenetre, date.today().isoformat()
    )
    if n_arch:
        log.info(
            "fenêtre %s → : %d textes plus anciens archivés puis purgés",
            debut_fenetre, n_arch,
        )

    reconstruire_agregats(conn)

    date_donnees = max(toutes_dates)
    lignes = conn.execute("SELECT count(*) FROM jorf_textes").fetchone()[0]
    db.upsert_meta(
        conn,
        source_id="S3",
        nom="DILA — Journal officiel « Lois et décrets » (JORFSIMPLE)",
        url=URL_JORFSIMPLE,
        licence="Licence Ouverte (fr-lo)",
        frequence="quotidienne",
        date_donnees=date_donnees,
        lignes=lignes,
        notes=f"{len(selection)} livraisons nocturnes, fenêtre {debut_fenetre} → {date_donnees}",
    )
    log.info(
        "terminé: %d textes upsertés, %d en table, JO le plus récent: %s",
        total, lignes, date_donnees,
    )
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

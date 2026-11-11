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

- jorf_textes — un texte publié au JO (fenêtre : les `--jours` derniers JO
  PRÉSENTS EN BASE après l'ingestion, 30 par défaut — pas « ce que l'index
  liste encore » : voir « Index réduit » plus bas).
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

Serveur DILA injoignable (index ou tarball) → secours : RIEN n'est écrit.
Les tables jorf_* restent celles du dernier cycle réussi et la ligne S3 de
meta_sources garde sa date : la fraîcheur affichée reste vraie (exit 0,
WARNING). Tous les tarballs sont téléchargés AVANT la première écriture :
une panne en cours de route ne laisse pas une fenêtre à moitié renouvelée.
Base neuve sans JORF à reprendre, archive illisible ou index au format
inconnu → exit 1 (aucune donnée inventée).

Index réduit. Quand la DILA régénère son stock (`Freemium_jorf_simple_*`,
de l'ordre du Go), elle retire de l'index les livraisons antérieures :
constaté le 08/11/2026, l'index est passé de plusieurs centaines de
nocturnes à zéro, puis à une de plus par JO. Trois conséquences :
- index joignable SANS nocturne (le lendemain de la régénération) → même
  secours que ci-dessus, pas un échec : le format est reconnu, il n'y a
  simplement rien de neuf à lire ;
- la purge ne suit pas l'index : une base qui porte déjà ses JO les garde
  tant qu'ils sont parmi les `--jours` derniers JO en base ;
- ce qu'un cycle a archivé À TORT revient : avant de calculer la fenêtre,
  les textes de jorf_textes_archive dont le JO compte parmi les `--jours`
  derniers JO connus (table + archive) sont réintégrés, sans écraser un
  texte déjà en table, et quittent l'archive. Compté à chaque cycle ;
- une base neuve (CI, premier déploiement) n'a que ce que l'index liste :
  la fenêtre est RÉDUITE et la note de meta_sources le dit, compteur et
  date à l'appui. Le stock Freemium n'est PAS lu pour la compléter : plus
  d'un Go à chaque base neuve pour une trentaine de JO, et son contenu n'a
  jamais été ouvert ni mesuré ici.
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

# Stock global régénéré par la DILA (nom relevé à l'index : 20250713-140000
# puis 20261108-140000). Jamais téléchargé ici ; sa présence dit seulement
# que l'index est celui que l'on connaît, et son stamp date la régénération.
RE_STOCK = re.compile(r'href="(Freemium_jorf_simple_(\d{8})-(\d{6})\.tar\.gz)"')

# Livraison nocturne (~00h20-00h45 constaté, parfois bien plus tard) = JO du
# jour. Livraison du soir (~21h-22h45) = réécritures rétroactives, à ignorer.
# Index relu le 15/10/2026 : aucune nocturne après 04h21 depuis juillet 2025,
# et des correctifs isolés à 07h04, 10h14, 10h49, 10h54, 12h29…
# Celui du 01/10/2026 à 10h54 réécrivait un décret paru au JO du 27/11/2007 :
# admis par l'ancien seuil de 12 h, il avait reculé la fenêtre de dix-neuf ans.
# MARGE, dite telle qu'elle est : la nocturne du 11/11/2026 (jour férié) est
# stampée 04h43, au-delà du maximum précédent. Le seuil de 6 h n'est donc
# plus qu'à 1 h 17 de la nocturne la plus tardive connue, et rien ne garantit
# que la suivante restera dessous. Le seuil n'est pas relevé pour autant (le
# correctif le plus matinal connu est de 07h04) : une nocturne livrée après
# 6 h n'est pas ingérée, elle est NOMMÉE au journal du cycle par
# `signaler_jours_sans_nocturne`. Et une nocturne publiée après le passage
# du cycle n'est pas perdue : le cycle suivant relit tout l'index.
HEURE_MAX_NOCTURNE = 6

# Début de la livraison du soir (~21h-22h45 constaté). Entre HEURE_MAX_NOCTURNE
# et cette heure, une livraison est un correctif — ou une nocturne en retard :
# un jour qui n'a QUE cela n'a aucun JO retenu, et c'est dit au journal.
# Index relu le 15/10/2026 : 2 jours sur 452 dans ce cas (lundis 22/09/2025
# et 01/06/2026, sans JO), aucune nocturne livrée après 04h21.
HEURE_MIN_SOIR = 20

# Un texte livré la nuit du jour J paraît au JO du jour J (mesuré sur les 30
# nocturnes du 12/09 au 15/10/2026 : aucune exception). La veille est tolérée ;
# plus ancien, c'est une réécriture, écartée et comptée.
JOURS_TOLERES_AVANT_LIVRAISON = 1

# Profondeur maximale de la fenêtre en jours civils PAR JO visé. Mesuré sur
# les 30 nocturnes du 14/07 au 19/08/2026 : 30 JO couvrent 37 jours civils
# (1,2 par JO). Le double laisse à une base persistante de quoi traverser
# une panne de plusieurs semaines sans rien perdre, et borne quand même la
# fenêtre : un texte de 2007 resté en table (état servi le 15/10/2026) ne
# peut pas compter pour « un des 30 derniers JO en base ».
JOURS_CIVILS_MAX_PAR_JO = 2

# Écart normal entre deux JO consécutifs : 2 jours autour d'un lundi (pas de
# JO le lundi), 3 autour d'un pont (15/08/2026 → 18/08/2026). Au-delà, la
# fenêtre a probablement un trou — JO parus pendant que l'ingestion était
# arrêtée et que l'index ne liste plus. On ne le devine pas : on le compte,
# on le nomme au journal et dans la note de meta_sources.
ECART_NORMAL_ENTRE_JO = 3

# Débuts de la note de meta_sources quand la fenêtre n'est pas ce que son nom
# promet. La page /documents affiche la note telle quelle quand elle commence
# par l'une de ces marques (app/src/lib/queries/documents.ts,
# MARQUES_FENETRE_SIGNALEE) : ne pas les reformuler d'un seul côté.
MARQUE_FENETRE_REDUITE = "Fenêtre réduite"
MARQUE_FENETRE_DISCONTINUE = "Fenêtre discontinue"

# Les tarballs publiés sont immuables : présent en cache = jamais retéléchargé.
CACHE_IMMUABLE_H = 24 * 365 * 100

# Le 04/10/2026, les 3 tentatives par défaut de session_http étaient épuisées
# en 7,8 s sur l'index (run CI 37228277308) face aux connexions réinitialisées
# de echanges.dila.gouv.fr.
# Plus de patience pour une coupure brève ; une panne longue mène au secours.
TENTATIVES_DILA = 5
BACKOFF_DILA = 4.0

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


def livraisons_de_journee_sans_nocturne(html: str) -> list[str]:
    """Livraisons de journée (HEURE_MAX_NOCTURNE <= heure < HEURE_MIN_SOIR)
    des jours qui n'ont AUCUNE nocturne, ordre chronologique.

    POURQUOI : la règle des 06 h écarte les correctifs qui réécrivaient des
    JO anciens. Mais une nocturne livrée en retard (après 06 h) serait
    écartée de la même façon, et le JO de ce jour sauterait de la fenêtre
    sans aucun signe. Ces livraisons ne sont pas ingérées (on ne devine pas
    qu'un correctif est un JO) : elles sont NOMMÉES au journal du cycle.
    """
    nocturnes: set[str] = set()
    journee: dict[str, list[str]] = {}
    for nom, aaaammjj, hhmmss in RE_LIVRAISON.findall(html):
        heure = int(hhmmss[:2])
        if heure < HEURE_MAX_NOCTURNE:
            nocturnes.add(aaaammjj)
        elif heure < HEURE_MIN_SOIR:
            journee.setdefault(aaaammjj, []).append(nom)
    return sorted(n for j, noms in journee.items() if j not in nocturnes for n in noms)


def signaler_jours_sans_nocturne(html: str, debut: date) -> list[str]:
    """Journalise, à CHAQUE cycle et zéro compris, les jours de la fenêtre
    (à partir de `debut`) sans nocturne mais avec une livraison de journée
    écartée. Avertit sans lever : le JO manquant n'est pas une raison
    d'arrêter la nuit, mais il ne doit pas manquer en silence."""
    noms = [n for n in livraisons_de_journee_sans_nocturne(html)
            if jour_de_livraison(n) >= debut]
    if noms:
        log.warning(
            "%d livraison(s) de journée sur un jour sans nocturne, écartée(s)"
            " par la règle des %02d h : %s — si c'est une nocturne en retard,"
            " le JO de ce jour manque à la fenêtre (à vérifier)",
            len(noms), HEURE_MAX_NOCTURNE, ", ".join(noms),
        )
    else:
        log.info("jours sans nocturne avec livraison de journée dans la fenêtre : 0")
    return noms


def stock_a_l_index(html: str) -> str | None:
    """Stamp `AAAAMMJJ` du stock Freemium le plus récent listé à l'index, ou
    None. Le stock n'est jamais téléchargé : son stamp date la régénération
    qui a vidé l'index, pour le dire au journal et dans la note."""
    stamps = [aaaammjj for _nom, aaaammjj, _h in RE_STOCK.findall(html)]
    return max(stamps) if stamps else None


def index_reconnu(html: str) -> bool:
    """Vrai si l'index liste au moins un fichier que l'on sait nommer
    (livraison de n'importe quelle heure, ou stock). Sépare « rien de neuf à
    lire » (secours) de « page que l'on ne sait plus lire » (échec)."""
    return bool(RE_LIVRAISON.search(html) or RE_STOCK.search(html))


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


def _fr(iso: str) -> str:
    """`2026-11-08` → `08/11/2026` (la note de meta_sources est lue telle
    quelle sur /documents quand la fenêtre est signalée)."""
    return date.fromisoformat(iso).strftime("%d/%m/%Y")


def fenetre_en_base(conn, jours: int, avec_archive: bool = False) -> list[str]:
    """Dates des `jours` derniers JO PRÉSENTS EN BASE, ordre chronologique.
    `avec_archive` : compte aussi les JO de jorf_textes_archive (ce qui
    DEVRAIT être en fenêtre, pour la réintégration).

    C'est la base qui porte la fenêtre, pas l'index : la DILA retire de
    l'index les livraisons antérieures à chaque régénération de son stock,
    et « la plus ancienne livraison encore listée » n'est alors plus le
    début de rien. Borne de profondeur : aucun JO à plus de
    `jours * JOURS_CIVILS_MAX_PAR_JO` jours civils du plus récent.
    """
    plus_recent = conn.execute("SELECT MAX(date_publi) FROM jorf_textes").fetchone()[0]
    if plus_recent is None:
        return []
    plancher = (
        date.fromisoformat(plus_recent)
        - timedelta(days=jours * JOURS_CIVILS_MAX_PAR_JO)
    ).isoformat()
    tables = "SELECT date_publi FROM jorf_textes"
    if avec_archive:
        tables += " UNION SELECT date_publi FROM jorf_textes_archive"
    return sorted(
        r[0] for r in conn.execute(
            f"SELECT DISTINCT date_publi FROM ({tables}) WHERE date_publi >= ?"
            " ORDER BY date_publi DESC LIMIT ?", (plancher, jours),
        )
    )


def reintegrer_depuis_archive(conn, jours: int) -> tuple[int, list[str]]:
    """Ramène en table les textes archivés dont le JO est dans la fenêtre.

    POURQUOI : jusqu'au 11/11/2026 la purge suivait l'index. Un cycle joué
    devant l'index réduit a envoyé à l'archive des JO qui comptaient encore
    parmi les 30 derniers ; `jorf` passant avant la plupart des pipelines, un
    cycle qui échoue plus loin peut avoir laissé la base dans cet état sans
    rien publier. La fenêtre de référence se calcule donc sur table +
    archive, et ce qui y tombe revient.

    `INSERT OR IGNORE` : un texte déjà en table (livré de nouveau depuis)
    n'est pas écrasé par sa copie archivée. Les lignes revenues quittent
    l'archive : un texte est en table OU en archive, jamais les deux.
    Retourne (textes réintégrés, dates des JO concernés).
    """
    dates = fenetre_en_base(conn, jours, avec_archive=True)
    if not dates:
        return 0, []
    debut = dates[0]
    concernes = [r[0] for r in conn.execute(
        "SELECT DISTINCT date_publi FROM jorf_textes_archive"
        " WHERE date_publi >= ? ORDER BY 1", (debut,))]
    if not concernes:
        return 0, []
    colonnes = ", ".join(COLONNES_JORF_TEXTES)
    n = conn.execute(
        f"INSERT OR IGNORE INTO jorf_textes ({colonnes})"
        f" SELECT {colonnes} FROM jorf_textes_archive WHERE date_publi >= ?",
        (debut,),
    ).rowcount
    conn.execute("DELETE FROM jorf_textes_archive WHERE date_publi >= ?", (debut,))
    return n, concernes


def ecarts_anormaux(dates_jo: list[str]) -> list[tuple[str, str, int]]:
    """(JO d'avant, JO d'après, jours civils entre les deux) pour chaque
    paire de JO consécutifs de la fenêtre séparés de plus de
    ECART_NORMAL_ENTRE_JO jours."""
    trous = []
    for avant, apres in zip(dates_jo, dates_jo[1:]):
        ecart = (date.fromisoformat(apres) - date.fromisoformat(avant)).days
        if ecart > ECART_NORMAL_ENTRE_JO:
            trous.append((avant, apres, ecart))
    return trous


def _editions(n: int) -> str:
    return (
        "1 édition quotidienne du JO" if n == 1
        else f"{n} éditions quotidiennes du JO"
    )


def note_fenetre(
    dates_jo: list[str],
    jours: int,
    nocturnes_index: int,
    stock: str | None,
    constat: str,
) -> str:
    """Note de meta_sources : ce que la fenêtre contient VRAIMENT.

    Fenêtre pleine et continue : compte et bornes. Sinon la note commence
    par MARQUE_FENETRE_REDUITE ou MARQUE_FENETRE_DISCONTINUE, donne le
    compteur, la date du constat et ce que la DILA proposait ce jour-là.
    Elle est LUE sur /documents : mots du lecteur, pas ceux du pipeline
    (« édition quotidienne », pas « livraison nocturne » ; « renouvellement
    du dépôt », pas « Freemium »). Elle ne dit pas où sont les JO plus
    anciens (absents, ou à l'archive) : seulement qu'ils ne sont pas affichés.
    """
    debut, fin = dates_jo[0], dates_jo[-1]
    index_reduit = nocturnes_index < jours
    etat_index = f"le dépôt public de la DILA propose {_editions(nocturnes_index)}"
    if index_reduit and stock:
        etat_index += (
            " depuis son renouvellement du "
            f"{_fr(f'{stock[:4]}-{stock[4:6]}-{stock[6:]}')}"
        )
    trous = ecarts_anormaux(dates_jo)
    dit_trous = " ; ".join(
        f"aucun JO entre le {_fr(a)} et le {_fr(b)} ({n} jours)"
        for a, b, n in trous
    )
    if len(dates_jo) < jours:
        note = (
            f"{MARQUE_FENETRE_REDUITE} : {len(dates_jo)} JO sur les {jours}"
            f" visés, du {_fr(debut)} au {_fr(fin)} (constat du"
            f" {_fr(constat)}) ; {etat_index}, les JO plus anciens ne sont"
            " pas affichés ici"
        )
        return f"{note} ; {dit_trous}" if trous else note
    note = f"{len(dates_jo)} JO, du {_fr(debut)} au {_fr(fin)} ; {etat_index}"
    if index_reduit:
        note += ", les JO plus anciens viennent des ingestions précédentes"
    if trous:
        return (
            f"{MARQUE_FENETRE_DISCONTINUE} : {dit_trous} (constat du"
            f" {_fr(constat)}) ; {note}"
        )
    return note


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


def secours_cycle_precedent(motif: str) -> int:
    """Rien de neuf à lire à la DILA (serveur injoignable, ou index sans
    aucune livraison nocturne) : reprendre le JORF du dernier cycle réussi.

    N'écrit rien (voir db.publication_precedente). Exit 0 si un cycle
    précédent a laissé des textes datés, exit 1 sinon (base neuve).
    """
    conn = db.connexion()
    try:
        precedent = db.publication_precedente(conn, "jorf_textes", "S3")
    finally:
        conn.close()
    if precedent is None:
        log.error(
            "%s et aucun JORF d'un cycle précédent à reprendre : échec", motif,
        )
        return 1
    lignes, date_donnees = precedent
    log.warning(
        "%s → secours : jorf_textes reprise telle que"
        " publiée par le dernier cycle réussi (%d textes, JO le plus récent"
        " du %s) ; rien n'est écrit, meta_sources S3 garde cette date",
        motif, lignes, date_donnees,
    )
    return 0


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

    session = session_http(total_retries=TENTATIVES_DILA, backoff=BACKOFF_DILA)
    try:
        log.info("index: %s", URL_JORFSIMPLE)
        r = session.get(URL_JORFSIMPLE, timeout=60)
        r.raise_for_status()
    except requests.RequestException as exc:
        return secours_cycle_precedent(
            f"DILA injoignable (index JORFSIMPLE : {exc})")

    nocturnes = livraisons_nocturnes(r.text)
    stock = stock_a_l_index(r.text)
    if not nocturnes:
        if not index_reconnu(r.text):
            log.error(
                "index JORFSIMPLE illisible : ni livraison ni stock reconnus"
                " (format changé ?)")
            return 1
        # Cas du 09/11/2026 : stock régénéré la veille, première nocturne
        # attendue le lendemain. Sortir en erreur gelait tout le cycle pour
        # un index parfaitement lisible. Une livraison de journée listée
        # seule peut être la nocturne en retard : elle est nommée ici aussi.
        signaler_jours_sans_nocturne(r.text, date.min)
        return secours_cycle_precedent(
            "index DILA réduit à 0 livraison nocturne ("
            f"{len(RE_LIVRAISON.findall(r.text))} livraison(s) d'une autre"
            f" heure listée(s), stock Freemium : {stock or 'aucun'})"
        )
    selection = nocturnes[-args.jours:]
    log.info(
        "%d livraisons nocturnes à l'index, %d retenues (%s → %s)",
        len(nocturnes), len(selection), selection[0], selection[-1],
    )
    # Journalisé à chaque cycle, cas normal compris : un index réduit ne
    # casse rien, il doit donc se dire.
    if len(nocturnes) < args.jours:
        log.warning(
            "index DILA réduit à %d livraison(s) nocturne(s) pour %d JO visés"
            " (stock Freemium : %s) : la fenêtre ne tient que par les JO déjà"
            " en base", len(nocturnes), args.jours, stock or "aucun",
        )
    else:
        log.info(
            "index DILA non réduit : %d livraisons nocturnes pour %d JO visés",
            len(nocturnes), args.jours,
        )
    signaler_jours_sans_nocturne(r.text, jour_de_livraison(selection[0]))

    # Tout le réseau AVANT la première écriture : une coupure au 12e tarball
    # ne doit pas laisser en base 11 JO neufs sous la date de la veille.
    chemins: list[tuple[str, Path]] = []
    for nom in selection:
        try:
            chemins.append((nom, telecharger(
                URL_JORFSIMPLE + nom,
                f"jorf/{nom}",
                max_age_heures=CACHE_IMMUABLE_H,  # tarballs immuables
                session=session,
            )))
        except requests.RequestException as exc:
            return secours_cycle_precedent(f"DILA injoignable ({nom} : {exc})")

    conn = db.init_db()
    conn.executescript(_SCHEMA)
    conn.commit()

    total, toutes_dates = 0, []
    for nom, chemin in chemins:
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

    # Fenêtre glissante : les `--jours` derniers JO EN BASE, ceux de ce run
    # compris. Elle se calculait sur `min(toutes_dates)`, c'est-à-dire sur
    # la plus ancienne livraison encore listée : avec un index réduit à deux
    # nocturnes, 28 JO encore dans la fenêtre partaient à l'archive, en
    # sortie 0 et sans un mot.
    aujourd_hui = date.today().isoformat()
    n_revenus, jo_revenus = reintegrer_depuis_archive(conn, args.jours)
    if n_revenus or jo_revenus:
        log.warning(
            "%d texte(s) de %d JO réintégré(s) depuis jorf_textes_archive"
            " (%s → %s) : archivés par un cycle précédent alors qu'ils"
            " comptent parmi les %d derniers JO connus",
            n_revenus, len(jo_revenus), jo_revenus[0], jo_revenus[-1],
            args.jours,
        )
    else:
        log.info("textes réintégrés depuis jorf_textes_archive : 0")
    dates_fenetre = fenetre_en_base(conn, args.jours)
    debut_fenetre = dates_fenetre[0]
    n_sortants = conn.execute(
        "SELECT count(*) FROM jorf_textes WHERE date_publi < ?", (debut_fenetre,)
    ).fetchone()[0]
    archiver_et_purger_jorf(conn, debut_fenetre, aujourd_hui)
    log.info(
        "fenêtre : %d JO en base sur %d visés (%s → %s) ; %d texte(s) plus"
        " ancien(s) archivé(s) puis purgé(s)",
        len(dates_fenetre), args.jours, debut_fenetre, dates_fenetre[-1],
        n_sortants,
    )
    if len(dates_fenetre) < args.jours:
        log.warning(
            "fenêtre RÉDUITE : %d JO en base sur %d visés — l'index ne liste"
            " pas les JO antérieurs et la base ne les porte pas",
            len(dates_fenetre), args.jours,
        )
    trous = ecarts_anormaux(dates_fenetre)
    if trous:
        log.warning(
            "fenêtre DISCONTINUE : %d écart(s) de plus de %d jours entre deux"
            " JO consécutifs en base : %s — des JO parus dans l'intervalle"
            " peuvent manquer (à vérifier)",
            len(trous), ECART_NORMAL_ENTRE_JO,
            ", ".join(f"{a} → {b} ({n} j)" for a, b, n in trous),
        )
    else:
        log.info(
            "écarts de plus de %d jours entre deux JO consécutifs de la"
            " fenêtre : 0", ECART_NORMAL_ENTRE_JO,
        )

    reconstruire_agregats(conn)

    date_donnees = dates_fenetre[-1]
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
        notes=note_fenetre(
            dates_fenetre, args.jours, len(nocturnes), stock, aujourd_hui),
    )
    log.info(
        "terminé: %d textes upsertés, %d en table, JO le plus récent: %s",
        total, lignes, date_donnees,
    )
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

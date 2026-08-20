"""P16 — Avis et conseils de la CADA, en agrégats seulement (source S38).

Alimente la « carte des verrous » du module UI « Frais & train de vie » :
qui refuse de communiquer un document administratif, sur quel fondement, et
dans quel sens la Commission d'accès aux documents administratifs tranche.

POURQUOI DES AGRÉGATS, ET RIEN QUE DES AGRÉGATS
-----------------------------------------------
Le CSV consolidé publié par la CADA pèse 198 Mo, dont 93 % pour la seule
colonne « Avis » : le texte intégral de chaque décision. Ce texte n'est
jamais ingéré, pour deux raisons cumulatives :

1. le poids — il ferait à lui seul un tiers de plus que toute la base servie,
   pour une information que la page ne restitue pas ;
2. la prudence — les demandeurs sont anonymisés à la source (« X, député »),
   mais les motivations citent nommément des responsables publics et
   décrivent des situations individuelles. Un dénombrement porte toute
   l'information utile au module sans transporter une seule de ces phrases.

Ne sont donc conservés que des comptages. Le seul texte libre qui entre en
base est le libellé de l'administration mise en cause — une personne morale,
publiée comme telle par la CADA — accompagné du vocabulaire fermé des sens
et des motivations.

LE PIÈGE ÉDITORIAL, QUI DOIT RESTER VISIBLE
-------------------------------------------
Le jeu de données porte une date de modification récente alors que la
dernière séance qu'il contient est bien plus ancienne : la CADA verse ses
décisions par lots, avec un décalage d'environ deux ans, et ce décalage
s'aggrave (les lots récents couvrent moins de mois de séance qu'il ne s'est
écoulé de mois entre deux versements). Conséquence directe : les derniers
millésimes du corpus sont incomplets par construction.

Ce pipeline refuse donc de prendre la date de modification du dataset pour
une date de fraîcheur : `meta_sources.date_donnees` porte la date de la
dernière SÉANCE réellement ingérée, et `notes` porte l'écart entre les deux.
C'est ce qui fait sonner `ft-fraicheur` et le badge de la page, comme prévu
par SOURCES.md §0.2.

CE QUE CE PIPELINE NE FAIT PAS, ET POURQUOI
-------------------------------------------
- **Aucun référentiel d'administrations n'est inventé.** Le champ
  « Administration » est du texte libre ; sa distribution réelle montre plus
  de seize mille libellés distincts, dont près de dix mille n'apparaissent
  qu'une fois (« Mairie de Dœuil-sur-le-Mignon »). Replier la casse et les
  accents n'en supprime que quelques centaines : il n'existe pas de
  référentiel à retrouver, seulement une longue traîne de communes et
  d'établissements. Le libellé est donc conservé tel que publié (orthographe
  majoritaire retenue quand plusieurs graphies désignent la même entité), et
  seule une **typologie grossière, par préfixe explicite et vérifiable**, est
  ajoutée — avec une catégorie « autre » assumée pour ce qui n'entre dans
  aucune règle. Rapprocher ces libellés d'un SIREN serait de l'invention.
- **La colonne « Thème et sous thème » n'est pas ingérée.** Elle liste des
  couples `thème/sous-thème` séparés par des virgules, mais les thèmes
  eux-mêmes contiennent des virgules (« Justice, Ordre Public Et Sécurité »,
  « Economie, Industrie, Agriculture ») : le séparateur appartient au
  vocabulaire, la découpe est donc ambiguë dès qu'une décision porte
  plusieurs thèmes. Reconstituer le vocabulaire à la main reviendrait à
  inventer une nomenclature que la CADA ne publie pas. Colonne écartée.

La colonne « Sens et motivation » souffre du même défaut — « Irrecevable/
Documentation, établissement de document » contient une virgule — mais là,
il est réparable sans rien deviner : le vocabulaire des SENS est fermé et
connu (cinq valeurs), et tout élément commence par l'un d'eux suivi d'une
fin de champ ou d'un `/`. Un fragment qui ne répond pas à ce motif est donc
la suite du précédent, et lui est recollé. Contrôle sur le corpus entier :
zéro fragment orphelin, cinq sens distincts, un vocabulaire de motivations
fermé — si l'un de ces trois invariants cassait, le pipeline échouerait au
lieu de produire des agrégats faux.

Tables créées (idempotent, intégralement reconstruites à chaque passage) :

- cada_administrations : une administration mise en cause.
    id (entier de surface, réattribué à chaque passage par ordre de clé
    normalisée), libelle, categorie, nb_dossiers, premiere_annee,
    derniere_annee.
- cada_saisines : le DÉNOMINATEUR — nombre de dossiers par administration,
    année et type de saisine. Indispensable : une décision peut porter
    plusieurs sens, la somme de `cada_sens` dépasse donc le nombre de
    dossiers et ne peut jamais servir de total.
- cada_sens : le fait — nombre de dossiers où un sens donné apparaît, par
    administration, année et type.
- cada_motifs : le vocabulaire des verrous — nombre de dossiers par
    motivation (`sens/motivation`), année et type. C'est le fondement
    juridique opposé au demandeur, la matière même de la carte des verrous.

Usage :
    python -m pipelines.ingest_cada
    python -m pipelines.ingest_cada --csv chemin/local.csv   # sans réseau
"""

from __future__ import annotations

import argparse
import csv
import re
import sqlite3
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path

import requests

from pipelines import db
from pipelines.common import RAW_DIR, obtenir_logger, session_http, telecharger

log = obtenir_logger("ingest_cada")

SOURCE_ID = "S38"

URL_DATASET_API = "https://www.data.gouv.fr/api/1/datasets/avis-et-conseils-de-la-cada/"
URL_DATASET_PAGE = "https://www.data.gouv.fr/datasets/avis-et-conseils-de-la-cada/"

# La ressource consolidée est repérée par son TITRE, jamais par une URL en
# dur : l'URL static.data.gouv.fr porte l'horodatage du versement et change
# à chaque lot (…/20260814-172417/cada-2026-08-14.csv).
TITRE_RESSOURCE = "ensemble consolidé"

NOM_SOURCE = "CADA — avis et conseils (ensemble consolidé)"
LICENCE = "Licence Ouverte (fr-lo)"
# Cadence réelle observée sur les lots publiés : deux à quatre versements par
# an, sans calendrier annoncé. « annuelle » serait faux, « quotidienne » aussi.
FREQUENCE = "irrégulière (versements par lots, 2 à 4 fois par an)"

FICHIER_CACHE = RAW_DIR / "cada" / "cada-consolide.csv"
# Le corpus ne bouge qu'à un versement (quelques fois par an) : re-télécharger
# 198 Mo à chaque ingestion quotidienne serait du gâchis pour l'amont comme
# pour nous. Une semaine de cache reste très en deçà de la cadence amont.
CACHE_HEURES = 7 * 24

# Colonnes attendues du CSV consolidé. La colonne « Avis » (texte intégral)
# est listée pour que le contrôle d'en-tête soit strict, mais n'est jamais lue.
COLONNES_ATTENDUES = (
    "Numéro de dossier",
    "Administration",
    "Type",
    "Année",
    "Séance",
    "Objet",
    "Thème et sous thème",
    "Mots clés",
    "Sens et motivation",
    "Partie",
    "Avis",
)

# Vocabulaire FERMÉ des sens (contrôlé sur le corpus entier : aucun autre).
SENS = ("Favorable", "Défavorable", "Irrecevable", "Incompétence", "Sans objet")

# Les sens qui constituent un refus ou un non-lieu à statuer — les « verrous »
# au sens du module. « Sans objet » n'en est pas un (le document a été
# communiqué en cours d'instruction, ou n'existe pas).
SENS_VERROU = ("Défavorable", "Incompétence", "Irrecevable")

TYPES = ("Avis", "Conseil", "Sanction")

# Un élément de « Sens et motivation » commence par un sens du vocabulaire,
# suivi d'une fin de champ ou d'un `/`. Tout le reste est une suite recollée.
_RX_ELEMENT = re.compile(r"^(?:%s)\s*(?:/|$)" % "|".join(map(re.escape, SENS)))

# ---------------------------------------------------------------------------
# Typologie des administrations mises en cause
# ---------------------------------------------------------------------------

# Règles de classement par PRÉFIXE de la clé normalisée (minuscules, sans
# accents, ponctuation réduite à des espaces). Elles sont volontairement
# littérales : chacune se relit et se vérifie sur le libellé publié, aucune
# ne repose sur une liste d'entités que la CADA ne fournit pas. Ce qui
# n'entre dans aucune règle reste en « autre » — environ un quart des
# dossiers, et c'est dit tel quel dans l'UI plutôt que forcé quelque part.
CATEGORIES = (
    "ministere",
    "prefecture",
    "commune",
    "departement_region",
    "sante",
    "enseignement",
    "securite_sociale",
    "finances",
    "justice_police",
    "autorite_independante",
    "autre",
)

_REGLES_CATEGORIE: tuple[tuple[str, str], ...] = (
    # L'ordre compte : « prefecture de police de Paris » doit tomber dans
    # justice_police, pas dans prefecture — d'où sa présence plus haut.
    ("justice_police",
     r"^(prefecture de police|tribunal|cour d |cour de |cour administrative|parquet|"
     r"procureur|direction generale de la police|direction generale de la gendarmerie|"
     r"direction departementale de la securite publique|etablissement penitentiaire|"
     r"centre penitentiaire|maison d arret|direction (de l|interregionale des services p)"
     r"?administration penitentiaire)"),
    ("finances",
     r"^(direction generale des finances publiques|dgfip|direction (departementale|"
     r"regionale) des finances publiques|tresorerie|direction generale des douanes|"
     r"direction (interregionale|regionale) des douanes)"),
    ("ministere",
     r"^(ministere|ministre|secretariat d etat|secretaire d etat|premier ministre|"
     r"presidence de la republique|haut commissaire|haut commissariat|"
     r"secretariat general du gouvernement)"),
    ("prefecture",
     r"^(prefecture|prefet|sous prefecture|sous prefet|haut commissariat de la republique)"),
    ("commune",
     r"^(mairie|commune|ville d |ville de |ville du |ville des |maire d |maire de |"
     r"maire du |centre communal d action sociale|ccas|syndicat intercommunal|"
     r"syndicat mixte|communaute d agglomeration|communaute de communes|"
     r"communaute urbaine|etablissement public territorial)"),
    # Le « conseil départemental de l'ordre des médecins » est un ordre
    # professionnel, pas une collectivité : exclu explicitement (48 libellés,
    # 80 dossiers dans le corpus publié) et laissé en « autre ».
    ("departement_region",
     r"^(conseil (departemental|general|regional)(?! de l ordre)|departement d |"
     r"departement de |departement du |departement des |region |collectivite "
     r"territoriale|collectivite europeenne|collectivite de|collectivite unique)"),
    ("sante",
     r"^(centre hospitalier|hopital|hopitaux|assistance publique|chu |chru |ehpad|"
     r"agence regionale de sante|ars |clinique|centre medico|groupe hospitalier|"
     r"institut medico|centre de lutte contre le cancer)"),
    ("enseignement",
     r"^(rectorat|academie|universite|lycee|college|ecole|inspection academique|"
     r"inspection d academie|crous|centre national d enseignement|"
     r"institut universitaire|institut national (des sciences|polytechnique|"
     r"universitaire))"),
    ("securite_sociale",
     r"^(caisse|cpam|caf |urssaf|carsat|cram |msa |cnav|cnaf|cnam|"
     r"mutualite sociale agricole|regime social des independants|rsi )"),
    ("autorite_independante",
     r"^(commission nationale|autorite|haute autorite|defenseur des droits|"
     r"mediateur de la republique|conseil superieur de l audiovisuel|"
     r"commission d acces aux documents)"),
)

_REGLES_COMPILEES = tuple(
    (nom, re.compile(motif)) for nom, motif in _REGLES_CATEGORIE
)


def cle_administration(libelle: str) -> str:
    """Clé de repli d'un libellé d'administration : minuscules, sans accents,
    ponctuation réduite à des espaces simples.

    Sert UNIQUEMENT à réunir les graphies d'un même libellé (« Ministère de
    la Justice » / « Ministère de la justice », « Ministère des Armées » /
    « Ministère des armées »). Elle ne rapproche jamais deux libellés
    différents : « Mairie de Lyon » et « Ville de Lyon » restent deux
    entrées, faute de référentiel permettant d'affirmer qu'il s'agit du même
    interlocuteur au même moment.
    """
    sans_accent = "".join(
        c for c in unicodedata.normalize("NFD", libelle.lower())
        if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"[^a-z0-9]+", " ", sans_accent).strip()


def categorie_administration(cle: str) -> str:
    """Typologie grossière d'une administration à partir de sa clé normalisée.

    Première règle qui accroche, sinon « autre ». Aucun classement n'est
    déduit d'autre chose que du texte publié par la CADA.
    """
    for nom, motif in _REGLES_COMPILEES:
        if motif.match(cle):
            return nom
    return "autre"


# ---------------------------------------------------------------------------
# Découpe de « Sens et motivation »
# ---------------------------------------------------------------------------


def decouper_motivations(brut: str | None) -> list[str]:
    """« Sens et motivation » → liste de motivations normalisées.

    Chaque motivation s'écrit `Sens` ou `Sens/Motivation`. Le champ en
    concatène plusieurs, séparées par des virgules — mais une motivation peut
    elle-même contenir une virgule (« Irrecevable/Documentation, établissement
    de document »). Un fragment est donc un NOUVEL élément seulement s'il
    commence par un sens du vocabulaire fermé suivi d'un `/` ou de la fin ;
    sinon il est recollé au précédent.

    Les espaces autour du premier `/` sont normalisés (« Favorable / Sauf vie
    privée » et « Favorable/Sauf vie privée » sont la même motivation, écrite
    de deux façons selon le millésime).

    Lève ValueError sur un fragment orphelin : un champ dont le premier
    élément ne commence par aucun sens connu signale un changement de
    vocabulaire amont, pas une ligne à ignorer discrètement.
    """
    elements: list[str] = []
    for fragment in (brut or "").split(","):
        fragment = re.sub(r"\s+", " ", fragment).strip()
        if not fragment:
            continue
        if _RX_ELEMENT.match(fragment):
            elements.append(fragment)
        elif elements:
            elements[-1] += ", " + fragment
        else:
            raise ValueError(
                f"vocabulaire des sens inconnu dans « {brut} » (fragment « {fragment} »)"
            )
    return [re.sub(r"\s*/\s*", "/", e, count=1) for e in elements]


def sens_de(motivation: str) -> str:
    """Sens porté par une motivation (partie avant le premier `/`)."""
    return motivation.split("/", 1)[0]


# ---------------------------------------------------------------------------
# Résolution de la ressource amont
# ---------------------------------------------------------------------------


def resoudre_ressource(session: requests.Session | None = None,
                       timeout: int = 60) -> dict[str, str]:
    """Interroge l'API data.gouv.fr et retourne la ressource consolidée.

    Retourne `{"url", "titre", "derniere_modification", "octets"}`.
    Lève RuntimeError si la ressource a disparu du dataset : mieux vaut un
    échec franc qu'un repli silencieux sur un lot mensuel partiel.
    """
    s = session or session_http()
    reponse = s.get(URL_DATASET_API, timeout=timeout)
    reponse.raise_for_status()
    dataset = reponse.json()
    for ressource in dataset.get("resources", []):
        titre = (ressource.get("title") or "").strip()
        if TITRE_RESSOURCE in titre.lower():
            return {
                "url": ressource["url"],
                "titre": titre,
                "derniere_modification": (ressource.get("last_modified") or "")[:10],
                "octets": str(ressource.get("filesize") or ""),
            }
    titres = [r.get("title") for r in dataset.get("resources", [])]
    raise RuntimeError(
        f"ressource « {TITRE_RESSOURCE} » absente du dataset CADA ; présentes : {titres}"
    )


# ---------------------------------------------------------------------------
# Agrégation en flux
# ---------------------------------------------------------------------------


class Agregats:
    """Compteurs remplis en une passe de lecture, jamais le corpus entier.

    Le CSV fait 198 Mo mais n'est jamais matérialisé en mémoire : seules les
    clés d'agrégation sont conservées (quelques dizaines de milliers), et le
    texte intégral de chaque décision est relâché dès la ligne suivante.
    """

    def __init__(self) -> None:
        self.graphies: dict[str, Counter] = defaultdict(Counter)
        self.dossiers_admin: Counter = Counter()
        self.annees_admin: dict[str, list[int]] = {}
        self.saisines: Counter = Counter()      # (cle, annee, type) -> n
        self.sens: Counter = Counter()          # (cle, annee, type, sens) -> n
        self.motifs: Counter = Counter()        # (annee, type, motivation) -> n
        self.lignes = 0
        self.types: Counter = Counter()
        self.derniere_seance: date | None = None
        self.premiere_seance: date | None = None
        self.sans_motivation = 0


def _lire_seance(valeur: str) -> date | None:
    """`03/03/1984` → date. Retourne None sur une séance absente ou illisible."""
    try:
        return datetime.strptime(valeur.strip(), "%d/%m/%Y").date()
    except (ValueError, AttributeError):
        return None


def agreger(chemin: str | Path) -> Agregats:
    """Lit le CSV consolidé en flux et remplit les compteurs.

    Contrôle strict de l'en-tête : une colonne qui bouge en amont doit faire
    échouer le pipeline, jamais produire des agrégats décalés en silence.
    """
    chemin = Path(chemin)
    # Le texte intégral d'un avis dépasse la limite par défaut du module csv.
    csv.field_size_limit(1 << 30)
    agr = Agregats()

    with open(chemin, newline="", encoding="utf-8") as flux:
        lecteur = csv.reader(flux)
        entete = next(lecteur, None)
        if entete != list(COLONNES_ATTENDUES):
            raise RuntimeError(
                f"en-tête inattendu dans {chemin.name} : {entete}"
            )
        i_admin = entete.index("Administration")
        i_type = entete.index("Type")
        i_annee = entete.index("Année")
        i_seance = entete.index("Séance")
        i_sens = entete.index("Sens et motivation")

        for ligne in lecteur:
            if len(ligne) != len(COLONNES_ATTENDUES):
                raise RuntimeError(
                    f"ligne à {len(ligne)} colonnes dans {chemin.name} "
                    f"(attendu {len(COLONNES_ATTENDUES)})"
                )
            agr.lignes += 1

            libelle = re.sub(r"\s+", " ", ligne[i_admin]).strip()
            if not libelle:
                libelle = "Administration non renseignée"
            cle = cle_administration(libelle) or "non renseignee"
            agr.graphies[cle][libelle] += 1
            agr.dossiers_admin[cle] += 1

            type_saisine = ligne[i_type].strip() or "Avis"
            agr.types[type_saisine] += 1

            try:
                annee = int(ligne[i_annee])
            except ValueError:
                raise RuntimeError(
                    f"année illisible « {ligne[i_annee]} » dans {chemin.name}"
                ) from None
            bornes = agr.annees_admin.get(cle)
            if bornes is None:
                agr.annees_admin[cle] = [annee, annee]
            else:
                bornes[0] = min(bornes[0], annee)
                bornes[1] = max(bornes[1], annee)

            seance = _lire_seance(ligne[i_seance])
            if seance is not None:
                if agr.derniere_seance is None or seance > agr.derniere_seance:
                    agr.derniere_seance = seance
                if agr.premiere_seance is None or seance < agr.premiere_seance:
                    agr.premiere_seance = seance

            agr.saisines[(cle, annee, type_saisine)] += 1

            motivations = decouper_motivations(ligne[i_sens])
            if not motivations:
                agr.sans_motivation += 1
                continue
            for motivation in motivations:
                agr.motifs[(annee, type_saisine, motivation)] += 1
            # Un dossier est compté UNE fois par sens présent, même si
            # plusieurs motivations partagent ce sens.
            for sens in {sens_de(m) for m in motivations}:
                agr.sens[(cle, annee, type_saisine, sens)] += 1

    return agr


# ---------------------------------------------------------------------------
# Schéma
# ---------------------------------------------------------------------------

_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS cada_administrations (
    id             INTEGER PRIMARY KEY,
    libelle        TEXT    NOT NULL,
    categorie      TEXT    NOT NULL CHECK (categorie IN
                     ({", ".join("'" + c + "'" for c in CATEGORIES)})),
    nb_dossiers    INTEGER NOT NULL CHECK (nb_dossiers > 0),
    premiere_annee INTEGER NOT NULL,
    derniere_annee INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cada_admin_categorie
    ON cada_administrations(categorie, nb_dossiers DESC);

-- Volontairement PEU indexé au-delà des clés primaires : un index secondaire
-- sur `cada_sens(sens, annee)` coûtait 1,4 Mo en base pour faire gagner
-- quelques millisecondes sur un balayage de 47 000 lignes — balayage qui
-- n'a lieu qu'au build (le site est intégralement pré-rendu). Le poids de la
-- base, lui, est servi à chaque déploiement.

-- Dénominateur : nombre de DOSSIERS. Ne jamais totaliser cada_sens à la
-- place : une décision porte souvent plusieurs sens.
CREATE TABLE IF NOT EXISTS cada_saisines (
    administration_id INTEGER NOT NULL REFERENCES cada_administrations(id),
    annee             INTEGER NOT NULL,
    type_saisine      TEXT    NOT NULL CHECK (type_saisine IN
                        ({", ".join("'" + t + "'" for t in TYPES)})),
    nb_dossiers       INTEGER NOT NULL CHECK (nb_dossiers > 0),
    PRIMARY KEY (administration_id, annee, type_saisine)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS cada_sens (
    administration_id INTEGER NOT NULL REFERENCES cada_administrations(id),
    annee             INTEGER NOT NULL,
    type_saisine      TEXT    NOT NULL CHECK (type_saisine IN
                        ({", ".join("'" + t + "'" for t in TYPES)})),
    sens              TEXT    NOT NULL CHECK (sens IN
                        ({", ".join("'" + s + "'" for s in SENS)})),
    nb_dossiers       INTEGER NOT NULL CHECK (nb_dossiers > 0),
    PRIMARY KEY (administration_id, annee, type_saisine, sens)
) WITHOUT ROWID;

-- Le fondement opposé au demandeur : « Défavorable/Vie privée »,
-- « Incompétence/Judiciaire »… C'est la matière de la carte des verrous.
-- `motivation` est NULL quand la CADA publie un sens sans motivation (cas
-- réel, ex. « Défavorable » seul) : une chaîne vide serait un faux libellé.
-- D'où l'unicité par index d'expression plutôt qu'une clé primaire, qui
-- interdirait le NULL.
CREATE TABLE IF NOT EXISTS cada_motifs (
    annee        INTEGER NOT NULL,
    type_saisine TEXT    NOT NULL CHECK (type_saisine IN
                   ({", ".join("'" + t + "'" for t in TYPES)})),
    sens         TEXT    NOT NULL CHECK (sens IN
                   ({", ".join("'" + s + "'" for s in SENS)})),
    motivation   TEXT,
    nb_dossiers  INTEGER NOT NULL CHECK (nb_dossiers > 0)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_cada_motifs_cle
    ON cada_motifs(annee, type_saisine, sens, ifnull(motivation, ''));
CREATE INDEX IF NOT EXISTS idx_cada_motifs_sens ON cada_motifs(sens, motivation);
"""

# Pluriels des types de saisine : « avis » est invariable, un `+ "s"`
# mécanique écrirait « aviss » dans les notes de fraîcheur affichées.
_PLURIELS = {"Avis": "avis", "Conseil": "conseils", "Sanction": "sanctions"}


# ---------------------------------------------------------------------------
# Écriture
# ---------------------------------------------------------------------------


def ecrire_db(conn: sqlite3.Connection, agr: Agregats,
              ressource: dict[str, str]) -> dict:
    """Reconstruit les quatre tables et actualise meta_sources. Idempotent.

    Les identifiants d'administration sont des entiers de surface réattribués
    à chaque passage, par ordre alphabétique de clé normalisée : le résultat
    est donc reproductible à corpus identique, et rien d'autre en base ne les
    référence (les quatre tables sont reconstruites ensemble).
    """
    conn.executescript(_SCHEMA)

    cles = sorted(agr.dossiers_admin)
    ids = {cle: rang for rang, cle in enumerate(cles, start=1)}

    administrations = []
    for cle in cles:
        # Graphie retenue : la plus fréquente ; à égalité, la première dans
        # l'ordre alphabétique — jamais un choix qui dépend de l'ordre de
        # lecture du fichier.
        graphies = agr.graphies[cle]
        libelle = min(graphies.items(), key=lambda kv: (-kv[1], kv[0]))[0]
        premiere, derniere = agr.annees_admin[cle]
        administrations.append((ids[cle], libelle, categorie_administration(cle),
                                agr.dossiers_admin[cle], premiere, derniere))

    with conn:
        # Ordre de purge inverse des dépendances (clés étrangères actives).
        conn.execute("DELETE FROM cada_motifs")
        conn.execute("DELETE FROM cada_sens")
        conn.execute("DELETE FROM cada_saisines")
        conn.execute("DELETE FROM cada_administrations")
        conn.executemany(
            "INSERT INTO cada_administrations "
            "(id, libelle, categorie, nb_dossiers, premiere_annee, derniere_annee) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            administrations,
        )
        conn.executemany(
            "INSERT INTO cada_saisines "
            "(administration_id, annee, type_saisine, nb_dossiers) VALUES (?, ?, ?, ?)",
            ((ids[cle], annee, type_saisine, n)
             for (cle, annee, type_saisine), n in agr.saisines.items()),
        )
        conn.executemany(
            "INSERT INTO cada_sens "
            "(administration_id, annee, type_saisine, sens, nb_dossiers) "
            "VALUES (?, ?, ?, ?, ?)",
            ((ids[cle], annee, type_saisine, sens, n)
             for (cle, annee, type_saisine, sens), n in agr.sens.items()),
        )
        conn.executemany(
            "INSERT INTO cada_motifs "
            "(annee, type_saisine, sens, motivation, nb_dossiers) VALUES (?, ?, ?, ?, ?)",
            ((annee, type_saisine, sens_de(motivation),
              motivation.split("/", 1)[1] if "/" in motivation else None, n)
             for (annee, type_saisine, motivation), n in agr.motifs.items()),
        )

    derniere_seance = agr.derniere_seance
    assert derniere_seance is not None  # garanti par les garde-fous d'executer()
    versement = None
    retard_mois = None
    modif = ressource.get("derniere_modification") or ""
    if modif:
        try:
            versement = datetime.strptime(modif, "%Y-%m-%d").date()
        except ValueError:
            versement = None
    if versement is not None:
        retard_mois = round((versement - derniere_seance).days / 30.44)
        phrase_retard = (
            f"Retard de versement : dernière séance publiée le "
            f"{derniere_seance.strftime('%d/%m/%Y')} alors que le jeu a été modifié "
            f"le {versement.strftime('%d/%m/%Y')} — soit {retard_mois} mois ; "
            f"les derniers millésimes sont donc incomplets par construction."
        )
    else:
        phrase_retard = ("Date de versement amont indisponible : "
                         "le retard n'est pas mesurable ce jour.")

    par_categorie = Counter(a[2] for a in administrations)
    classees = sum(v for c, v in par_categorie.items() if c != "autre")
    volumes = ", ".join(f"{n} {_PLURIELS.get(t, t.lower())}"
                        for t, n in agr.types.most_common())
    notes = (
        f"AGRÉGATS SEULEMENT : le texte intégral des décisions (93 % du CSV de "
        f"198 Mo) n'est jamais ingéré — poids et prudence, les motivations "
        f"nomment des responsables publics. {agr.lignes} décisions dépouillées "
        f"({volumes}), séances du "
        f"{agr.premiere_seance.strftime('%d/%m/%Y') if agr.premiere_seance else '?'} "
        f"au {derniere_seance.strftime('%d/%m/%Y')}, "
        f"{len(administrations)} administrations distinctes "
        f"({classees} classées par préfixe, {par_categorie['autre']} en « autre » : "
        f"le champ est du texte libre, aucun référentiel n'est inventé). "
        f"Colonne « Thème et sous thème » écartée : ses libellés contiennent le "
        f"séparateur, la découpe serait ambiguë. {phrase_retard}"
    )

    db.upsert_meta(
        conn,
        source_id=SOURCE_ID,
        nom=NOM_SOURCE,
        url=URL_DATASET_PAGE,
        licence=LICENCE,
        frequence=FREQUENCE,
        # JAMAIS la date de modification du dataset (SOURCES.md §0.2) : c'est
        # précisément l'écart entre les deux qui est l'information.
        date_donnees=derniere_seance.isoformat(),
        lignes=len(agr.sens),
        notes=notes,
    )

    return {
        "administrations": len(administrations),
        "saisines": len(agr.saisines),
        "sens": len(agr.sens),
        "motifs": len(agr.motifs),
        "decisions": agr.lignes,
        "date_donnees": derniere_seance.isoformat(),
        "retard_mois": retard_mois,
        "categories": dict(par_categorie),
    }


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def executer(chemin_db=None, max_age_heures: float | None = CACHE_HEURES,
             chemin_csv: str | Path | None = None) -> dict:
    """Pipeline complet : résout la ressource, télécharge, agrège, écrit.

    `chemin_csv` court-circuite le réseau (tests, rejeu sur un extrait).
    """
    if chemin_csv is None:
        ressource = resoudre_ressource()
        log.info("ressource « %s » (%s o, modifiée le %s)", ressource["titre"],
                 ressource["octets"] or "?", ressource["derniere_modification"] or "?")
        chemin_csv = telecharger(ressource["url"], FICHIER_CACHE,
                                 max_age_heures=max_age_heures)
    else:
        ressource = {"url": str(chemin_csv), "titre": "extrait local",
                     "derniere_modification": "", "octets": ""}

    agr = agreger(chemin_csv)

    # Garde-fous : une donnée réelle plausible, sinon échec franc. Chacun
    # correspond à un invariant mesuré sur le corpus publié.
    if agr.lignes < 1:
        raise RuntimeError("aucune décision lue dans le CSV consolidé")
    if agr.derniere_seance is None:
        raise RuntimeError("aucune date de séance exploitable : fraîcheur inconnue")
    sens_vus = {s for (_, _, _, s) in agr.sens}
    if not sens_vus <= set(SENS):
        raise RuntimeError(f"sens hors vocabulaire fermé : {sens_vus - set(SENS)}")
    types_vus = set(agr.types)
    if not types_vus <= set(TYPES):
        raise RuntimeError(f"type de saisine inconnu : {types_vus - set(TYPES)}")
    if agr.sans_motivation:
        log.warning("%d décision(s) sans sens exprimé (comptées dans les "
                    "saisines, absentes des sens)", agr.sans_motivation)

    conn = db.init_db(chemin=chemin_db)
    try:
        stats = ecrire_db(conn, agr, ressource)
    finally:
        conn.close()

    log.info(
        "CADA OK : %d décisions → %d administrations, %d saisines, %d agrégats "
        "de sens, %d motivations ; date_donnees=%s (retard de versement : %s)",
        stats["decisions"], stats["administrations"], stats["saisines"],
        stats["sens"], stats["motifs"], stats["date_donnees"],
        f"{stats['retard_mois']} mois" if stats["retard_mois"] is not None else "inconnu",
    )
    return stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="P16 — avis et conseils de la CADA, en agrégats seulement."
    )
    parser.add_argument(
        "--csv", dest="chemin_csv", default=None,
        help="agrège un CSV local au lieu de télécharger la ressource amont",
    )
    args = parser.parse_args(argv)
    try:
        executer(chemin_csv=args.chemin_csv)
    except Exception:
        log.exception("échec du pipeline CADA")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

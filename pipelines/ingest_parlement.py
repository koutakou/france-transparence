"""P9 — Parlement : députés, groupes, scrutins AN + sénateurs (module UI « Élus & Institutions »).

Sources (toutes réelles, appelées à chaque run ; catalogue docs/SOURCES.md,
détails docs/recherche/03-parlement.md) :
- S5 AMO10 (AN, quotidien) : députés actifs / mandats actifs / organes de la
  législature courante — JAMAIS AMO50 (figé au 11/07/2024) ;
- S5 Scrutins.json.zip (AN, quotidien) : tous les scrutins publics de la
  législature, votes nominaux par député ;
- S6 ODSEN_GENERAL.csv + ODSEN_ELUSEN.csv (Sénat, quotidien, ISO-8859-1,
  lignes de commentaire « % » en tête) : sénateurs en exercice ;
- S6 Dosleg dosleg.zip (Sénat, quotidien, UTF-8) : dump PostgreSQL, tables
  `scr` + `votsen` seulement — COPY parsé sans serveur Postgres ; pas Ameli,
  pas questions, pas TAP export_sens ;
- S7 Datan deputes-active.csv (data.gouv.fr, quotidien, fr-lo) : scores de
  participation / loyauté / majorité calculés par Datan (crédités comme tels),
  URL re-résolue via l'API data.gouv à chaque run (convention SOURCES.md §0.3).

Tables écrites (CREATE TABLE IF NOT EXISTS, run idempotent) :
- deputes : uid_an (PK), legislature, nom, prenom, departement,
  num_departement, num_circo, groupe_ref, groupe_sigle, groupe_nom,
  commission_ref, commission, date_debut_mandat, date_prise_fonction,
  date_fin_mandat, url_fiche_an, url_hatvp (fourni par le JSON AN),
  taux_participation_12m / nb_votes_12m / nb_scrutins_12m /
  participation_source / participation_maj (calcul France Transparence sur
  les scrutins AN des 12 derniers mois — fallback documenté des scores Datan),
  datan_score_participation / datan_score_participation_specialite /
  datan_score_loyaute / datan_score_majorite / datan_source / datan_date
  (scores Datan, étiquetés ; les deux familles de scores coexistent).
  La table reflète les députés EN EXERCICE (AMO10 du jour) : les sortants
  sont supprimés de deputes (ils restent dans elus).
- groupes_an : organe_ref (PK), legislature, sigle, nom, effectif (compté
  sur les mandats GP actifs d'AMO10, acteurs distincts), couleur
  (couleurAssociee AN), position (préséance AN).
- senateurs : matricule (PK), nom, prenom, sexe, circonscription
  (département d'élection ; la série de renouvellement n'est pas publiée
  dans ODSEN), groupe, groupe_appartenance (Membre/Rattaché/Apparenté),
  commission, date_debut_mandat / date_fin_mandat (ODSEN_ELUSEN, mandat en
  cours ; fin vide tant que le mandat court — constaté le 19/08/2026 :
  aucune date de fin future publiée avant le renouvellement du 27/09/2026,
  et ELUSEN ne couvre qu'une partie des mandats en cours → NULL assumés),
  date_naissance, profession, email, url_fiche_senat (motif d'URL officiel
  senat.fr/senateur/<nom>_<prenom><matricule>.html, vérifié sur échantillon).
  Table = sénateurs en exercice (état ACTIF) du jour.
- scrutins : uid (PK), legislature, numero (UNIQUE avec legislature), date_scrutin,
  titre, type_vote (libellé AN), sort (« adopté »/« rejeté »), demandeur,
  nombre_votants, suffrages_exprimes, pour, contre, abstentions, non_votants,
  adopte (0/1). TOUS les scrutins de la législature.
- votes_recents : scrutin_uid + uid_an (PK composite), scrutin_numero,
  position (pour/contre/abstention/nonVotant), par_delegation,
  cause_position — détail nominal conservé pour les ~100 derniers scrutins
  seulement (les plus anciens sont copiés vers votes_recents_archive
  puis purgés). Table d'archive NOUVELLE, non servie.
- votes_recents_archive : même grain que votes_recents + archive_le ;
  INSERT OR IGNORE avant le DELETE de fenêtre. Pas un ALTER.
- scrutins_senat : (sesann, numero) PK, date_scrutin, titre, totaux
  pour/contre/votants/exprimés/abstentions, adopte/sort. TOUS les scrutins
  publics Dosleg depuis 2006. Tables NOUVELLES — pas une colonne chambre
  sur `scrutins`.
- votes_senat : (sesann, numero, matricule) PK, position, par_delegation
  (senmatdel renseigné). ~100 derniers scrutins seulement. Les votes
  qui sortent de ces 100 sont copiés vers votes_senat_archive (table
  NOUVELLE, non servie) avant le DELETE ALL.
- participation_senat : matricule PK, taux 12 mois (même formule que
  l'AN : exprimés pour+contre+abstention / scrutins depuis l'entrée en
  mandat). Table dédiée : ODSEN fait INSERT OR REPLACE sur senateurs.
- elus (table noyau, cf. db.py) : UPSERT par uid_an (députés, id = uid_an)
  et par matricule_senat (sénateurs, id = 'SEN-<matricule>') SANS toucher
  aux colonnes des autres pipelines (hatvp_flag notamment) ; la colonne
  mandats (JSON) est fusionnée : seules les entrées source AN-P9/SENAT-P9
  sont remplacées.

Jointures pour le front : elus.uid_an ↔ deputes.uid_an ↔ votes_recents.uid_an
↔ id Datan ; deputes.groupe_ref ↔ groupes_an.organe_ref ;
elus.matricule_senat ↔ senateurs.matricule.

Fraîcheur : upsert_meta() par source — S5-AMO10, S5-SCRUTINS (date_donnees =
date du dernier scrutin ingéré), S6-ODSEN, S6-DOSLEG (date_donnees = date
du dernier scr.scrdat), S7-DATAN (date_donnees = dateMaj du CSV).
Législature paramétrable via FT_LEGISLATURE (défaut 17), jamais en dur
dans les URL.

Robustesse : l'échec d'UNE source n'arrête pas les autres ; le bilan final
liste les échecs et le processus sort avec un code ≠ 0 s'il y en a eu.
Aucune donnée inventée : tout champ absent de la source reste NULL.

Volumétrie mesurée le 19/08/2026 : AMO10 4,9 Mo + Scrutins 26,3 Mo +
ODSEN ~0,9 Mo + Datan ~0,2 Mo ; parse complet des 8 434 scrutins ≈ 1 s
(mesuré) → le re-parse intégral quotidien est moins fragile qu'un diff et
reste très en deçà du budget (< 10 min).

Exécution : python -m pipelines.ingest_parlement
(FT_DB_PATH pour rejouer sur base jetable).
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
import sys
import unicodedata
import zipfile
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from itertools import dropwhile
from pathlib import Path

import requests

from pipelines import db
from pipelines.archive_fenetre import archiver_sortie_fenetre
from pipelines.common import (
    assainir_texte,
    obtenir_logger,
    session_http,
    telecharger,
)

log = obtenir_logger("parlement")

LEGISLATURE = int(os.environ.get("FT_LEGISLATURE", "17"))

BASE_AN = ("https://data.assemblee-nationale.fr/static/openData/repository/"
           f"{LEGISLATURE}")
URL_AMO10 = (f"{BASE_AN}/amo/deputes_actifs_mandats_actifs_organes/"
             "AMO10_deputes_actifs_mandats_actifs_organes.json.zip")
URL_SCRUTINS = f"{BASE_AN}/loi/scrutins/Scrutins.json.zip"
URL_ODSEN_GENERAL = "https://data.senat.fr/data/senateurs/ODSEN_GENERAL.csv"
URL_ODSEN_ELUSEN = "https://data.senat.fr/data/senateurs/ODSEN_ELUSEN.csv"
URL_DOSLEG = "https://data.senat.fr/data/dosleg/dosleg.zip"
# posvotcod Dosleg (table posvot) — votes exprimés = 1/2/3, pas le 4.
POSVOT_SENAT = {
    "1": "pour",
    "2": "contre",
    "3": "abstention",
    "4": "nonVotant",
}
# S7 : l'URL du CSV est horodatée (static.data.gouv.fr) → re-résolution via
# l'API data.gouv à chaque run (SOURCES.md §0.3).
URL_API_DATASET_DATAN = ("https://www.data.gouv.fr/api/1/datasets/"
                         "deputes-actifs-de-lassemblee-nationale-"
                         "informations-et-statistiques/")

# Détail nominal conservé pour les N derniers scrutins (task/SOURCES.md).
NB_SCRUTINS_DETAIL = 100
COLONNES_VOTES_RECENTS = (
    "scrutin_uid", "scrutin_numero", "uid_an",
    "position", "par_delegation", "cause_position",
)
COLONNES_VOTES_SENAT = (
    "sesann", "numero", "matricule", "position", "par_delegation",
)
# Fenêtre des agrégats de participation.
FENETRE_JOURS = 365

# Cache local : re-téléchargement au plus toutes les 6 h (sources quotidiennes).
MAX_AGE_H = 6.0

_SCHEMA_P9 = """
CREATE TABLE IF NOT EXISTS deputes (
    uid_an              TEXT PRIMARY KEY,      -- PAxxxx (open data AN)
    legislature         INTEGER NOT NULL,
    nom                 TEXT NOT NULL,
    prenom              TEXT,
    departement         TEXT,                  -- nom du département d'élection
    num_departement     TEXT,
    num_circo           TEXT,
    groupe_ref          TEXT,                  -- organe GP (POxxxx)
    groupe_sigle        TEXT,
    groupe_nom          TEXT,
    commission_ref      TEXT,                  -- organe COMPER (POxxxx)
    commission          TEXT,
    date_debut_mandat   TEXT,                  -- mandat ASSEMBLEE en cours
    date_prise_fonction TEXT,
    date_fin_mandat     TEXT,                  -- NULL tant que le mandat court
    url_fiche_an        TEXT,
    url_hatvp           TEXT,                  -- uri_hatvp du JSON AN si présent
    -- calcul France Transparence (scrutins AN, 12 derniers mois)
    taux_participation_12m REAL,               -- 0-100 (%)
    nb_votes_12m        INTEGER,
    nb_scrutins_12m     INTEGER,               -- dénominateur (scrutins du mandat)
    participation_source TEXT,
    participation_maj   TEXT,
    -- scores Datan (source créditée, coexistent avec le calcul ci-dessus)
    datan_score_participation            REAL, -- 0-1 (tel que publié)
    datan_score_participation_specialite REAL,
    datan_score_loyaute                  REAL,
    datan_score_majorite                 REAL,
    datan_source        TEXT,
    datan_date          TEXT
);
CREATE INDEX IF NOT EXISTS idx_deputes_groupe ON deputes(groupe_sigle);
CREATE INDEX IF NOT EXISTS idx_deputes_departement ON deputes(num_departement);

CREATE TABLE IF NOT EXISTS groupes_an (
    organe_ref  TEXT PRIMARY KEY,
    legislature INTEGER NOT NULL,
    sigle       TEXT NOT NULL,
    nom         TEXT NOT NULL,
    effectif    INTEGER NOT NULL,
    couleur     TEXT,
    position    TEXT                            -- préséance AN (ordre d'affichage)
);

CREATE TABLE IF NOT EXISTS senateurs (
    matricule         TEXT PRIMARY KEY,
    nom               TEXT NOT NULL,
    prenom            TEXT,
    sexe              TEXT,
    circonscription   TEXT,                     -- département (série non publiée)
    groupe            TEXT,
    groupe_appartenance TEXT,                   -- Membre / Rattaché / Apparenté
    commission        TEXT,
    date_debut_mandat TEXT,                     -- ODSEN_ELUSEN si publié
    date_fin_mandat   TEXT,                     -- NULL : mandat en cours
    date_naissance    TEXT,
    profession        TEXT,
    email             TEXT,                     -- 'Non public' possible
    url_fiche_senat   TEXT
);
CREATE INDEX IF NOT EXISTS idx_senateurs_groupe ON senateurs(groupe);

CREATE TABLE IF NOT EXISTS scrutins (
    uid                TEXT PRIMARY KEY,        -- VTANR5L17Vnnnn
    legislature        INTEGER NOT NULL,
    numero             INTEGER NOT NULL,
    date_scrutin       TEXT NOT NULL,
    titre              TEXT,
    type_vote          TEXT,
    sort               TEXT,                    -- 'adopté' / 'rejeté'
    demandeur          TEXT,
    nombre_votants     INTEGER,
    suffrages_exprimes INTEGER,
    pour               INTEGER,
    contre             INTEGER,
    abstentions        INTEGER,
    non_votants        INTEGER,
    adopte             INTEGER NOT NULL DEFAULT 0,
    UNIQUE (legislature, numero)
);
CREATE INDEX IF NOT EXISTS idx_scrutins_date ON scrutins(date_scrutin);

CREATE TABLE IF NOT EXISTS votes_recents (
    scrutin_uid     TEXT NOT NULL,
    scrutin_numero  INTEGER NOT NULL,
    uid_an          TEXT NOT NULL,
    position        TEXT NOT NULL CHECK (position IN
                      ('pour','contre','abstention','nonVotant')),
    par_delegation  INTEGER NOT NULL DEFAULT 0,
    cause_position  TEXT,                       -- ex. PAN/PSE pour les non-votants
    PRIMARY KEY (scrutin_uid, uid_an)
);
CREATE INDEX IF NOT EXISTS idx_votes_recents_acteur ON votes_recents(uid_an);

-- Archive locale, NON servie. Table NOUVELLE : pas un ALTER de
-- votes_recents (CREATE TABLE IF NOT EXISTS ne migre pas france.db).
CREATE TABLE IF NOT EXISTS votes_recents_archive (
    scrutin_uid     TEXT NOT NULL,
    scrutin_numero  INTEGER NOT NULL,
    uid_an          TEXT NOT NULL,
    position        TEXT NOT NULL CHECK (position IN
                      ('pour','contre','abstention','nonVotant')),
    par_delegation  INTEGER NOT NULL DEFAULT 0,
    cause_position  TEXT,
    archive_le      TEXT NOT NULL,
    PRIMARY KEY (scrutin_uid, uid_an)
);
CREATE INDEX IF NOT EXISTS idx_votes_recents_archive_acteur
    ON votes_recents_archive(uid_an);

-- Scrutins / votes Sénat : TABLES NOUVELLES. Ne pas ajouter de colonne
-- `chambre` à scrutins / votes_recents (CREATE TABLE IF NOT EXISTS ne
-- migre pas france.db persistante ; votes_recents.uid_an n'est pas un
-- matricule). Clé = (sesann, numero) : scrnum est local à la session.
CREATE TABLE IF NOT EXISTS scrutins_senat (
    sesann             INTEGER NOT NULL,
    numero             INTEGER NOT NULL,
    date_scrutin       TEXT NOT NULL,
    titre              TEXT,
    nombre_votants     INTEGER,
    suffrages_exprimes INTEGER,
    pour               INTEGER,
    contre             INTEGER,
    abstentions        INTEGER,
    adopte             INTEGER NOT NULL DEFAULT 0,
    sort               TEXT,
    PRIMARY KEY (sesann, numero)
);
CREATE INDEX IF NOT EXISTS idx_scrutins_senat_date ON scrutins_senat(date_scrutin);

CREATE TABLE IF NOT EXISTS votes_senat (
    sesann          INTEGER NOT NULL,
    numero          INTEGER NOT NULL,
    matricule       TEXT NOT NULL,
    position        TEXT NOT NULL CHECK (position IN
                      ('pour','contre','abstention','nonVotant')),
    par_delegation  INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (sesann, numero, matricule)
);
CREATE INDEX IF NOT EXISTS idx_votes_senat_acteur ON votes_senat(matricule);

CREATE TABLE IF NOT EXISTS votes_senat_archive (
    sesann          INTEGER NOT NULL,
    numero          INTEGER NOT NULL,
    matricule       TEXT NOT NULL,
    position        TEXT NOT NULL CHECK (position IN
                      ('pour','contre','abstention','nonVotant')),
    par_delegation  INTEGER NOT NULL DEFAULT 0,
    archive_le      TEXT NOT NULL,
    PRIMARY KEY (sesann, numero, matricule)
);
CREATE INDEX IF NOT EXISTS idx_votes_senat_archive_acteur
    ON votes_senat_archive(matricule);

-- Agrégats 12 mois : table dédiée (ODSEN fait INSERT OR REPLACE sur
-- senateurs — des colonnes ajoutées là seraient écrasées chaque run).
CREATE TABLE IF NOT EXISTS participation_senat (
    matricule              TEXT PRIMARY KEY,
    taux_participation_12m REAL,
    nb_votes_12m           INTEGER,
    nb_scrutins_12m        INTEGER,
    participation_source   TEXT,
    participation_maj      TEXT
);
"""

def archiver_votes_recents_sous_seuil(
    conn, seuil_detail: int, archive_le: str
) -> int:
    """Copie vers votes_recents_archive les nominaux sous le seuil (100)."""
    return archiver_sortie_fenetre(
        conn,
        source="votes_recents",
        archive="votes_recents_archive",
        colonnes=COLONNES_VOTES_RECENTS,
        where="scrutin_numero < ?",
        params=(seuil_detail,),
        archive_le=archive_le,
    )


def archiver_votes_senat_hors_cles(
    conn, cles_detail: set[tuple[int, int]], archive_le: str
) -> int:
    """Copie les votes_senat dont (sesann, numero) n'est plus dans les 100."""
    conn.execute("DROP TABLE IF EXISTS _cles_votes_senat_gardes")
    conn.execute(
        """CREATE TEMP TABLE _cles_votes_senat_gardes (
               sesann INTEGER NOT NULL,
               numero INTEGER NOT NULL,
               PRIMARY KEY (sesann, numero)
           )"""
    )
    if cles_detail:
        conn.executemany(
            "INSERT INTO _cles_votes_senat_gardes(sesann, numero) VALUES (?, ?)",
            list(cles_detail),
        )
    n = archiver_sortie_fenetre(
        conn,
        source="votes_senat",
        archive="votes_senat_archive",
        colonnes=COLONNES_VOTES_SENAT,
        where=(
            "NOT EXISTS (SELECT 1 FROM _cles_votes_senat_gardes g "
            "WHERE g.sesann = votes_senat.sesann "
            "AND g.numero = votes_senat.numero)"
        ),
        params=(),
        archive_le=archive_le,
    )
    conn.execute("DROP TABLE IF EXISTS _cles_votes_senat_gardes")
    return n


# ---------------------------------------------------------------------------
# Helpers de parsing (purs, testés dans tests/test_parlement.py)
# ---------------------------------------------------------------------------


def as_list(x) -> list:
    """Champ AN « objet ou liste selon la cardinalité » → toujours une liste."""
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


def _texte(x) -> str | None:
    """Valeur AN parfois emballée en {'#text': ...} ou en dict-nil
    {'@xsi:nil': 'true'} (constaté sur uri_hatvp d'un acteur réel)."""
    if isinstance(x, dict):
        return x.get("#text")  # None pour un dict-nil
    return x


def parser_acteur(data: dict) -> dict:
    """Extrait d'un fichier acteur AMO10 les champs utiles au dashboard.

    Retourne un dict : uid, nom, prenom, sexe, date_naissance, profession,
    url_hatvp, et pour les mandats ACTIFS (dateFin nulle) : assemblee
    (dict du mandat de député), groupe_ref, commission_ref.
    """
    a = data["acteur"]
    ident = a["etatCivil"]["ident"]
    civ = _texte(ident.get("civ"))
    naissance = _texte((a["etatCivil"].get("infoNaissance") or {}).get("dateNais"))
    profession = _texte((a.get("profession") or {}).get("libelleCourant"))
    out = {
        "uid": _texte(a["uid"]),
        "nom": _texte(ident.get("nom")),
        "prenom": _texte(ident.get("prenom")),
        "sexe": {"M.": "M", "Mme": "F"}.get(civ),
        "date_naissance": naissance,
        "profession": profession,
        "url_hatvp": _texte(a.get("uri_hatvp")),
        "assemblee": None,
        "groupe_ref": None,
        "commission_ref": None,
    }
    for m in as_list((a.get("mandats") or {}).get("mandat")):
        if _texte(m.get("dateFin")) is not None:
            continue  # AMO10 = mandats actifs, mais on reste défensif
        type_organe = m.get("typeOrgane")
        organe_ref = (m.get("organes") or {}).get("organeRef")
        if type_organe == "ASSEMBLEE":
            lieu = (m.get("election") or {}).get("lieu") or {}
            out["assemblee"] = {
                "date_debut": _texte(m.get("dateDebut")),
                "date_fin": _texte(m.get("dateFin")),
                "date_prise_fonction": _texte((m.get("mandature") or {}).get(
                    "datePriseFonction")),
                "departement": _texte(lieu.get("departement")),
                "num_departement": _texte(lieu.get("numDepartement")),
                "num_circo": _texte(lieu.get("numCirco")),
                "legislature": _texte(m.get("legislature")),
            }
        elif type_organe == "GP":
            # Un président de groupe a deux mandats GP (Membre + Président)
            # sur le MÊME organe : le premier réf rencontré suffit.
            out["groupe_ref"] = out["groupe_ref"] or organe_ref
        elif type_organe == "COMPER":
            out["commission_ref"] = out["commission_ref"] or organe_ref
    return out


def parser_organe(data: dict) -> dict:
    """Champs utiles d'un organe AMO10 (groupe, commission…)."""
    o = data["organe"]
    return {
        "uid": _texte(o["uid"]),
        "code_type": o.get("codeType"),
        "nom": o.get("libelle"),
        "sigle": o.get("libelleAbrev"),
        "couleur": o.get("couleurAssociee"),
        "position": o.get("preseance"),
        "legislature": o.get("legislature"),
    }


def parser_scrutin(data: dict) -> tuple[dict, list[tuple[str, str, int, str | None]]]:
    """Un fichier scrutin AN → (méta, votes nominaux).

    votes : liste de (uid_an, position, par_delegation, cause_position),
    position ∈ pour/contre/abstention/nonVotant. Les absents ne figurent
    pas dans la donnée source (seuls les votes exprimés et les non-votants
    déclarés sont nominatifs).
    """
    s = data["scrutin"]
    synthese = s.get("syntheseVote") or {}
    decompte = synthese.get("decompte") or {}

    def _i(v):
        return int(v) if v not in (None, "") else None

    meta = {
        "uid": s["uid"],
        "legislature": int(s["legislature"]),
        "numero": int(s["numero"]),
        "date_scrutin": s["dateScrutin"],
        "titre": s.get("titre"),
        "type_vote": (s.get("typeVote") or {}).get("libelleTypeVote"),
        "sort": (s.get("sort") or {}).get("code"),
        "demandeur": (s.get("demandeur") or {}).get("texte"),
        "nombre_votants": _i(synthese.get("nombreVotants")),
        "suffrages_exprimes": _i(synthese.get("suffragesExprimes")),
        "pour": _i(decompte.get("pour")),
        "contre": _i(decompte.get("contre")),
        "abstentions": _i(decompte.get("abstentions")),
        "non_votants": _i(decompte.get("nonVotants")),
    }
    meta["adopte"] = 1 if meta["sort"] == "adopté" else 0

    votes: list[tuple[str, str, int, str | None]] = []
    positions = (("pours", "pour"), ("contres", "contre"),
                 ("abstentions", "abstention"), ("nonVotants", "nonVotant"))
    organe = (s.get("ventilationVotes") or {}).get("organe") or {}
    for groupe in as_list((organe.get("groupes") or {}).get("groupe")):
        dn = (groupe.get("vote") or {}).get("decompteNominatif") or {}
        for cle, position in positions:
            bloc = dn.get(cle)
            if not bloc:
                continue
            for votant in as_list(bloc.get("votant")):
                votes.append((
                    votant.get("acteurRef"),
                    position,
                    1 if votant.get("parDelegation") == "true" else 0,
                    votant.get("causePositionVote"),
                ))
    return meta, votes


def lire_csv_senat(octets: bytes) -> list[dict]:
    """CSV Sénat → liste de dicts.

    Pièges réels (constatés le 19/08/2026) : encodage ISO-8859-1, lignes de
    commentaire « % » en tête (requête SQL d'export), séparateur « , » sur
    les ODSEN_* actuels, dates au format 'AAAA-MM-JJ 00:00:00.0'.
    """
    texte = octets.decode("iso-8859-1")
    lignes = list(dropwhile(lambda l: l.startswith("%"), texte.splitlines()))
    lecteur = csv.DictReader(lignes)
    return [dict(r) for r in lecteur]


def nettoyer_date_senat(v: str | None) -> str | None:
    """'1974-04-17 00:00:00.0' → '1974-04-17' ; vide → None."""
    if not v:
        return None
    return v.strip()[:10] or None


def construire_url_senateur(nom: str, prenom: str, matricule: str) -> str:
    """URL de la fiche officielle senat.fr (motif vérifié sur échantillon réel :
    aeschlimann_marie_do21071f, allizard_pascal14133k, kerrouche_eric19489j,
    tous HTTP 200 le 19/08/2026)."""
    def slug(t: str) -> str:
        t = unicodedata.normalize("NFKD", t or "")
        t = "".join(c for c in t if not unicodedata.combining(c))
        t = re.sub(r"[^a-z0-9]+", "_", t.lower()).strip("_")
        return t
    return (f"https://www.senat.fr/senateur/"
            f"{slug(nom)}_{slug(prenom)}{matricule.lower()}.html")


def calculer_participation(
    scrutins_fenetre: list[tuple[str, set[str]]],
    debut_mandat: dict[str, str],
) -> dict[str, tuple[int, int, float | None]]:
    """Taux de participation par député sur une fenêtre de scrutins.

    - scrutins_fenetre : liste (date_scrutin ISO, ensemble des uid_an ayant
      EXPRIMÉ un vote — pour/contre/abstention ; les non-votants déclarés
      (président de séance…) ne comptent pas comme participation) ;
    - debut_mandat : uid_an → date de début du mandat de député (ISO).

    Retour : uid_an → (nb_votes, nb_scrutins_eligibles, taux_pct ou None).
    Le dénominateur d'un député = scrutins de la fenêtre postérieurs ou
    égaux à son entrée en mandat (un élu de mars n'est pas pénalisé des
    scrutins de janvier). Taux None si aucun scrutin éligible.
    """
    resultat: dict[str, tuple[int, int, float | None]] = {}
    for uid, debut in debut_mandat.items():
        eligibles = 0
        votes = 0
        for date_scrutin, participants in scrutins_fenetre:
            if debut and date_scrutin < debut:
                continue
            eligibles += 1
            if uid in participants:
                votes += 1
        taux = round(100.0 * votes / eligibles, 2) if eligibles else None
        resultat[uid] = (votes, eligibles, taux)
    return resultat


# ---------------------------------------------------------------------------
# Dosleg (dump PostgreSQL) — COPY sans serveur Postgres
# ---------------------------------------------------------------------------


def decoder_champ_copy(champ: str) -> str | None:
    """Décode un champ COPY PostgreSQL (format texte).

    Un champ égal à ``\\N`` est NULL. Les séquences ``\\t`` ``\\n`` ``\\r``
    ``\\\\`` et l'octal ``\\nnn`` sont rétablies. Le dump Dosleg est UTF-8
    (pas l'ISO-8859-1 d'ODSEN).
    """
    if champ == r"\N":
        return None
    out: list[str] = []
    i = 0
    n = len(champ)
    while i < n:
        ch = champ[i]
        if ch != "\\":
            out.append(ch)
            i += 1
            continue
        i += 1
        if i >= n:
            out.append("\\")
            break
        nxt = champ[i]
        if nxt == "N":
            out.append("N")
        elif nxt == "t":
            out.append("\t")
        elif nxt == "n":
            out.append("\n")
        elif nxt == "r":
            out.append("\r")
        elif nxt == "b":
            out.append("\b")
        elif nxt == "f":
            out.append("\f")
        elif nxt == "v":
            out.append("\v")
        elif nxt == "\\":
            out.append("\\")
        elif nxt.isdigit():
            j = i
            while j < n and j < i + 3 and champ[j].isdigit():
                j += 1
            out.append(chr(int(champ[i:j], 8)))
            i = j
            continue
        else:
            out.append(nxt)
        i += 1
    return "".join(out)


def decoder_ligne_copy(raw: bytes) -> list[str | None]:
    """Une ligne COPY (tabulation, UTF-8) → champs décodés."""
    return [decoder_champ_copy(p) for p in raw.decode("utf-8").split("\t")]


def _lignes_binaires(fp) -> object:
    """Itère les lignes d'un flux binaire sans tout charger."""
    buf = b""
    while True:
        chunk = fp.read(1 << 20)
        if not chunk:
            if buf:
                yield buf
            return
        buf += chunk
        while True:
            i = buf.find(b"\n")
            if i < 0:
                break
            yield buf[:i]
            buf = buf[i + 1:]


_COPY_ENTETE = re.compile(r"^COPY (\w+) \((.*)\) FROM stdin;$")


def iterer_copy_postgres(fp, tables: set[str]):
    """Lit un dump PostgreSQL et cède ``(table, {colonne: valeur})``.

    Les autres tables COPY sont sautées (on n'ingère pas Ameli, dossiers,
    rapports). ``\\.`` termine un bloc. Pas de serveur Postgres.
    """
    courant: str | None = None
    colonnes: list[str] = []
    for raw in _lignes_binaires(fp):
        if courant is None:
            if not raw.startswith(b"COPY "):
                continue
            m = _COPY_ENTETE.match(raw.decode("utf-8"))
            if not m:
                continue
            nom = m.group(1)
            if nom in tables:
                courant = nom
                colonnes = [c.strip() for c in m.group(2).split(",")]
            else:
                courant = "__skip__"
                colonnes = []
            continue
        if raw == b"\\.":
            courant = None
            colonnes = []
            continue
        if courant == "__skip__":
            continue
        champs = decoder_ligne_copy(raw)
        if len(champs) != len(colonnes):
            raise RuntimeError(
                f"Dosleg COPY {courant} : {len(champs)} champs "
                f"pour {len(colonnes)} colonnes"
            )
        yield courant, dict(zip(colonnes, champs))


def _entier_copy(valeur: str | None) -> int | None:
    if valeur is None or valeur == "":
        return None
    try:
        return int(valeur)
    except ValueError:
        return None


def _date_copy(valeur: str | None) -> str | None:
    """Timestamp COPY → ISO date (YYYY-MM-DD)."""
    if not valeur:
        return None
    return valeur[:10]


def _titre_dosleg(brut: str | None) -> str | None:
    """Intitulé Dosleg : U+0092 du dump (apostrophe Windows) → apostrophe."""
    if brut is None:
        return None
    return assainir_texte(brut.replace("\u0092", "'").replace("\u0085", "…"))


def _matricule_dosleg(brut: str | None) -> str | None:
    """character(6) PostgreSQL : espaces de padding à droite."""
    if brut is None:
        return None
    m = brut.strip()
    return m or None


def _sort_scrutin_senat(
    pour: int | None, contre: int | None
) -> tuple[int, str | None]:
    """Résultat officiel : pour > contre → adopté. Pas un score de loyauté."""
    if pour is None or contre is None:
        return 0, None
    adopte = 1 if pour > contre else 0
    return adopte, "adopté" if adopte else "rejeté"


# ---------------------------------------------------------------------------
# Upsert elus (sans écraser les colonnes des autres pipelines)
# ---------------------------------------------------------------------------


def _fusionner_mandats(existant: str | None, entree: dict, source: str) -> str:
    """Fusionne la colonne elus.mandats (JSON) : remplace uniquement les
    entrées portées par `source`, préserve celles des autres pipelines."""
    try:
        mandats = json.loads(existant) if existant else []
        if not isinstance(mandats, list):
            mandats = [mandats]
    except (ValueError, TypeError):
        mandats = []
    mandats = [m for m in mandats
               if not (isinstance(m, dict) and m.get("source") == source)]
    entree = dict(entree)
    entree["source"] = source
    mandats.append(entree)
    return json.dumps(mandats, ensure_ascii=False)


def upsert_elu(
    conn,
    *,
    cle: str,                      # 'uid_an' ou 'matricule_senat'
    valeur_cle: str,
    id_defaut: str,
    nom: str,
    prenom: str | None,
    sexe: str | None,
    date_naissance: str | None,
    profession: str | None,
    mandat: dict,
    source_mandat: str,
) -> None:
    """UPSERT dans la table noyau elus par identifiant de chambre.

    Ne touche JAMAIS aux colonnes des autres pipelines (hatvp_flag, et
    l'identifiant de l'autre chambre) ; la colonne mandats est fusionnée.
    """
    ligne = conn.execute(
        f"SELECT id, mandats FROM elus WHERE {cle} = ?", (valeur_cle,)
    ).fetchone()
    if ligne:
        mandats = _fusionner_mandats(ligne["mandats"], mandat, source_mandat)
        conn.execute(
            """UPDATE elus SET nom = ?, prenom = ?, sexe = ?,
               date_naissance = ?, profession = ?, mandats = ? WHERE id = ?""",
            (nom, prenom, sexe, date_naissance, profession, mandats,
             ligne["id"]),
        )
    else:
        mandats = _fusionner_mandats(None, mandat, source_mandat)
        conn.execute(
            f"""INSERT INTO elus
                (id, nom, prenom, sexe, date_naissance, profession,
                 {cle}, mandats)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (id_defaut, nom, prenom, sexe, date_naissance, profession,
             valeur_cle, mandats),
        )


# ---------------------------------------------------------------------------
# Étapes d'ingestion (une par source)
# ---------------------------------------------------------------------------


def _date_last_modified(session: requests.Session, url: str) -> str:
    """Date (ISO) du Last-Modified serveur ; à défaut, date du jour (les
    dumps AN/Sénat sont des instantanés quotidiens de l'état courant)."""
    try:
        r = session.head(url, timeout=60, allow_redirects=True)
        lm = r.headers.get("Last-Modified")
        if lm:
            return parsedate_to_datetime(lm).date().isoformat()
    except requests.RequestException:
        pass
    return date.today().isoformat()


def ingerer_amo10(conn, session: requests.Session) -> None:
    """AN AMO10 → deputes + groupes_an + elus."""
    date_donnees = _date_last_modified(session, URL_AMO10)
    chemin = telecharger(URL_AMO10, "parlement/AMO10_deputes_actifs_mandats_actifs_organes.json.zip",
                         max_age_heures=MAX_AGE_H, session=session)
    z = zipfile.ZipFile(chemin)
    acteurs = []
    for nom_fichier in z.namelist():
        if "/acteur/" in nom_fichier and nom_fichier.endswith(".json"):
            acteurs.append(parser_acteur(json.loads(z.read(nom_fichier))))
    if not acteurs:
        raise RuntimeError("AMO10 : aucun acteur dans le zip")
    log.info("AMO10 : %d députés actifs", len(acteurs))

    # Organes référencés (groupes + commissions) chargés à la demande.
    refs = {a["groupe_ref"] for a in acteurs} | {a["commission_ref"] for a in acteurs}
    organes: dict[str, dict] = {}
    for ref in sorted(r for r in refs if r):
        organes[ref] = parser_organe(json.loads(z.read(f"json/organe/{ref}.json")))

    effectifs: dict[str, set[str]] = {}
    for a in acteurs:
        if a["groupe_ref"]:
            effectifs.setdefault(a["groupe_ref"], set()).add(a["uid"])

    with conn:
        for a in acteurs:
            ass = a["assemblee"] or {}
            groupe = organes.get(a["groupe_ref"] or "", {})
            commission = organes.get(a["commission_ref"] or "", {})
            conn.execute(
                """INSERT INTO deputes
                     (uid_an, legislature, nom, prenom, departement,
                      num_departement, num_circo, groupe_ref, groupe_sigle,
                      groupe_nom, commission_ref, commission,
                      date_debut_mandat, date_prise_fonction, date_fin_mandat,
                      url_fiche_an, url_hatvp)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(uid_an) DO UPDATE SET
                     legislature = excluded.legislature,
                     nom = excluded.nom, prenom = excluded.prenom,
                     departement = excluded.departement,
                     num_departement = excluded.num_departement,
                     num_circo = excluded.num_circo,
                     groupe_ref = excluded.groupe_ref,
                     groupe_sigle = excluded.groupe_sigle,
                     groupe_nom = excluded.groupe_nom,
                     commission_ref = excluded.commission_ref,
                     commission = excluded.commission,
                     date_debut_mandat = excluded.date_debut_mandat,
                     date_prise_fonction = excluded.date_prise_fonction,
                     date_fin_mandat = excluded.date_fin_mandat,
                     url_fiche_an = excluded.url_fiche_an,
                     url_hatvp = excluded.url_hatvp""",
                (a["uid"], LEGISLATURE, a["nom"], a["prenom"],
                 ass.get("departement"), ass.get("num_departement"),
                 ass.get("num_circo"), a["groupe_ref"],
                 groupe.get("sigle"), groupe.get("nom"),
                 a["commission_ref"], commission.get("nom"),
                 ass.get("date_debut"), ass.get("date_prise_fonction"),
                 ass.get("date_fin"),
                 f"https://www.assemblee-nationale.fr/dyn/deputes/{a['uid']}",
                 a["url_hatvp"]),
            )
            upsert_elu(
                conn,
                cle="uid_an", valeur_cle=a["uid"], id_defaut=a["uid"],
                nom=a["nom"], prenom=a["prenom"], sexe=a["sexe"],
                date_naissance=a["date_naissance"], profession=a["profession"],
                mandat={
                    "type": "depute", "legislature": LEGISLATURE,
                    "date_debut": ass.get("date_debut"),
                    "date_fin": ass.get("date_fin"),
                    "departement": ass.get("departement"),
                    "circonscription": ass.get("num_circo"),
                    "groupe": groupe.get("sigle"),
                },
                source_mandat="AN-P9",
            )
        # Députés sortis du dump du jour → hors exercice, retirés de deputes.
        uids = [a["uid"] for a in acteurs]
        marqueurs = ",".join("?" * len(uids))
        conn.execute(
            f"DELETE FROM deputes WHERE legislature = ? AND uid_an NOT IN ({marqueurs})",
            [LEGISLATURE, *uids],
        )
        # Groupes politiques : remplacés pour la législature courante.
        conn.execute("DELETE FROM groupes_an WHERE legislature = ?", (LEGISLATURE,))
        for ref, membres in sorted(effectifs.items()):
            o = organes[ref]
            conn.execute(
                """INSERT INTO groupes_an
                     (organe_ref, legislature, sigle, nom, effectif, couleur, position)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (ref, LEGISLATURE, o["sigle"], o["nom"], len(membres),
                 o["couleur"], o["position"]),
            )
    db.upsert_meta(
        conn, source_id="S5-AMO10",
        nom="AN — députés, mandats, organes actifs (AMO10)",
        url=URL_AMO10, licence="Licence Ouverte (AN)", frequence="quotidienne",
        date_donnees=date_donnees, lignes=len(acteurs),
        notes=(f"législature {LEGISLATURE} ; {len(effectifs)} groupes ; "
               "AMO50 proscrit (figé au 11/07/2024) ; lien HATVP fourni par "
               "le champ uri_hatvp de l'AN"),
    )
    log.info("AMO10 : %d députés, %d groupes écrits", len(acteurs), len(effectifs))


def ingerer_scrutins(conn, session: requests.Session) -> None:
    """AN Scrutins → scrutins (tous) + votes_recents (~100 derniers)
    + agrégats de participation 12 mois dans deputes."""
    chemin = telecharger(URL_SCRUTINS, "parlement/Scrutins.json.zip",
                         max_age_heures=MAX_AGE_H, session=session)
    z = zipfile.ZipFile(chemin)
    fichiers = [n for n in z.namelist() if n.endswith(".json")]
    if not fichiers:
        raise RuntimeError("Scrutins : zip vide")

    date_min_fenetre = (date.today() - timedelta(days=FENETRE_JOURS)).isoformat()
    metas: list[dict] = []
    votes_par_scrutin: dict[int, list] = {}       # numero -> votes nominaux
    fenetre: list[tuple[str, set[str]]] = []      # (date, participants exprimés)
    for nom_fichier in fichiers:
        meta, votes = parser_scrutin(json.loads(z.read(nom_fichier)))
        metas.append(meta)
        votes_par_scrutin[meta["numero"]] = (meta["uid"], votes)
        if meta["date_scrutin"] >= date_min_fenetre:
            exprimes = {uid for uid, pos, _, _ in votes
                        if pos in ("pour", "contre", "abstention") and uid}
            fenetre.append((meta["date_scrutin"], exprimes))
    metas.sort(key=lambda m: m["numero"])
    dernier = metas[-1]
    seuil_detail = dernier["numero"] - NB_SCRUTINS_DETAIL + 1

    with conn:
        conn.executemany(
            """INSERT OR REPLACE INTO scrutins
                 (uid, legislature, numero, date_scrutin, titre, type_vote,
                  sort, demandeur, nombre_votants, suffrages_exprimes,
                  pour, contre, abstentions, non_votants, adopte)
               VALUES (:uid, :legislature, :numero, :date_scrutin, :titre,
                       :type_vote, :sort, :demandeur, :nombre_votants,
                       :suffrages_exprimes, :pour, :contre, :abstentions,
                       :non_votants, :adopte)""",
            metas,
        )
        # Détail nominal : fenêtre glissante des ~100 derniers scrutins.
        # Copier AVANT le DELETE : sinon la ligne n'existe plus nulle part.
        n_arch = archiver_votes_recents_sous_seuil(
            conn, seuil_detail, date.today().isoformat()
        )
        if n_arch:
            log.info(
                "votes_recents : %d lignes sorties de fenêtre archivées", n_arch
            )
        conn.execute("DELETE FROM votes_recents WHERE scrutin_numero < ?",
                     (seuil_detail,))
        lignes_votes = []
        for numero in range(seuil_detail, dernier["numero"] + 1):
            if numero not in votes_par_scrutin:
                continue
            uid_scrutin, votes = votes_par_scrutin[numero]
            for uid_an, position, delegation, cause in votes:
                if uid_an:
                    lignes_votes.append((uid_scrutin, numero, uid_an,
                                         position, delegation, cause))
        conn.executemany(
            """INSERT OR REPLACE INTO votes_recents
                 (scrutin_uid, scrutin_numero, uid_an, position,
                  par_delegation, cause_position)
               VALUES (?, ?, ?, ?, ?, ?)""",
            lignes_votes,
        )

    # Agrégats 12 mois : dénominateur = scrutins du mandat de chaque député
    # en exercice (deputes vient d'être rafraîchi par AMO10 ; si la table est
    # vide — échec AMO10 sur base neuve — on saute honnêtement le calcul).
    deputes = conn.execute(
        "SELECT uid_an, date_debut_mandat FROM deputes WHERE legislature = ?",
        (LEGISLATURE,),
    ).fetchall()
    if deputes:
        debuts = {d["uid_an"]: d["date_debut_mandat"] for d in deputes}
        taux = calculer_participation(fenetre, debuts)
        maintenant = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with conn:
            conn.executemany(
                """UPDATE deputes SET taux_participation_12m = ?,
                     nb_votes_12m = ?, nb_scrutins_12m = ?,
                     participation_source = ?, participation_maj = ?
                   WHERE uid_an = ?""",
                [(t, v, e,
                  "calcul France Transparence — scrutins publics AN des "
                  f"{FENETRE_JOURS} derniers jours (votes exprimés / scrutins "
                  "depuis l'entrée en mandat)", maintenant, uid)
                 for uid, (v, e, t) in taux.items()],
            )
        log.info("participation 12 mois : %d députés, %d scrutins en fenêtre",
                 len(taux), len(fenetre))
    else:
        log.warning("deputes vide : agrégats de participation non calculés")

    db.upsert_meta(
        conn, source_id="S5-SCRUTINS",
        nom="AN — scrutins publics et votes nominaux",
        url=URL_SCRUTINS, licence="Licence Ouverte (AN)",
        frequence="quotidienne", date_donnees=dernier["date_scrutin"],
        lignes=len(metas),
        notes=(f"dernier scrutin n° {dernier['numero']} du "
               f"{dernier['date_scrutin']} ; détail nominal conservé pour les "
               f"scrutins n° ≥ {seuil_detail} ({NB_SCRUTINS_DETAIL} derniers) ; "
               f"agrégats de participation sur {len(fenetre)} scrutins "
               f"depuis le {date_min_fenetre}"),
    )
    log.info("scrutins : %d en méta, dernier n° %d du %s",
             len(metas), dernier["numero"], dernier["date_scrutin"])


def ingerer_senat(conn, session: requests.Session) -> None:
    """Sénat ODSEN → senateurs (en exercice) + elus."""
    date_donnees = _date_last_modified(session, URL_ODSEN_GENERAL)
    chemin_general = telecharger(URL_ODSEN_GENERAL, "parlement/ODSEN_GENERAL.csv",
                                 max_age_heures=MAX_AGE_H, session=session)
    chemin_elusen = telecharger(URL_ODSEN_ELUSEN, "parlement/ODSEN_ELUSEN.csv",
                                max_age_heures=MAX_AGE_H, session=session)
    lignes = lire_csv_senat(chemin_general.read_bytes())
    actifs = [r for r in lignes if r.get("État") == "ACTIF"]
    if not actifs:
        raise RuntimeError("ODSEN_GENERAL : aucun sénateur ACTIF")
    log.info("ODSEN : %d sénateurs en exercice (%d lignes au total)",
             len(actifs), len(lignes))

    # Dates de mandat en cours (ODSEN_ELUSEN, partiel — constaté 19/08/2026).
    mandats_en_cours: dict[str, tuple[str | None, str | None]] = {}
    for r in lire_csv_senat(chemin_elusen.read_bytes()):
        if r.get("Date de fin de mandat"):
            continue
        mandats_en_cours[r.get("Matricule")] = (
            nettoyer_date_senat(r.get("Date de début de mandat")), None)

    with conn:
        for r in actifs:
            matricule = r["Matricule"]
            nom, prenom = r.get("Nom usuel"), r.get("Prénom usuel")
            debut, fin = mandats_en_cours.get(matricule, (None, None))
            conn.execute(
                """INSERT OR REPLACE INTO senateurs
                     (matricule, nom, prenom, sexe, circonscription, groupe,
                      groupe_appartenance, commission, date_debut_mandat,
                      date_fin_mandat, date_naissance, profession, email,
                      url_fiche_senat)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (matricule, nom, prenom,
                 {"M.": "M", "Mme": "F"}.get(r.get("Qualité")),
                 r.get("Circonscription"), r.get("Groupe politique"),
                 r.get("Type d'app au grp politique") or None,
                 r.get("Commission permanente") or None,
                 debut, fin,
                 nettoyer_date_senat(r.get("Date naissance")),
                 r.get("Description de la profession") or None,
                 r.get("Courrier électronique") or None,
                 construire_url_senateur(nom or "", prenom or "", matricule)),
            )
            upsert_elu(
                conn,
                cle="matricule_senat", valeur_cle=matricule,
                id_defaut=f"SEN-{matricule}",
                nom=nom, prenom=prenom,
                sexe={"M.": "M", "Mme": "F"}.get(r.get("Qualité")),
                date_naissance=nettoyer_date_senat(r.get("Date naissance")),
                profession=r.get("Description de la profession") or None,
                mandat={
                    "type": "senateur",
                    "date_debut": debut, "date_fin": fin,
                    "departement": r.get("Circonscription"),
                    "groupe": r.get("Groupe politique"),
                },
                source_mandat="SENAT-P9",
            )
        # Sortis de l'état ACTIF (démission, décès, renouvellement) → retirés.
        matricules = [r["Matricule"] for r in actifs]
        marqueurs = ",".join("?" * len(matricules))
        conn.execute(
            f"DELETE FROM senateurs WHERE matricule NOT IN ({marqueurs})",
            matricules,
        )
    db.upsert_meta(
        conn, source_id="S6-ODSEN",
        nom="Sénat — sénateurs en exercice (ODSEN_GENERAL + ODSEN_ELUSEN)",
        url=URL_ODSEN_GENERAL, licence="Licence Ouverte",
        frequence="quotidienne", date_donnees=date_donnees,
        lignes=len(actifs),
        notes=("ISO-8859-1, lignes % sautées ; renouvellement par moitié le "
               "27/09/2026 (aucune date de fin de mandat future publiée dans "
               "ODSEN au 19/08/2026 → date_fin_mandat NULL, recharger après "
               "le scrutin) ; dates de début via ODSEN_ELUSEN, partiel"),
    )
    log.info("Sénat : %d sénateurs écrits", len(actifs))


def ingerer_dosleg(conn, session: requests.Session) -> None:
    """Dosleg `scr` + `votsen` → scrutins_senat + votes_senat (~100
    derniers) + participation_senat (365 jours, même formule que l'AN).

    Pas Ameli, pas questions, pas TAP export_sens, pas de score de
    loyauté. Tables nouvelles — on ne touche pas à scrutins/votes_recents.
    """
    chemin = telecharger(
        URL_DOSLEG, "parlement/dosleg.zip",
        max_age_heures=MAX_AGE_H, session=session,
    )
    z = zipfile.ZipFile(chemin)
    noms = z.namelist()
    if "dosleg.sql" not in noms:
        raise RuntimeError(f"Dosleg : zip sans dosleg.sql ({noms!r})")

    date_min_fenetre = (date.today() - timedelta(days=FENETRE_JOURS)).isoformat()
    scrutins: list[dict] = []
    cles_detail: set[tuple[int, int]] = set()
    fenetre_exprimes: dict[tuple[int, int], set[str]] = {}
    dates_par_cle: dict[tuple[int, int], str] = {}
    lignes_votes: list[tuple] = []
    votes_prets = False

    def _cloturer_scr() -> None:
        nonlocal votes_prets, cles_detail, fenetre_exprimes, dates_par_cle
        if votes_prets:
            return
        if not scrutins:
            raise RuntimeError("Dosleg : aucun scrutin dans COPY scr")
        scrutins.sort(key=lambda s: (s["date_scrutin"], s["sesann"], s["numero"]))
        n_detail = min(NB_SCRUTINS_DETAIL, len(scrutins))
        cles_detail = {
            (s["sesann"], s["numero"]) for s in scrutins[-n_detail:]
        }
        dates_par_cle = {
            (s["sesann"], s["numero"]): s["date_scrutin"] for s in scrutins
        }
        fenetre_exprimes = {
            cle: set()
            for cle, d in dates_par_cle.items()
            if d >= date_min_fenetre
        }
        votes_prets = True

    # Un seul passage : COPY scr précède COPY votsen dans le dump.
    with z.open("dosleg.sql") as fp:
        for table, row in iterer_copy_postgres(fp, {"scr", "votsen"}):
            if table == "scr":
                sesann = _entier_copy(row.get("sesann"))
                numero = _entier_copy(row.get("scrnum"))
                date_scrutin = _date_copy(row.get("scrdat"))
                if sesann is None or numero is None or not date_scrutin:
                    continue
                pour = _entier_copy(row.get("scrpou"))
                contre = _entier_copy(row.get("scrcon"))
                votants = _entier_copy(row.get("scrvot"))
                exprimes = _entier_copy(row.get("scrsuf"))
                abstentions = None
                if votants is not None and exprimes is not None:
                    abstentions = votants - exprimes
                adopte, sort = _sort_scrutin_senat(pour, contre)
                scrutins.append({
                    "sesann": sesann,
                    "numero": numero,
                    "date_scrutin": date_scrutin,
                    "titre": _titre_dosleg(row.get("scrint")),
                    "nombre_votants": votants,
                    "suffrages_exprimes": exprimes,
                    "pour": pour,
                    "contre": contre,
                    "abstentions": abstentions,
                    "adopte": adopte,
                    "sort": sort,
                })
            elif table == "votsen":
                _cloturer_scr()
                sesann = _entier_copy(row.get("sesann"))
                numero = _entier_copy(row.get("scrnum"))
                matricule = _matricule_dosleg(row.get("senmat"))
                if sesann is None or numero is None or not matricule:
                    continue
                cle = (sesann, numero)
                position = POSVOT_SENAT.get((row.get("posvotcod") or "").strip())
                if position is None:
                    continue
                if cle in fenetre_exprimes and position in (
                    "pour", "contre", "abstention"
                ):
                    fenetre_exprimes[cle].add(matricule)
                if cle in cles_detail:
                    delg = _matricule_dosleg(row.get("senmatdel"))
                    lignes_votes.append(
                        (sesann, numero, matricule, position, 1 if delg else 0)
                    )

    _cloturer_scr()
    dernier = scrutins[-1]
    n_detail = min(NB_SCRUTINS_DETAIL, len(scrutins))

    with conn:
        n_arch = archiver_votes_senat_hors_cles(
            conn, cles_detail, date.today().isoformat()
        )
        if n_arch:
            log.info(
                "votes_senat : %d lignes sorties de fenêtre archivées", n_arch
            )
        conn.execute("DELETE FROM votes_senat")
        conn.execute("DELETE FROM scrutins_senat")
        conn.execute("DELETE FROM participation_senat")
        conn.executemany(
            """INSERT INTO scrutins_senat
                 (sesann, numero, date_scrutin, titre, nombre_votants,
                  suffrages_exprimes, pour, contre, abstentions, adopte, sort)
               VALUES (:sesann, :numero, :date_scrutin, :titre,
                       :nombre_votants, :suffrages_exprimes, :pour, :contre,
                       :abstentions, :adopte, :sort)""",
            scrutins,
        )
        conn.executemany(
            """INSERT INTO votes_senat
                 (sesann, numero, matricule, position, par_delegation)
               VALUES (?, ?, ?, ?, ?)""",
            lignes_votes,
        )

    senateurs = conn.execute(
        "SELECT matricule, date_debut_mandat FROM senateurs"
    ).fetchall()
    if senateurs:
        debuts = {s["matricule"]: s["date_debut_mandat"] for s in senateurs}
        fenetre = [
            (dates_par_cle[cle], participants)
            for cle, participants in fenetre_exprimes.items()
        ]
        taux = calculer_participation(fenetre, debuts)
        maintenant = datetime.now(timezone.utc).isoformat(timespec="seconds")
        source = (
            "calcul France Transparence — scrutins publics du Sénat des "
            f"{FENETRE_JOURS} derniers jours (votes exprimés / scrutins "
            "depuis l'entrée en mandat ; une délégation n'est pas une "
            "présence physique)"
        )
        with conn:
            conn.executemany(
                """INSERT INTO participation_senat
                     (matricule, taux_participation_12m, nb_votes_12m,
                      nb_scrutins_12m, participation_source, participation_maj)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                [(uid, t, v, e, source, maintenant)
                 for uid, (v, e, t) in taux.items()],
            )
        log.info("participation Sénat 12 mois : %d sénateurs, %d scrutins en fenêtre",
                 len(taux), len(fenetre_exprimes))
    else:
        log.warning("senateurs vide : agrégats de participation Sénat non calculés")

    db.upsert_meta(
        conn, source_id="S6-DOSLEG",
        nom="Sénat — scrutins publics et votes nominaux (Dosleg scr + votsen)",
        url=URL_DOSLEG, licence="Licence Ouverte",
        frequence="quotidienne", date_donnees=dernier["date_scrutin"],
        lignes=len(scrutins),
        notes=(
            f"dernier scrutin session {dernier['sesann']} n° {dernier['numero']} "
            f"du {dernier['date_scrutin']} ; {len(lignes_votes)} votes nominaux "
            f"conservés pour les {n_detail} derniers scrutins ; agrégats de "
            f"participation sur {len(fenetre_exprimes)} scrutins depuis le "
            f"{date_min_fenetre} ; COPY sans PostgreSQL ; pas Ameli, pas "
            "questions, pas TAP export_sens"
        ),
    )
    log.info("Dosleg : %d scrutins, dernier session %s n° %s du %s",
             len(scrutins), dernier["sesann"], dernier["numero"],
             dernier["date_scrutin"])


def ingerer_datan(conn, session: requests.Session) -> None:
    """Datan deputes-active.csv → colonnes datan_* de deputes (scores crédités)."""
    r = session.get(URL_API_DATASET_DATAN, timeout=60)
    r.raise_for_status()
    ressources = r.json().get("resources", [])
    url_csv = next((res["url"] for res in ressources
                    if (res.get("url") or "").endswith("deputes-active.csv")
                    or res.get("title") == "deputes-active.csv"), None)
    if not url_csv:
        raise RuntimeError("Datan : ressource deputes-active.csv introuvable "
                           "dans le dataset data.gouv")
    chemin = telecharger(url_csv, "parlement/datan_deputes-active.csv",
                         max_age_heures=MAX_AGE_H, session=session)
    lignes = list(csv.DictReader(io.StringIO(chemin.read_text("utf-8"))))
    if not lignes:
        raise RuntimeError("Datan : CSV vide")

    def _f(v):
        try:
            return float(v) if v not in (None, "") else None
        except ValueError:
            return None

    source = ("Datan — dataset data.gouv.fr « Députés actifs de l'Assemblée "
              "nationale », licence fr-lo, méthodologie datan.fr (scores "
              "calculés par Datan, non par France Transparence)")
    date_maj = max((l.get("dateMaj") or "" for l in lignes), default="") or None
    if date_maj is None:
        raise RuntimeError("Datan : colonne dateMaj absente ou vide")
    apparies = 0
    with conn:
        for l in lignes:
            cur = conn.execute(
                """UPDATE deputes SET datan_score_participation = ?,
                     datan_score_participation_specialite = ?,
                     datan_score_loyaute = ?, datan_score_majorite = ?,
                     datan_source = ?, datan_date = ?
                   WHERE uid_an = ?""",
                (_f(l.get("scoreParticipation")),
                 _f(l.get("scoreParticipationSpecialite")),
                 _f(l.get("scoreLoyaute")), _f(l.get("scoreMajorite")),
                 source, l.get("dateMaj"), l.get("id")),
            )
            apparies += cur.rowcount
    if apparies == 0:
        raise RuntimeError("Datan : aucun id PA… apparié avec deputes "
                           "(AMO10 manquant ?)")
    db.upsert_meta(
        conn, source_id="S7-DATAN",
        nom="Datan — scores participation/loyauté/majorité des députés",
        url="https://www.data.gouv.fr/datasets/deputes-actifs-de-lassemblee-"
            "nationale-informations-et-statistiques",
        licence="Licence Ouverte (fr-lo)", frequence="quotidienne",
        date_donnees=date_maj, lignes=len(lignes),
        notes=(f"{apparies}/{len(lignes)} députés appariés par id PA… ; "
               "scores Datan à créditer à l'affichage ; le taux calculé "
               "France Transparence coexiste (colonnes taux_participation_12m)"),
    )
    log.info("Datan : %d/%d scores appariés (dateMaj %s)",
             apparies, len(lignes), date_maj)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def main() -> int:
    debut = datetime.now()
    conn = db.init_db()
    conn.executescript(_SCHEMA_P9)
    conn.commit()
    session = session_http()

    etapes = [
        ("AN AMO10 (députés/groupes)", ingerer_amo10),
        ("AN Scrutins (méta+votes+participation)", ingerer_scrutins),
        ("Sénat ODSEN (sénateurs)", ingerer_senat),
        ("Sénat Dosleg (scrutins+votes)", ingerer_dosleg),
        ("Datan (scores députés)", ingerer_datan),
    ]
    echecs: list[tuple[str, str]] = []
    for nom_etape, fonction in etapes:
        try:
            fonction(conn, session)
        except Exception as e:  # une source en panne n'arrête pas les autres
            log.error("ÉCHEC %s : %s", nom_etape, e)
            echecs.append((nom_etape, str(e)))

    duree = (datetime.now() - debut).total_seconds()
    if echecs:
        log.error("bilan P9 : %d/%d sources en échec (%.0f s) : %s",
                  len(echecs), len(etapes), duree,
                  " | ".join(f"{n} → {m}" for n, m in echecs))
        conn.close()
        return 1
    log.info("bilan P9 : %d/%d sources ingérées sans échec (%.0f s)",
             len(etapes), len(etapes), duree)
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

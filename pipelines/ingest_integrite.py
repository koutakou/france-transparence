"""P7 — Intégrité des élus : HATVP `liste.csv` (S14) × Répertoire national des élus (S17).

Modules UI alimentés : « Élus & Institutions » et « Alertes ».

Tables produites (remplacement complet, idempotent) :
- hatvp_declarations : 1 ligne = 1 dossier déclaratif HATVP, doublons stricts
  écartés (12 930 lignes publiées au 14/08/2026, 50 doublons → 12 880).
  Colonnes : civilite, prenom, nom, classement (clé personne HATVP), type_mandat,
  qualite (mandat/fonction concerné), type_document (di/dia/dsp/dim/diam/dspm/dspfm),
  departement, date_publication, date_depot, statut_publication (natif),
  nom_fichier, url_dossier, url_fiche (lien absolu hatvp.fr), open_data,
  id_origine, url_photo.
- hatvp_agregats : (categorie, cle, nb) — categorie ∈ {'statut_publication',
  'type_document', 'depots_par_mois'} ; les dépôts par mois couvrent les
  24 derniers mois (mois sans dépôt = 0).
- rne_cm_agregats : conseillers municipaux (~511 000, PAS ingérés nominativement)
  agrégés par département : code_departement, libelle_departement, nb_conseillers,
  nb_femmes, nb_hommes, age_moyen.
- alertes : table PARTAGÉE entre pipelines (CREATE TABLE IF NOT EXISTS ; ce
  pipeline n'efface QUE ses propres types : A1_hatvp_non_deposee,
  A1_hatvp_en_cours_delai_ecoule, et l'ancien A1_hatvp_retard_presume pour le
  purger). Colonnes : id, type, gravite, titre, detail, regle, base_legale,
  source_url, date_calcul, date_fait (date du fichier HATVP lu).

Table noyau complétée, et — depuis le rattrapage — élaguée :
- elus : UPSERT prudent par (nom, prénom, date de naissance) normalisés —
  députés (577), sénateurs (348), maires (~34 800), présidents d'exécutifs
  (conseils départementaux, conseils régionaux, EPCI). Les colonnes remplies par
  d'autres pipelines (uid_an, matricule_senat) ne sont jamais touchées ; les
  mandats sont fusionnés dans le JSON `mandats` (seules les entrées
  "source": "RNE" sont remplacées). Croisement HATVP : hatvp_flag et
  hatvp_url (colonne ajoutée par ce pipeline si absente ; seul ce pipeline
  écrit les deux) sont recalculés à chaque cycle — flag à 1 et lien de la
  fiche uniquement quand le couple nom+prénom est unique des deux côtés ET
  qu'un dossier concorde avec un mandat de la fiche (chambre, département ou
  nature : `dossier_corrobore_fiche`). Homonymie non tranchée ou concordance
  absente = pas de flag.

Contrôle d'après-cycle, non bloquant :
- collisions de clé d'état civil (`controler_collisions_de_cle`) — nombre de
  clés (nom, prénom, date de naissance) normalisées portées par plus d'une ligne
  de `elus`. Une collision fait gagner le `setdefault` de l'UPSERT à la ligne
  que le balayage rencontre en premier ; si ce n'est pas une fiche `rne-*`, le
  doublon `rne-*` cesse d'être purgeable et le site sert deux fiches pour une
  seule personne, sans qu'aucun compteur de CE pipeline ne bouge (P15, lancé
  après, en voit une partie — voir la docstring de la fonction). Le compte part
  au journal à chaque cycle, zéro compris.

Alerte A1 — règle révisée de docs/SOURCES.md §4 (appliquée à la lettre) :
- Nominatif RÉSERVÉ aux statuts natifs « Déclaration non déposée » (constat
  officiel HATVP, 4 cas au 14/08/2026) → 1 alerte nominative par dossier.
- Compte des dossiers « En cours » au délai légal écoulé (décision du
  propriétaire du 20/11/2026 : le mot « retard » est retiré, le site ne
  connaît pas la définition officielle de « En cours ») : statut « En cours »
  ET date de début de la fonction (RNE) + 2 MOIS CALENDAIRES dépassée (le
  délai légal, et non 60 jours : `common.ajouter_mois`). Garde-fous :
  (1) mandats EPCI exclus (délai courant à la transmission de la délégation en
  préfecture, date absente de l'open data) ; (2) jointure nom+prénom+département
  normalisés (accents/casse/tirets), homonyme non tranché = non-alerte ;
  (3) restitution en AGRÉGATS par type de mandat, jamais nominative, et
  jamais sous SEUIL_PERSONNES_AGREGAT personnes (les types sous le seuil sont
  regroupés, le regroupement lui-même soumis au seuil) ;
  (4) seuls les documents initiaux (di, dsp, dia) sont testés — le délai légal
  des modificatives et des fins de mandat court sur d'autres faits générateurs ;
  (5) périmètre apparié = populations RNE ingérées (députés, sénateurs, maires,
  présidents de conseils départementaux/régionaux) avec filtre sur la qualité
  déclarée ; le reste (adjoints, vice-présidents, ctsp, gouvernement…) = non
  apparié = non-alerte ; (6) réserve affichée : RNE trimestriel (11/08/2026),
  dates de fonction possiblement périmées jusqu'à ~3 mois ; (7) pas d'alerte
  pour une chambre dont le dernier renouvellement (lu dans la table de P9)
  est postérieur à la date de début la plus récente du fichier RNE : un réélu
  y porte encore la date de son mandat PRÉCÉDENT (constat du 15/10/2026 :
  216 dossiers comptés à tort pour des sénateurs réélus le
  27/09/2026, dont l'échéance légale court jusqu'en décembre).

meta_sources : S14 (HATVP liste.csv, date_donnees = Last-Modified réel) et
S17 (RNE, date_donnees = last_modified des ressources via l'API data.gouv —
les URLs static.data.gouv.fr horodatées sont re-résolues à chaque run).

Exécution : `python -m pipelines.ingest_integrite` (FT_DB_PATH pour rediriger
la base). Échec net (exit ≠ 0) si une source est indisponible ou difforme.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import sqlite3
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import date
from email.utils import parsedate_to_datetime
from pathlib import Path

from pipelines import db
from pipelines.common import (
    RACINE, RAW_DIR, ajouter_mois, obtenir_logger, session_http, telecharger,
)
from pipelines.ingest_hatvp_declarations import (CHEMIN_REDIRECTIONS_ELUS,
                                                 charger_fiches_passees_au_senat,
                                                 charger_liste_blanche,
                                                 composantes_identite,
                                                 date_complete,
                                                 departager_fiches_passees_au_senat,
                                                 ecritures_incluses)
from pipelines.ingest_hatvp_declarations import date_donnees_sans_last_modified

log = obtenir_logger("ingest_integrite")

# ---------------------------------------------------------------------------
# Constantes source
# ---------------------------------------------------------------------------

URL_HATVP_LISTE = "https://www.hatvp.fr/livraison/opendata/liste.csv"
URL_HATVP_SITE = "https://www.hatvp.fr"
URL_RNE_API = "https://www.data.gouv.fr/api/1/datasets/repertoire-national-des-elus-1/"
URL_RNE_PAGE = "https://www.data.gouv.fr/datasets/repertoire-national-des-elus-1/"

REP_RAW = RAW_DIR / "integrite"

COLONNES_HATVP = [
    "civilite", "prenom", "nom", "classement", "type_mandat", "qualite",
    "type_document", "departement", "date_publication", "date_depot",
    "nom_fichier", "url_dossier", "open_data", "statut_publication",
    "id_origine", "url_photo",
]

# Ressources RNE ingérées : motif (sur le titre normalisé) → clé interne.
RESSOURCES_RNE = {
    "deputes": "deputes",
    "senateurs": "senateurs",
    "maires": "maires",
    "departementaux": "cd",
    "regionaux": "cr",
    "communautaires": "epci",
    "municipaux": "cm",
}

STATUT_EN_COURS = "En cours"
STATUT_NON_DEPOSEE = "Déclaration non déposée"

# Documents « initiaux » dont le délai court sur l'entrée en fonction
# (di = intérêts, dsp = patrimoine, dia = intérêts et activités).
DOCS_INITIAUX = {"di", "dsp", "dia"}

LIBELLES_DOC = {
    "di": "déclaration d'intérêts",
    "dia": "déclaration d'intérêts et d'activités",
    "dsp": "déclaration de situation patrimoniale",
    "dim": "déclaration d'intérêts modificative",
    "diam": "déclaration d'intérêts et d'activités modificative",
    "dspm": "déclaration de situation patrimoniale modificative",
    "dspfm": "déclaration de situation patrimoniale de fin de mandat",
}

TYPE_ALERTE_NON_DEPOSEE = "A1_hatvp_non_deposee"
TYPE_ALERTE_EN_COURS = "A1_hatvp_en_cours_delai_ecoule"
# Ancien type, qui portait le mot « retard » : plus jamais écrit, mais effacé à
# chaque cycle pour que ses lignes ne survivent pas dans la table partagée.
TYPE_ALERTE_RETARD_ANCIEN = "A1_hatvp_retard_presume"
TYPES_ALERTES_P7 = (TYPE_ALERTE_NON_DEPOSEE, TYPE_ALERTE_EN_COURS)
TYPES_ALERTES_EFFACES_P7 = TYPES_ALERTES_P7 + (TYPE_ALERTE_RETARD_ANCIEN,)

# Délai légal de dépôt des déclarations initiales : « dans les deux mois qui
# suivent l'entrée en fonction ». Compté en mois calendaires, jamais en jours.
DELAI_LEGAL_A1_MOIS = 2

# Aucun agrégat publié sous ce nombre de personnes : sur 577 députés, une
# cellule « 1 personne » se lit nominativement dans liste.csv (constat de
# l'audit du 20/11/2026, décision du propriétaire).
SEUIL_PERSONNES_AGREGAT = 3

BASE_LEGALE_A1 = (
    "Loi n° 2013-907 du 11 octobre 2013 (art. 4 et 11). Art. LO 135-1 du code "
    "électoral : dépôt dans les 2 mois suivant l'entrée en fonction. Sanctions "
    "(art. 26) : 3 ans d'emprisonnement, 45 000 € d'amende, inéligibilité."
)

REGLE_A1_EN_COURS = (
    "Compte des dossiers au statut natif « En cours » dans liste.csv de la "
    "HATVP dont l'entrée en fonction (RNE du {date_rne}) remonte à plus de 2 "
    "mois, délai légal de dépôt compté en mois calendaires et non en jours. "
    "Le site ne connaît pas la définition officielle de ce statut et n'en "
    "déduit aucun manquement. Garde-fous appliqués : mandats EPCI exclus "
    "(délai courant à la transmission de la délégation en préfecture, date "
    "absente de l'open data), jointure nom, prénom et département normalisés, "
    "homonyme non tranché écarté, documents initiaux seulement (di, dsp, dia), "
    "qualité déclarée filtrée sur la population RNE appariée (maires, "
    "présidents d'exécutifs, parlementaires), aucun compte pour une chambre "
    "dont le dernier renouvellement est postérieur au RNE ingéré. Agrégat non "
    "nominatif, jamais publié sous 3 personnes : les mandats sous ce seuil "
    "sont regroupés, et le regroupement n'est publié qu'à partir de 3 "
    "personnes. Réserve : RNE trimestriel, dates de fonction possiblement "
    "périmées jusqu'à environ 3 mois."
)

# Garde-fou n° 7 de la règle A1 : le RNE trimestriel ignore-t-il le dernier
# renouvellement d'une chambre ? La date d'entrée COLLECTIVE est lue dans la
# table de la chambre en exercice écrite par P9 (lancé avant P7) : la plus
# récente date de début de mandat partagée par au moins cette part des élus
# en exercice. Le Sénat se renouvelle par moitié, l'AN en entier : un quart
# sépare un renouvellement d'une élection partielle ou d'un remplacement.
TABLES_CHAMBRES = {"depute": "deputes", "senateur": "senateurs"}
CLES_RNE_CHAMBRES = {"depute": "deputes", "senateur": "senateurs"}
PART_ENTREE_COLLECTIVE = 0.25

REGLE_A1_NON_DEPOSEE = (
    "Constat officiel HATVP repris tel quel : statut natif « Déclaration non "
    "déposée » dans liste.csv. Seuls cas nominatifs de cette alerte (les dossiers "
    "« En cours » ne sont publiés qu'en agrégats)."
)

SCHEMA_P7 = """
CREATE TABLE IF NOT EXISTS alertes (
    id          TEXT PRIMARY KEY,
    type        TEXT NOT NULL,
    gravite     TEXT NOT NULL,
    titre       TEXT NOT NULL,
    detail      TEXT,
    regle       TEXT,
    base_legale TEXT,
    source_url  TEXT,
    date_calcul TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_alertes_type ON alertes(type);

DROP TABLE IF EXISTS hatvp_declarations;
CREATE TABLE hatvp_declarations (
    id                 INTEGER PRIMARY KEY,
    civilite           TEXT,
    prenom             TEXT,
    nom                TEXT,
    classement         TEXT,
    type_mandat        TEXT,
    qualite            TEXT,
    type_document      TEXT,
    departement        TEXT,
    date_publication   TEXT,
    date_depot         TEXT,
    statut_publication TEXT NOT NULL,
    nom_fichier        TEXT,
    url_dossier        TEXT,
    url_fiche          TEXT,
    open_data          TEXT,
    id_origine         TEXT,
    url_photo          TEXT
);
CREATE INDEX IF NOT EXISTS idx_hatvp_decl_statut ON hatvp_declarations(statut_publication);
CREATE INDEX IF NOT EXISTS idx_hatvp_decl_nom    ON hatvp_declarations(nom, prenom);

DROP TABLE IF EXISTS hatvp_agregats;
CREATE TABLE hatvp_agregats (
    categorie TEXT NOT NULL,
    cle       TEXT NOT NULL,
    nb        INTEGER NOT NULL,
    PRIMARY KEY (categorie, cle)
);

DROP TABLE IF EXISTS rne_cm_agregats;
CREATE TABLE rne_cm_agregats (
    code_departement    TEXT PRIMARY KEY,
    libelle_departement TEXT,
    nb_conseillers      INTEGER NOT NULL,
    nb_femmes           INTEGER NOT NULL,
    nb_hommes           INTEGER NOT NULL,
    age_moyen           REAL
);
"""


def instructions_schema(script: str = SCHEMA_P7) -> list[str]:
    """Découpe un script SQL en instructions, pour les passer UNE À UNE.

    POURQUOI ne plus confier ce travail à `executescript`, qui le faisait :
    il VALIDE implicitement la transaction en cours avant de lancer son
    script. Comme `SCHEMA_P7` porte trois `DROP TABLE`, la destruction de
    `hatvp_declarations`, `hatvp_agregats` et `rne_cm_agregats` partait sur
    disque d'emblée, et le `rollback()` du bloc `except` de `main()` — qui
    n'annule que les insertions — ne pouvait pas la reprendre. Passées une à
    une à `conn.execute`, les mêmes instructions restent dans la transaction
    ouverte par `appliquer_schema()` : SQLite fait du DDL transactionnel,
    `DROP TABLE` compris, index et lignes revenant ensemble (mesuré).

    POURQUOI `sqlite3.complete_statement` ALORS QUE `split(";")` SUFFIRAIT
    AUJOURD'HUI — la mesure, faite sur ce littéral-ci et non recopiée de P15 :
    `SCHEMA_P7` porte 10 points-virgules, **zéro** ligne de commentaire `--`
    et **zéro** apostrophe. Les deux pièges qui condamnent le découpage naïf
    dans `ingest_hatvp_declarations.py` (des `;` en commentaire, des
    apostrophes impaires) **n'existent pas ici** : il ne faut pas prétendre
    l'inverse. `complete_statement` est retenu quand même pour deux raisons
    mesurables : il est l'outil de la bibliothèque standard pour cela — celui
    du shell `sqlite3` — et il ignore les commentaires, si bien que le jour
    où quelqu'un annotera ce schéma comme l'autre est annoté, le découpage
    ne se cassera pas. Or il se casserait AU PIRE ENDROIT : après les trois
    `DROP`. 10 instructions, mesuré (3 `DROP TABLE`, 4 `CREATE TABLE`,
    3 `CREATE INDEX`).

    Lève `ValueError` sur un script qui se termine hors instruction : mieux
    vaut un échec bruyant AVANT le `BEGIN` qu'un schéma appliqué à moitié.
    """
    instructions: list[str] = []
    tampon = ""
    for ligne in script.splitlines(keepends=True):
        tampon += ligne
        if sqlite3.complete_statement(tampon):
            instructions.append(tampon.strip())
            tampon = ""
    reste = [l for l in tampon.splitlines()
             if l.strip() and not l.strip().startswith("--")]
    if reste:
        raise ValueError(
            "script SQL mal formé : la dernière instruction n'est pas terminée "
            f"par « ; » — {reste[0].strip()[:60]!r}")
    return instructions


def appliquer_schema(conn, script: str = SCHEMA_P7) -> None:
    """Applique `SCHEMA_P7` DANS une transaction, au lieu de la valider.

    C'EST LA LIGNE QUI REND LE CYCLE ATOMIQUE. Ce qu'il ne faut jamais
    remettre à sa place, c'est `conn.executescript(SCHEMA_P7)`.

    Ce qui était exposé, re-mesuré le 26/08/2026 sur la base SERVIE
    (`data/france.db`, Python 3.14.6 et SQLite 3.37.2, ceux de la production) :
    **13 277** lignes de `hatvp_declarations`, **37** de `hatvp_agregats`,
    **104** de `rne_cm_agregats`. Entre l'ancien `executescript` et le
    `conn.commit()` de `main()` tiennent **65 lignes**, dont
    `agreger_conseillers_municipaux`, qui lit et parse le CSV des conseillers
    municipaux du RNE (65 Mo, 2,13 s, 511 225 conseillers mesurés) et peut
    lever. Reproduit à l'identique : avec
    `executescript`, une panne à cet endroit puis `rollback()` laisse une
    connexion neuve relire **0 / 0 / 0** ; avec ce correctif, elle relit les
    trois comptes d'avant l'incident.

    ⚠️ LA TRANSACTION NE VA PAS JUSQU'AU `conn.commit()` DE `main()`, et il
    faut le savoir : `db.upsert_meta` valide lui-même (`pipelines/db.py`,
    `conn.commit()` en fin de fonction) et `main()` l'appelle DEUX fois, pour
    S14 puis S17, avant son propre `commit`. La transaction ouverte ici se
    referme donc au premier `upsert_meta`. Ce n'est pas un défaut résiduel :
    tout ce qui peut détruire des données — les trois `DROP`, les trois
    remplissages, `upsert_elus`, le parsing du CSV RNE, les alertes — est en
    amont de ce point. Ce qui reste après lui est l'écriture de deux lignes
    de `meta_sources`, dont l'échec laisse la base complète et à jour, avec
    une date de source non rafraîchie. Ne pas « corriger » `upsert_meta` au
    passage : il est partagé par les 31 pipelines.

    ⚠️ `BEGIN IMMEDIATE` ET NON `BEGIN` — la réserve laissée ouverte par P15
    (« un SQLITE_BUSY tardif n'a pas été mesuré ») a été mesurée ici, et elle
    mord. Un `BEGIN` nu est *deferred*, et les deux premières instructions de
    `SCHEMA_P7` sont `CREATE TABLE IF NOT EXISTS alertes` et son
    `CREATE INDEX IF NOT EXISTS` : dans le cas nominal, où la table existe,
    ce sont des NO-OP. Mesuré, avec un écrivain concurrent sur la base :
    `BEGIN` nu → le premier `DROP` échoue « database is locked » en **0,00 s**,
    le busy handler n'étant PAS appelé, donc sans rien devoir au `timeout=30`
    de `db.connexion()` ; `BEGIN IMMEDIATE` → le verrou est pris d'emblée et
    le `DROP` passe. Vérifié dans les DEUX modes de journalisation, `wal` et
    `delete`. En `wal` le mécanisme est visible à l'œil nu : après les deux
    NO-OP la transaction ne tient aucun verrou d'écriture, l'écrivain
    concurrent valide, et la montée lecture→écriture n'est plus possible.
    ⚠️ ET C'EST EN `wal` QUE CE PIPELINE TOURNE : `db.connexion()` bascule la
    base à chaque ouverture (mesuré, y compris sur une base au repos en
    `delete`). Le `delete` qu'on lit sur `data/france.db` entre deux cycles est
    posé APRÈS l'ingestion, délibérément, par `ft-deploy` (« Consolidation de
    la base », `wal_checkpoint(TRUNCATE)` puis `journal_mode=DELETE`) pour que
    l'export parte en fichier unique. Ne pas conclure du mode au repos que le
    cas `wal` serait théorique : c'est l'inverse.

    ⚠️ À NE PAS SUR-VENDRE : sur le chemin réel, aucun écrivain concurrent
    n'existe — `make ingest` enchaîne les 31 pipelines en série et rien
    d'autre n'écrit `france.db`. `IMMEDIATE` est donc ici une prophylaxie
    gratuite, pas la correction d'une panne observée en production. Elle
    compte parce que l'ancien `executescript` n'avait pas cette fenêtre : sans
    elle, le correctif d'atomicité aurait AJOUTÉ un mode d'échec.
    ⚠️ La réserve NE se transpose PAS telle quelle à `SCHEMA_P15`, dont la
    première instruction est un `DROP TABLE` : là, le `BEGIN` nu écrit tout de
    suite. Ne pas « corriger » P15 sans refaire la mesure.

    ⚠️ Si l'appelant a DÉJÀ une transaction ouverte, on s'y greffe : un second
    `BEGIN` lèverait « cannot start a transaction within a transaction »
    (mesuré). Sur le chemin réel le cas ne se présente pas — `db.init_db()`
    valide, et entre lui et cet appel `main()` ne fait que télécharger et
    parser, sans toucher la base.
    """
    if not conn.in_transaction:
        conn.execute("BEGIN IMMEDIATE")
    for instruction in instructions_schema(script):
        conn.execute(instruction)

# ---------------------------------------------------------------------------
# Normalisation (règle de matching documentée — garde-fou n° 2 de A1)
# ---------------------------------------------------------------------------


def normaliser_texte(s: str | None) -> str:
    """Minuscule, sans accents, tirets/apostrophes → espace, espaces réduits."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.replace("-", " ").replace("'", " ").replace("’", " ")
    return " ".join(s.split()).casefold()


def normaliser_departement(s: str | None) -> str:
    """'01'→'1', '099'→'99', '974'→'974', '2a'→'2A', ''→''."""
    s = (s or "").strip().upper()
    return str(int(s)) if s.isdigit() else s


_ARTICLES = ("le ", "la ", "les ", "l ")


def _sans_article(s: str) -> str:
    for a in _ARTICLES:
        if s.startswith(a):
            return s[len(a):]
    return s


_RE_MAIRE = re.compile(r"^maire (?!delegue\b)(?:de |du |des |d )?(.+)$")
_RE_PRESIDENT_CD = re.compile(r"^presidente? du conseil departemental")
_RE_PRESIDENT_CR = re.compile(r"^presidente? du conseil regional")


def _parser_date_iso(s: str | None) -> date | None:
    try:
        return date.fromisoformat((s or "").strip())
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# HATVP — liste.csv
# ---------------------------------------------------------------------------


def parser_liste_hatvp(chemin: str | Path) -> list[dict]:
    """Parse liste.csv (UTF-8 BOM, `;`) et vérifie l'en-tête attendu."""
    with open(chemin, encoding="utf-8-sig", newline="") as f:
        lecteur = csv.DictReader(f, delimiter=";")
        if lecteur.fieldnames != COLONNES_HATVP:
            raise ValueError(
                f"liste.csv : en-tête inattendu {lecteur.fieldnames!r} "
                f"(attendu {COLONNES_HATVP!r})"
            )
        lignes = [{k: (v or "").strip() for k, v in ligne.items()} for ligne in lecteur]
    if not lignes:
        raise ValueError("liste.csv : fichier vide")
    return lignes


def dedoublonner_hatvp(dossiers: list[dict]) -> list[dict]:
    """Écarte les lignes STRICTEMENT identiques de liste.csv.

    POURQUOI un dédoublonnage exact et pas sur une clé métier : liste.csv
    n'a pas d'identifiant de dossier fiable (`id_origine` est vide 64 % du
    temps), et deux déclarations différentes d'une même personne peuvent
    partager n'importe quel sous-ensemble de colonnes — même type de
    document, même qualité, même date de dépôt. La SEULE duplication qu'on
    puisse écarter sans risque de perte est celle où les seize colonnes
    coïncident : la ligne n'apporte alors rien, par construction.
    Mesuré le 20/08/2026 sur le fichier publié : 12 930 lignes, dont 50
    doublons stricts répartis en 49 groupes (un groupe à 3 exemplaires).
    Conséquence : les agrégats par statut et par type de document, servis
    sur /elus, comptaient ces lignes deux fois.

    L'ordre d'origine est conservé (premier exemplaire gagnant) : c'est ce
    qui rend le résultat reproductible d'une ingestion à l'autre.
    """
    vus: set[tuple] = set()
    uniques: list[dict] = []
    for dossier in dossiers:
        empreinte = tuple(sorted(dossier.items()))
        if empreinte in vus:
            continue
        vus.add(empreinte)
        uniques.append(dossier)
    ecartes = len(dossiers) - len(uniques)
    if ecartes:
        log.info("HATVP : %d doublon(s) strict(s) écarté(s) sur %d lignes",
                 ecartes, len(dossiers))
    return uniques


def controler_dates_hatvp(dossiers: list[dict], aujourd_hui: date) -> dict[str, int]:
    """Compte et JOURNALISE les dates impossibles de liste.csv.

    POURQUOI signaler et ne rien corriger : ces dates sont des défauts de la
    source, et aucune correction ne serait autre chose qu'une devinette —
    « 2026-11-27 » peut être une coquille pour 2025-11-27 comme pour
    2026-01-27, on n'en sait rien. Les effacer serait pire : on perdrait la
    trace d'un défaut réel sans rien gagner, puisque ces champs ne sont pas
    affichés nominativement. Le pipeline dit donc ce qu'il voit, à chaque
    run, et le silence du log devient l'information utile (« la source s'est
    corrigée »). Mesuré le 20/08/2026 : 1 dépôt à trois mois dans le futur,
    4 publications antérieures à leur propre dépôt, 4 publications
    postérieures au jour d'ingestion — ces dernières étant probablement des
    publications programmées, donc légitimes : c'est bien un signalement, pas
    un verdict.
    """
    depots_futurs = publications_futures = publications_avant_depot = 0
    for dossier in dossiers:
        depot = _parser_date_iso(dossier.get("date_depot"))
        publication = _parser_date_iso(dossier.get("date_publication"))
        if depot and depot > aujourd_hui:
            depots_futurs += 1
            log.warning("HATVP : dépôt daté du futur — %s %s, %s",
                        dossier.get("prenom"), dossier.get("nom"), depot)
        if publication and publication > aujourd_hui:
            publications_futures += 1
        if depot and publication and publication < depot:
            publications_avant_depot += 1
            log.warning("HATVP : publication (%s) antérieure au dépôt (%s) — %s %s",
                        publication, depot, dossier.get("prenom"), dossier.get("nom"))
    if publications_futures:
        log.info("HATVP : %d publication(s) datée(s) après le jour d'ingestion "
                 "(publications programmées probables)", publications_futures)
    return {
        "depots_futurs": depots_futurs,
        "publications_futures": publications_futures,
        "publications_avant_depot": publications_avant_depot,
    }


def agreger_hatvp(dossiers: list[dict], aujourd_hui: date) -> list[tuple[str, str, int]]:
    """Agrégats : counts par statut, par type de document, dépôts par mois (24 mois)."""
    sortie: list[tuple[str, str, int]] = []
    for cle, nb in sorted(Counter(d["statut_publication"] for d in dossiers).items()):
        sortie.append(("statut_publication", cle, nb))
    for cle, nb in sorted(Counter(d["type_document"] for d in dossiers).items()):
        sortie.append(("type_document", cle, nb))
    # 24 derniers mois pleins, mois courant inclus ; mois sans dépôt = 0.
    mois_fenetre: list[str] = []
    a, m = aujourd_hui.year, aujourd_hui.month
    for _ in range(24):
        mois_fenetre.append(f"{a:04d}-{m:02d}")
        m -= 1
        if m == 0:
            a, m = a - 1, 12
    depots = Counter(d["date_depot"][:7] for d in dossiers if d["date_depot"])
    for cle in sorted(mois_fenetre):
        sortie.append(("depots_par_mois", cle, depots.get(cle, 0)))
    return sortie


# ---------------------------------------------------------------------------
# RNE — lecture et index
# ---------------------------------------------------------------------------


def lire_rne(chemin: str | Path, colonnes_requises: tuple[str, ...]) -> list[dict]:
    """Lit un CSV RNE (`;`, UTF-8, CRLF) et vérifie les colonnes requises."""
    with open(chemin, encoding="utf-8-sig", newline="") as f:
        lecteur = csv.DictReader(f, delimiter=";")
        champs = lecteur.fieldnames or []
        manquantes = [c for c in colonnes_requises if c not in champs]
        if manquantes:
            raise ValueError(f"{chemin} : colonnes manquantes {manquantes} dans {champs}")
        return list(lecteur)


_COLS_BASE = ("Nom de l'élu", "Prénom de l'élu", "Code sexe", "Date de naissance",
              "Libellé de la catégorie socio-professionnelle", "Date de début du mandat")


def _cle_personne(r: dict) -> tuple[str, str, str]:
    return (
        normaliser_texte(r["Nom de l'élu"]),
        normaliser_texte(r["Prénom de l'élu"]),
        (r["Date de naissance"] or "").strip(),
    )


# Garde-fou de VOLUME du rattrapage (ajustement n° 4 de la qualification D22).
# Chaque rattrapage émet un `DELETE FROM elus` : c'est le seul endroit où ce
# pipeline retire une ligne de sa table noyau. Sans plafond, un millésime RNE
# abîmé — un fichier tronqué, une colonne décalée, un export de test — pourrait
# en émettre des centaines dans un cycle qui se termine en SUCCÈS, sans qu'un
# seul seuil morde. `ft-deploy` ne rattraperait pas : ses deux seuls contrôles
# de volumétrie sont `NB_ELUS >= 900` (l. 303) et un plafond de taille d'export
# (l. 305) — mesuré, 1 049 fiches tombant à 1 036 passe sans un mot, et il
# faudrait perdre 97 % des fiches pour que le premier morde.
#
# La forme est celle de P15 : un PLANCHER *et* une PROPORTION, jamais la
# proportion seule. La proportion seule ferait échouer l'intégration continue,
# dont les fixtures ne portent qu'une poignée de fiches (1 rattrapage sur 2
# cibles = 50 %) ; le plancher seul serait aveugle à une base qui aurait fondu.
# Mesure du 26/08/2026 sur la base servie : 17 rattrapages pour 925 fiches
# AN/Sénat, soit 1,8 % — deux ordres de grandeur sous le déclenchement.
PLANCHER_RATTRAPAGES = 50
PROPORTION_RATTRAPAGES = 0.05

# Issue de secours, calquée sur `FT_P15_PERTES_ACQUITTEES` : elle ne desserre
# aucun seuil, elle NOMME les identifiants dont un exploitant assume la
# suppression. Ce qui est acquitté est donc tracé dans la commande, pas effacé
# du code. Elle existe pour la même raison qu'en P15 : une levée arrête les
# 21 pipelines en aval et tout le rafraîchissement du site jusqu'à intervention
# humaine, chaque nuit.
ENV_RATTRAPAGES_ACQUITTES = "FT_P7_RATTRAPAGES_ACQUITTES"


def _composantes(s: str | None) -> frozenset[str]:
    """Composantes d'un nom ou d'un prénom — celles de P15, ramenées au casefold.

    POURQUOI ON N'EN ÉCRIT PAS UNE SECONDE. `composantes_identite` (P15,
    `ingest_hatvp_declarations`) fait déjà exactement ce travail — retrait des
    parenthèses de désambiguïsation de l'Assemblée, forme recollée pour les
    graphies coupées autrement (RNE « KBIDI » / AN « K/Bidi ») — ET elle exclut
    les PARTICULES, ce que la version d'origine de ce correctif ne faisait pas.
    Mesuré : « LE MAIRE » × « LE GAC » s'apparient sur la seule syllabe « le »
    sans ce filtre, et « DE RUGY » × « DE COURSON » sur « de » ; « LE » est porté
    par 18 fiches servies, « DE » par 14. Réintroduire une variante sans filtre
    dans un chemin qui SUPPRIME une fiche, alors que la PR #89 venait de fermer
    cette faille dans un chemin qui se contente de rattacher, était une faille
    armée — pas un défaut de style.

    ⚠️ LA CASSE, ET POURQUOI CE N'EST PAS UN APPEL DIRECT. `composantes_identite`
    rend du MAJUSCULE (convention de la source HATVP, cf. `normaliser_identite`)
    ; tout P7 est en `casefold` (`normaliser_texte`). Les deux jeux ne
    s'intersectent JAMAIS. Le repli reste cohérent avec lui-même dans les deux
    conventions — il ne croise que ses propres sorties — mais une comparaison
    ultérieure contre une clé P7 rendrait un ensemble vide EN SILENCE : aucune
    exception, zéro rattrapage, garde-fou muet. Le casefold est donc posé ici,
    à la frontière, une fois pour toutes.

    Différence résiduelle assumée : P15 normalise en NFD, P7 en NFKD ; les
    caractères de compatibilité (« Ⅷ », « № ») s'évaporent au lieu d'être
    dépliés. Aucun patronyme du RNE n'en porte (mesuré : 0 sur 36 020).
    """
    return frozenset(c.casefold() for c in composantes_identite(s))


# Liste blanche des rattrapages relus à la main (décision du propriétaire du
# 20/11/2026 : zéro fusion fausse). Clé : l'identifiant `rne-*` que la
# personne RNE recevrait (`_identifiant_rne`), cible : la fiche AN ou Sénat.
# Voir `_rattraper` pour ce qui y entre et pourquoi.
CHEMIN_RATTRAPAGES_VERIFIES = RACINE / "deploy" / "rattrapages-elus.tsv"
# Une cible de rattrapage est une fiche AN ou Sénat, jamais une `rne-*`.
MOTIF_CLE_RNE = r"rne-[0-9a-f]{16}"
MOTIF_FICHE_PARLEMENTAIRE = r"PA\d+|SEN-\d{5}[A-Z]"


def charger_rattrapages_verifies(chemin=None) -> dict[str, str]:
    """La liste blanche de P7, au format validé (voir `charger_liste_blanche`)."""
    return charger_liste_blanche(chemin or CHEMIN_RATTRAPAGES_VERIFIES,
                                 MOTIF_CLE_RNE, MOTIF_FICHE_PARLEMENTAIRE)


def _a_un_mandat_parlementaire(p: dict) -> bool:
    """Vrai si la personne RNE porte un mandat de député ou de sénateur.

    Une fiche AN/Sénat ne reçoit que les mandats d'une personne que le RNE
    enregistre AUSSI comme député ou sénateur : un maire homonyme, né le même
    jour, n'est jamais une cible. Mesuré le 20/11/2026 : les 16 rattrapages
    l'ont tous.
    """
    return any(m.get("type") in ("depute", "senateur") for m in p["mandats"])


def _identifiant_rne(cle: tuple[str, str, str]) -> str:
    """Identifiant `rne-*` d'une personne RNE : haché de sa clé d'état civil."""
    return "rne-" + hashlib.sha1("|".join(cle).encode()).hexdigest()[:16]


def _dep_rne(r: dict) -> str:
    d = normaliser_departement(r.get("Code du département"))
    return d or normaliser_departement(r.get("Code de la collectivité à statut particulier"))


def est_president_cd(r: dict) -> bool:
    return normaliser_texte(r.get("Libellé de la fonction")).startswith(
        "president du conseil departemental")


def est_president_cr(r: dict) -> bool:
    return normaliser_texte(r.get("Libellé de la fonction")).startswith(
        "president du conseil regional")


def est_president_epci(r: dict) -> bool:
    return normaliser_texte(r.get("Libellé de la fonction")).startswith(
        "president du conseil communautaire")


def construire_index_rne(rne: dict[str, list[dict]]) -> dict[str, dict]:
    """Index d'appariement A1 : {type_mandat: {(nom, prénom, dept): [candidats]}}.

    Candidat = {"fonction_debut": date|None, "commune": str normalisée (maires)}.
    Pour `region`, la HATVP ne publie pas de département → clé dept = ''.
    """
    index: dict[str, dict] = {t: defaultdict(list) for t in
                              ("depute", "senateur", "commune", "departement", "region")}

    def cle(r: dict, dep: str) -> tuple[str, str, str]:
        return (normaliser_texte(r["Nom de l'élu"]), normaliser_texte(r["Prénom de l'élu"]), dep)

    for r in rne["deputes"]:
        index["depute"][cle(r, _dep_rne(r))].append(
            {"fonction_debut": _parser_date_iso(r["Date de début du mandat"]), "commune": ""})
    for r in rne["senateurs"]:
        index["senateur"][cle(r, _dep_rne(r))].append(
            {"fonction_debut": _parser_date_iso(r["Date de début du mandat"]), "commune": ""})
    for r in rne["maires"]:
        index["commune"][cle(r, _dep_rne(r))].append({
            "fonction_debut": _parser_date_iso(
                r["Date de début de la fonction"] or r["Date de début du mandat"]),
            "commune": normaliser_texte(r["Libellé de la commune"]),
        })
    for r in rne["cd"]:
        if est_president_cd(r):
            index["departement"][cle(r, normaliser_departement(r["Code du département"]))].append({
                "fonction_debut": _parser_date_iso(
                    r["Date de début de la fonction"] or r["Date de début du mandat"]),
                "commune": "",
            })
    for r in rne["cr"]:
        if est_president_cr(r):
            index["region"][cle(r, "")].append({
                "fonction_debut": _parser_date_iso(
                    r["Date de début de la fonction"] or r["Date de début du mandat"]),
                "commune": "",
            })
    return index


# ---------------------------------------------------------------------------
# Alerte A1 — règle révisée de SOURCES.md §4
# ---------------------------------------------------------------------------


def derniere_entree_collective(conn, table: str) -> str | None:
    """Plus récente date de début de mandat partagée par au moins
    PART_ENTREE_COLLECTIVE des élus en exercice de `table` (deputes ou
    senateurs, écrites par P9). None si la table est absente, vide, ou
    qu'aucune date n'atteint ce seuil : rien n'est alors vérifiable."""
    if table not in TABLES_CHAMBRES.values():
        raise ValueError(f"table de chambre inconnue : {table!r}")
    try:
        total = conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        lignes = conn.execute(
            f"SELECT date_debut_mandat, count(*) FROM {table}"
            " WHERE date_debut_mandat IS NOT NULL GROUP BY 1").fetchall()
    except sqlite3.OperationalError:
        return None
    dates = [d for d, n in lignes if total and n >= PART_ENTREE_COLLECTIVE * total]
    return max(dates) if dates else None


def types_rne_anterieurs(conn, rne: dict[str, list[dict]]) -> dict[str, tuple]:
    """{type_mandat: (entrée collective de la chambre, début le plus récent
    du RNE)} pour les chambres dont le RNE ingéré précède le dernier
    renouvellement. Une chambre non vérifiable (table de P9 absente ou sans
    date collective) est journalisée et N'EST PAS écartée : le garde-fou ne
    retire une alerte que sur preuve."""
    perimes: dict[str, tuple] = {}
    for tm, table in TABLES_CHAMBRES.items():
        entree = derniere_entree_collective(conn, table)
        debuts = [d for d in (_parser_date_iso(r.get("Date de début du mandat"))
                              for r in rne.get(CLES_RNE_CHAMBRES[tm], [])) if d]
        plus_recent = max(debuts).isoformat() if debuts else None
        if entree is None:
            log.warning("A1 : renouvellement de la chambre « %s » non vérifiable"
                        " (table %s absente ou sans date d'entrée collective)",
                        tm, table)
            continue
        if plus_recent is None or plus_recent < entree:
            perimes[tm] = (entree, plus_recent)
    # Journalisé À CHAQUE CYCLE, vide compris.
    log.info("A1 : chambres dont le RNE précède le dernier renouvellement"
             " (dossiers « En cours » non comptés) : %s",
             {tm: f"entrée {e}, RNE au plus tard {r}" for tm, (e, r) in perimes.items()}
             or "aucune")
    return perimes


def delai_legal_ecoule(debut: date, aujourd_hui: date) -> bool:
    """Vrai si le délai légal de 2 mois ouvert le jour `debut` est échu.

    Entrée en fonction le 1er juillet : échéance le 1er septembre, jour
    compris. Lu le 31 août ou le 1er septembre, le délai court encore, lu le
    2 septembre il est écoulé. L'ancien décompte en 60 jours le donnait pour
    écoulé dès le 31 août.
    """
    return ajouter_mois(debut, DELAI_LEGAL_A1_MOIS) < aujourd_hui


def calculer_a1(dossiers: list[dict], index_rne: dict[str, dict],
                aujourd_hui: date,
                types_perimes: frozenset[str] | set[str] = frozenset(),
                ) -> tuple[list[dict], list[dict], Counter]:
    """Applique la règle A1. Retourne (nominatives, en_cours_delai_ecoule, stats).

    `types_perimes` : types de mandat dont le RNE précède le dernier
    renouvellement de la chambre (voir types_rne_anterieurs) : aucun dossier
    n'y est compté au-delà du délai, chaque dossier est compté à part.

    - nominatives : dossiers au statut natif « Déclaration non déposée »
      (seuls cas nominatifs autorisés) ;
    - en_cours_delai_ecoule : dossiers « En cours » appariés à un élu RNE
      unique dont l'entrée en fonction remonte à plus de 2 mois calendaires
      (`delai_legal_ecoule`, EPCI exclus, homonymes non tranchés exclus,
      documents initiaux seulement) ;
    - stats : compteurs de tri (exclusions, non-appariés…) pour la traçabilité.
    """
    nominatives = [d for d in dossiers if d["statut_publication"] == STATUT_NON_DEPOSEE]
    retards: list[dict] = []
    stats: Counter = Counter()

    for d in dossiers:
        if d["statut_publication"] != STATUT_EN_COURS:
            continue
        stats["en_cours"] += 1
        tm = d["type_mandat"]
        if tm == "epci":                       # garde-fou n° 1
            stats["exclu_epci"] += 1
            continue
        if d["type_document"] not in DOCS_INITIAUX:   # garde-fou n° 4
            stats["exclu_document_non_initial"] += 1
            continue
        if tm not in index_rne:                # garde-fou n° 5 (périmètre apparié)
            stats["exclu_mandat_hors_perimetre"] += 1
            continue
        if tm in types_perimes:                # garde-fou n° 7
            stats["rne_anterieur_au_renouvellement"] += 1
            continue
        qualite = normaliser_texte(d["qualite"])
        commune_qualite = ""
        if tm == "commune":
            m = _RE_MAIRE.match(qualite)
            if not m:                          # adjoints, maires délégués…
                stats["exclu_qualite_hors_population"] += 1
                continue
            commune_qualite = _sans_article(m.group(1))
        elif tm == "departement" and not _RE_PRESIDENT_CD.match(qualite):
            stats["exclu_qualite_hors_population"] += 1
            continue
        elif tm == "region" and not _RE_PRESIDENT_CR.match(qualite):
            stats["exclu_qualite_hors_population"] += 1
            continue

        cle = (normaliser_texte(d["nom"]), normaliser_texte(d["prenom"]),
               "" if tm == "region" else normaliser_departement(d["departement"]))
        candidats = index_rne[tm].get(cle, [])
        if not candidats:
            stats["non_apparie"] += 1
            continue
        if len(candidats) > 1:                 # garde-fou n° 2
            stats["homonyme_non_tranche"] += 1
            continue
        candidat = candidats[0]
        if tm == "commune" and commune_qualite and \
                _sans_article(candidat["commune"]) != commune_qualite:
            stats["commune_differente"] += 1   # même nom, autre commune → prudence
            continue
        debut = candidat["fonction_debut"]
        if debut is None:
            stats["sans_date_fonction"] += 1
            continue
        if delai_legal_ecoule(debut, aujourd_hui):
            stats["delai_ecoule"] += 1
            retards.append(d)
        else:
            stats["delai_non_ecoule"] += 1
    return nominatives, retards, stats


#: Clé de la cellule qui regroupe les types de mandat sous le seuil.
MANDATS_REGROUPES = "autres"


def regrouper_sous_seuil(par_mandat: dict[str, list[dict]],
                         seuil: int = SEUIL_PERSONNES_AGREGAT,
                         ) -> tuple[list[tuple[str, list[dict]]], int]:
    """Cellules publiables d'un agrégat par type de mandat.

    Un type de mandat qui compte moins de `seuil` personnes distinctes
    (`classement`, clé personne HATVP) ne forme pas sa propre cellule : ses
    dossiers rejoignent « autres mandats ». Ce regroupement n'est publié que
    s'il atteint lui-même le seuil. Retourne (cellules, personnes_retenues),
    où `personnes_retenues` compte les personnes qui ne figurent dans aucune
    cellule publiée (journalisé, jamais publié).
    """
    cellules: list[tuple[str, list[dict]]] = []
    reste: list[dict] = []
    for tm in sorted(par_mandat):
        ds = par_mandat[tm]
        if len({d["classement"] for d in ds}) >= seuil:
            cellules.append((tm, ds))
        else:
            reste.extend(ds)
    personnes_reste = len({d["classement"] for d in reste})
    if reste and personnes_reste >= seuil:
        cellules.append((MANDATS_REGROUPES, reste))
        personnes_reste = 0
    return cellules, personnes_reste


def _cle_dossier_hatvp(d: dict) -> str:
    """Clé lisible d'un dossier : `classement`, la clé personne que liste.csv
    publie sur chaque ligne (« GÂTÉ Sylvie23162 » → « gate-sylvie23162 »).

    POURQUOI pas le bout de `url_dossier` : l'URL peut manquer, puis être
    publiée plus tard. L'identifiant changeait alors, et l'alerte prenait
    une nouvelle date de détection (`db.remplacer_alertes`). `classement` ne
    dépend pas de l'URL. Repli sur le nom quand il manque.
    """
    brut = (d.get("classement") or "").strip() or f"{d['nom']} {d['prenom']}"
    return normaliser_texte(brut).replace(" ", "-")


def identifiants_non_deposees(nominatives: list[dict]) -> list[str]:
    """Identifiants des alertes A1-ND, un par dossier et dans le même ordre.

    Forme ordinaire : `A1-ND-{classement}-{type_document}`. Deux dossiers
    qui la partagent (deux mandats d'une même personne, ou deux homonymes
    sans `classement`) faisaient échouer l'insertion sur la clé primaire, et
    tomber le pipeline. Chacun reçoit alors en suffixe l'empreinte de sa
    ligne liste.csv entière. `dedoublonner_hatvp` a écarté les lignes
    identiques : deux dossiers distincts ont deux empreintes distinctes,
    quel que soit leur ordre de lecture. Le cas ordinaire garde un
    identifiant qui ne dépend que de la personne et du type de document.
    """
    bases = [f"A1-ND-{_cle_dossier_hatvp(d)}-{d['type_document']}" for d in nominatives]
    nombre = Counter(bases)
    ids = []
    for base, d in zip(bases, nominatives):
        if nombre[base] == 1:
            ids.append(base)
            continue
        ligne = "\x1f".join(str(d.get(c) or "") for c in COLONNES_HATVP)
        ids.append(f"{base}-{hashlib.sha256(ligne.encode('utf-8')).hexdigest()[:10]}")
    if len(set(ids)) != len(ids):
        raise RuntimeError("A1 : deux dossiers HATVP identiques après dédoublonnage")
    return ids


def construire_alertes(nominatives: list[dict], en_cours: list[dict],
                       aujourd_hui: date, date_hatvp: str, date_rne: str) -> list[tuple]:
    """Lignes prêtes pour la table alertes. Nominatif = non déposées SEULEMENT.

    `date_hatvp` / `date_rne` : dates réelles des données (ISO), citées dans
    les textes pour que les réserves restent vraies aux runs suivants.
    `date_hatvp` est aussi la `date_fait` des lignes : les deux types
    décrivent l'état de liste.csv à cette date, pas l'instant du cycle.
    """
    date_calcul = aujourd_hui.isoformat()
    regle_en_cours = REGLE_A1_EN_COURS.format(date_rne=date_rne)
    lignes: list[tuple] = []
    ids_nd = identifiants_non_deposees(nominatives)
    for d, ident in zip(nominatives, ids_nd):
        lignes.append((
            ident,
            TYPE_ALERTE_NON_DEPOSEE,
            "haute",
            f"Déclaration non déposée (constat officiel HATVP) : "
            f"{d['prenom']} {d['nom']}, {d['qualite']}",
            f"{LIBELLES_DOC.get(d['type_document'], d['type_document'])} "
            f"(mandat « {d['type_mandat']} », département « {d['departement']} »). "
            f"Statut publié tel quel par la HATVP dans liste.csv du {date_hatvp}.",
            REGLE_A1_NON_DEPOSEE,
            BASE_LEGALE_A1,
            (URL_HATVP_SITE + d["url_dossier"]) if d["url_dossier"] else URL_HATVP_LISTE,
            date_calcul,
            date_hatvp,
        ))
    par_mandat: dict[str, list[dict]] = defaultdict(list)
    for d in en_cours:
        par_mandat[d["type_mandat"]].append(d)
    cellules, retenues = regrouper_sous_seuil(par_mandat)
    if retenues:
        log.info("A1 : %d personne(s) hors de tout agrégat publié (moins de %d "
                 "personnes, même regroupées)", retenues, SEUIL_PERSONNES_AGREGAT)
    for tm, ds in cellules:
        personnes = len({d["classement"] for d in ds})
        libelle = ("autres mandats, chacun sous 3 personnes"
                   if tm == MANDATS_REGROUPES else f"mandat « {tm} »")
        lignes.append((
            f"A1-EC-{tm}",
            TYPE_ALERTE_EN_COURS,
            "info",
            f"{len(ds)} déclarations au statut « En cours » à la HATVP plus de "
            f"2 mois après l'entrée en fonction, {libelle}",
            f"{len(ds)} dossiers au statut « En cours » dans liste.csv de la "
            f"HATVP du {date_hatvp}, pour {personnes} personnes, dont l'entrée "
            f"en fonction connue du répertoire national des élus du {date_rne} "
            f"remonte à plus de 2 mois, délai légal de dépôt. Le site ne connaît "
            f"pas la définition officielle de ce statut : il peut désigner une "
            f"déclaration attendue comme une déclaration déposée en cours "
            f"d'examen. Ce compte ne constate aucun manquement. Agrégat non "
            f"nominatif, jamais publié sous 3 personnes.",
            regle_en_cours,
            BASE_LEGALE_A1,
            URL_HATVP_LISTE,
            date_calcul,
            date_hatvp,
        ))
    return lignes


def ecrire_alertes(conn, lignes: list[tuple],
                   aujourd_hui: date | None = None) -> None:
    """Table partagée : ne supprime QUE les types d'alerte de ce pipeline,
    ancien type compris. `date_detection` (premier cycle qui a vu l'id) est
    relue avant la purge et gardée, `aujourd_hui` date les alertes nouvelles
    (db.remplacer_alertes)."""
    db.remplacer_alertes(
        conn, TYPES_ALERTES_EFFACES_P7,
        ("id", "type", "gravite", "titre", "detail", "regle", "base_legale",
         "source_url", "date_calcul", "date_fait"),
        lignes, (aujourd_hui or date.today()).isoformat())


# ---------------------------------------------------------------------------
# elus — upsert prudent + croisement HATVP
# ---------------------------------------------------------------------------


def preparer_personnes(rne: dict[str, list[dict]]) -> dict[tuple, dict]:
    """Fusionne les fichiers RNE en personnes : 1 personne = n mandats (JSON)."""
    personnes: dict[tuple, dict] = {}

    def ajouter(r: dict, mandat: dict) -> None:
        cle = _cle_personne(r)
        p = personnes.setdefault(cle, {
            "nom": r["Nom de l'élu"].strip(),
            "prenom": r["Prénom de l'élu"].strip(),
            "sexe": (r["Code sexe"] or "").strip() or None,
            "date_naissance": (r["Date de naissance"] or "").strip() or None,
            "profession": (r["Libellé de la catégorie socio-professionnelle"] or "").strip() or None,
            "mandats": [],
        })
        p["mandats"].append({k: v for k, v in mandat.items() if v})

    for r in rne["deputes"]:
        ajouter(r, {"source": "RNE", "type": "depute",
                    "departement": r["Code du département"],
                    "circonscription": r["Libellé de la circonscription législative"],
                    "date_debut_mandat": r["Date de début du mandat"]})
    for r in rne["senateurs"]:
        ajouter(r, {"source": "RNE", "type": "senateur",
                    "departement": r["Code du département"],
                    "date_debut_mandat": r["Date de début du mandat"]})
    for r in rne["maires"]:
        ajouter(r, {"source": "RNE", "type": "maire",
                    "departement": r["Code du département"],
                    "code_commune": r["Code de la commune"],
                    "commune": r["Libellé de la commune"],
                    "date_debut_mandat": r["Date de début du mandat"],
                    "date_debut_fonction": r["Date de début de la fonction"]})
    for r in rne["cd"]:
        if est_president_cd(r):
            ajouter(r, {"source": "RNE", "type": "president_conseil_departemental",
                        "departement": r["Code du département"],
                        "libelle": r["Libellé du département"],
                        "fonction": r["Libellé de la fonction"],
                        "date_debut_mandat": r["Date de début du mandat"],
                        "date_debut_fonction": r["Date de début de la fonction"]})
    for r in rne["cr"]:
        if est_president_cr(r):
            ajouter(r, {"source": "RNE", "type": "president_conseil_regional",
                        "region": r["Libellé de la région"],
                        "code_region": r["Code de la région"],
                        "fonction": r["Libellé de la fonction"],
                        "date_debut_mandat": r["Date de début du mandat"],
                        "date_debut_fonction": r["Date de début de la fonction"]})
    for r in rne["epci"]:
        if est_president_epci(r):
            ajouter(r, {"source": "RNE", "type": "president_epci",
                        "departement": r["Code du département"],
                        "siren_epci": r["N° SIREN"],
                        "epci": r["Libellé de l'EPCI"],
                        "fonction": r["Libellé de la fonction"],
                        "date_debut_mandat": r["Date de début du mandat"],
                        "date_debut_fonction": r["Date de début de la fonction"]})
    return personnes


def _rattraper(p: dict, index_nom: dict, garde: set) -> dict | None:
    """Retrouve la fiche AN/Sénat d'une personne que la clé exacte a manquée.

    POURQUOI cette seconde chance existe. La clé exacte est
    `(nom, prénom, date de naissance)` normalisés. Elle est juste, et elle doit
    le rester : 588 couples nom+prénom sont partagés par au moins deux
    personnes dans `elus`, et c'est la date de naissance qui les sépare
    (cf. tests de P15, et § 9.6 de la documentation d'exploitation, tenue
    HORS DU DÉPÔT sur le serveur : /srv/france-transparence/doc/EXPLOITATION.md).
    Mais elle échoue chaque fois que le RNE et la chambre n'écrivent pas
    l'état civil de la MÊME façon — mesuré le 26/08/2026 sur les 36 020
    lignes de la base servie, 17 fois :

      · le RNE tronque un nom composé que la chambre porte en entier
        (RNE « FAVENNEC » / AN « Favennec-Bécot », 4 cas), ou l'inverse
        (RNE « FOUCHER CHAZÉ » / AN « Chazé »), ou la composante commune est
        en FIN de nom (RNE « VAGINAY » / AN « Ricourt Vaginay », 3 cas) ;
      · l'AN désambiguïse deux homonymes par le département entre parenthèses
        (« Martin (Gironde) »), 2 cas ;
      · les graphies divergent sur la ponctuation (RNE « KBIDI » / AN
        « K/Bidi ») ou le RNE porte une faute de frappe (« REID ABERLOT »
        pour « Reid Arbelot ») ;
      · le prénom est tronqué (RNE « Frédéric » / AN « Frédéric-Pierre »,
        2 cas) ;
      · les deux sources se contredisent d'un chiffre sur la date (2 cas).

    Trois garde-fous, sans lesquels le remède serait pire que le mal :
      1. on ne cherche QUE parmi les fiches AN/Sénat (`index_nom` ne contient
         qu'elles). Le problème est de ne pas créer un `rne-*` en double d'une
         fiche existante ; élargir aux 35 093 lignes d'élus locaux ferait
         fusionner des homonymes que rien ne distingue plus ;
      2. depuis le 20/11/2026 (audit C1, décision du propriétaire : zéro
         fusion fausse) : la date de naissance EXACTE, et le nom comme le
         prénom en relation d'inclusion (`ecritures_incluses`). L'ancienne
         règle cumulait trois tolérances (un mot de nom commun, un mot de
         prénom commun, une composante de date différente) et laissait
         fusionner deux personnes : RNE « Jean-Paul » né 9 jours après une
         fiche « Jean-Luc » de même nom, ou deux jumeaux « Jean-Marc » et
         « Jean-Luc ». Les cas justes que la règle stricte perd (la faute de
         frappe, les deux dates qui divergent d'un chiffre) ne passent plus
         que par la liste blanche relue `CHEMIN_RATTRAPAGES_VERIFIES`, avec
         la preuve de chaque ligne. Depuis le 21/11/2026, la règle ne fait
         plus que proposer : `upsert_elus` n'applique que la liste blanche,
         et signale au journal, sans l'appliquer, ce que la règle trouve hors
         de la liste.
      3. **un seul candidat**, sinon on renonce. Deux candidats, c'est une
         homonymie, et attribuer la déclaration d'intérêts d'une personne à
         une autre serait la faute la plus grave possible ici.

    Mesure de contrôle du 26/08/2026, en rejouant `upsert_elus` sur une COPIE
    de la base servie : 17 rattrapages, 0 candidat ambigu, 0 fiche déjà
    appariée touchée, 0 fiche créée, `elus` passant de 36 020 à 36 003 lignes.

    ⚠️ CE « 17 » EST PÉRIMÉ, PAS FAUX, et le chiffre du jour est **16**.
    Il valait 17 tant que la base portait les deux fiches en double. Le `DELETE`
    du 26/08 a retiré les doublons ; depuis, une des 17 paires —
    `rne-14dcb94cc2c7d19f` -> `SEN-21634U` — est attrapée par la CLÉ EXACTE,
    donc AVANT d'arriver ici : c'est la seule des 17 dont le RNE et le Sénat
    écrivent l'état civil à l'identique. `_rattraper` n'en voit plus que 16, et
    le journal de chaque cycle l'écrit (« 16 rattrapés sur une fiche AN/Sénat »).
    Re-mesuré le 28/08/2026 par rejeu sur une copie de la base servie, avec sa
    contre-épreuve : le doublon réinséré avec un rowid inférieur redonne 17.
    **16 est correct et stable.** Ne pas « corriger » ce nombre vers 17 sans
    avoir rejoué la mesure : c'est l'état de `elus` qui le fixe, pas ce texte.

    Re-mesuré le 20/11/2026 par rejeu en lecture seule sur la base servie et
    le RNE relivré le jour même : toujours 16, mais pas les mêmes. MAINGAULT et
    PONCET sont sortis (fin de mandat au Sénat), VERMOREL-MARQUES est entré
    (le RNE porte désormais le nom composé, l'AN « Vermorel »). Sous la règle
    stricte, 13 tiennent seuls et 3 ne tiennent que par la liste blanche
    (OLIVE et GALZY, une composante de date, REID ABERLOT, faute de frappe),
    tous au même siège des deux côtés.

    La liste des 17 identifiants est dans `deploy/redirections-elus.tsv` : le
    lot se MESURE, il ne se recopie pas d'une séance à l'autre — il dépend de
    l'état de `elus` du jour et du millésime RNE du jour. Cette table est aussi
    la source des redirections 301 qui empêchent les URL retirées de tomber en
    404 : voir `docs/REDIRECTIONS-ELUS.md`.

    ⚠️ L'ordre des gestes a changé le 27/08/2026 : ce texte prescrivait de
    « poser la règle nginx AVANT de laisser un cycle retirer les fiches ». Le
    régime COURANT est désormais l'inverse — `poser-301-d22.sh` lit l'arbre qui
    PUBLIE, qui n'avance qu'au `git fetch` de `ft-deploy` : posée avant, la
    règle serait engendrée depuis l'ANCIENNE table. Les deux régimes et ce
    qu'ils coûtent sont dans `docs/REDIRECTIONS-ELUS.md`.

    Les fiches AN/Sénat qui restent sans mandat RNE après ce passage ne sont
    PAS des doublons : ce sont des arrivées récentes absentes du millésime RNE,
    et un prénom d'usage qu'aucune règle sur l'état civil ne peut trancher
    (RNE « Peter VIGIER » / AN « Jean-Pierre Vigier » : même date de naissance
    et même siège, mais `_composantes('Peter') ∩ _composantes('Jean-Pierre')`
    est vide — le repli y est structurellement AVEUGLE). Les laisser non
    appariées est le comportement correct : il vaut mieux deux fiches qu'une
    fusion fausse.
    """
    naissance = (p["date_naissance"] or "").strip()
    if len(naissance) != 10:
        return None
    composantes_prenom = _composantes(p["prenom"])
    if not composantes_prenom:
        return None
    candidats: dict[str, dict] = {}
    for c in _composantes(p["nom"]):
        for e in index_nom.get((naissance[:4], c), ()):
            if e["id"] in candidats or e["id"] in garde:
                continue
            if (e["date_naissance"] or "").strip() != naissance:
                continue
            if not (composantes_prenom & _composantes(e["prenom"])):
                continue
            if not (ecritures_incluses(p["nom"], e["nom"])
                    and ecritures_incluses(p["prenom"], e["prenom"])):
                continue
            candidats[e["id"]] = e
    if len(candidats) != 1:                # garde-fou n° 3 : homonymie
        return None
    return next(iter(candidats.values()))


def _controler_volume_supprimees(supprimes: list[str], nb_cibles: int) -> None:
    """Refuse un cycle qui supprimerait un volume invraisemblable de fiches.

    POURQUOI C'EST LA SUPPRESSION QU'ON GARDE, ET PAS LE COMPTE DE RATTRAPAGES.
    Un rattrapage qui n'efface rien — le cas de l'intégration continue, dont la
    base naît neuve — ne fait que verser des mandats RNE sur une fiche AN ; le
    cycle suivant les remplace en bloc, l'erreur ne survit pas à la nuit. Le
    `DELETE`, lui, ne se répare pas : la fiche partie, les déclarations que P15
    lui rattachait basculent sur son chemin `hors_fiche`, qui journalise sans
    faire échouer et **efface la mémoire du garde-fou de la PR #90 sans
    retour**. C'est donc le geste irréversible qu'il faut borner, pas son
    superensemble.

    PLANCHER *ET* PROPORTION, jamais l'un sans l'autre — la forme est celle des
    garde-fous de P15 (`ingest_hatvp_declarations`, repli d'orthographe ≤ 15 %
    doublé d'un plancher de 1 000 rattachements). La proportion seule ferait
    échouer l'intégration continue, dont les fixtures ne portent qu'une poignée
    de fiches ; le plancher seul serait aveugle à une base qui aurait fondu.

    L'acquittement ne desserre AUCUN seuil : il nomme, un par un, les
    identifiants dont l'exploitant assume la suppression.
    """
    acquittes = {i.strip() for i in
                 os.environ.get(ENV_RATTRAPAGES_ACQUITTES, "").split(",") if i.strip()}
    restants = [i for i in supprimes if i not in acquittes]
    if acquittes:
        log.warning("rattrapage : %d suppression(s) acquittée(s) par %s",
                    len(supprimes) - len(restants), ENV_RATTRAPAGES_ACQUITTES)
    if not (len(restants) > PLANCHER_RATTRAPAGES
            and len(restants) > PROPORTION_RATTRAPAGES * nb_cibles):
        return
    # La liste COMPLÈTE part au journal AVANT la levée : le message d'exception
    # tronque à huit, et l'acquittement exige de nommer chaque identifiant.
    # Sans cette ligne, l'issue de secours serait inutilisable.
    log.error("rattrapage : liste complète des %d fiches à supprimer : %s",
              len(restants), " ".join(restants))
    raise ValueError(
        f"rattrapage invraisemblable : {len(restants)} fiche(s) `rne-*` seraient "
        f"supprimées pour {nb_cibles} fiches AN/Sénat indexées "
        f"(plancher {PLANCHER_RATTRAPAGES}, plafond "
        f"{PROPORTION_RATTRAPAGES:.0%}) — le millésime RNE est-il abîmé ? "
        f"Base NON modifiée. Identifiants : {', '.join(restants[:8])}"
        f"{' …' if len(restants) > 8 else ''}. Après examen, acquitter "
        f"identifiant par identifiant avec {ENV_RATTRAPAGES_ACQUITTES}=<id,id> "
        f"— la liste complète est dans le journal, ligne « rattrapage : liste "
        f"complète ».")


# La requête d'état civil est écrite UNE fois et partagée par `upsert_elus` et
# son contrôle : le contrôle voit ainsi le MÊME ordre de balayage que le code
# qu'il observe, et aucune réécriture future ne peut le lui faire perdre en
# silence. ⚠️ Mesuré le 28/08/2026 sur la base servie, contre une première
# rédaction de ce commentaire qui affirmait trop : abréger la projection ne
# suffit PAS à changer l'ordre. `SELECT id, nom, prenom, date_naissance FROM
# elus` reste planifié `SCAN elus` et rend le même ordre. Seule une projection
# ENTIÈREMENT contenue dans un index bascule — `SELECT rowid` devient
# `SCAN elus USING COVERING INDEX idx_elus_uid_an`, `SELECT id` devient
# `SCAN … USING COVERING INDEX sqlite_autoindex_elus_1`, et celle-là rend bien
# un autre ordre. Le partage ne corrige donc pas un défaut existant : il ferme
# une porte étroite, avant qu'un index ajouté un jour ne l'élargisse.
REQUETE_ETAT_CIVIL = ("SELECT id, nom, prenom, date_naissance, sexe, profession,"
                      " mandats FROM elus")


def upsert_elus(conn, personnes: dict[tuple, dict],
                liste_blanche: dict[str, str] | None = None,
                passees: dict[str, str] | None = None) -> tuple[int, int, int]:
    """UPSERT prudent par (nom, prénom, date de naissance) normalisés.

    `liste_blanche` : {identifiant `rne-*` : fiche AN/Sénat}, rattrapages relus
    à la main. Par défaut, `CHEMIN_RATTRAPAGES_VERIFIES`. C'est le SEUL moyen
    de rattraper : une ligne ne s'applique qu'à une personne RNE qui porte un
    mandat de député ou de sénateur, dont la date de naissance est complète,
    et vers une fiche AN/Sénat que la clé exacte n'atteint pas déjà.
    `_rattraper` ne fait que proposer, au journal, ce qu'il faut vérifier
    puis inscrire. Une ligne refusée ou sans effet est journalisée.

    Ne touche jamais uid_an / matricule_senat ; ne remplit sexe et profession
    que s'ils sont NULL ; remplace uniquement les mandats "source": "RNE" du
    JSON, les autres sont conservés. `date_naissance` n'est JAMAIS écrite sur
    une fiche existante (une version antérieure de cette docstring promettait
    de la compléter) : elle fait partie de la clé d'appariement. Une fiche
    sans date n'est atteinte par la clé exacte que par une personne RNE
    elle-même sans date, et jamais par `_rattraper`, qui exige l'année : il
    n'y aurait rien à compléter. Et la compléter changerait la clé d'une
    fiche que P15 indexe sur la même date.

    Quand la clé exacte échoue, `_rattraper` tente une seconde fois contre les
    seules fiches AN/Sénat — voir sa docstring pour le pourquoi et les trois
    garde-fous. Un rattrapage supprime au passage la ligne `rne-*` que les
    ingestions PRÉCÉDENTES avaient créée pour cette même personne : sans cette
    purge, corriger l'appariement cesserait d'ajouter des doublons sans
    effacer ceux qui sont déjà en base, et le site continuerait de servir deux
    fiches pour une seule personne. La base servie survit d'un déploiement à
    l'autre, contrairement à celle de l'intégration continue qui naît neuve à
    chaque passage : c'est là, et là seulement, que les doublons persistent.

    `passees` : {fiche PA retirée : fiche SEN de la même personne}, par défaut
    les lignes `PA* -> SEN-*` de `deploy/redirections-elus.tsv`. Le député
    devenu sénateur porte deux fiches sous la même clé. Les mandats RNE vont à
    la fiche SEN, la seule publiée, quel que soit l'ordre de lecture, et ceux
    qu'un cycle précédent avait posés sur la PA retirée en sont ôtés. Avant le
    21/11/2026, le premier lu gagnait : la PA recevait le mandat de sénateur.
    """
    if liste_blanche is None:
        liste_blanche = charger_rattrapages_verifies()
    if passees is None:
        passees = charger_fiches_passees_au_senat()
    existants: dict[tuple, dict] = {}
    evincees: dict[tuple, dict] = {}    # clé -> fiche PA retirée au profit de sa SEN
    index_nom: dict[tuple, list] = defaultdict(list)
    # Fiches AN/Sénat indexées : dénominateur du garde-fou de volume, et seules
    # cibles admises pour la liste blanche.
    cibles: dict[str, dict] = {}
    for r in conn.execute(REQUETE_ETAT_CIVIL):
        e = dict(r)
        cle = (normaliser_texte(e["nom"]), normaliser_texte(e["prenom"]),
               (e["date_naissance"] or "").strip())
        deja = existants.get(cle)
        if deja is None:
            existants[cle] = e
        elif passees.get(deja["id"]) == e["id"]:
            evincees[cle] = deja
            existants[cle] = e
        elif passees.get(e["id"]) == deja["id"]:
            evincees[cle] = e
        if not e["id"].startswith("rne-"):     # garde-fou n° 1 : cibles AN/Sénat
            annee = (e["date_naissance"] or "")[:4]
            if annee:
                cibles[e["id"]] = e
                for c in _composantes(e["nom"]):
                    index_nom[(annee, c)].append(e)

    inseres = maj = rattrapes = 0
    hors_liste: list[str] = []      # proposés par la règle, absents de la liste
    refus: list[str] = []           # lignes de la liste refusées ce cycle
    utilisees: set[str] = set()
    supprimes: list[str] = []
    # Garde-fou n° 4 : une fiche AN/Sénat que la CLÉ EXACTE atteint déjà n'est
    # pas rattrapable. Le seul `pris.add()` de la boucle n'interdit qu'un DOUBLE
    # rattrapage ; il laisse ouverte la collision clé exacte × rattrapage — deux
    # personnes RNE distinctes écrivant leurs mandats sur la même fiche, la
    # seconde effaçant en silence les entrées "source": "RNE" de la première
    # (reproduit en laboratoire ; 0 occurrence sur les données du 26/08/2026).
    # Le pré-calcul rend le garde-fou INDÉPENDANT DE L'ORDRE d'itération :
    # interdire la cible seulement quand la clé exacte l'a déjà rencontrée
    # laisserait passer le cas où le rattrapage arrive en premier.
    pris: set = {existants[c]["id"] for c in personnes
                 if c in existants and not existants[c]["id"].startswith("rne-")}
    for cle, p in personnes.items():
        e = existants.get(cle)
        # La clé exacte peut très bien retomber sur le DOUBLON lui-même : une
        # ingestion antérieure au correctif a créé une ligne `rne-*` qui porte
        # exactement cette clé. La trouver ne prouve donc rien — il faut quand
        # même chercher la fiche AN/Sénat, et si elle existe, c'est ELLE la
        # bonne cible et la ligne `rne-*` doit disparaître. Sans cette reprise,
        # le correctif cesserait de créer des doublons sans jamais effacer ceux
        # que la base servie porte déjà, et le site ne bougerait pas.
        # Seule la liste blanche rattrape. La règle ne fait que proposer, au
        # journal, ce qu'il faut vérifier puis inscrire. Garde-fou n° 5 : la
        # personne RNE porte elle-même un mandat de député ou de sénateur.
        cible = None
        if (e is None or e["id"].startswith("rne-")) and _a_un_mandat_parlementaire(p):
            ident_rne = _identifiant_rne(cle)
            verifiee = liste_blanche.get(ident_rne)
            if verifiee is not None:
                raison = None
                if not date_complete(cle[2]):
                    raison = "clé calculée sans date de naissance complète"
                elif verifiee not in cibles:
                    raison = "la cible n'est pas une fiche AN/Sénat de la base"
                elif verifiee in pris:
                    raison = "fiche déjà atteinte par la clé exacte"
                if raison is None:
                    cible = cibles[verifiee]
                    utilisees.add(ident_rne)
                else:
                    refus.append(f"{ident_rne} -> {verifiee} ({p['nom']} {p['prenom']})"
                                 f" : {raison}")
            if cible is None:
                regle = _rattraper(p, index_nom, pris)
                if regle is not None:
                    hors_liste.append(f"{ident_rne} -> {regle['id']}"
                                      f" ({p['nom']} {p['prenom']})")
        if cible is not None:
            pris.add(cible["id"])
            rattrapes += 1
            if e is not None:
                conn.execute("DELETE FROM elus WHERE id = ?", (e["id"],))
                supprimes.append(e["id"])
            e = cible
        if e is not None:
            try:
                anciens = json.loads(e["mandats"]) if e["mandats"] else []
            except json.JSONDecodeError:
                anciens = []
            mandats = [m for m in anciens if m.get("source") != "RNE"] + p["mandats"]
            conn.execute(
                "UPDATE elus SET sexe = COALESCE(sexe, ?),"
                " profession = COALESCE(profession, ?), mandats = ? WHERE id = ?",
                (p["sexe"], p["profession"], json.dumps(mandats, ensure_ascii=False), e["id"]))
            maj += 1
            retiree = evincees.get(cle)
            if retiree is not None and passees.get(retiree["id"]) == e["id"]:
                try:
                    siens = json.loads(retiree["mandats"]) if retiree["mandats"] else []
                except json.JSONDecodeError:
                    siens = []
                gardes = [m for m in siens if m.get("source") != "RNE"]
                if len(gardes) != len(siens):
                    conn.execute("UPDATE elus SET mandats = ? WHERE id = ?",
                                 (json.dumps(gardes, ensure_ascii=False), retiree["id"]))
                    log.info("rattrapage : mandats RNE ôtés de la fiche retirée %s, posés"
                             " sur %s (même personne, %s)", retiree["id"], e["id"],
                             CHEMIN_REDIRECTIONS_ELUS.name)
        else:
            ident = _identifiant_rne(cle)
            conn.execute(
                "INSERT INTO elus (id, nom, prenom, sexe, date_naissance, profession,"
                " mandats) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (ident, p["nom"], p["prenom"], p["sexe"], p["date_naissance"],
                 p["profession"], json.dumps(p["mandats"], ensure_ascii=False)))
            inseres += 1
    nom_liste = CHEMIN_RATTRAPAGES_VERIFIES.name
    log.info("rattrapage : %d par la liste blanche %s, %d proposé(s) par la règle"
             " hors de la liste, non appliqué(s)", rattrapes, nom_liste, len(hors_liste))
    if hors_liste:
        log.warning("rattrapage : %d rattachement(s) que la règle ferait, NON appliqué(s)"
                    " faute de figurer dans la liste blanche %s. Vérifier chaque cas à"
                    " la main (même personne, même siège), puis ajouter au fichier une"
                    " ligne avec sa preuve pour qu'il soit appliqué au cycle suivant : %s",
                    len(hors_liste), nom_liste, " | ".join(hors_liste))
    for r in refus:
        log.warning("liste blanche %s : ligne refusée, %s", nom_liste, r)
    mortes = sorted(set(liste_blanche) - utilisees)
    if mortes:
        log.warning("liste blanche %s : %d ligne(s) sans effet ce cycle (personne absente"
                    " du RNE, sans mandat de député ou de sénateur, ou refusée). Vérifier,"
                    " puis retirer ou corriger : %s", nom_liste, len(mortes),
                    " | ".join(f"{c} -> {liste_blanche[c]}" for c in mortes))
    _controler_volume_supprimees(supprimes, len(cibles))
    return inseres, maj, rattrapes


def controler_collisions_de_cle(conn) -> list[dict]:
    """Compte les clés d'état civil portées par PLUS D'UNE ligne de `elus`.

    POURQUOI CE COMPTEUR-LÀ, ET PAS UN AUTRE. `upsert_elus` indexe les fiches
    déjà en base par `(nom, prénom, date de naissance)` normalisés avec un
    `setdefault` : quand deux lignes portent la même clé, la PREMIÈRE rencontrée
    gagne, et l'ordre de rencontre est celui que SQLite choisit — une propriété
    du PLAN d'exécution, pas des données. Si la gagnante n'est pas une fiche
    `rne-*`, la branche `if e is None or e["id"].startswith("rne-")` n'est jamais
    prise : aucun rattrapage, aucun `DELETE`, et le doublon `rne-*` continue
    d'être servi indéfiniment, figé sur ses mandats du jour de la convergence.

    DANS CE PIPELINE, C'EST UN NON-ÉVÉNEMENT : rien n'est inséré, ni complété,
    ni rattrapé, ni supprimé, donc aucun de ses compteurs ne bouge. Ni
    `rattrapes`, ni la liste `supprimes` — qui n'en est qu'un sous-ensemble
    strict — ne peuvent le voir. Le seul état observable est le nombre de clés
    portées par plus d'une ligne : c'est ce qui est compté ici.

    🛑 EN REVANCHE, « PERSONNE D'AUTRE NE PEUT LE VOIR » SERAIT FAUX, ET CE
    CONTRÔLE A FAILLI ÊTRE ÉCRIT SUR CE MOTIF-LÀ. Une réfutation adversariale
    l'a cassé le 28/08/2026, mesures à l'appui. `ingest_hatvp_declarations`
    (P15), que le `Makefile` lance APRÈS celui-ci dans le même cycle, indexe les
    fiches sur la MÊME clé et se défend déjà : il écarte les clés partagées et
    il AVERTIT. Rejoué sur la base servie avec la convergence simulée de la
    seule paire armée connue : son index passe de 1 039 à 1 037, la fiche
    devient injoignable, ses 2 déclarations toujours publiées basculent en
    « perte de rattachement » — et P15 LÈVE, donc `make ingest` échoue et
    `ft-deploy` gèle la publication. La convergence n'est pas invisible : sur ce
    cas-là, elle CASSE le cycle.

    CE QUE CE CONTRÔLE APPORTE MALGRÉ TOUT, et qui est sa vraie justification :
      · P15 n'indexe que les fiches à mandat `depute`/`senateur`/`president_*`
        — 1 039 lignes le 28/08/2026 sur 36 003. Les ~35 000 autres (maires,
        exécutifs locaux) sont hors de sa vue ; elles sont dans celle-ci ;
      · quand la personne en collision ne porte aucune déclaration publiée, P15
        se contente d'un avertissement et le cycle passe ;
      · P15 parle de SON index, jamais de `elus` : il ne nomme ni les
        identifiants, ni celui que le `setdefault` retiendra ;
      · il arrive plus tard dans le cycle, et ce contrôle-ci tire plus tôt ;
      · le compte part au journal CHAQUE nuit, zéro compris.

    IL AVERTIT, IL NE LÈVE JAMAIS, ET IL NE CORRIGE RIEN. `ft-deploy` est en
    tout-ou-rien : une levée gèlerait la publication entière du site pour un
    défaut qui n'altère aucune donnée servie le jour même. Et trancher entre
    deux fiches est une décision d'identité, pas une opération de pipeline — la
    seule paire connue à porter ce risque est laissée volontairement non
    appariée par `deploy/redirections-elus.tsv`, au motif que l'identité y serait
    une INFÉRENCE et non une source d'état civil. Ce qu'il faut est de VOIR la
    convergence si elle survient, surtout pas de la provoquer.

    LA REQUÊTE EST CELLE, EXACTE, DE `upsert_elus` (`REQUETE_ETAT_CIVIL`) — voir
    le commentaire de la constante pour ce que cette précaution couvre vraiment,
    et pour ce qu'une première rédaction lui faisait dire de trop.

    Retourne une entrée par clé en collision : `cle`, `ids` dans l'ordre de
    balayage, et `retenu` — l'identifiant que le `setdefault` conserverait. La
    liste vide est le cas nominal, et le compte part au journal À CHAQUE CYCLE,
    y compris quand il vaut zéro : un contrôle muet au vert est indiscernable
    d'un contrôle débranché.
    """
    par_cle: dict[tuple, list[str]] = {}
    for r in conn.execute(REQUETE_ETAT_CIVIL):
        cle = (normaliser_texte(r["nom"]), normaliser_texte(r["prenom"]),
               (r["date_naissance"] or "").strip())
        par_cle.setdefault(cle, []).append(r["id"])

    collisions = [{"cle": cle, "ids": ids, "retenu": ids[0]}
                  for cle, ids in par_cle.items() if len(ids) > 1]
    for c in collisions:
        ignorees = c["ids"][1:]
        log.warning("collision de clé d'état civil : %d lignes de elus portent"
                    " (%s | %s | %s) — retenue par le balayage : %s ;"
                    " ignorée(s) : %s",
                    len(c["ids"]), *c["cle"], c["retenu"], " ".join(ignorees))
        doublons_rne = [i for i in ignorees if i.startswith("rne-")]
        if doublons_rne and not c["retenu"].startswith("rne-"):
            log.warning("collision de clé : la fiche retenue %s n'est PAS une"
                        " fiche rne-*, donc la branche de rattrapage ne sera pas"
                        " prise et le ou les doublons %s ne seront plus jamais"
                        " purgés", c["retenu"], " ".join(doublons_rne))
    return collisions


# Nature du mandat déclaré à la HATVP (type_mandat) → types de mandat de la
# fiche (`elus.mandats`) qui le corroborent quand la HATVP ne publie pas de
# département (régions, EPCI sans département…).
NATURES_HATVP = {
    "commune": {"maire"},
    "departement": {"president_conseil_departemental"},
    "region": {"president_conseil_regional"},
    "epci": {"president_epci"},
    "depute": {"depute"},
    "senateur": {"senateur"},
}


def index_mandats_locaux(rne: dict[str, list[dict]]) -> dict[tuple, set]:
    """(nom, prénom, date de naissance) normalisés → {(nature HATVP, dép.)}
    des mandats RNE qu'une fiche n'enregistre pas : conseiller départemental
    (« departement »), régional (« region », département = section),
    communautaire (« epci »), et « ctsp » pour les deux premiers quand le RNE
    les rattache à une collectivité à statut particulier.

    C'est la clé d'état civil du projet, date de naissance comprise : elle
    permet de dire qu'un maire est AUSSI vice-président de son EPCI ou
    conseiller régional — ce que la HATVP déclare souvent sans département —
    sans rien déduire du seul nom.
    """
    index: dict[tuple, set] = defaultdict(set)
    for cle_rne, nature in (("cd", "departement"), ("cr", "region"), ("epci", "epci")):
        for r in rne.get(cle_rne, []):
            cle = _cle_personne(r)
            if not cle[2]:
                continue
            if nature == "region":
                dep = normaliser_departement(r.get("Code de la section départementale"))
            else:
                dep = _dep_rne(r)
            index[cle].add((nature, dep))
            if nature != "epci" and (r.get("Code de la collectivité à statut particulier")
                                     or "").strip():
                index[cle].add(("ctsp", dep))
    return index


def dossier_corrobore_fiche(dossier: dict, mandats: list[dict],
                            locaux: set | frozenset = frozenset()) -> bool:
    """Un dossier HATVP désigne-t-il la personne de cette fiche, au-delà du
    seul nom+prénom ?

    Oui si un mandat de la fiche concorde : même chambre pour un dossier de
    député ou de sénateur (la circonscription des Français de l'étranger
    s'écrit « 99 » à la HATVP, « ZZ » au RNE, en toutes lettres à l'AN) ;
    sinon même département normalisé quand la HATVP en publie un ; sinon,
    faute de département, même nature de mandat (NATURES_HATVP).

    `locaux` : mandats RNE de la MÊME personne (clé nom, prénom, date de
    naissance, voir index_mandats_locaux) que la fiche n'enregistre pas. Ils
    concordent de la même façon — même département si la HATVP en publie un,
    même nature sinon. Mesuré le 15/10/2026 sur un échantillon de 15 écartés
    sans eux : 14 désignaient vraisemblablement la bonne personne (maire de
    Trélivan, vice-présidente de Dinan Agglomération…).

    Faute de département, la nature suffit : le NOM de l'intercommunalité ou
    de la région n'est pas comparé, et c'est mesuré. Le 15/10/2026, sur une
    copie de l'ingestion du jour (P9 et P7 rejoués), exiger en plus que les
    mots du libellé RNE (`Libellé de l'EPCI`, `Libellé de la région`, formes
    juridiques retirées) figurent dans la `qualite` HATVP faisait passer les
    flags de 3 572 à 3 523 : 444 reposent sur la seule nature, 49 seraient
    perdus, tous des EPCI (aucune région). 15 des 49, relus : 14 désignent la
    même intercommunalité écrite autrement (« Ca Du Grand Avignon (Ga) » /
    « communauté d'agglomération du Grand Avignon », « Cc Pays Pontchateau St
    Gildas Des Bois », « Ca Civis » / « communauté intercommunale des Villes
    Solidaires »…). Le rapprochement par nom ferait perdre de vrais liens :
    il n'est pas appliqué. Le quinzième (rne-21dc0877411d1a6f : RNE
    « Cc De L'Ouest Guyanais », HATVP « Territoire de la Côte Ouest », à La
    Réunion) a été relu le 15/10/2026 : ce n'est pas un homonyme. Le RNE ne
    connaît qu'un Jonathan ABIENSO (maire de Maripasoula, 1er vice-président
    de la CC de l'Ouest Guyanais), et la CA du TCO y compte quinze
    vice-présidents, exactement les quinze que la page HATVP liste à côté de
    lui : aucun siège du TCO ne lui revient. C'est l'organe que la HATVP
    écrit qui paraît erroné (à signaler au producteur), pas la personne ; le
    lien est conservé. Une vérification du département de l'EPCI ne
    l'aurait pas tranché : la HATVP n'en publie pas pour ce dossier, et le
    déduire du nom de l'organe est le rapprochement par nom écarté ci-dessus.

    Le département d'un mandat AN-P9 ou SENAT-P9 est un NOM (« Rhône ») :
    c'est son `code_departement`, écrit par P9 depuis la source officielle de
    chaque chambre, qui est comparé au code HATVP. Sans lui, une députée du
    Rhône déclarant un mandat municipal dans le 69 n'était pas reconnue
    (PA794910, relecture du 15/10/2026).
    """
    tm = dossier.get("type_mandat") or ""
    dep = normaliser_departement(dossier.get("departement"))
    for m in mandats:
        if not isinstance(m, dict):
            continue
        if tm in ("depute", "senateur") and m.get("type") == tm:
            return True
        if dep:
            if dep == normaliser_departement(
                    m.get("code_departement") or m.get("departement")):
                return True
        elif m.get("type") in NATURES_HATVP.get(tm, ()):
            return True
    for nature, dep_local in locaux:
        if dep:
            if dep == dep_local:
                return True
        elif nature == tm:
            return True
    return False


def croiser_hatvp_flag(conn, dossiers: list[dict],
                       locaux: dict[tuple, set] | None = None,
                       passees: dict[str, str] | None = None) -> tuple[int, int]:
    """hatvp_flag + hatvp_url quand la personne est UNE des deux côtés ET
    qu'un de ses dossiers concorde avec un mandat de la fiche.

    Homonymie (plusieurs personnes HATVP ou plusieurs élus pour le même
    nom+prénom) = pas de flag. Nom+prénom uniques ne suffisent pas : un
    patronyme unique dans `elus` peut désigner un autre élu que le déclarant
    (constat du 15/10/2026 : LEROY Gilles, maire dans l'Aisne, recevait la
    fiche HATVP d'un vice-président du conseil départemental de
    Maine-et-Loire). Il faut en plus `dossier_corrobore_fiche` ; sinon on
    renonce, et le cas est compté.

    Le flag et le lien sont RECALCULÉS à chaque cycle (remis à 0 / NULL
    d'abord) : seul ce pipeline les écrit, et un flag posé à tort par un
    cycle précédent ne doit pas survivre au correctif. Tout est dans la
    transaction de `ecrire()`.

    Le député devenu sénateur n'est pas un homonyme : sa fiche PA retirée et
    sa fiche SEN portent le même nom et le même prénom. Quand `passees`
    ({PA : SEN}, par défaut `deploy/redirections-elus.tsv`) les donne pour la
    même personne et que les deux fiches ont la même date de naissance, la PA
    est écartée des candidats et la SEN, seule publiée, reçoit le lien. Avant
    le 21/11/2026, ces 8 sénateurs n'avaient aucun lien HATVP.

    Retour : (flags posés, appariements nom+prénom uniques écartés faute de
    concordance).
    """
    if passees is None:
        passees = charger_fiches_passees_au_senat()
    colonnes = {r["name"] for r in conn.execute("PRAGMA table_info(elus)")}
    if "hatvp_url" not in colonnes:
        conn.execute("ALTER TABLE elus ADD COLUMN hatvp_url TEXT")
    conn.execute("UPDATE elus SET hatvp_flag = 0, hatvp_url = NULL"
                 " WHERE hatvp_flag <> 0 OR hatvp_url IS NOT NULL")

    hatvp_par_nom: dict[tuple, dict] = defaultdict(dict)   # nom → {classement: url}
    dossiers_par_classement: dict[str, list[dict]] = defaultdict(list)
    for d in dossiers:
        cle = (normaliser_texte(d["nom"]), normaliser_texte(d["prenom"]))
        hatvp_par_nom[cle].setdefault(d["classement"],
                                      (URL_HATVP_SITE + d["url_dossier"])
                                      if d["url_dossier"] else URL_HATVP_LISTE)
        dossiers_par_classement[d["classement"]].append(d)
    elus_par_nom: dict[tuple, list[tuple]] = defaultdict(list)
    for r in conn.execute("SELECT id, nom, prenom, date_naissance, mandats FROM elus"):
        elus_par_nom[(normaliser_texte(r["nom"]), normaliser_texte(r["prenom"]))].append(
            (r["id"], r["mandats"], (r["date_naissance"] or "").strip()))
    locaux = locaux or {}

    n = ecartes = 0
    departages: list[str] = []
    for cle, classements in hatvp_par_nom.items():
        if len(classements) != 1:
            continue
        candidats = elus_par_nom.get(cle, [])
        retirees: list[str] = []
        if len(candidats) > 1:
            restants = departager_fiches_passees_au_senat(
                (c[0] for c in candidats), passees)
            naissances = {c[0]: c[2] for c in candidats}
            # Même date de naissance, non vide, des deux côtés : sinon ce n'est
            # pas la paire que la table décrit, et l'on ne départage rien.
            if all(naissances[i] and naissances[i] == naissances[passees[i]]
                   for i in naissances.keys() - restants):
                retirees = sorted(naissances.keys() - restants)
                candidats = [c for c in candidats if c[0] in restants]
        if len(candidats) != 1:
            continue
        ident, brut, naissance = candidats[0]
        try:
            mandats = json.loads(brut) if brut else []
        except json.JSONDecodeError:
            mandats = []
        classement, url = next(iter(classements.items()))
        siens = locaux.get(cle + (naissance,), frozenset()) if naissance else frozenset()
        if not any(dossier_corrobore_fiche(d, mandats, siens)
                   for d in dossiers_par_classement[classement]):
            ecartes += 1
            continue
        conn.execute("UPDATE elus SET hatvp_flag = 1, hatvp_url = ? WHERE id = ?",
                     (url, ident))
        n += 1
        if retirees:
            departages.append(f"{' + '.join(retirees)} -> {ident} ({url})")
    log.info("hatvp_flag : %d lien(s) posé(s) sur la fiche de sénateur d'un député"
             " passé au Sénat, fiche de député retirée écartée (%s) : %s",
             len(departages), CHEMIN_REDIRECTIONS_ELUS.name,
             " | ".join(departages) or "aucun")
    return n, ecartes


# ---------------------------------------------------------------------------
# Conseillers municipaux — agrégats seulement (jamais nominatif : ~511 000 lignes)
# ---------------------------------------------------------------------------


def agreger_conseillers_municipaux(chemin: str | Path,
                                   aujourd_hui: date) -> tuple[list[tuple], int]:
    """(code_dep, libellé, nb, femmes, hommes, âge moyen) par département."""
    stats: dict[str, dict] = {}
    total = 0
    with open(chemin, encoding="utf-8-sig", newline="") as f:
        lecteur = csv.DictReader(f, delimiter=";")
        requises = {"Code du département", "Libellé du département", "Code sexe",
                    "Date de naissance"}
        if not requises <= set(lecteur.fieldnames or []):
            raise ValueError(f"{chemin} : colonnes attendues absentes ({requises})")
        for r in lecteur:
            total += 1
            dep = (r["Code du département"] or "").strip() or \
                (r.get("Code de la collectivité à statut particulier") or "").strip()
            s = stats.setdefault(dep, {"libelle": (r["Libellé du département"] or "").strip()
                                       or (r.get("Libellé de la collectivité à statut particulier") or "").strip(),
                                       "nb": 0, "f": 0, "h": 0,
                                       "somme_age": 0.0, "nb_age": 0})
            s["nb"] += 1
            sexe = (r["Code sexe"] or "").strip().upper()
            if sexe == "F":
                s["f"] += 1
            elif sexe == "M":
                s["h"] += 1
            naissance = _parser_date_iso(r["Date de naissance"])
            if naissance:
                s["somme_age"] += (aujourd_hui - naissance).days / 365.2425
                s["nb_age"] += 1
    lignes = [(dep, s["libelle"], s["nb"], s["f"], s["h"],
               round(s["somme_age"] / s["nb_age"], 1) if s["nb_age"] else None)
              for dep, s in sorted(stats.items())]
    return lignes, total


# ---------------------------------------------------------------------------
# Téléchargements
# ---------------------------------------------------------------------------


def date_derniere_modification(session, url: str) -> str | None:
    """Date (ISO) du Last-Modified HTTP, via HEAD puis GET en secours."""
    try:
        r = session.head(url, timeout=60, allow_redirects=True)
        lm = r.headers.get("Last-Modified")
        if not lm:
            with session.get(url, stream=True, timeout=60) as g:
                lm = g.headers.get("Last-Modified")
        return parsedate_to_datetime(lm).date().isoformat() if lm else None
    except (ValueError, TypeError, OSError):
        return None


def resoudre_ressources_rne(session) -> dict[str, dict]:
    """Re-résout les URLs static.data.gouv.fr (horodatées) via l'API data.gouv.

    Retourne {clé: {"url": ..., "last_modified": "YYYY-MM-DD", "titre": ...}}.
    """
    r = session.get(URL_RNE_API, timeout=120)
    r.raise_for_status()
    ressources = r.json().get("resources", [])
    trouvees: dict[str, dict] = {}
    for res in ressources:
        titre = normaliser_texte(res.get("title", ""))
        for motif, cle in RESSOURCES_RNE.items():
            if motif in titre and cle not in trouvees:
                lm = (res.get("last_modified") or "")[:10]
                trouvees[cle] = {"url": res["url"], "last_modified": lm,
                                 "titre": res.get("title", "")}
    manquantes = set(RESSOURCES_RNE.values()) - set(trouvees)
    if manquantes:
        raise ValueError(f"API data.gouv RNE : ressources introuvables {sorted(manquantes)}")
    return trouvees


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def ecrire(conn, dossiers: list[dict], rne: dict, chemins: dict,
           aujourd_hui: date, date_hatvp: str, date_rne: str) -> dict:
    """Écrit TOUT le cycle P7, dans UNE transaction, sans la valider.

    POURQUOI CETTE FONCTION EXISTE — elle a été extraite de `main()` le
    26/08/2026, et ce n'est pas de la cosmétique. Tant que ces lignes vivaient
    au milieu de `main()`, qui télécharge, aucun test ne pouvait les exécuter :
    la promesse d'atomicité n'était éprouvée que sur une RÉPLIQUE écrite à la
    main dans le fichier de test, et deux revues adversariales ont montré la
    même faille — un `conn.commit()` d'une seule ligne ajouté ici restaurait
    intégralement le défaut d'origine en laissant les tests verts. C'est
    `test_un_echec_apres_le_drop_laisse_la_base_intacte` qui tient la promesse,
    et il ne la tient que parce qu'il appelle CETTE fonction.

    Ce que `ecrire()` ne fait pas : valider. Elle laisse la transaction
    ouverte, comme `ecrire()` de `ingest_hatvp_declarations.py`. C'est `main()`
    qui écrit `meta_sources` puis valide — et `db.upsert_meta` validant
    lui-même, la transaction se referme en pratique au premier des deux appels.
    Tout ce qui peut détruire des données (les trois `DROP`, les trois
    remplissages, `upsert_elus`, le parsing du CSV RNE, le `DELETE FROM
    alertes`) est en amont de ce point ; ce qui suit est l'écriture de deux
    lignes de `meta_sources`, dont l'échec laisse la base complète et à jour
    avec une date de source non rafraîchie. Ne pas « corriger » `upsert_meta`
    au passage : il est partagé par les 31 pipelines.

    Retourne de quoi renseigner `meta_sources` sans relire la base.
    """
    # --- Schéma et tables HATVP ----------------------------------------
    appliquer_schema(conn)
    conn.executemany(
        "INSERT INTO hatvp_declarations (civilite, prenom, nom, classement,"
        " type_mandat, qualite, type_document, departement, date_publication,"
        " date_depot, statut_publication, nom_fichier, url_dossier, url_fiche,"
        " open_data, id_origine, url_photo)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [(d["civilite"], d["prenom"], d["nom"], d["classement"], d["type_mandat"],
          d["qualite"], d["type_document"], d["departement"],
          d["date_publication"] or None, d["date_depot"] or None,
          d["statut_publication"], d["nom_fichier"] or None, d["url_dossier"] or None,
          (URL_HATVP_SITE + d["url_dossier"]) if d["url_dossier"] else None,
          d["open_data"] or None, d["id_origine"] or None, d["url_photo"] or None)
         for d in dossiers])
    conn.executemany("INSERT INTO hatvp_agregats (categorie, cle, nb) VALUES (?, ?, ?)",
                     agreger_hatvp(dossiers, aujourd_hui))

    # --- elus : upsert prudent + croisement HATVP ----------------------
    personnes = preparer_personnes(rne)
    inseres, maj, rattrapes = upsert_elus(conn, personnes)
    flags, flags_ecartes = croiser_hatvp_flag(conn, dossiers,
                                              index_mandats_locaux(rne))
    collisions = controler_collisions_de_cle(conn)
    log.info("elus : %d insérés, %d complétés (fusion mandats), %d rattrapés sur"
             " une fiche AN/Sénat, %d hatvp_flag posés, %d appariement(s)"
             " nom+prénom écarté(s) faute de mandat concordant, %d collision(s)"
             " de clé", inseres, maj, rattrapes, flags, flags_ecartes,
             len(collisions))

    # --- Conseillers municipaux : agrégats seulement -------------------
    lignes_cm, total_cm = agreger_conseillers_municipaux(chemins["cm"], aujourd_hui)
    conn.executemany(
        "INSERT INTO rne_cm_agregats (code_departement, libelle_departement,"
        " nb_conseillers, nb_femmes, nb_hommes, age_moyen) VALUES (?, ?, ?, ?, ?, ?)",
        lignes_cm)
    log.info("conseillers municipaux : %d lignes agrégées en %d départements",
             total_cm, len(lignes_cm))

    # --- Alerte A1 ------------------------------------------------------
    # Le délai de 2 mois se juge à la date du fichier HATVP lu, pas au jour
    # du cycle : un dossier déposé entre la date du fichier et le cycle
    # serait sinon compté « En cours » alors que le fichier ne peut pas le
    # savoir. `aujourd_hui` reste la date de calcul des lignes.
    date_lecture_a1 = date.fromisoformat(date_hatvp)
    index = construire_index_rne(rne)
    perimes = types_rne_anterieurs(conn, rne)
    nominatives, en_cours, stats = calculer_a1(dossiers, index, date_lecture_a1,
                                               frozenset(perimes))
    lignes_alertes = construire_alertes(nominatives, en_cours, aujourd_hui,
                                        date_hatvp, date_rne)
    ecrire_alertes(conn, lignes_alertes, aujourd_hui)
    log.info("A1 : %d constats nominatifs « non déposée », %d dossiers « En cours »"
             " au délai légal écoulé (agrégés en %d alertes) ; tri : %s",
             len(nominatives), len(en_cours),
             len(lignes_alertes) - len(nominatives), dict(stats))

    return {"total_cm": total_cm, "nb_alertes": len(lignes_alertes)}


def date_s14_sans_last_modified(conn: sqlite3.Connection, dossiers: list[dict],
                                aujourd_hui: date) -> str:
    """Date de donnée de S14 quand la HATVP n'envoie pas de Last-Modified.

    Jamais la date du jour : S14 paraîtrait fraîche à chaque cycle, fichier
    régénéré ou non. Même règle que S15 (`date_donnees_sans_last_modified`) :
    la plus haute des bornes basses que l'on sait vraies, la date du cycle
    précédent et le dépôt ou la publication la plus récente du fichier. Au
    pire la source paraît plus âgée qu'elle n'est, jamais plus fraîche. Les
    dates postérieures au jour sont ignorées (coquilles et publications
    programmées existent dans le fichier, voir `controler_dates_hatvp`).
    Garder cette date plutôt que lever : une levée arrêterait les pipelines
    en aval et tout le rafraîchissement du site pour un en-tête HTTP absent.
    Sans aucune borne (base neuve et en-tête absent), il n'y a rien de vrai à
    écrire : lève.
    """
    ligne = conn.execute(
        "SELECT date_donnees FROM meta_sources WHERE source_id = 'S14'"
    ).fetchone()
    precedente = ligne[0] if ligne else None
    contenu = [j for d in dossiers for c in ("date_depot", "date_publication")
               if (j := _parser_date_iso(d.get(c))) and j <= aujourd_hui]
    retenue = date_donnees_sans_last_modified(
        precedente, max(contenu).isoformat() if contenu else None)
    if not retenue:
        raise RuntimeError(
            "liste.csv : Last-Modified indisponible et aucune date connue "
            "(ni cycle précédent ni dépôt daté) : pas de date de donnée vraie")
    log.warning("liste.csv : Last-Modified indisponible, date de donnée gardée "
                "au %s (cycle précédent %s)", retenue, precedente)
    return retenue


def main() -> int:
    aujourd_hui = date.today()
    session = session_http()
    conn = None
    try:
        conn = db.init_db()
        # --- S14 : HATVP liste.csv (hebdomadaire) --------------------------
        chemin_liste = telecharger(URL_HATVP_LISTE, REP_RAW / "liste.csv",
                                   max_age_heures=6, session=session)
        date_hatvp = date_derniere_modification(session, URL_HATVP_LISTE)
        dossiers = parser_liste_hatvp(chemin_liste)
        if not date_hatvp:
            date_hatvp = date_s14_sans_last_modified(conn, dossiers, aujourd_hui)
        if len(dossiers) < 10_000:
            raise ValueError(f"liste.csv : {len(dossiers)} lignes, seuil de plausibilité "
                             "(10 000) non atteint — source suspecte, abandon")
        dossiers = dedoublonner_hatvp(dossiers)
        controler_dates_hatvp(dossiers, aujourd_hui)
        log.info("HATVP : %d dossiers déclaratifs (données du %s)", len(dossiers), date_hatvp)

        # --- S17 : RNE (trimestriel, URLs re-résolues) ---------------------
        ressources = resoudre_ressources_rne(session)
        date_rne = max(r["last_modified"] for r in ressources.values())
        chemins = {cle: telecharger(r["url"], REP_RAW / f"rne_{cle}.csv",
                                    max_age_heures=24, session=session)
                   for cle, r in ressources.items()}
        rne = {
            "deputes": lire_rne(chemins["deputes"], _COLS_BASE),
            "senateurs": lire_rne(chemins["senateurs"], _COLS_BASE),
            "maires": lire_rne(chemins["maires"], _COLS_BASE + ("Date de début de la fonction",)),
            "cd": lire_rne(chemins["cd"], _COLS_BASE + ("Libellé de la fonction",)),
            "cr": lire_rne(chemins["cr"], _COLS_BASE + ("Libellé de la fonction",)),
            "epci": lire_rne(chemins["epci"], _COLS_BASE + ("Libellé de la fonction",)),
        }
        if len(rne["deputes"]) < 400 or len(rne["senateurs"]) < 250 or len(rne["maires"]) < 30_000:
            raise ValueError("RNE : volumétrie invraisemblable (députés %d, sénateurs %d,"
                             " maires %d) — abandon" % (len(rne["deputes"]),
                                                        len(rne["senateurs"]), len(rne["maires"])))
        log.info("RNE : %d députés, %d sénateurs, %d maires, %d cons. dép., %d cons. rég.,"
                 " %d cons. comm. (données du %s)", len(rne["deputes"]), len(rne["senateurs"]),
                 len(rne["maires"]), len(rne["cd"]), len(rne["cr"]), len(rne["epci"]), date_rne)

        resume = ecrire(conn, dossiers, rne, chemins, aujourd_hui,
                        date_hatvp, date_rne)
        total_cm = resume["total_cm"]

        # --- meta_sources ----------------------------------------------------
        nb_mandats_ingeres = (len(rne["deputes"]) + len(rne["senateurs"]) + len(rne["maires"])
                              + sum(1 for r in rne["cd"] if est_president_cd(r))
                              + sum(1 for r in rne["cr"] if est_president_cr(r))
                              + sum(1 for r in rne["epci"] if est_president_epci(r)))
        statuts = Counter(d["statut_publication"] for d in dossiers)
        db.upsert_meta(
            conn, source_id="S14",
            nom="HATVP : liste des déclarations publiées (liste.csv)",
            url=URL_HATVP_LISTE, licence="Licence Ouverte (version non vérifiée)",
            frequence="hebdomadaire", date_donnees=date_hatvp, lignes=len(dossiers),
            notes=f"statuts : {statuts[STATUT_EN_COURS]} « En cours », "
                  f"{statuts[STATUT_NON_DEPOSEE]} « Déclaration non déposée ». "
                  "Décompte recalculé à chaque cycle (méthode : "
                  "https://francetransparence.fr/comprendre/#elus)")
        db.upsert_meta(
            conn, source_id="S17",
            nom="Répertoire national des élus (RNE, ministère de l'Intérieur)",
            url=URL_RNE_PAGE, licence="Licence Ouverte 2.0",
            frequence="trimestrielle", date_donnees=date_rne, lignes=nb_mandats_ingeres,
            notes=f"mandats ingérés : députés, sénateurs, maires, présidents "
                  f"d'exécutifs, {total_cm} conseillers municipaux agrégés par "
                  "département, non ingérés nominativement")
        conn.commit()
        log.info("P7 terminé : %d dossiers HATVP, %d mandats RNE, %d alertes A1",
                 len(dossiers), nb_mandats_ingeres, resume["nb_alertes"])
        return 0
    except Exception:
        if conn is not None:
            conn.rollback()
        # Ce message a longtemps dit « le prochain run réussi remet toutes les
        # tables d'aplomb : remplacement complet idempotent ». Deux défauts,
        # relevés par une revue adversariale le 26/08/2026 : il laissait croire
        # que la base était cassée — ce qui était vrai, et ne l'est plus — et
        # « toutes les tables » était faux de toute façon, `elus` étant
        # complétée et jamais écrasée (en-tête du module) et `hatvp_flag`
        # jamais remis à 0. Ce qui tient la promesse ci-dessous est le
        # `BEGIN IMMEDIATE` de `appliquer_schema()` et les tests qui
        # l'éprouvent, jamais cette phrase.
        log.exception(
            "P7 en échec. La base n'est PAS modifiée : l'écriture est atomique, "
            "le cycle précédent reste servi entier. Les tables remplacées "
            "(hatvp_declarations, hatvp_agregats, rne_cm_agregats, et les "
            "alertes A1) gardent leur contenu de la veille ; `elus` est "
            "complétée, et les seules lignes qu'elle perd sont les fiches "
            "`rne-*` rattrapées sur une fiche AN/Sénat — ce `DELETE` tombe "
            "dans la même transaction, il est donc annulé lui aussi")
        return 1
    finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    sys.exit(main())

"""P7 — Intégrité des élus : HATVP `liste.csv` (S14) × Répertoire national des élus (S17).

Modules UI alimentés : « Élus & Institutions » et « Alertes ».

Tables produites (remplacement complet, idempotent) :
- hatvp_declarations : 1 ligne = 1 dossier déclaratif HATVP (12 930 au 14/08/2026).
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
  A1_hatvp_retard_presume). Colonnes : id, type, gravite, titre, detail, regle,
  base_legale, source_url, date_calcul.

Table noyau complétée (jamais écrasée) :
- elus : UPSERT prudent par (nom, prénom, date de naissance) normalisés —
  députés (577), sénateurs (348), maires (~34 800), présidents d'exécutifs
  (conseils départementaux, conseils régionaux, EPCI). Les colonnes remplies par
  d'autres pipelines (uid_an, matricule_senat) ne sont jamais touchées ; les
  mandats sont fusionnés dans le JSON `mandats` (seules les entrées
  "source": "RNE" sont remplacées). Croisement HATVP : hatvp_flag passe à 1
  (jamais remis à 0, pour ne pas écraser un autre pipeline) et hatvp_url
  (colonne ajoutée par ce pipeline si absente) reçoit le lien de la fiche —
  uniquement quand le couple nom+prénom est unique des deux côtés (homonymie
  non tranchée = pas de flag).

Alerte A1 — règle révisée de docs/SOURCES.md §4 (appliquée à la lettre) :
- Nominatif RÉSERVÉ aux statuts natifs « Déclaration non déposée » (constat
  officiel HATVP, 4 cas au 14/08/2026) → 1 alerte nominative par dossier.
- Retard PRÉSUMÉ (libellé « présumé » obligatoire) : statut « En cours »
  ET date de début de la fonction (RNE) + 60 jours dépassée. Garde-fous :
  (1) mandats EPCI exclus (délai courant à la transmission de la délégation en
  préfecture, date absente de l'open data) ; (2) jointure nom+prénom+département
  normalisés (accents/casse/tirets), homonyme non tranché = non-alerte ;
  (3) restitution en AGRÉGATS par type de mandat, jamais nominative ;
  (4) seuls les documents initiaux (di, dsp, dia) sont testés — le délai légal
  des modificatives et des fins de mandat court sur d'autres faits générateurs ;
  (5) périmètre apparié = populations RNE ingérées (députés, sénateurs, maires,
  présidents de conseils départementaux/régionaux) avec filtre sur la qualité
  déclarée ; le reste (adjoints, vice-présidents, ctsp, gouvernement…) = non
  apparié = non-alerte ; (6) réserve affichée : RNE trimestriel (11/08/2026),
  dates de fonction possiblement périmées jusqu'à ~3 mois.

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
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import date, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path

from pipelines import db
from pipelines.common import RAW_DIR, obtenir_logger, session_http, telecharger

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
TYPE_ALERTE_RETARD = "A1_hatvp_retard_presume"
TYPES_ALERTES_P7 = (TYPE_ALERTE_NON_DEPOSEE, TYPE_ALERTE_RETARD)

BASE_LEGALE_A1 = (
    "Loi n° 2013-907 du 11 octobre 2013 (art. 4 et 11) ; art. LO 135-1 du code "
    "électoral : dépôt dans les 2 mois suivant l'entrée en fonction. Sanctions "
    "(art. 26) : 3 ans d'emprisonnement, 45 000 € d'amende, inéligibilité."
)

REGLE_A1_RETARD = (
    "Retard PRÉSUMÉ : statut natif « En cours » (déclaration attendue, non "
    "déposée) ET date de début de la fonction (RNE du {date_rne}) + 60 jours "
    "dépassée. Garde-fous appliqués : mandats EPCI exclus (délai courant à la "
    "transmission de la délégation en préfecture, date absente de l'open data) ; "
    "jointure nom+prénom+département normalisés, homonyme non tranché = "
    "non-alerte ; documents initiaux seulement (di, dsp, dia) ; qualité "
    "déclarée filtrée sur la population RNE appariée (maires, présidents "
    "d'exécutifs, parlementaires) ; agrégat non nominatif. Réserve : RNE "
    "trimestriel, dates de fonction possiblement périmées jusqu'à ~3 mois."
)

REGLE_A1_NON_DEPOSEE = (
    "Constat officiel HATVP repris tel quel : statut natif « Déclaration non "
    "déposée » dans liste.csv. Seuls cas nominatifs de l'alerte A1 (les retards "
    "présumés restent agrégés)."
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


def calculer_a1(dossiers: list[dict], index_rne: dict[str, dict],
                aujourd_hui: date) -> tuple[list[dict], list[dict], Counter]:
    """Applique la règle A1. Retourne (nominatives, retards_presumes, stats).

    - nominatives : dossiers au statut natif « Déclaration non déposée »
      (seuls cas nominatifs autorisés) ;
    - retards_presumes : dossiers « En cours » appariés à un élu RNE unique
      dont la date de début de fonction + 60 jours est dépassée (EPCI exclus,
      homonymes non tranchés exclus, documents initiaux seulement) ;
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
        if debut + timedelta(days=60) < aujourd_hui:
            stats["retard_presume"] += 1
            retards.append(d)
        else:
            stats["delai_non_ecoule"] += 1
    return nominatives, retards, stats


def construire_alertes(nominatives: list[dict], retards: list[dict],
                       aujourd_hui: date, date_hatvp: str, date_rne: str) -> list[tuple]:
    """Lignes prêtes pour la table alertes. Nominatif = non déposées SEULEMENT.

    `date_hatvp` / `date_rne` : dates réelles des données (ISO), citées dans
    les textes pour que les réserves restent vraies aux runs suivants.
    """
    date_calcul = aujourd_hui.isoformat()
    regle_retard = REGLE_A1_RETARD.format(date_rne=date_rne)
    lignes: list[tuple] = []
    for d in nominatives:
        slug = (d["url_dossier"].rstrip("/").rsplit("/", 1)[-1]
                or normaliser_texte(f"{d['nom']} {d['prenom']}").replace(" ", "-"))
        lignes.append((
            f"A1-ND-{slug}-{d['type_document']}",
            TYPE_ALERTE_NON_DEPOSEE,
            "haute",
            f"Déclaration non déposée (constat officiel HATVP) — "
            f"{d['prenom']} {d['nom']}, {d['qualite']}",
            f"{LIBELLES_DOC.get(d['type_document'], d['type_document'])} "
            f"(mandat « {d['type_mandat']} », département « {d['departement']} »). "
            f"Statut publié tel quel par la HATVP dans liste.csv du {date_hatvp}.",
            REGLE_A1_NON_DEPOSEE,
            BASE_LEGALE_A1,
            (URL_HATVP_SITE + d["url_dossier"]) if d["url_dossier"] else URL_HATVP_LISTE,
            date_calcul,
        ))
    par_mandat: dict[str, list[dict]] = defaultdict(list)
    for d in retards:
        par_mandat[d["type_mandat"]].append(d)
    for tm in sorted(par_mandat):
        ds = par_mandat[tm]
        personnes = len({d["classement"] for d in ds})
        lignes.append((
            f"A1-RP-{tm}",
            TYPE_ALERTE_RETARD,
            "moyenne",
            f"{len(ds)} déclaration(s) HATVP présumée(s) en retard — mandat « {tm} »",
            f"{len(ds)} dossier(s) « En cours » concernant {personnes} personne(s), "
            f"attendus depuis plus de 60 jours après l'entrée en fonction (RNE du "
            f"{date_rne}). Agrégat non nominatif : le détail individuel reste une "
            f"présomption (RNE trimestriel, démissions/délégations non visibles).",
            regle_retard,
            BASE_LEGALE_A1,
            URL_HATVP_LISTE,
            date_calcul,
        ))
    return lignes


def ecrire_alertes(conn, lignes: list[tuple]) -> None:
    """Table partagée : ne supprime QUE les types d'alerte de ce pipeline."""
    marqueurs = ",".join("?" for _ in TYPES_ALERTES_P7)
    conn.execute(f"DELETE FROM alertes WHERE type IN ({marqueurs})", TYPES_ALERTES_P7)
    conn.executemany(
        "INSERT INTO alertes (id, type, gravite, titre, detail, regle, base_legale,"
        " source_url, date_calcul) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", lignes)


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


def upsert_elus(conn, personnes: dict[tuple, dict]) -> tuple[int, int]:
    """UPSERT prudent par (nom, prénom, date de naissance) normalisés.

    Ne touche jamais uid_an / matricule_senat ; ne remplit sexe, profession,
    date_naissance que s'ils sont NULL ; remplace uniquement les mandats
    "source": "RNE" du JSON, les autres sont conservés.
    """
    existants: dict[tuple, dict] = {}
    for r in conn.execute("SELECT id, nom, prenom, date_naissance, sexe, profession,"
                          " mandats FROM elus"):
        cle = (normaliser_texte(r["nom"]), normaliser_texte(r["prenom"]),
               (r["date_naissance"] or "").strip())
        existants.setdefault(cle, dict(r))

    inseres = maj = 0
    for cle, p in personnes.items():
        if cle in existants:
            e = existants[cle]
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
        else:
            ident = "rne-" + hashlib.sha1("|".join(cle).encode()).hexdigest()[:16]
            conn.execute(
                "INSERT INTO elus (id, nom, prenom, sexe, date_naissance, profession,"
                " mandats) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (ident, p["nom"], p["prenom"], p["sexe"], p["date_naissance"],
                 p["profession"], json.dumps(p["mandats"], ensure_ascii=False)))
            inseres += 1
    return inseres, maj


def croiser_hatvp_flag(conn, dossiers: list[dict]) -> int:
    """hatvp_flag + hatvp_url quand nom+prénom est unique des deux côtés.

    Homonymie (plusieurs personnes HATVP ou plusieurs élus pour le même
    nom+prénom) = pas de flag. Ne remet jamais un flag existant à 0.
    """
    colonnes = {r["name"] for r in conn.execute("PRAGMA table_info(elus)")}
    if "hatvp_url" not in colonnes:
        conn.execute("ALTER TABLE elus ADD COLUMN hatvp_url TEXT")

    hatvp_par_nom: dict[tuple, dict] = defaultdict(dict)   # nom → {classement: url}
    for d in dossiers:
        cle = (normaliser_texte(d["nom"]), normaliser_texte(d["prenom"]))
        hatvp_par_nom[cle].setdefault(d["classement"],
                                      (URL_HATVP_SITE + d["url_dossier"])
                                      if d["url_dossier"] else URL_HATVP_LISTE)
    elus_par_nom: dict[tuple, list[str]] = defaultdict(list)
    for r in conn.execute("SELECT id, nom, prenom FROM elus"):
        elus_par_nom[(normaliser_texte(r["nom"]), normaliser_texte(r["prenom"]))].append(r["id"])

    n = 0
    for cle, classements in hatvp_par_nom.items():
        if len(classements) != 1:
            continue
        ids = elus_par_nom.get(cle, [])
        if len(ids) != 1:
            continue
        conn.execute("UPDATE elus SET hatvp_flag = 1, hatvp_url = ? WHERE id = ?",
                     (next(iter(classements.values())), ids[0]))
        n += 1
    return n


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
        if not date_hatvp:
            log.warning("liste.csv : Last-Modified indisponible, date d'ingestion utilisée")
            date_hatvp = aujourd_hui.isoformat()
        dossiers = parser_liste_hatvp(chemin_liste)
        if len(dossiers) < 10_000:
            raise ValueError(f"liste.csv : {len(dossiers)} lignes, seuil de plausibilité "
                             "(10 000) non atteint — source suspecte, abandon")
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

        # --- Schéma et tables HATVP ----------------------------------------
        conn.executescript(SCHEMA_P7)
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
        inseres, maj = upsert_elus(conn, personnes)
        flags = croiser_hatvp_flag(conn, dossiers)
        log.info("elus : %d insérés, %d complétés (fusion mandats), %d hatvp_flag posés",
                 inseres, maj, flags)

        # --- Conseillers municipaux : agrégats seulement -------------------
        lignes_cm, total_cm = agreger_conseillers_municipaux(chemins["cm"], aujourd_hui)
        conn.executemany(
            "INSERT INTO rne_cm_agregats (code_departement, libelle_departement,"
            " nb_conseillers, nb_femmes, nb_hommes, age_moyen) VALUES (?, ?, ?, ?, ?, ?)",
            lignes_cm)
        log.info("conseillers municipaux : %d lignes agrégées en %d départements",
                 total_cm, len(lignes_cm))

        # --- Alerte A1 ------------------------------------------------------
        index = construire_index_rne(rne)
        nominatives, retards, stats = calculer_a1(dossiers, index, aujourd_hui)
        lignes_alertes = construire_alertes(nominatives, retards, aujourd_hui,
                                            date_hatvp, date_rne)
        ecrire_alertes(conn, lignes_alertes)
        log.info("A1 : %d constats nominatifs « non déposée », %d retards présumés "
                 "(agrégés en %d alertes) ; tri : %s", len(nominatives), len(retards),
                 len(lignes_alertes) - len(nominatives), dict(stats))

        # --- meta_sources ----------------------------------------------------
        nb_mandats_ingeres = (len(rne["deputes"]) + len(rne["senateurs"]) + len(rne["maires"])
                              + sum(1 for r in rne["cd"] if est_president_cd(r))
                              + sum(1 for r in rne["cr"] if est_president_cr(r))
                              + sum(1 for r in rne["epci"] if est_president_epci(r)))
        statuts = Counter(d["statut_publication"] for d in dossiers)
        db.upsert_meta(
            conn, source_id="S14",
            nom="HATVP — liste des déclarations publiées (liste.csv)",
            url=URL_HATVP_LISTE, licence="Licence Ouverte Etalab",
            frequence="hebdomadaire", date_donnees=date_hatvp, lignes=len(dossiers),
            notes=f"statuts : {statuts[STATUT_EN_COURS]} « En cours », "
                  f"{statuts[STATUT_NON_DEPOSEE]} « Déclaration non déposée » ; "
                  "alerte A1 recalculée à chaque run (garde-fous SOURCES.md §4)")
        db.upsert_meta(
            conn, source_id="S17",
            nom="Répertoire national des élus (RNE, ministère de l'Intérieur)",
            url=URL_RNE_PAGE, licence="Licence Ouverte 2.0",
            frequence="trimestrielle", date_donnees=date_rne, lignes=nb_mandats_ingeres,
            notes=f"mandats ingérés dans elus : députés, sénateurs, maires, présidents "
                  f"d'exécutifs ; {total_cm} conseillers municipaux agrégés par "
                  "département (rne_cm_agregats), non ingérés nominativement")
        conn.commit()
        log.info("P7 terminé : %d dossiers HATVP, %d mandats RNE, %d alertes A1",
                 len(dossiers), nb_mandats_ingeres, len(lignes_alertes))
        return 0
    except Exception:
        if conn is not None:
            conn.rollback()
        log.exception("P7 en échec (le prochain run réussi remet toutes les tables "
                      "d'aplomb : remplacement complet idempotent)")
        return 1
    finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    sys.exit(main())

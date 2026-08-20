"""P10 — Financement de la vie politique (CNCCFP). Module UI : « Financement de la vie politique ».

Sources (docs/SOURCES.md ; docs/recherche/04-elus-integrite.md §5, §5 bis, §6) :
- S25 — CNCCFP, comptes des partis et groupements politiques, exercices 2021-2024.
  CSV UTF-8 BOM, séparateur ';', décimale à virgule, « - » = absence de valeur,
  166 colonnes homogènes ; l'exercice N est publié début N+2 (2024 paru le
  10/02/2026 — dernier possible). URLs static.data.gouv.fr horodatées →
  re-résolues via l'API data.gouv à chaque passage (SOURCES.md §0.3).
  Piège constaté le 19/08/2026 : le fichier « exercice 2021 » contient une
  ligne datée 2022 (code 671, S.I.E.L.), en DOUBLON du fichier 2022 avec des
  montants différents → chaque ligne garde son exercice déclaré et le couple
  (code, exercice) est dédoublonné au profit de la publication dédiée.
- S29 — CNCCFP, comptes de campagne des législatives des 30/06 et 07/07/2024.
  CSV cp1252 + CRLF, 6 lignes de garde avant l'en-tête, mojibake résiduel
  (double encodage UTF-8→cp1252, ex. « ErgÃ¼n ») réparé champ par champ,
  valeur de saisie « Choisir une nuance déjà enregistrée... » → NULL ;
  4 010 candidats, publication data.gouv du 29/07/2025.
- S37 — décrets annuels d'aide publique aux partis : enveloppe NATIONALE
  fixée par décret, une ligne par décret réellement consulté (2024 et 2026 ;
  aucune autre année n'est inscrite tant qu'elle n'est pas sourcée). AUCUN
  fichier exploitable par parti n'existe (tableau dans le corps du décret,
  Légifrance anti-bot, pas de CSV — constat reconduit le 20/08/2026) → seul
  le TOTAL national est inséré ; la répartition par parti reste en v2
  (SOURCES.md S37). L'aide perçue par parti et par exercice reste lisible
  dans partis_comptes (2021-2024).

  ATTENTION — deux grandeurs de nature différente, à ne jamais juxtaposer
  comme si elles étaient comparables :
  * l'ENVELOPPE du décret = le montant national ouvert par l'État ;
  * la somme des aides INSCRITES AUX COMPTES par les partis (partis_comptes,
    colonnes 102-103) = un cumul de déclarations.
  Les deux séries coïncident en 2021 (66,19 M€) et 2022 (66,13 M€) puis
  divergent en 2023 (70,33 M€) et 2024 (70,28 M€) : une même aide peut être
  déclarée à la fois par la structure qui la perçoit et par celle à qui elle
  est reversée. La DATATION de la rupture est établie ; sa cause ne l'est
  pas — l'apparition en 2023 de « ENSEMBLE ! (MAJORITÉ PRÉSIDENTIELLE) »
  (19,52 M€ en 2023, 19,47 M€ en 2024) est une hypothèse, pas un fait.

Tables créées (idempotentes, rejouables à volonté) :
- partis : référentiel — id ('PARTI-<code_cnccfp>', clé partagée avec
  entites(id), type 'parti'), code_cnccfp (identifiant stable CNCCFP : les
  noms changent, 45 renommages constatés entre 2021 et 2024), nom (dernier
  exercice publié), sigle (extrait du nom si parenthèse finale courte en
  capitales, ex. « (MDC) » ; sinon NULL), dernier_exercice.
- partis_comptes : 1 ligne = parti × exercice — nom_declare, unite ('EUR'
  sauf 2 lignes XPF et 1 unité vide en 2023, EXCLUES des agrégats en euros),
  produits_total, dons (personnes physiques), cotisations_adherents,
  cotisations_elus, aide_publique_f1, aide_publique_f2,
  autres_aides_publiques, contributions_recues (d'autres partis),
  charges_total, resultat.
- campagnes_2024 : 1 ligne = candidat — candidat_id, nom (civilité incluse ;
  casse réparée par normaliser_casse_nom, marqueur « (*) » sorti du nom vers
  la colonne marqueur_etoile), marqueur_etoile (0/1 — signification NON
  documentée dans le jeu de données CNCCFP),
  scrutin, circonscription, departement, code_departement,
  nuance, depenses_declarees, depenses_retenues, recettes_declarees,
  recettes_retenues, remboursement_etat (colonne « RFE » = remboursement
  forfaitaire de l'État), decision (code CNCCFP brut : A, AM, AR, ARM, ARR,
  ARRR, ARRRM, R, AD, HD, DD — les suffixes sont conservés tels quels),
  decision_famille (normalisation mécanique documentée dans FAMILLES_DECISION).
- partis_aide_annuelle : enveloppes légales sourcées, 1 ligne par décret
  consulté — annee, montant_total_eur, fraction1_eur, fraction2_eur (NULL si
  le décret n'a pas été dépouillé fraction par fraction), perimetre,
  reference, source_url, note. Remplace l'ancienne table mono-année
  partis_aide_2026 (supprimée par le schéma).
- alertes (table PARTAGÉE entre pipelines — CREATE TABLE IF NOT EXISTS,
  schéma : id, type, gravite, titre, detail, regle, base_legale, source_url,
  date_calcul). Seuls les types de CE pipeline sont effacés puis recalculés :
    financement_campagne_rejetee      décision R (SOURCES.md §4 A5), gravité haute
    financement_campagne_reformee     décision AR* (A5), gravité moyenne
    financement_parti_dependance_aide aide publique ≥ 75 % des produits et
                                      produits ≥ 1 M€, dernier exercice (A4,
                                      indicateur, pas une infraction), gravité info
    financement_parti_prive_aide      documentaire : la liste des partis privés
                                      d'aide pour manquement n'existe qu'en PDF
                                      au JO (avis CNCCFP, A4/M7), gravité info

Vues (agrégats pour le front) :
- v_partis_top_produits            top partis par produits, dernier exercice (EUR)
- v_partis_aide_publique_evolution aide publique par exercice (f1, f2, autres)
- v_partis_ressources_par_type     répartition des ressources par exercice
- v_campagnes_2024_agregats        totaux, comptes par famille de décision,
                                   taux de rejet sur comptes déposés
- v_campagnes_2024_par_decision    effectifs et montants par code décision
- v_campagnes_2024_top_depenses    candidats triés par dépenses retenues

meta_sources : S25, S29, S37 (date_donnees = date réelle de la donnée,
jamais la date de modification du dataset — SOURCES.md §0.2).

Exécution : python -m pipelines.ingest_financement (FT_DB_PATH pour base
jetable). Échec → code retour 1, rien d'inventé, rien de partiellement écrit
(chaque chargement est transactionnel).
"""

from __future__ import annotations

import csv
import io
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from pipelines import db
from pipelines.common import obtenir_logger, session_http, telecharger

log = obtenir_logger("ingest_financement")

# ---------------------------------------------------------------------------
# Constantes sources
# ---------------------------------------------------------------------------

API_DATASET = "https://www.data.gouv.fr/api/1/datasets/{slug}/"
SLUG_PARTIS = "comptes-des-partis-et-groupements-politiques"
SLUG_LEG2024 = "elections-legislatives-generales-des-30-juin-et-7-juillet-2024"
URL_DATASET_PARTIS = f"https://www.data.gouv.fr/datasets/{SLUG_PARTIS}/"
URL_DATASET_LEG2024 = f"https://www.data.gouv.fr/datasets/{SLUG_LEG2024}/"

EXERCICES = (2021, 2022, 2023, 2024)
MAX_AGE_HEURES = 7 * 24  # données annuelles figées : cache 7 jours

# Décrets annuels d'aide publique (S37) — enveloppe NATIONALE, un enregistrement
# par décret réellement consulté. On n'inscrit AUCUNE année non sourcée : la
# série est volontairement trouée (2021, 2022, 2023, 2025 absents).
#
# `fraction1_eur`/`fraction2_eur` restent None tant que le décret n'a pas été
# dépouillé fraction par fraction (le tableau est dans le corps du texte).
DECRETS_AIDE_PUBLIQUE: tuple[dict, ...] = (
    {
        "annee": 2024,
        "montant_total_eur": 66_438_848.34,
        "fraction1_eur": None,
        "fraction2_eur": None,
        "perimetre": "Enveloppe nationale, 1re + 2nde fractions",
        "reference": "Décret n° 2024-77 du 2 février 2024",
        "source_url": (
            "https://www.legifrance.gouv.fr/search"
            "?fonds=JORF&tab_selection=jorf&query=d%C3%A9cret%20n%C2%B0%202024-77"
        ),
        "note": (
            "Montant repris du diagnostic interne du projet ; le texte du "
            "décret n'a PAS pu être re-vérifié sur Légifrance (HTTP 403 "
            "anti-bot au 20/08/2026), et l'identifiant JORFTEXT n'a pas été "
            "résolu — d'où un lien de recherche Légifrance plutôt qu'un lien "
            "direct. À confirmer sur le texte publié. Cette enveloppe n'est "
            "PAS comparable à la somme des aides inscrites aux comptes 2024 "
            "par les partis (70 275 372,28 € sur 575 comptes) : la seconde "
            "est un cumul de déclarations, où une même aide peut être comptée "
            "deux fois."
        ),
    },
    {
        "annee": 2026,
        "montant_total_eur": 64_262_871.05,
        "fraction1_eur": None,
        "fraction2_eur": None,
        "perimetre": "Enveloppe nationale, 1re + 2nde fractions",
        "reference": "Décret n° 2026-149 du 3 mars 2026 (JO du 04/03/2026)",
        "source_url": "https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000053613045",
        "note": (
            "Répartition par parti non publiée en données exploitables "
            "(tableau dans le corps du décret, Légifrance anti-bot — constat "
            "du 19/08/2026, SOURCES.md S37) : extraction par parti = v2. "
            "L'aide perçue par parti figure dans partis_comptes (exercices "
            "2021-2024), qui relève d'une autre nature de donnée."
        ),
    },
)

# Colonnes utiles du CSV « comptes des partis » (indices 0-based vérifiés sur
# les 4 fichiers 2021-2024, en-têtes identiques). L'en-tête contient des noms
# DUPLIQUÉS (Total_I…, Total_II…, Total_III…) → sélection par indice, avec
# garde sur le nom attendu.
COLONNES_PARTIS = {
    0: "Code_CNCCFP",
    1: "Nom_du_parti",
    2: "Unite_monetaire",
    3: "Exercice",
    100: "Cotisations_des_adherents",
    101: "Cotisations_des_elus",
    102: "Aide_publique_1ere_fraction",
    103: "Aide_publique_2nde_fraction",
    104: "Autres_aides_publiques",
    105: "Dons_de_personne_physique",
    108: "Contributions_financieres_de_partis_ou_groupements_politiques",
    163: "Total_des_produits_I_+_III_+_V",
    164: "Total_des_charges_II_+_IV_+VI_+_VII_+_VIII_+_IX",
    165: "EXCEDENT_OU_DEFICIT_D_ENSEMBLE",
}

# Colonnes utiles du CSV « comptes de campagne » (76 colonnes, en-tête en
# ligne 7 après 6 lignes de garde). « RFE » = remboursement forfaitaire de
# l'État ; décision = code CNCCFP.
COLONNES_CAMPAGNES = {
    0: "candidat",
    1: "nom",
    2: "scrutin",
    3: "circonscription",
    4: "département",
    5: "code département",
    6: "nuance",
    7: "dépenses totales déclarées",
    29: "recettes totales déclarées",
    36: "depenses totales retenues",
    58: "recettes totales retenues",
    74: "RFE",
    75: "decision",
}

NUANCE_PLACEHOLDER = "Choisir une nuance"  # artefact de saisie CNCCFP → NULL

# Normalisation mécanique des codes décision CNCCFP. Les codes composés
# (AM, ARM, ARR, ARRR, ARRRM) portent des mentions complémentaires publiées
# avec la décision : la famille est donnée par le préfixe, le code brut est
# conservé dans campagnes_2024.decision.
FAMILLES_DECISION = {
    "A": "approuve",
    "AR": "approuve_apres_reformation",
    "R": "rejete",
    "AD": "absence_depot",
    "HD": "hors_delai",
    "DD": "dispense_depot",
}

TYPES_ALERTES = (
    "financement_campagne_rejetee",
    "financement_campagne_reformee",
    "financement_parti_dependance_aide",
    "financement_parti_prive_aide",
)

SEUIL_DEPENDANCE_RATIO = 0.75   # aide publique / produits totaux
SEUIL_DEPENDANCE_PRODUITS = 1_000_000.0  # € — écarte le bruit des micro-partis

# ---------------------------------------------------------------------------
# Schéma
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS partis (
    id               TEXT PRIMARY KEY REFERENCES entites(id),
    code_cnccfp      TEXT NOT NULL UNIQUE,
    nom              TEXT NOT NULL,
    sigle            TEXT,
    dernier_exercice INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS partis_comptes (
    parti_id               TEXT NOT NULL REFERENCES partis(id),
    exercice               INTEGER NOT NULL,
    nom_declare            TEXT NOT NULL,
    unite                  TEXT NOT NULL DEFAULT 'EUR',
    produits_total         REAL,
    dons                   REAL,
    cotisations_adherents  REAL,
    cotisations_elus       REAL,
    aide_publique_f1       REAL,
    aide_publique_f2       REAL,
    autres_aides_publiques REAL,
    contributions_recues   REAL,
    charges_total          REAL,
    resultat               REAL,
    PRIMARY KEY (parti_id, exercice)
);
CREATE INDEX IF NOT EXISTS idx_partis_comptes_exercice ON partis_comptes(exercice);

CREATE TABLE IF NOT EXISTS campagnes_2024 (
    candidat_id        TEXT PRIMARY KEY,
    nom                TEXT NOT NULL,
    -- Marqueur « (*) » accolé au nom dans le CSV CNCCFP : sorti du nom pour
    -- ne pas polluer l'identité, conservé ici. Sa SIGNIFICATION n'est pas
    -- documentée dans le jeu de données (aucune légende publiée).
    marqueur_etoile    INTEGER NOT NULL DEFAULT 0,
    scrutin            TEXT,
    circonscription    TEXT NOT NULL,
    departement        TEXT,
    code_departement   TEXT,
    nuance             TEXT,
    depenses_declarees REAL,
    depenses_retenues  REAL,
    recettes_declarees REAL,
    recettes_retenues  REAL,
    remboursement_etat REAL,
    decision           TEXT NOT NULL,
    decision_famille   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_campagnes_2024_decision ON campagnes_2024(decision_famille);

-- Ancienne table mono-année, remplacée par partis_aide_annuelle : elle
-- laissait croire qu'il n'existait qu'un seul décret opposable, ce qui
-- poussait à comparer 2026 (décret) à 2024 (déclarations des partis).
DROP TABLE IF EXISTS partis_aide_2026;

CREATE TABLE IF NOT EXISTS partis_aide_annuelle (
    annee             INTEGER PRIMARY KEY,
    montant_total_eur REAL NOT NULL,
    fraction1_eur     REAL,
    fraction2_eur     REAL,
    perimetre         TEXT NOT NULL,
    reference         TEXT NOT NULL,
    source_url        TEXT NOT NULL,
    note              TEXT
);

-- Table PARTAGÉE entre pipelines : ne jamais la recréer ni la vider en bloc.
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
"""

# ---------------------------------------------------------------------------
# Nettoyage bas niveau
# ---------------------------------------------------------------------------


def montant(valeur: str) -> float | None:
    """Montant CNCCFP → float. '' et '-' = absence de valeur → None.

    Gère la décimale à virgule et les espaces (y compris insécables U+00A0 /
    U+202F) éventuels. Lève ValueError sur toute autre forme : rien n'est
    deviné.
    """
    v = valeur.strip().replace(" ", "").replace(" ", "").replace(" ", "")
    if v in ("", "-"):
        return None
    return float(v.replace(",", "."))


_MOJIBAKE_RE = re.compile(r"[ÃÂ].")


def reparer_mojibake(texte: str) -> str:
    """Répare le double encodage UTF-8 lu en cp1252 (« ErgÃ¼n » → « Ergün »).

    Constaté sur ~10 lignes du CSV campagnes (en-têtes comprises), MÊLÉ à des
    accents légitimement cp1252 dans la même chaîne (« déjÃ\xa0 enregistrée »)
    → la réparation est chirurgicale, paire par paire : seules les séquences
    « Ã/Â + 1 caractère » dont l'aller-retour cp1252→UTF-8 est valide sont
    re-décodées ; tout le reste est rendu tel quel (jamais de perte).
    """
    if "Ã" not in texte and "Â" not in texte:
        return texte

    def _reparer_paire(m: re.Match) -> str:
        paire = m.group(0)
        try:
            return paire.encode("cp1252").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            return paire

    return _MOJIBAKE_RE.sub(_reparer_paire, texte)


_MAJ_ASCII = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
_MIN_ASCII = frozenset("abcdefghijklmnopqrstuvwxyz")


def _est_minuscule_accentuee(caractere: str) -> bool:
    """Minuscule NON ASCII (é, è, ï, ô, ç…) — le symptôme de la casse cassée."""
    return (
        caractere.isalpha()
        and caractere.islower()
        and caractere not in _MIN_ASCII
    )


def _normaliser_token(token: str) -> str:
    """Répare la casse d'UN token. Voir normaliser_casse_nom pour la règle."""
    # Famille 1 — patronyme en capitales dont les accents sont restés en bas
    # de casse (« ELéLOUé-VALMAR »). Le garde-fou « aucune minuscule ASCII »
    # est ce qui protège « ACQUAVIVA », « Jean-Félix », « Agnès », « de »,
    # « van », « d'Ornano », « 12éme »… : dès qu'une minuscule ASCII est
    # présente, le token est une graphie normale et n'est pas touché.
    if len(token) >= 3 and not any(c in _MIN_ASCII for c in token):
        majuscules = sum(1 for c in token if c in _MAJ_ASCII)
        if majuscules >= 2 and any(_est_minuscule_accentuee(c) for c in token):
            # .upper() est Unicode-aware en Python 3 : « ELéLOUé » → « ELÉLOUÉ ».
            return token.upper()
    # Famille 2 — prénom entièrement en bas de casse ouvert par une minuscule
    # accentuée (« éric », « émilie », « édouard »). Un prénom bas de casse à
    # initiale ASCII (« de », « van ») n'est PAS concerné : ce sont des
    # particules, leur bas de casse est la graphie correcte.
    if token and _est_minuscule_accentuee(token[0]) and token == token.lower():
        return token[0].upper() + token[1:]
    return token


# ---------------------------------------------------------------------------
# Rattachement géographique des comptes de campagne (§ M5 QUALITE-DONNEES.md)
# ---------------------------------------------------------------------------

# POURQUOI ces trois correspondances et pas une table complète : la CNCCFP
# publie des codes qui ne sont PAS ceux du COG, mais l'écart est systématique
# et se réduit à trois familles, chacune vérifiée sur le CSV publié le
# 20/08/2026 (4 010 lignes) :
#   - un zéro initial perdu par un tableur (« 1 » pour l'Ain) — 216 lignes ;
#   - la Corse notée « 20A »/« 20B » au lieu de « 2A »/« 2B » — 32 lignes ;
#   - Saint-Barthélemy notée « ZX », dont le code COG est « 977 » — 8 lignes.
# Tout autre code est rendu tel quel : on corrige ce qui est prouvé, rien de
# plus. Enjeu concret : sans cela, campagnes_2024 ne peut PAS être jointe à
# ref_departements, et toute carte des comptes de campagne est impossible.
_CODES_DEPARTEMENT_CNCCFP = {"20A": "2A", "20B": "2B", "ZX": "977"}

# Sentinelle de la CNCCFP pour les onze circonscriptions des Français de
# l'étranger. Le CSV leur attribue en outre le code département « 75 »
# (Paris) : c'est FAUX, et 125 lignes sont ainsi rattachées à tort à un
# département métropolitain. On restitue le libellé porté par la
# circonscription elle-même, et on met le code à NULL — il n'existe aucun
# département français correspondant, et NULL dit « pas de département »
# sans inventer de code.
_SENTINELLE_HORS_DE_FRANCE = "ZZ"
_LIBELLE_HORS_DE_FRANCE = "Français établis hors de France"

# Quatre conventions typographiques pour le même ordinal cohabitent dans la
# colonne `circonscription` : « 2e » (3 048 lignes), « 1re » (624),
# « 2ème » (246), « 1ère » (50). Les deux dernières ne sont pas des abréviations
# françaises correctes ; surtout, elles s'affichent côte à côte en page
# Alertes (« 8ème circonscription » à côté de « 6e circonscription »).
# On ramène tout sur la forme courte, qui est déjà majoritaire à 87 %.
_ORDINAL_EME_RE = re.compile(r"(\d+)ème\b")
_ORDINAL_ERE_RE = re.compile(r"(\d+)ère\b")


def normaliser_code_departement(code: str | None) -> str | None:
    """Code département CNCCFP → code COG, ou None si non renseigné."""
    if not code:
        return None
    code = code.strip()
    if not code:
        return None
    if code in _CODES_DEPARTEMENT_CNCCFP:
        return _CODES_DEPARTEMENT_CNCCFP[code]
    # Zéro initial rétabli pour les seuls codes métropolitains à un chiffre.
    if len(code) == 1 and code.isdigit():
        return "0" + code
    return code


def normaliser_ordinaux(texte: str) -> str:
    """« 8ème circonscription » → « 8e », « 1ère » → « 1re ». Rien d'autre."""
    return _ORDINAL_ERE_RE.sub(r"\1re", _ORDINAL_EME_RE.sub(r"\1e", texte))


def normaliser_geographie_campagne(
    circonscription: str, departement: str | None, code_departement: str | None
) -> tuple[str, str | None, str | None]:
    """(circonscription, departement, code) nettoyés — voir les constantes.

    Fonction pure et sans accès base : elle ne fait que réécrire ce que le
    CSV contient déjà, jamais compléter depuis une autre source.
    """
    circonscription = normaliser_ordinaux(circonscription)
    if departement == _SENTINELLE_HORS_DE_FRANCE:
        return circonscription, _LIBELLE_HORS_DE_FRANCE, None
    return circonscription, departement, normaliser_code_departement(code_departement)


def normaliser_casse_nom(texte: str) -> str:
    """Répare la casse des noms de personnes livrés cassés par la CNCCFP.

    Défaut PRÉSENT DANS LA SOURCE (prouvé au niveau octet : le CSV contient
    « M. EL\xe9LOU\xe9-VALMAR », soit 0xE9 = « é » minuscule cp1252, là où
    « É » majuscule serait 0xC9). Ce n'est donc PAS un mojibake : aucun « Ã »
    n'est en jeu et `reparer_mojibake` ne voit même pas le motif — les deux
    fonctions traitent deux défauts distincts et se complètent.

    Deux familles, réparées token par token :
    1. token d'au moins 3 caractères, ≥ 2 majuscules ASCII, ≥ 1 minuscule
       accentuée et AUCUNE minuscule ASCII → passage en capitales ;
    2. token entièrement en bas de casse ouvert par une minuscule accentuée
       → capitalisation de la seule initiale.

    Tout le reste est rendu à l'identique : « M. ACQUAVIVA Jean-Félix »,
    « Mme FIRMIN LE BODO Agnès », « Mme de COSSé BRISSAC Céline » (seul
    « COSSé » bouge, « de » est conservé), les noms composés et les
    particules ne sont jamais touchés.
    """
    if not texte:
        return texte
    # split/join sur l'espace simple : les séparateurs sont préservés tels
    # quels, rien n'est perdu ni réécrit hors des tokens eux-mêmes.
    return " ".join(_normaliser_token(t) for t in texte.split(" "))


_MARQUEUR_ETOILE_RE = re.compile(r"\s*\(\*\)\s*$")


def extraire_marqueur_etoile(nom: str) -> tuple[str, bool]:
    """Sort le marqueur « (*) » suffixé au nom. → (nom_net, marqueur_present).

    51 noms du CSV comptes de campagne portent ce suffixe. Le jeu de données
    ne publie AUCUNE légende : sa signification n'est pas documentée. Il est
    donc retiré du nom (il n'en fait pas partie) et conservé à part, pour
    être restitué tel quel, avec cette réserve, dans le détail de l'alerte.
    """
    net = _MARQUEUR_ETOILE_RE.sub("", nom)
    return (net.strip(), net != nom)


# ---------------------------------------------------------------------------
# Format monétaire français (même convention que app/src/lib/format.ts)
# ---------------------------------------------------------------------------

#: Espace fine insécable — séparateur de milliers ET espace avant l'unité.
ESPACE_FINE = "\u202f"


def formater_euros(valeur: float | None, decimales: int = 2) -> str:
    """Montant → « 19 474 807 € » / « 1 234,56 € », ou « non renseigné ».

    Convention identique au front (docs/DATAVIZ.md §4) : espace fine
    insécable U+202F en séparateur de milliers et devant l'unité, virgule
    décimale, décimales supprimées quand elles sont nulles.

    `None` ne devient JAMAIS « 0 € » : une donnée absente est rendue
    « non renseigné ». Un zéro réel, lui, reste un zéro et s'affiche « 0 € ».
    """
    if valeur is None:
        return "non renseigné"
    arrondi = round(float(valeur), decimales)
    if arrondi == int(arrondi):
        corps = f"{int(arrondi):,}".replace(",", ESPACE_FINE)
    else:
        corps = f"{arrondi:,.{decimales}f}".replace(",", "\x00")
        corps = corps.replace(".", ",").replace("\x00", ESPACE_FINE)
    return corps + ESPACE_FINE + "€"


_SIGLE_RE = re.compile(r"\(([^()]{2,12})\)\s*$")


def extraire_sigle(nom: str) -> str | None:
    """Sigle si le nom se termine par une parenthèse courte en capitales.

    Ex. « MOUVEMENT DES CITOYENS (MDC) » → « MDC ». Les parenthèses longues
    (« ENSEMBLE ! (MAJORITÉ PRÉSIDENTIELLE) ») ne sont pas des sigles → None.
    """
    m = _SIGLE_RE.search(nom.strip())
    if not m:
        return None
    sigle = m.group(1).strip()
    if not sigle or sigle != sigle.upper():
        return None
    return sigle


def famille_decision(code: str) -> str:
    """Famille normalisée d'un code décision CNCCFP (préfixe documenté)."""
    c = code.strip().upper()
    if c in FAMILLES_DECISION:
        return FAMILLES_DECISION[c]
    if c.startswith("AR"):
        return "approuve_apres_reformation"
    if c.startswith("AD"):
        return "absence_depot"
    if c.startswith("A"):
        return "approuve"  # A + mention complémentaire (ex. AM)
    if c.startswith("R"):
        return "rejete"
    return "autre"


def _verifier_colonnes(entete: list[str], attendues: dict[int, str], contexte: str) -> None:
    """Garde anti-dérive de format : chaque indice doit porter le nom attendu."""
    if len(entete) < max(attendues) + 1:
        raise ValueError(
            f"{contexte} : {len(entete)} colonnes lues, "
            f"au moins {max(attendues) + 1} attendues"
        )
    for idx, nom in attendues.items():
        lu = reparer_mojibake(entete[idx]).strip()
        if lu != nom:
            raise ValueError(
                f"{contexte} : colonne {idx} = {lu!r}, attendu {nom!r} "
                "(format source modifié ?)"
            )


# ---------------------------------------------------------------------------
# Résolution des ressources (SOURCES.md §0.3 : URLs horodatées, re-résoudre)
# ---------------------------------------------------------------------------


def resoudre_ressources(session) -> dict:
    """Interroge l'API data.gouv et retourne les URLs réelles des fichiers.

    Retour : {'partis': {exercice: url}, 'avis_2024': url|None, 'campagnes': url}.
    Lève RuntimeError si une ressource attendue manque (échec franc).
    """
    ressources: dict = {"partis": {}, "avis_2024": None, "campagnes": None}

    r = session.get(API_DATASET.format(slug=SLUG_PARTIS), timeout=60)
    r.raise_for_status()
    for res in r.json().get("resources", []):
        titre = (res.get("title") or "").lower()
        fmt = (res.get("format") or "").lower()
        for ex in EXERCICES:
            if fmt == "csv" and "exercice" in titre and str(ex) in titre \
                    and ex not in ressources["partis"]:
                ressources["partis"][ex] = res["url"]
        if fmt == "pdf" and "avis" in titre and "2024" in titre \
                and ressources["avis_2024"] is None:
            ressources["avis_2024"] = res["url"]

    r = session.get(API_DATASET.format(slug=SLUG_LEG2024), timeout=60)
    r.raise_for_status()
    for res in r.json().get("resources", []):
        titre = (res.get("title") or "").lower()
        if (res.get("format") or "").lower() == "csv" and "comptes_campagne" in titre:
            ressources["campagnes"] = res["url"]
            break

    manquants = [str(ex) for ex in EXERCICES if ex not in ressources["partis"]]
    if manquants:
        raise RuntimeError(
            f"CSV comptes des partis introuvables via l'API data.gouv "
            f"pour les exercices : {', '.join(manquants)}"
        )
    if not ressources["campagnes"]:
        raise RuntimeError(
            "CSV comptes de campagne législatives 2024 introuvable via l'API data.gouv"
        )
    return ressources


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def parser_partis(brut: bytes, millesime: int) -> list[dict]:
    """CSV comptes des partis (un millésime de publication) → lignes utiles.

    UTF-8 BOM strict (toute dérive d'encodage = échec franc), ';', décimale à
    virgule, « - » = None. Chaque ligne est conservée avec SON exercice déclaré
    (colonne Exercice) : le fichier « exercice 2021 » publié contient 1 ligne
    datée 2022 (code 671, S.I.E.L. — constat du 19/08/2026), signalée en
    avertissement. Si AUCUNE ligne ne porte le millésime attendu, le fichier
    n'est pas le bon → échec franc.
    """
    texte = brut.decode("utf-8-sig")  # UnicodeDecodeError = échec voulu
    lignes = list(csv.reader(io.StringIO(texte), delimiter=";"))
    if not lignes:
        raise ValueError(f"comptes des partis {millesime} : fichier vide")
    _verifier_colonnes(lignes[0], COLONNES_PARTIS, f"comptes des partis {millesime}")

    resultat: list[dict] = []
    au_millesime = 0
    for champs in lignes[1:]:
        if not champs or not any(c.strip() for c in champs):
            continue
        if len(champs) < 166:
            raise ValueError(
                f"comptes des partis {millesime} : ligne à {len(champs)} champs"
            )
        code = champs[0].strip()
        if not code:
            raise ValueError(f"comptes des partis {millesime} : Code_CNCCFP vide")
        ex_lu = int(champs[3].strip())
        if ex_lu == millesime:
            au_millesime += 1
        else:
            log.warning(
                "comptes des partis %d : code %s daté %d — ligne conservée "
                "avec son propre exercice",
                millesime, code, ex_lu,
            )
        resultat.append(
            {
                "code": code,
                # même normalisation de casse que les noms de personnes, par
                # symétrie (aucun nom de parti n'est modifié dans le corpus
                # 2021-2024 : le garde-fou « aucune minuscule ASCII » protège
                # « 12éme », « 8ème », « SoCARRIÈRES »…).
                "nom": normaliser_casse_nom(champs[1].strip()),
                "unite": champs[2].strip(),
                "exercice": ex_lu,
                "millesime": millesime,
                "cotisations_adherents": montant(champs[100]),
                "cotisations_elus": montant(champs[101]),
                "aide_publique_f1": montant(champs[102]),
                "aide_publique_f2": montant(champs[103]),
                "autres_aides_publiques": montant(champs[104]),
                "dons": montant(champs[105]),
                "contributions_recues": montant(champs[108]),
                "produits_total": montant(champs[163]),
                "charges_total": montant(champs[164]),
                "resultat": montant(champs[165]),
            }
        )
    if resultat and au_millesime == 0:
        raise ValueError(
            f"comptes des partis {millesime} : aucune ligne datée {millesime} "
            "— mauvais fichier ?"
        )
    return resultat


def decoder_campagnes(brut: bytes) -> tuple[str, str]:
    """Décode le CSV campagnes en testant réellement UTF-8 puis cp1252.

    Le fichier publié est en cp1252 (l'UTF-8 échoue, constaté) ; l'UTF-8 est
    tenté d'abord pour survivre à un futur changement d'encodage côté CNCCFP.
    Retourne (texte, encodage_retenu).
    """
    try:
        return brut.decode("utf-8-sig"), "utf-8"
    except UnicodeDecodeError:
        return brut.decode("cp1252"), "cp1252"


def parser_campagnes(brut: bytes) -> list[dict]:
    """CSV comptes de campagne → lignes candidates propres.

    Traite les pièges constatés (docs/recherche/04 §6) : encodage cp1252,
    lignes de garde avant l'en-tête (6 dans le fichier publié — détectées,
    pas comptées en dur), mojibake réparé champ par champ, « - » = None,
    nuance « Choisir une nuance… » (artefact de saisie) → None.

    Deux traitements du nom en plus (constats du 20/08/2026) : casse réparée
    (normaliser_casse_nom — défaut du CSV source, distinct du mojibake) et
    marqueur « (*) » sorti du nom vers un champ dédié.

    Et depuis le 20/08/2026, le rattachement géographique est normalisé
    (normaliser_geographie_campagne) : codes département ramenés au COG,
    sentinelle « ZZ » des Français de l'étranger explicitée, ordinaux de
    circonscription unifiés. Voir § M5 de doc/QUALITE-DONNEES.md.
    """
    texte, encodage = decoder_campagnes(brut)
    log.info("comptes de campagne : encodage retenu = %s", encodage)

    lignes_physiques = texte.splitlines()
    idx_entete = None
    for i, ligne in enumerate(lignes_physiques[:20]):
        if ligne.startswith("candidat;"):
            idx_entete = i
            break
    if idx_entete is None:
        raise ValueError(
            "comptes de campagne : en-tête 'candidat;…' introuvable "
            "dans les 20 premières lignes"
        )
    if idx_entete:
        log.info("comptes de campagne : %d ligne(s) de garde sautée(s)", idx_entete)

    lecteur = csv.reader(
        io.StringIO("\n".join(lignes_physiques[idx_entete:])), delimiter=";"
    )
    lignes = list(lecteur)
    _verifier_colonnes(lignes[0], COLONNES_CAMPAGNES, "comptes de campagne")

    resultat: list[dict] = []
    for champs in lignes[1:]:
        if not champs or not any(c.strip() for c in champs):
            continue
        if len(champs) < 76:
            raise ValueError(f"comptes de campagne : ligne à {len(champs)} champs")
        champs = [reparer_mojibake(c) for c in champs]
        nuance = champs[6].strip() or None
        if nuance and nuance.startswith(NUANCE_PLACEHOLDER):
            nuance = None
        decision = champs[75].strip()
        # Le nom subit DEUX traitements distincts et cumulatifs : réparation
        # du mojibake (déjà faite ci-dessus sur tous les champs) puis
        # réparation de la casse, défaut présent tel quel dans le CSV source.
        nom, marqueur_etoile = extraire_marqueur_etoile(
            normaliser_casse_nom(champs[1].strip())
        )
        circonscription, departement, code_departement = (
            normaliser_geographie_campagne(
                champs[3].strip(), champs[4].strip() or None,
                champs[5].strip() or None,
            )
        )
        resultat.append(
            {
                "candidat_id": champs[0].strip(),
                "nom": nom,
                "marqueur_etoile": marqueur_etoile,
                "scrutin": champs[2].strip() or None,
                # Les trois colonnes géographiques sont traitées ENSEMBLE :
                # la sentinelle « ZZ » du département conditionne le sort du
                # code (cf. normaliser_geographie_campagne).
                "circonscription": circonscription,
                "departement": departement,
                "code_departement": code_departement,
                "nuance": nuance,
                "depenses_declarees": montant(champs[7]),
                "depenses_retenues": montant(champs[36]),
                "recettes_declarees": montant(champs[29]),
                "recettes_retenues": montant(champs[58]),
                "remboursement_etat": montant(champs[74]),
                "decision": decision,
                "decision_famille": famille_decision(decision),
            }
        )
    return resultat


# ---------------------------------------------------------------------------
# Chargements (chacun transactionnel)
# ---------------------------------------------------------------------------


def creer_tables(conn) -> None:
    """Crée/migre les tables du pipeline. Rejouable sur une base existante."""
    conn.executescript(_SCHEMA)
    # `CREATE TABLE IF NOT EXISTS` n'ajoute pas de colonne à une table déjà
    # présente : la colonne marqueur_etoile est posée explicitement sur les
    # bases antérieures (migration idempotente).
    colonnes = {
        r["name"] for r in conn.execute("PRAGMA table_info(campagnes_2024)")
    }
    if "marqueur_etoile" not in colonnes:
        conn.execute(
            "ALTER TABLE campagnes_2024 "
            "ADD COLUMN marqueur_etoile INTEGER NOT NULL DEFAULT 0"
        )
        log.info("migration : colonne campagnes_2024.marqueur_etoile ajoutée")
    conn.commit()


# Tolérance de l'identité comptable produits − charges = résultat, en unités
# monétaires. 1 unité suffit : les comptes sont publiés au centime, un écart
# supérieur à l'euro n'est pas un arrondi mais une incohérence de saisie.
TOLERANCE_EQUILIBRE = 1.0


def controler_comptes_partis(lignes: list[dict]) -> dict[str, int]:
    """Journalise les incohérences comptables des comptes de partis.

    Trois contrôles, tous fondés sur des impossibilités et non sur des
    seuils d'opinion :
    1. `produits_total < 0` — un TOTAL de produits ne peut pas être négatif ;
       une charge n'a rien à faire dans un total de produits ;
    2. `produits − charges ≠ résultat` au-delà de TOLERANCE_EQUILIBRE — c'est
       l'identité qui définit le résultat ;
    3. `produits_total = 0` — techniquement possible (parti en sommeil), mais
       massif : 51 à 61 partis par exercice. Simple compteur, pas d'alerte
       ligne à ligne : impossible de distinguer la coquille vide réelle du
       dépôt incomplet sans une source externe.

    POURQUOI journaliser et ne RIEN corriger : ces montants sont ceux que la
    CNCCFP publie. Les rectifier reviendrait à publier des comptes que
    personne n'a déposés. Le site n'expose que le Top 10 des partis, où
    aucune de ces lignes n'apparaît ; l'enjeu est de ne plus les absorber en
    silence, pour qu'une dégradation de la source se voie dans les logs
    d'ingestion. Mesuré le 20/08/2026 : 5 produits totaux négatifs,
    3 comptes déséquilibrés, 222 exercices à produits nuls.
    """
    produits_negatifs = desequilibres = produits_nuls = 0
    for ligne in lignes:
        produits = ligne.get("produits_total")
        charges = ligne.get("charges_total")
        resultat_ = ligne.get("resultat")
        if produits is not None and produits < 0:
            produits_negatifs += 1
            log.warning(
                "comptes de partis : produits totaux négatifs — %s (%s), %s",
                ligne.get("nom"), ligne.get("exercice"), produits,
            )
        if produits is not None and produits == 0:
            produits_nuls += 1
        # L'identité comptable ne se teste que sur une même unité monétaire :
        # les comptes du Pacifique sont publiés en XPF (cf. colonne `unite`).
        if (
            ligne.get("unite") == "EUR"
            and produits is not None
            and charges is not None
            and resultat_ is not None
            and abs(produits - charges - resultat_) > TOLERANCE_EQUILIBRE
        ):
            desequilibres += 1
            log.warning(
                "comptes de partis : produits − charges ≠ résultat — %s (%s), "
                "%s − %s ≠ %s", ligne.get("nom"), ligne.get("exercice"),
                produits, charges, resultat_,
            )
    if produits_nuls:
        log.info("comptes de partis : %d exercice(s) à produits totaux nuls",
                 produits_nuls)
    return {
        "produits_negatifs": produits_negatifs,
        "desequilibres": desequilibres,
        "produits_nuls": produits_nuls,
    }


def charger_partis(conn, comptes_par_exercice: dict[int, list[dict]]) -> tuple[int, int]:
    """Référentiel partis (+ entites) et table partis_comptes. → (partis, lignes).

    Déduplique les couples (code, exercice) présents dans deux publications
    (1 cas constaté : code 671, exercice 2022, publié dans les fichiers 2021
    ET 2022 avec des montants différents) : priorité à la ligne issue de la
    publication dédiée à l'exercice, l'autre est écartée et signalée.
    """
    par_cle: dict[tuple[str, int], dict] = {}
    for ligne in (l for lignes in comptes_par_exercice.values() for l in lignes):
        cle = (ligne["code"], ligne["exercice"])
        en_place = par_cle.get(cle)
        if en_place is None:
            par_cle[cle] = ligne
            continue
        gardee, ecartee = en_place, ligne
        if ligne["millesime"] == ligne["exercice"] != en_place["millesime"]:
            par_cle[cle] = ligne
            gardee, ecartee = ligne, en_place
        log.warning(
            "doublon (code %s, exercice %d) : ligne du millésime %d écartée "
            "au profit de celle du millésime %d",
            cle[0], cle[1], ecartee["millesime"], gardee["millesime"],
        )
    toutes = list(par_cle.values())
    controler_comptes_partis(toutes)
    referentiel: dict[str, dict] = {}
    for ligne in sorted(toutes, key=lambda l: l["exercice"]):
        referentiel[ligne["code"]] = ligne  # le dernier exercice publié gagne

    with conn:
        conn.execute("DELETE FROM partis_comptes")
        conn.execute("DELETE FROM partis")
        for code, ligne in referentiel.items():
            parti_id = f"PARTI-{code}"
            sigle = extraire_sigle(ligne["nom"])
            conn.execute(
                """
                INSERT INTO entites (id, type, nom, sigle)
                VALUES (?, 'parti', ?, ?)
                ON CONFLICT(id) DO UPDATE SET nom = excluded.nom,
                                              sigle = excluded.sigle
                """,
                (parti_id, ligne["nom"], sigle),
            )
            conn.execute(
                """
                INSERT INTO partis (id, code_cnccfp, nom, sigle, dernier_exercice)
                VALUES (?, ?, ?, ?, ?)
                """,
                (parti_id, code, ligne["nom"], sigle, ligne["exercice"]),
            )
        conn.executemany(
            """
            INSERT INTO partis_comptes
                (parti_id, exercice, nom_declare, unite, produits_total, dons,
                 cotisations_adherents, cotisations_elus, aide_publique_f1,
                 aide_publique_f2, autres_aides_publiques, contributions_recues,
                 charges_total, resultat)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    f"PARTI-{l['code']}", l["exercice"], l["nom"], l["unite"],
                    l["produits_total"], l["dons"], l["cotisations_adherents"],
                    l["cotisations_elus"], l["aide_publique_f1"],
                    l["aide_publique_f2"], l["autres_aides_publiques"],
                    l["contributions_recues"], l["charges_total"], l["resultat"],
                )
                for l in toutes
            ],
        )
    return len(referentiel), len(toutes)


def charger_campagnes(conn, lignes: list[dict]) -> int:
    with conn:
        conn.execute("DELETE FROM campagnes_2024")
        conn.executemany(
            """
            INSERT INTO campagnes_2024
                (candidat_id, nom, marqueur_etoile, scrutin, circonscription,
                 departement, code_departement, nuance, depenses_declarees,
                 depenses_retenues, recettes_declarees, recettes_retenues,
                 remboursement_etat, decision, decision_famille)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    l["candidat_id"], l["nom"], int(l["marqueur_etoile"]),
                    l["scrutin"], l["circonscription"],
                    l["departement"], l["code_departement"], l["nuance"],
                    l["depenses_declarees"], l["depenses_retenues"],
                    l["recettes_declarees"], l["recettes_retenues"],
                    l["remboursement_etat"], l["decision"], l["decision_famille"],
                )
                for l in lignes
            ],
        )
    return len(lignes)


def charger_decrets_aide(conn) -> int:
    """Enveloppes légales sourcées (S37) → partis_aide_annuelle. → nb de lignes.

    Une ligne par décret réellement consulté, et RIEN d'autre : aucune année
    n'est interpolée ni reconduite. Ne pas confondre avec partis_comptes, qui
    porte l'aide déclarée par les partis (autre nature de donnée).
    """
    with conn:
        conn.execute("DELETE FROM partis_aide_annuelle")
        conn.executemany(
            """
            INSERT INTO partis_aide_annuelle
                (annee, montant_total_eur, fraction1_eur, fraction2_eur,
                 perimetre, reference, source_url, note)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    d["annee"], d["montant_total_eur"], d["fraction1_eur"],
                    d["fraction2_eur"], d["perimetre"], d["reference"],
                    d["source_url"], d["note"],
                )
                for d in DECRETS_AIDE_PUBLIQUE
            ],
        )
    return len(DECRETS_AIDE_PUBLIQUE)


def creer_vues(conn) -> None:
    """Agrégats servis au front. Les lignes XPF/unité vide sont hors agrégats €."""
    with conn:
        conn.executescript(
            """
            DROP VIEW IF EXISTS v_partis_top_produits;
            CREATE VIEW v_partis_top_produits AS
            SELECT p.id AS parti_id, p.code_cnccfp, p.nom, p.sigle, c.exercice,
                   c.produits_total, c.charges_total, c.resultat,
                   COALESCE(c.aide_publique_f1,0) + COALESCE(c.aide_publique_f2,0)
                     + COALESCE(c.autres_aides_publiques,0) AS aide_publique,
                   c.dons,
                   COALESCE(c.cotisations_adherents,0)
                     + COALESCE(c.cotisations_elus,0)       AS cotisations
            FROM partis_comptes c
            JOIN partis p ON p.id = c.parti_id
            WHERE c.exercice = (SELECT MAX(exercice) FROM partis_comptes)
              AND c.unite = 'EUR'
            ORDER BY c.produits_total DESC;

            DROP VIEW IF EXISTS v_partis_aide_publique_evolution;
            CREATE VIEW v_partis_aide_publique_evolution AS
            SELECT exercice,
                   ROUND(SUM(COALESCE(aide_publique_f1,0)), 2)        AS aide_f1,
                   ROUND(SUM(COALESCE(aide_publique_f2,0)), 2)        AS aide_f2,
                   ROUND(SUM(COALESCE(autres_aides_publiques,0)), 2)  AS autres_aides_publiques,
                   ROUND(SUM(COALESCE(aide_publique_f1,0)
                           + COALESCE(aide_publique_f2,0)), 2)        AS aide_f1_f2,
                   SUM(CASE WHEN COALESCE(aide_publique_f1,0)
                              + COALESCE(aide_publique_f2,0) > 0
                        THEN 1 ELSE 0 END)                            AS nb_partis_aides
            FROM partis_comptes
            WHERE unite = 'EUR'
            GROUP BY exercice
            ORDER BY exercice;

            DROP VIEW IF EXISTS v_partis_ressources_par_type;
            CREATE VIEW v_partis_ressources_par_type AS
            SELECT exercice,
                   ROUND(SUM(COALESCE(dons,0)), 2)                   AS dons,
                   ROUND(SUM(COALESCE(cotisations_adherents,0)), 2)  AS cotisations_adherents,
                   ROUND(SUM(COALESCE(cotisations_elus,0)), 2)       AS cotisations_elus,
                   ROUND(SUM(COALESCE(aide_publique_f1,0)
                           + COALESCE(aide_publique_f2,0)
                           + COALESCE(autres_aides_publiques,0)), 2) AS aide_publique,
                   ROUND(SUM(COALESCE(contributions_recues,0)), 2)   AS contributions_recues,
                   ROUND(SUM(COALESCE(produits_total,0))
                       - SUM(COALESCE(dons,0))
                       - SUM(COALESCE(cotisations_adherents,0))
                       - SUM(COALESCE(cotisations_elus,0))
                       - SUM(COALESCE(aide_publique_f1,0)
                           + COALESCE(aide_publique_f2,0)
                           + COALESCE(autres_aides_publiques,0))
                       - SUM(COALESCE(contributions_recues,0)), 2)   AS autres_produits,
                   ROUND(SUM(COALESCE(produits_total,0)), 2)         AS produits_total
            FROM partis_comptes
            WHERE unite = 'EUR'
            GROUP BY exercice
            ORDER BY exercice;

            DROP VIEW IF EXISTS v_campagnes_2024_agregats;
            CREATE VIEW v_campagnes_2024_agregats AS
            SELECT nb_candidats, depenses_declarees, depenses_retenues,
                   recettes_declarees, recettes_retenues, remboursement_etat,
                   nb_approuves, nb_reformes, nb_rejetes, nb_absences_depot,
                   nb_hors_delai, nb_dispenses_depot,
                   ROUND(1.0 * nb_rejetes
                         / NULLIF(nb_candidats - nb_dispenses_depot
                                  - nb_absences_depot, 0), 4)
                       AS taux_rejet_comptes_deposes
            FROM (
                SELECT COUNT(*)                                          AS nb_candidats,
                       ROUND(SUM(COALESCE(depenses_declarees,0)), 2)     AS depenses_declarees,
                       ROUND(SUM(COALESCE(depenses_retenues,0)), 2)      AS depenses_retenues,
                       ROUND(SUM(COALESCE(recettes_declarees,0)), 2)     AS recettes_declarees,
                       ROUND(SUM(COALESCE(recettes_retenues,0)), 2)      AS recettes_retenues,
                       ROUND(SUM(COALESCE(remboursement_etat,0)), 2)     AS remboursement_etat,
                       SUM(decision_famille = 'approuve')                AS nb_approuves,
                       SUM(decision_famille = 'approuve_apres_reformation') AS nb_reformes,
                       SUM(decision_famille = 'rejete')                  AS nb_rejetes,
                       SUM(decision_famille = 'absence_depot')           AS nb_absences_depot,
                       SUM(decision_famille = 'hors_delai')              AS nb_hors_delai,
                       SUM(decision_famille = 'dispense_depot')          AS nb_dispenses_depot
                FROM campagnes_2024
            );

            DROP VIEW IF EXISTS v_campagnes_2024_par_decision;
            CREATE VIEW v_campagnes_2024_par_decision AS
            SELECT decision, decision_famille, COUNT(*) AS nb,
                   ROUND(SUM(COALESCE(depenses_retenues,0)), 2)  AS depenses_retenues,
                   ROUND(SUM(COALESCE(remboursement_etat,0)), 2) AS remboursement_etat
            FROM campagnes_2024
            GROUP BY decision, decision_famille
            ORDER BY nb DESC;

            DROP VIEW IF EXISTS v_campagnes_2024_top_depenses;
            CREATE VIEW v_campagnes_2024_top_depenses AS
            SELECT candidat_id, nom, circonscription, departement, nuance,
                   depenses_declarees, depenses_retenues, remboursement_etat,
                   decision, decision_famille
            FROM campagnes_2024
            ORDER BY COALESCE(depenses_retenues, 0) DESC;
            """
        )


# ---------------------------------------------------------------------------
# Alertes (SOURCES.md §4, règles A4 et A5)
# ---------------------------------------------------------------------------


#: Les quatre postes monétaires d'un compte de campagne. La condition
#: « compte sans montant » est CONJONCTIVE sur ces quatre postes : un seul
#: poste à zéro ne prouve rien (152 comptes ont des dépenses > 0 et un
#: remboursement à 0 — un vrai zéro, juridiquement obligatoire pour un compte
#: rejeté ; 47 comptes réformés ont un écart de 0 € — un vrai zéro aussi).
POSTES_COMPTE_CAMPAGNE = (
    "depenses_declarees",
    "depenses_retenues",
    "recettes_declarees",
    "remboursement_etat",
)


def compte_sans_montant(ligne) -> bool:
    """Vrai si les QUATRE postes monétaires sont à zéro et tous non NULL.

    Un compte de campagne intégralement à zéro n'est pas un candidat qui n'a
    rien dépensé : c'est l'absence de compte exploitable, souvent le motif du
    rejet. Le CSV CNCCFP distingue bien le vide du zéro (une même ligne peut
    avoir 46 champs vides sur 76 tout en portant des « 0 » littéraux) : ce
    zéro-là est écrit par la source, il n'est pas un NULL perdu à
    l'ingestion. Publier « dépenses déclarées : 0 € » sous le nom d'une
    personne serait donc une affirmation de fait fausse.
    """
    valeurs = [ligne[poste] for poste in POSTES_COMPTE_CAMPAGNE]
    return all(v is not None and v == 0 for v in valeurs)


def legende_marqueur_etoile(marqueur) -> str:
    """Légende du marqueur « (*) », ou chaîne vide s'il est absent.

    Le marqueur est restitué au lecteur (il figure dans la source), mais
    accompagné de la seule chose vraie à son sujet : le jeu de données ne
    publie aucune légende.
    """
    if not marqueur:
        return ""
    return (
        " — le nom est suivi du marqueur « (*) » dans le fichier CNCCFP ; "
        "sa signification n'est pas documentée dans le jeu de données."
    )


def calculer_alertes(conn, url_avis_2024: str | None) -> int:
    """Recalcule les alertes de CE pipeline (types effacés puis réinsérés)."""
    quand = datetime.now(timezone.utc).isoformat(timespec="seconds")
    alertes: list[tuple] = []

    # A5 — comptes de campagne rejetés (R) et réformés (AR*).
    regle_rejet = (
        "Décision CNCCFP = 'R' dans le CSV comptes de campagne "
        "législatives 2024 (SOURCES.md §4, alerte A5)."
    )
    regle_reforme = (
        "Décision CNCCFP commençant par 'AR' (approbation après réformation, "
        "mentions conservées) ; montant réformé = dépenses déclarées − retenues "
        "(SOURCES.md §4, alerte A5)."
    )
    base_a5 = "Code électoral, contrôle des comptes de campagne par la CNCCFP (art. L.52-15)."
    for c in conn.execute(
        """SELECT candidat_id, nom, marqueur_etoile, circonscription,
                  depenses_declarees, depenses_retenues, recettes_declarees,
                  remboursement_etat, decision
           FROM campagnes_2024
           WHERE decision_famille IN ('rejete', 'approuve_apres_reformation')
           ORDER BY candidat_id"""
    ):
        rejet = famille_decision(c["decision"]) == "rejete"
        dd, dr = c["depenses_declarees"], c["depenses_retenues"]
        ecart = (dd - dr) if (dd is not None and dr is not None) else None
        entete = (
            f"{c['nom']} ({c['circonscription']}) — décision {c['decision']} ; "
        )
        if compte_sans_montant(c):
            corps = (
                "aucun montant renseigné : tous les postes du compte sont à "
                "zéro dans le fichier CNCCFP (dépenses déclarées, dépenses "
                "retenues, recettes déclarées et remboursement de l'État). "
                "Cette absence de compte exploitable est fréquemment le motif "
                "même de la décision ; elle ne signifie PAS que le candidat "
                "n'a rien dépensé."
            )
        else:
            corps = (
                f"dépenses déclarées : {formater_euros(dd)} ; "
                f"retenues : {formater_euros(dr)} ; "
                + (f"écart : {formater_euros(ecart)} ; " if ecart is not None else "")
                + f"remboursement État : {formater_euros(c['remboursement_etat'])}"
            )
        detail = entete + corps + legende_marqueur_etoile(c["marqueur_etoile"])
        if rejet:
            alertes.append(
                (
                    f"FIN-CAMP-REJ-{c['candidat_id']}",
                    "financement_campagne_rejetee", "haute",
                    f"Compte de campagne rejeté — {c['nom']}",
                    detail, regle_rejet, base_a5, URL_DATASET_LEG2024, quand,
                )
            )
        else:
            alertes.append(
                (
                    f"FIN-CAMP-REF-{c['candidat_id']}",
                    "financement_campagne_reformee", "moyenne",
                    f"Compte de campagne réformé — {c['nom']}",
                    detail, regle_reforme, base_a5, URL_DATASET_LEG2024, quand,
                )
            )

    # A4 (part calculable) — dépendance à l'aide publique, dernier exercice.
    regle_dep = (
        f"Aide publique (1ère + 2nde fractions + autres aides publiques) "
        f"≥ {SEUIL_DEPENDANCE_RATIO:.0%} des produits totaux ET produits totaux "
        f"≥ {formater_euros(SEUIL_DEPENDANCE_PRODUITS)}, dernier exercice publié, "
        "comptes en euros (SOURCES.md §4, alerte A4 — indicateur de structure "
        "de financement, pas une infraction)."
    )
    base_a4 = "Loi n° 88-227 du 11 mars 1988 relative à la transparence financière de la vie politique."
    for p in conn.execute(
        """SELECT p.id, p.nom, c.exercice, c.produits_total,
                  COALESCE(c.aide_publique_f1,0) + COALESCE(c.aide_publique_f2,0)
                    + COALESCE(c.autres_aides_publiques,0) AS aide
           FROM partis_comptes c JOIN partis p ON p.id = c.parti_id
           WHERE c.exercice = (SELECT MAX(exercice) FROM partis_comptes)
             AND c.unite = 'EUR'
             AND c.produits_total >= ?
             AND COALESCE(c.aide_publique_f1,0) + COALESCE(c.aide_publique_f2,0)
                 + COALESCE(c.autres_aides_publiques,0)
                 >= ? * c.produits_total
           ORDER BY p.id""",
        (SEUIL_DEPENDANCE_PRODUITS, SEUIL_DEPENDANCE_RATIO),
    ):
        ratio = p["aide"] / p["produits_total"]
        alertes.append(
            (
                f"FIN-PARTI-DEP-{p['exercice']}-{p['id']}",
                "financement_parti_dependance_aide", "info",
                f"Parti financé à {ratio:.0%} par l'aide publique — {p['nom']}",
                # ATTENTION — le motif « (ratio X.X%) » est une CLÉ DE TRI :
                # app/src/lib/queries/financement.ts classe ces alertes par
                # CAST(substr(detail, instr(detail,'(ratio ') + 7) AS REAL).
                # Le point décimal doit rester un POINT : SQLite lit
                # CAST('92,7%' AS REAL) = 92.0 et perdrait la décimale. Ce
                # fragment est donc laissé tel quel, seuls les montants en
                # euros passent par le formateur français.
                f"Exercice {p['exercice']} : aide publique "
                f"{formater_euros(p['aide'])} pour "
                f"{formater_euros(p['produits_total'])} de produits totaux "
                f"(ratio {ratio:.1%}).",
                regle_dep, base_a4, URL_DATASET_PARTIS, quand,
            )
        )

    # A4 (part documentaire) — partis privés d'aide pour manquement : la liste
    # officielle n'existe qu'en PDF au JO (avis CNCCFP) → alerte documentaire,
    # traitement manuel annuel (SOURCES.md §4 A4 et 10-critique M7).
    dernier_ex = conn.execute("SELECT MAX(exercice) AS m FROM partis_comptes").fetchone()["m"]
    if dernier_ex is not None:
        alertes.append(
            (
                f"FIN-PARTI-PRIVE-{dernier_ex}",
                "financement_parti_prive_aide", "info",
                f"Partis privés d'aide publique pour manquement (exercice {dernier_ex}) : "
                "liste publiée uniquement en PDF au JO",
                "L'avis annuel CNCCFP listant les partis n'ayant pas respecté "
                "leurs obligations comptables (perte de l'aide publique) n'est "
                "publié qu'en PDF au Journal officiel — aucune donnée "
                "structurée. Traitement manuel annuel à déclencher (détection "
                "du texte par P6/S3), la liste n'est pas recalculable ici.",
                "Avis CNCCFP annuel publié au JO, en PDF seulement "
                "(SOURCES.md §4, alerte A4 ; mitigation 10-critique M7).",
                base_a4,
                url_avis_2024 or URL_DATASET_PARTIS,
                quand,
            )
        )

    with conn:
        marqueurs = ",".join("?" for _ in TYPES_ALERTES)
        conn.execute(f"DELETE FROM alertes WHERE type IN ({marqueurs})", TYPES_ALERTES)
        conn.executemany(
            """INSERT INTO alertes
                   (id, type, gravite, titre, detail, regle, base_legale,
                    source_url, date_calcul)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            alertes,
        )
    return len(alertes)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def main() -> int:
    depart = time.monotonic()
    try:
        session = session_http()
        ressources = resoudre_ressources(session)

        conn = db.init_db()
        creer_tables(conn)

        comptes: dict[int, list[dict]] = {}
        for exercice in EXERCICES:
            chemin = telecharger(
                ressources["partis"][exercice],
                f"financement/comptes-partis-{exercice}.csv",
                max_age_heures=MAX_AGE_HEURES,
                session=session,
            )
            comptes[exercice] = parser_partis(chemin.read_bytes(), exercice)
            log.info("exercice %d : %d partis", exercice, len(comptes[exercice]))

        nb_partis, nb_comptes = charger_partis(conn, comptes)

        chemin_campagnes = telecharger(
            ressources["campagnes"],
            "financement/comptes-campagne-legislatives-2024.csv",
            max_age_heures=MAX_AGE_HEURES,
            session=session,
        )
        lignes_campagnes = parser_campagnes(chemin_campagnes.read_bytes())
        nb_candidats = charger_campagnes(conn, lignes_campagnes)

        nb_decrets = charger_decrets_aide(conn)
        creer_vues(conn)
        nb_alertes = calculer_alertes(conn, ressources["avis_2024"])

        db.upsert_meta(
            conn,
            source_id="S25",
            nom="CNCCFP — comptes des partis et groupements politiques",
            url=URL_DATASET_PARTIS,
            licence="Licence Ouverte",
            frequence="annuelle",
            date_donnees="2024-12-31",
            lignes=nb_comptes,
            notes="Exercices 2021-2024 ; l'exercice 2024 (dernier possible, "
                  "dépôt N+1, publication N+2) est paru le 10/02/2026 ; "
                  "exercice 2025 attendu ~T1 2027. 2 lignes en XPF et 1 sans "
                  "unité (2023) exclues des agrégats en euros.",
        )
        db.upsert_meta(
            conn,
            source_id="S29",
            nom="CNCCFP — comptes de campagne, législatives 2024",
            url=URL_DATASET_LEG2024,
            licence="Licence Ouverte",
            frequence="par scrutin",
            date_donnees="2024-07-07",
            lignes=nb_candidats,
            notes="Scrutin des 30/06 et 07/07/2024, CSV publié le 29/07/2025 "
                  "(cp1252, 6 lignes de garde, mojibake réparé). Casse des "
                  "noms réparée à l'ingestion : le CSV source livre "
                  "« M. EL\xe9LOU\xe9-VALMAR » (0xE9 = « é » minuscule) — "
                  "défaut de la source, pas du pipeline. Marqueur « (*) » "
                  "(51 noms) sorti du nom, signification non documentée par "
                  "la CNCCFP. Municipales 2026 : aucun dataset au 19/08/2026, "
                  "publication attendue fin 2026/2027 — à surveiller.",
        )
        dernier_decret = max(DECRETS_AIDE_PUBLIQUE, key=lambda d: d["annee"])
        db.upsert_meta(
            conn,
            source_id="S37",
            nom="Décrets annuels d'aide publique aux partis (enveloppe nationale)",
            url=dernier_decret["source_url"],
            licence="Texte officiel (JORF)",
            frequence="annuelle",
            date_donnees="2026-03-03",
            lignes=nb_decrets,
            notes="Enveloppes NATIONALES fixées par décret, "
                  + ", ".join(
                      f"{d['annee']} : {formater_euros(d['montant_total_eur'])}"
                      for d in DECRETS_AIDE_PUBLIQUE
                  )
                  + ". Totaux seuls (tableau par parti non publié en données ; "
                  "Légifrance anti-bot) — répartition par parti = v2. Le "
                  "décret n° 2024-77 n'a pas pu être re-vérifié sur Légifrance "
                  "(HTTP 403 au 20/08/2026) : valeur reprise du diagnostic "
                  "interne, à confirmer. Ces enveloppes ne sont PAS "
                  "comparables aux aides inscrites aux comptes des partis "
                  "(partis_comptes), qui sont des déclarations cumulées.",
        )

        duree = time.monotonic() - depart
        log.info(
            "OK en %.1f s — %d partis, %d lignes de comptes (2021-2024), "
            "%d candidats législatives 2024, %d alertes, %d décret(s) d'aide "
            "publique (totaux nationaux seuls)",
            duree, nb_partis, nb_comptes, nb_candidats, nb_alertes, nb_decrets,
        )
        conn.close()
        return 0
    except Exception:
        log.exception("échec du pipeline financement — base laissée en l'état antérieur")
        return 1


if __name__ == "__main__":
    sys.exit(main())

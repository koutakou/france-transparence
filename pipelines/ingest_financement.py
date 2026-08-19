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
- S37 — décret n° 2026-149 du 03/03/2026 (JO du 04/03/2026) : aide publique
  2026 = 64 262 871,05 €. AUCUN fichier exploitable par parti n'existe
  (tableau dans le corps du décret, Légifrance anti-bot, pas de CSV — vérifié
  le 19/08/2026) → seul le TOTAL national est inséré, en fait sourcé ;
  la répartition par parti reste en v2 (SOURCES.md S37). L'aide perçue par
  parti et par exercice reste lisible dans partis_comptes (2021-2024).

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
- campagnes_2024 : 1 ligne = candidat — candidat_id, nom (civilité incluse,
  tel que publié), scrutin, circonscription, departement, code_departement,
  nuance, depenses_declarees, depenses_retenues, recettes_declarees,
  recettes_retenues, remboursement_etat (colonne « RFE » = remboursement
  forfaitaire de l'État), decision (code CNCCFP brut : A, AM, AR, ARM, ARR,
  ARRR, ARRRM, R, AD, HD, DD — les suffixes sont conservés tels quels),
  decision_famille (normalisation mécanique documentée dans FAMILLES_DECISION).
- partis_aide_2026 : faits sourcés — annee, montant_total_eur, perimetre,
  reference, source_url, note.
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

# Décret annuel d'aide publique (S37) — faits sourcés, cf. docstring.
AIDE_2026_TOTAL_EUR = 64_262_871.05
AIDE_2026_REFERENCE = "Décret n° 2026-149 du 3 mars 2026 (JO du 04/03/2026)"
AIDE_2026_URL = "https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000053613045"

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

CREATE TABLE IF NOT EXISTS partis_aide_2026 (
    annee             INTEGER PRIMARY KEY,
    montant_total_eur REAL NOT NULL,
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
                "nom": champs[1].strip(),
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
        resultat.append(
            {
                "candidat_id": champs[0].strip(),
                "nom": champs[1].strip(),
                "scrutin": champs[2].strip() or None,
                "circonscription": champs[3].strip(),
                "departement": champs[4].strip() or None,
                "code_departement": champs[5].strip() or None,
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
    conn.executescript(_SCHEMA)
    conn.commit()


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
                (candidat_id, nom, scrutin, circonscription, departement,
                 code_departement, nuance, depenses_declarees, depenses_retenues,
                 recettes_declarees, recettes_retenues, remboursement_etat,
                 decision, decision_famille)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    l["candidat_id"], l["nom"], l["scrutin"], l["circonscription"],
                    l["departement"], l["code_departement"], l["nuance"],
                    l["depenses_declarees"], l["depenses_retenues"],
                    l["recettes_declarees"], l["recettes_retenues"],
                    l["remboursement_etat"], l["decision"], l["decision_famille"],
                )
                for l in lignes
            ],
        )
    return len(lignes)


def charger_aide_2026(conn) -> None:
    """Fait sourcé S37 : total national 2026 seul (cf. docstring module)."""
    with conn:
        conn.execute("DELETE FROM partis_aide_2026")
        conn.execute(
            """
            INSERT INTO partis_aide_2026
                (annee, montant_total_eur, perimetre, reference, source_url, note)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                2026,
                AIDE_2026_TOTAL_EUR,
                "Total national, 1ère + 2nde fractions",
                AIDE_2026_REFERENCE,
                AIDE_2026_URL,
                "Répartition par parti non publiée en données exploitables "
                "(tableau dans le corps du décret, Légifrance anti-bot — "
                "constat du 19/08/2026, SOURCES.md S37) : extraction par "
                "parti = v2. L'aide perçue par parti figure dans "
                "partis_comptes (exercices 2021-2024).",
            ),
        )


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
        """SELECT candidat_id, nom, circonscription, depenses_declarees,
                  depenses_retenues, remboursement_etat, decision
           FROM campagnes_2024
           WHERE decision_famille IN ('rejete', 'approuve_apres_reformation')
           ORDER BY candidat_id"""
    ):
        rejet = famille_decision(c["decision"]) == "rejete"
        dd, dr = c["depenses_declarees"], c["depenses_retenues"]
        ecart = (dd - dr) if (dd is not None and dr is not None) else None
        detail = (
            f"{c['nom']} ({c['circonscription']}) — décision {c['decision']} ; "
            f"dépenses déclarées : {dd if dd is not None else 'n.c.'} € ; "
            f"retenues : {dr if dr is not None else 'n.c.'} € ; "
            + (f"écart : {round(ecart, 2)} € ; " if ecart is not None else "")
            + f"remboursement État : {c['remboursement_etat'] if c['remboursement_etat'] is not None else 'n.c.'} €"
        )
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
        f"≥ {SEUIL_DEPENDANCE_PRODUITS:,.0f} €, dernier exercice publié, "
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
                f"Exercice {p['exercice']} : aide publique {round(p['aide'], 2)} € "
                f"pour {round(p['produits_total'], 2)} € de produits totaux "
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

        charger_aide_2026(conn)
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
                  "(cp1252, 6 lignes de garde, mojibake réparé). Municipales "
                  "2026 : aucun dataset au 19/08/2026, publication attendue "
                  "fin 2026/2027 — à surveiller.",
        )
        db.upsert_meta(
            conn,
            source_id="S37",
            nom="Décret annuel d'aide publique aux partis (2026)",
            url=AIDE_2026_URL,
            licence="Texte officiel (JORF)",
            frequence="annuelle",
            date_donnees="2026-03-03",
            lignes=1,
            notes="Décret n° 2026-149 du 03/03/2026 : 64 262 871,05 € en "
                  "2 fractions. Total seul (tableau par parti non publié en "
                  "données ; Légifrance anti-bot) — répartition par parti = v2.",
        )

        duree = time.monotonic() - depart
        log.info(
            "OK en %.1f s — %d partis, %d lignes de comptes (2021-2024), "
            "%d candidats législatives 2024, %d alertes, aide 2026 : total seul",
            duree, nb_partis, nb_comptes, nb_candidats, nb_alertes,
        )
        conn.close()
        return 0
    except Exception:
        log.exception("échec du pipeline financement — base laissée en l'état antérieur")
        return 1


if __name__ == "__main__":
    sys.exit(main())

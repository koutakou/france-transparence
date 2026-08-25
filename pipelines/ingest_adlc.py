"""P29 — Sanctions financières de l'Autorité de la concurrence (S52).

Sources (data.gouv.fr, organisation autorite-de-la-concurrence) :
- CSV des sanctions 2009+ (euros) — dataset
  entreprises-sanctionnees-financierement-par-lautorite-de-la-concurrence-depuis-2009
- CSV de métadonnées (titre, date, URL, secteurs) — dataset
  decisions-publiees-par-lautorite-de-la-concurrence-depuis-1988

Licence : Licence Ouverte 2.0 (Etalab) — champ API `lov2` ; texte légal
relu https://www.data.gouv.fr/pages/legal/licences/etalab-2.0/ (25/08/2026).

CE PIPELINE N'EST PAS S39, NI S13, NI UN MARCHÉ PUBLIC
------------------------------------------------------
S39 = jaune opérateurs du PLF (liste, 0 €). On ne recycle pas son
`source_id`. S13 = exécution du budget général. Une amende ADLC n'est
pas une recette de l'État A, pas un recouvrement (le producteur le dit :
« avant éventuels appels et recours »), pas un marché DECP/BOAMP.
0 SIREN dans le CSV → aucune jointure DECP / HATVP.

N'ingère PAS le JSON de texte intégral (~219 Mo), PAS le xlsx 2021
(couverture 2009–2020). Leçon S38 : le texte intégral n'entre pas en base.

Grain du héros = SUM(Montant total) **une fois par id_decision**.
SUM(Montant individuel) et la somme naïve des totaux répétés sur
chaque ligne d'entreprise sont des chiffres faux (filiales / solidarité
du groupe ; le total de décision est recopié sur chaque ligne).

Personnes physiques : préfixe civil (M. / Mme / Mlle) + revue des deux
noms restants sans préfixe (J. Grenot, R. Vecchietti). Hors table
nominative. Si une décision n'a plus aucune personne morale, elle
sort aussi du héros (18-D-19). C. Steinweg est une raison sociale
(gardée, à côté de C. Steinweg Belgium N.V.).

Une même dénomination peut apparaître deux fois dans une décision
avec deux montants : ce sont deux lignes, pas deux entreprises.
On ne DISTINCT pas les noms.

`date_donnees` = date de la dernière décision **sanctionnée** encore
dans `adlc_decisions`, jamais `last_modified` du dataset (le dump
mensuel/hebdo peut bouger sans nouvelle amende).

Cadence déclarée : mensuelle (jeu euros).

Exécution : python -m pipelines.ingest_adlc
Base : FT_DB_PATH sinon data/france.db. Réécriture idempotente
(DELETE puis INSERT dans une transaction), puis upsert_meta('S52', …).
Échec → exit ≠ 0, base intacte.

Tables NOUVELLES (`adlc_*`) : pas un IF NOT EXISTS sur une table
existante, pas un ALTER.
"""

from __future__ import annotations

import csv
import io
import re
import sys
from collections import defaultdict
from pathlib import Path

import requests

from pipelines import db
from pipelines.common import (
    assainir_texte,
    obtenir_logger,
    session_http,
    telecharger,
)

log = obtenir_logger("adlc")

SOURCE_ID = "S52"
NOM_SOURCE = (
    "Sanctions financières de l'Autorité de la concurrence (2009+)"
)
LICENCE = "Licence Ouverte 2.0 (Etalab)"
FREQUENCE = "mensuelle"

URL_DATASET_SANCTIONS = (
    "https://www.data.gouv.fr/api/1/datasets/"
    "entreprises-sanctionnees-financierement-par-lautorite-de-la-concurrence-depuis-2009/"
)
URL_DATASET_META = (
    "https://www.data.gouv.fr/api/1/datasets/"
    "decisions-publiees-par-lautorite-de-la-concurrence-depuis-1988/"
)
URL_PAGE = (
    "https://www.data.gouv.fr/datasets/"
    "entreprises-sanctionnees-financierement-par-lautorite-de-la-concurrence-depuis-2009"
)

TITRE_SANCTIONS = "sanctions-depuis-2009.csv"
TITRE_META = "metadata-publications-adlc.csv"

# Le JSON de texte intégral dépasse 200 Mo ; le CSV de métadonnées ~2,4 Mo.
# Un fichier au-delà de cette borne n'est pas le CSV attendu.
OCTETS_MAX_CSV = 10_000_000

CACHE_HEURES = 23
CACHE_SANCTIONS = "adlc/sanctions-depuis-2009.csv"
CACHE_META = "adlc/metadata-publications-adlc.csv"

COLONNES_SANCTIONS = (
    "id_decision",
    "Entreprise",
    "Montant individuel",
    "Montant total",
    "Annee",
)
COLONNES_META = (
    "id_decision",
    "sous_titre",
    "date_decision_year",
    "date_decision_datetime",
    "liste_secteurs",
    "entreprises_concernees",
    "url_site",
    "Montant sanction",
)

# Préfixe civil du CSV producteur. Les cinq lignes mesurées le 25/08/2026
# (19-D-19, 11-D-02) portent « M. ».
_RX_CIVIL = re.compile(r"^(M\.|Mme|Mlle)\s")

# Revue manuelle des noms sans préfixe civil (qualification 25/08/2026).
# C. Steinweg n'y figure pas : raison sociale, conservée.
PERSONNES_SANS_CIVIL = frozenset(
    {
        ("18-D-19", "J. Grenot"),
        ("09-D-25", "R. Vecchietti"),
    }
)

N_DECISIONS_MIN = 50
N_DECISIONS_MAX = 500
HEROS_MIN = 1_000_000_000.0
HEROS_MAX = 50_000_000_000.0

NOTES = (
    "CSV sanctions 2009+ joint aux métadonnées (titre, date, URL) ; "
    "grain = SUM(Montant total) une fois par id_decision ; pas "
    "SUM(individuel) ni totaux répétés sur chaque ligne ; personnes "
    "physiques hors table nominative ; décision 18-D-19 hors héros "
    "(particulier seul) ; date_donnees = date de la dernière décision "
    "sanctionnée, jamais last_modified du dataset ; JSON texte intégral "
    "non ingéré ; xlsx 2021 non ingéré ; 0 SIREN, pas de jointure "
    "DECP/HATVP ; pas un marché public, pas une recette S13, pas un "
    "recouvrement (avant appels et recours) ; source_id S52, jamais S39"
)

_DDL = """
CREATE TABLE IF NOT EXISTS adlc_decisions (
    id_decision    TEXT PRIMARY KEY,
    montant_total  REAL NOT NULL CHECK (montant_total >= 0),
    date_decision  TEXT NOT NULL,
    annee          INTEGER NOT NULL,
    sous_titre     TEXT,
    url_site       TEXT,
    secteurs       TEXT
);
CREATE TABLE IF NOT EXISTS adlc_lignes (
    id_decision          TEXT NOT NULL,
    n_ligne              INTEGER NOT NULL,
    denomination         TEXT NOT NULL,
    montant_individuel   REAL NOT NULL CHECK (montant_individuel >= 0),
    annee                INTEGER NOT NULL,
    PRIMARY KEY (id_decision, n_ligne),
    FOREIGN KEY (id_decision) REFERENCES adlc_decisions(id_decision)
);
"""


def est_personne_physique(id_decision: str, denomination: str) -> bool:
    """True si la ligne nomme une personne physique, pas une personne morale."""
    nom = (denomination or "").strip()
    if _RX_CIVIL.match(nom):
        return True
    return (id_decision, nom) in PERSONNES_SANS_CIVIL


def _euros(valeur: str, *, champ: str) -> float:
    s = (valeur or "").strip().replace("\u00a0", "").replace(" ", "").replace(",", ".")
    if not s:
        raise ValueError(f"{champ} vide")
    try:
        n = float(s)
    except ValueError as exc:
        raise ValueError(f"{champ} illisible : {valeur!r}") from exc
    if n < 0:
        raise ValueError(f"{champ} négatif : {valeur!r}")
    return n


def _lire_csv(chemin: Path, colonnes: tuple[str, ...]) -> list[dict[str, str]]:
    brut = chemin.read_bytes()
    if len(brut) > OCTETS_MAX_CSV:
        raise ValueError(
            f"{chemin.name} trop volumineux ({len(brut)} o) — "
            "ce n'est pas le CSV attendu (JSON texte intégral écarté)"
        )
    texte = brut.decode("utf-8-sig")
    lecteur = csv.DictReader(io.StringIO(texte))
    champs = tuple(lecteur.fieldnames or ())
    if champs != colonnes:
        raise ValueError(
            f"{chemin.name} : colonnes {champs} ≠ {colonnes}"
        )
    return list(lecteur)


def extraire_sanctions(chemin: Path) -> list[dict]:
    """Lignes brutes du CSV euros, montants lus, dénomination assainie."""
    lignes: list[dict] = []
    for n, row in enumerate(_lire_csv(chemin, COLONNES_SANCTIONS), start=1):
        iid = (row["id_decision"] or "").strip()
        if not iid:
            raise ValueError(f"sanctions ligne {n} : id_decision vide")
        nom = assainir_texte(row["Entreprise"]) or ""
        if not nom:
            raise ValueError(f"sanctions {iid} : dénomination vide")
        annee_s = (row["Annee"] or "").strip()
        try:
            annee = int(annee_s)
        except ValueError as exc:
            raise ValueError(f"sanctions {iid} : année {annee_s!r}") from exc
        lignes.append(
            {
                "id_decision": iid,
                "denomination": nom,
                "montant_individuel": _euros(
                    row["Montant individuel"], champ="Montant individuel"
                ),
                "montant_total": _euros(
                    row["Montant total"], champ="Montant total"
                ),
                "annee": annee,
            }
        )
    if not lignes:
        raise ValueError("CSV sanctions vide")
    return lignes


def extraire_meta(chemin: Path) -> dict[str, dict]:
    """Métadonnées indexées par id_decision (première occurrence).

    Les 5 id dupliqués du dump 25/08 sont des DCC/A, hors sanctions.
    Un conflit de date/titre/URL sur un id sanctionné échoue plus bas.
    """
    index: dict[str, dict] = {}
    for row in _lire_csv(chemin, COLONNES_META):
        iid = (row["id_decision"] or "").strip()
        if not iid:
            continue
        date = (row["date_decision_datetime"] or "").strip()
        fiche = {
            "sous_titre": assainir_texte(row["sous_titre"]),
            "date_decision": date,
            "secteurs": assainir_texte(row["liste_secteurs"]),
            "url_site": (row["url_site"] or "").strip() or None,
        }
        if iid in index:
            # Cinq id dupliqués dans le dump du 25/08 (DCC/A, hors
            # sanctions). Les 189 id du CSV euros n'ont aucun doublon.
            # On conserve la première occurrence.
            continue
        index[iid] = fiche
    if not index:
        raise ValueError("CSV métadonnées vide")
    return index


def assembler(
    lignes_brutes: list[dict],
    meta: dict[str, dict],
) -> tuple[list[dict], list[dict]]:
    """Décisions (héros) + lignes nominatives (personnes morales).

    Une décision dont toutes les lignes sont des personnes physiques
    sort du héros. Le Montant total ADLC est conservé tel quel pour
    les décisions qui gardent au moins une personne morale — y compris
    quand une ligne physique a été retirée (09-D-25).
    """
    par_decision: dict[str, list[dict]] = defaultdict(list)
    totaux: dict[str, float] = {}
    annees: dict[str, int] = {}
    for ligne in lignes_brutes:
        iid = ligne["id_decision"]
        tot = ligne["montant_total"]
        if iid in totaux and abs(totaux[iid] - tot) > 0.01:
            raise ValueError(
                f"{iid} : Montant total instable "
                f"({totaux[iid]} vs {tot})"
            )
        totaux[iid] = tot
        annees[iid] = ligne["annee"]
        par_decision[iid].append(ligne)

    decisions: list[dict] = []
    lignes_out: list[dict] = []
    for iid, groupe in par_decision.items():
        morales = [
            l
            for l in groupe
            if not est_personne_physique(iid, l["denomination"])
        ]
        if not morales:
            continue
        fiche = meta.get(iid)
        if fiche is None:
            raise ValueError(f"{iid} : absent des métadonnées")
        date = fiche["date_decision"]
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date or ""):
            raise ValueError(f"{iid} : date_decision {date!r}")
        decisions.append(
            {
                "id_decision": iid,
                "montant_total": totaux[iid],
                "date_decision": date,
                "annee": annees[iid],
                "sous_titre": fiche["sous_titre"],
                "url_site": fiche["url_site"],
                "secteurs": fiche["secteurs"],
            }
        )
        for n, l in enumerate(morales, start=1):
            lignes_out.append(
                {
                    "id_decision": iid,
                    "n_ligne": n,
                    "denomination": l["denomination"],
                    "montant_individuel": l["montant_individuel"],
                    "annee": l["annee"],
                }
            )
    if not decisions:
        raise ValueError("aucune décision conservée après filtre personnes")
    return decisions, lignes_out


def controler_grain(
    lignes_brutes: list[dict],
    decisions: list[dict],
    lignes: list[dict],
) -> None:
    """Filet de grain : les deux sommes interdites ne sont pas le héros."""
    heros = sum(d["montant_total"] for d in decisions)
    somme_ind = sum(l["montant_individuel"] for l in lignes_brutes)
    somme_naive = sum(l["montant_total"] for l in lignes_brutes)
    if abs(somme_ind - heros) < 0.5:
        raise ValueError(
            "SUM(individuel) = héros — le grain id_decision a disparu"
        )
    if abs(somme_naive - heros) < 0.5:
        raise ValueError(
            "somme naïve des totaux répétés = héros — "
            "le CSV n'a plus une ligne par entreprise"
        )
    ids = {d["id_decision"] for d in decisions}
    if "18-D-19" in ids:
        raise ValueError("18-D-19 (particulier seul) encore dans le héros")
    for l in lignes:
        if est_personne_physique(l["id_decision"], l["denomination"]):
            raise ValueError(
                f"personne physique encore nominative : "
                f"{l['id_decision']} {l['denomination']!r}"
            )
    if any(l["denomination"].startswith("M. ") for l in lignes):
        raise ValueError("préfixe civil M. encore dans adlc_lignes")


def controler_ampleur(
    lignes_brutes: list[dict],
    decisions: list[dict],
    lignes: list[dict],
) -> None:
    """Grain + bornes d'ordre de grandeur du corpus live (pas des fixtures)."""
    controler_grain(lignes_brutes, decisions, lignes)
    n = len(decisions)
    if not (N_DECISIONS_MIN <= n <= N_DECISIONS_MAX):
        raise ValueError(
            f"{n} décisions conservées, hors [{N_DECISIONS_MIN}, {N_DECISIONS_MAX}]"
        )
    heros = sum(d["montant_total"] for d in decisions)
    if not (HEROS_MIN < heros < HEROS_MAX):
        raise ValueError(
            f"héros {heros:.0f} € hors ]{HEROS_MIN:.0f}, {HEROS_MAX:.0f}["
        )


def _ressource_csv(
    dataset: dict,
    titre_attendu: str,
    octets_max: int,
) -> dict[str, str]:
    """Choisit la ressource CSV par son titre. JSON et xlsx : échec franc."""
    titres: list[str] = []
    for ressource in dataset.get("resources") or []:
        titre = (ressource.get("title") or "").strip()
        titres.append(titre)
        if titre_attendu.lower() not in titre.lower():
            continue
        fmt = (ressource.get("format") or "").lower()
        mime = (ressource.get("mime") or "").lower()
        if (
            "json" in fmt
            or "json" in mime
            or titre.lower().endswith(".json")
        ):
            raise RuntimeError(
                f"ressource « {titre} » est du JSON — non ingéré"
            )
        if "xls" in fmt or titre.lower().endswith((".xlsx", ".xls")):
            raise RuntimeError(
                f"ressource « {titre} » est un tableur — non ingéré"
            )
        octets = int(ressource.get("filesize") or 0)
        if octets > octets_max:
            raise RuntimeError(
                f"ressource « {titre} » trop volumineuse "
                f"({octets} o > {octets_max})"
            )
        url = ressource.get("url")
        if not url:
            raise RuntimeError(f"ressource « {titre} » sans URL")
        return {
            "url": url,
            "titre": titre,
            "octets": str(octets),
        }
    raise RuntimeError(
        f"ressource « {titre_attendu} » absente ; présentes : {titres}"
    )


def resoudre_ressources(
    session: requests.Session | None = None,
    timeout: int = 60,
) -> tuple[dict[str, str], dict[str, str]]:
    """API data.gouv : CSV sanctions + CSV métadonnées, jamais le JSON."""
    s = session or session_http()
    r1 = s.get(URL_DATASET_SANCTIONS, timeout=timeout)
    r1.raise_for_status()
    r2 = s.get(URL_DATASET_META, timeout=timeout)
    r2.raise_for_status()
    sanctions = _ressource_csv(r1.json(), TITRE_SANCTIONS, OCTETS_MAX_CSV)
    meta = _ressource_csv(r2.json(), TITRE_META, OCTETS_MAX_CSV)
    return sanctions, meta


def ecrire_db(
    conn,
    decisions: list[dict],
    lignes: list[dict],
) -> str:
    """DELETE+INSERT en transaction, puis upsert_meta S52. Retourne date_donnees."""
    if not decisions or not lignes:
        raise ValueError("écriture vide")
    date_donnees = max(d["date_decision"] for d in decisions)
    conn.executescript(_DDL)
    with conn:
        conn.execute("DELETE FROM adlc_lignes")
        conn.execute("DELETE FROM adlc_decisions")
        conn.executemany(
            """INSERT INTO adlc_decisions
               (id_decision, montant_total, date_decision, annee,
                sous_titre, url_site, secteurs)
               VALUES (:id_decision, :montant_total, :date_decision, :annee,
                       :sous_titre, :url_site, :secteurs)""",
            decisions,
        )
        conn.executemany(
            """INSERT INTO adlc_lignes
               (id_decision, n_ligne, denomination, montant_individuel, annee)
               VALUES (:id_decision, :n_ligne, :denomination,
                       :montant_individuel, :annee)""",
            lignes,
        )
    db.upsert_meta(
        conn,
        source_id=SOURCE_ID,
        nom=NOM_SOURCE,
        url=URL_PAGE,
        licence=LICENCE,
        frequence=FREQUENCE,
        date_donnees=date_donnees,
        lignes=len(decisions),
        notes=NOTES,
    )
    return date_donnees


def ingere_depuis_fichiers(
    conn,
    chemin_sanctions: Path,
    chemin_meta: Path,
    *,
    verifier_ampleur: bool = True,
) -> str:
    """Parse, assemble, contrôle, écrit. Point d'entrée des tests.

    `verifier_ampleur=False` : fixtures inventées (le grain reste contrôlé).
    """
    brutes = extraire_sanctions(chemin_sanctions)
    meta = extraire_meta(chemin_meta)
    decisions, lignes = assembler(brutes, meta)
    if verifier_ampleur:
        controler_ampleur(brutes, decisions, lignes)
    else:
        controler_grain(brutes, decisions, lignes)
    return ecrire_db(conn, decisions, lignes)


def main() -> int:
    try:
        session = session_http()
        res_s, res_m = resoudre_ressources(session=session)
        brut_s = telecharger(
            res_s["url"],
            CACHE_SANCTIONS,
            max_age_heures=CACHE_HEURES,
            session=session,
        )
        brut_m = telecharger(
            res_m["url"],
            CACHE_META,
            max_age_heures=CACHE_HEURES,
            session=session,
        )
        conn = db.init_db()
        date_donnees = ingere_depuis_fichiers(conn, Path(brut_s), Path(brut_m))
        n = conn.execute("SELECT count(*) AS n FROM adlc_decisions").fetchone()[
            "n"
        ]
        conn.close()
        log.info(
            "adlc: %d décisions, données au %s",
            n,
            date_donnees,
        )
        return 0
    except Exception:
        log.exception("échec de l'ingestion S52 — base laissée intacte")
        return 1


if __name__ == "__main__":
    sys.exit(main())

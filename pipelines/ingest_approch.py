"""Ingestion S9 — APProch, projets d'achats publics à venir (data.economie).

Source : https://data.economie.gouv.fr, dataset `projets-dachats-publics`
(DAE/AIFE, Licence Ouverte v2.0, sans clé). Intentions d'achat publiées en
amont de toute consultation — l'étage que ni le BOAMP ni les DECP ne
couvrent (« ce que l'État s'apprête à acheter »). Couverture : surtout
État et hôpitaux, collectivités volontaires.

Table produite (réécriture complète à chaque run, en transaction) :

- marches_a_venir — projets dont la publication est prévue dans le futur :
    code (PK), intitule, description, statut, acheteur_siren (re-paddé à
    9 chiffres — pas de nom d'acheteur dans la source, résolution via le
    référentiel entités/S10), categorie_achat, code_cpv,
    montant_estime_tranche (texte, ex. « 1M - 5M€ » — jamais sommable),
    date_prev_publication, date_cible_remise_offres, type_procedure,
    duree_prev_mois, departements (JSON), lien_consultation.

Module UI : Commande publique (« marchés à venir », tri par date
prévisionnelle de publication).

Notes de véracité (aucune donnée inventée) :
- montant : la source ne publie que des tranches en texte → conservées
  telles quelles, NULL si absentes (le front affiche « non publié »).
- SIREN livré en entier par l'export (zéros de tête perdus) → re-paddé.
- valeur de remplissage « CDL » de data.economie → NULL (SOURCES.md §0.5).
- date_donnees (meta_sources) : la source n'a pas de date de publication
  par enregistrement ; on prend la date `data_processed` du dataset
  (dernier traitement réel des données par la plateforme, constaté J-4),
  jamais `metadata_processed`.

Exécution : python -m pipelines.ingest_approch
"""

from __future__ import annotations

import json
import sys
from datetime import date
from urllib.parse import quote, urlencode

from pipelines import db
from pipelines.common import obtenir_logger, session_http, telecharger

log = obtenir_logger("ingest_approch")

SOURCE_ID = "S9"
SOURCE_NOM = "APProch — projets d'achats publics (DAE/AIFE)"
SOURCE_URL = (
    "https://data.economie.gouv.fr/explore/dataset/projets-dachats-publics/"
)
SOURCE_LICENCE = "Licence Ouverte v2.0"
SOURCE_FREQUENCE = "quotidienne"

DATASET_URL = (
    "https://data.economie.gouv.fr"
    "/api/explore/v2.1/catalog/datasets/projets-dachats-publics"
)
EXPORT_URL = DATASET_URL + "/exports/json"

SCHEMA = """
CREATE TABLE IF NOT EXISTS marches_a_venir (
    code                     TEXT PRIMARY KEY,
    intitule                 TEXT,
    description              TEXT,
    statut                   TEXT,
    acheteur_siren           TEXT,          -- 9 chiffres, pas de nom dans la source
    categorie_achat          TEXT,          -- Travaux / Fournitures / Services
    code_cpv                 TEXT,
    montant_estime_tranche   TEXT,          -- tranche texte, NULL = non publié
    date_prev_publication    TEXT NOT NULL, -- ISO date (future à l'ingestion)
    date_cible_remise_offres TEXT,
    type_procedure           TEXT,
    duree_prev_mois          INTEGER,
    departements             TEXT CHECK (departements IS NULL OR json_valid(departements)),
    lien_consultation        TEXT
);
CREATE INDEX IF NOT EXISTS idx_mav_date_publication
    ON marches_a_venir(date_prev_publication);
CREATE INDEX IF NOT EXISTS idx_mav_siren ON marches_a_venir(acheteur_siren);
"""

# ---------------------------------------------------------------------------
# Parsing (fonction pure, testée sur enregistrement réel)
# ---------------------------------------------------------------------------


def _texte(valeur: object) -> str | None:
    """Normalise un champ texte : None/''/'CDL' (remplissage data.economie) → None."""
    if valeur is None:
        return None
    texte = str(valeur).strip()
    if not texte or texte == "CDL":
        return None
    return texte


def parser_projet(rec: dict) -> dict | None:
    """Enregistrement export APProch → ligne marches_a_venir, ou None si
    code/date prévisionnelle manquent.

    L'export livre `code` et `siren_de_l_entite_acheteuse` en entiers :
    re-typés en texte, SIREN re-paddé à 9 chiffres (zéros de tête perdus).
    """
    code = rec.get("code")
    date_publication = _texte(rec.get("date_previsionnelle_de_publication"))
    if code is None or not date_publication:
        return None

    siren = _texte(rec.get("siren_de_l_entite_acheteuse"))
    if siren is not None:
        siren = siren.zfill(9)

    duree = _texte(rec.get("duree_previsionnelle_du_marche"))
    try:
        duree_mois = int(float(duree)) if duree is not None else None
    except ValueError:
        duree_mois = None

    departements = None
    brut_deps = _texte(rec.get("departement_s_d_execution_du_marche"))
    if brut_deps:
        liste = [d.strip() for d in brut_deps.split("|") if d.strip()]
        if liste:
            departements = json.dumps(liste, ensure_ascii=False)

    return {
        "code": str(code),
        "intitule": _texte(rec.get("libelle")),
        "description": _texte(rec.get("description")),
        "statut": _texte(rec.get("statut")),
        "acheteur_siren": siren,
        "categorie_achat": _texte(rec.get("categorie_d_achat")),
        "code_cpv": _texte(rec.get("code_s_cpv")),
        "montant_estime_tranche": _texte(rec.get("montant_estime_du_marche")),
        "date_prev_publication": date_publication,
        "date_cible_remise_offres": _texte(rec.get("date_cible_de_remise_des_offres")),
        "type_procedure": _texte(rec.get("type_de_procedure")),
        "duree_prev_mois": duree_mois,
        "departements": departements,
        "lien_consultation": _texte(rec.get("lien_vers_la_consultation")),
    }


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------


def _date_donnees_dataset(session) -> str:
    """Date `data_processed` du dataset (dernier traitement réel des données).

    La source n'a aucune date par enregistrement ; c'est l'indicateur de
    fraîcheur le plus honnête disponible (jamais `metadata_processed`).
    """
    r = session.get(DATASET_URL, timeout=60)
    r.raise_for_status()
    metas = r.json().get("metas", {}).get("default", {})
    brut = metas.get("data_processed") or metas.get("modified")
    if not brut:
        raise RuntimeError("métadonnées APProch sans data_processed/modified")
    return str(brut)[:10]  # partie date de l'ISO


def _executer() -> None:
    aujourdhui = date.today().isoformat()
    session = session_http()
    date_donnees = _date_donnees_dataset(session)

    url = EXPORT_URL + "?" + urlencode(
        {"where": f"date_previsionnelle_de_publication>=date'{aujourdhui}'"},
        quote_via=quote,
    )
    chemin = telecharger(url, "approch_projets_a_venir.json",
                         max_age_heures=None, session=session)
    with open(chemin, encoding="utf-8") as f:
        brut = json.load(f)
    if not isinstance(brut, list):
        raise RuntimeError("export APProch inattendu (pas une liste JSON)")

    projets, ecartes = [], 0
    for rec in brut:
        ligne = parser_projet(rec)
        if ligne is None:
            ecartes += 1
        else:
            projets.append(ligne)
    if not projets:
        raise RuntimeError("aucun projet d'achat à venir parsé : API changée ?")
    if ecartes:
        log.warning("projets écartés (code/date manquants) : %d", ecartes)
    nb_avec_tranche = sum(
        1 for p in projets if p["montant_estime_tranche"] is not None
    )

    conn = db.init_db()
    try:
        conn.executescript(SCHEMA)
        # Réécriture idempotente en une transaction.
        conn.execute("DELETE FROM marches_a_venir")
        conn.executemany(
            """
            INSERT OR REPLACE INTO marches_a_venir
                (code, intitule, description, statut, acheteur_siren,
                 categorie_achat, code_cpv, montant_estime_tranche,
                 date_prev_publication, date_cible_remise_offres,
                 type_procedure, duree_prev_mois, departements, lien_consultation)
            VALUES (:code, :intitule, :description, :statut, :acheteur_siren,
                    :categorie_achat, :code_cpv, :montant_estime_tranche,
                    :date_prev_publication, :date_cible_remise_offres,
                    :type_procedure, :duree_prev_mois, :departements, :lien_consultation)
            """,
            projets,
        )
        conn.commit()

        db.upsert_meta(
            conn,
            source_id=SOURCE_ID,
            nom=SOURCE_NOM,
            url=SOURCE_URL,
            licence=SOURCE_LICENCE,
            frequence=SOURCE_FREQUENCE,
            date_donnees=date_donnees,
            lignes=len(projets),
            notes=(
                f"{len(projets)} projets à publication future "
                f"(dont {nb_avec_tranche} avec tranche de montant) ; "
                "montants en tranches texte non sommables ; acheteur = SIREN "
                "seul ; date_donnees = data_processed du dataset "
                "(pas de date par enregistrement)"
            ),
        )
    finally:
        conn.close()

    log.info(
        "APProch ingéré : %d marchés à venir (%d avec tranche de montant), "
        "données du %s",
        len(projets), nb_avec_tranche, date_donnees,
    )


def main() -> int:
    try:
        _executer()
    except Exception:
        log.exception("échec de l'ingestion APProch")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

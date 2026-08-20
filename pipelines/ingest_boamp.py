"""Ingestion S2 — BOAMP, annonces de marchés publics (API Opendatasoft DILA).

Source : https://boamp-datadila.opendatasoft.com, dataset `boamp` (licence
etalab-2.0, sans clé, quotidien — annonces du jour présentes le matin même).
Le plafond `/records` (offset+limit ≤ 10 000) est contourné partout par
`/exports/json` (streaming filtrable, cf. SOURCES.md §0.1 et fiche S2).

Tables produites (réécriture complète à chaque run, en transaction) :

- ao_en_cours — appels d'offres dont la date limite de réponse est future
  ET plausible (écart parution → limite ≤ 20 ans, cf.
  ECART_MAX_LIMITE_ANNEES) :
    idweb (PK), objet, acheteur, nature, nature_libelle, famille,
    famille_libelle, type_marche (JSON), type_procedure, procedure_libelle,
    descripteurs (JSON), departements (JSON), montant_estime (EUR, NULL si
    non publié), devise, date_parution, date_limite_reponse, url_avis,
    annulee (0/1), rectifiee_par (idweb du dernier rectificatif lié).
- annonces_recentes — flux des annonces parues sur FENETRE_JOURS jours,
  attributions incluses :
    idweb (PK), objet, acheteur, nature, nature_libelle, famille,
    famille_libelle, type_marche (JSON), titulaires (JSON), departements
    (JSON), date_parution, date_limite_reponse, url_avis.
- annonces_par_famille — agrégat du flux : famille, famille_libelle,
  nature, nb.
- annonces_par_jour — sparkline du flux : jour, nb, nb_appels_offre,
  nb_attributions.

Module UI : Commande publique (« appels d'offres en cours » triés par
urgence, fil des annonces/attributions) et Accueil (flux + sparkline).

Notes de véracité (aucune donnée inventée) :
- montant_estime : le BOAMP n'a pas de champ montant à plat ; la valeur est
  extraite du JSON `donnees` quand elle y est réellement publiée (eForms
  `cbc:EstimatedOverallContractAmount`, `efbc:OverallMaximumFramework
  ContractsAmount`, FNS `valeurEstimee`), sinon NULL — le front l'affiche
  « non publié ». Montants d'accords-cadres = maximums, pas du dépensé.
- annulee / rectifiee_par : joints depuis les annonces ANNULATION et
  RECTIFICATIF via leur champ `annonce_lie` ; le front doit exclure
  (ou barrer) les AO annulee=1 et pointer le rectificatif s'il existe.
- code_departement BOAMP : codes NON zéro-paddés (« 4 », pas « 04 »).

Exécution : python -m pipelines.ingest_boamp
"""

from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from urllib.parse import quote, urlencode

from pipelines import db
from pipelines.common import obtenir_logger, telecharger

log = obtenir_logger("ingest_boamp")

SOURCE_ID = "S2"
SOURCE_NOM = "BOAMP — annonces de marchés publics (DILA)"
SOURCE_URL = "https://boamp-datadila.opendatasoft.com/explore/dataset/boamp/"
SOURCE_LICENCE = "etalab-2.0"
SOURCE_FREQUENCE = "quotidienne"

EXPORT_URL = (
    "https://boamp-datadila.opendatasoft.com"
    "/api/explore/v2.1/catalog/datasets/boamp/exports/json"
)

#: Fenêtre du flux « annonces récentes » (jours).
FENETRE_JOURS = 30

#: Clés portant un montant dans le JSON `donnees`, par ordre de préférence
#: (constatées sur enregistrements réels du 19/08/2026 : schémas eForms et FNS).
CLES_MONTANT = (
    "cbc:EstimatedOverallContractAmount",
    "efbc:OverallMaximumFrameworkContractsAmount",
    "valeurEstimee",
)

CHAMPS_AO = (
    "idweb,objet,nomacheteur,nature,nature_libelle,famille,famille_libelle,"
    "type_marche,type_procedure,procedure_libelle,descripteur_libelle,"
    "code_departement,dateparution,datelimitereponse,url_avis,donnees"
)
CHAMPS_ANNONCE = (
    "idweb,objet,nomacheteur,nature,nature_libelle,famille,famille_libelle,"
    "type_marche,titulaire,code_departement,dateparution,datelimitereponse,url_avis"
)
CHAMPS_LIEN = "idweb,annonce_lie,dateparution,nature"

SCHEMA = """
CREATE TABLE IF NOT EXISTS ao_en_cours (
    idweb               TEXT PRIMARY KEY,
    objet               TEXT,
    acheteur            TEXT,
    nature              TEXT NOT NULL,
    nature_libelle      TEXT,
    famille             TEXT,
    famille_libelle     TEXT,
    type_marche         TEXT CHECK (type_marche IS NULL OR json_valid(type_marche)),
    type_procedure      TEXT,
    procedure_libelle   TEXT,
    descripteurs        TEXT CHECK (descripteurs IS NULL OR json_valid(descripteurs)),
    departements        TEXT CHECK (departements IS NULL OR json_valid(departements)),
    montant_estime      REAL,              -- NULL = non publié dans l'annonce
    devise              TEXT,
    date_parution       TEXT NOT NULL,     -- ISO date
    date_limite_reponse TEXT NOT NULL,     -- ISO datetime (UTC)
    url_avis            TEXT,
    annulee             INTEGER NOT NULL DEFAULT 0,
    rectifiee_par       TEXT               -- idweb du dernier RECTIFICATIF lié
);
CREATE INDEX IF NOT EXISTS idx_ao_date_limite ON ao_en_cours(date_limite_reponse);
CREATE INDEX IF NOT EXISTS idx_ao_famille     ON ao_en_cours(famille);

CREATE TABLE IF NOT EXISTS annonces_recentes (
    idweb               TEXT PRIMARY KEY,
    objet               TEXT,
    acheteur            TEXT,
    nature              TEXT,
    nature_libelle      TEXT,
    famille             TEXT,
    famille_libelle     TEXT,
    type_marche         TEXT CHECK (type_marche IS NULL OR json_valid(type_marche)),
    titulaires          TEXT CHECK (titulaires IS NULL OR json_valid(titulaires)),
    departements        TEXT CHECK (departements IS NULL OR json_valid(departements)),
    date_parution       TEXT NOT NULL,
    date_limite_reponse TEXT,
    url_avis            TEXT
);
CREATE INDEX IF NOT EXISTS idx_annonces_parution ON annonces_recentes(date_parution);
CREATE INDEX IF NOT EXISTS idx_annonces_nature   ON annonces_recentes(nature);

CREATE TABLE IF NOT EXISTS annonces_par_famille (
    famille         TEXT,
    famille_libelle TEXT,
    nature          TEXT,
    nb              INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS annonces_par_jour (
    jour             TEXT PRIMARY KEY,
    nb               INTEGER NOT NULL,
    nb_appels_offre  INTEGER NOT NULL,
    nb_attributions  INTEGER NOT NULL
);
"""

# ---------------------------------------------------------------------------
# Parsing (fonctions pures, testées sur enregistrements réels)
# ---------------------------------------------------------------------------


def _liste_json(valeur: object) -> str | None:
    """Champ multivalué ODS (liste, scalaire ou None) → texte JSON ou None."""
    if valeur is None or valeur == "":
        return None
    if not isinstance(valeur, list):
        valeur = [valeur]
    return json.dumps(valeur, ensure_ascii=False)


def _vers_montant(valeur: object) -> tuple[float, str | None] | None:
    """Valeur brute d'une clé montant → (montant > 0, devise) ou None.

    Formes réelles rencontrées : {"@currencyID": "EUR", "#text": "168000.00"}
    (eForms) et {"@devise": "EUR", "valeur": "220000"} (FNS).
    """
    devise: str | None = None
    brut = valeur
    if isinstance(valeur, dict):
        devise = valeur.get("@currencyID") or valeur.get("@devise")
        brut = valeur.get("#text") if "#text" in valeur else valeur.get("valeur")
    if isinstance(brut, (dict, list)) or brut is None:
        return None
    try:
        nettoye = str(brut).replace(" ", "").replace("\u00a0", "").replace("\u202f", "")
        montant = float(nettoye.replace(",", "."))
    except ValueError:
        return None
    if montant <= 0:  # 0.00 = non renseigné dans les eForms constatés
        return None
    return montant, devise


def extraire_montant(donnees_texte: str | None) -> tuple[float | None, str | None]:
    """Extrait un montant estimé du JSON `donnees` d'une annonce BOAMP.

    Parcourt récursivement le document (schémas eForms 3.x et FNS) et retient,
    parmi les clés CLES_MONTANT, le candidat le moins profond (le montant
    global de l'avis est moins profond que les montants par lot). Retourne
    (None, None) si aucun montant n'est publié — cas fréquent, jamais inventé.
    """
    if not donnees_texte:
        return None, None
    try:
        racine = json.loads(donnees_texte)
    except (TypeError, ValueError):
        return None, None

    candidats: list[tuple[int, int, float, str | None]] = []

    def marcher(noeud: object, profondeur: int) -> None:
        if isinstance(noeud, dict):
            for cle, val in noeud.items():
                if cle in CLES_MONTANT:
                    resultat = _vers_montant(val)
                    if resultat is not None:
                        candidats.append(
                            (profondeur, CLES_MONTANT.index(cle), *resultat)
                        )
                marcher(val, profondeur + 1)
        elif isinstance(noeud, list):
            for val in noeud:
                marcher(val, profondeur)

    marcher(racine, 0)
    if not candidats:
        return None, None
    candidats.sort(key=lambda c: (c[0], c[1]))
    _, _, montant, devise = candidats[0]
    return montant, devise or "EUR"


# Écart maximal admis entre parution et date limite de réponse, en années.
# POURQUOI un garde-fou : la date limite est saisie par l'acheteur et le
# BOAMP ne la contrôle pas. La base de production du 20/08/2026 contenait
# 17 avis à échéance impossible (« 7017-07-24 », « 2924-04-15 » — un chiffre
# de mille frappé de travers), dont deux parus en 2017 et 2018 encore
# comptés comme « en cours » neuf ans plus tard dans le compteur public.
# POURQUOI 20 ans, et pas 15 comme à l'origine : le seuil avait été posé à 15
# parce que la distribution s'arrêtait alors net à 10 ans, laissant une bande
# vide entre 11 et 15 — « le seuil ne peut donc écarter aucun avis légitime ».
# Cette justification a cessé d'être vraie. La distribution mesurée le
# 20/08/2026 est 15 ans → 1 avis, 11 ans → 1, 10 ans → 14, 9 ans → 2 : la
# bande n'est plus vide, et un avis réel est venu se poser EXACTEMENT sur le
# couperet — un système d'acquisition dynamique paru le 03/08/2025 et ouvert
# jusqu'au 01/09/2040. Un SAD n'a pas de durée maximale légale, contrairement
# à l'accord-cadre : rien n'empêche le suivant d'aller à 16 ou 18 ans, et il
# serait alors écarté en silence (un simple log.warning) d'un compteur public.
# Le garde-fou vise des millésimes frappés de travers — « 7017 », « 2924 »,
# soit des écarts de plusieurs siècles. 20 ans les arrête tout aussi
# sûrement que 15, en rendant au seuil la marge qu'il avait perdue.
ECART_MAX_LIMITE_ANNEES = 20


def _limite_plausible(parution: str, limite: str) -> bool:
    """Date limite de réponse cohérente avec la parution ?

    Comparaison sur le seul millésime : les deux champs sont des chaînes
    ISO 8601 et l'écart en cause se joue sur des siècles, pas sur des jours.
    Parser les dates complètes n'apporterait qu'un risque d'exception sur
    les formats bancals que le BOAMP laisse passer.
    Retourne True si l'un des deux millésimes est illisible : on ne rejette
    jamais sur une incertitude de format, seulement sur une preuve.
    """
    try:
        an_parution = int(parution[:4])
        an_limite = int(limite[:4])
    except (TypeError, ValueError):
        return True
    return an_limite - an_parution <= ECART_MAX_LIMITE_ANNEES


def parser_ao(rec: dict) -> dict | None:
    """Enregistrement export BOAMP (AO) → ligne ao_en_cours, ou None si
    les champs indispensables (idweb, dates) manquent, ou si la date limite
    de réponse est manifestement fautive (cf. `_limite_plausible`)."""
    idweb = rec.get("idweb")
    parution = rec.get("dateparution")
    limite = rec.get("datelimitereponse")
    if not idweb or not parution or not limite:
        return None
    if not _limite_plausible(parution, limite):
        log.warning(
            "AO %s écarté : date limite %s incohérente avec la parution %s "
            "(> %d ans)", idweb, limite, parution, ECART_MAX_LIMITE_ANNEES,
        )
        return None
    montant, devise = extraire_montant(rec.get("donnees"))
    return {
        "idweb": idweb,
        "objet": rec.get("objet"),
        "acheteur": rec.get("nomacheteur"),
        "nature": rec.get("nature") or "APPEL_OFFRE",
        "nature_libelle": rec.get("nature_libelle"),
        "famille": rec.get("famille"),
        "famille_libelle": rec.get("famille_libelle"),
        "type_marche": _liste_json(rec.get("type_marche")),
        "type_procedure": rec.get("type_procedure"),
        "procedure_libelle": rec.get("procedure_libelle"),
        "descripteurs": _liste_json(rec.get("descripteur_libelle")),
        "departements": _liste_json(rec.get("code_departement")),
        "montant_estime": montant,
        "devise": devise,
        "date_parution": parution,
        "date_limite_reponse": limite,
        "url_avis": rec.get("url_avis"),
    }


def parser_annonce(rec: dict) -> dict | None:
    """Enregistrement export BOAMP (toute nature) → ligne annonces_recentes,
    ou None si idweb/dateparution manquent."""
    idweb = rec.get("idweb")
    parution = rec.get("dateparution")
    if not idweb or not parution:
        return None
    return {
        "idweb": idweb,
        "objet": rec.get("objet"),
        "acheteur": rec.get("nomacheteur"),
        "nature": rec.get("nature"),
        "nature_libelle": rec.get("nature_libelle"),
        "famille": rec.get("famille"),
        "famille_libelle": rec.get("famille_libelle"),
        "type_marche": _liste_json(rec.get("type_marche")),
        "titulaires": _liste_json(rec.get("titulaire")),
        "departements": _liste_json(rec.get("code_departement")),
        "date_parution": parution,
        "date_limite_reponse": rec.get("datelimitereponse"),
        "url_avis": rec.get("url_avis"),
    }


def indexer_liens(recs: list[dict]) -> tuple[set[str], dict[str, str]]:
    """Annonces ANNULATION/RECTIFICATIF → (idweb annulés, cible → dernier
    rectificatif). `annonce_lie` pointe vers la ou les annonces d'origine."""
    annules: set[str] = set()
    rectifs: dict[str, tuple[str, str]] = {}  # cible -> (dateparution, idweb)
    for rec in recs:
        cibles = rec.get("annonce_lie") or []
        if not isinstance(cibles, list):
            cibles = [cibles]
        parution = rec.get("dateparution") or ""
        idweb = rec.get("idweb") or ""
        for cible in cibles:
            if not cible:
                continue
            if rec.get("nature") == "ANNULATION":
                annules.add(cible)
            elif rec.get("nature") == "RECTIFICATIF":
                if (parution, idweb) > rectifs.get(cible, ("", "")):
                    rectifs[cible] = (parution, idweb)
    return annules, {cible: idweb for cible, (_, idweb) in rectifs.items()}


# ---------------------------------------------------------------------------
# Téléchargements (exports ODS, streaming, hors plafond 10 000)
# ---------------------------------------------------------------------------


def _exporter(where: str, select: str, dest: str) -> list[dict]:
    """Appelle /exports/json avec `where`/`select` et retourne la liste."""
    url = EXPORT_URL + "?" + urlencode(
        {"where": where, "select": select}, quote_via=quote
    )
    chemin = telecharger(url, dest, max_age_heures=None)
    with open(chemin, encoding="utf-8") as f:
        donnees = json.load(f)
    if not isinstance(donnees, list):
        raise RuntimeError(f"export BOAMP inattendu (pas une liste JSON) : {dest}")
    return donnees


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------


def _executer() -> None:
    aujourdhui = date.today()
    debut_fenetre = (aujourdhui - timedelta(days=FENETRE_JOURS)).isoformat()

    # 1. Appels d'offres à clôture future (~9 000 constatés le 19/08/2026).
    brut_ao = _exporter(
        "datelimitereponse>now() AND nature='APPEL_OFFRE'",
        CHAMPS_AO,
        "boamp_ao_en_cours.json",
    )
    # 2. Flux des annonces parues sur la fenêtre (attributions incluses).
    brut_annonces = _exporter(
        f"dateparution>=date'{debut_fenetre}'",
        CHAMPS_ANNONCE,
        "boamp_annonces_recentes.json",
    )
    # 3. Annulations/rectificatifs (tout l'historique : ~71 000 lignes légères)
    #    pour ne pas afficher un AO annulé (piège SOURCES.md S2).
    brut_liens = _exporter(
        "nature IN ('ANNULATION','RECTIFICATIF')",
        CHAMPS_LIEN,
        "boamp_annonces_liees.json",
    )

    aos, ecartes_ao = [], 0
    for rec in brut_ao:
        ligne = parser_ao(rec)
        if ligne is None:
            ecartes_ao += 1
        else:
            aos.append(ligne)
    annonces, ecartes_annonces = [], 0
    for rec in brut_annonces:
        ligne = parser_annonce(rec)
        if ligne is None:
            ecartes_annonces += 1
        else:
            annonces.append(ligne)

    if not aos:
        raise RuntimeError("aucun appel d'offres en cours parsé : API changée ?")
    if not annonces:
        raise RuntimeError("aucune annonce récente parsée : API changée ?")
    if ecartes_ao or ecartes_annonces:
        log.warning(
            "enregistrements écartés (champs indispensables absents) : %d AO, %d annonces",
            ecartes_ao, ecartes_annonces,
        )

    annules, rectifs = indexer_liens(brut_liens)
    for ligne in aos:
        ligne["annulee"] = 1 if ligne["idweb"] in annules else 0
        ligne["rectifiee_par"] = rectifs.get(ligne["idweb"])
    nb_annulees = sum(l["annulee"] for l in aos)
    nb_montants = sum(1 for l in aos if l["montant_estime"] is not None)

    conn = db.init_db()
    try:
        conn.executescript(SCHEMA)
        # Réécriture idempotente en une transaction.
        conn.execute("DELETE FROM ao_en_cours")
        conn.executemany(
            """
            INSERT OR REPLACE INTO ao_en_cours
                (idweb, objet, acheteur, nature, nature_libelle, famille,
                 famille_libelle, type_marche, type_procedure, procedure_libelle,
                 descripteurs, departements, montant_estime, devise,
                 date_parution, date_limite_reponse, url_avis, annulee, rectifiee_par)
            VALUES (:idweb, :objet, :acheteur, :nature, :nature_libelle, :famille,
                    :famille_libelle, :type_marche, :type_procedure, :procedure_libelle,
                    :descripteurs, :departements, :montant_estime, :devise,
                    :date_parution, :date_limite_reponse, :url_avis, :annulee, :rectifiee_par)
            """,
            aos,
        )
        conn.execute("DELETE FROM annonces_recentes")
        conn.executemany(
            """
            INSERT OR REPLACE INTO annonces_recentes
                (idweb, objet, acheteur, nature, nature_libelle, famille,
                 famille_libelle, type_marche, titulaires, departements,
                 date_parution, date_limite_reponse, url_avis)
            VALUES (:idweb, :objet, :acheteur, :nature, :nature_libelle, :famille,
                    :famille_libelle, :type_marche, :titulaires, :departements,
                    :date_parution, :date_limite_reponse, :url_avis)
            """,
            annonces,
        )
        conn.execute("DELETE FROM annonces_par_famille")
        conn.execute(
            """
            INSERT INTO annonces_par_famille (famille, famille_libelle, nature, nb)
            SELECT famille, famille_libelle, nature, count(*)
            FROM annonces_recentes
            GROUP BY famille, famille_libelle, nature
            """
        )
        conn.execute("DELETE FROM annonces_par_jour")
        conn.execute(
            """
            INSERT INTO annonces_par_jour (jour, nb, nb_appels_offre, nb_attributions)
            SELECT date_parution,
                   count(*),
                   sum(CASE WHEN nature = 'APPEL_OFFRE' THEN 1 ELSE 0 END),
                   sum(CASE WHEN nature = 'ATTRIBUTION' THEN 1 ELSE 0 END)
            FROM annonces_recentes
            GROUP BY date_parution
            """
        )
        conn.commit()

        date_donnees = conn.execute(
            """
            SELECT max(d) FROM (
                SELECT max(date_parution) AS d FROM annonces_recentes
                UNION ALL
                SELECT max(date_parution) FROM ao_en_cours
            )
            """
        ).fetchone()[0]
        db.upsert_meta(
            conn,
            source_id=SOURCE_ID,
            nom=SOURCE_NOM,
            url=SOURCE_URL,
            licence=SOURCE_LICENCE,
            frequence=SOURCE_FREQUENCE,
            date_donnees=date_donnees,
            lignes=len(aos) + len(annonces),
            notes=(
                f"{len(aos)} AO en cours (dont {nb_annulees} annulés, "
                f"{nb_montants} avec montant publié dans l'annonce) ; "
                f"{len(annonces)} annonces sur {FENETRE_JOURS} j ; "
                "via /exports/json (plafond /records 10 000)"
            ),
        )
    finally:
        conn.close()

    log.info(
        "BOAMP ingéré : %d AO en cours (%d annulés, %d avec montant), "
        "%d annonces %d j, fraîcheur %s",
        len(aos), nb_annulees, nb_montants, len(annonces), FENETRE_JOURS, date_donnees,
    )


def main() -> int:
    try:
        _executer()
    except Exception:
        log.exception("échec de l'ingestion BOAMP")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

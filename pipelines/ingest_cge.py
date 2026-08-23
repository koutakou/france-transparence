"""P21 — Bilan patrimonial de l'État, comptabilité générale (S22, CGE).

Source : pièce de synthèse xlsx jointe au jeu ODS
`balances_des_comptes_etat` (DGFiP / data.economie.gouv.fr) —
« 2006-2024 Bilan, CDR, solde.xlsx » au 23/08/2026. Licence Ouverte v2.0.

CE PIPELINE N'INGÈRE PAS LES 517 489 LIGNES DE BALANCES
-------------------------------------------------------
Le grain compte × programme × année ne reconstitue PAS les totaux
officiels I / II / III : les sommer inventerait un total. Les totaux
publiés sont lus dans la pièce de synthèse (onglets Bilan et Compte
de résultat). Les balances 2025 existent au grain compte ; tant que
la pièce de synthèse ne porte pas 2025, aucun total 2025 n'est écrit.

CE N'EST PAS LA SOURCE S13
--------------------------
S13 = situations mensuelles budgétaires DGFiP (caisse, flux YTD de
l'État). S22 = comptabilité générale (droits constatés, stock au
31/12). Les deux ne s'additionnent pas.

CE N'EST PAS MAASTRICHT
-----------------------
S41 = encours APU (ESA S13, GD). S42 = déficit APU (B9). S44 = TE/TR
APU. S22 = bilan de l'État (personne morale), situation nette = I − II.
La situation nette n'est pas « la dette de l'État ». Les dettes
financières CGE ne sont pas l'encours Maastricht.

PIÈGE D'UNITÉ DANS LA PIÈCE
---------------------------
L'en-tête dit « En millions d'euros ». Les colonnes 2024, 2022-2018
sont en EUROS ; 2023 et 2017-2006 sont en millions. Détection par
l'ordre de grandeur de TOTAL ACTIF (I), colonne par colonne — jamais
par l'en-tête. Md€ = euros ÷ 1e9 (convention S13), jamais ÷ 1000
(convention Eurostat MIO_EUR).

`date_donnees` = 31/12 du millésime max de la pièce, jamais
`metas.default.modified` du catalogue.

Exécution : python -m pipelines.ingest_cge
Base : FT_DB_PATH sinon data/france.db. Réécriture idempotente
(DELETE puis INSERT dans une transaction), puis upsert_meta('S22', …).
Échec → exit ≠ 0, base intacte.
"""

from __future__ import annotations

import json
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

from pipelines import db
from pipelines.common import obtenir_logger, telecharger

log = obtenir_logger("cge")

SOURCE_ID = "S22"
NOM_SOURCE = (
    "Compte général de l'État — bilan patrimonial (DGFiP, pièce de synthèse)"
)
URL_DATASET = (
    "https://data.economie.gouv.fr/explore/dataset/balances_des_comptes_etat/"
)
URL_API_DATASET = (
    "https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/"
    "balances_des_comptes_etat"
)
LICENCE = "Licence Ouverte 2.0 (Etalab)"
FREQUENCE = "annuelle"
FICHIER_META = "cge/balances_des_comptes_etat.json"
FICHIER_XLSX = "cge/bilan_cdr_solde.xlsx"
CACHE_HEURES = 7 * 24

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
COL_RE = re.compile(r"^([A-Z]+)(\d+)$")
ANNEE_RE = re.compile(r"(?:31/12/)?(20\d{2})")

POSTES = (
    "actif",
    "passif_hors_sn",
    "situation_nette",
    "dettes_financieres",
    "solde_exercice",
)

# Libellés officiels de la pièce, après compactage des espaces.
LIBELLE_POSTE = {
    "total actif (i)": "actif",
    "total passif (hors situation nette) (ii)": "passif_hors_sn",
    "situation nette (iii = i - ii)": "situation_nette",
    "total dettes financières": "dettes_financieres",
    "solde des opérations de l'exercice (xvi - xii)": "solde_exercice",
}

# TOTAL ACTIF de l'État : ~500 Md€ à ~4 000 Md€ sur la série connue.
BORNE_ACTIF_MIN = 4e11
BORNE_ACTIF_MAX = 4e12
# |situation nette| du même ordre ; le signe est négatif sur 2006-2024.
BORNE_SN_ABS_MIN = 1e11
BORNE_SN_ABS_MAX = 5e12
N_ANNEES_MIN = 15
# Seuil : une colonne en euros dépasse largement 100 millions sur I.
SEUIL_EUR = 1e8

NOTES = (
    "comptabilité générale de l'État (CGE), pas le budget (S13) ; "
    "totaux lus dans la pièce de synthèse xlsx, jamais sommés depuis "
    "les balances compte×programme ; millésime = 31/12 de la pièce, "
    "jamais modified du catalogue ; les balances 2025 existent au grain "
    "compte tant que la pièce ne porte pas 2025 aucun total 2025 n'est écrit ; "
    "situation nette = I − II, ce n'est pas la dette de l'État ni Maastricht "
    "(S41/S42/S44) ; Md€ = euros÷1e9 ; certaines colonnes de la pièce sont "
    "en euros, d'autres en millions malgré l'en-tête"
)

_DDL = """
CREATE TABLE IF NOT EXISTS cge_bilan_etat (
    annee          INTEGER NOT NULL,
    poste          TEXT NOT NULL CHECK (poste IN (
                       'actif',
                       'passif_hors_sn',
                       'situation_nette',
                       'dettes_financieres',
                       'solde_exercice'
                   )),
    valeur_euros   REAL NOT NULL,
    unite_source   TEXT NOT NULL CHECK (unite_source IN ('EUR', 'MIO_EUR')),
    PRIMARY KEY (annee, poste)
);
"""


def euros_en_md(euros: float) -> float:
    """Euros → Md€. Un milliard d'euros = 1 Md€. Jamais ÷ 1000 (Eurostat)."""
    return euros / 1e9


def date_fin_annee(annee: int) -> str:
    if not isinstance(annee, int) or annee < 1990 or annee > 2100:
        raise ValueError(f"année hors plage : {annee!r}")
    return f"{annee}-12-31"


def compact(texte: str) -> str:
    return " ".join((texte or "").split()).strip().lower()


def annee_depuis_entete(texte: str) -> int | None:
    m = ANNEE_RE.search(texte or "")
    return int(m.group(1)) if m else None


def _col_row(ref: str) -> tuple[str, int]:
    m = COL_RE.match(ref)
    if not m:
        raise ValueError(f"référence de cellule hors motif : {ref!r}")
    return m.group(1), int(m.group(2))


def _shared_strings(z: zipfile.ZipFile) -> list[str]:
    brut = z.read("xl/sharedStrings.xml")
    racine = ET.fromstring(brut)
    out: list[str] = []
    for si in racine.findall(f"{NS}si"):
        out.append("".join(t.text or "" for t in si.findall(f".//{NS}t")))
    return out


def _valeur_cellule(c: ET.Element, shared: list[str]):
    t = c.attrib.get("t")
    v = c.find(f"{NS}v")
    if v is None or v.text is None:
        return None
    if t == "s":
        return shared[int(v.text)]
    if t == "b":
        return v.text == "1"
    try:
        return float(v.text)
    except ValueError:
        return v.text


def lire_feuille(z: zipfile.ZipFile, chemin: str, shared: list[str]) -> dict[int, dict[str, object]]:
    racine = ET.fromstring(z.read(chemin))
    lignes: dict[int, dict[str, object]] = defaultdict(dict)
    for c in racine.findall(f".//{NS}c"):
        ref = c.attrib.get("r")
        if not ref:
            continue
        col, row = _col_row(ref)
        val = _valeur_cellule(c, shared)
        if val is not None:
            lignes[row][col] = val
    return lignes


def feuilles_du_classeur(chemin: Path) -> dict[str, dict[int, dict[str, object]]]:
    """Lit les onglets nommés d'un xlsx (stdlib, sans openpyxl)."""
    with zipfile.ZipFile(chemin) as z:
        shared = _shared_strings(z)
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        ns_rel = "{http://schemas.openxmlformats.org/package/2006/relationships}"
        cibles = {}
        for rel in rels:
            rid = rel.attrib.get("Id")
            cible = rel.attrib.get("Target")
            if rid and cible:
                cibles[rid] = "xl/" + cible.lstrip("/") if not cible.startswith("xl/") else cible
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        out: dict[str, dict[int, dict[str, object]]] = {}
        for sheet in wb.findall(f"{NS}sheets/{NS}sheet"):
            nom = sheet.attrib.get("name") or ""
            rid = sheet.attrib.get(
                "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
            )
            cible = cibles.get(rid or "")
            if nom and cible:
                out[nom] = lire_feuille(z, cible, shared)
        return out


def colonnes_annees(ligne_entete: dict[str, object]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for col, val in ligne_entete.items():
        if col == "B":
            continue
        if isinstance(val, str):
            an = annee_depuis_entete(val)
            if an is not None:
                mapping[col] = an
    if len(mapping) < N_ANNEES_MIN:
        raise ValueError(
            f"trop peu d'années dans l'en-tête : {sorted(mapping.values())}"
        )
    return mapping


def detecter_unite(valeur_actif) -> str:
    """EUR si |I| ≥ 1e8, sinon millions d'euros. Jamais l'en-tête de la pièce."""
    try:
        v = float(valeur_actif)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"TOTAL ACTIF illisible : {valeur_actif!r}") from exc
    return "EUR" if abs(v) >= SEUIL_EUR else "MIO_EUR"


def en_euros(valeur, unite: str) -> float:
    v = float(valeur)
    if unite == "EUR":
        return v
    if unite == "MIO_EUR":
        return v * 1e6
    raise ValueError(f"unité inconnue : {unite!r}")


def _libelle_ligne(ligne: dict[str, object]) -> str:
    b = ligne.get("B")
    if isinstance(b, str) and compact(b):
        return compact(b)
    c = ligne.get("C")
    if isinstance(c, str) and compact(c):
        return compact(c)
    return ""


def extraire_postes(
    feuille: dict[int, dict[str, object]],
    annees: dict[str, int],
    unites: dict[int, str],
    postes_attendus: set[str],
) -> list[dict]:
    trouves: dict[tuple[int, str], dict] = {}
    for row in feuille.values():
        poste = LIBELLE_POSTE.get(_libelle_ligne(row))
        if poste is None or poste not in postes_attendus:
            continue
        for col, annee in annees.items():
            if col not in row:
                continue
            unite = unites[annee]
            euros = en_euros(row[col], unite)
            cle = (annee, poste)
            if cle in trouves:
                raise ValueError(f"poste {poste} dupliqué pour {annee}")
            trouves[cle] = {
                "annee": annee,
                "poste": poste,
                "valeur_euros": euros,
                "unite_source": unite,
            }
    manquants = postes_attendus - {p for _, p in trouves}
    if manquants:
        raise ValueError(f"postes absents de la feuille : {sorted(manquants)}")
    return list(trouves.values())


def unites_par_annee(
    feuille_bilan: dict[int, dict[str, object]],
    annees: dict[str, int],
) -> dict[int, str]:
    ligne_i = None
    for row in feuille_bilan.values():
        if LIBELLE_POSTE.get(_libelle_ligne(row)) == "actif":
            ligne_i = row
            break
    if ligne_i is None:
        raise ValueError("TOTAL ACTIF (I) introuvable — impossible de détecter l'unité")
    unites: dict[int, str] = {}
    for col, annee in annees.items():
        if col not in ligne_i:
            raise ValueError(f"TOTAL ACTIF (I) sans colonne {annee}")
        unites[annee] = detecter_unite(ligne_i[col])
    return unites


def controler_identite(observations: list[dict]) -> None:
    par = {(o["annee"], o["poste"]): o["valeur_euros"] for o in observations}
    annees = sorted({o["annee"] for o in observations})
    for an in annees:
        try:
            actif = par[(an, "actif")]
            passif = par[(an, "passif_hors_sn")]
            sn = par[(an, "situation_nette")]
        except KeyError as exc:
            raise ValueError(f"identité I−II=III incomplète pour {an}") from exc
        ecart = actif - passif - sn
        tol = max(1.0, 1e-9 * max(abs(actif), abs(passif), 1.0))
        if abs(ecart) > tol:
            raise ValueError(
                f"I − II ≠ III pour {an} : "
                f"{actif} − {passif} − {sn} = {ecart} (tol {tol})"
            )


def controler_ampleur(observations: list[dict]) -> None:
    """Garde-fous d'unité sur une série réelle, pas sur une fixture minimale."""
    annees = sorted({o["annee"] for o in observations})
    if len(annees) < N_ANNEES_MIN:
        raise ValueError(
            f"{len(annees)} années, {N_ANNEES_MIN} attendues au minimum"
        )
    par = {(o["annee"], o["poste"]): o["valeur_euros"] for o in observations}
    for an in annees:
        actif_an = par[(an, "actif")]
        if not (BORNE_ACTIF_MIN < actif_an < BORNE_ACTIF_MAX):
            raise ValueError(
                "ordre de grandeur suspect (erreur d'unité ?) : "
                f"actif {an} = {actif_an} EUR "
                f"hors ]{BORNE_ACTIF_MIN:g}, {BORNE_ACTIF_MAX:g}["
            )
    dernier = max(annees)
    sn = par[(dernier, "situation_nette")]
    if not (BORNE_SN_ABS_MIN < abs(sn) < BORNE_SN_ABS_MAX):
        raise ValueError(
            "ordre de grandeur suspect (situation nette) : "
            f"{dernier} = {sn} EUR "
            f"|SN| hors ]{BORNE_SN_ABS_MIN:g}, {BORNE_SN_ABS_MAX:g}["
        )
    # Sur 2006-2024 la SN de l'État est négative. Un signe positif
    # n'est pas interdit par le SQL ; il ferait échouer ce garde-fou
    # pour qu'un humain relise plutôt que de publier un retournement
    # silencieux.
    if sn >= 0:
        raise ValueError(
            f"situation nette {dernier} = {sn} EUR ≥ 0 — "
            "inattendu sur la série CGE de l'État, à relire"
        )


def extraire(chemin_xlsx: Path) -> list[dict]:
    """Totaux officiels I/II/III + dettes financières + solde CDR."""
    feuilles = feuilles_du_classeur(chemin_xlsx)
    if "Bilan" not in feuilles:
        raise ValueError(f"onglet Bilan absent : {sorted(feuilles)}")
    cdr_nom = next((n for n in feuilles if "résultat" in n.lower() or "resultat" in n.lower()), None)
    if cdr_nom is None:
        raise ValueError(f"onglet Compte de résultat absent : {sorted(feuilles)}")

    bilan = feuilles["Bilan"]
    # L'en-tête des années est la première ligne qui contient « 20 ».
    ligne_entete = None
    for r in sorted(bilan):
        if any(isinstance(v, str) and ANNEE_RE.search(v) for v in bilan[r].values()):
            ligne_entete = bilan[r]
            break
    if ligne_entete is None:
        raise ValueError("en-tête d'années introuvable dans Bilan")
    annees = colonnes_annees(ligne_entete)
    unites = unites_par_annee(bilan, annees)

    obs = extraire_postes(
        bilan,
        annees,
        unites,
        {"actif", "passif_hors_sn", "situation_nette", "dettes_financieres"},
    )

    cdr = feuilles[cdr_nom]
    ligne_entete_cdr = None
    for r in sorted(cdr):
        if any(isinstance(v, str) and ANNEE_RE.search(v) for v in cdr[r].values()):
            ligne_entete_cdr = cdr[r]
            break
    if ligne_entete_cdr is None:
        raise ValueError("en-tête d'années introuvable dans Compte de résultat")
    annees_cdr = colonnes_annees(ligne_entete_cdr)
    # Même détection d'unité, par année, d'après |solde| (même piège).
    ligne_solde = None
    for row in cdr.values():
        if LIBELLE_POSTE.get(_libelle_ligne(row)) == "solde_exercice":
            ligne_solde = row
            break
    if ligne_solde is None:
        raise ValueError("SOLDE DES OPÉRATIONS DE L'EXERCICE introuvable")
    unites_cdr: dict[int, str] = {}
    for col, annee in annees_cdr.items():
        if col not in ligne_solde:
            continue
        unites_cdr[annee] = detecter_unite(ligne_solde[col])
    annees_cdr_ok = {col: an for col, an in annees_cdr.items() if an in unites_cdr}
    obs += extraire_postes(cdr, annees_cdr_ok, unites_cdr, {"solde_exercice"})

    controler_identite(obs)
    obs.sort(key=lambda o: (o["annee"], o["poste"]))
    return obs


def url_piece_synthese(meta: dict) -> str:
    for att in meta.get("attachments") or []:
        titre = (att.get("title") or "").lower()
        mime = (att.get("mimetype") or "").lower()
        url = att.get("url")
        if not url:
            continue
        if "bilan" in titre and ("xlsx" in titre or "spreadsheet" in mime):
            return url
    raise ValueError("pièce de synthèse xlsx (Bilan) introuvable dans les attachments")


def controler_licence(meta: dict) -> None:
    try:
        lic = meta["metas"]["default"]["license"]
    except (KeyError, TypeError) as exc:
        raise ValueError("licence absente des métadonnées du jeu") from exc
    if "Licence Ouverte" not in lic or "2.0" not in lic:
        raise ValueError(f"licence inattendue : {lic!r}")


def ecrire_db(conn, observations: list[dict]) -> str:
    """DELETE+INSERT en transaction, puis upsert_meta S22. Retourne date_donnees."""
    postes = {o["poste"] for o in observations}
    if set(POSTES) - postes:
        raise ValueError(f"écriture incomplète : {sorted(postes)}")
    par_an: dict[int, set[str]] = {}
    for o in observations:
        par_an.setdefault(o["annee"], set()).add(o["poste"])
    for an, postes_an in sorted(par_an.items()):
        if postes_an != set(POSTES):
            raise ValueError(
                f"{an} incomplet : {sorted(postes_an)} (attendu {list(POSTES)})"
            )
    date_donnees = date_fin_annee(max(o["annee"] for o in observations))
    conn.executescript(_DDL)
    with conn:
        conn.execute("DELETE FROM cge_bilan_etat")
        conn.executemany(
            """INSERT INTO cge_bilan_etat
               (annee, poste, valeur_euros, unite_source)
               VALUES (:annee, :poste, :valeur_euros, :unite_source)""",
            observations,
        )
    db.upsert_meta(
        conn,
        source_id=SOURCE_ID,
        nom=NOM_SOURCE,
        url=URL_DATASET,
        licence=LICENCE,
        frequence=FREQUENCE,
        date_donnees=date_donnees,
        lignes=len(observations),
        notes=NOTES,
    )
    return date_donnees


def main() -> int:
    try:
        chemin_meta = telecharger(
            URL_API_DATASET, FICHIER_META, max_age_heures=CACHE_HEURES
        )
        meta = json.loads(Path(chemin_meta).read_text(encoding="utf-8"))
        controler_licence(meta)
        url_xlsx = url_piece_synthese(meta)
        chemin_xlsx = telecharger(
            url_xlsx, FICHIER_XLSX, max_age_heures=CACHE_HEURES
        )
        observations = extraire(Path(chemin_xlsx))
        controler_ampleur(observations)
        conn = db.init_db()
        date_donnees = ecrire_db(conn, observations)
        conn.close()
        log.info(
            "cge_bilan_etat: %d lignes, données au %s (millésime max %s)",
            len(observations),
            date_donnees,
            max(o["annee"] for o in observations),
        )
        return 0
    except Exception:
        log.exception("échec de l'ingestion S22 — base laissée intacte")
        return 1


if __name__ == "__main__":
    sys.exit(main())

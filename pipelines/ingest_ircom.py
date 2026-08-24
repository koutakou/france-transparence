"""P24 — Impôt sur le revenu par collectivité territoriale (S47, IRCOM).

Source : jeu data.gouv `limpot-sur-le-revenu-par-collectivite-territoriale-ircom`
(DGFiP / DESF, ministères économiques et financiers). Ressource zip du
millésime courant, fichier `ircom_communes_complet_revenus_AAAA.xlsx`.
Licence : Licence Ouverte / Open Licence (identifiant data.gouv `fr-lo`),
relue le 24/08/2026 sur la fiche live (HTTP 200) — « Licence Ouverte /
Open Licence ». Le miroir data.economie (`…territoriale0`) est figé
(modified 2018, 0 enregistrement) : ce n'est PAS la source.

CE PIPELINE N'EST PAS LA SOURCE S13
-----------------------------------
S13 = situations mensuelles DGFiP, Impôt sur le revenu **net de caisse**
du budget général, cumul depuis le 1er janvier, exécution. S47 = impôt
net **sur rôle** des foyers fiscaux, millésime = année des **revenus**,
par commune de résidence. `source_id` = **S47**, jamais `'S13'`. On
n'additionne pas. On ne « rapproche » pas 91 Md€ et 88 Md€.

CE QUE L'IMPÔT NET IRCOM EST (notice DESF, 4 p., 26/05/2026)
----------------------------------------------------------
Somme de l'IR payé ou restitué, déduction faite des prélèvements
sociaux, pour la partie correspondant à l'émission sur rôle. N'inclut
PAS le crédit d'impôt relatif au PFU. La CEHR s'y ajoute. Un montant
négatif est licite (restitution). `n.c.` = secret statistique.

CE QUI N'EST PAS INGÉRÉ
-----------------------
Les tranches de revenu fiscal de référence (RFR). Les montants de
traitements, salaires, retraites. Un classement de communes par
revenu n'a pas sa place ici : ce n'est pas de l'argent public.
Seules les lignes `Total` par commune sont lues. 0 page communale
(décision : 34 875 pages refusées).

UNITÉ
-----
Native : **milliers d'euros** (en-tête du xlsx), excepté le RFR par
tranche (non lu). Stockage : **euros** (× 1000). Md€ à la lecture =
euros ÷ 1e9, jamais ÷ 1000.

`date_donnees` = 31 décembre de l'année des revenus (2024 → 2024-12-31),
jamais `last_update` data.gouv (2026-05-26) ni `modified` du miroir
2018. Publication du millésime 2024 : 26/05/2026 (campagne IRCOM 2025).
Seuils 650/750 j comme S22/S45 : 400/440 sonnerait dès l'été.

Exécution : python -m pipelines.ingest_ircom
Base : FT_DB_PATH sinon data/france.db. Réécriture idempotente
(DELETE puis INSERT dans une transaction), puis upsert_meta
('S47', …). Échec → exit ≠ 0, base intacte.
"""

from __future__ import annotations

import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from xml.etree.ElementTree import iterparse

from pipelines import db
from pipelines.common import (
    assainir_texte,
    obtenir_logger,
    session_http,
    telecharger,
)

log = obtenir_logger("ircom")

SOURCE_ID = "S47"
NOM_SOURCE = (
    "IRCOM — impôt sur le revenu par collectivité territoriale "
    "(DGFiP, DESF)"
)
URL_DATASET = (
    "https://www.data.gouv.fr/datasets/"
    "limpot-sur-le-revenu-par-collectivite-territoriale-ircom"
)
URL_API_DATASET = (
    "https://www.data.gouv.fr/api/1/datasets/"
    "536998cba3a729239d20505e/"
)
LICENCE = "Licence Ouverte / Open Licence"
FREQUENCE = "annuelle"
CACHE_HEURES = 7 * 24
FICHIER_ZIP = "ircom/ircom_courant.zip"

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
COL_RE = re.compile(r"^([A-Z]+)(\d+)$")
ANNEE_RE = re.compile(r"(20\d{2})")

# Garde-fous d'ampleur sur le millésime réel, pas la fixture.
N_COMMUNES_MIN = 30_000
N_COMMUNES_MAX = 40_000
BORNE_IMPOT_EUR = (50e9, 150e9)  # 50–150 Md€
BORNE_FOYERS = (30e6, 55e6)
N_NC_MAX = 1_000

NOTES = (
    "impôt net SUR RÔLE des foyers, année des REVENUS, par commune "
    "de résidence ; pas l'IR de caisse S13 (budget général, cumul YTD) ; "
    "pas le PFU (crédit d'impôt exclu) ; CEHR incluse ; n.c. = secret "
    "statistique (notice DESF) ; un négatif est une restitution ; "
    "tranches de RFR, salaires et pensions NON ingérés ; "
    "unité native = milliers d'euros, stockée en euros (× 1000) ; "
    "Md€ = euros ÷ 1e9 ; date_donnees = 31/12 de l'année des revenus, "
    "jamais last_update data.gouv ; B31 (Autres, DINR, SPM) entre "
    "dans le total national, pas dans la carte des départements"
)

_DDL = """
CREATE TABLE IF NOT EXISTS ircom_communes (
    annee              INTEGER NOT NULL,
    dep_carte          TEXT,
    dep_source         TEXT    NOT NULL,
    com_source         TEXT    NOT NULL,
    libelle            TEXT    NOT NULL,
    n_foyers           INTEGER NOT NULL,
    impot_net_euros    REAL,
    n_foyers_imposes   INTEGER,
    PRIMARY KEY (annee, dep_source, com_source)
);
CREATE INDEX IF NOT EXISTS idx_ircom_communes_dep
    ON ircom_communes(annee, dep_carte);

CREATE TABLE IF NOT EXISTS ircom_departements (
    annee              INTEGER NOT NULL,
    dep_carte          TEXT    NOT NULL,
    n_communes         INTEGER NOT NULL,
    n_communes_nc      INTEGER NOT NULL,
    n_foyers           INTEGER NOT NULL,
    impot_net_euros    REAL    NOT NULL,
    PRIMARY KEY (annee, dep_carte)
);

CREATE TABLE IF NOT EXISTS ircom_national (
    annee              INTEGER PRIMARY KEY,
    n_communes         INTEGER NOT NULL,
    n_communes_nc      INTEGER NOT NULL,
    n_foyers           INTEGER NOT NULL,
    impot_net_euros    REAL    NOT NULL
);
"""


def date_fin_annee(annee: int) -> str:
    """31 décembre de l'année des revenus : 2024 → 2024-12-31."""
    if not isinstance(annee, int) or annee < 1990 or annee > 2100:
        raise ValueError(f"année hors plage : {annee!r}")
    return f"{annee}-12-31"


def milliers_en_euros(k: float) -> float:
    """Milliers d'euros → euros. 1 542,261 k€ = 1 542 261 €."""
    return k * 1000.0


def euros_en_md(euros: float) -> float:
    """Euros → Md€. Jamais ÷ 1000 (unité native IRCOM)."""
    return euros / 1e9


def _col_row(ref: str) -> tuple[str, int]:
    m = COL_RE.match(ref)
    if not m:
        raise ValueError(f"référence cellule illisible : {ref!r}")
    return m.group(1), int(m.group(2))


def departement_carte(dep_source: str, com_source: str) -> str | None:
    """Code département INSEE pour la carte, ou None si hors carte.

    B31 (Autres / DINR / Saint-Pierre-et-Miquelon dans le xlsx 2024) :
    entre dans le total national, pas dans un département de métropole
    ou d'outre-mer de la carte. Paris / Lyon / Marseille sont découpés
    en arrondissements : le code commune (101–120, 201–216, 381–389)
    tranche, pas le préfixe B (754/757 pour Paris 1er/16e).
    """
    b = (dep_source or "").strip()
    c = (com_source or "").strip()
    if b == "B31":
        return None
    if b in ("2A0", "2A"):
        return "2A"
    if b in ("2B0", "2B"):
        return "2B"
    if c.isdigit():
        ic = int(c)
        if b.startswith("75") and 101 <= ic <= 120:
            return "75"
        if b.startswith("13") and 201 <= ic <= 216:
            return "13"
        if b.startswith("69") and 381 <= ic <= 389:
            return "69"
    if len(b) == 3 and b.startswith("97") and b.isdigit():
        return b
    if len(b) == 3 and b.startswith("0") and b.isdigit():
        return b[:2]
    if len(b) == 3 and b.isdigit():
        return b[:2]
    return None


def _valeur_cellule(elem: ET.Element, shared: list[str]):
    t = elem.attrib.get("t")
    if t == "inlineStr":
        texts = [
            n.text or ""
            for n in elem.iter(f"{NS}t")
        ]
        s = "".join(texts).strip()
        return s if s else None
    v = elem.find(f"{NS}v")
    if v is None or v.text is None:
        return None
    if t == "s":
        return shared[int(v.text)]
    if t == "b":
        return v.text == "1"
    brut = v.text
    try:
        return float(brut)
    except ValueError:
        return brut


def _shared_strings(z: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in z.namelist():
        return []
    racine = ET.fromstring(z.read("xl/sharedStrings.xml"))
    out: list[str] = []
    for si in racine.findall(f"{NS}si"):
        out.append("".join(n.text or "" for n in si.iter(f"{NS}t")))
    return out


def _annee_depuis_cellule(val) -> int | None:
    if val is None:
        return None
    m = ANNEE_RE.search(str(val))
    if not m:
        return None
    return int(m.group(1))


def _nombre(val):
    """Nombre IRCOM : float, ou None si n.c. / vide. 0 est licite."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    if not s or s.lower() in ("n.c.", "n.c", "nc"):
        return None
    s = s.replace(" ", "").replace(",", ".")
    try:
        return float(s)
    except ValueError as e:
        raise ValueError(f"nombre IRCOM illisible : {val!r}") from e


def extraire(chemin_xlsx: Path) -> tuple[int, list[dict]]:
    """xlsx communes → (année des revenus, lignes Total)."""
    with zipfile.ZipFile(chemin_xlsx) as z:
        shared = _shared_strings(z)
        feuilles = [
            n
            for n in z.namelist()
            if n.startswith("xl/worksheets/sheet") and n.endswith(".xml")
        ]
        if not feuilles:
            raise ValueError("xlsx sans feuille")
        # Une seule feuille ListeCommune (mesuré).
        src = z.open(sorted(feuilles)[0])
        annee: int | None = None
        lignes: list[dict] = []
        current: int | None = None
        cells: dict[str, object] = {}

        def flush() -> None:
            nonlocal annee
            e = cells.get("E")
            if e is None:
                return
            e_txt = str(e).strip()
            if annee is None:
                a = _annee_depuis_cellule(cells.get("E")) or _annee_depuis_cellule(
                    cells.get("B")
                )
                if a:
                    annee = a
            if e_txt != "Total":
                return
            dep = str(cells.get("B") or "").strip()
            com = str(cells.get("C") or "").strip()
            libelle = assainir_texte(str(cells.get("D") or "")) or ""
            if not dep or not com or not libelle:
                raise ValueError(
                    f"ligne Total incomplète : dep={dep!r} com={com!r} "
                    f"libelle={libelle!r}"
                )
            n_foyers = _nombre(cells.get("F"))
            if n_foyers is None:
                raise ValueError(
                    f"Total {dep}/{com} : nombre de foyers n.c. ou vide "
                    "(le total commune doit porter les foyers)"
                )
            impot_k = _nombre(cells.get("H"))
            n_imp = _nombre(cells.get("I"))
            lignes.append(
                {
                    "dep_source": dep,
                    "com_source": com,
                    "dep_carte": departement_carte(dep, com),
                    "libelle": libelle,
                    "n_foyers": int(n_foyers),
                    "impot_net_euros": (
                        None if impot_k is None else milliers_en_euros(impot_k)
                    ),
                    "n_foyers_imposes": None if n_imp is None else int(n_imp),
                }
            )

        for _event, elem in iterparse(src, events=("end",)):
            if not elem.tag.endswith("}c") and elem.tag != f"{NS}c":
                continue
            ref = elem.attrib.get("r")
            if not ref:
                elem.clear()
                continue
            col, row = _col_row(ref)
            if current is None:
                current = row
            if row != current:
                flush()
                current = row
                cells = {}
            val = _valeur_cellule(elem, shared)
            if val is not None:
                cells[col] = val
            elem.clear()
        if cells:
            flush()

    if annee is None:
        raise ValueError("année des revenus introuvable (cellule IRCOM revenus AAAA)")
    if not lignes:
        raise ValueError("aucune ligne Total extraite")
    vus: set[tuple[str, str]] = set()
    for o in lignes:
        cle = (o["dep_source"], o["com_source"])
        if cle in vus:
            raise ValueError(f"commune dupliquée : {cle}")
        vus.add(cle)
    return annee, lignes


def controler_ampleur(annee: int, lignes: list[dict]) -> None:
    """Garde-fous d'unité et de catalogue sur le millésime réel."""
    n = len(lignes)
    if not (N_COMMUNES_MIN <= n <= N_COMMUNES_MAX):
        raise ValueError(
            f"{n} communes Total, attendu entre {N_COMMUNES_MIN} et {N_COMMUNES_MAX}"
        )
    n_nc = sum(1 for o in lignes if o["impot_net_euros"] is None)
    if n_nc > N_NC_MAX:
        raise ValueError(f"{n_nc} communes n.c. sur l'impôt net, max {N_NC_MAX}")
    somme = sum(o["impot_net_euros"] or 0.0 for o in lignes)
    if not (BORNE_IMPOT_EUR[0] < somme < BORNE_IMPOT_EUR[1]):
        raise ValueError(
            "ordre de grandeur suspect (erreur d'unité ?) : "
            f"impôt net {annee} = {somme} € "
            f"hors ]{BORNE_IMPOT_EUR[0]:g}, {BORNE_IMPOT_EUR[1]:g}["
        )
    foyers = sum(o["n_foyers"] for o in lignes)
    if not (BORNE_FOYERS[0] < foyers < BORNE_FOYERS[1]):
        raise ValueError(
            f"foyers {annee} = {foyers}, hors ]{BORNE_FOYERS[0]:g}, {BORNE_FOYERS[1]:g}["
        )
    deps = {o["dep_carte"] for o in lignes if o["dep_carte"]}
    for code in ("75", "13", "69", "2A", "2B"):
        if code not in deps:
            raise ValueError(f"département {code} absent des totaux carte")


def _agreger(annee: int, lignes: list[dict]) -> tuple[list[dict], dict]:
    par_dep: dict[str, dict] = {}
    n_nc = 0
    n_foyers = 0
    impot = 0.0
    for o in lignes:
        n_foyers += o["n_foyers"]
        if o["impot_net_euros"] is None:
            n_nc += 1
        else:
            impot += o["impot_net_euros"]
        dep = o["dep_carte"]
        if not dep:
            continue
        slot = par_dep.setdefault(
            dep,
            {
                "annee": annee,
                "dep_carte": dep,
                "n_communes": 0,
                "n_communes_nc": 0,
                "n_foyers": 0,
                "impot_net_euros": 0.0,
            },
        )
        slot["n_communes"] += 1
        slot["n_foyers"] += o["n_foyers"]
        if o["impot_net_euros"] is None:
            slot["n_communes_nc"] += 1
        else:
            slot["impot_net_euros"] += o["impot_net_euros"]
    national = {
        "annee": annee,
        "n_communes": len(lignes),
        "n_communes_nc": n_nc,
        "n_foyers": n_foyers,
        "impot_net_euros": impot,
    }
    return list(par_dep.values()), national


def ecrire_db(conn, annee: int, lignes: list[dict]) -> str:
    """DELETE+INSERT en transaction, puis upsert_meta S47."""
    deps, national = _agreger(annee, lignes)
    date_donnees = date_fin_annee(annee)
    for o in lignes:
        o["annee"] = annee
    conn.executescript(_DDL)
    with conn:
        conn.execute("DELETE FROM ircom_communes")
        conn.execute("DELETE FROM ircom_departements")
        conn.execute("DELETE FROM ircom_national")
        conn.executemany(
            """INSERT INTO ircom_communes
               (annee, dep_carte, dep_source, com_source, libelle,
                n_foyers, impot_net_euros, n_foyers_imposes)
               VALUES (:annee, :dep_carte, :dep_source, :com_source, :libelle,
                       :n_foyers, :impot_net_euros, :n_foyers_imposes)""",
            lignes,
        )
        conn.executemany(
            """INSERT INTO ircom_departements
               (annee, dep_carte, n_communes, n_communes_nc,
                n_foyers, impot_net_euros)
               VALUES (:annee, :dep_carte, :n_communes, :n_communes_nc,
                       :n_foyers, :impot_net_euros)""",
            deps,
        )
        conn.execute(
            """INSERT INTO ircom_national
               (annee, n_communes, n_communes_nc, n_foyers, impot_net_euros)
               VALUES (:annee, :n_communes, :n_communes_nc,
                       :n_foyers, :impot_net_euros)""",
            national,
        )
    db.upsert_meta(
        conn,
        source_id=SOURCE_ID,
        nom=NOM_SOURCE,
        url=URL_DATASET,
        licence=LICENCE,
        frequence=FREQUENCE,
        date_donnees=date_donnees,
        lignes=len(lignes),
        notes=NOTES,
    )
    return date_donnees


def url_zip_courant(session=None) -> str:
    """URL de la ressource zip IRCOM la plus récente, via l'API data.gouv.

    Les chemins static.data.gouv.fr portent un horodatage : on ne les
    fige pas. Un zip dont le titre ne dit pas IRCOM / revenus est ignoré.
    """
    s = session or session_http()
    r = s.get(URL_API_DATASET, timeout=60)
    r.raise_for_status()
    data = r.json()
    cands: list[tuple[str, str, str]] = []
    for res in data.get("resources") or []:
        titre = (res.get("title") or "").lower()
        fmt = (res.get("format") or "").lower()
        url = res.get("url") or ""
        if fmt != "zip" or "ircom" not in titre or "revenu" not in titre:
            continue
        if not url:
            continue
        cands.append((res.get("last_modified") or "", url, res.get("title") or ""))
    if not cands:
        raise ValueError("aucune ressource zip IRCOM (revenus) sur le dataset")
    cands.sort(reverse=True)
    log.info("ressource IRCOM retenue : %s", cands[0][2])
    return cands[0][1]


def xlsx_communes_dans_zip(chemin_zip: Path, dest_xlsx: Path) -> Path:
    """Extrait le xlsx communes_complet du zip IRCOM."""
    with zipfile.ZipFile(chemin_zip) as z:
        cands = [
            n
            for n in z.namelist()
            if n.lower().endswith(".xlsx")
            and "communes_complet" in n.lower()
            and not n.startswith("__")
        ]
        if len(cands) != 1:
            raise ValueError(
                f"xlsx communes_complet : {len(cands)} candidat(s) {cands!r}"
            )
        dest_xlsx.parent.mkdir(parents=True, exist_ok=True)
        dest_xlsx.write_bytes(z.read(cands[0]))
        log.info("extrait : %s → %s", cands[0], dest_xlsx)
    return dest_xlsx


def main() -> int:
    try:
        s = session_http()
        url = url_zip_courant(s)
        chemin_zip = telecharger(
            url, FICHIER_ZIP, max_age_heures=CACHE_HEURES, session=s
        )
        xlsx = xlsx_communes_dans_zip(
            Path(chemin_zip), Path(chemin_zip).parent / "ircom_communes.xlsx"
        )
        annee, lignes = extraire(xlsx)
        controler_ampleur(annee, lignes)
        conn = db.init_db()
        date_donnees = ecrire_db(conn, annee, lignes)
        conn.close()
        somme = sum(o["impot_net_euros"] or 0.0 for o in lignes)
        n_nc = sum(1 for o in lignes if o["impot_net_euros"] is None)
        log.info(
            "ircom: %d communes Total, %d n.c., données au %s "
            "(revenus %s, impôt net publié %.3f Md€)",
            len(lignes),
            n_nc,
            date_donnees,
            annee,
            euros_en_md(somme),
        )
        return 0
    except Exception:
        log.exception("échec de l'ingestion S47 — base laissée intacte")
        return 1


if __name__ == "__main__":
    sys.exit(main())

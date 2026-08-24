"""P25 — Fiscalité directe locale (S48, REI DGFiP / DESF).

Source : jeu data.gouv `impots-locaux-fichier-de-recensement-des-elements-
dimposition-a-la-fiscalite-directe-locale-rei-4` (id 6657c57abbefc8869c7c6364),
pièce jointe zip du millésime courant (`REI-YYYY-fichier-notice-trace.zip`),
fichier `REI_YYYY.csv`. Licence relue le 24/08/2026 sur la fiche live
(HTTP 200) : « Licence Ouverte / Open Licence version 2.0 ». Le jeu ODS
tableur du même slug a 0 enregistrement : les données sont dans les
pièces jointes, pas dans l'API records.

CE PIPELINE N'EST PAS LA SOURCE S16, NI S13, NI S47
---------------------------------------------------
S16 = comptes OFGL (budget principal des communes, agrégat comptable
« Impôts locaux »). S48 = impositions primitives du rôle général,
par taxe et par collectivité bénéficiaire, année d'imposition N.
S13 = caisse du budget général de l'État. S47 = IR net sur rôle des
foyers, année des revenus. `source_id` = **S48**, jamais `'S16'` ni
`'S13'` ni `'S47'`. On n'additionne pas. On ne « rapproche » pas
65 Md€ (REI) et 55 Md€ (OFGL communes BP).

CE QUE LE PRODUIT REI EST (notice DESF, 4 p., millésime 2025)
------------------------------------------------------------
Rôle général, impositions primitives : pas les rôles supplémentaires,
pas les dégrèvements, pas les frais d'assiette perçus par l'État.
Une cellule vide = secret statistique (BOI-DJC-CADA-20 : moins de
3 ou 11 articles, ou un article > 85 % du communal) — ce n'est pas
un zéro. Unité native = **euros**. Md€ = euros ÷ 1e9, jamais ÷ 1000.

CE QUI N'EST PAS INGÉRÉ
-----------------------
Les taux. Les bases. Les compensations et fractions de TVA (TH, CVAE,
TFPB départementale). Les chambres (agriculture, CCI, CMA). Les
dotations de compensation (DCRTP, FNGIR, coefficient correcteur).
Les millésimes 1982–N-1. Les sous-colonnes CFE P33_1 / P33_2 /
P33_2U / P33_2Z / P33_3 (P33 est déjà le total intercommunal).
Les tranches de TEOM F23–F83 (F13 est déjà le montant réel total).
0 page communale.

PIÈGE IFERREG
-------------
Le produit IFER régional est **répliqué** sur chaque commune de la
région. Le sommer sur les 34 907 lignes fabrique un trillion. On
prend UNE valeur par LIBREG.

`date_donnees` = 31 décembre de l'année d'imposition (2025 →
2025-12-31), jamais last_update data.gouv ni last-modified du zip.
Seuils 650/750 j comme S22/S45/S47.

Exécution : python -m pipelines.ingest_rei
Base : FT_DB_PATH sinon data/france.db. Réécriture idempotente
(DELETE puis INSERT dans une transaction), puis upsert_meta
('S48', …). Échec → exit ≠ 0, base intacte.
"""

from __future__ import annotations

import csv
import io
import re
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

from pipelines import db
from pipelines.common import (
    assainir_texte,
    obtenir_logger,
    session_http,
    telecharger,
)

log = obtenir_logger("rei")

SOURCE_ID = "S48"
NOM_SOURCE = (
    "REI — fiscalité directe locale "
    "(DGFiP, DESF)"
)
URL_DATASET = (
    "https://www.data.gouv.fr/datasets/"
    "impots-locaux-fichier-de-recensement-des-elements-"
    "dimposition-a-la-fiscalite-directe-locale-rei-4"
)
URL_API_DATASET = (
    "https://www.data.gouv.fr/api/1/datasets/"
    "6657c57abbefc8869c7c6364/"
)
LICENCE = "Licence Ouverte / Open Licence version 2.0"
FREQUENCE = "annuelle"
CACHE_HEURES = 7 * 24
FICHIER_ZIP = "rei/rei_courant.zip"

CSV_NOM_RE = re.compile(r"REI_(\d{4})\.csv$", re.I)

# Produits exclusifs par taxe. Les partitions commune / syndicat /
# intercommunalité d'UNE taxe s'additionnent (ce n'est pas un
# double compte : ce sont des bénéficiaires distincts du même impôt).
COLONNES_TAXE: dict[str, tuple[str, ...]] = {
    "tfpb": ("E13", "E23", "E33"),
    "tfpnb": ("B13", "B23", "B33"),
    "ths": ("H13THS", "H23THS", "H33THS"),
    "thlv": ("H13LV", "H23LV", "H33LV"),
    "cfe": ("P13", "P23", "P33"),
    "teom": ("F13",),
    # Part incitative, déjà dans F13 (CGI 1522 bis). Stockée, jamais
    # additionnée au FDL affiché.
    "teomi": ("TIEOMC", "TIEOMS", "TIEOMG"),
    "tascom": ("TASCOMcom", "TASCOMgfp"),
    "ifer_local": ("IFERCOM", "IFERGFP", "IFERDEP"),
    "tse": (
        "E53", "E53A", "B53", "B53A", "P53",
        "H53THS", "H53LV", "H53ATHS", "H53ALV",
    ),
    "gemapi": (
        "E53gGEMAPI", "B53gGEMAPI", "P53gGEMAPI",
        "H53gGEMAPITHS", "H53gGEMAPILV",
    ),
    "tasa": ("E53TASA", "P53TASA"),
    "tafnb": ("B13TAFNB", "B33TAFNB", "B33MGPTAFNB"),
    "tsc": ("P53TSC",),
}

# Interdites : sous-totaux déjà contenus dans une colonne retenue.
COLONNES_INTERDITES = (
    "P33_1", "P33_2", "P33_2U", "P33_2Z", "P33_3",
    "F23", "F33", "F43", "F53", "F63", "F83",
)

for _interdite in COLONNES_INTERDITES:
    for _cols in COLONNES_TAXE.values():
        if _interdite in _cols:
            raise RuntimeError(
                f"colonne interdite {_interdite} listée dans COLONNES_TAXE"
            )

N_COMMUNES_MIN = 30_000
N_COMMUNES_MAX = 40_000
BORNE_TFPB = (30e9, 55e9)
BORNE_TEOM = (5e9, 15e9)
BORNE_CFE = (5e9, 12e9)

NOTES = (
    "impositions primitives du rôle général, année d'IMPOSITION, par "
    "taxe et bénéficiaire ; pas les comptes OFGL S16 ; pas l'IRCOM S47 ; "
    "pas la caisse S13 ; pas les compensations/fractions de TVA ; pas "
    "les chambres ; pas les taux ; cellule vide = secret statistique "
    "(BOI-DJC-CADA-20), pas un zéro ; IFER régional répliqué par commune "
    "— une valeur par région ; P33 est le total CFE intercommunal "
    "(P33_1/P33_2 non additionnés) ; F13 est le TEOM total (F23–F83 et "
    "TIEOM* non additionnés au FDL : TIEOM est une part de F13) ; "
    "unité native = euros ; Md€ = euros ÷ 1e9 ; "
    "date_donnees = 31/12 de l'année d'imposition, jamais last_update ; "
    "0 page communale"
)

_DDL = """
CREATE TABLE IF NOT EXISTS rei_communes (
    annee           INTEGER NOT NULL,
    dep_carte       TEXT,
    dep_source      TEXT    NOT NULL,
    com_source      TEXT    NOT NULL,
    libelle         TEXT    NOT NULL,
    tfpb            REAL,
    tfpnb           REAL,
    ths             REAL,
    thlv            REAL,
    cfe             REAL,
    teom            REAL,
    tascom          REAL,
    ifer_local      REAL,
    PRIMARY KEY (annee, dep_source, com_source)
);
CREATE INDEX IF NOT EXISTS idx_rei_communes_dep
    ON rei_communes(annee, dep_carte);

CREATE TABLE IF NOT EXISTS rei_departements (
    annee           INTEGER NOT NULL,
    dep_carte       TEXT    NOT NULL,
    n_communes      INTEGER NOT NULL,
    n_tfpb_nc       INTEGER NOT NULL,
    tfpb            REAL    NOT NULL,
    teom            REAL    NOT NULL,
    cfe             REAL    NOT NULL,
    ths             REAL    NOT NULL,
    tfpnb           REAL    NOT NULL,
    PRIMARY KEY (annee, dep_carte)
);

CREATE TABLE IF NOT EXISTS rei_national (
    annee           INTEGER PRIMARY KEY,
    n_communes      INTEGER NOT NULL,
    n_tfpb_nc       INTEGER NOT NULL,
    tfpb            REAL    NOT NULL,
    tfpnb           REAL    NOT NULL,
    ths             REAL    NOT NULL,
    thlv            REAL    NOT NULL,
    cfe             REAL    NOT NULL,
    teom            REAL    NOT NULL,
    teomi           REAL    NOT NULL,
    tascom          REAL    NOT NULL,
    ifer_local      REAL    NOT NULL,
    ifer_reg        REAL    NOT NULL,
    tse             REAL    NOT NULL,
    gemapi          REAL    NOT NULL,
    tasa            REAL    NOT NULL,
    tafnb           REAL    NOT NULL,
    tsc             REAL    NOT NULL
);
"""


def date_fin_annee(annee: int) -> str:
    """31 décembre de l'année d'imposition : 2025 → 2025-12-31."""
    if not isinstance(annee, int) or annee < 1990 or annee > 2100:
        raise ValueError(f"année hors plage : {annee!r}")
    return f"{annee}-12-31"


def euros_en_md(euros: float) -> float:
    """Euros → Md€. Jamais ÷ 1000."""
    return euros / 1e9


def departement_carte(dep_source: str) -> str | None:
    """Code département pour la carte, ou None si hors carte.

    977 Saint-Barthélemy et 978 Saint-Martin : dans le total national,
    pas sur la carte (comme B31 côté IRCOM). 2A / 2B / 971–976 conservés.
    """
    b = (dep_source or "").strip()
    if b in ("977", "978"):
        return None
    if b in ("2A", "2B"):
        return b
    if b.isdigit() and len(b) in (2, 3):
        return b
    return None


def _nombre(val) -> float | None:
    """Nombre REI : float, ou None si vide / n.c. 0 est licite."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    if not s or s.lower() in ("n.c.", "n.c", "nc", "n.s.", "ns"):
        return None
    s = s.replace(" ", "").replace(",", ".")
    try:
        return float(s)
    except ValueError as e:
        raise ValueError(f"nombre REI illisible : {val!r}") from e


def _somme_colonnes(row: dict[str, str], noms: tuple[str, ...]) -> float | None:
    """Somme des colonnes présentes et non occultées. None si toutes vides."""
    total = 0.0
    vu = False
    for nom in noms:
        if nom not in row:
            continue
        v = _nombre(row[nom])
        if v is None:
            continue
        total += v
        vu = True
    return total if vu else None


def extraire(chemin_csv: Path, annee: int) -> tuple[list[dict], dict[str, float]]:
    """CSV REI → (lignes communales, IFER régional par LIBREG)."""
    brut = chemin_csv.read_bytes()
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            texte = brut.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError("encodage REI illisible (utf-8 / cp1252 / latin-1)")

    lecteur = csv.DictReader(io.StringIO(texte), delimiter=";")
    if not lecteur.fieldnames:
        raise ValueError("CSV REI sans en-tête")
    champs = set(lecteur.fieldnames)
    manquants = [
        c
        for groupe in COLONNES_TAXE.values()
        for c in groupe
        if c not in champs
    ]
    # Colonnes optionnelles (millésime ancien) : on tolère l'absence
    # de TSE AUTRES / GEMAPI TH / TSC, pas de E13/F13/P33.
    obligatoires = ("DEP", "COM", "LIBCOM", "E13", "F13", "P33", "IFERREG")
    absents = [c for c in obligatoires if c not in champs]
    if absents:
        raise ValueError(f"colonnes REI absentes : {absents}")
    if manquants:
        log.info("colonnes optionnelles absentes (ignorées) : %s", manquants[:12])

    vus: set[tuple[str, str]] = set()
    lignes: list[dict] = []
    ifer_reg: dict[str, float] = {}
    for row in lecteur:
        dep = (row.get("DEP") or "").strip()
        com = (row.get("COM") or "").strip()
        if not dep or not com:
            continue
        cle = (dep, com)
        if cle in vus:
            raise ValueError(f"commune dupliquée REI : {dep}/{com}")
        vus.add(cle)
        libelle = assainir_texte(row.get("LIBCOM")) or f"{dep}{com}"
        libreg = assainir_texte(row.get("LIBREG")) or ""
        ifer = _nombre(row.get("IFERREG"))
        if libreg and ifer is not None:
            precedent = ifer_reg.get(libreg)
            if precedent is None:
                ifer_reg[libreg] = ifer
            elif abs(precedent - ifer) > 0.5:
                raise ValueError(
                    f"IFERREG divergent dans {libreg!r} : "
                    f"{precedent} vs {ifer}"
                )
        produit = {
            nom: _somme_colonnes(row, cols)
            for nom, cols in COLONNES_TAXE.items()
        }
        lignes.append(
            {
                "dep_source": dep,
                "com_source": com,
                "dep_carte": departement_carte(dep),
                "libelle": libelle,
                "tfpb": produit["tfpb"],
                "tfpnb": produit["tfpnb"],
                "ths": produit["ths"],
                "thlv": produit["thlv"],
                "cfe": produit["cfe"],
                "teom": produit["teom"],
                "tascom": produit["tascom"],
                "ifer_local": produit["ifer_local"],
                "_tse": produit["tse"] or 0.0,
                "_gemapi": produit["gemapi"] or 0.0,
                "_tasa": produit["tasa"] or 0.0,
                "_tafnb": produit["tafnb"] or 0.0,
                "_tsc": produit["tsc"] or 0.0,
                "_teomi": produit["teomi"] or 0.0,
            }
        )
    if not lignes:
        raise ValueError("CSV REI sans aucune commune")
    log.info(
        "REI %s : %d communes, %d régions IFER",
        annee,
        len(lignes),
        len(ifer_reg),
    )
    return lignes, ifer_reg


def _zero_si_none(v: float | None) -> float:
    return 0.0 if v is None else v


def _agreger(
    annee: int,
    lignes: list[dict],
    ifer_reg: dict[str, float],
) -> tuple[list[dict], dict]:
    par_dep: dict[str, dict] = {}
    n_tfpb_nc = 0
    tot = {k: 0.0 for k in (
        "tfpb", "tfpnb", "ths", "thlv", "cfe", "teom", "teomi",
        "tascom", "ifer_local", "tse", "gemapi", "tasa", "tafnb", "tsc",
    )}
    for o in lignes:
        tot["tfpb"] += _zero_si_none(o["tfpb"])
        tot["tfpnb"] += _zero_si_none(o["tfpnb"])
        tot["ths"] += _zero_si_none(o["ths"])
        tot["thlv"] += _zero_si_none(o["thlv"])
        tot["cfe"] += _zero_si_none(o["cfe"])
        tot["teom"] += _zero_si_none(o["teom"])
        tot["tascom"] += _zero_si_none(o["tascom"])
        tot["ifer_local"] += _zero_si_none(o["ifer_local"])
        tot["tse"] += o["_tse"]
        tot["gemapi"] += o["_gemapi"]
        tot["tasa"] += o["_tasa"]
        tot["tafnb"] += o["_tafnb"]
        tot["tsc"] += o["_tsc"]
        tot["teomi"] += o["_teomi"]
        if o["tfpb"] is None:
            n_tfpb_nc += 1
        dep = o["dep_carte"]
        if dep is None:
            continue
        slot = par_dep.setdefault(
            dep,
            {
                "annee": annee,
                "dep_carte": dep,
                "n_communes": 0,
                "n_tfpb_nc": 0,
                "tfpb": 0.0,
                "teom": 0.0,
                "cfe": 0.0,
                "ths": 0.0,
                "tfpnb": 0.0,
            },
        )
        slot["n_communes"] += 1
        if o["tfpb"] is None:
            slot["n_tfpb_nc"] += 1
        else:
            slot["tfpb"] += o["tfpb"]
        slot["teom"] += _zero_si_none(o["teom"])
        slot["cfe"] += _zero_si_none(o["cfe"])
        slot["ths"] += _zero_si_none(o["ths"])
        slot["tfpnb"] += _zero_si_none(o["tfpnb"])
    national = {
        "annee": annee,
        "n_communes": len(lignes),
        "n_tfpb_nc": n_tfpb_nc,
        "tfpb": tot["tfpb"],
        "tfpnb": tot["tfpnb"],
        "ths": tot["ths"],
        "thlv": tot["thlv"],
        "cfe": tot["cfe"],
        "teom": tot["teom"],
        "teomi": tot["teomi"],
        "tascom": tot["tascom"],
        "ifer_local": tot["ifer_local"],
        "ifer_reg": sum(ifer_reg.values()),
        "tse": tot["tse"],
        "gemapi": tot["gemapi"],
        "tasa": tot["tasa"],
        "tafnb": tot["tafnb"],
        "tsc": tot["tsc"],
    }
    return list(par_dep.values()), national


def controler_ampleur(annee: int, lignes: list[dict], ifer_reg: dict[str, float]) -> None:
    """Garde-fous d'ampleur sur le millésime réel, pas la fixture."""
    n = len(lignes)
    if not (N_COMMUNES_MIN <= n <= N_COMMUNES_MAX):
        raise ValueError(f"communes REI hors plage : {n}")
    tfpb = sum(_zero_si_none(o["tfpb"]) for o in lignes)
    teom = sum(_zero_si_none(o["teom"]) for o in lignes)
    cfe = sum(_zero_si_none(o["cfe"]) for o in lignes)
    if not (BORNE_TFPB[0] <= tfpb <= BORNE_TFPB[1]):
        raise ValueError(f"TFPB hors plage : {tfpb}")
    if not (BORNE_TEOM[0] <= teom <= BORNE_TEOM[1]):
        raise ValueError(f"TEOM hors plage : {teom}")
    if not (BORNE_CFE[0] <= cfe <= BORNE_CFE[1]):
        raise ValueError(f"CFE hors plage : {cfe}")
    ifer = sum(ifer_reg.values())
    if ifer > 5e9:
        raise ValueError(
            f"IFER régional aberrant (réplication non repliée ?) : {ifer}"
        )
    if annee < 2020 or annee > 2100:
        raise ValueError(f"année REI hors plage : {annee}")


def ecrire_db(
    conn,
    annee: int,
    lignes: list[dict],
    ifer_reg: dict[str, float],
) -> str:
    """DELETE+INSERT en transaction, puis upsert_meta S48."""
    deps, national = _agreger(annee, lignes, ifer_reg)
    date_donnees = date_fin_annee(annee)
    a_inserer = [
        {
            "annee": annee,
            "dep_carte": o["dep_carte"],
            "dep_source": o["dep_source"],
            "com_source": o["com_source"],
            "libelle": o["libelle"],
            "tfpb": o["tfpb"],
            "tfpnb": o["tfpnb"],
            "ths": o["ths"],
            "thlv": o["thlv"],
            "cfe": o["cfe"],
            "teom": o["teom"],
            "tascom": o["tascom"],
            "ifer_local": o["ifer_local"],
        }
        for o in lignes
    ]
    conn.executescript(_DDL)
    with conn:
        conn.execute("DELETE FROM rei_communes")
        conn.execute("DELETE FROM rei_departements")
        conn.execute("DELETE FROM rei_national")
        conn.executemany(
            """INSERT INTO rei_communes
               (annee, dep_carte, dep_source, com_source, libelle,
                tfpb, tfpnb, ths, thlv, cfe, teom, tascom, ifer_local)
               VALUES (:annee, :dep_carte, :dep_source, :com_source, :libelle,
                       :tfpb, :tfpnb, :ths, :thlv, :cfe, :teom, :tascom,
                       :ifer_local)""",
            a_inserer,
        )
        conn.executemany(
            """INSERT INTO rei_departements
               (annee, dep_carte, n_communes, n_tfpb_nc,
                tfpb, teom, cfe, ths, tfpnb)
               VALUES (:annee, :dep_carte, :n_communes, :n_tfpb_nc,
                       :tfpb, :teom, :cfe, :ths, :tfpnb)""",
            deps,
        )
        conn.execute(
            """INSERT INTO rei_national
               (annee, n_communes, n_tfpb_nc, tfpb, tfpnb, ths, thlv,
                cfe, teom, teomi, tascom, ifer_local, ifer_reg,
                tse, gemapi, tasa, tafnb, tsc)
               VALUES (:annee, :n_communes, :n_tfpb_nc, :tfpb, :tfpnb,
                       :ths, :thlv, :cfe, :teom, :teomi, :tascom,
                       :ifer_local, :ifer_reg, :tse, :gemapi, :tasa,
                       :tafnb, :tsc)""",
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


def url_zip_courant(session=None) -> tuple[str, int]:
    """URL du zip REI du millésime le plus récent, via l'API data.gouv."""
    s = session or session_http()
    r = s.get(URL_API_DATASET, timeout=60)
    r.raise_for_status()
    data = r.json()
    cands: list[tuple[int, str, str]] = []
    for res in data.get("resources") or []:
        titre = res.get("title") or ""
        fmt = (res.get("format") or "").lower()
        url = res.get("url") or ""
        if fmt != "zip" or not url:
            continue
        m = re.search(r"REI[-_](20\d{2})", titre, re.I)
        if not m:
            continue
        cands.append((int(m.group(1)), url, titre))
    if not cands:
        raise ValueError("aucune ressource zip REI-YYYY sur le dataset")
    cands.sort(reverse=True)
    log.info("ressource REI retenue : %s", cands[0][2])
    return cands[0][1], cands[0][0]


def csv_dans_zip(chemin_zip: Path, dest_csv: Path, annee_attendue: int) -> Path:
    """Extrait REI_YYYY.csv du zip. Refuse l'ambiguïté."""
    with zipfile.ZipFile(chemin_zip) as z:
        cands = []
        for n in z.namelist():
            if n.startswith("__"):
                continue
            m = CSV_NOM_RE.search(Path(n).name)
            if m:
                cands.append((n, int(m.group(1))))
        if len(cands) != 1:
            raise ValueError(f"CSV REI : {len(cands)} candidat(s) {cands!r}")
        nom, annee = cands[0]
        if annee != annee_attendue:
            raise ValueError(
                f"année CSV {annee} ≠ année zip {annee_attendue}"
            )
        dest_csv.parent.mkdir(parents=True, exist_ok=True)
        dest_csv.write_bytes(z.read(nom))
        log.info("extrait : %s → %s", nom, dest_csv)
    return dest_csv


def main() -> int:
    try:
        s = session_http()
        url, annee = url_zip_courant(s)
        chemin_zip = telecharger(
            url, FICHIER_ZIP, max_age_heures=CACHE_HEURES, session=s
        )
        csv_path = csv_dans_zip(
            Path(chemin_zip),
            Path(chemin_zip).parent / f"REI_{annee}.csv",
            annee,
        )
        lignes, ifer_reg = extraire(csv_path, annee)
        controler_ampleur(annee, lignes, ifer_reg)
        conn = db.init_db()
        date_donnees = ecrire_db(conn, annee, lignes, ifer_reg)
        conn.close()
        tfpb = sum(_zero_si_none(o["tfpb"]) for o in lignes)
        n_nc = sum(1 for o in lignes if o["tfpb"] is None)
        log.info(
            "rei: %d communes, %d TFPB occultés, données au %s "
            "(imposition %s, TFPB publié %.3f Md€, IFER régional %.3f Md€)",
            len(lignes),
            n_nc,
            date_donnees,
            annee,
            euros_en_md(tfpb),
            euros_en_md(sum(ifer_reg.values())),
        )
        return 0
    except Exception:
        log.exception("échec de l'ingestion S48 — base laissée intacte")
        return 1


if __name__ == "__main__":
    sys.exit(main())

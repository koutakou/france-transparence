"""P8 — Lobbying : répertoire des représentants d'intérêts HATVP (AGORA, S4).

Source : vues séparées CSV `https://www.hatvp.fr/agora/opendata/csv/Vues_Separees_CSV.zip`
(~14 Mo, 15 tables, mise à jour quotidienne ~04h30). Le JSON intégral de 137 Mo
n'est PAS utilisé (décision SOURCES.md P8). Licence Ouverte Etalab.

Volumétrie réelle (constatée le 19/08/2026) : 4 067 entités (3 692 actives,
375 désinscrites), 112 450 fiches d'activités, 24 424 exercices. ⚠ Les chiffres
« 6 829 entités / 118 516 activités / 24 568 exercices » des rapports Phase 0
sont des artefacts de `wc -l` : les champs entre guillemets contiennent des
retours à la ligne (6 830 lignes physiques = 4 067 enregistrements + en-tête
+ 2 762 retours internes, vérifié par deux parseurs CSV).

Flag natif « défaut de déclaration » : la vue `15_exercices.csv` n'a qu'UN flag,
`declaration_incomplete`, documenté par la HATVP comme « l'organisation apparaît
dans la liste des représentants d'intérêts n'ayant pas communiqué à la Haute
Autorité tout ou partie des informations exigibles par la loi » — c'est le champ
`defautDeclaration` du JSON (vérifié sur SUNROCK, exercice 2025). Aucun flag
n'est inventé : la nuance « rien communiqué / communication partielle » est
dérivée de `date_publication` (vide ou non) de l'exercice flaggé.

Tables écrites (remplacement complet, idempotent) :
- lobby_entites : id (representants_id AGORA), identifiant_national (SIREN/RNA/
  HATVP), type_identifiant, denomination, nom_usage, sigle, categorie (label
  natif), ville, pays, active (0 si désinscrite), date_cessation,
  date_premiere_publication, derniere_publication_activite, secteurs,
  niveaux_intervention, nb_activites_total, nb_activites_12m,
  budget_periode_debut/fin (dernier exercice avec dépenses déclarées),
  budget_libelle (fourchette telle quelle) + budget_min/budget_max (bornes
  natives, max NULL si non borné), effectifs (nombre_salaries ETP — donnée
  native numérique, pas une fourchette), ca_libelle + ca_min/ca_max,
  defaut_declaration (flag natif = liste officielle HATVP),
  declaration_incomplete (flag natif ET publication partielle existante),
  url_fiche (fiche publique hatvp.fr).
- lobby_activites : détail des 24 derniers mois (date de publication) —
  activite_id, entite_id, exercice_id, periode_debut/fin, date_publication,
  identifiant_fiche, objet (résumé 500 c.), domaines, decisions, institutions
  (catégories natives de responsables publics visés), ministeres, actions.
  L'historique complet (2018→) reste couvert par les agrégats.
- lobby_agg_institutions : institution (catégorie native normalisée), groupe
  (Gouvernement, Parlement, Présidence…), nb_activites_total, nb_activites_12m,
  nb_entites.
- lobby_agg_ministeres : departement_ministeriel précisé (trim), mêmes
  compteurs. Le champ est multivalué et l'export CSV le coupe sur la
  virgule : les portefeuilles connus sont RECOMPOSÉS via la table fermée
  PORTEFEUILLES_MINISTERIELS (« Environnement » + « énergie et mer » →
  « Environnement, énergie et mer »), les compteurs restant des
  count(DISTINCT activite_id) — union des fragments, jamais somme. Un
  libellé hors table s'affiche brut.
- lobby_agg_top_entites : top 50 par nb d'activités publiées sur 12 mois
  (rang, entite_id, denomination, categorie, nb_activites_12m).
- lobby_agg_budgets : répartition des entités ACTIVES par fourchette de
  dépenses (dernier exercice déclaré) — fourchette, borne_min/max, nb_entites.
- lobby_agg_trimestres : série complète 2018→ (trimestre 'AAAA-Tn',
  nb_activites, nb_entites).
- alertes (table PARTAGÉE, CREATE IF NOT EXISTS, seuls les types
  'lobbying_defaut_declaration' et 'lobbying_declaration_incomplete' sont
  recalculés) : une alerte par entité sur la liste officielle (flag natif,
  base légale Sapin II) + une alerte agrégat.
- meta_sources : source_id 'S4', fréquence quotidienne, date_donnees = date de
  publication la plus récente réellement constatée dans les données.

Module UI : « Lobbying ».

Exécution : `python -m pipelines.ingest_lobbying` (échec → exit ≠ 0).
Base : data/france.db, ou FT_DB_PATH pour les épreuves sur base jetable.
"""

from __future__ import annotations

import sys
import zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import duckdb

from pipelines import db
from pipelines.common import (
    RAW_DIR,
    assainir_texte_integral,
    obtenir_logger,
    telecharger,
)

log = obtenir_logger("lobbying")

ID_SOURCE = "S4"
NOM_SOURCE = "HATVP — Répertoire des représentants d'intérêts (AGORA)"
URL_ZIP = "https://www.hatvp.fr/agora/opendata/csv/Vues_Separees_CSV.zip"
LICENCE = "Licence Ouverte Etalab"
FREQUENCE = "quotidienne"

DOSSIER_RAW = RAW_DIR / "lobbying"

# Fichiers du zip réellement exploités (les autres vues — dirigeants,
# collaborateurs, clients, affiliations, bénéficiaires — ne sont pas ingérées).
FICHIERS_REQUIS = (
    "1_informations_generales.csv",
    "6_niveaux_intervention.csv",
    "7_domaines_intervention.csv",
    "8_objets_activites.csv",
    "9_secteurs_activites.csv",
    "10_actions_menees.csv",
    "12_decisions_concernees.csv",
    "13_ministeres_aai_api.csv",
    "14_observations.csv",
    "15_exercices.csv",
)

TYPES_ALERTES = ("lobbying_defaut_declaration", "lobbying_declaration_incomplete")

BASE_LEGALE = (
    "Loi n° 2016-1691 du 09/12/2016 « Sapin II » (répertoire des représentants "
    "d'intérêts) — art. 18-3 de la loi n° 2013-907 du 11/10/2013 : communication "
    "annuelle des activités et moyens à la HATVP ; sanctions pénales en cas de "
    "manquement (art. 18-9 et 18-10) ; décret n° 2017-867 du 09/05/2017."
)

REGLE_DEFAUT = (
    "Flag natif AGORA (vue 15_exercices.csv, champ declaration_incomplete = "
    "defautDeclaration du JSON) : organisation inscrite sur la liste des "
    "représentants d'intérêts n'ayant pas communiqué à la Haute Autorité tout "
    "ou partie des informations exigibles par la loi, pour au moins un exercice. "
    "Aucun calcul de délai : constat officiel HATVP repris tel quel."
)

# Regroupement d'affichage des catégories natives de responsables publics.
# La catégorie native est TOUJOURS conservée telle quelle dans la colonne
# `institution` ; ce mapping n'ajoute qu'une étiquette de regroupement.
# NB : la donnée ne sépare pas AN et Sénat (catégorie parlementaire unique).
GROUPES_INSTITUTIONS = {
    "Membre du Gouvernement ou membre de cabinet ministériel": "Gouvernement",
    "Député, sénateur, collaborateur du Président de l'Assemblée nationale ou "
    "du Président du Sénat, d'un député, d'un sénateur ou d'un groupe "
    "parlementaire, agents des services des assemblées parlementaires":
        "Parlement (AN + Sénat)",
    "Collaborateur du Président de la République": "Présidence de la République",
    "Titulaire d'un emploi à la décision du Gouvernement": "Administration de l'État",
    "Agent de l'État": "Administration de l'État",
    "Directeur ou secrétaire général, ou leur adjoint, ou membre du collège ou "
    "d'une commission des sanctions d'une autorité administrative ou publique "
    "indépendante": "AAI / API",
    "Élu ou membre de cabinet d'une collectivité territoriale":
        "Collectivités territoriales",
    "Agent d'une collectivité territoriale": "Collectivités territoriales",
    "Agent d'un centre hospitalier": "Établissements publics de santé",
}

# Recomposition des portefeuilles ministériels éclatés par la HATVP.
#
# Le champ « département ministériel » de la vue 13 est MULTIVALUÉ, et l'export
# CSV le sépare par une virgule — sans distinguer la virgule qui sépare deux
# ministères visés de celle qui appartient au nom d'un seul portefeuille.
# « Environnement, énergie et mer » ressort donc en DEUX lignes portant le même
# action_representation_interet_id, et le tableau des ministères visés affiche
# deux fragments (« Environnement », « énergie et mer ») au lieu d'un libellé.
#
# Pourquoi cette table est FERMÉE (écrite en dur, jamais devinée) :
#
# 1. Aucune règle syntaxique ne sépare un fragment d'un vrai second ministère.
#    L'espace de tête n'est PAS un discriminant : 325 libellés apparaissent à
#    la fois avec et sans espace initial (« Economie et finances » : 15 764
#    occurrences avec, 9 644 sans). Un morceau situé après une virgule est le
#    plus souvent un ministère à part entière.
# 2. L'égalité des compteurs n'est PAS une preuve. « Communauté d'agglomération
#    du Cotentin » et « Communauté d'agglomération d'Epinal » ont les mêmes
#    trois compteurs par coïncidence ; « Logement » et « Education nationale »
#    ont le même nombre d'activités historiques (2 938) mais pas le même
#    compteur 12 mois. Fusionner sur les compteurs fabriquerait des ministères.
#
# Le seul critère retenu est l'identité STRICTE des ensembles d'identifiants
# d'action : deux fragments d'un même portefeuille sont toujours déclarés
# ensemble, sur exactement les mêmes actions. Les huit familles ci-dessous sont
# celles — et les seules — que ce critère isole dans la donnée réelle.
#
# Un libellé absent de cette table est affiché BRUT : dégradation propre, jamais
# une erreur. Si la HATVP renomme un portefeuille (remaniement), les fragments
# devenus introuvables sont signalés par `verifier_fragments()` — la table doit
# alors être relue à la main, pas élargie automatiquement.
PORTEFEUILLES_MINISTERIELS: tuple[tuple[str, ...], ...] = (
    ("Environnement", "énergie et mer"),
    ("Agriculture", "agroalimentaire et forêt"),
    ("Travail", "emploi", "formation professionnelle et dialogue social"),
    ("Aménagement du territoire", "ruralité et collectivités territoriales"),
    ("Education nationale", "enseignement supérieur et recherche"),
    ("Ville", "jeunesse et sport"),
    ("Famille", "enfance et droits des femmes"),
    ("Autorité de régulation des communications électroniques",
     "des postes et de la distribution de la presse"),
)

# fragment (trimé, tel qu'il sort du CSV) → libellé de portefeuille recomposé.
FRAGMENTS_MINISTERIELS: dict[str, str] = {
    fragment: ", ".join(famille)
    for famille in PORTEFEUILLES_MINISTERIELS
    for fragment in famille
}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS lobby_entites (
    id                           TEXT PRIMARY KEY,
    identifiant_national         TEXT,
    type_identifiant             TEXT,
    denomination                 TEXT NOT NULL,
    nom_usage                    TEXT,
    sigle                        TEXT,
    categorie                    TEXT,
    ville                        TEXT,
    pays                         TEXT,
    active                       INTEGER NOT NULL DEFAULT 1,
    date_cessation               TEXT,
    date_premiere_publication    TEXT,
    derniere_publication_activite TEXT,
    secteurs                     TEXT,
    niveaux_intervention         TEXT,
    nb_activites_total           INTEGER NOT NULL DEFAULT 0,
    nb_activites_12m             INTEGER NOT NULL DEFAULT 0,
    budget_periode_debut         TEXT,
    budget_periode_fin           TEXT,
    budget_libelle               TEXT,
    budget_min                   REAL,
    budget_max                   REAL,
    effectifs                    REAL,
    ca_libelle                   TEXT,
    ca_min                       REAL,
    ca_max                       REAL,
    defaut_declaration           INTEGER NOT NULL DEFAULT 0,
    declaration_incomplete       INTEGER NOT NULL DEFAULT 0,
    url_fiche                    TEXT
);
CREATE INDEX IF NOT EXISTS idx_lobby_entites_categorie ON lobby_entites(categorie);
CREATE INDEX IF NOT EXISTS idx_lobby_entites_defaut    ON lobby_entites(defaut_declaration);

CREATE TABLE IF NOT EXISTS lobby_activites (
    activite_id       TEXT PRIMARY KEY,
    entite_id         TEXT NOT NULL,
    exercice_id       TEXT,
    periode_debut     TEXT,
    periode_fin       TEXT,
    date_publication  TEXT,
    identifiant_fiche TEXT,
    objet             TEXT,
    domaines          TEXT,
    decisions         TEXT,
    institutions      TEXT,
    ministeres        TEXT,
    actions           TEXT
);
CREATE INDEX IF NOT EXISTS idx_lobby_activites_entite ON lobby_activites(entite_id);
CREATE INDEX IF NOT EXISTS idx_lobby_activites_date   ON lobby_activites(date_publication);

CREATE TABLE IF NOT EXISTS lobby_agg_institutions (
    institution        TEXT PRIMARY KEY,
    groupe             TEXT NOT NULL,
    nb_activites_total INTEGER NOT NULL,
    nb_activites_12m   INTEGER NOT NULL,
    nb_entites         INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS lobby_agg_ministeres (
    ministere          TEXT PRIMARY KEY,
    nb_activites_total INTEGER NOT NULL,
    nb_activites_12m   INTEGER NOT NULL,
    nb_entites         INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS lobby_agg_top_entites (
    rang             INTEGER PRIMARY KEY,
    entite_id        TEXT NOT NULL,
    denomination     TEXT NOT NULL,
    categorie        TEXT,
    nb_activites_12m INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS lobby_agg_budgets (
    fourchette TEXT PRIMARY KEY,
    borne_min  REAL,
    borne_max  REAL,
    nb_entites INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS lobby_agg_trimestres (
    trimestre    TEXT PRIMARY KEY,
    nb_activites INTEGER NOT NULL,
    nb_entites   INTEGER NOT NULL
);

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
# Helpers purs (testés unitairement)
# ---------------------------------------------------------------------------


def parse_borne(valeur: str | None, libelle: str | None) -> float | None:
    """Borne numérique native d'une fourchette AGORA.

    - `libelle` vide → rien n'a été déclaré → None (les 0/0.0 de remplissage
      de la vue ne sont PAS des montants) ;
    - 'inf' (fourchette non bornée, ex. « ≥ 10 000 000 € ») → None ;
    - sinon float.
    """
    if not libelle or not str(libelle).strip():
        return None
    if valeur is None or str(valeur).strip() in ("", "inf"):
        return None
    try:
        return float(valeur)
    except ValueError:
        return None


def iso_de_fr(valeur: str | None) -> str | None:
    """'16/05/2024 16:21:46' ou '01/04/2024' → '2024-05-16' / '2024-04-01'.

    Les dates déjà ISO sont renvoyées telles quelles (tronquées à la date).
    Valeur non reconnue → None (jamais de date fabriquée).
    """
    if not valeur:
        return None
    v = str(valeur).strip()
    if not v:
        return None
    v = v.split(" ")[0].split("T")[0]
    if len(v) == 10 and v[4] == "-" and v[7] == "-":  # déjà ISO
        return v
    parts = v.split("/")
    if len(parts) == 3 and len(parts[2]) == 4:
        j, m, a = parts
        try:
            return date(int(a), int(m), int(j)).isoformat()
        except ValueError:
            return None
    return None


def url_fiche_hatvp(identifiant_national: str | None) -> str | None:
    """Fiche publique AGORA (motif d'URL du site hatvp.fr, vérifié HTTP 200)."""
    if not identifiant_national or not str(identifiant_national).strip():
        return None
    return ("https://www.hatvp.fr/fiche-organisation/?organisation="
            + str(identifiant_national).strip())


def groupe_institution(categorie_native: str) -> str:
    """Étiquette de regroupement d'une catégorie native (apostrophes unifiées)."""
    cle = categorie_native.replace("’", "'").strip()
    return GROUPES_INSTITUTIONS.get(cle, "Autre")


def portefeuille_ministeriel(libelle: str) -> str:
    """Fragment connu → portefeuille recomposé ; sinon le libellé tel quel.

    Aucune heuristique : uniquement la table fermée FRAGMENTS_MINISTERIELS.
    Un libellé inconnu ressort brut (dégradation propre, jamais une erreur).
    """
    return FRAGMENTS_MINISTERIELS.get(libelle.strip(), libelle.strip())


def verifier_fragments(libelles_observes) -> list[str]:
    """Fragments de la table fermée qui n'apparaissent PLUS dans la donnée.

    Sert de sonnette : si la HATVP renomme un portefeuille après un
    remaniement, la table cesse silencieusement de recomposer. La liste
    retournée (triée) doit rester vide ; le pipeline la journalise en
    WARNING et les tests la vérifient.
    """
    vus = {(lib or "").strip() for lib in libelles_observes}
    return sorted(f for f in FRAGMENTS_MINISTERIELS if f not in vus)


def assainir_lignes(lignes: list[tuple]) -> tuple[list[tuple], int]:
    """Jeu de lignes prêtes à écrire → même jeu assaini, et nombre de VALEURS
    modifiées.

    Toutes les chaînes sont assainies, sans liste blanche de colonnes. POURQUOI
    SANS LISTE : les sept jeux de ce pipeline sortent de `fetchall()` sous forme
    de tuples positionnels, sans nom de colonne ; une liste d'indices serait un
    doublon silencieux du schéma, qui se périmerait à la première colonne
    insérée. Les valeurs non-`str` (entiers, `None`, flottants) sont rendues à
    l'identique par `assainir_texte_integral`, et aucune colonne de ce pipeline
    ne transporte de sérialisation dont l'hygiène casserait la syntaxe : les
    multivaluées sont des agrégats `string_agg(…, ' | ')`, pas du JSON.

    🛑 CE PASSAGE EST EN AVAL DE TOUT APPARIEMENT, ET C'EST OBLIGATOIRE.
    `groupe_institution`, `portefeuille_ministeriel` et `verifier_fragments`
    apparient des libellés bruts sur la table fermée `FRAGMENTS_MINISTERIELS`,
    par `.strip()` et `.replace("’", "'")`. Assainir en amont d'eux changerait
    ce qu'ils apparient — et `verifier_fragments` signalerait des fragments
    « absents » qui ne le sont pas. L'hygiène est donc posée à la toute fin de
    `construire()`, après le dernier `fetchall()` et avant la moindre écriture.
    """
    modifiees = 0
    propres = []
    for ligne in lignes:
        neuve = []
        for valeur in ligne:
            propre = assainir_texte_integral(valeur)
            if propre != valeur:
                modifiees += 1
            neuve.append(propre)
        propres.append(tuple(neuve))
    return propres, modifiees



# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------


def extraire_zip(chemin_zip: Path, dossier: Path) -> Path:
    """Extrait les seules vues requises du zip HATVP, retourne leur dossier.

    Le zip contient un répertoire racine `Vues_Separees/` (toléré absent).
    N'extrait que les 10 fichiers exploités (~103 Mo au lieu de 110) ;
    RuntimeError si l'un d'eux manque dans l'archive.
    """
    dossier_csv = dossier / "Vues_Separees"
    dossier_csv.mkdir(parents=True, exist_ok=True)
    requis = set(FICHIERS_REQUIS)
    with zipfile.ZipFile(chemin_zip) as z:
        membres = {Path(m).name: m for m in z.namelist()
                   if Path(m).name in requis}
        manquants = sorted(requis - set(membres))
        if manquants:
            raise RuntimeError(
                f"vues CSV manquantes dans le zip HATVP : {manquants}")
        for nom, membre in membres.items():
            with z.open(membre) as src, open(dossier_csv / nom, "wb") as out:
                out.write(src.read())
    return dossier_csv


# ---------------------------------------------------------------------------
# Construction des données (duckdb, lecture seule des CSV)
# ---------------------------------------------------------------------------


def _rc(dossier: Path, nom: str) -> str:
    """Fragment SQL duckdb de lecture d'une vue (tout en varchar, fidèle)."""
    chemin = str((dossier / nom).resolve()).replace("'", "''")
    return (f"read_csv('{chemin}', delim=';', header=true, all_varchar=true)")


def construire(dossier_csv: Path, aujourdhui: date) -> dict:
    """Lit les vues CSV et construit toutes les lignes à écrire.

    Retourne un dict : entites, activites, agg_institutions, agg_ministeres,
    agg_top, agg_budgets, agg_trimestres, alertes_defaut (détail par entité
    flaggée), date_donnees, stats.
    """
    coupe_12m = (aujourdhui - timedelta(days=365)).isoformat()
    coupe_24m = (aujourdhui - timedelta(days=730)).isoformat()

    con = duckdb.connect()
    inf = _rc(dossier_csv, "1_informations_generales.csv")
    niv = _rc(dossier_csv, "6_niveaux_intervention.csv")
    dom = _rc(dossier_csv, "7_domaines_intervention.csv")
    act = _rc(dossier_csv, "8_objets_activites.csv")
    sec = _rc(dossier_csv, "9_secteurs_activites.csv")
    ame = _rc(dossier_csv, "10_actions_menees.csv")
    dec = _rc(dossier_csv, "12_decisions_concernees.csv")
    mia = _rc(dossier_csv, "13_ministeres_aai_api.csv")
    obs = _rc(dossier_csv, "14_observations.csv")
    exe = _rc(dossier_csv, "15_exercices.csv")

    # Vues de travail matérialisées (petites) pour éviter les relectures.
    con.execute(f"CREATE TEMP TABLE t_inf AS SELECT * FROM {inf}")
    con.execute(f"CREATE TEMP TABLE t_exe AS SELECT * FROM {exe}")
    con.execute(
        f"CREATE TEMP TABLE t_act AS "
        f"SELECT a.*, e.representants_id, e.date_debut, e.date_fin "
        f"FROM {act} a LEFT JOIN t_exe e USING (exercices_id)"
    )
    con.execute(
        f"CREATE TEMP TABLE t_lien AS SELECT DISTINCT activite_id, "
        f"action_representation_interet_id FROM {obs}"
    )

    # ---- fraîcheur réelle (jamais la date de modification du fichier)
    date_donnees = con.execute(
        """
        SELECT max(d) FROM (
            SELECT date_publication_activite AS d FROM t_act
            UNION ALL
            SELECT date_publication FROM t_exe
        ) WHERE d SIMILAR TO '\\d{4}-\\d{2}-\\d{2}'
        """
    ).fetchone()[0]

    # ---- entités ----------------------------------------------------------
    lignes_entites = con.execute(
        f"""
        WITH sect AS (
            SELECT representants_id,
                   string_agg(DISTINCT secteur_activite, ' | ' ORDER BY secteur_activite) s
            FROM {sec} WHERE coalesce(secteur_activite,'') <> '' GROUP BY 1
        ),
        niveaux AS (
            SELECT representants_id,
                   string_agg(DISTINCT niveau_intervention, ' | ' ORDER BY niveau_intervention) n
            FROM {niv} WHERE coalesce(niveau_intervention,'') <> '' GROUP BY 1
        ),
        flags AS (
            SELECT representants_id,
                   max(CASE WHEN declaration_incomplete = 'True' THEN 1 ELSE 0 END) AS defaut,
                   max(CASE WHEN declaration_incomplete = 'True'
                             AND coalesce(date_publication,'') <> '' THEN 1 ELSE 0 END) AS partiel
            FROM t_exe GROUP BY 1
        ),
        dernier_budget AS (
            SELECT *, row_number() OVER (
                       PARTITION BY representants_id ORDER BY date_fin DESC) AS rn
            FROM t_exe WHERE coalesce(montant_depense,'') <> ''
        ),
        nb AS (
            SELECT representants_id,
                   count(*) AS total,
                   count(*) FILTER (date_publication_activite >= '{coupe_12m}') AS n12
            FROM t_act WHERE representants_id IS NOT NULL GROUP BY 1
        )
        SELECT i.representants_id, i.identifiant_national, i.type_identifiant_national,
               i.denomination, i.nom_usage_HATVP, i.sigle_HATVP,
               i.label_categorie_organisation, i.ville, i.pays,
               i.dateCessation, i.date_premiere_publication, i.derniere_publication_activite,
               sect.s, niveaux.n,
               coalesce(nb.total, 0), coalesce(nb.n12, 0),
               b.date_debut, b.date_fin, b.montant_depense,
               b.montant_depense_inf, b.montant_depense_sup,
               b.nombre_salaries, b.chiffre_affaires, b.ca_inf, b.ca_sup,
               coalesce(f.defaut, 0), coalesce(f.partiel, 0)
        FROM t_inf i
        LEFT JOIN sect    ON sect.representants_id    = i.representants_id
        LEFT JOIN niveaux ON niveaux.representants_id = i.representants_id
        LEFT JOIN flags f ON f.representants_id       = i.representants_id
        LEFT JOIN (SELECT * FROM dernier_budget WHERE rn = 1) b
               ON b.representants_id = i.representants_id
        LEFT JOIN nb      ON nb.representants_id      = i.representants_id
        """
    ).fetchall()

    entites = []
    for r in lignes_entites:
        (rid, ident, type_ident, denom, nom_usage, sigle, categorie, ville, pays,
         cessation, prem_pub, dern_pub, secteurs, niveaux, nb_total, nb_12m,
         b_debut, b_fin, b_lib, b_inf, b_sup, salaries, ca_lib, ca_inf_v, ca_sup_v,
         defaut, partiel) = r
        cessation_iso = iso_de_fr(cessation)
        try:
            effectifs = float(salaries) if salaries not in (None, "") else None
        except ValueError:
            effectifs = None
        entites.append((
            rid, ident or None, type_ident or None, denom, nom_usage or None,
            sigle or None, categorie or None, ville or None, pays or None,
            0 if cessation_iso else 1, cessation_iso,
            iso_de_fr(prem_pub), iso_de_fr(dern_pub),
            secteurs, niveaux, nb_total, nb_12m,
            b_debut, b_fin, b_lib or None,
            parse_borne(b_inf, b_lib), parse_borne(b_sup, b_lib),
            effectifs, ca_lib or None,
            parse_borne(ca_inf_v, ca_lib), parse_borne(ca_sup_v, ca_lib),
            int(defaut), int(partiel), url_fiche_hatvp(ident),
        ))

    # ---- activités (détail 24 mois) ---------------------------------------
    activites = con.execute(
        f"""
        WITH doms AS (
            SELECT activite_id, string_agg(DISTINCT domaines_intervention_actions_menees,
                                           ' | ' ORDER BY domaines_intervention_actions_menees) d
            FROM {dom} WHERE coalesce(domaines_intervention_actions_menees,'') <> ''
            GROUP BY 1
        ),
        decs AS (
            SELECT l.activite_id, string_agg(DISTINCT d.decision_concernee,
                                             ' | ' ORDER BY d.decision_concernee) d
            FROM {dec} d JOIN t_lien l USING (action_representation_interet_id)
            WHERE coalesce(d.decision_concernee,'') <> '' GROUP BY 1
        ),
        insts AS (
            SELECT l.activite_id,
                   string_agg(DISTINCT trim(replace(m.responsable_public, chr(8217), '''')),
                              ' | ') AS i,
                   string_agg(DISTINCT nullif(trim(m.departement_ministeriel), ''),
                              ' | ') AS mn
            FROM {mia} m JOIN t_lien l USING (action_representation_interet_id)
            WHERE coalesce(m.responsable_public,'') <> ''
               OR coalesce(m.departement_ministeriel,'') <> ''
            GROUP BY 1
        ),
        acts AS (
            SELECT l.activite_id, string_agg(DISTINCT a.action_menee,
                                             ' | ' ORDER BY a.action_menee) a
            FROM {ame} a JOIN t_lien l USING (action_representation_interet_id)
            WHERE coalesce(a.action_menee,'') <> '' GROUP BY 1
        )
        SELECT t.activite_id, t.representants_id, t.exercices_id,
               t.date_debut, t.date_fin, t.date_publication_activite,
               t.identifiant_fiche,
               CASE WHEN length(t.objet_activite) > 500
                    THEN substr(t.objet_activite, 1, 497) || '…'
                    ELSE t.objet_activite END,
               doms.d, decs.d, insts.i, insts.mn, acts.a
        FROM t_act t
        LEFT JOIN doms  USING (activite_id)
        LEFT JOIN decs  USING (activite_id)
        LEFT JOIN insts USING (activite_id)
        LEFT JOIN acts  USING (activite_id)
        WHERE t.date_publication_activite >= '{coupe_24m}'
          AND t.representants_id IS NOT NULL
        """
    ).fetchall()

    # ---- agrégats ----------------------------------------------------------
    agg_institutions = [
        (cat, groupe_institution(cat), total, n12, nbe)
        for cat, total, n12, nbe in con.execute(
            f"""
            SELECT trim(replace(m.responsable_public, chr(8217), '''')) AS c,
                   count(DISTINCT l.activite_id),
                   count(DISTINCT l.activite_id)
                       FILTER (t.date_publication_activite >= '{coupe_12m}'),
                   count(DISTINCT t.representants_id)
            FROM {mia} m
            JOIN t_lien l USING (action_representation_interet_id)
            JOIN t_act t USING (activite_id)
            WHERE coalesce(trim(m.responsable_public), '') <> ''
            GROUP BY 1 ORDER BY 2 DESC
            """
        ).fetchall()
    ]

    # Recomposition des portefeuilles éclatés (table FERMÉE, cf. constantes) :
    # la correspondance entre dans le GROUP BY, et les compteurs restent des
    # count(DISTINCT …) — une activité visant deux fragments du MÊME
    # portefeuille n'est comptée qu'une fois (union, jamais somme).
    con.execute(
        "CREATE TEMP TABLE t_portefeuilles (fragment VARCHAR, portefeuille VARCHAR)")
    con.executemany(
        "INSERT INTO t_portefeuilles VALUES (?, ?)",
        sorted(FRAGMENTS_MINISTERIELS.items()),
    )

    # Sonnette de dérive : un fragment de la table qui a disparu de la donnée
    # (renommage HATVP après remaniement) doit se voir, pas passer inaperçu.
    libelles_observes = [
        r[0] for r in con.execute(
            f"""
            SELECT DISTINCT trim(m.departement_ministeriel)
            FROM {mia} m
            WHERE coalesce(trim(m.departement_ministeriel), '') <> ''
            """
        ).fetchall()
    ]
    fragments_absents = verifier_fragments(libelles_observes)
    if fragments_absents:
        log.warning(
            "recomposition des ministères : %d fragment(s) de la table fermée "
            "introuvable(s) dans la donnée HATVP (%s) — le vocabulaire a "
            "probablement changé, la table doit être relue à la main",
            len(fragments_absents), " ; ".join(fragments_absents),
        )

    agg_ministeres = con.execute(
        f"""
        SELECT coalesce(p.portefeuille, trim(m.departement_ministeriel)) AS c,
               count(DISTINCT l.activite_id),
               count(DISTINCT l.activite_id)
                   FILTER (t.date_publication_activite >= '{coupe_12m}'),
               count(DISTINCT t.representants_id)
        FROM {mia} m
        JOIN t_lien l USING (action_representation_interet_id)
        JOIN t_act t USING (activite_id)
        LEFT JOIN t_portefeuilles p
               ON p.fragment = trim(m.departement_ministeriel)
        WHERE coalesce(trim(m.departement_ministeriel), '') <> ''
        GROUP BY 1 ORDER BY 2 DESC
        """
    ).fetchall()

    agg_top = con.execute(
        f"""
        SELECT row_number() OVER (ORDER BY count(*) DESC, i.denomination),
               t.representants_id, i.denomination, i.label_categorie_organisation,
               count(*) AS n
        FROM t_act t JOIN t_inf i USING (representants_id)
        WHERE t.date_publication_activite >= '{coupe_12m}'
        GROUP BY t.representants_id, i.denomination, i.label_categorie_organisation
        ORDER BY n DESC, i.denomination LIMIT 50
        """
    ).fetchall()

    agg_budgets = [
        (lib, parse_borne(binf, lib), parse_borne(bsup, lib), n)
        for lib, binf, bsup, n in con.execute(
            """
            WITH dernier AS (
                SELECT e.*, row_number() OVER (
                           PARTITION BY representants_id ORDER BY date_fin DESC) rn
                FROM t_exe e WHERE coalesce(montant_depense,'') <> ''
            )
            SELECT d.montant_depense, d.montant_depense_inf, d.montant_depense_sup,
                   count(*)
            FROM dernier d JOIN t_inf i USING (representants_id)
            WHERE d.rn = 1 AND coalesce(i.dateCessation, '') = ''
            GROUP BY 1, 2, 3 ORDER BY try_cast(d.montant_depense_inf AS DOUBLE)
            """
        ).fetchall()
    ]

    agg_trimestres = con.execute(
        """
        SELECT substr(date_publication_activite, 1, 4) || '-T' ||
               CAST(ceil(CAST(substr(date_publication_activite, 6, 2) AS INT) / 3.0) AS INT),
               count(*), count(DISTINCT representants_id)
        FROM t_act
        WHERE date_publication_activite SIMILAR TO '\\d{4}-\\d{2}-\\d{2}'
        GROUP BY 1 ORDER BY 1
        """
    ).fetchall()

    # ---- détail des exercices flaggés (alertes défaut) ---------------------
    alertes_defaut = con.execute(
        """
        SELECT e.representants_id, i.denomination, i.identifiant_national,
               i.label_categorie_organisation, i.ville,
               e.date_debut, e.date_fin, e.date_publication,
               coalesce(e.nombre_activites, '0')
        FROM t_exe e JOIN t_inf i USING (representants_id)
        WHERE e.declaration_incomplete = 'True'
        ORDER BY i.denomination, e.date_debut
        """
    ).fetchall()

    # Hygiène à l'entrée : mojibake, contrôles C1 cp1252, espaces. Un seul
    # passage, ici, en aval de tous les appariements de libellés (voir la
    # docstring d'`assainir_lignes`) et en amont des sept `INSERT` d'`ecrire_db`
    # — donc aussi en amont de `_lignes_alertes`, qui compose ses titres
    # d'alerte à partir d'`alertes_defaut`.
    valeurs_assainies = 0
    entites, n = assainir_lignes(entites)
    valeurs_assainies += n
    activites, n = assainir_lignes(activites)
    valeurs_assainies += n
    agg_institutions, n = assainir_lignes(agg_institutions)
    valeurs_assainies += n
    agg_ministeres, n = assainir_lignes(agg_ministeres)
    valeurs_assainies += n
    agg_top, n = assainir_lignes(agg_top)
    valeurs_assainies += n
    agg_budgets, n = assainir_lignes(agg_budgets)
    valeurs_assainies += n
    agg_trimestres, n = assainir_lignes(agg_trimestres)
    valeurs_assainies += n
    alertes_defaut, n = assainir_lignes(alertes_defaut)
    valeurs_assainies += n

    stats = {
        "entites": len(entites),
        "entites_actives": sum(1 for e in entites if e[9] == 1),
        "activites_total": con.execute(
            "SELECT count(*) FROM t_act WHERE representants_id IS NOT NULL"
        ).fetchone()[0],
        "activites_detail": len(activites),
        "exercices": con.execute("SELECT count(*) FROM t_exe").fetchone()[0],
        "activites_orphelines": con.execute(
            "SELECT count(*) FROM t_act WHERE representants_id IS NULL"
        ).fetchone()[0],
        # fragments de la table fermée introuvables dans la donnée du jour
        "fragments_ministeres_absents": fragments_absents,
        "valeurs_assainies": valeurs_assainies,
    }
    con.close()

    return {
        "entites": entites,
        "activites": activites,
        "agg_institutions": agg_institutions,
        "agg_ministeres": agg_ministeres,
        "agg_top": agg_top,
        "agg_budgets": agg_budgets,
        "agg_trimestres": agg_trimestres,
        "alertes_defaut": alertes_defaut,
        "date_donnees": date_donnees,
        "stats": stats,
    }


# ---------------------------------------------------------------------------
# Écriture SQLite
# ---------------------------------------------------------------------------


def _lignes_alertes(donnees: dict, date_calcul: str) -> list[tuple]:
    """Lignes de la table partagée `alertes` (types lobbying uniquement)."""
    lignes = []
    par_entite: dict[str, list] = {}
    for row in donnees["alertes_defaut"]:
        par_entite.setdefault(row[0], []).append(row)

    nb_rien = nb_partiel = 0
    par_annee: dict[str, int] = {}
    for rid, exercices in par_entite.items():
        denom = exercices[0][1]
        ident = exercices[0][2]
        categorie = exercices[0][3] or "catégorie non renseignée"
        ville = exercices[0][4]
        morceaux = []
        for (_rid, _d, _i, _c, _v, debut, fin, date_pub, nb_act) in exercices:
            annee = (fin or debut or "?")[:4]
            par_annee[annee] = par_annee.get(annee, 0) + 1
            if date_pub and str(date_pub).strip():
                nb_partiel += 1
                morceaux.append(
                    f"exercice {debut} → {fin} : communication partielle "
                    f"(publication du {date_pub}, {nb_act} activité(s) publiée(s))"
                )
            else:
                nb_rien += 1
                morceaux.append(
                    f"exercice {debut} → {fin} : aucune information communiquée "
                    f"(aucune publication)"
                )
        detail = (f"{categorie}" + (f", {ville}" if ville else "") + ". "
                  + " ; ".join(morceaux) + ".")
        lignes.append((
            f"lobbying_defaut_declaration:{rid}",
            "lobbying_defaut_declaration",
            "haute",
            f"Défaut de déclaration lobbying : {denom}",
            detail,
            REGLE_DEFAUT,
            BASE_LEGALE,
            url_fiche_hatvp(ident) or URL_ZIP,
            date_calcul,
        ))

    n = len(par_entite)
    if n:
        repartition = " ; ".join(
            f"exercice {a} : {c}" for a, c in sorted(par_annee.items()))
        lignes.append((
            "lobbying_declaration_incomplete:agregat",
            "lobbying_declaration_incomplete",
            "moyenne",
            f"{n} représentants d'intérêts en défaut de déclaration "
            f"(liste officielle HATVP)",
            (f"{n} entités inscrites sur la liste officielle des représentants "
             f"d'intérêts n'ayant pas communiqué tout ou partie des informations "
             f"exigibles : {nb_rien} sans aucune publication pour l'exercice "
             f"concerné, {nb_partiel} avec communication partielle. "
             f"Répartition : {repartition}."),
            "Agrégat des flags natifs AGORA declaration_incomplete=True "
            "(un exercice flaggé = une entité comptée).",
            BASE_LEGALE,
            URL_ZIP,
            date_calcul,
        ))
    return lignes


def ecrire_db(conn, donnees: dict) -> dict:
    """Écrit toutes les tables (remplacement complet) + alertes + meta. Commit."""
    date_calcul = datetime.now(timezone.utc).isoformat(timespec="seconds")
    conn.executescript(_SCHEMA)

    lignes_alertes = _lignes_alertes(donnees, date_calcul)
    try:
        conn.execute("DELETE FROM lobby_entites")
        conn.executemany(
            "INSERT INTO lobby_entites VALUES (" + ",".join("?" * 29) + ")",
            donnees["entites"],
        )
        conn.execute("DELETE FROM lobby_activites")
        conn.executemany(
            "INSERT INTO lobby_activites VALUES (" + ",".join("?" * 13) + ")",
            donnees["activites"],
        )
        conn.execute("DELETE FROM lobby_agg_institutions")
        conn.executemany("INSERT INTO lobby_agg_institutions VALUES (?,?,?,?,?)",
                         donnees["agg_institutions"])
        conn.execute("DELETE FROM lobby_agg_ministeres")
        conn.executemany("INSERT INTO lobby_agg_ministeres VALUES (?,?,?,?)",
                         donnees["agg_ministeres"])
        conn.execute("DELETE FROM lobby_agg_top_entites")
        conn.executemany("INSERT INTO lobby_agg_top_entites VALUES (?,?,?,?,?)",
                         donnees["agg_top"])
        conn.execute("DELETE FROM lobby_agg_budgets")
        conn.executemany("INSERT INTO lobby_agg_budgets VALUES (?,?,?,?)",
                         donnees["agg_budgets"])
        conn.execute("DELETE FROM lobby_agg_trimestres")
        conn.executemany("INSERT INTO lobby_agg_trimestres VALUES (?,?,?)",
                         donnees["agg_trimestres"])
        # table partagée : on ne touche QUE nos types
        conn.execute(
            "DELETE FROM alertes WHERE type IN (?, ?)", TYPES_ALERTES)
        conn.executemany(
            "INSERT INTO alertes VALUES (?,?,?,?,?,?,?,?,?)", lignes_alertes)
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    stats = donnees["stats"]
    db.upsert_meta(
        conn,
        source_id=ID_SOURCE,
        nom=NOM_SOURCE,
        url=URL_ZIP,
        licence=LICENCE,
        frequence=FREQUENCE,
        date_donnees=donnees["date_donnees"],
        lignes=stats["entites"],
        notes=(
            f"{stats['entites']} entités ({stats['entites_actives']} actives), "
            f"{stats['activites_total']} activités (détail 24 mois : "
            f"{stats['activites_detail']}), {stats['exercices']} exercices. "
            f"Vues séparées CSV (le JSON de 137 Mo n'est pas utilisé). "
            f"Budgets en fourchettes natives. Flag défaut = liste officielle "
            f"HATVP (champ declaration_incomplete des vues = defautDeclaration "
            f"du JSON). NB : les volumes « 6 829 / 118 516 / 24 568 » cités en "
            f"Phase 0 étaient des comptes de lignes physiques (champs "
            f"multilignes), pas d'enregistrements."
        ),
    )
    nb_defaut = sum(1 for a in lignes_alertes
                    if a[1] == "lobbying_defaut_declaration")
    return {"alertes_defaut": nb_defaut,
            "alertes_agregat": len(lignes_alertes) - nb_defaut}


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def executer(chemin_db=None, max_age_heures: float | None = 6.0,
             aujourdhui: date | None = None) -> dict:
    """Pipeline complet : télécharge, extrait, construit, écrit. Retourne stats."""
    aujourdhui = aujourdhui or date.today()
    chemin_zip = telecharger(URL_ZIP, DOSSIER_RAW / "Vues_Separees_CSV.zip",
                             max_age_heures=max_age_heures)
    dossier_csv = extraire_zip(chemin_zip, DOSSIER_RAW)
    donnees = construire(dossier_csv, aujourdhui)
    stats = donnees["stats"]

    # Garde-fous : données réelles plausibles, sinon échec franc.
    if stats["entites"] < 1000:
        raise RuntimeError(
            f"volumétrie anormale : {stats['entites']} entités (≥ 1000 attendues)")
    if stats["activites_total"] < 10000:
        raise RuntimeError(
            f"volumétrie anormale : {stats['activites_total']} activités")
    if not donnees["date_donnees"]:
        raise RuntimeError("aucune date de publication exploitable (date_donnees)")
    if stats["activites_orphelines"]:
        log.warning("%d activités sans exercice rattaché (ignorées du détail)",
                    stats["activites_orphelines"])

    conn = db.init_db(chemin=chemin_db)
    try:
        stats_alertes = ecrire_db(conn, donnees)
    finally:
        conn.close()

    stats.update(stats_alertes)
    stats["date_donnees"] = donnees["date_donnees"]
    # Le compteur d'hygiène est journalisé INCONDITIONNELLEMENT, zéro compris :
    # un compteur muet au vert est indiscernable d'un compteur débranché
    # (règle posée par la PR #100).
    log.info(
        "lobbying OK : %d entités, %d activités (détail %d), %d alertes défaut "
        "+ %d agrégat, %d valeur(s) assainie(s) (mojibake, contrôles C1 cp1252, "
        "espaces), date_donnees=%s",
        stats["entites"], stats["activites_total"], stats["activites_detail"],
        stats["alertes_defaut"], stats["alertes_agregat"],
        stats["valeurs_assainies"], stats["date_donnees"],
    )
    return stats


def main() -> int:
    try:
        executer()
    except Exception:
        log.exception("échec du pipeline lobbying")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

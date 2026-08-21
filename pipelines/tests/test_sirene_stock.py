"""Tests du pipeline S18 — stock Sirene des unités légales (`ingest_sirene`).

À ne pas confondre avec `pipelines/sirene.py` (résolution unitaire d'un SIRET
par l'API recherche-entreprises), testé par `test_referentiels.py`.

Ce pipeline a trois façons de nuire, et les tests ci-dessous existent pour les
rendre impossibles :

1. **Faire entrer en base l'identité de personnes physiques.** Le stock décrit
   aussi les entrepreneurs individuels : nom de naissance, nom d'usage, quatre
   prénoms, prénom usuel, pseudonyme, sexe. La minimisation ne tient ici qu'à
   la liste des colonnes du SELECT — rien dans le schéma SQLite n'empêcherait
   d'y ajouter `nomUniteLegale` un jour de fatigue, et la base servie
   publierait alors l'identité de milliers de personnes sans qu'aucun test ne
   sonne. `test_minimisation_aucune_donnee_personnelle_en_base` balaye donc
   TOUTES les colonnes de la table, pas celles qu'on s'attend à y trouver.
   Corollaire : le droit d'opposition (`statutDiffusionUniteLegale`, art.
   A123-96 du code de commerce) doit écarter des unités entières.

2. **Écrire un référentiel faux sans rien casser.** Un fichier amont tronqué,
   un format changé, ou un lancement avant les autres pipelines produisent un
   référentiel vide ou décimé — qui s'insère parfaitement. Les garde-fous
   (`MIN_LIGNES_PARQUET`, `MIN_SIREN_CITES`, `TAUX_APPARIEMENT_MIN`) doivent
   échouer franchement ET laisser la table précédente intacte.

3. **Mentir sur la fraîcheur.** `date_donnees` doit porter la date du dernier
   traitement des unités RETENUES : ni le maximum du fichier entier (dont
   99,45 % des lignes ne concernent pas la base), ni celui des unités écartées
   pour non-diffusion, ni la date de publication du dataset.

S'y ajoutent les pièges de typage du parquet, dont `categorieJuridiqueUniteLegale`
qui y est un BIGINT alors que c'est un code à quatre chiffres.

Tout tourne hors ligne sur `fixtures/sirene/stock_unites_legales_mini.parquet`
(25 lignes, ~8 Ko), fabriqué par le script versionné à côté de lui, qui
documente ligne par ligne le piège éprouvé. Aucun test ne télécharge quoi que
ce soit ; la base servie n'est jamais ouverte (base jetable sous `tmp_path`,
et `FT_DB_PATH` détourné par précaution).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import duckdb
import pytest

from pipelines import db, ingest_sirene
from pipelines.ingest_sirene import (
    SOURCE_ID,
    SOURCE_FREQUENCE,
    SOURCE_LICENCE,
    executer,
    resoudre_ressource,
    siren_cites,
    transformer,
)

FIXTURE = Path(__file__).parent / "fixtures" / "sirene" / "stock_unites_legales_mini.parquet"

# ---------------------------------------------------------------------------
# Valeurs de la fixture, recomptées à la main (cf. fabriquer_fixture.py)
# ---------------------------------------------------------------------------

LIGNES_PARQUET = 25
# Les 14 SIREN que la base de test cite, répartis exprès sur toutes les
# branches de SQL_SIREN_CITES (marchés, cotitulaires JSON, subventions,
# lobbying, achats à venir, entités, quatre tables de collectivités, deux
# palmarès DECP).
SIREN_CITES_ATTENDUS = 14
# 11 d'entre eux sont dans le parquet ET diffusibles : ce sont les seules
# lignes que la table doit contenir.
APPARIES = 11
# 2 sont dans le parquet mais opposés à la diffusion ('P'), 1 est cité sans
# figurer au stock (SIREN d'un cotitulaire disparu du répertoire).
NON_DIFFUSIBLES = 2
PERSONNES_PHYSIQUES = 2
# Dernier traitement des seules unités retenues. Le fichier contient des dates
# plus récentes : 2026-08-19 (unité non diffusible) et 2026-08-20 (unité non
# citée). Les prendre serait la faute.
DATE_DONNEES = "2026-08-10"

SIREN_PERSONNE_MORALE = "110014016"
SIREN_PERSONNE_PHYSIQUE = "000325175"
SIREN_PERSONNE_PHYSIQUE_COMPLETE = "005410220"
SIREN_NON_DIFFUSIBLE_PP = "402398372"
SIREN_NON_DIFFUSIBLE_PM = "799478602"
SIREN_ESS_OUI = "775665912"
SIREN_ESS_NON = "552032534"
SIREN_SANS_ATTRIBUTS = "843701234"
SIREN_ESPACES = "213105554"
SIREN_CATEGORIE_COURTE = "388554702"
SIREN_NON_CITE = "652014051"
SIREN_NON_CITE_PP = "380129866"
SIREN_CITE_ABSENT_DU_STOCK = "918273645"

# Colonnes à caractère personnel du stock. Aucune ne doit être lue par le
# pipeline ; la liste sert à extraire de la fixture les chaînes interdites.
COLONNES_PERSONNELLES = [
    "nomUniteLegale",
    "nomUsageUniteLegale",
    "prenom1UniteLegale",
    "prenom2UniteLegale",
    "prenom3UniteLegale",
    "prenom4UniteLegale",
    "prenomUsuelUniteLegale",
    "pseudonymeUniteLegale",
]


# ---------------------------------------------------------------------------
# Base jetable : les tables sources minimales que lit SQL_SIREN_CITES
# ---------------------------------------------------------------------------

# Schéma volontairement réduit aux colonnes lues par la semi-jointure : ces
# tables appartiennent à d'autres pipelines, les recopier en entier ferait de
# ce fichier un test de leurs schémas plutôt que du nôtre. Les NOMS, eux, sont
# ceux de production : c'est ce qui casse si une source renomme sa colonne.
_DDL_SOURCES = """
CREATE TABLE decp_marches (
    uid             TEXT PRIMARY KEY,
    acheteur_siret  TEXT,
    titulaire_siret TEXT,
    titulaires_json TEXT
);
CREATE TABLE subventions_associations (siren TEXT);
CREATE TABLE lobby_entites (
    id                   TEXT PRIMARY KEY,
    identifiant_national TEXT,
    type_identifiant     TEXT
);
CREATE TABLE marches_a_venir (code TEXT PRIMARY KEY, acheteur_siren TEXT);
CREATE TABLE collectivites_communes_series (code_insee TEXT, siren TEXT);
CREATE TABLE collectivites_communes_top200 (code_insee TEXT, siren TEXT);
CREATE TABLE collectivites_conseils_departementaux (code_dep TEXT, siren TEXT);
CREATE TABLE collectivites_regions (code_region TEXT, siren TEXT);
CREATE TABLE decp_top_acheteurs (rang INTEGER PRIMARY KEY, siret TEXT);
CREATE TABLE decp_top_titulaires (rang INTEGER PRIMARY KEY, siret TEXT);
"""


def _peupler_sources(conn: sqlite3.Connection) -> None:
    """Sème les SIREN cités, un par branche de la semi-jointure.

    On y glisse aussi des identifiants malformés (numéro de TVA, SIRET
    tronqué, NULL) : les filtres GLOB du pipeline doivent les écarter, faute
    de quoi ils gonfleraient le dénominateur du taux d'appariement d'un bruit
    qui n'est pas une anomalie d'appariement.
    """
    conn.executescript(_DDL_SOURCES)
    conn.executemany(
        "INSERT INTO decp_marches (uid, acheteur_siret, titulaire_siret, "
        "titulaires_json) VALUES (?, ?, ?, ?)",
        [
            # Un marché ordinaire : acheteur non diffusible, titulaire personne
            # physique, et un cotitulaire lisible seulement dans le JSON.
            ("m1", f"{SIREN_NON_DIFFUSIBLE_PP}00025",
             f"{SIREN_PERSONNE_PHYSIQUE}00018",
             json.dumps([{"siret": f"{SIREN_CITE_ABSENT_DU_STOCK}00017",
                          "nom": "COTITULAIRE DISPARU DU REPERTOIRE"}])),
            # Identifiants malformés : TVA intracommunautaire, SIRET tronqué,
            # colonne JSON vide. Aucun ne doit produire de SIREN cité.
            ("m2", "FR12345678901", "00001", ""),
            ("m3", None, None, None),
        ],
    )
    conn.executemany(
        "INSERT INTO subventions_associations (siren) VALUES (?)",
        [(SIREN_PERSONNE_PHYSIQUE_COMPLETE,), (SIREN_ESS_OUI,),
         (SIREN_ESS_OUI,),  # doublon : la semi-jointure dédoublonne
         ("FR76552032534",), (None,)],
    )
    conn.executemany(
        "INSERT INTO lobby_entites (id, identifiant_national, type_identifiant) "
        "VALUES (?, ?, ?)",
        [
            ("l1", SIREN_NON_DIFFUSIBLE_PM, "SIREN"),
            # Piège : un identifiant RNA de neuf chiffres qui « ressemble » à
            # un SIREN. Le filtre porte sur type_identifiant ; s'il sautait,
            # cette unité non citée entrerait au référentiel.
            ("l2", SIREN_NON_CITE, "RNA"),
        ],
    )
    conn.execute(
        "INSERT INTO marches_a_venir (code, acheteur_siren) VALUES (?, ?)",
        ("mav1", SIREN_SANS_ATTRIBUTS),
    )
    conn.execute(
        "INSERT INTO entites (id, type, nom, siren) VALUES (?, ?, ?, ?)",
        ("inst-interieur", "ministere", "Ministère de l'Intérieur",
         SIREN_PERSONNE_MORALE),
    )
    conn.execute(
        "INSERT INTO collectivites_communes_top200 (code_insee, siren) "
        "VALUES (?, ?)", ("31555", SIREN_ESPACES),
    )
    conn.execute(
        "INSERT INTO collectivites_communes_series (code_insee, siren) "
        "VALUES (?, ?)", ("31555", "200054781"),
    )
    conn.execute(
        "INSERT INTO collectivites_conseils_departementaux (code_dep, siren) "
        "VALUES (?, ?)", ("25", "225000019"),
    )
    conn.execute(
        "INSERT INTO collectivites_regions (code_region, siren) VALUES (?, ?)",
        ("84", "234500023"),
    )
    conn.execute(
        "INSERT INTO decp_top_acheteurs (rang, siret) VALUES (?, ?)",
        (1, f"{SIREN_CATEGORIE_COURTE}00023"),
    )
    conn.execute(
        "INSERT INTO decp_top_titulaires (rang, siret) VALUES (?, ?)",
        (1, f"{SIREN_ESS_NON}00015"),
    )
    conn.commit()


@pytest.fixture
def chemin_base(tmp_path, monkeypatch):
    """Base jetable, peuplée des tables sources, base servie hors d'atteinte.

    `FT_DB_PATH` est détourné en plus du paramètre explicite : si un jour un
    chemin de code oubliait de propager `chemin_db`, il tomberait sur la base
    jetable et non sur `data/france.db`.
    """
    chemin = tmp_path / "s18.db"
    monkeypatch.setenv("FT_DB_PATH", str(chemin))
    conn = db.init_db(chemin=chemin)
    try:
        _peupler_sources(conn)
    finally:
        conn.close()
    return chemin


def _assouplir_gardefous(monkeypatch, **remplacements) -> None:
    """Cale les seuils sur la taille de la fixture.

    Les vraies valeurs (20 M de lignes, 50 000 SIREN cités, 90 %
    d'appariement) décrivent le fichier de production ; les éprouver telles
    quelles demanderait une fixture de plusieurs centaines de Mo. On les
    remplace donc par leurs homologues à l'échelle de 25 lignes, et les tests
    de garde-fous, eux, reprennent le seuil qui doit déclencher.
    """
    seuils = {
        "MIN_LIGNES_PARQUET": 20,     # la fixture en a 25
        "MIN_SIREN_CITES": 10,        # la base de test en cite 14
        # 11 appariés sur 14 cités : le taux nominal de la fixture est de
        # 78,6 %, deux unités étant écartées pour non-diffusion et une étant
        # absente du stock. Le seuil réel de 90 % n'a de sens que sur un stock
        # complet.
        "TAUX_APPARIEMENT_MIN": 0.70,
    }
    seuils.update(remplacements)
    for nom, valeur in seuils.items():
        monkeypatch.setattr(ingest_sirene, nom, valeur)


@pytest.fixture
def base_ingeree(chemin_base, monkeypatch):
    """Base jetable après une ingestion nominale hors ligne. Rend (chemin, stats)."""
    _assouplir_gardefous(monkeypatch)
    stats = executer(chemin_db=chemin_base, chemin_parquet=FIXTURE)
    return chemin_base, stats


def _lire(chemin: Path, requete: str, parametres: tuple = ()) -> list[sqlite3.Row]:
    conn = db.connexion(chemin)
    try:
        return conn.execute(requete, parametres).fetchall()
    finally:
        conn.close()


def _contenu_integral(chemin: Path) -> list[tuple]:
    """Photographie de la table, pour prouver qu'un échec ne l'a pas touchée."""
    return [tuple(ligne) for ligne in _lire(
        chemin, "SELECT * FROM sirene_unites_legales ORDER BY siren")]


# ---------------------------------------------------------------------------
# 0. La fixture elle-même : elle ne prouve rien si son schéma dérive
# ---------------------------------------------------------------------------


def test_la_fixture_reproduit_le_schema_reel_du_stock():
    """Le parquet de fixture porte les 35 colonnes réelles, avec leurs types.

    Sans ce test, une fixture « arrangée » (catégorie juridique en texte,
    dates en chaînes) ferait passer tous les autres pour de mauvaises raisons :
    c'est justement le typage du parquet amont qui piège le pipeline.
    """
    duck = duckdb.connect()
    try:
        schema = duck.execute(
            "SELECT * FROM read_parquet(?) LIMIT 0", [str(FIXTURE)]
        ).description
    finally:
        duck.close()
    colonnes = [nom for nom, *_ in schema]
    assert len(colonnes) == 35
    assert colonnes[:6] == [
        "siren", "statutDiffusionUniteLegale", "unitePurgeeUniteLegale",
        "dateCreationUniteLegale", "sigleUniteLegale", "sexeUniteLegale",
    ]
    assert set(COLONNES_PERSONNELLES) <= set(colonnes)

    duck = duckdb.connect()
    try:
        types = {ligne[0]: ligne[1] for ligne in duck.execute(
            "DESCRIBE SELECT * FROM read_parquet(?)", [str(FIXTURE)]).fetchall()}
        nombre = duck.execute(
            "SELECT count(*) FROM read_parquet(?)", [str(FIXTURE)]).fetchone()[0]
    finally:
        duck.close()
    assert nombre == LIGNES_PARQUET
    # Les types qui piègent, un par un.
    assert types["categorieJuridiqueUniteLegale"] == "BIGINT"
    assert types["anneeEffectifsUniteLegale"] == "BIGINT"
    assert types["dateDernierTraitementUniteLegale"] == "TIMESTAMP"
    assert types["dateCreationUniteLegale"] == "DATE"
    assert types["siren"] == "VARCHAR"
    assert types["statutDiffusionUniteLegale"] == "VARCHAR"
    assert types["economieSocialeSolidaireUniteLegale"] == "VARCHAR"
    assert types["societeMissionUniteLegale"] == "VARCHAR"
    assert types["etatAdministratifUniteLegale"] == "VARCHAR"


# ---------------------------------------------------------------------------
# 1. Minimisation des données personnelles — le test qui compte
# ---------------------------------------------------------------------------


def _identites_de_la_fixture() -> tuple[set[str], set[str]]:
    """Noms, prénoms et pseudonymes de la fixture, plus les sexes.

    Les jetons sont relus DU PARQUET plutôt que recopiés ici : si demain la
    fixture gagne une personne physique, le balayage la couvre sans qu'on
    pense à mettre la liste à jour — et une fixture vidée de ses identités
    ferait échouer le contrôle de non-vacuité plus bas.
    """
    duck = duckdb.connect()
    try:
        lignes = duck.execute(
            f"SELECT {', '.join(COLONNES_PERSONNELLES)} FROM read_parquet(?)",
            [str(FIXTURE)],
        ).fetchall()
        sexes = duck.execute(
            "SELECT DISTINCT sexeUniteLegale FROM read_parquet(?) "
            "WHERE sexeUniteLegale IS NOT NULL", [str(FIXTURE)],
        ).fetchall()
    finally:
        duck.close()
    jetons = {
        valeur.strip().casefold()
        for ligne in lignes for valeur in ligne
        if valeur and valeur.strip()
    }
    return jetons, {ligne[0] for ligne in sexes}


def test_minimisation_aucune_donnee_personnelle_en_base(base_ingeree):
    """Aucune colonne de la table ne contient d'identité de personne physique.

    Le balayage porte sur TOUTES les colonnes de `sirene_unites_legales`, pas
    sur celles qu'on s'attend à y trouver : c'est la seule formulation qui
    échoue si quelqu'un ajoute un jour `nomUniteLegale` au SELECT
    d'extraction, ou ressuscite une colonne `nom` dans le DDL. La règle est
    tenue par la requête, pas par le schéma — un test qui n'inspecterait que
    les colonnes connues ne verrait jamais la fuite.

    Le sexe est traité à part, par égalité : chercher « M » en sous-chaîne
    ferait sonner « COMMUNE DE FIXTURELLES ».
    """
    chemin, _ = base_ingeree
    jetons, sexes = _identites_de_la_fixture()
    # Non-vacuité : la fixture porte bien des identités, et les personnes
    # physiques concernées sont bien entrées au référentiel (sans quoi le
    # balayage passerait pour de mauvaises raisons).
    assert len(jetons) >= 12
    assert sexes == {"M", "F"}
    presents = {ligne["siren"] for ligne in _lire(
        chemin, "SELECT siren FROM sirene_unites_legales")}
    assert {SIREN_PERSONNE_PHYSIQUE, SIREN_PERSONNE_PHYSIQUE_COMPLETE} <= presents

    lignes = _lire(chemin, "SELECT * FROM sirene_unites_legales")
    assert lignes
    for ligne in lignes:
        for colonne in ligne.keys():
            valeur = ligne[colonne]
            if valeur is None:
                continue
            texte = str(valeur).casefold()
            for jeton in jetons:
                assert jeton not in texte, (
                    f"identité « {jeton} » retrouvée dans "
                    f"sirene_unites_legales.{colonne} (siren {ligne['siren']}) : "
                    "la minimisation du SELECT d'extraction a sauté"
                )
            assert str(valeur) not in sexes, (
                f"sexe retrouvé dans sirene_unites_legales.{colonne}"
            )

    # La ligne de traçabilité résume des comptes, jamais des identités.
    for meta in _lire(chemin, "SELECT * FROM meta_sources"):
        for colonne in meta.keys():
            texte = str(meta[colonne] or "").casefold()
            assert not any(jeton in texte for jeton in jetons)


def test_personne_physique_entre_avec_ses_attributs_et_sans_identite(base_ingeree):
    """Une personne physique est qualifiée, jamais identifiée.

    C'est le compromis assumé du pipeline : catégorie juridique, activité et
    état administratif entrent (ils qualifient un attributaire de marché),
    l'identité non. `denomination` reste NULL parce que l'INSEE ne renseigne
    la dénomination que pour les personnes morales — la remplir depuis le nom
    serait exactement la fuite qu'on interdit.
    """
    chemin, stats = base_ingeree
    ligne = _lire(chemin, "SELECT * FROM sirene_unites_legales WHERE siren = ?",
                  (SIREN_PERSONNE_PHYSIQUE,))[0]
    assert ligne["est_personne_physique"] == 1
    assert ligne["denomination"] is None
    assert ligne["sigle"] is None
    # Les attributs, eux, sont bien là : sans eux la ligne ne servirait à rien.
    assert ligne["categorie_juridique"] == "1000"
    assert ligne["activite_principale"] == "32.12Z"
    assert ligne["nomenclature_activite"] == "NAFRev2"
    assert ligne["etat_administratif"] == "A"
    assert ligne["categorie_entreprise"] == "PME"
    assert ligne["date_creation"] == "2000-09-26"

    # La personne morale ordinaire, elle, porte sa dénomination et le drapeau à 0.
    morale = _lire(chemin, "SELECT * FROM sirene_unites_legales WHERE siren = ?",
                   (SIREN_PERSONNE_MORALE,))[0]
    assert morale["est_personne_physique"] == 0
    assert morale["denomination"] == "MINISTERE DE L INTERIEUR"

    assert stats["personnes_physiques"] == PERSONNES_PHYSIQUES


# ---------------------------------------------------------------------------
# 2. Droit d'opposition : les unités non diffusibles
# ---------------------------------------------------------------------------


def test_unites_non_diffusibles_absentes_et_comptees(base_ingeree):
    """`statutDiffusionUniteLegale <> 'O'` fait disparaître l'unité entière.

    Le stock réel n'utilise pas que 'N' : sur 3 M de lignes mesurées, les
    valeurs observées sont 'O' (diffusible) et 'P' (diffusion partielle). La
    fixture emploie 'P', qui est le cas réel et le plus perfide : un test
    écrit contre 'N' laisserait passer tout le reste.

    L'unité écartée l'est quelle que soit sa nature — la fixture en a une
    physique et une morale.
    """
    chemin, stats = base_ingeree
    presents = {ligne["siren"] for ligne in _lire(
        chemin, "SELECT siren FROM sirene_unites_legales")}
    assert SIREN_NON_DIFFUSIBLE_PP not in presents
    assert SIREN_NON_DIFFUSIBLE_PM not in presents
    assert stats["ecartes_non_diffusibles"] == NON_DIFFUSIBLES
    # Le compte ne porte que sur les SIREN cités : les unités non diffusibles
    # que la base ne cite pas ne sont pas « écartées », elles n'ont jamais été
    # candidates (la fixture en contient, cf. lignes de remplissage).
    assert stats["siren_cites"] == SIREN_CITES_ATTENDUS
    assert stats["apparies"] == APPARIES


# ---------------------------------------------------------------------------
# 3. Typages : catégorie juridique, ESS, société à mission, champs vides
# ---------------------------------------------------------------------------


def test_categorie_juridique_rendue_en_texte_de_quatre_caracteres(base_ingeree):
    """Le BIGINT du parquet ne doit pas produire un code amputé.

    `categorieJuridiqueUniteLegale` vaut 1000, 5710, 9220… : lu tel quel,
    c'est un entier, et une jointure avec la nomenclature INSEE (qui est
    textuelle) échouerait silencieusement. Le pipeline le rend en texte cadré
    sur quatre positions ; la fixture contient une valeur qui, en entier,
    s'écrit sur une seule.
    """
    chemin, _ = base_ingeree
    for ligne in _lire(chemin, "SELECT siren, categorie_juridique, "
                               "typeof(categorie_juridique) AS type "
                               "FROM sirene_unites_legales"):
        assert ligne["type"] == "text", ligne["siren"]
        assert len(ligne["categorie_juridique"]) == 4, ligne["siren"]
    par_siren = {ligne["siren"]: ligne["categorie_juridique"] for ligne in _lire(
        chemin, "SELECT siren, categorie_juridique FROM sirene_unites_legales")}
    assert par_siren[SIREN_PERSONNE_PHYSIQUE] == "1000"
    assert par_siren[SIREN_PERSONNE_MORALE] == "7113"
    assert par_siren[SIREN_ESS_OUI] == "9220"
    # Le cas défensif : 0 en BIGINT devient '0000', pas '0'.
    assert par_siren[SIREN_CATEGORIE_COURTE] == "0000"


def test_economie_sociale_solidaire_a_trois_etats(base_ingeree):
    """'O' → 1, 'N' → 0, non renseigné → NULL — et surtout pas 0.

    Confondre « déclare ne pas relever de l'ESS » et « ne dit rien » ferait
    d'un dénombrement d'entreprises de l'ESS un chiffre faux dans les deux
    sens. Même règle pour `societe_mission`.
    """
    chemin, _ = base_ingeree
    lignes = {ligne["siren"]: ligne for ligne in _lire(
        chemin, "SELECT siren, economie_sociale_solidaire, societe_mission "
                "FROM sirene_unites_legales")}
    assert lignes[SIREN_ESS_OUI]["economie_sociale_solidaire"] == 1
    assert lignes[SIREN_ESS_OUI]["societe_mission"] == 0
    assert lignes[SIREN_ESS_NON]["economie_sociale_solidaire"] == 0
    assert lignes[SIREN_ESS_NON]["societe_mission"] == 1
    # Champ vide dans le parquet : NULL, pas 0.
    assert lignes[SIREN_SANS_ATTRIBUTS]["economie_sociale_solidaire"] is None
    # Champ absent (NULL amont) : NULL également.
    assert lignes[SIREN_PERSONNE_MORALE]["economie_sociale_solidaire"] is None
    assert lignes[SIREN_PERSONNE_MORALE]["societe_mission"] is None


def test_champs_vides_et_espaces_parasites_normalises(base_ingeree):
    """Chaîne vide → NULL, espaces rognés : « '' » et NULL ne se comptent pas pareil.

    Le stock mélange les deux conventions selon les colonnes et les millésimes.
    Sans `nullif(trim(coalesce(...)))`, un `WHERE activite_principale IS NULL`
    donnerait un nombre d'unités sans activité déclarée systématiquement faux.
    """
    chemin, _ = base_ingeree
    vide = _lire(chemin, "SELECT * FROM sirene_unites_legales WHERE siren = ?",
                 (SIREN_SANS_ATTRIBUTS,))[0]
    for colonne in ("sigle", "activite_principale", "nomenclature_activite",
                    "tranche_effectifs", "categorie_entreprise",
                    "etat_administratif", "date_creation", "annee_effectifs"):
        assert vide[colonne] is None, colonne

    espaces = _lire(chemin, "SELECT * FROM sirene_unites_legales WHERE siren = ?",
                    (SIREN_ESPACES,))[0]
    assert espaces["denomination"] == "COMMUNE DE FIXTURELLES"
    # Un sigle fait uniquement d'espaces n'est pas un sigle.
    assert espaces["sigle"] is None


# ---------------------------------------------------------------------------
# 4. Semi-jointure : le référentiel est restreint aux SIREN cités
# ---------------------------------------------------------------------------


def test_siren_non_cites_restent_hors_du_referentiel(base_ingeree):
    """Le référentiel ne contient que ce que la base cite — c'est tout son intérêt.

    Ingérer le stock entier coûterait 5,8 Gio pour 0,55 % d'usage. Si la
    semi-jointure sautait, la table gonflerait sans que rien n'échoue : d'où
    un test sur des unités précises du parquet qui ne doivent PAS y être, dont
    une personne physique (fuite de données personnelles en prime).
    """
    chemin, stats = base_ingeree
    presents = {ligne["siren"] for ligne in _lire(
        chemin, "SELECT siren FROM sirene_unites_legales")}
    assert SIREN_NON_CITE not in presents
    assert SIREN_NON_CITE_PP not in presents
    # Les lignes de remplissage de la fixture (900000001…) ne sont citées par
    # aucune table : aucune ne doit avoir franchi la porte.
    assert not any(siren.startswith("9000000") for siren in presents)
    # Un SIREN cité mais absent du stock ne peut évidemment pas entrer : il
    # pèse en revanche sur le taux d'appariement.
    assert SIREN_CITE_ABSENT_DU_STOCK not in presents
    assert len(presents) == APPARIES
    # Le taux mesure l'APPARIEMENT, donc les unités RETROUVÉES dans le stock,
    # qu'elles soient ensuite retenues ou écartées pour non-diffusion. Le
    # rapporter aux seules retenues confondrait deux phénomènes distincts :
    # un format amont qui change (ce que le garde-fou doit voir) et des
    # personnes qui exercent leur droit d'opposition (normal, et hors de
    # notre main). Seul SIREN_CITE_ABSENT_DU_STOCK fait donc baisser ce taux.
    assert stats["trouves"] == APPARIES + NON_DIFFUSIBLES
    assert stats["taux"] == pytest.approx(
        (APPARIES + NON_DIFFUSIBLES) / SIREN_CITES_ATTENDUS
    )


def test_siren_cites_dedoublonne_et_ecarte_les_identifiants_malformes(chemin_base):
    """La liste des SIREN cités est propre avant même de toucher au parquet.

    Les DECP charrient 7 406 lignes à SIRET malformé (TVA intracommunautaire,
    `00001`…). Les laisser passer ne casserait rien mais ferait chuter le taux
    d'appariement, donc déclencherait le garde-fou pour une fausse raison.
    """
    conn = db.connexion(chemin_base)
    try:
        sirens = siren_cites(conn)
    finally:
        conn.close()
    assert len(sirens) == len(set(sirens)) == SIREN_CITES_ATTENDUS
    assert all(len(siren) == 9 and siren.isdigit() for siren in sirens)
    # Le cotitulaire n'existe que dans le JSON du marché.
    assert SIREN_CITE_ABSENT_DU_STOCK in sirens
    # Le faux « SIREN » de type RNA ne doit pas être cité.
    assert SIREN_NON_CITE not in sirens
    assert "FR12345678901" not in sirens


# ---------------------------------------------------------------------------
# 5. Millésime
# ---------------------------------------------------------------------------


def test_date_donnees_est_le_dernier_traitement_des_unites_retenues(base_ingeree):
    """Ni le max du fichier, ni celui des unités écartées, ni la date du dataset.

    La fixture est construite pour que les trois réponses fausses soient
    distinctes de la bonne : l'unité non citée a été traitée le 2026-08-20,
    l'unité non diffusible le 2026-08-19, et la plus récente des unités
    réellement retenues le 2026-08-10. C'est cette dernière qui fait la
    fraîcheur affichée dans l'UI ; les deux autres la surestimeraient.
    """
    chemin, stats = base_ingeree
    assert stats["date_donnees"] == DATE_DONNEES
    meta = _lire(chemin, "SELECT * FROM meta_sources WHERE source_id = ?",
                 (SOURCE_ID,))[0]
    assert meta["date_donnees"] == DATE_DONNEES

    # Contre-preuve : les dates plus récentes existent bien dans le fichier.
    duck = duckdb.connect()
    try:
        max_global = duck.execute(
            "SELECT CAST(max(dateDernierTraitementUniteLegale) AS DATE) "
            "FROM read_parquet(?)", [str(FIXTURE)]).fetchone()[0]
    finally:
        duck.close()
    assert max_global.isoformat() == "2026-08-20"
    assert stats["date_donnees"] < max_global.isoformat()


def test_transformer_est_pur_et_rend_des_comptes_exacts(monkeypatch):
    """`transformer()` ne touche ni le réseau ni SQLite : parquet + liste → lignes.

    C'est ce découpage qui rend le pipeline testable hors ligne ; on le fixe
    ici, et on en profite pour figer les compteurs qui alimentent `notes`.
    """
    _assouplir_gardefous(monkeypatch)
    sirens = [
        SIREN_PERSONNE_MORALE, SIREN_PERSONNE_PHYSIQUE,
        SIREN_NON_DIFFUSIBLE_PM, SIREN_CITE_ABSENT_DU_STOCK,
        # Doublon volontaire : le dénominateur du taux compte les SIREN
        # distincts, pas les mentions.
        SIREN_PERSONNE_MORALE,
    ]
    lignes, stats = transformer(FIXTURE, sirens)
    assert stats["lignes_parquet"] == LIGNES_PARQUET
    assert stats["siren_cites"] == 4
    assert stats["apparies"] == 2
    assert len(lignes) == 2
    assert stats["ecartes_non_diffusibles"] == 1
    assert stats["personnes_physiques"] == 1
    # 3 des 4 SIREN cités sont retrouvés dans le stock (2 retenus + 1 écarté
    # pour non-diffusion) ; seul SIREN_CITE_ABSENT_DU_STOCK manque à l'appel.
    assert stats["trouves"] == 3
    assert stats["taux"] == pytest.approx(0.75)
    # Les lignes sortent triées par SIREN : l'ordre d'insertion est stable
    # d'une exécution à l'autre, ce qui rend l'idempotence vérifiable.
    assert [ligne[0] for ligne in lignes] == sorted(ligne[0] for ligne in lignes)
    # La tuple d'insertion a exactement les 14 colonnes du DDL.
    assert all(len(ligne) == 14 for ligne in lignes)


# ---------------------------------------------------------------------------
# 6. Idempotence et traçabilité
# ---------------------------------------------------------------------------


def test_rejouer_ne_duplique_rien(chemin_base, monkeypatch):
    """Deux exécutions d'affilée donnent exactement la même table.

    Le chargement est un DELETE + INSERT en une transaction : rejouer doit
    remplacer, jamais empiler. Un `INSERT OR IGNORE` sans DELETE laisserait au
    contraire des unités radiées survivre indéfiniment au référentiel.
    """
    _assouplir_gardefous(monkeypatch)
    premier = executer(chemin_db=chemin_base, chemin_parquet=FIXTURE)
    contenu_premier = _contenu_integral(chemin_base)
    second = executer(chemin_db=chemin_base, chemin_parquet=FIXTURE)
    contenu_second = _contenu_integral(chemin_base)

    assert premier == second
    assert contenu_premier == contenu_second
    assert len(contenu_second) == APPARIES
    metas = _lire(chemin_base, "SELECT * FROM meta_sources WHERE source_id = ?",
                  (SOURCE_ID,))
    assert len(metas) == 1


def test_meta_sources_recoit_la_ligne_s18(base_ingeree):
    """La traçabilité doit dire vrai, y compris sur le nombre de lignes.

    `lignes` est recompté sur la table plutôt que repris des stats : c'est la
    seule façon de détecter un jour où le compte annoncé et le contenu réel
    divergeraient (chargement partiel, contrainte silencieuse).
    """
    chemin, stats = base_ingeree
    meta = _lire(chemin, "SELECT * FROM meta_sources WHERE source_id = ?",
                 (SOURCE_ID,))[0]
    reel = _lire(chemin, "SELECT count(*) AS n FROM sirene_unites_legales")[0]["n"]
    assert meta["lignes"] == reel == APPARIES == stats["apparies"]
    assert meta["licence"] == SOURCE_LICENCE == "Licence Ouverte 2.0"
    assert meta["frequence"] == SOURCE_FREQUENCE == "mensuelle"
    assert meta["url"].startswith("https://www.data.gouv.fr/datasets/")
    assert meta["date_ingestion"]
    # Les notes portent la mesure du jour, dont l'aveu de minimisation.
    assert "non diffusibles écartées" in meta["notes"]
    assert str(SIREN_CITES_ATTENDUS) in meta["notes"]


# ---------------------------------------------------------------------------
# 7. Garde-fous : échouer franchement, et ne rien abîmer
# ---------------------------------------------------------------------------


def test_gardefou_parquet_trop_petit_laisse_la_base_intacte(base_ingeree, monkeypatch):
    """Un fichier amont tronqué doit échouer, pas s'ingérer.

    Le stock compte 29,9 M d'unités ; si la ressource était un jour remplacée
    par un extrait, l'ingestion « réussirait » et le référentiel perdrait
    l'essentiel de son contenu sans un mot. On vérifie surtout la seconde
    moitié du contrat : la table précédente survit intacte à l'échec.
    """
    chemin, _ = base_ingeree
    avant = _contenu_integral(chemin)
    assert avant  # sinon le test ne prouverait rien

    _assouplir_gardefous(monkeypatch, MIN_LIGNES_PARQUET=1_000)
    with pytest.raises(RuntimeError, match="parquet Sirene suspect"):
        executer(chemin_db=chemin, chemin_parquet=FIXTURE)
    assert _contenu_integral(chemin) == avant


def test_gardefou_trop_peu_de_siren_cites(chemin_base, monkeypatch):
    """Lancé avant les autres pipelines, S18 refuse d'écrire un référentiel vide.

    Ce pipeline est dérivé : il ne connaît que les SIREN que les autres tables
    citent. Sur une base fraîchement construite il en trouverait une poignée
    et produirait un référentiel presque vide — qui s'ingérerait sans erreur
    et écraserait le précédent. Le seuil réel (50 000) est ici conservé : la
    base de test n'en cite que 14, ce qui est exactement la situation décrite.
    """
    # Une ingestion nominale d'abord, pour avoir quelque chose à abîmer.
    _assouplir_gardefous(monkeypatch)
    executer(chemin_db=chemin_base, chemin_parquet=FIXTURE)
    avant = _contenu_integral(chemin_base)

    monkeypatch.setattr(ingest_sirene, "MIN_SIREN_CITES",
                        50_000)  # valeur de production
    with pytest.raises(RuntimeError, match="SIREN cités"):
        executer(chemin_db=chemin_base, chemin_parquet=FIXTURE)
    assert _contenu_integral(chemin_base) == avant


def test_gardefou_taux_appariement_insuffisant(base_ingeree, monkeypatch):
    """Un appariement effondré signale un format changé, pas une dérive.

    Mesuré à 99,80 % en production. S'il s'effondre, c'est que les SIREN ne
    se retrouvent plus dans le fichier — colonne renommée, format modifié —
    et la bonne réponse est de ne pas toucher au référentiel existant.
    """
    chemin, stats = base_ingeree
    avant = _contenu_integral(chemin)
    assert stats["taux"] < 0.99  # la fixture est bâtie pour cela

    _assouplir_gardefous(monkeypatch, TAUX_APPARIEMENT_MIN=0.99)
    with pytest.raises(RuntimeError, match="appariement"):
        executer(chemin_db=chemin, chemin_parquet=FIXTURE)
    assert _contenu_integral(chemin) == avant


def test_base_sans_tables_sources_echoue_sans_rien_ecrire(tmp_path, monkeypatch):
    """Sur une base neuve (tables des autres pipelines absentes), échec franc.

    Le module promet dans sa docstring de tolérer « une à une » les tables
    absentes pour se rabattre sur le message de MIN_SIREN_CITES. Ce n'est pas
    ce qui arrive : `SQL_SIREN_CITES` est une seule requête UNION, et la
    première table manquante lève une `sqlite3.OperationalError` convertie en
    `RuntimeError`. Le test se contente donc du contrat qui compte — échec
    franc, aucune table écrite — et vaudra quel que soit celui des deux
    messages qui sort.
    """
    chemin = tmp_path / "neuve.db"
    monkeypatch.setenv("FT_DB_PATH", str(chemin))
    db.init_db(chemin=chemin).close()
    _assouplir_gardefous(monkeypatch)
    with pytest.raises(RuntimeError, match="SIREN cités"):
        executer(chemin_db=chemin, chemin_parquet=FIXTURE)
    tables = {ligne["name"] for ligne in _lire(
        chemin, "SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert "sirene_unites_legales" not in tables
    assert not _lire(chemin, "SELECT * FROM meta_sources WHERE source_id = ?",
                     (SOURCE_ID,))


# ---------------------------------------------------------------------------
# 8. Résolution de la ressource amont (fausse session : aucun accès réseau)
# ---------------------------------------------------------------------------


class _FausseReponse:
    def __init__(self, corps, statut=200):
        self._corps = corps
        self.status_code = statut

    def json(self):
        return self._corps

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class _FausseSession:
    def __init__(self, corps, statut=200):
        self._corps = corps
        self._statut = statut
        self.appels = []

    def get(self, url, params=None, timeout=None):
        self.appels.append((url, params, timeout))
        return _FausseReponse(self._corps, self._statut)


# Extrait de la réponse de l'API dataset, réduit aux ressources qui piègent.
# Le jeu réel en compte 24, dont trois autres stocks : le titre est le seul
# discriminant disponible, et deux d'entre eux contiennent « StockUniteLegale ».
DATASET_SIRENE = {
    "id": "5b7ffc618b4c4169d30727e0",
    "resources": [
        {"title": "StockEtablissement - 01 août 2026 (format parquet)",
         "url": "https://static.data.gouv.fr/.../StockEtablissement.parquet",
         "format": "parquet", "filesize": 3_500_000_000},
        # Piège n° 1 : le fichier « Historique » contient aussi le marqueur
        # StockUniteLegale ET le format parquet. Il décrit les périodes
        # passées, pas l'état courant.
        {"title": "StockUniteLegaleHistorique - 01 août 2026 (format parquet)",
         "url": "https://static.data.gouv.fr/.../StockUniteLegaleHistorique.parquet",
         "format": "parquet", "filesize": 1_200_000_000},
        # Piège n° 2 : la variante CSV zippée du même stock (971 Mo, 159 s de
        # parcours en Python contre moins d'une seconde en parquet).
        {"title": "StockUniteLegale_utf8.zip", "format": "zip",
         "url": "https://static.data.gouv.fr/.../StockUniteLegale_utf8.zip",
         "filesize": 970_595_120},
        {"title": "StockUniteLegale - 01 août 2026 (format parquet)",
         "url": "https://static.data.gouv.fr/resources/xxx/20260801-000000/"
                "StockUniteLegale.parquet",
         "format": "parquet", "filesize": 739_142_016,
         "last_modified": "2026-08-01T05:12:44.123000+00:00"},
        # Une seconde ressource conforme, placée après : la première trouvée
        # doit l'emporter, sans quoi le choix dépendrait de l'ordre du jeu.
        {"title": "StockUniteLegale - 01 juillet 2026 (format parquet)",
         "url": "https://static.data.gouv.fr/.../20260701/StockUniteLegale.parquet",
         "format": "parquet", "filesize": 738_000_000},
    ],
}


def test_resoudre_ressource_choisit_le_parquet_du_stock_courant():
    """Le titre est le seul discriminant : trois marqueurs, dont un d'exclusion.

    Les URL `static.data.gouv.fr` sont horodatées et changent à chaque
    millésime ; coder l'URL en dur ferait un 404 mensuel. La ressource est
    donc re-résolue à chaque exécution, et il faut prouver qu'elle ne se
    trompe pas de fichier au sein d'un jeu qui en compte 24.
    """
    session = _FausseSession(DATASET_SIRENE)
    ressource = resoudre_ressource(session=session)
    assert ressource["titre"] == "StockUniteLegale - 01 août 2026 (format parquet)"
    assert ressource["url"].endswith("StockUniteLegale.parquet")
    assert "Historique" not in ressource["titre"]
    assert not ressource["url"].endswith(".zip")
    # `last_modified` est tronquée à la date : la partie horaire n'a pas de
    # sens pour un millésime mensuel.
    assert ressource["derniere_modification"] == "2026-08-01"
    assert ressource["octets"] == "739142016"
    # Un seul appel, sur l'API dataset, avec un timeout.
    url, _, timeout = session.appels[0]
    assert url == ingest_sirene.URL_DATASET_API
    assert timeout == 60
    assert len(session.appels) == 1


def test_resoudre_ressource_tolere_une_ressource_sans_horodatage():
    """Une ressource sans `last_modified` ni `filesize` ne doit pas planter.

    Ces deux champs sont facultatifs côté data.gouv ; ils ne servent qu'au
    journal. Une exception ici ferait échouer une ingestion parfaitement
    valable.
    """
    session = _FausseSession({"resources": [
        {"title": "StockUniteLegale (format parquet)",
         "url": "https://static.data.gouv.fr/x.parquet"},
    ]})
    ressource = resoudre_ressource(session=session)
    assert ressource["derniere_modification"] == ""
    assert ressource["octets"] == ""


def test_resoudre_ressource_absente_leve_une_erreur_explicite():
    """Aucun repli silencieux : si le stock parquet disparaît, on s'arrête.

    Le jeu contient d'autres fichiers volumineux qui « marcheraient » à moitié.
    Se rabattre dessus produirait un référentiel plausible et faux ; le message
    d'erreur liste donc les titres réellement présents, pour qu'on voie tout
    de suite ce que l'amont a renommé.
    """
    dataset = {"resources": [
        r for r in DATASET_SIRENE["resources"]
        if r["title"].startswith(("StockEtablissement", "StockUniteLegaleHistorique"))
    ]}
    session = _FausseSession(dataset)
    with pytest.raises(RuntimeError, match="absente du dataset Sirene"):
        resoudre_ressource(session=session)
    # Le cas « jeu vide » ne doit pas non plus passer pour un succès.
    with pytest.raises(RuntimeError):
        resoudre_ressource(session=_FausseSession({"resources": []}))


def test_resoudre_ressource_propage_l_erreur_http():
    """Une API en erreur ne doit pas se traduire par un choix par défaut."""
    session = _FausseSession({"resources": []}, statut=503)
    with pytest.raises(RuntimeError):
        resoudre_ressource(session=session)

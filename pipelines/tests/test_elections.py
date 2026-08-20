"""Tests du pipeline P14 (participation électorale, source S26).

Fixture `fixtures/elections/general_results_mini.parquet` : 12 Ko, 181 lignes
RÉELLES extraites par DuckDB du parquet « Résultats généraux » du 07/07/2026
(mêmes 25 colonnes), choisies pour couvrir exactement les pièges documentés
dans `pipelines/ingest_elections.py` :

- **97101 Les Abymes** : `code_departement` vaut `ZA` en 2022 et `971` en 2026
  pour la MÊME commune — le piège n° 1, à l'état pur ;
- **97701 Saint-Barthélemy et 97801 Saint-Martin** : deux territoires distincts
  que la source range sous un unique `code_departement = 'ZX'` ; seule la
  dérivation depuis `code_commune` les sépare ;
- **41205 Saint-Cyr-du-Gault** (`nuls = -84`, `votants = 0`) et **60400 Le
  Mesnil-sur-Bulles** (212 votants pour 209 inscrits) : les deux agrégats
  réellement incohérents des municipales 2026, piège n° 2 ;
- **97701** encore : présente à la présidentielle 2022, ABSENTE des municipales
  2026 (collectivité de l'article 74, pas de conseil municipal) — piège n° 3 ;
- **ZZ001 Abidjan** : « Français établis hors de France », qui n'est pas un
  département et ne doit apparaître dans aucune des deux tables ;
- **2A004 Ajaccio** et **75056 Paris** : agrégation de 12 bureaux de vote,
  code corse alphanumérique, communes du périmètre du site ;
- **01004 Ambérieu-en-Bugey** : commune ordinaire HORS périmètre du site
  (prouve la restriction de la table ville) ;
- **2020_muni_t1** : scrutin hors liste (prouve le filtre sur `SCRUTINS`).

Les valeurs attendues ci-dessous ont été relevées indépendamment dans la
fixture au moment de sa génération (agrégats DuckDB). La transformation est
testée en PUR (parquet seulement, aucun réseau) ; le chargement l'est sur une
base SQLite jetable (`FT_DB_PATH` n'est pas nécessaire : `db.init_db(chemin=…)`).
"""

from pathlib import Path

import pytest

from pipelines import db, ingest_elections

FIXTURE = Path(__file__).parent / "fixtures" / "elections" / "general_results_mini.parquet"

# Scrutins présents dans la fixture (la liste de production en compte 7, dont
# les quatre scrutins 2024 que la fixture n'embarque pas).
SCRUTINS_FIXTURE = ("2022_pres_t1", "2026_muni_t1", "2026_muni_t2")

# Périmètre communal simulé : 6 communes « connues du site », dont 98613 Uvea
# qui n'existe dans AUCUN scrutin (piège 3) et 01004 volontairement absente.
PERIMETRE = ["2A004", "75056", "97101", "97701", "97801", "98613"]

# Libellés départementaux : ref_departements (métropole + DROM) complétés par
# les collectivités hors référentiel du pipeline.
LIBELLES = {
    "01": "Ain",
    "2A": "Corse-du-Sud",
    "41": "Loir-et-Cher",
    "60": "Oise",
    "75": "Paris",
    "971": "Guadeloupe",
    **ingest_elections.LIBELLES_COLLECTIVITES,
}


@pytest.fixture(scope="module")
def resultat():
    """Transformation complète de la fixture (pure : ni réseau ni SQLite)."""
    return ingest_elections.transformer(FIXTURE, PERIMETRE, LIBELLES, SCRUTINS_FIXTURE)


def _verifier(conn, stats):
    """`verifier()` avec les minimums de volume ramenés à l'échelle de la
    fixture (181 lignes de bureau) — tous les autres contrôles sont ceux de
    la production, à l'identique."""
    return ingest_elections.verifier(
        conn, stats, min_lignes_dep=10, min_lignes_ville=5, min_departements=2
    )


def _index(lignes, *positions):
    """Indexe une liste de tuples par les colonnes données."""
    return {tuple(l[p] for p in positions): l for l in lignes}


# ---------------------------------------------------------------------------
# Constantes et garde-fous éditoriaux
# ---------------------------------------------------------------------------


def test_import_et_constantes():
    assert ingest_elections.SOURCE_ID == "S26"
    assert ingest_elections.FREQUENCE == "par scrutin"
    assert len(ingest_elections.SCRUTINS) == 7
    # Chaque scrutin ingéré doit avoir une date de convocation déclarée, sans
    # quoi meta_sources.date_donnees ne pourrait pas être renseignée.
    assert set(ingest_elections.SCRUTINS) <= set(ingest_elections.DATES_SCRUTINS)


def test_aucune_nuance_aucun_candidat_dans_le_schema():
    """Garde-fou éditorial : le schéma ne peut pas accueillir de nuance
    politique ni de nom de personne, et le pipeline n'adresse jamais la
    ressource `candidats_results`."""
    schema = ingest_elections._SCHEMA.lower()
    for interdit in ("nuance", "candidat", "nom_", "prenom", "voix", "sieges"):
        assert interdit not in schema, f"colonne interdite dans le schéma : {interdit}"
    source = Path(ingest_elections.__file__).read_text(encoding="utf-8")
    # Le fichier PARLE de candidats_results (pour dire qu'il ne l'utilise pas)
    # mais ne doit contenir aucune URL vers cette ressource.
    assert "candidats_results.parquet" not in ingest_elections.URL_PARQUET
    assert source.count("candidats_results") <= 2


# ---------------------------------------------------------------------------
# Filtres : scrutins retenus, périmètre communal, Français hors de France
# ---------------------------------------------------------------------------


def test_seuls_les_scrutins_retenus_sont_agreges(resultat):
    lignes_dep, lignes_ville, stats = resultat
    assert stats["scrutins_trouves"] == sorted(SCRUTINS_FIXTURE)
    assert stats["scrutins_manquants"] == []
    # 2020_muni_t1 est dans la fixture mais hors liste : jamais agrégé.
    assert "2020_muni_t1" not in {l[0] for l in lignes_dep}
    assert "2020_muni_t1" not in {l[0] for l in lignes_ville}


def test_francais_hors_de_france_jamais_un_departement(resultat):
    lignes_dep, lignes_ville, _ = resultat
    # ZZ001 (Abidjan) pèse 12 775 inscrits dans la fixture : ni dans la table
    # départementale (ce n'est pas un département), ni dans la table ville
    # (hors périmètre du site).
    assert "ZZ" not in {l[1] for l in lignes_dep}
    assert "ZZ001" not in {l[1] for l in lignes_ville}


def test_table_ville_restreinte_au_perimetre_du_site(resultat):
    _, lignes_ville, _ = resultat
    codes = {l[1] for l in lignes_ville}
    assert codes <= set(PERIMETRE)
    # Ambérieu-en-Bugey est dans la fixture, hors périmètre : jamais ingérée.
    assert "01004" not in codes
    # 41205 et 60400 non plus, alors qu'elles portent les incohérences.
    assert {"41205", "60400"}.isdisjoint(codes)


# ---------------------------------------------------------------------------
# PIÈGE 1 — département dérivé de code_commune, jamais de code_departement
# ---------------------------------------------------------------------------


def test_piege1_outre_mer_stable_malgre_le_changement_de_codification(resultat):
    lignes_dep, lignes_ville, _ = resultat
    villes = _index(lignes_ville, 0, 1)
    # Les Abymes : 'ZA' à la source en 2022, '971' en 2026 → même département.
    assert villes[("2022_pres_t1", "97101")][3] == "971"
    assert villes[("2026_muni_t1", "97101")][3] == "971"
    deps = _index(lignes_dep, 0, 1)
    assert ("2022_pres_t1", "971") in deps
    assert ("2026_muni_t1", "971") in deps
    # Et le libellé vient du référentiel du site, pas du parquet.
    assert deps[("2022_pres_t1", "971")][2] == "Guadeloupe"


def test_piege1_ZX_se_scinde_en_deux_collectivites(resultat):
    lignes_dep, _, _ = resultat
    deps = _index(lignes_dep, 0, 1)
    # La source range Saint-Barthélemy ET Saint-Martin sous code_departement
    # = 'ZX' : la dérivation depuis code_commune est la SEULE façon de les
    # distinguer, et le référentiel leur rend leur nom.
    saint_barth = deps[("2022_pres_t1", "977")]
    saint_martin = deps[("2022_pres_t1", "978")]
    assert saint_barth[2] == "Saint-Barthélemy"
    assert saint_martin[2] == "Saint-Martin"
    assert saint_barth[3] == 5267        # inscrits relevés dans la fixture
    assert saint_martin[3] == 12659


def test_piege1_code_corse_conserve_sur_deux_caracteres(resultat):
    lignes_dep, _, _ = resultat
    deps = _index(lignes_dep, 0, 1)
    ajaccio = deps[("2026_muni_t1", "2A")]
    assert ajaccio[2] == "Corse-du-Sud"
    # 12 bureaux d'Ajaccio sommés (valeurs relevées dans la fixture).
    assert ajaccio[3:] == (10506, 7192, 129, 102, 6961)


# ---------------------------------------------------------------------------
# PIÈGE 2 — cohérence arithmétique : signalée, jamais corrigée
# ---------------------------------------------------------------------------


def test_piege2_agregats_incoherents_comptes_et_conserves(resultat):
    lignes_dep, _, stats = resultat
    deps = _index(lignes_dep, 0, 1)
    # Saint-Cyr-du-Gault : nuls négatifs et 0 votant — donnée réelle du
    # ministère, conservée TELLE QUELLE (ni corrigée, ni supprimée, ni mise à 0).
    loir_et_cher = deps[("2026_muni_t1", "41")]
    assert loir_et_cher[3:] == (157, 0, 5, -84, 79)
    # Le Mesnil-sur-Bulles : plus de votants que d'inscrits.
    oise = deps[("2026_muni_t1", "60")]
    assert oise[3] == 209 and oise[4] == 212
    # Les deux sont comptées comme incohérentes, au grain natif comme à
    # l'agrégat départemental ; aucune n'est communale ici (hors périmètre).
    assert stats["incoherentes_bureau"] == 2
    assert stats["incoherentes_dep"] == 2
    assert stats["incoherentes_ville"] == 0
    # L'identité votants = blancs + nuls + exprimés tient partout, y compris
    # sur la ligne à nuls négatifs (0 = 5 - 84 + 79).
    assert stats["ecarts_votants"] == 0


def test_piege2_verifier_refuse_une_proportion_anormale(tmp_path, resultat):
    lignes_dep, lignes_ville, stats = resultat
    conn = _base_de_travail(tmp_path, lignes_dep, lignes_ville)
    try:
        # Tel quel : 2 incohérences sur 26 lignes = 7,7 % > 1 % toléré.
        with pytest.raises(RuntimeError, match="agrégats incohérents"):
            _verifier(conn, stats)
        # Avec une proportion réaliste (2 sur 2 264 en production), ça passe.
        _verifier(conn, {**stats, "incoherentes_dep": 0})
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# PIÈGE 3 — communes connues absentes : diagnostiquées, pas comblées
# ---------------------------------------------------------------------------


def test_piege3_communes_connues_absentes_du_dernier_premier_tour(resultat):
    _, lignes_ville, stats = resultat
    assert stats["dernier_scrutin"] == "2026_muni_t2"
    # L'absence se mesure sur le dernier PREMIER tour, où chaque commune vote :
    # au second tour, une commune manque parce que son conseil est élu, pas
    # parce que la donnée manque.
    assert stats["dernier_premier_tour"] == "2026_muni_t1"
    # Saint-Barthélemy et Saint-Martin (collectivités de l'article 74 : conseil
    # territorial, pas de conseil municipal) et Uvea (Wallis-et-Futuna n'a pas
    # de communes) manquent. Aucune n'est comblée par un zéro.
    assert set(stats["communes_absentes"]) == {"97701", "97801", "98613"}
    # Les Abymes, elle, vote bien aux municipales : jamais signalée absente.
    assert "97101" not in stats["communes_absentes"]
    # 97701 et 97801 existent bien aux scrutins nationaux — l'absence des
    # municipales est structurelle, pas un trou de données.
    presentes_2022 = {l[1] for l in lignes_ville if l[0] == "2022_pres_t1"}
    assert {"97701", "97801", "97101"} <= presentes_2022
    # Uvea (98613) n'est présente à AUCUN scrutin : pas de niveau communal.
    assert stats["communes_jamais_vues"] == ["98613"]
    assert "98613" not in {l[1] for l in lignes_ville}


# ---------------------------------------------------------------------------
# Chargement SQLite : idempotence, contrôles, périmètre lu en base
# ---------------------------------------------------------------------------


def _base_de_travail(tmp_path, lignes_dep, lignes_ville):
    """Base jetable : socle + ref_departements des seuls départements de la
    fixture, puis chargement des deux tables (sans commit)."""
    conn = db.init_db(chemin=tmp_path / "elections.db")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS ref_departements (
            code TEXT PRIMARY KEY, nom TEXT NOT NULL,
            code_region TEXT NOT NULL, nom_region TEXT NOT NULL, population INTEGER
        );
        """
    )
    conn.executemany(
        "INSERT OR REPLACE INTO ref_departements VALUES (?,?,'00','région',NULL)",
        [(c, n) for c, n in LIBELLES.items() if c not in ingest_elections.LIBELLES_COLLECTIVITES],
    )
    ingest_elections.charger(conn, lignes_dep, lignes_ville)
    conn.commit()
    return conn


def test_charger_est_idempotent(tmp_path, resultat):
    lignes_dep, lignes_ville, _ = resultat
    conn = _base_de_travail(tmp_path, lignes_dep, lignes_ville)
    try:
        avant = (
            conn.execute("SELECT count(*) FROM elections_participation_departement").fetchone()[0],
            conn.execute("SELECT count(*) FROM elections_participation_ville").fetchone()[0],
        )
        # Second passage sur la même base : delete+insert, aucun doublon.
        ingest_elections.charger(conn, lignes_dep, lignes_ville)
        conn.commit()
        apres = (
            conn.execute("SELECT count(*) FROM elections_participation_departement").fetchone()[0],
            conn.execute("SELECT count(*) FROM elections_participation_ville").fetchone()[0],
        )
        assert avant == apres == (len(lignes_dep), len(lignes_ville))
    finally:
        conn.close()


def test_verifier_signale_un_departement_du_referentiel_sans_resultat(tmp_path, resultat):
    """Le contrôle qui aurait attrapé une jointure sur `code_departement` :
    un département du référentiel sans aucune ligne fait échouer l'ingestion."""
    lignes_dep, lignes_ville, stats = resultat
    conn = _base_de_travail(tmp_path, lignes_dep, lignes_ville)
    try:
        conn.execute(
            "INSERT INTO ref_departements VALUES ('972','Martinique','00','région',NULL)"
        )
        conn.commit()
        with pytest.raises(RuntimeError, match="sans résultat.*972"):
            _verifier(conn, {**stats, "incoherentes_dep": 0})
    finally:
        conn.close()


def test_verifier_signale_un_libelle_departemental_manquant(tmp_path, resultat):
    """Un code sans libellé de référentiel retombe sur son code — dégradation
    propre côté données, mais l'ingestion refuse de le publier tel quel."""
    lignes_dep, lignes_ville, stats = resultat
    sans_nom = [(l[0], l[1], l[1], *l[3:]) if l[1] == "978" else l for l in lignes_dep]
    conn = _base_de_travail(tmp_path, sans_nom, lignes_ville)
    try:
        with pytest.raises(RuntimeError, match="libellé départemental manquant"):
            _verifier(conn, {**stats, "incoherentes_dep": 0})
    finally:
        conn.close()


def test_perimetre_communes_lit_les_deux_tables_du_site(tmp_path):
    """Le périmètre est l'UNION de ref_villes et collectivites_communes, sans
    doublon — jamais une liste en dur dans le pipeline."""
    conn = db.init_db(chemin=tmp_path / "perimetre.db")
    try:
        conn.executescript(
            """
            CREATE TABLE ref_villes (code_insee TEXT PRIMARY KEY, nom TEXT);
            CREATE TABLE collectivites_communes (code_insee TEXT PRIMARY KEY, nom TEXT);
            INSERT INTO ref_villes VALUES ('75056','Paris'), ('2A004','Ajaccio');
            INSERT INTO collectivites_communes VALUES ('75056','Paris'), ('69123','Lyon');
            """
        )
        conn.commit()
        assert ingest_elections.perimetre_communes(conn) == ["2A004", "69123", "75056"]
    finally:
        conn.close()


def test_date_donnees_est_celle_du_dernier_tour_ingere():
    """`date_donnees` = date de la DONNÉE (dernier tour), jamais celle de
    modification du dataset amont (07/07/2026)."""
    assert (
        ingest_elections.date_donnees({"scrutins_trouves": list(SCRUTINS_FIXTURE)})
        == "2026-03-22"
    )
    # Scrutin sans date déclarée : on retombe sur le dernier tour daté connu.
    assert (
        ingest_elections.date_donnees(
            {"scrutins_trouves": ["2022_pres_t1", "2027_pres_t1"]}
        )
        == "2022-04-10"
    )
    with pytest.raises(RuntimeError, match="aucun scrutin ingéré"):
        ingest_elections.date_donnees({"scrutins_trouves": ["1999_euro_t1"]})


def test_aucun_taux_stocke(resultat):
    """Seuls des effectifs bruts sont stockés : un taux en base se lirait
    comme un zéro quand la donnée manque (règle n° 1 du projet)."""
    lignes_dep, lignes_ville, _ = resultat
    for ligne in lignes_dep:
        assert len(ligne) == 8 and all(isinstance(v, int) for v in ligne[3:])
    for ligne in lignes_ville:
        assert len(ligne) == 9 and all(isinstance(v, int) for v in ligne[4:])

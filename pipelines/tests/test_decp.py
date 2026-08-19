"""Tests du pipeline P3 (DECP marchés publics, source S1).

Fixture `fixtures/decp_mini.parquet` : ~29 Ko, 61 lignes RÉELLES extraites
par DuckDB du parquet consolidé du 19/08/2026 (mêmes 64 colonnes), choisies
pour couvrir : 40 marchés ordinaires récents, un accord-cadre « suspect » à
12,311 Md€ (dép. 58), un marché « aberrant » (montant brut ~100 Md€
rationalisé à 115 k€, dép. 971), un marché à 3 co-titulaires (dép. 89), un
marché aux lignes titulaires dupliquées (dép. 972), deux marchés à montant
NULL (dép. 29), plus des lignes à ÉCARTER : donneesActuelles = false,
dateNotification NULL, notifications 2023 (hors fenêtre détail). Les valeurs attendues ci-dessous ont été relevées
indépendamment dans la fixture au moment de sa génération.

La transformation est testée en pur (DuckDB seulement, date de référence
figée au 19/08/2026) ; l'intégration réelle (téléchargement 243 Mo + SQLite)
est marquée `reseau`.
"""

import json
from datetime import date
from pathlib import Path

import pytest

from pipelines import db, ingest_decp

DATE_REF = date(2026, 8, 19)
FIXTURE = Path(__file__).parent / "fixtures" / "decp_mini.parquet"

UID_GEANT = "255801185000182024AC34_40100000"          # 12 311 111 111 €, 'suspect'
UID_ABERRANT = "7943807330002020212021-036_45111100"   # brut 99 999 999 999,99 €
UID_MULTI = "015450638001172026p9f730000000_71222000"  # 3 co-titulaires
UID_DOUBLONS = "200041788000642025_017_PI0_79311000"   # lignes titulaires dupliquées
UID_SANS_MONTANT = "2529011450004200067_45231400"      # montant NULL (réel)


@pytest.fixture(scope="module")
def resultat():
    """Transformation complète de la fixture (pure, sans réseau ni SQLite)."""
    duck, stats = ingest_decp.transformer(FIXTURE, DATE_REF)
    yield duck, stats
    duck.close()


def _table(duck, nom, cles):
    lignes = duck.execute(f"SELECT * FROM {nom}").fetchall()
    noms = [d[0] for d in duck.description]
    return {tuple(r[noms.index(c)] for c in cles) if len(cles) > 1
            else r[noms.index(cles[0])]: dict(zip(noms, r)) for r in lignes}


def test_import_et_constantes():
    assert ingest_decp.SOURCE_ID == "S1"
    assert ingest_decp.PLAFOND_ECRETAGE_EUR == 100_000_000.0
    assert ingest_decp.MOIS_DETAIL == 24


def test_detail_filtre_et_dedoublonne(resultat):
    duck, stats = resultat
    marches = _table(duck, "t_marches", ["uid"])
    # 41 uid distincts dans la fenêtre 24 mois (donneesActuelles seulement) :
    # les lignes false/NULL/2023 de la fixture sont écartées.
    assert stats["nb_marches"] == len(marches) == 41
    assert stats["date_max"] == "2026-07-28"
    for m in marches.values():
        assert "2024-08-20" <= m["date_notification"] <= "2026-08-19"


def test_montants_conserves_et_drapeau_suspect(resultat):
    duck, _ = resultat
    marches = _table(duck, "t_marches", ["uid"])
    geant = marches[UID_GEANT]
    # 'suspect' : montant NON corrigé par la source, conservé tel quel dans
    # le détail (pas d'écrêtage hors agrégats), mais drapeau levé.
    assert geant["montant"] == geant["montant_retenu"] == 12_311_111_111.0
    assert geant["montant_anomalie"] == "suspect"
    assert geant["montant_suspect"] == 1
    # Le caractère accord-cadre (montant = maximum) se lit dans techniques.
    assert "Accord-cadre" in (geant["techniques"] or "")

    aberrant = marches[UID_ABERRANT]
    # 'aberrant' : la source fournit le montant rationalisé, qui devient
    # le montant retenu ; le brut est conservé pour trace.
    assert aberrant["montant"] == pytest.approx(99_999_999_999.99)
    assert aberrant["montant_rationalise"] == aberrant["montant_retenu"] == 115_000.0
    assert aberrant["montant_suspect"] == 1

    sans_montant = marches[UID_SANS_MONTANT]
    # Montant absent à la source : NULL conservé (rien d'inventé), non suspect.
    assert sans_montant["montant"] is None
    assert sans_montant["montant_retenu"] is None
    assert sans_montant["montant_suspect"] == 0


def test_titulaires_agreges(resultat):
    duck, _ = resultat
    marches = _table(duck, "t_marches", ["uid"])
    multi = marches[UID_MULTI]
    assert multi["nb_titulaires"] == 3
    # Titulaire principal déterministe = plus petit SIRET.
    assert multi["titulaire_siret"] == "38181085200057"
    assert multi["titulaire_nom"] == "5-CINQ ARCHITECTURE"
    tit = json.loads(multi["titulaires_json"])
    assert [t["siret"] for t in tit] == sorted(t["siret"] for t in tit)
    assert len(tit) == 3 and all(t["nom"] for t in tit)
    # Lignes source dupliquées (8 lignes : 3 titulaires ×2 + 2 simples)
    # → pas de double compte, 5 titulaires distincts.
    assert marches[UID_DOUBLONS]["nb_titulaires"] == 5


def test_agregat_departemental_ecrete(resultat):
    duck, _ = resultat
    dep = _table(duck, "t_agg_departement", ["departement_code"])
    # Département du géant à 12,3 Md€ : l'agrégat N'EST PAS écrasé —
    # 100 M€ (plafond) + 13 833,50 € (l'autre marché du 58 de la fixture).
    assert dep["58"]["nb_marches"] == 2
    assert dep["58"]["montant_total"] == pytest.approx(100_013_833.50)
    assert dep["58"]["nb_marches_ecretes"] == 1
    # Département ordinaire : somme exacte des montants retenus relevés
    # indépendamment dans la fixture (117 788,30 + 656 680,00).
    assert dep["07"]["nb_marches"] == 2
    assert dep["07"]["montant_total"] == pytest.approx(774_468.30)
    # L'aberrant compte pour son montant rationalisé, pas pour 100 Md€.
    assert dep["971"]["montant_total"] == pytest.approx(115_000.0)
    # Marchés à montant NULL : comptés, somme NULL (pas de zéro inventé).
    assert dep["29"]["nb_marches"] == 2
    assert dep["29"]["montant_total"] is None
    assert dep["29"]["nb_marches_ecretes"] == 0
    # Aucun agrégat ne peut dépasser nb × plafond ; pas de département NULL.
    for code, ligne in dep.items():
        assert code is not None
        if ligne["montant_total"] is not None:
            assert ligne["montant_total"] <= ligne["nb_marches"] * 100_000_000.0
    assert len(dep) == 31
    assert sum(l["nb_marches"] for l in dep.values()) == 36  # 37 uid 12 mois - 1 sans dép.


def test_tops_ecretes_et_repartis(resultat):
    duck, _ = resultat
    top_a = duck.execute(
        "SELECT rang, siret, montant_total FROM t_top_acheteurs ORDER BY rang"
    ).fetchall()
    # L'acheteur du géant plafonne à exactement 100 M€ au lieu de 12,3 Md€.
    assert top_a[0][1] == "25580118500018"
    assert top_a[0][2] == pytest.approx(100_000_000.0)
    assert [r[0] for r in top_a] == list(range(1, len(top_a) + 1))

    top_t = duck.execute(
        "SELECT siret, nb_marches, montant_total FROM t_top_titulaires ORDER BY rang"
    ).fetchall()
    assert top_t[0][2] == pytest.approx(100_000_000.0)  # titulaire du géant
    # Marché multi-titulaires : montant divisé entre les 3 co-titulaires.
    part = {r[0]: r[2] for r in top_t}["38181085200057"]
    assert part == pytest.approx(94_100.0 / 3)


def test_repartition_normalisee(resultat):
    duck, _ = resultat
    rep = duck.execute(
        "SELECT dimension, valeur, nb_marches FROM t_repartition"
    ).fetchall()
    dims = {r[0] for r in rep}
    assert dims == {"procedure", "nature"}
    for dim in dims:
        assert sum(r[2] for r in rep if r[0] == dim) == 37  # tous les uid 12 mois


def test_normalisation_des_libelles_heterogenes():
    # Variantes réelles observées dans S1 : casse et apostrophes divergent.
    import duckdb

    cle = ingest_decp._SQL_CLE_LIBELLE.format(col="x")
    n = duckdb.sql(
        f"""SELECT count(DISTINCT {cle}) FROM (VALUES
            ('Marché'), ('MARCHE'),
            ('Appel d''offres ouvert'), ('Appel d offres ouvert')) t(x)"""
    ).fetchone()[0]
    assert n == 2


def test_serie_mensuelle(resultat):
    duck, _ = resultat
    mois = duck.execute("SELECT mois, nb_marches FROM t_agg_mois ORDER BY mois").fetchall()
    assert all(len(m[0]) == 7 and m[0][4] == "-" for m in mois)
    assert mois[0][0] >= "2023-09"          # 36 mois civils max
    assert mois[-1][0] == "2026-07"         # dernier mois présent dans la fixture
    assert sum(m[1] for m in mois) >= 41    # série ⊇ fenêtre détail


def test_derniers_marches(resultat):
    duck, _ = resultat
    derniers = duck.execute(
        "SELECT rang, date_notification FROM t_derniers_marches ORDER BY rang"
    ).fetchall()
    assert 0 < len(derniers) <= 200
    assert derniers[0][1] == "2026-07-28"
    dates = [d[1] for d in derniers]
    assert dates == sorted(dates, reverse=True)


def test_charger_est_idempotent(tmp_path, resultat):
    duck, _ = resultat
    conn = db.init_db(chemin=tmp_path / "decp_test.db")
    try:
        for _ in range(2):  # double passage : mêmes comptes, pas de doublon
            comptes = ingest_decp.charger(conn, duck)
            conn.commit()
        assert comptes["decp_marches"] == 41
        assert comptes["decp_agg_departement"] == 31
        n = conn.execute("SELECT count(*) AS n FROM decp_marches").fetchone()["n"]
        assert n == 41
        suspects = conn.execute(
            "SELECT count(*) AS n FROM decp_marches WHERE montant_suspect = 1"
        ).fetchone()["n"]
        assert suspects >= 2  # au moins le géant et l'aberrant
    finally:
        conn.close()


@pytest.mark.reseau
def test_integration_reelle(tmp_path, monkeypatch):
    """Run complet : téléchargement (cache 24 h) + base jetable, données réelles."""
    chemin = tmp_path / "decp_reel.db"
    monkeypatch.setenv("FT_DB_PATH", str(chemin))
    assert ingest_decp.main() == 0

    conn = db.connexion(chemin)
    try:
        n = conn.execute("SELECT count(*) AS n FROM decp_marches").fetchone()["n"]
        assert n > 100_000  # ~600 k attendus sur 24 mois
        borne = conn.execute(
            """SELECT max(montant_total * 1.0 / nb_marches) AS m
               FROM decp_agg_departement"""
        ).fetchone()["m"]
        assert borne <= ingest_decp.PLAFOND_ECRETAGE_EUR
        meta = conn.execute(
            "SELECT * FROM meta_sources WHERE source_id = 'S1'"
        ).fetchone()
        assert meta["licence"] == "Licence Ouverte 2.0"
        assert meta["date_donnees"] >= "2026-08-01"  # build quotidien, notif J-1
    finally:
        conn.close()

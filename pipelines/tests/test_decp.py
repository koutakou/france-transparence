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

Le marché du dép. 972 porte aussi le cas de l'AVENANT : notifié le
17/04/2026 (modification 1, non courante), il reçoit le 03/06/2026 une
modification 2 qui, elle, est la version courante. C'est sur lui que se
vérifie la date retenue. 17 des 42 marchés servis n'ont aucune ligne
modification_id = 0 — le cas que min(dateNotification) couvre sans détour.

La transformation est testée en pur (DuckDB seulement, date de référence
figée au 19/08/2026) ; l'intégration réelle (téléchargement 243 Mo + SQLite)
est marquée `reseau`.
"""

import json
import math
import re
import sqlite3
from datetime import date
from pathlib import Path

import pytest

from pipelines import db, ingest_decp

DATE_REF = date(2026, 8, 19)
FIXTURE = Path(__file__).parent / "fixtures" / "decp_mini.parquet"

UID_GEANT = "255801185000182024AC34_40100000"          # 12 311 111 111 €, 'suspect'
UID_ABERRANT = "7943807330002020212021-036_45111100"   # brut 99 999 999 999,99 €
UID_MULTI = "015450638001172026p9f730000000_71222000"  # 3 co-titulaires
UID_DOUBLONS = "200041788000642025_017_PI0_79311000"   # avenant + titulaires dupliqués
UID_SANS_MONTANT = "2529011450004200067_45231400"      # montant NULL (réel)
# Marché notifié en 2023, catégorie « Commune » : seul cas de la fixture qui
# tombe à la fois dans une cohorte CLOSE et dans une catégorie renseignée
# partagée avec un autre marché — de quoi voir une ligne bouger sans
# disparaître. Hors fenêtre des tables de marchés, il n'appartient qu'aux
# tables de publication.
UID_COHORTE_CLOSE = "213401839000132023OP371L300_45112500"


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
    """Les deux classements sont écrêtés, répartis, et rangés par ENTREPRISE.

    Les clés attendues sont des SIREN (9 chiffres), pas des SIRET : c'est
    l'unité de regroupement des deux tables.
    """
    duck, _ = resultat
    top_a = duck.execute(
        "SELECT rang, siren, montant_total FROM t_top_acheteurs ORDER BY rang"
    ).fetchall()
    # L'acheteur du géant plafonne à exactement 100 M€ au lieu de 12,3 Md€.
    assert top_a[0][1] == "255801185"        # SIREN de 25580118500018
    assert top_a[0][2] == pytest.approx(100_000_000.0)
    assert [r[0] for r in top_a] == list(range(1, len(top_a) + 1))

    top_t = duck.execute(
        "SELECT siren, nb_marches, montant_total FROM t_top_titulaires ORDER BY rang"
    ).fetchall()
    assert top_t[0][2] == pytest.approx(100_000_000.0)  # titulaire du géant
    # Marché multi-titulaires : montant divisé entre les 3 co-titulaires.
    part = {r[0]: r[2] for r in top_t}["381810852"]   # SIREN de 38181085200057
    assert part == pytest.approx(94_100.0 / 3)

    # Toutes les clés servies sont des SIREN à 9 chiffres — aucun SIRET, aucun
    # identifiant-rebut n'a survécu au filtre de conformité.
    for table in ("t_top_acheteurs", "t_top_titulaires"):
        cles = [c for (c,) in duck.execute(f"SELECT siren FROM {table}").fetchall()]
        assert cles and all(len(c) == 9 and c.isdigit() for c in cles)


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


# ---------------------------------------------------------------------------
# Qualité des montants : ce que vaut le total affiché
# ---------------------------------------------------------------------------


def test_qualite_montants_est_une_ligne_coherente(resultat):
    """La table de qualité décrit EXACTEMENT la fenêtre 12 mois des agrégats.

    Elle est calculée dans le pipeline, sur la vue `recents`, parce que la
    coupe des 12 mois n'est stockée nulle part en base : elle dépend du jour
    d'ingestion, et max(date_notification) — antérieur de quelques jours —
    la retrouverait décalée.
    """
    duck, _ = resultat
    lignes = duck.execute("SELECT * FROM t_qualite_montants").fetchall()
    assert len(lignes) == 1
    noms = [d[0] for d in duck.description]
    q = dict(zip(noms, lignes[0]))

    assert q["id"] == 1
    assert q["plafond"] == ingest_decp.PLAFOND_ECRETAGE_EUR

    # Même population et même total que decp_repartition (100 % des marchés
    # de la fenêtre) : les deux chiffres affichés doivent coïncider.
    nb_rep, montant_rep = duck.execute(
        "SELECT sum(nb_marches), sum(montant_total) FROM t_repartition "
        "WHERE dimension = 'procedure'"
    ).fetchone()
    assert q["nb_marches"] == nb_rep == 37
    assert q["montant_total"] == pytest.approx(montant_rep)
    assert q["montant_total"] == pytest.approx(122_699_312.99)

    # Part écrêtée : le géant à 12,3 Md€ compté au plafond, et lui seul.
    assert q["nb_ecretes"] == 1
    assert q["montant_ecretes"] == pytest.approx(100_000_000.0)

    # Part suspecte : le géant + l'aberrant (drapeau de la source).
    assert q["nb_suspects"] == 2
    assert q["montant_suspects"] == pytest.approx(100_115_000.0)

    # Les écrêtés sont un sous-ensemble des suspects (règle du pipeline :
    # montant_suspect = 1 dès que montant_retenu dépasse le plafond).
    assert q["nb_ecretes"] <= q["nb_suspects"]

    # Borne basse = total moins la part suspecte, à l'euro près.
    assert q["montant_hors_suspects"] == pytest.approx(
        q["montant_total"] - q["montant_suspects"]
    )

    # Le brut n'est pas écrêté : il dépasse largement le total affiché.
    assert q["montant_brut"] == pytest.approx(12_333_810_423.99)
    assert q["montant_brut"] > q["montant_total"]

    # Marchés sans montant : comptés dans nb_marches, hors de toute somme.
    assert q["nb_sans_montant"] == 2


def test_qualite_montants_ecrit_une_seule_ligne(tmp_path, resultat):
    """`decp_qualite_montants` reste à UNE ligne après plusieurs passages."""
    duck, _ = resultat
    conn = db.init_db(chemin=tmp_path / "decp_qualite.db")
    try:
        for _ in range(2):
            comptes = ingest_decp.charger(conn, duck)
            conn.commit()
        assert comptes["decp_qualite_montants"] == 1
        lignes = conn.execute("SELECT * FROM decp_qualite_montants").fetchall()
        assert len(lignes) == 1
        assert lignes[0]["id"] == 1
        assert lignes[0]["nb_marches"] == 37
        assert lignes[0]["plafond"] == ingest_decp.PLAFOND_ECRETAGE_EUR
        # Les valeurs traversent SQLite en REAL/INTEGER (jamais un Decimal,
        # que sqlite3 refuse de lier).
        for col in ("montant_total", "montant_ecretes", "montant_suspects",
                    "montant_hors_suspects", "montant_brut", "plafond"):
            assert isinstance(lignes[0][col], float)
    finally:
        conn.close()


def test_drapeau_suspect_se_decompose_en_trois_classes(resultat):
    """Le drapeau `montant_suspect` recouvre TROIS situations distinctes.

    /marches les compte séparément, parce qu'elles ne se valent pas :
    'aberrant' = la source a repéré ET redressé la saisie (le montant compté
    est déjà le montant corrigé) ; 'suspect' = elle signale sans corriger (le
    montant déclaré est conservé tel quel) ; anomalie NULL = c'est notre seul
    écrêtage qui lève le drapeau. Ce test fige la partition sur laquelle la
    page s'appuie : exhaustive, sans recouvrement, et recomposant exactement
    le `nb_suspects` publié.
    """
    duck, _ = resultat
    plafond = ingest_decp.PLAFOND_ECRETAGE_EUR
    classes = {
        r[0]: (r[1], r[2])
        for r in duck.execute(
            """
            SELECT coalesce(montant_anomalie, '(écrêtage seul)') AS classe,
                   count(*), sum(montant_ecrete)
            FROM recents WHERE montant_suspect = 1
            GROUP BY classe
            """
        ).fetchall()
    }
    # Fixture : l'accord-cadre géant (signalé, non corrigé, donc écrêté au
    # plafond) et l'aberrant (redressé par la source à 115 k€).
    assert classes == {
        "suspect": (1, pytest.approx(plafond)),
        "aberrant": (1, pytest.approx(115_000.0)),
    }

    # La partition recompose exactement le compteur publié.
    nb_suspects = duck.execute(
        "SELECT nb_suspects FROM t_qualite_montants"
    ).fetchone()[0]
    assert sum(nb for nb, _ in classes.values()) == nb_suspects

    # Exhaustivité dans l'autre sens : aucun marché non drapeauté ne relève
    # d'une des trois classes (sinon la décomposition en oublierait).
    assert duck.execute(
        f"""
        SELECT count(*) FROM recents
        WHERE montant_suspect = 0
          AND (montant_anomalie IS NOT NULL OR montant_retenu > {plafond})
        """
    ).fetchone()[0] == 0

    # Le redressement de la source ramène l'aberrant SOUS le plafond : il
    # n'est donc pas écrêté — le confondre avec un montant non expliqué
    # gonflerait le compteur sans rien apporter au total.
    assert duck.execute(
        "SELECT count(*) FROM recents "
        "WHERE montant_anomalie = 'aberrant' AND ecrete"
    ).fetchone()[0] == 0


def test_ecretes_totaux_depassent_le_sous_total_departemental(resultat):
    """Le compte d'écrêtés de la qualité couvre TOUS les acheteurs.

    `SUM(nb_marches_ecretes) FROM decp_agg_departement` n'en couvre que les
    acheteurs à département connu (402 contre 404 sur la base réelle du
    20/08/2026) : la page doit citer le compte total, pas ce sous-total.
    """
    duck, _ = resultat
    total = duck.execute("SELECT nb_ecretes FROM t_qualite_montants").fetchone()[0]
    par_dep = duck.execute(
        "SELECT coalesce(sum(nb_marches_ecretes), 0) FROM t_agg_departement"
    ).fetchone()[0]
    assert total >= par_dep


# ---------------------------------------------------------------------------
# Date de notification : celle du marché initial, pas celle du dernier avenant
# ---------------------------------------------------------------------------


def test_la_date_retenue_est_celle_de_la_notification_initiale(resultat):
    """Un avenant ne renotifie pas le marché : la date reste celle de l'origine.

    À la source, la ligne d'un avenant porte comme `dateNotification` la date
    de l'AVENANT, et `donneesActuelles` ne vaut que sur la dernière
    modification : lire la date sur la seule ligne courante date le marché de
    son dernier avenant. Mesuré le 21/08/2026 sur le parquet du 20/08
    (3 240 022 lignes, 1 827 781 uid) : 314 173 marchés étaient datés trop
    tard, tous vers le futur, dont 307 517 (97,9 %) changeaient de mois.

    Valeurs relevées à la main dans la fixture pour ce uid : 8 lignes, une
    modification 1 non courante notifiée le 17/04/2026 (3 titulaires) et une
    modification 2 courante notifiée le 03/06/2026 (5 titulaires), toutes à
    4 012 774 € dans le département 972.
    """
    duck, _ = resultat
    marche = _table(duck, "t_marches", ["uid"])[UID_DOUBLONS]
    assert marche["date_notification"] == "2026-04-17"
    # Les ATTRIBUTS restent lus sur la ligne COURANTE — « marché notifié le
    # 17/04/2026, montant et titulaires connus à ce jour » : les 5 titulaires
    # de la modification 2, pas les 3 de la modification 1.
    assert marche["nb_titulaires"] == 5
    assert marche["montant_retenu"] == pytest.approx(4_012_774.0)
    assert marche["acheteur_departement_code"] == "972"


def test_les_dates_servies_valent_le_minimum_sur_toutes_les_lignes(resultat):
    """Invariant sur les 42 marchés servis, vérifié contre la fixture brute.

    La date publiée vaut le min(dateNotification) de TOUTES les lignes du uid
    — les non courantes comprises — donc jamais postérieure à la date de la
    ligne courante. Aucune n'est NULL et aucune n'est inventée : chacune est
    reprise telle quelle d'une ligne de la fixture.
    """
    import duckdb

    def dates_par_uid(clause: str) -> dict[str, str]:
        return dict(
            duckdb.sql(
                f"""SELECT uid, CAST(min(dateNotification) AS VARCHAR)
                    FROM read_parquet('{FIXTURE}')
                    WHERE dateNotification IS NOT NULL {clause}
                    GROUP BY uid"""
            ).fetchall()
        )

    origine = dates_par_uid("")                         # toutes les lignes
    courante = dates_par_uid("AND donneesActuelles")    # la seule version courante

    duck, _ = resultat
    servis = duck.execute("SELECT uid, date_notification FROM t_marches_36").fetchall()
    assert len(servis) == 42
    for uid, date_notification in servis:
        assert date_notification is not None
        assert date_notification == origine[uid]
        assert date_notification <= courante[uid]
    # Un cas au moins doit séparer les deux dates, sinon l'invariant ci-dessus
    # serait vrai sans rien démontrer.
    assert sum(1 for uid, d in servis if d < courante[uid]) == 1


def test_la_serie_mensuelle_range_le_marche_dans_son_mois_dorigine(resultat):
    """Le marché à avenant compte en avril, mois où il a été notifié.

    Comptes relevés à la main dans la fixture. Mesuré le 21/08/2026 sur le
    parquet du 20/08, l'enjeu de ce déplacement : sur les 861 849 marchés de
    la fenêtre 36 mois, 217 827 (25,3 %) étaient rangés dans le mauvais mois.
    """
    duck, _ = resultat
    mois = dict(duck.execute("SELECT mois, nb_marches FROM t_agg_mois").fetchall())
    assert mois["2026-04"] == 5
    assert mois["2026-06"] == 4
    # Le marché est déplacé, pas dupliqué ni perdu : le total ne bouge pas.
    total = duck.execute("SELECT count(*) FROM t_marches_36").fetchone()[0]
    assert sum(mois.values()) == total == 42


def test_les_fenetres_portent_sur_la_date_de_notification_initiale():
    """Les coupes 24 et 12 mois se font sur la date d'origine.

    Même fixture, autre date de référence — la transformation est pure et
    rejouable. Au 01/05/2027, le marché notifié le 17/04/2026 est sorti des
    12 derniers mois, alors que la date de son avenant (03/06/2026) y serait
    encore : il ne doit plus peser dans les agrégats.
    """
    duck, _ = ingest_decp.transformer(FIXTURE, date(2027, 5, 1))
    try:
        assert duck.execute(
            f"SELECT date_notification FROM t_marches WHERE uid = '{UID_DOUBLONS}'"
        ).fetchone() == ("2026-04-17",)
        assert duck.execute(
            f"SELECT count(*) FROM recents WHERE uid = '{UID_DOUBLONS}'"
        ).fetchone()[0] == 0
        # C'était le seul marché du 972 dans la fixture : le département sort
        # de la carte, au lieu d'y porter 4 012 774 € qui n'y sont plus.
        assert duck.execute(
            "SELECT count(*) FROM t_agg_departement WHERE departement_code = '972'"
        ).fetchone()[0] == 0
        assert duck.execute("SELECT count(*) FROM recents").fetchone()[0] == 7
    finally:
        duck.close()


def test_les_marches_sans_ligne_modification_zero_sont_dates(resultat):
    """POURQUOI min() global plutôt que « la valeur à modification_id = 0 ».

    Mesuré le 21/08/2026 sur le parquet du 20/08 : 12 278 uid n'ont aucune
    ligne modification_id = 0. Les lire à la ligne 0 les laisserait sans
    date ; min(dateNotification) sur toutes les lignes les couvre sans cas
    particulier. La fixture en porte 17 sur les 42 marchés servis — tous
    datés, aucune date manquante comblée par une valeur de remplacement.
    """
    import duckdb

    sans_ligne_zero = {
        uid
        for (uid,) in duckdb.sql(
            f"""SELECT uid FROM read_parquet('{FIXTURE}')
                GROUP BY uid HAVING count(*) FILTER (modification_id = 0) = 0"""
        ).fetchall()
    }
    duck, _ = resultat
    servis = dict(
        duck.execute("SELECT uid, date_notification FROM t_marches_36").fetchall()
    )
    concernes = {uid: d for uid, d in servis.items() if uid in sans_ligne_zero}
    assert len(concernes) == 17
    assert all(d is not None and len(d) == 10 for d in concernes.values())
    # Valeur relevée à la main : ce marché n'a qu'une ligne, modification 10.
    assert concernes[UID_SANS_MONTANT] == "2026-03-03"


# ---------------------------------------------------------------------------
# Hygiène des chaînes au chargement (§ M8 de doc/QUALITE-DONNEES.md)
# ---------------------------------------------------------------------------


def test_assainir_lot_repare_et_normalise_les_colonnes_servies():
    """Mesuré le 20/08/2026 sur la base de production : 308 objets porteurs
    de mojibake (→ 5 irréparables) et 77 306 porteurs d'espaces parasites."""
    champs = ["uid", "objet", "acheteur_nom", "montant_retenu"]
    lot = [("U1", "TRAVAUX  DE\nRÃ‰NOVATION ", "  MAIRIE DE PARIS ", 1000.0)]
    (ligne,) = ingest_decp._assainir_lot(lot, champs)
    assert ligne == ("U1", "TRAVAUX DE RÉNOVATION", "MAIRIE DE PARIS", 1000.0)


def test_assainir_lot_ne_touche_pas_aux_espaces_du_json_titulaires():
    """`titulaires_json` est de la syntaxe : on y répare le mojibake, pas
    les espaces, qui sont porteurs de sens dans une chaîne sérialisée."""
    champs = ["uid", "titulaires_json"]
    valeur = '[{"siret": "123", "nom": "SociÃ©tÃ©  X"}]'
    (ligne,) = ingest_decp._assainir_lot([("U1", valeur)], champs)
    assert ligne[1] == '[{"siret": "123", "nom": "Société  X"}]'


def test_assainir_lot_laisse_passer_un_lot_sans_colonne_texte():
    """Le pipeline transfère ~600 000 lignes : pas de coût là où c'est inutile."""
    lot = [("2026-01", 42, 1000.0)]
    assert ingest_decp._assainir_lot(lot, ["mois", "nb_marches", "montant_total"]) is lot


# ---------------------------------------------------------------------------
# Qualité de PUBLICATION : le délai légal de 2 mois est-il respecté ?
# ---------------------------------------------------------------------------
#
# Population de la fixture pour ces tables : 45 uid (les 42 servis aux autres
# tables, plus les 3 que leurs dates en écartent), dont 1 sans date de
# notification et 1 publié AVANT d'être notifié. Aucun uid de la fixture ne
# porte de date sentinelle ni de date manquante côté publication : les
# compteurs correspondants y valent 0, ce que les tests ci-dessous
# n'immobilisent pas — ils vérifient la recomposition, pas les effectifs.

CLASSES_PUBLICATION = frozenset({
    "retenu", "sans_notification", "sans_publication",
    "dates_hors_bornes", "publication_anterieure",
})


def _ligne_qualite_publication(duck):
    """La ligne unique de t_publication_qualite, en dictionnaire."""
    lignes = duck.execute("SELECT * FROM t_publication_qualite").fetchall()
    assert len(lignes) == 1
    return dict(zip([d[0] for d in duck.description], lignes[0]))


def _fixture_modifiee(chemin_sortie, dates_par_uid=None, categories_par_uid=None,
                      titulaires_par_uid=None, acheteurs_id_par_uid=None):
    """Copie de la fixture où quelques uid reçoivent d'autres valeurs.

    Les 64 colonnes et toutes les lignes sont conservées : seules les deux
    dates du délai, la catégorie d'acheteur et — depuis le regroupement par
    entreprise — l'identité du titulaire changent, pour les uid nommés.
    `titulaires_par_uid` associe un uid au triplet
    (titulaire_id, titulaire_nom, titulaire_categorie) : il ne vaut donc que
    pour des marchés à titulaire UNIQUE, sinon il fondrait les co-titulaires
    en un seul.
    Sert à construire les cas que la fixture ne contient pas — un vrai
    parquet, lu par le vrai `transformer`, plutôt qu'une réécriture du SQL
    dans le test, qui ne prouverait rien du pipeline.
    """
    import duckdb

    dates_par_uid = dates_par_uid or {}
    categories_par_uid = categories_par_uid or {}
    titulaires_par_uid = titulaires_par_uid or {}
    acheteurs_id_par_uid = acheteurs_id_par_uid or {}

    def litteral(valeur, type_sql):
        if valeur is None:
            return "NULL"
        if type_sql == "DATE":
            return f"DATE '{valeur}'"
        return "'" + valeur.replace("'", "''") + "'"

    def cas(valeurs_par_uid, colonne, type_sql):
        if not valeurs_par_uid:
            return colonne
        branches = " ".join(
            f"WHEN '{uid}' THEN {litteral(valeur, type_sql)}"
            for uid, valeur in valeurs_par_uid.items()
        )
        return f"CASE uid {branches} ELSE {colonne} END"

    notification = cas(
        {u: d[0] for u, d in dates_par_uid.items()}, "dateNotification", "DATE"
    )
    publication = cas(
        {u: d[1] for u, d in dates_par_uid.items()}, "datePublicationDonnees", "DATE"
    )
    categorie = cas(categories_par_uid, "acheteur_categorie", "VARCHAR")
    tit_id = cas(
        {u: v[0] for u, v in titulaires_par_uid.items()}, "titulaire_id", "VARCHAR"
    )
    tit_nom = cas(
        {u: v[1] for u, v in titulaires_par_uid.items()}, "titulaire_nom", "VARCHAR"
    )
    tit_cat = cas(
        {u: v[2] for u, v in titulaires_par_uid.items()},
        "titulaire_categorie", "VARCHAR",
    )
    ach_id = cas(acheteurs_id_par_uid, "acheteur_id", "VARCHAR")

    duckdb.sql(
        f"""
        COPY (SELECT * REPLACE (
                  {notification} AS dateNotification,
                  {publication}  AS datePublicationDonnees,
                  {categorie}    AS acheteur_categorie,
                  {tit_id}       AS titulaire_id,
                  {tit_nom}      AS titulaire_nom,
                  {tit_cat}      AS titulaire_categorie,
                  {ach_id}       AS acheteur_id)
              FROM read_parquet('{FIXTURE}'))
        TO '{chemin_sortie}' (FORMAT PARQUET)
        """
    )
    return chemin_sortie


def test_publication_qualite_recompose_la_population_de_depart(resultat):
    """Les cinq classes se partagent EXACTEMENT les marchés du parquet.

    C'est l'invariant qui rend la table lisible : un lecteur doit pouvoir
    retrancher les écarts de la population de départ et retomber sur les
    retenus. Il suppose deux choses — que le classement soit exhaustif, et
    qu'aucun marché n'y figure deux fois.
    """
    duck, _ = resultat
    q = _ligne_qualite_publication(duck)

    assert q["id"] == 1
    # Population = les uid du parquet, sans aucune borne de date.
    nb_uid = duck.execute(
        f"SELECT count(DISTINCT uid) FROM read_parquet('{FIXTURE}')"
    ).fetchone()[0]
    assert q["nb_marches_source"] == nb_uid == 45

    assert (
        q["nb_retenus"]
        + q["nb_sans_notification"]
        + q["nb_sans_publication"]
        + q["nb_dates_hors_bornes"]
        + q["nb_publication_anterieure"]
    ) == q["nb_marches_source"]

    # Exhaustivité et unicité, vues depuis la table classée : aucune classe
    # hors nomenclature, et un uid dans une seule ligne.
    classes = duck.execute(
        "SELECT DISTINCT classe FROM t_publication_classee"
    ).fetchall()
    assert {c for (c,) in classes} <= CLASSES_PUBLICATION
    assert duck.execute(
        "SELECT count(*), count(DISTINCT uid) FROM t_publication_classee"
    ).fetchone() == (45, 45)

    # Les retenus sont ceux dont les deux dates existent, tiennent dans les
    # bornes et sont dans l'ordre — la définition, vérifiée sur les données.
    assert duck.execute(
        f"""
        SELECT count(*) FROM t_publication_classee
        WHERE (classe = 'retenu') <> (
              notification IS NOT NULL AND publication IS NOT NULL
          AND notification BETWEEN DATE '{ingest_decp.BORNE_DATE_MIN}'
                               AND DATE '{ingest_decp.BORNE_DATE_MAX}'
          AND publication  BETWEEN DATE '{ingest_decp.BORNE_DATE_MIN}'
                               AND DATE '{ingest_decp.BORNE_DATE_MAX}'
          AND publication >= notification)
        """
    ).fetchone()[0] == 0


def test_publication_le_classement_est_exclusif_sur_un_marche_a_deux_defauts(
    tmp_path,
):
    """Un marché qui cumule deux défauts n'est compté qu'une fois.

    La fixture n'en contient aucun — tous ses écarts sont simples — donc
    l'invariant de recomposition y serait vrai même avec des compteurs qui
    se recouvrent. Le cas est donc construit, et il n'a rien de théorique :
    mesuré le 21/08/2026 sur data/raw/decp.parquet, compter les défauts
    séparément donne 14 838 marchés sans publication et 73 141 publiés avant
    notification, contre 3 017 et 73 119 une fois le classement rendu
    exclusif — 9 283 marchés comptés deux fois, et une somme des classes qui
    dépasse la population de 9 283.

    Trois marchés retenus de la fixture sont redatés :
      · l'un perd ses DEUX dates → « sans notification » seulement ;
      · un autre reçoit une notification hors borne haute (2050) ET une
        publication antérieure → « dates hors bornes » seulement ;
      · le dernier reçoit la sentinelle 0001-01-01 que la source livre en
        guise de date manquante, sous la borne basse → « dates hors bornes ».
    """
    chemin = _fixture_modifiee(
        tmp_path / "decp_deux_defauts.parquet",
        {
            UID_MULTI: (None, None),
            UID_GEANT: ("2050-01-01", "2026-01-01"),
            UID_SANS_MONTANT: ("0001-01-01", "2026-01-01"),
        },
    )
    duck, _ = ingest_decp.transformer(chemin, DATE_REF)
    try:
        q = _ligne_qualite_publication(duck)
        assert q["nb_marches_source"] == 45
        # La fixture porte déjà 1 marché sans notification et 1 publié avant
        # notification : les cas construits ajoutent 1 à leur SEULE classe.
        assert q["nb_sans_notification"] == 2
        assert q["nb_dates_hors_bornes"] == 2
        # Les deux classes que le cumul aurait fait doubler ne bougent pas.
        assert q["nb_sans_publication"] == 0
        assert q["nb_publication_anterieure"] == 1
        assert q["nb_retenus"] == 40
        assert (
            q["nb_retenus"]
            + q["nb_sans_notification"]
            + q["nb_sans_publication"]
            + q["nb_dates_hors_bornes"]
            + q["nb_publication_anterieure"]
        ) == q["nb_marches_source"]

        classes = dict(
            duck.execute(
                "SELECT uid, classe FROM t_publication_classee WHERE uid IN "
                f"('{UID_MULTI}', '{UID_GEANT}', '{UID_SANS_MONTANT}')"
            ).fetchall()
        )
        assert classes == {
            UID_MULTI: "sans_notification",
            UID_GEANT: "dates_hors_bornes",
            UID_SANS_MONTANT: "dates_hors_bornes",
        }
    finally:
        duck.close()


def test_publication_le_delai_legal_se_compte_en_mois_et_non_en_jours(tmp_path):
    """« 2 mois » et « 60 jours » ne désignent pas le même délai.

    Aucun marché de la fixture ne les sépare : sur ses 43 retenus, les deux
    règles rendent le même verdict partout. Les deux cas sont donc
    construits, et ils tombent des deux côtés :
      · notifié le 11/03/2026, publié le 11/05/2026 — 61 jours, mais le
        11 mai EST la date limite légale : dans les temps ;
      · notifié le 31/12/2025, publié le 01/03/2026 — 60 jours, mais la
        limite légale était le 28/02/2026 : hors délai.
    Une règle en jours se tromperait sur les deux, en sens contraires.
    """
    chemin = _fixture_modifiee(
        tmp_path / "decp_delai_mois.parquet",
        {
            UID_ABERRANT: ("2026-03-11", "2026-05-11"),
            UID_DOUBLONS: ("2025-12-31", "2026-03-01"),
        },
    )
    duck, _ = ingest_decp.transformer(chemin, DATE_REF)
    try:
        verdicts = dict(
            duck.execute(
                "SELECT uid, dans_delai FROM publies "
                f"WHERE uid IN ('{UID_ABERRANT}', '{UID_DOUBLONS}')"
            ).fetchall()
        )
        assert verdicts == {UID_ABERRANT: True, UID_DOUBLONS: False}
        # Les délais en jours, eux, disent l'inverse : c'est bien la règle
        # qui départage, pas les données.
        delais = dict(
            duck.execute(
                "SELECT uid, delai FROM publies "
                f"WHERE uid IN ('{UID_ABERRANT}', '{UID_DOUBLONS}')"
            ).fetchall()
        )
        assert delais == {UID_ABERRANT: 61, UID_DOUBLONS: 60}
        assert (delais[UID_ABERRANT] <= 60) is not verdicts[UID_ABERRANT]
        assert (delais[UID_DOUBLONS] <= 60) is not verdicts[UID_DOUBLONS]
    finally:
        duck.close()

    # Le délai publié est celui du code de la commande publique.
    assert ingest_decp.DELAI_LEGAL_MOIS == 2


def test_publication_retient_la_premiere_mise_en_ligne(resultat):
    """Une republication lors d'un avenant ne défait pas une publication à l'heure.

    Le uid à avenant de la fixture porte deux dates de publication : le
    17/04/2026 sur la modification 1, le 16/06/2026 sur la modification 2,
    devenue la version courante. Le délai légal vise la PREMIÈRE mise en
    ligne — celle du 17/04, le jour même de la notification, soit 0 jour.
    Lire la dernière ferait apparaître 60 jours de retard là où il n'y en a
    aucun. Le cas n'est pas marginal : mesuré le 21/08/2026 sur
    data/raw/decp.parquet, 264 177 marchés portent plusieurs dates de
    publication.
    """
    duck, _ = resultat
    ligne = duck.execute(
        "SELECT CAST(publication AS VARCHAR), delai, dans_delai FROM publies "
        f"WHERE uid = '{UID_DOUBLONS}'"
    ).fetchone()
    assert ligne == ("2026-04-17", 0, True)
    # La fixture porte bien deux dates distinctes pour ce marché, sinon le
    # test ne départagerait rien.
    assert duck.execute(
        f"""SELECT count(DISTINCT datePublicationDonnees)
            FROM read_parquet('{FIXTURE}') WHERE uid = '{UID_DOUBLONS}'"""
    ).fetchone()[0] == 2


def test_publication_ne_reprend_pas_la_fenetre_glissante_des_agregats(resultat):
    """La série de publication porte sur TOUT le parquet, pas sur 36 mois.

    Les tables de marchés sont bornées (`t_date_initiale` coupe par son
    HAVING, `recents` par sa clause de date). Calculer la qualité de
    publication à partir d'elles amputerait la série de ses premières
    années : la fixture porte 2 marchés notifiés avant la fenêtre, qui
    doivent malgré tout compter ici.
    """
    duck, _ = resultat
    retenus = {uid for (uid,) in duck.execute("SELECT uid FROM publies").fetchall()}
    fenetre = {
        uid for (uid,) in duck.execute("SELECT uid FROM t_marches_36").fetchall()
    }
    hors_fenetre = retenus - fenetre
    assert len(hors_fenetre) == 2
    assert all(
        d < "2023-08-19"
        for (d,) in duck.execute(
            "SELECT CAST(notification AS VARCHAR) FROM publies "
            f"WHERE uid IN ({', '.join(repr(u) for u in hors_fenetre)})"
        ).fetchall()
    )
    # Et réciproquement : un marché de la fenêtre peut être écarté ici (le
    # marché publié avant d'être notifié). Les deux populations ne sont donc
    # ni l'une dans l'autre ni interchangeables.
    assert fenetre - retenus


def test_publication_qualite_decrit_une_distribution_ordonnee(resultat):
    """Quantiles, cohortes et date d'observation d'une seule ligne cohérente."""
    duck, _ = resultat
    q = _ligne_qualite_publication(duck)

    quantiles = [q["delai_q1"], q["delai_median"], q["delai_q3"], q["delai_d9"]]
    assert quantiles == sorted(quantiles)
    # Aucun délai négatif ne survit au classement : les publications
    # antérieures à la notification sont écartées, pas ramenées à zéro.
    assert quantiles[0] >= 0
    assert duck.execute("SELECT min(delai) FROM publies").fetchone()[0] >= 0

    # Les quantiles portent sur les SEULS retenus. Re-dérivés ici depuis le
    # parquet brut, sans passer par les tables du pipeline : laisser entrer
    # les écartés déplacerait le troisième quartile de la fixture de 37 à
    # 29 jours, un marché publié 257 jours avant d'être notifié suffisant à
    # tirer la distribution vers le bas.
    delais = sorted(
        d
        for (d,) in duck.execute(
            f"""
            SELECT date_diff('day', min(dateNotification),
                                    min(datePublicationDonnees))
            FROM read_parquet('{FIXTURE}')
            GROUP BY uid
            HAVING min(dateNotification) IS NOT NULL
               AND min(datePublicationDonnees) IS NOT NULL
               AND min(datePublicationDonnees) >= min(dateNotification)
            """
        ).fetchall()
    )
    assert len(delais) == q["nb_retenus"]
    # Quantiles DISCRETS : chacun est un délai réellement observé, jamais une
    # moyenne entre deux marchés.
    assert quantiles == [
        delais[max(0, math.ceil(part * len(delais)) - 1)]
        for part in (0.25, 0.50, 0.75, 0.90)
    ]
    assert all(x in delais for x in quantiles)

    assert q["delai_legal_mois"] == ingest_decp.DELAI_LEGAL_MOIS
    assert q["cohorte_min"] == ingest_decp.ANNEE_MIN_COHORTE
    assert q["cohorte_max"] == DATE_REF.year - ingest_decp.DECALAGE_COHORTE_CLOSE
    assert q["cohorte_min"] <= q["cohorte_max"]

    # Date d'observation = la publication la plus récente parmi les retenus,
    # en ISO : c'est elle qui borne ce que la série peut savoir.
    assert q["date_observation_max"] == duck.execute(
        "SELECT CAST(max(publication) AS VARCHAR) FROM publies"
    ).fetchone()[0]
    assert len(q["date_observation_max"]) == 10

    # Les sans-catégorie sont comptés sur les cohortes CLOSES, exactement la
    # population que la ventilation par acheteur couvre. C'est leur seul
    # usage : dire quelle part de cette ventilation échappe au lecteur. Ils
    # partagent donc son dénominateur — comptés sur tous les retenus, toutes
    # années confondues, ils gonfleraient la part affichée d'un manque qui
    # n'est pas celui de la ventilation.
    retenus_closes = duck.execute(
        f"""SELECT count(*) FROM publies
            WHERE annee BETWEEN {q['cohorte_min']} AND {q['cohorte_max']}"""
    ).fetchone()[0]
    ventiles = duck.execute(
        "SELECT coalesce(sum(nb_marches), 0) FROM t_publication_acheteurs"
    ).fetchone()[0]
    assert ventiles + q["nb_sans_categorie"] == retenus_closes


def test_publication_annees_invariants(resultat):
    """La série annuelle ne peut pas mentir sur son propre dénominateur."""
    duck, _ = resultat
    annees = duck.execute(
        "SELECT annee, nb_marches, nb_dans_delai, taux_dans_delai, "
        "delai_median, nb_plus_un_an, cohorte_close "
        "FROM t_publication_annees ORDER BY annee"
    ).fetchall()
    assert annees

    cohorte_max = DATE_REF.year - ingest_decp.DECALAGE_COHORTE_CLOSE
    vues = [a[0] for a in annees]
    assert vues == sorted(set(vues))  # une ligne par année, PK respectée

    for annee, nb, dans, taux, median, plus_un_an, close in annees:
        # Avant 2018 la série n'a pas de sens (effectifs résiduels) : elle
        # commence là, et la fixture ne doit pas la faire remonter plus haut.
        assert annee >= ingest_decp.ANNEE_MIN_PUBLICATION
        assert nb > 0
        assert 0 <= dans <= nb
        assert taux == pytest.approx(100.0 * dans / nb)
        assert 0.0 <= taux <= 100.0
        assert median >= 0          # conséquence du filtre d'incohérence
        assert 0 <= plus_un_an <= nb
        assert close == (1 if annee <= cohorte_max else 0)

    # Aucun retenu de 2018 ou après n'est perdu en route.
    assert sum(a[1] for a in annees) == duck.execute(
        "SELECT count(*) FROM publies "
        f"WHERE annee >= {ingest_decp.ANNEE_MIN_PUBLICATION}"
    ).fetchone()[0]
    # Les deux régimes de cohorte sont représentés dans la fixture, sinon
    # l'assertion sur `cohorte_close` ne vaudrait que dans un sens.
    assert {a[6] for a in annees} == {0, 1}


def test_publication_annees_ecarte_les_annees_residuelles(tmp_path):
    """Un marché notifié avant 2018 n'ouvre pas une ligne de série.

    Mesuré le 21/08/2026 sur data/raw/decp.parquet, ces années comptent 92
    marchés retenus en 2015, 377 en 2016, 834 en 2017, contre 20 000 en
    2018 : une ligne « 2002 » à 66 marchés donnerait un taux affiché comme
    les autres alors qu'il ne décrit rien. La fixture ne remonte pas si
    loin, le cas est donc construit à partir d'un de ses marchés.
    """
    chemin = _fixture_modifiee(
        tmp_path / "decp_avant_2018.parquet",
        {UID_MULTI: ("2016-05-04", "2016-06-01")},
    )
    duck, _ = ingest_decp.transformer(chemin, DATE_REF)
    try:
        # Le marché est bien retenu — il n'est pas écarté comme incohérent…
        assert duck.execute(
            f"SELECT annee FROM publies WHERE uid = '{UID_MULTI}'"
        ).fetchone() == (2016,)
        # … mais la série annuelle commence à 2018.
        annees = [
            a for (a,) in duck.execute(
                "SELECT annee FROM t_publication_annees ORDER BY annee"
            ).fetchall()
        ]
        assert 2016 not in annees
        assert min(annees) >= ingest_decp.ANNEE_MIN_PUBLICATION
        # Il reste compté dans la population de départ et dans les retenus :
        # écarté de la série, pas effacé.
        q = _ligne_qualite_publication(duck)
        assert q["nb_marches_source"] == 45
        assert q["nb_retenus"] == 43
        assert q["nb_retenus"] > sum(
            n for (n,) in duck.execute(
                "SELECT nb_marches FROM t_publication_annees"
            ).fetchall()
        )
    finally:
        duck.close()


def test_publication_acheteurs_ne_fabrique_pas_de_categorie_inconnue(resultat):
    """Sans catégorie n'est pas une catégorie : aucune ligne vide ni NULL.

    Agréger les marchés sans catégorie en une ligne « inconnu » fabriquerait
    un acteur qui n'existe pas et qu'un classement afficherait à côté des
    vrais. Ils sont comptés à part (nb_sans_categorie).
    """
    duck, _ = resultat
    lignes = duck.execute(
        "SELECT categorie, nb_marches, nb_dans_delai, taux_dans_delai, "
        "delai_median, nb_plus_un_an, taux_plus_un_an "
        "FROM t_publication_acheteurs"
    ).fetchall()
    assert lignes

    categories = [l[0] for l in lignes]
    assert all(c is not None and c.strip() != "" for c in categories)
    assert len(categories) == len(set(categories))  # PK

    for _, nb, dans, taux, median, plus_un_an, taux_long in lignes:
        assert nb > 0
        assert 0 <= dans <= nb
        assert taux == pytest.approx(100.0 * dans / nb)
        assert median >= 0
        assert 0 <= plus_un_an <= nb
        assert taux_long == pytest.approx(100.0 * plus_un_an / nb)

    # La ventilation ne couvre que les cohortes CLOSES : un marché d'une
    # cohorte encore ouverte y ferait baisser le taux sans raison, ses
    # retards restant hors d'observation à la date de l'ingestion.
    cohorte_max = DATE_REF.year - ingest_decp.DECALAGE_COHORTE_CLOSE
    assert sum(l[1] for l in lignes) == duck.execute(
        f"""SELECT count(*) FROM publies
            WHERE categorie IS NOT NULL
              AND annee BETWEEN {ingest_decp.ANNEE_MIN_COHORTE} AND {cohorte_max}"""
    ).fetchone()[0]


def test_publication_acheteurs_ecarte_la_categorie_vide(tmp_path, resultat):
    """Une catégorie réduite à des espaces est une absence, pas un libellé.

    Sans quoi la ventilation gagnerait une ligne sans nom, affichée à côté
    des vraies catégories et impossible à interpréter. La fixture ne porte
    que des catégories renseignées ou NULL — le cas est donc construit en
    vidant celle d'un marché de cohorte close, et vérifié de bout en bout.
    """
    duck, _ = resultat
    avant = dict(
        duck.execute(
            "SELECT categorie, nb_marches FROM t_publication_acheteurs"
        ).fetchall()
    )
    assert avant["Commune"] == 2
    assert _ligne_qualite_publication(duck)["nb_sans_categorie"] == 1

    chemin = _fixture_modifiee(
        tmp_path / "decp_categorie_vide.parquet",
        categories_par_uid={UID_COHORTE_CLOSE: "   "},
    )
    duck_vide, _ = ingest_decp.transformer(chemin, DATE_REF)
    try:
        apres = dict(
            duck_vide.execute(
                "SELECT categorie, nb_marches FROM t_publication_acheteurs"
            ).fetchall()
        )
        # Aucune ligne sans nom n'apparaît, et le marché quitte « Commune ».
        assert all(c is not None and c.strip() != "" for c in apres)
        assert apres["Commune"] == 1
        # Il n'est pas perdu pour autant : il rejoint les sans-catégorie.
        assert _ligne_qualite_publication(duck_vide)["nb_sans_categorie"] == 2
        assert duck_vide.execute(
            f"SELECT categorie FROM publies WHERE uid = '{UID_COHORTE_CLOSE}'"
        ).fetchone() == (None,)
    finally:
        duck_vide.close()


def test_publication_charger_ecrit_les_trois_tables(tmp_path, resultat):
    """Les trois tables traversent SQLite sans perdre ni dupliquer de ligne."""
    duck, _ = resultat
    conn = db.init_db(chemin=tmp_path / "decp_publication.db")
    try:
        for _ in range(2):  # double passage : réécriture, pas accumulation
            comptes = ingest_decp.charger(conn, duck)
            conn.commit()

        assert comptes["decp_publication_qualite"] == 1
        assert comptes["decp_publication_annees"] == duck.execute(
            "SELECT count(*) FROM t_publication_annees"
        ).fetchone()[0]
        assert comptes["decp_publication_acheteurs"] == duck.execute(
            "SELECT count(*) FROM t_publication_acheteurs"
        ).fetchone()[0]

        qualite = conn.execute("SELECT * FROM decp_publication_qualite").fetchall()
        assert len(qualite) == 1
        assert qualite[0]["id"] == 1
        assert qualite[0]["nb_marches_source"] == 45
        assert qualite[0]["delai_legal_mois"] == 2
        # Les taux sont des pourcentages 0-100 en REAL, pas des fractions,
        # et jamais un Decimal (que sqlite3 refuse de lier).
        for table in ("decp_publication_annees", "decp_publication_acheteurs"):
            for ligne in conn.execute(f"SELECT * FROM {table}").fetchall():
                assert isinstance(ligne["taux_dans_delai"], float)
                assert 0.0 <= ligne["taux_dans_delai"] <= 100.0
                assert ligne["nb_dans_delai"] <= ligne["nb_marches"]

        # Les valeurs relues depuis SQLite sont, ligne pour ligne et colonne
        # pour colonne, celles que DuckDB a calculées : le transfert par lots
        # ne réordonne rien et n'arrondit rien.
        annees = conn.execute(
            "SELECT * FROM decp_publication_annees ORDER BY annee"
        ).fetchall()
        attendu = duck.execute(
            "SELECT annee, nb_marches, nb_dans_delai, taux_dans_delai, "
            "delai_median, nb_plus_un_an, cohorte_close "
            "FROM t_publication_annees ORDER BY annee"
        ).fetchall()
        assert [tuple(l) for l in annees] == [
            (a, nb, dans, pytest.approx(taux), med, plus, close)
            for a, nb, dans, taux, med, plus, close in attendu
        ]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
#
# Regroupement par ENTREPRISE (SIREN) des deux classements
#
# ---------------------------------------------------------------------------
#
# Ces tests réutilisent `_fixture_modifiee` (défini plus haut pour les tables
# de publication) : la fixture RÉELLE ne porte pas les cas nécessaires ici.
# Elle ne contient qu'un seul établissement par entreprise sur la fenêtre 12
# mois — nb_sirens_multi_etab y vaut 0, la fusion ne s'y voit donc pas — et un
# seul identifiant non conforme, le « 00002 » réel du marché
# 263700189002222026F16117_33184200, qui suffit à voir l'écart mais pas à voir
# comment plusieurs formes de malformation sont traitées. Les cas manquants
# sont donc écrits dans une COPIE du parquet, relue par le vrai `transformer`.

SIREN_DOUBLE = "999888777"      # deux établissements, deux marchés
SIREN_LIBELLE = "111222333"     # quatre établissements, libellés divergents
SIREN_EX_AEQUO = "555444333"    # deux libellés à égalité de fréquence
SIREN_ACHETEUR = "777666555"    # deux établissements ACHETEURS

# Identifiant-rebut RÉEL de la fixture, et son montant relevé à la main.
IDENTIFIANT_REBUT_REEL = "00002"
MONTANT_REBUT_REEL = 570_000.00

# Deux établissements d'une même entreprise, sur deux marchés DISTINCTS de la
# fenêtre 12 mois. Montants relevés dans la fixture : 255 552,00 et 31 979,96.
TITULAIRES_DOUBLE = {
    "130001670000122797399_34992200": (
        SIREN_DOUBLE + "00018", "DOUBLE ETABLISSEMENT", "PME"),
    "130020340000192819642_45340000": (
        SIREN_DOUBLE + "00026", "DOUBLE ETABLISSEMENT", "PME"),
}
MONTANT_DOUBLE = 255_552.00 + 31_979.96

# Quatre établissements d'une même entreprise aux libellés DIVERGENTS. Le
# libellé dominant (2 lignes sur 4) est placé de telle sorte qu'AUCUN raccourci
# ne le trouve par hasard : il n'est ni le premier ni le dernier de l'ordre
# alphabétique, ni celui du plus petit SIRET, ni celui du plus grand. Même
# construction pour la catégorie, « GE » se rangeant entre « ETI » et « PME ».
NOM_DOMINANT = "MEDIAN FREQUENT"
CATEGORIE_DOMINANTE = "GE"
TITULAIRES_LIBELLE = {
    "1300268260001120256006110000_15880000": (
        SIREN_LIBELLE + "00011", "ALPHA RARE", "ETI"),
    "157000290000132939878_90460000": (
        SIREN_LIBELLE + "00029", NOM_DOMINANT, CATEGORIE_DOMINANTE),
    "20004133300267202424TCMC09_45421153": (
        SIREN_LIBELLE + "00037", NOM_DOMINANT, CATEGORIE_DOMINANTE),
    "2130033460001126-1157327-2_45223220": (
        SIREN_LIBELLE + "00045", "ZETA RARE", "PME"),
}

# Deux libellés à ÉGALITÉ de fréquence : c'est l'ordre alphabétique qui
# départage. Le plus PETIT SIRET porte volontairement le libellé perdant, pour
# qu'un départage « par le plus petit SIRET » ne passe pas ce test par hasard.
TITULAIRES_EX_AEQUO = {
    "21350093700015202520252001_45420000": (
        SIREN_EX_AEQUO + "00013", "ZZZ EX AEQUO", "PME"),
    "215302472000182026143E11DAF00_45454000": (
        SIREN_EX_AEQUO + "00021", "AAA EX AEQUO", "ETI"),
}

# Identifiants MALFORMÉS construits : 14 caractères dont une lettre, et 13
# chiffres (le SIRET amputé de son zéro de tête, forme courante à la source).
# Montants relevés dans la fixture : 42 735,00 et 170 000,00.
IDENTIFIANTS_MALFORMES = ("0000000000000A", "1234567890123")
TITULAIRES_MALFORMES = {
    "216902890000132025-19_45112711": (
        IDENTIFIANTS_MALFORMES[0], "REBUT A QUATORZE", "PME"),
    "220300016000802020BATLO00032_71630000": (
        IDENTIFIANTS_MALFORMES[1], "REBUT A TREIZE", "PME"),
}
MONTANT_MALFORME_CONSTRUIT = 42_735.00 + 170_000.00

# Côté ACHETEURS : deux établissements d'une même entreprise, plus un
# identifiant malformé. Montants relevés dans la fixture : 223 661,23 et
# 400 000,00 pour les deux premiers.
ACHETEUR_MALFORME = "0000000000000X"
ACHETEURS_CONSTRUITS = {
    "243301223000672024T00057_45421152": SIREN_ACHETEUR + "00014",
    "247600588000472026F00011_18930000": SIREN_ACHETEUR + "00022",
    "2484002850005720212021FCS022_85311300": ACHETEUR_MALFORME,
}
MONTANT_ACHETEUR_DOUBLE = 223_661.23 + 400_000.00


@pytest.fixture(scope="module")
def resultat_entreprises(tmp_path_factory):
    """Transformation d'une copie de la fixture portant les cas construits."""
    chemin = _fixture_modifiee(
        tmp_path_factory.mktemp("entreprises") / "decp_entreprises.parquet",
        titulaires_par_uid={
            **TITULAIRES_DOUBLE, **TITULAIRES_LIBELLE,
            **TITULAIRES_EX_AEQUO, **TITULAIRES_MALFORMES,
        },
        acheteurs_id_par_uid=ACHETEURS_CONSTRUITS,
    )
    duck, _ = ingest_decp.transformer(chemin, DATE_REF)
    yield duck
    duck.close()


def _ligne_titulaires_qualite(duck):
    """La ligne unique de t_titulaires_qualite, en dictionnaire."""
    lignes = duck.execute("SELECT * FROM t_titulaires_qualite").fetchall()
    assert len(lignes) == 1
    return dict(zip([d[0] for d in duck.description], lignes[0]))


def _population_titulaires_du_parquet(duck, chemin):
    """(lignes, marchés, identifiants) titulaires de la fenêtre, relus du parquet.

    Recalculés depuis le parquet BRUT — date initiale = min(dateNotification)
    sur TOUTES les lignes du uid, attributs sur la version courante — pour que
    la vérification ne repasse pas par les tables que le pipeline vient de
    construire. Un compteur de défauts ne se prouve que contre la population
    de départ, pas contre lui-même.
    """
    return duck.execute(
        f"""
        WITH initiale AS (
            SELECT uid, min(dateNotification) AS d
            FROM read_parquet('{chemin}')
            WHERE dateNotification IS NOT NULL
            GROUP BY uid
        ),
        couples AS (
            SELECT DISTINCT l.uid, l.titulaire_id
            FROM read_parquet('{chemin}') l
            JOIN initiale i USING (uid)
            WHERE l.donneesActuelles
              AND l.titulaire_id IS NOT NULL
              AND i.d <= DATE '{DATE_REF.isoformat()}'
              AND i.d >  DATE '{DATE_REF.isoformat()}'
                         - INTERVAL {ingest_decp.MOIS_AGGREGATS} MONTH
        )
        SELECT count(*), count(DISTINCT uid), count(DISTINCT titulaire_id)
        FROM couples
        """
    ).fetchone()


def test_titulaires_qualite_recompose_la_population_de_depart(resultat):
    """Retenus + écartés = la population de départ, en lignes ET en montants.

    C'est l'invariant qui rend la table lisible : un lecteur doit pouvoir
    retrancher les écartés de la population et retomber sur les retenus. La
    population n'est pas reprise des tables du pipeline mais relue du parquet
    brut — additionner deux `count(*) FILTER` écrits séparément ne prouverait
    que leur cohérence mutuelle, jamais qu'ils couvrent tout.
    """
    duck, _ = resultat
    q = _ligne_titulaires_qualite(duck)
    assert q["id"] == 1

    nb_lignes, nb_marches_avec, nb_identifiants = _population_titulaires_du_parquet(
        duck, FIXTURE
    )
    assert q["nb_lignes"] == nb_lignes
    assert q["nb_marches_avec_titulaire"] == nb_marches_avec
    # Les identifiants se partagent aussi en deux : conformes et écartés.
    assert q["nb_sirets"] + q["nb_identifiants_ecartes"] == nb_identifiants

    # La partition des LIGNES recompose la population, sans reste ni doublon.
    assert q["nb_lignes_identifiables"] + q["nb_lignes_ecartees"] == q["nb_lignes"]

    # Celle des MONTANTS recompose le total, à l'euro près. `or 0.0` parce
    # qu'une part vide vaut NULL et non zéro : la somme d'un ensemble vide
    # n'est pas un montant nul, et le pipeline ne l'invente pas.
    total = duck.execute(
        "SELECT sum(montant_part) FROM t_titulaires_lignes"
    ).fetchone()[0]
    assert (q["montant_identifiable"] or 0.0) + (
        q["montant_ecarte"] or 0.0
    ) == pytest.approx(total or 0.0)

    # Le dénominateur est celui de decp_qualite_montants — même fenêtre, même
    # source : deux pages du site ne peuvent pas afficher deux « nombre de
    # marchés » différents pour la même période.
    assert q["nb_marches"] == duck.execute(
        "SELECT nb_marches FROM t_qualite_montants"
    ).fetchone()[0]
    assert q["nb_marches_avec_titulaire"] <= q["nb_marches"]

    # Une entreprise porte au moins un établissement, et le compteur
    # « multi-établissements » n'est non nul que s'il y a plus de SIRET que
    # de SIREN — les deux façons de dire la même chose doivent concorder.
    assert q["nb_sirens"] <= q["nb_sirets"]
    assert (q["nb_sirets"] > q["nb_sirens"]) == (q["nb_sirens_multi_etab"] > 0)


def test_la_recomposition_tient_aussi_avec_des_identifiants_malformes(
    resultat_entreprises,
):
    """Même invariant sur la copie qui porte, elle, plusieurs malformations.

    L'invariant ne vaut que s'il tient là où il y a matière à fuir : sur la
    fixture réelle, un seul identifiant est écarté.
    """
    duck = resultat_entreprises
    q = _ligne_titulaires_qualite(duck)
    assert q["nb_lignes_ecartees"] > 1          # sinon le test ne prouve rien
    assert q["nb_lignes_identifiables"] + q["nb_lignes_ecartees"] == q["nb_lignes"]
    total = duck.execute(
        "SELECT sum(montant_part) FROM t_titulaires_lignes"
    ).fetchone()[0]
    assert (q["montant_identifiable"] or 0.0) + (
        q["montant_ecarte"] or 0.0
    ) == pytest.approx(total or 0.0)


def test_un_identifiant_malforme_est_ecarte_du_classement_et_compte(
    resultat_entreprises,
):
    """Un identifiant non conforme ne classe pas, et ne disparaît pas non plus.

    Doctrine maison : on écarte ET on compte. Vérifier la seule absence
    passerait aussi sur un pipeline qui aurait perdu ces lignes en amont — le
    test exige donc les deux moitiés, la présence dans la population et
    l'absence du classement.
    """
    duck = resultat_entreprises
    q = _ligne_titulaires_qualite(duck)
    rebuts = (IDENTIFIANT_REBUT_REEL,) + IDENTIFIANTS_MALFORMES

    # Trois identifiants non conformes : le « 00002 » réel de la fixture, plus
    # les deux construits (une lettre parmi 14 caractères, et 13 chiffres).
    assert q["nb_identifiants_ecartes"] == len(rebuts)
    assert q["nb_lignes_ecartees"] == len(rebuts)
    assert q["montant_ecarte"] == pytest.approx(
        MONTANT_REBUT_REEL + MONTANT_MALFORME_CONSTRUIT
    )

    # Présents dans la population de départ : rien n'a été filtré en amont.
    marqueurs = ", ".join(f"'{r}'" for r in rebuts)
    assert duck.execute(
        f"SELECT count(*) FROM t_titulaires_lignes "
        f"WHERE titulaire_id IN ({marqueurs})"
    ).fetchone()[0] == len(rebuts)

    # Absents du classement, ni tels quels ni tronqués à neuf caractères :
    # tronquer un rebut ne fabrique pas un SIREN.
    classes = {c for (c,) in duck.execute("SELECT siren FROM t_top_titulaires").fetchall()}
    for rebut in rebuts:
        assert rebut not in classes
        assert rebut[:9] not in classes
    # Et aucune valeur par défaut n'a été glissée à leur place.
    assert all(c is not None and len(c) == 9 and c.isdigit() for c in classes)


def test_deux_etablissements_dun_meme_siren_ne_font_quune_ligne(
    resultat_entreprises,
):
    """Deux établissements, une entreprise : une ligne, deux marchés, montant sommé.

    C'est le défaut corrigé : agrégé par établissement, un groupe à réseau
    local est émietté en autant de lignes qu'il a de SIRET, dont aucune ne
    franchit le seuil d'entrée du top 50.
    """
    duck = resultat_entreprises
    lignes = duck.execute(
        "SELECT nom, categorie, nb_etablissements, nb_marches, montant_total "
        f"FROM t_top_titulaires WHERE siren = '{SIREN_DOUBLE}'"
    ).fetchall()
    assert len(lignes) == 1
    nom, categorie, nb_etab, nb_marches, montant = lignes[0]
    assert nb_etab == 2
    assert nb_marches == 2
    assert montant == pytest.approx(MONTANT_DOUBLE)
    assert nom == "DOUBLE ETABLISSEMENT"
    assert categorie == "PME"

    # Les deux SIRET existent bien séparément dans la population : la fusion
    # est un regroupement, pas la perte de l'un des deux.
    assert duck.execute(
        f"SELECT count(DISTINCT titulaire_id) FROM t_titulaires_lignes "
        f"WHERE siren = '{SIREN_DOUBLE}'"
    ).fetchone()[0] == 2

    # Aucune entreprise n'apparaît deux fois dans le classement.
    total, distincts = duck.execute(
        "SELECT count(*), count(DISTINCT siren) FROM t_top_titulaires"
    ).fetchone()
    assert total == distincts

    # Le compteur de qualité voit les deux entreprises multi-établissements
    # construites (titulaires doubles et libellés divergents), et elles seules.
    q = _ligne_titulaires_qualite(duck)
    assert q["nb_sirens_multi_etab"] == 3        # DOUBLE, LIBELLE, EX_AEQUO
    assert q["nb_sirets"] - q["nb_sirens"] == (2 - 1) + (4 - 1) + (2 - 1)


def test_le_libelle_retenu_est_le_plus_frequent_et_non_un_libelle_quelconque(
    resultat_entreprises,
):
    """Le libellé servi est le DOMINANT, pas un libellé arbitraire du groupe.

    Le cas est bâti pour qu'aucun raccourci ne tombe juste par hasard : le
    libellé attendu n'est ni le premier ni le dernier de l'ordre alphabétique,
    ni celui du plus petit SIRET, ni celui du plus grand. `any_value()`,
    `min()`, `max()`, `arg_min(nom, titulaire_id)` échouent donc tous ici —
    c'est ce qui donne sa valeur au test, et c'est indispensable : sur un
    SIREN à des dizaines d'établissements, un libellé arbitraire peut changer
    d'un passage à l'autre sans qu'aucune donnée ait bougé.
    """
    duck = resultat_entreprises
    nom, categorie, nb_etab = duck.execute(
        "SELECT nom, categorie, nb_etablissements FROM t_top_titulaires "
        f"WHERE siren = '{SIREN_LIBELLE}'"
    ).fetchone()
    assert nb_etab == 4
    assert nom == NOM_DOMINANT
    assert categorie == CATEGORIE_DOMINANTE

    # Les fréquences du groupe, telles que la copie de fixture les porte.
    frequences = dict(duck.execute(
        f"SELECT nom, count(*) FROM t_titulaires_lignes "
        f"WHERE siren = '{SIREN_LIBELLE}' GROUP BY nom"
    ).fetchall())
    assert frequences == {"ALPHA RARE": 1, NOM_DOMINANT: 2, "ZETA RARE": 1}

    # Les quatre raccourcis que le test doit faire échouer rendent tous autre
    # chose que le libellé dominant — vérifié sur les données, pas supposé.
    raccourcis = duck.execute(
        f"""SELECT min(nom), max(nom),
                   arg_min(nom, titulaire_id), arg_max(nom, titulaire_id),
                   min(categorie), max(categorie),
                   arg_min(categorie, titulaire_id),
                   arg_max(categorie, titulaire_id)
            FROM t_titulaires_lignes WHERE siren = '{SIREN_LIBELLE}'"""
    ).fetchone()
    assert all(v not in (NOM_DOMINANT, CATEGORIE_DOMINANTE) for v in raccourcis)


def test_les_libelles_ex_aequo_sont_departages_par_ordre_alphabetique(
    resultat_entreprises,
):
    """À fréquence égale, c'est l'ordre alphabétique qui tranche.

    Sans ce départage, deux libellés à égalité laisseraient le résultat
    indéterminé et le classement cesserait d'être rejouable — le problème que
    le libellé dominant vient précisément régler reviendrait intact sur les
    groupes à deux établissements. Le plus PETIT SIRET porte ici le libellé
    perdant, pour qu'un départage « par le plus petit SIRET » ne passe pas ce
    test par accident.
    """
    duck = resultat_entreprises
    nom, categorie = duck.execute(
        "SELECT nom, categorie FROM t_top_titulaires "
        f"WHERE siren = '{SIREN_EX_AEQUO}'"
    ).fetchone()
    frequences = dict(duck.execute(
        f"SELECT nom, count(*) FROM t_titulaires_lignes "
        f"WHERE siren = '{SIREN_EX_AEQUO}' GROUP BY nom"
    ).fetchall())
    assert set(frequences.values()) == {1}      # égalité stricte, sinon rien à départager
    assert nom == min(frequences) == "AAA EX AEQUO"
    assert categorie == "ETI"
    assert duck.execute(
        f"SELECT arg_min(nom, titulaire_id) FROM t_titulaires_lignes "
        f"WHERE siren = '{SIREN_EX_AEQUO}'"
    ).fetchone()[0] == "ZZZ EX AEQUO"


def test_le_classement_des_acheteurs_suit_la_meme_regle(resultat_entreprises):
    """Acheteurs : même regroupement par entreprise, même filtre de conformité.

    L'effet y est plus faible — la plupart des acheteurs publics n'ont qu'un
    établissement acheteur — mais servir un classement par entreprise d'un
    côté et par établissement de l'autre serait une différence de définition
    invisible à l'écran et inexplicable au lecteur.
    """
    duck = resultat_entreprises
    nom, nb_etab, nb_marches, montant = duck.execute(
        "SELECT nom, nb_etablissements, nb_marches, montant_total "
        f"FROM t_top_acheteurs WHERE siren = '{SIREN_ACHETEUR}'"
    ).fetchone()
    assert nb_etab == 2
    assert nb_marches == 2
    assert montant == pytest.approx(MONTANT_ACHETEUR_DOUBLE)
    assert nom is not None

    # L'acheteur à identifiant malformé est écarté du classement.
    classes = {c for (c,) in duck.execute("SELECT siren FROM t_top_acheteurs").fetchall()}
    assert ACHETEUR_MALFORME not in classes
    assert ACHETEUR_MALFORME[:9] not in classes
    assert all(len(c) == 9 and c.isdigit() for c in classes)
    # ... mais son marché reste compté dans la fenêtre : c'est le classement
    # qui l'écarte, pas le pipeline qui le perd.
    assert duck.execute(
        f"SELECT count(*) FROM recents WHERE acheteur_siret = '{ACHETEUR_MALFORME}'"
    ).fetchone()[0] == 1


def test_les_deux_classements_sont_ordonnes_et_bornes(resultat):
    """Invariants de forme communs aux deux tables, sur la fixture réelle."""
    duck, _ = resultat
    for table, source in (("t_top_acheteurs", "acheteurs_conformes"),
                          ("t_top_titulaires", "titulaires_conformes")):
        lignes = duck.execute(
            f"SELECT rang, siren, nb_etablissements, nb_marches, montant_total "
            f"FROM {table} ORDER BY rang"
        ).fetchall()
        assert [l[0] for l in lignes] == list(range(1, len(lignes) + 1))
        # Une entreprise, une ligne.
        assert len({l[1] for l in lignes}) == len(lignes)
        # Montants décroissants, les montants absents (NULL) en queue.
        montants = [l[4] for l in lignes]
        connus = [m for m in montants if m is not None]
        assert connus == sorted(connus, reverse=True)
        assert montants[: len(connus)] == connus
        for _, _, nb_etab, nb_marches, montant in lignes:
            # Chaque établissement regroupé est entré par au moins un marché.
            assert 1 <= nb_etab <= nb_marches
            # L'écrêtage vaut aussi après regroupement : aucune entreprise ne
            # peut dépasser le plafond multiplié par son nombre de marchés.
            if montant is not None:
                assert montant <= nb_marches * ingest_decp.PLAFOND_ECRETAGE_EUR
        # Le classement couvre toute la population conforme, tronquée à NB_TOP.
        attendu = duck.execute(
            f"SELECT count(DISTINCT siren) FROM {source}"
        ).fetchone()[0]
        assert len(lignes) == min(attendu, ingest_decp.NB_TOP)


def test_charger_ecrit_la_qualite_des_titulaires_et_les_tops_par_entreprise(
    tmp_path, resultat
):
    """Les trois tables traversent SQLite : une ligne de qualité, deux tops."""
    duck, _ = resultat
    conn = db.init_db(chemin=tmp_path / "decp_entreprises.db")
    try:
        for _ in range(2):  # double passage : réécriture, pas accumulation
            comptes = ingest_decp.charger(conn, duck)
            conn.commit()
        assert comptes["decp_titulaires_qualite"] == 1

        lignes = conn.execute("SELECT * FROM decp_titulaires_qualite").fetchall()
        assert len(lignes) == 1
        q = lignes[0]
        assert q["id"] == 1
        # L'invariant survit au transfert par lots vers SQLite.
        assert q["nb_lignes_identifiables"] + q["nb_lignes_ecartees"] == q["nb_lignes"]
        assert q["nb_marches"] == conn.execute(
            "SELECT nb_marches FROM decp_qualite_montants"
        ).fetchone()["nb_marches"]
        # Les montants arrivent en REAL, jamais en Decimal (que sqlite3 refuse
        # de lier), et NULL reste NULL.
        for col in ("montant_identifiable", "montant_ecarte"):
            assert q[col] is None or isinstance(q[col], float)

        # Les deux classements portent bien `siren` et plus du tout `siret`.
        for table in ("decp_top_acheteurs", "decp_top_titulaires"):
            colonnes = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
            assert colonnes == set(ingest_decp._TABLES[table][1])
            assert "siren" in colonnes and "siret" not in colonnes
            assert "nb_etablissements" in colonnes
            cles = [
                r["siren"] for r in conn.execute(f"SELECT siren FROM {table}")
            ]
            assert cles and all(len(c) == 9 and c.isdigit() for c in cles)
    finally:
        conn.close()


def _ligne_acheteurs_qualite(duck):
    """La ligne unique de t_acheteurs_qualite, en dictionnaire."""
    lignes = duck.execute("SELECT * FROM t_acheteurs_qualite").fetchall()
    assert len(lignes) == 1
    return dict(zip([d[0] for d in duck.description], lignes[0]))


def _population_acheteurs_du_parquet(duck, chemin):
    """(marchés avec acheteur, identifiants distincts, max par marché) du parquet.

    Relus du parquet BRUT, comme pour les titulaires : la date du marché est
    min(dateNotification) sur TOUTES ses lignes, l'acheteur se lit sur les
    lignes COURANTES. La troisième valeur sert de garde : le pipeline retient
    un acheteur par marché, ce recompte n'est exact que si aucun marché n'en
    déclare deux.
    """
    borne = DATE_REF.isoformat()
    return duck.execute(
        f"""
        WITH initiale AS (
            SELECT uid, min(dateNotification) AS d
            FROM read_parquet('{chemin}')
            WHERE dateNotification IS NOT NULL
            GROUP BY uid
        ),
        courantes AS (
            SELECT l.uid, l.acheteur_id
            FROM read_parquet('{chemin}') l
            JOIN initiale i USING (uid)
            WHERE l.donneesActuelles
              AND l.acheteur_id IS NOT NULL
              AND i.d <= DATE '{borne}'
              AND i.d >  DATE '{borne}'
                         - INTERVAL {ingest_decp.MOIS_AGGREGATS} MONTH
        )
        SELECT (SELECT count(DISTINCT uid) FROM courantes),
               (SELECT count(DISTINCT acheteur_id) FROM courantes),
               (SELECT coalesce(max(n), 0) FROM (
                    SELECT count(DISTINCT acheteur_id) AS n
                    FROM courantes GROUP BY uid))
        """
    ).fetchone()


def test_acheteurs_qualite_recompose_la_population_de_depart(resultat):
    """Identifiables + écartés = les marchés À ACHETEUR de la fenêtre.

    Le dénominateur de la partition est nb_marches_avec_acheteur, PAS
    nb_marches : les deux se distinguent des marchés sans acheteur renseigné,
    et les confondre ferait passer un défaut de saisie amont pour un
    identifiant que nous aurions écarté. La population est relue du parquet
    brut — additionner deux `count(*) FILTER` ne prouverait que leur cohérence
    mutuelle, jamais qu'ils couvrent tout.
    """
    duck, _ = resultat
    q = _ligne_acheteurs_qualite(duck)
    assert q["id"] == 1

    nb_avec, nb_identifiants, max_par_marche = _population_acheteurs_du_parquet(
        duck, FIXTURE
    )
    # Garde : un marché n'a qu'un acheteur, sinon le recompte ne vaudrait rien.
    assert max_par_marche <= 1
    assert q["nb_marches_avec_acheteur"] == nb_avec
    assert q["nb_sirets"] + q["nb_identifiants_ecartes"] == nb_identifiants

    # La partition des MARCHÉS recompose la population, sans reste ni doublon.
    assert (
        q["nb_marches_identifiables"] + q["nb_marches_ecartes"]
        == q["nb_marches_avec_acheteur"]
    )

    # Celle des MONTANTS recompose le total, à l'euro près. `or 0.0` parce
    # qu'une part vide vaut NULL et non zéro — sur la fixture réelle, aucun
    # acheteur n'est écarté et montant_ecarte est donc NULL, pas 0.
    total = duck.execute(
        "SELECT sum(montant_ecrete) FROM t_acheteurs_marches"
    ).fetchone()[0]
    assert (q["montant_identifiable"] or 0.0) + (
        q["montant_ecarte"] or 0.0
    ) == pytest.approx(total or 0.0)

    # Un seul dénominateur pour la fenêtre, partagé par les trois tables de
    # qualité : elles le lisent au même endroit, elles ne peuvent pas diverger.
    reference = duck.execute(
        "SELECT nb_marches FROM t_qualite_montants"
    ).fetchone()[0]
    assert q["nb_marches"] == reference
    assert duck.execute(
        "SELECT nb_marches FROM t_titulaires_qualite"
    ).fetchone()[0] == reference
    # Tout marché à acheteur est un marché de la fenêtre, jamais l'inverse.
    assert q["nb_marches_avec_acheteur"] <= q["nb_marches"]

    assert q["nb_sirens"] <= q["nb_sirets"]
    assert (q["nb_sirets"] > q["nb_sirens"]) == (q["nb_sirens_multi_etab"] > 0)


def test_un_acheteur_malforme_est_ecarte_du_classement_et_compte(
    resultat_entreprises,
):
    """Côté acheteurs aussi : écarté du classement, ET compté.

    L'invariant est rejoué ici parce que la fixture réelle n'écarte AUCUN
    acheteur — un invariant qui ne tient que là où il n'y a rien à perdre ne
    prouve rien.
    """
    duck = resultat_entreprises
    q = _ligne_acheteurs_qualite(duck)

    # La copie de fixture porte un acheteur à identifiant malformé, et un seul.
    assert q["nb_marches_ecartes"] == 1
    assert q["nb_identifiants_ecartes"] == 1
    assert q["montant_ecarte"] is not None

    # La partition tient là où il y a matière à fuir.
    assert (
        q["nb_marches_identifiables"] + q["nb_marches_ecartes"]
        == q["nb_marches_avec_acheteur"]
    )
    total = duck.execute(
        "SELECT sum(montant_ecrete) FROM t_acheteurs_marches"
    ).fetchone()[0]
    assert (q["montant_identifiable"] or 0.0) + (
        q["montant_ecarte"] or 0.0
    ) == pytest.approx(total or 0.0)

    # Le marché reste dans la population de départ : c'est le classement qui
    # l'écarte, pas le pipeline qui le perd.
    assert duck.execute(
        f"SELECT count(*) FROM t_acheteurs_marches "
        f"WHERE acheteur_siret = '{ACHETEUR_MALFORME}'"
    ).fetchone()[0] == 1
    assert duck.execute(
        f"SELECT count(*) FROM t_acheteurs_marches "
        f"WHERE acheteur_siret = '{ACHETEUR_MALFORME}' AND identifiable"
    ).fetchone()[0] == 0

    # Les deux établissements acheteurs construits sont bien vus comme une
    # seule entreprise à deux établissements.
    assert q["nb_sirens_multi_etab"] >= 1
    assert q["nb_sirets"] - q["nb_sirens"] >= 1


def test_charger_ecrit_la_qualite_des_acheteurs(tmp_path, resultat):
    """La table acheteurs traverse SQLite : une ligne, invariant préservé."""
    duck, _ = resultat
    conn = db.init_db(chemin=tmp_path / "decp_acheteurs.db")
    try:
        for _ in range(2):  # double passage : réécriture, pas accumulation
            comptes = ingest_decp.charger(conn, duck)
            conn.commit()
        assert comptes["decp_acheteurs_qualite"] == 1

        lignes = conn.execute("SELECT * FROM decp_acheteurs_qualite").fetchall()
        assert len(lignes) == 1
        q = lignes[0]
        assert q["id"] == 1
        assert (
            q["nb_marches_identifiables"] + q["nb_marches_ecartes"]
            == q["nb_marches_avec_acheteur"]
        )
        # Les trois tables de qualité affichent le même dénominateur.
        assert q["nb_marches"] == conn.execute(
            "SELECT nb_marches FROM decp_qualite_montants"
        ).fetchone()["nb_marches"]
        assert q["nb_marches"] == conn.execute(
            "SELECT nb_marches FROM decp_titulaires_qualite"
        ).fetchone()["nb_marches"]
        # Montants en REAL, jamais en Decimal (que sqlite3 refuse de lier),
        # et NULL conservé quand la part est vide.
        for col in ("montant_identifiable", "montant_ecarte"):
            assert q[col] is None or isinstance(q[col], float)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
#
# Filet de schéma : la base SERVIE est persistante, celle de la CI est neuve
#
# ---------------------------------------------------------------------------
#
# `CREATE TABLE IF NOT EXISTS` ne modifie pas une table déjà présente. En
# intégration continue la base part de zéro : les tables y naissent au schéma
# courant, et un changement de colonnes ne se voit pas. La base servie, elle,
# survit d'un déploiement à l'autre et garde ses anciennes colonnes — l'INSERT
# y échouerait, et l'ingestion étant tout-ou-rien, le déploiement ENTIER
# tomberait. Ces trois tests rejouent la situation de la production, la seule
# où le défaut existe.

_ANCIEN_SCHEMA_TOPS = """
CREATE TABLE decp_top_acheteurs (
    rang          INTEGER PRIMARY KEY,
    siret         TEXT,
    nom           TEXT,
    nb_marches    INTEGER NOT NULL,
    montant_total REAL
);
CREATE TABLE decp_top_titulaires (
    rang          INTEGER PRIMARY KEY,
    siret         TEXT,
    nom           TEXT,
    categorie     TEXT,
    nb_marches    INTEGER NOT NULL,
    montant_total REAL
);

-- Table de qualité des acheteurs réduite à deux colonnes : elle tient ici la
-- place d'une table CÂBLÉE APRÈS COUP, dont la base servie porterait une
-- forme périmée. Le filet doit la rattraper sans une ligne de code de plus —
-- c'est ce que le test vérifie, au lieu de le supposer.
CREATE TABLE decp_acheteurs_qualite (
    id         INTEGER PRIMARY KEY CHECK (id = 1),
    nb_marches INTEGER NOT NULL
);
"""


def _base_au_schema_ancien(chemin):
    """Base portant l'ANCIEN schéma des deux classements, avec des lignes.

    Les lignes comptent : une table vide ne dirait pas si la migration a
    réécrit le contenu ou seulement les colonnes.
    """
    conn = db.init_db(chemin=chemin)
    conn.executescript(_ANCIEN_SCHEMA_TOPS)
    conn.execute(
        "INSERT INTO decp_top_titulaires "
        "(rang, siret, nom, categorie, nb_marches, montant_total) "
        "VALUES (1, '32933888303058', 'ANCIENNE LIGNE', 'GE', 43, 215000000.0)"
    )
    conn.execute(
        "INSERT INTO decp_top_acheteurs "
        "(rang, siret, nom, nb_marches, montant_total) "
        "VALUES (1, '25580118500018', 'ANCIENNE LIGNE', 1, 100000000.0)"
    )
    conn.execute(
        "INSERT INTO decp_acheteurs_qualite (id, nb_marches) VALUES (1, 999999)"
    )
    conn.commit()
    return conn


def test_charger_migre_une_base_portant_lancien_schema(tmp_path, resultat):
    """Une base persistante aux colonnes obsolètes ressort au schéma courant."""
    duck, _ = resultat
    conn = _base_au_schema_ancien(tmp_path / "decp_ancien.db")
    try:
        avant = {r[1] for r in conn.execute("PRAGMA table_info(decp_top_titulaires)")}
        assert "siret" in avant and "siren" not in avant

        comptes = ingest_decp.charger(conn, duck)
        conn.commit()

        for table in ("decp_top_acheteurs", "decp_top_titulaires"):
            colonnes = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
            assert colonnes == set(ingest_decp._TABLES[table][1])
            assert "siret" not in colonnes
            # Repeuplée, et l'ancienne ligne a disparu avec l'ancien schéma.
            n = conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            assert n == comptes[table]
            assert n > 0
            assert conn.execute(
                f"SELECT count(*) FROM {table} WHERE nom = 'ANCIENNE LIGNE'"
            ).fetchone()[0] == 0

        # La table de qualité des acheteurs, câblée APRÈS le premier jet, est
        # couverte par le MÊME filet sans une ligne de code de plus : sa forme
        # périmée est remplacée et sa ligne réécrite.
        colonnes = {
            r[1] for r in conn.execute("PRAGMA table_info(decp_acheteurs_qualite)")
        }
        assert colonnes == set(ingest_decp._TABLES["decp_acheteurs_qualite"][1])
        assert conn.execute(
            "SELECT nb_marches FROM decp_acheteurs_qualite"
        ).fetchone()[0] != 999_999

        # Rejouable : sur la base désormais conforme, plus rien n'est supprimé.
        assert ingest_decp._reconcilier_schema(conn) == []
        ingest_decp.charger(conn, duck)
        conn.commit()
    finally:
        conn.close()


def test_le_drop_de_migration_repose_les_index_de_la_table(tmp_path, resultat):
    """Le DROP emporte les index ; c'est `_SCHEMA`, rejoué après, qui les repose.

    D'où l'ordre imposé dans `charger` : contrôle, DROP, `_SCHEMA`,
    DELETE/INSERT. Inversé, la base servie perdrait les index de
    `decp_marches` sans qu'aucune erreur ne le signale — les pages qui s'en
    servent ralentiraient en silence.
    """
    duck, _ = resultat
    conn = db.init_db(chemin=tmp_path / "decp_index.db")
    try:
        # `decp_marches` amputée de presque toutes ses colonnes : discordante,
        # donc supprimée — et son index part avec elle.
        conn.executescript(
            "CREATE TABLE decp_marches (uid TEXT PRIMARY KEY, "
            "date_notification TEXT NOT NULL);"
            "CREATE INDEX idx_decp_marches_date ON decp_marches(date_notification);"
        )
        conn.commit()

        ingest_decp.charger(conn, duck)
        conn.commit()

        index = {
            r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index' "
                "AND tbl_name = 'decp_marches'"
            )
        }
        assert {"idx_decp_marches_date", "idx_decp_marches_ach",
                "idx_decp_marches_tit", "idx_decp_marches_dep"} <= index
        assert conn.execute(
            "SELECT count(*) FROM decp_marches"
        ).fetchone()[0] == 41
    finally:
        conn.close()


def test_sans_le_filet_lingestion_casserait_en_production(
    tmp_path, resultat, monkeypatch
):
    """Preuve en sens inverse : sans le filet, l'INSERT échoue sur l'ancienne base.

    C'est exactement ce que la production aurait rencontré, alors que
    l'intégration continue — base neuve à chaque passage — restait verte.
    Le test échoue si le filet devient la seule chose qui masque l'erreur
    sans que le message la nomme.
    """
    duck, _ = resultat
    monkeypatch.setattr(ingest_decp, "_reconcilier_schema", lambda conn: [])
    conn = _base_au_schema_ancien(tmp_path / "decp_sans_filet.db")
    try:
        with pytest.raises(sqlite3.OperationalError, match="siren"):
            ingest_decp.charger(conn, duck)
    finally:
        conn.close()


def test_toutes_les_tables_du_schema_sont_cablees_donc_couvertes_par_le_filet():
    """Aucune table de `_SCHEMA` n'échappe à `_TABLES`, donc au filet de schéma.

    `_reconcilier_schema` ne contrôle que les tables de `_TABLES` : une table
    déclarée dans `_SCHEMA` mais non câblée n'y serait jamais vérifiée et
    rejouerait exactement le défaut que le filet existe pour empêcher — en
    production seulement, jamais en intégration continue. Ce test ferme la
    porte pour les tables À VENIR, pas seulement pour celles d'aujourd'hui :
    c'est la seule façon de ne pas redécouvrir le problème au prochain
    changement de schéma.
    """
    declarees = set(
        re.findall(r"CREATE TABLE IF NOT EXISTS (\w+)", ingest_decp._SCHEMA)
    )
    assert declarees == set(ingest_decp._TABLES)

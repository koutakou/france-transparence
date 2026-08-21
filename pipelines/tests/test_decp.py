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

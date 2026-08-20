"""Tests P11 finances locales (OFGL) : transformations pures sur extraits
RÉELS des exports du 19/08/2026 (fixtures : Hautes-Alpes complet + Marseille +
Fleury-devant-Douaumont, village « mort pour la France » à 0 habitant ; DGF
2026 : Territoire de Belfort complet + Lyon + Paris écrêtée à 0 € ; séries
communales 2018-2025 : Marseille + Gap ; médianes de strate : export agrégé
serveur complet, extraits du 20/08/2026) + intégration réseau
(@pytest.mark.reseau, contrôles de la recherche 06 et pipeline complet sur
base jetable FT_DB_PATH)."""

from __future__ import annotations

import socket
import sqlite3

from pathlib import Path

import pytest

from pipelines import db
from pipelines import ingest_collectivites as p11

FIXTURES = Path(__file__).parent / "fixtures"
COMMUNES = FIXTURES / "ofgl_communes_2025_extrait.csv"
DGF = FIXTURES / "ofgl_dgf_2026_extrait.csv"
SERIES = FIXTURES / "ofgl_communes_series_extrait.csv"
STRATES = FIXTURES / "ofgl_strates_extrait.csv"


def _en_ligne() -> bool:
    try:
        socket.getaddrinfo("data.ofgl.fr", 443)
        return True
    except OSError:
        return False


# ---------------------------------------------------------------------------
# Agrégat départemental (carte de France)
# ---------------------------------------------------------------------------


def test_agregat_departemental_hautes_alpes():
    """Valeurs constatées par la recherche (06 §1, group_by=dep_code) :
    dép. 05 = 221 320 201,17 € de fonctionnement, 145 336 hab., 1 522,82 €/hab."""
    deps = {d[0]: d for d in p11.agreger_departements(COMMUNES)}
    code, nom, fonct, inv, eur_hab, pop, nb, exercice = deps["05"]
    assert nom == "Hautes-Alpes"
    assert fonct == pytest.approx(221_320_201.17)
    assert inv == pytest.approx(188_385_008.54)
    assert pop == 145_336
    assert nb == 161
    assert exercice == 2025
    assert fonct / pop == pytest.approx(1522.82, abs=0.05)  # contrôle recherche
    assert eur_hab == pytest.approx((fonct + inv) / pop, abs=0.01)


def test_agregat_departemental_population_nulle():
    """Fleury-devant-Douaumont (55, 0 habitant) : montants réels conservés,
    €/hab NULL — jamais de division par zéro ni de valeur inventée."""
    deps = {d[0]: d for d in p11.agreger_departements(COMMUNES)}
    _, _, fonct, inv, eur_hab, pop, nb, _ = deps["55"]
    assert (fonct, inv) == (pytest.approx(27_242.44), pytest.approx(2_890.51))
    assert pop == 0
    assert eur_hab is None
    assert nb == 1


def test_aucun_euro_par_habitant_negatif():
    for d in p11.agreger_departements(COMMUNES):
        assert d[4] is None or 0 < d[4] < 10_000


# ---------------------------------------------------------------------------
# Grandes communes (top population, pivot fonctionnement/investissement)
# ---------------------------------------------------------------------------


def test_top_communes_marseille_en_tete():
    """Marseille, requête réelle de la recherche (06 §1) : 1 339 679 971,72 €
    de fonctionnement 2025, 1 516,39 €/hab, 883 466 hab."""
    top = p11.top_communes(COMMUNES, top_n=3)
    assert [t[0] for t in top] == ["13055", "05061", "05023"]  # tri par population
    code, nom, dep, dep_nom, siren, pop, fonct, fonct_hab, inv, inv_hab, exercice = top[0]
    assert (nom, dep, siren) == ("Marseille", "13", "211300553")
    assert pop == 883_466
    assert fonct == pytest.approx(1_339_679_971.72)
    assert fonct_hab == pytest.approx(1516.39, abs=0.01)
    assert inv == pytest.approx(354_862_136.64)
    assert inv_hab == pytest.approx(401.67, abs=0.01)
    assert exercice == 2025


def test_top_communes_exclut_les_communes_sans_population():
    codes = [t[0] for t in p11.top_communes(COMMUNES, top_n=500)]
    assert "55189" not in codes  # ptot = 0 → jamais dans un top « par population »


# ---------------------------------------------------------------------------
# Séries communales 2018-2025 (top 200) et médianes de strate
# ---------------------------------------------------------------------------


def test_series_communes_marseille_2018_2025():
    """Extrait réel du 20/08/2026 : Marseille, 8 exercices × 2 agrégats —
    fonctionnement 2018 = 953 555 238,57 € (1 096,27 €/hab) et 2025 =
    1 339 679 971,72 € (1 516,39 €/hab, la valeur déjà contrôlée par la
    recherche 06 §1). Strate '10' (≥ 100 000 hab), EPCI publié par l'OFGL."""
    ser = p11.series_communes([SERIES], ["13055", "05061"])
    assert len(ser) == 2 * 8 * 2  # 2 communes × 8 exercices × 2 agrégats
    marseille_fonct = [
        l for l in ser if l[0] == "13055" and l[6] == p11.AGREGAT_FONCT
    ]
    assert [l[5] for l in marseille_fonct] == list(range(2018, 2026))
    d2018, d2025 = marseille_fonct[0], marseille_fonct[-1]
    assert d2018[7] == pytest.approx(953_555_238.57)
    assert d2018[8] == pytest.approx(1096.27, abs=0.01)
    assert d2025[7] == pytest.approx(1_339_679_971.72)
    assert d2025[8] == pytest.approx(1516.39, abs=0.01)
    assert (d2025[1], d2025[2], d2025[3]) == ("Marseille", "211300553", "10")
    assert d2025[4] == "Métropole d'Aix-Marseille-Provence"
    assert d2025[9] == 883_466


def test_series_communes_restreintes_au_perimetre_demande():
    """Seules les communes de la liste passée sortent — le périmètre est
    celui du top 200, jamais élargi par un export trop généreux."""
    ser = p11.series_communes([SERIES], ["13055"])
    assert {l[0] for l in ser} == {"13055"}
    assert len(ser) == 8 * 2


def test_medianes_strates_export_agrege_serveur():
    """Export agrégé par l'API OFGL (20/08/2026) : 11 strates × 8 exercices
    × 2 agrégats = 176 lignes ; strate '10' (≥ 100 000 hab), fonctionnement
    2024 : médiane 1 358,92 €/hab sur 43 communes."""
    st = p11.medianes_strates(STRATES)
    assert len(st) == 11 * 8 * 2
    assert {l[0] for l in st} == {str(i) for i in range(11)}
    ligne = next(
        l for l in st if l[0] == "10" and l[1] == 2024 and l[2] == p11.AGREGAT_FONCT
    )
    assert ligne[3] == pytest.approx(1358.92, abs=0.01)
    assert ligne[4] == 43
    for _tranche, exercice, _agregat, mediane, nb in st:
        assert 2018 <= exercice <= 2025
        assert mediane is not None and 0 < mediane < 10_000
        assert nb > 0


# ---------------------------------------------------------------------------
# DGF (dotations-communes, format long variable/valeur)
# ---------------------------------------------------------------------------


def test_pivot_dgf_lyon_et_paris():
    """Lyon 2026 = 56 959 311 € (contrôle recherche 06 §3) ; Paris = 0 €
    (écrêtement réel, pas une donnée manquante)."""
    piv = {r[0]: r for r in p11.pivot_dgf_communes(DGF)}
    assert len(piv) == 104  # 101 communes du Territoire de Belfort + Lyon + Paris + Ajaccio
    lyon = piv["69123"]
    assert lyon[4] == pytest.approx(56_959_311.0)
    assert lyon[5] == 525_314  # Population INSEE
    assert lyon[6] == pytest.approx(108.43, abs=0.01)
    assert lyon[7] == 2026
    paris = piv["75056"]
    assert paris[4] == 0.0
    assert paris[6] == 0.0


def test_agregat_dgf_departemental():
    piv = p11.pivot_dgf_communes(DGF)
    deps = {d[0]: d for d in p11.agreger_dgf_departements(piv)}
    code, nom, dgf, pop, par_hab, nb, exercice = deps["90"]
    assert nb == 101
    assert dgf == pytest.approx(26_544_563.0)
    assert pop == 143_144
    assert par_hab == pytest.approx(dgf / pop, abs=0.01)
    assert exercice == 2026


def test_agregat_dgf_normalise_les_codes_corses():
    """dotations-communes code la Corse « 20A »/« 20B » ; la carte joint sur
    « 2A »/« 2B » (codes INSEE des comptes) — Ajaccio, lignes réelles."""
    deps = {d[0]: d for d in p11.agreger_dgf_departements(p11.pivot_dgf_communes(DGF))}
    assert "20A" not in deps
    assert deps["2A"][2] == pytest.approx(15_212_484.0)  # DGF 2026 d'Ajaccio


def test_communes_dgf_retenues_rangs_top_flop():
    piv = p11.pivot_dgf_communes(DGF)
    lignes = p11.communes_dgf_retenues(piv, seuil_pop=20_000, n=1)
    rangs = {code: rang for code, *_rest, rang in lignes}
    # ≥ 20 000 hab. dans la fixture : Belfort (364,33 €/hab), Ajaccio, Lyon, Paris (0 €).
    assert rangs == {"90010": "top", "2A004": None, "69123": None, "75056": "flop"}
    for ligne in lignes:
        assert ligne[5] is not None and ligne[5] >= 0  # aucun €/hab négatif


# ---------------------------------------------------------------------------
# Chargement SQLite : idempotence, entités
# ---------------------------------------------------------------------------


def test_charger_est_idempotent(tmp_path):
    conn = db.init_db(chemin=tmp_path / "test.db")
    deps = p11.agreger_departements(COMMUNES)
    communes = p11.top_communes(COMMUNES, top_n=3)
    piv = p11.pivot_dgf_communes(DGF)
    dgf_deps = p11.agreger_dgf_departements(piv)
    dgf_grandes = p11.communes_dgf_retenues(piv, seuil_pop=20_000, n=1)
    series_com = p11.series_communes([SERIES], ["13055", "05061"])
    strates = p11.medianes_strates(STRATES)
    # Ligne nationale réelle (group_by joué le 19/08/2026) : DGF communes 2026.
    dgf_nat = [(2026, 12_884_248_752.0, None, None, 34_961)]
    args = (conn, deps, communes, [], [], dgf_nat, dgf_deps, dgf_grandes,
            series_com, strates)

    comptes1 = p11.charger(*args)
    conn.commit()
    comptes2 = p11.charger(*args)  # rejouer ne duplique rien
    conn.commit()
    assert comptes1 == comptes2
    n = conn.execute("SELECT count(*) FROM collectivites_departements").fetchone()[0]
    assert n == len(deps)
    n = conn.execute("SELECT count(*) FROM dotations_dgf").fetchone()[0]
    assert n == 1 + len(dgf_deps) + len(dgf_grandes)
    n = conn.execute("SELECT count(*) FROM collectivites_communes_series").fetchone()[0]
    assert n == len(series_com)
    n = conn.execute("SELECT count(*) FROM collectivites_communes_strates").fetchone()[0]
    assert n == len(strates)
    entite = conn.execute("SELECT * FROM entites WHERE id = 'COLL-COM-13055'").fetchone()
    assert (entite["type"], entite["siren"], entite["departement"]) == (
        "collectivite", "211300553", "13")
    conn.close()


def test_charger_retire_l_ancienne_table_collectivites_communes(tmp_path):
    """Migration du renommage d'août 2026 : une base construite avant porte
    encore `collectivites_communes` (200 lignes sous un nom qui promettait
    les ~34 900 communes de France) — `charger` la retire pour que la base
    ne contienne plus que `collectivites_communes_top200`."""
    conn = db.init_db(chemin=tmp_path / "migration.db")
    conn.execute("CREATE TABLE collectivites_communes (code_insee TEXT PRIMARY KEY)")
    conn.commit()
    p11.charger(conn, [], [], [], [], [], [], [])
    conn.commit()
    tables = {
        l[0]
        for l in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name LIKE 'collectivites_communes%'"
        )
    }
    assert "collectivites_communes" not in tables
    assert {"collectivites_communes_top200", "collectivites_communes_series",
            "collectivites_communes_strates"} <= tables
    conn.close()


# ---------------------------------------------------------------------------
# Intégration réseau
# ---------------------------------------------------------------------------


@pytest.mark.reseau
def test_api_controles_recherche():
    """Les deux contrôles de la recherche 06 rejoués en direct :
    Marseille fonctionnement 2025 et DGF 2026 de Lyon."""
    if not _en_ligne():
        pytest.skip("hors ligne")
    from pipelines.common import session_http

    session = session_http()
    marseille = p11._records(
        session,
        "ofgl-base-communes",
        {
            "where": 'com_code="13055" and year(exer)=2025 '
                     'and agregat="Dépenses de fonctionnement" '
                     'and type_de_budget="Budget principal"',
            "select": "montant,euros_par_habitant,ptot",
            "limit": 5,
        },
    )
    assert len(marseille) == 1
    assert marseille[0]["montant"] == pytest.approx(1_339_679_971.72, rel=1e-6)
    assert marseille[0]["euros_par_habitant"] == pytest.approx(1516.39, abs=0.01)

    lyon = p11._records(
        session,
        "dotations-communes",
        {
            "where": 'code_insee="69123" and year(exercice)=2026 '
                     'and variable="Montant Dotation DGF"',
            "select": "valeur",
            "limit": 5,
        },
    )
    assert len(lyon) == 1
    assert lyon[0]["valeur"] == pytest.approx(56_959_311.0)


@pytest.mark.reseau
def test_pipeline_complet_sur_base_jetable(tmp_path, monkeypatch):
    """Pipeline entier sur base jetable (FT_DB_PATH) : volumes, contrôles."""
    if not _en_ligne():
        pytest.skip("hors ligne")
    chemin = tmp_path / "collectivites.db"
    monkeypatch.setenv("FT_DB_PATH", str(chemin))
    p11.executer()

    conn = sqlite3.connect(chemin)
    n_dep = conn.execute(
        "SELECT count(*) FROM collectivites_departements WHERE exercice = 2025"
    ).fetchone()[0]
    assert n_dep == 101
    n_com = conn.execute("SELECT count(*) FROM collectivites_communes_top200").fetchone()[0]
    assert n_com == p11.TOP_COMMUNES
    n_ser = conn.execute(
        "SELECT count(DISTINCT code_insee) FROM collectivites_communes_series"
    ).fetchone()[0]
    assert n_ser == p11.TOP_COMMUNES
    n_marseille = conn.execute(
        "SELECT count(*) FROM collectivites_communes_series"
        " WHERE code_insee = '13055' AND agregat = ?",
        (p11.AGREGAT_FONCT,),
    ).fetchone()[0]
    assert n_marseille == p11.EXERCICE_COMPTES - p11.SERIE_DEBUT + 1
    n_strates = conn.execute(
        "SELECT count(*) FROM collectivites_communes_strates"
    ).fetchone()[0]
    assert n_strates == 11 * (p11.EXERCICE_COMPTES - p11.SERIE_DEBUT + 1) * len(
        p11.AGREGATS_COMMUNES
    )
    lyon = conn.execute(
        "SELECT dgf_montant FROM dotations_dgf"
        " WHERE niveau = 'commune' AND code = '69123' AND exercice = 2026"
    ).fetchone()
    assert lyon is not None and lyon[0] == pytest.approx(56_959_311.0)
    meta = conn.execute(
        "SELECT date_donnees, lignes FROM meta_sources WHERE source_id = 'S16'"
    ).fetchone()
    assert meta is not None and meta[0] == "2025-12-31" and meta[1] > 0
    conn.close()

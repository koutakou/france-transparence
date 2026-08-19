"""Tests du pipeline P8 lobbying (HATVP AGORA).

La fixture `fixtures/lobbying/` est un sous-ensemble RÉEL des vues séparées
CSV du 19/08/2026 (< 50 Ko) : 5 entités choisies pour couvrir tous les cas —
SUNROCK (id 0, défaut de déclaration sans aucune publication), SKEZI (id 642,
défaut avec publication partielle), MOUVEMENT DES ENTREPRISES DE FRANCE
(id 141, 15 activités 2023→2026), CONVICTIONS' AFFAIRES PUBLIQUES (id 51,
désinscrite), FRANCE INDUSTRIE (id 10, 4 activités dont 2 hors fenêtre 24 mois).
Aucune ligne fabriquée.

Le test réseau (marque `reseau`) joue le pipeline complet contre hatvp.fr :
`pytest -m reseau` pour l'exécuter, `-m "not reseau"` pour l'exclure.
"""

from datetime import date
from pathlib import Path

import pytest

from pipelines import db
from pipelines.ingest_lobbying import (
    TYPES_ALERTES,
    construire,
    ecrire_db,
    executer,
    groupe_institution,
    iso_de_fr,
    parse_borne,
    url_fiche_hatvp,
)

FIXTURE = Path(__file__).parent / "fixtures" / "lobbying"
AUJOURDHUI = date(2026, 8, 19)  # date de constitution de la fixture


# ---------------------------------------------------------------------------
# Helpers purs
# ---------------------------------------------------------------------------


def test_parse_borne():
    # fourchette déclarée : bornes natives
    assert parse_borne("400000", "≥ 400 000 € et < 500 000 €") == 400000.0
    assert parse_borne("500000.0", "≥ 400 000 € et < 500 000 €") == 500000.0
    # non borné ('inf' natif, ex. « ≥ 10 000 000 € ») → None, pas d'infini
    assert parse_borne("inf", "≥ 10 000 000 €") is None
    # rien déclaré : les 0/0.0 de remplissage ne sont pas des montants
    assert parse_borne("0", None) is None
    assert parse_borne("0.0", "") is None


def test_iso_de_fr():
    assert iso_de_fr("16/05/2024 16:21:46") == "2024-05-16"
    assert iso_de_fr("01/04/2024") == "2024-04-01"
    assert iso_de_fr("2024-04-12") == "2024-04-12"
    assert iso_de_fr("") is None
    assert iso_de_fr(None) is None
    assert iso_de_fr("n/a") is None


def test_groupe_institution_et_url():
    assert groupe_institution(
        "Membre du Gouvernement ou membre de cabinet ministériel") == "Gouvernement"
    # variante d'apostrophe typographique (présente dans la donnée réelle)
    assert groupe_institution("Agent de l’État") == "Administration de l'État"
    assert groupe_institution("Catégorie inconnue") == "Autre"
    assert url_fiche_hatvp("497632109") == (
        "https://www.hatvp.fr/fiche-organisation/?organisation=497632109")
    assert url_fiche_hatvp("") is None


# ---------------------------------------------------------------------------
# Parsing de la fixture réelle + écriture
# ---------------------------------------------------------------------------


@pytest.fixture()
def base(tmp_path):
    """Base jetable remplie depuis la fixture réelle."""
    conn = db.init_db(chemin=tmp_path / "lobby.db")
    donnees = construire(FIXTURE, AUJOURDHUI)
    ecrire_db(conn, donnees)
    yield conn, donnees
    conn.close()


def _entite(conn, id_):
    return conn.execute("SELECT * FROM lobby_entites WHERE id = ?", (id_,)).fetchone()


def test_entites_fixture(base):
    conn, donnees = base
    assert conn.execute("SELECT count(*) n FROM lobby_entites").fetchone()["n"] == 5

    sunrock = _entite(conn, "0")
    assert sunrock["denomination"] == "SUNROCK"
    assert sunrock["defaut_declaration"] == 1          # flag natif, liste officielle
    assert sunrock["declaration_incomplete"] == 0      # rien publié du tout
    assert sunrock["budget_libelle"] is None           # rien déclaré → pas de 0 inventé
    assert sunrock["budget_min"] is None
    assert sunrock["url_fiche"].endswith("organisation=497632109")

    skezi = _entite(conn, "642")
    assert skezi["defaut_declaration"] == 1
    assert skezi["declaration_incomplete"] == 1        # publication partielle du 2026-04-08

    medef = _entite(conn, "141")
    assert medef["nb_activites_total"] == 15
    assert medef["nb_activites_12m"] == 8
    assert medef["effectifs"] == 1.0
    # fourchette telle quelle + bornes natives
    assert medef["budget_libelle"] == "≥ 10 000 € et < 25 000 €"
    assert (medef["budget_min"], medef["budget_max"]) == (10000.0, 25000.0)

    convictions = _entite(conn, "51")
    assert convictions["active"] == 0                  # désinscrite (dateCessation)
    assert convictions["date_cessation"] == "2024-04-01"
    assert convictions["ca_libelle"] == "< 100 000 €"
    assert (convictions["ca_min"], convictions["ca_max"]) == (0.0, 100000.0)


def test_activites_detail_24_mois(base):
    conn, _ = base
    n = conn.execute("SELECT count(*) n FROM lobby_activites").fetchone()["n"]
    assert n == 13  # 19 activités réelles, 6 publiées avant le 2024-08-19 exclues
    assert conn.execute(
        "SELECT count(*) n FROM lobby_activites WHERE date_publication < '2024-08-19'"
    ).fetchone()["n"] == 0
    act = conn.execute(
        "SELECT * FROM lobby_activites WHERE activite_id = '2301'").fetchone()
    assert act["entite_id"] == "141"
    assert "Député" in act["institutions"]
    assert act["decisions"] == "Autres décisions publiques"
    assert act["objet"]  # objet réel non vide
    assert (act["periode_debut"], act["periode_fin"]) == ("2024-01-01", "2024-12-31")


def test_agregats(base):
    conn, _ = base
    # séries trimestrielles : historique COMPLET (au-delà de la fenêtre détail)
    tri = {r["trimestre"]: (r["nb_activites"], r["nb_entites"])
           for r in conn.execute("SELECT * FROM lobby_agg_trimestres")}
    assert tri["2020-T4"] == (1, 1)   # activité de 2020 comptée bien qu'hors détail
    assert tri["2026-T1"] == (10, 2)

    top = conn.execute(
        "SELECT * FROM lobby_agg_top_entites ORDER BY rang").fetchall()
    assert (top[0]["entite_id"], top[0]["nb_activites_12m"]) == ("141", 8)
    assert (top[1]["entite_id"], top[1]["nb_activites_12m"]) == ("10", 2)

    bud = conn.execute(
        "SELECT * FROM lobby_agg_budgets WHERE fourchette = '< 10 000 €'").fetchone()
    assert (bud["borne_min"], bud["borne_max"], bud["nb_entites"]) == (0.0, 10000.0, 1)
    # la désinscrite (id 51) n'entre pas dans la répartition des actives :
    # sa fourchette « ≥ 10 000 € et < 25 000 € » ne compte que le MEDEF (141)
    bud2 = conn.execute(
        "SELECT nb_entites n FROM lobby_agg_budgets WHERE fourchette = '≥ 10 000 € et < 25 000 €'"
    ).fetchone()
    assert bud2["n"] == 1

    gouv = conn.execute(
        "SELECT * FROM lobby_agg_institutions WHERE groupe = 'Gouvernement'").fetchone()
    assert gouv["institution"] == "Membre du Gouvernement ou membre de cabinet ministériel"
    assert gouv["nb_activites_total"] == 4
    parlement = conn.execute(
        "SELECT institution FROM lobby_agg_institutions WHERE groupe = 'Parlement (AN + Sénat)'"
    ).fetchone()
    assert parlement is not None

    assert conn.execute(
        "SELECT nb_activites_total n FROM lobby_agg_ministeres WHERE ministere = 'Premier ministre'"
    ).fetchone()["n"] == 3


def test_meta_source(base):
    conn, _ = base
    meta = conn.execute(
        "SELECT * FROM meta_sources WHERE source_id = 'S4'").fetchone()
    assert meta["frequence"] == "quotidienne"
    assert meta["licence"] == "Licence Ouverte Etalab"
    # date de la donnée la plus récente DE LA FIXTURE (jamais la date du fichier)
    assert meta["date_donnees"] == "2026-04-08"
    assert meta["lignes"] == 5


# ---------------------------------------------------------------------------
# Règle d'alerte (flags natifs) + partage de la table alertes
# ---------------------------------------------------------------------------


def test_alertes_defaut_declaration(base):
    conn, _ = base
    defauts = conn.execute(
        "SELECT * FROM alertes WHERE type = 'lobbying_defaut_declaration' ORDER BY id"
    ).fetchall()
    assert len(defauts) == 2  # SUNROCK (id 0) et SKEZI (id 642), flags natifs

    par_id = {a["id"]: a for a in defauts}
    sunrock = par_id["lobbying_defaut_declaration:0"]
    assert sunrock["gravite"] == "haute"
    assert "SUNROCK" in sunrock["titre"]
    assert "aucune information communiquée" in sunrock["detail"]
    assert "2025-01-01" in sunrock["detail"]           # exercice réel concerné
    assert "2016-1691" in sunrock["base_legale"]       # Sapin II
    assert sunrock["source_url"].endswith("organisation=497632109")
    assert sunrock["date_calcul"]

    skezi = par_id["lobbying_defaut_declaration:642"]
    assert "communication partielle" in skezi["detail"]

    agregat = conn.execute(
        "SELECT * FROM alertes WHERE type = 'lobbying_declaration_incomplete'"
    ).fetchall()
    assert len(agregat) == 1
    assert agregat[0]["titre"].startswith("2 représentants d'intérêts")
    assert agregat[0]["gravite"] == "moyenne"
    assert "1 sans aucune publication" in agregat[0]["detail"]
    assert "1 avec communication partielle" in agregat[0]["detail"]


def test_idempotence_et_table_alertes_partagee(base, tmp_path):
    conn, donnees = base
    # une alerte d'un AUTRE pipeline doit survivre à nos passages
    conn.execute(
        "INSERT INTO alertes VALUES ('a1_test:x', 'hatvp_retard', 'haute', 't', "
        "'d', 'r', 'b', 'u', '2026-08-19T00:00:00+00:00')")
    conn.commit()

    ecrire_db(conn, donnees)  # second passage complet

    assert conn.execute("SELECT count(*) n FROM lobby_entites").fetchone()["n"] == 5
    assert conn.execute("SELECT count(*) n FROM lobby_activites").fetchone()["n"] == 13
    n_lobby = conn.execute(
        "SELECT count(*) n FROM alertes WHERE type IN (?, ?)", TYPES_ALERTES
    ).fetchone()["n"]
    assert n_lobby == 3  # 2 défauts + 1 agrégat, pas de doublon
    assert conn.execute(
        "SELECT count(*) n FROM alertes WHERE type = 'hatvp_retard'"
    ).fetchone()["n"] == 1  # intacte : on n'efface que nos types


# ---------------------------------------------------------------------------
# Intégration réelle (réseau)
# ---------------------------------------------------------------------------


@pytest.mark.reseau
def test_integration_reelle(tmp_path):
    """Pipeline complet contre hatvp.fr (zip ~14 Mo, cache 24 h)."""
    chemin = tmp_path / "lobby_reel.db"
    stats = executer(chemin_db=chemin, max_age_heures=24.0)
    assert stats["entites"] > 3000            # ~4 067 constatées le 19/08/2026
    assert stats["activites_total"] > 80000   # ~112 450 constatées
    assert stats["alertes_defaut"] > 100      # ~316 constatées

    conn = db.connexion(chemin)
    try:
        meta = conn.execute(
            "SELECT date_donnees FROM meta_sources WHERE source_id = 'S4'").fetchone()
        assert meta is not None
        annee, mois, jour = meta["date_donnees"].split("-")
        assert 2018 <= int(annee) <= 2100 and 1 <= int(mois) <= 12
        # les fourchettes de budget restent des libellés natifs
        libelles = [r["fourchette"] for r in conn.execute(
            "SELECT fourchette FROM lobby_agg_budgets")]
        assert any("€" in lib for lib in libelles)
    finally:
        conn.close()

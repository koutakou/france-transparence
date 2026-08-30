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
    FRAGMENTS_MINISTERIELS,
    assainir_lignes,
    PORTEFEUILLES_MINISTERIELS,
    TYPES_ALERTES,
    construire,
    ecrire_db,
    executer,
    groupe_institution,
    iso_de_fr,
    parse_borne,
    portefeuille_ministeriel,
    url_fiche_hatvp,
    verifier_fragments,
)

# Vues séparées réelles, si elles ont été extraites par une ingestion
# précédente : c'est sur ELLES que la sonnette de dérive du vocabulaire
# HATVP a un sens (la fixture ne contient que 2 des 8 portefeuilles).
VUES_REELLES = (
    Path(__file__).resolve().parents[2]
    / "data" / "raw" / "lobbying" / "Vues_Separees"
)
CSV_MINISTERES_REEL = VUES_REELLES / "13_ministeres_aai_api.csv"

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
# Recomposition des portefeuilles ministériels (table FERMÉE)
# ---------------------------------------------------------------------------


def test_table_des_portefeuilles_est_bien_formee():
    """La table fermée ne doit contenir ni doublon ni famille dégénérée."""
    for famille in PORTEFEUILLES_MINISTERIELS:
        # un portefeuille éclaté fait au moins deux morceaux
        assert len(famille) >= 2
        # aucun morceau vide ou déjà espacé/ponctué de travers
        for fragment in famille:
            assert fragment == fragment.strip() and fragment
            assert "," not in fragment  # sinon ce n'est pas un fragment
    # un fragment n'appartient qu'à UN portefeuille
    tous = [f for famille in PORTEFEUILLES_MINISTERIELS for f in famille]
    assert len(tous) == len(set(tous)) == len(FRAGMENTS_MINISTERIELS)
    # le libellé recomposé est la simple recollure des morceaux
    for famille in PORTEFEUILLES_MINISTERIELS:
        attendu = ", ".join(famille)
        for fragment in famille:
            assert FRAGMENTS_MINISTERIELS[fragment] == attendu


def test_portefeuille_ministeriel_degrade_proprement():
    assert portefeuille_ministeriel("Environnement") == "Environnement, énergie et mer"
    # l'espace de tête du CSV n'est PAS un discriminant : même résultat
    assert portefeuille_ministeriel(" énergie et mer") == "Environnement, énergie et mer"
    assert (portefeuille_ministeriel("formation professionnelle et dialogue social")
            == "Travail, emploi, formation professionnelle et dialogue social")
    # libellé hors table : rendu BRUT (trimé), jamais une erreur
    assert portefeuille_ministeriel(" Economie et finances") == "Economie et finances"
    assert portefeuille_ministeriel("Logement") == "Logement"
    assert portefeuille_ministeriel("Ministère créé demain") == "Ministère créé demain"


def test_recomposition_dans_lagregat(base):
    """Fragments recomposés, et compteurs en UNION (jamais en somme).

    Dans la fixture, les actions 150, 223 et 227 visent chacune les deux
    fragments « Environnement » et « énergie et mer ». Le portefeuille doit
    peser 3 activités — pas 6.
    """
    conn, _ = base
    lignes = {r["ministere"]: r for r in conn.execute(
        "SELECT * FROM lobby_agg_ministeres")}

    env = lignes["Environnement, énergie et mer"]
    assert env["nb_activites_total"] == 3      # union des deux fragments
    assert env["nb_entites"] == 1
    amenagement = lignes["Aménagement du territoire, ruralité et collectivités territoriales"]
    assert amenagement["nb_activites_total"] == 1

    # aucun fragment ne subsiste comme libellé autonome
    for fragment in FRAGMENTS_MINISTERIELS:
        assert fragment not in lignes

    # les libellés hors table restent bruts, à l'identique
    assert lignes["Economie et finances"]["nb_activites_total"] == 4
    assert "Conseil départemental d'Alsace" in lignes


def test_verifier_fragments_signale_les_disparitions():
    """La sonnette de dérive fonctionne dans les deux sens."""
    # vocabulaire intact (espaces de tête compris, comme dans le CSV)
    tous = [" " + f for f in FRAGMENTS_MINISTERIELS]
    assert verifier_fragments(tous) == []
    # un portefeuille renommé après remaniement : les morceaux disparus
    # doivent ressortir, triés, et non passer inaperçus
    ampute = [f for f in FRAGMENTS_MINISTERIELS if f != "jeunesse et sport"]
    assert verifier_fragments(ampute) == ["jeunesse et sport"]
    assert verifier_fragments([]) == sorted(FRAGMENTS_MINISTERIELS)
    assert verifier_fragments([None, ""]) == sorted(FRAGMENTS_MINISTERIELS)


def test_fragments_absents_remontent_dans_les_stats(base):
    """`construire` expose les fragments introuvables (la fixture en a)."""
    _conn, donnees = base
    absents = donnees["stats"]["fragments_ministeres_absents"]
    # la fixture ne porte que 2 des 8 portefeuilles : les autres manquent
    assert "jeunesse et sport" in absents
    # ceux qu'elle porte ne sont PAS signalés
    assert "Environnement" not in absents
    assert "ruralité et collectivités territoriales" not in absents


@pytest.mark.skipif(
    not CSV_MINISTERES_REEL.exists(),
    reason="vues séparées réelles absentes (data/raw/lobbying) — "
           "lancer le pipeline lobbying pour armer ce contrôle",
)
def test_aucun_fragment_connu_na_disparu_de_la_donnee_reelle():
    """Sonnette de dérive du vocabulaire HATVP, sur la donnée réelle.

    Si un remaniement fait renommer un portefeuille, ses fragments cessent
    d'exister et la table fermée cesse SILENCIEUSEMENT de recomposer : le
    tableau se remettrait à afficher des morceaux. Ce test échoue alors, et
    la table doit être relue à la main (jamais élargie automatiquement).
    """
    import csv

    with open(CSV_MINISTERES_REEL, encoding="utf-8", newline="") as f:
        libelles = [
            ligne["departement_ministeriel"]
            for ligne in csv.DictReader(f, delimiter=";")
        ]
    absents = verifier_fragments(libelles)
    assert absents == [], (
        "fragments de PORTEFEUILLES_MINISTERIELS introuvables dans la donnée "
        f"HATVP : {absents} — le vocabulaire a changé, relire la table fermée"
    )


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
    # la table fermée doit toujours coller au vocabulaire HATVP du jour
    assert stats["fragments_ministeres_absents"] == []

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
        # portefeuilles recomposés : aucun fragment ne subsiste seul
        ministeres = {r["ministere"] for r in conn.execute(
            "SELECT ministere FROM lobby_agg_ministeres")}
        assert not (ministeres & set(FRAGMENTS_MINISTERIELS))
        assert "Environnement, énergie et mer" in ministeres
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Lobbying — hygiène à l'entrée (`assainir_lignes`)
#
# MUTATIONS TUÉES PAR CE BLOC (jouées le 30/08/2026, chacune re-vérifiée en la
# réintroduisant et en exigeant que CE test-là rougisse) :
#   M14  `assainir_lignes` rendue identité
#   M16  compteur `valeurs_assainies` figé à zéro (la 1ʳᵉ version de son test
#        la laissait SURVIVRE — corrigé, cf. le docstring du test)
#   M17  un des huit jeux de lignes oublié dans le passage
#
# CE QUI N'EST PAS UNE MUTATION, ET NE DOIT PAS ÊTRE COMPTÉ COMME TELLE :
#   `test_hygiene_posee_EN_AVAL_des_appariements_de_fragments` est un GARDE
#   DIFFÉRENTIEL, pas un tueur de mutation. Sur cette fixture, remonter
#   l'hygiène en amont des appariements ne changerait rien — les libellés
#   ministériels y sont déjà propres —, donc aucun test ne pourrait le
#   détecter. Le garde vaut pour la donnée réelle, où ils ne le sont pas.
# ---------------------------------------------------------------------------


def test_assainir_lignes_compte_et_preserve_les_non_str():
    """MUTATION TUÉE : `assainir_lignes` rendue identité, et compteur figé.

    Les lignes de ce pipeline sont des tuples POSITIONNELS sortis de
    `fetchall()` : l'hygiène s'applique à toute chaîne, sans liste d'indices —
    une liste d'indices serait un doublon silencieux du schéma, qui se
    périmerait à la première colonne insérée.
    """
    lignes = [
        ("141", "MEDEF\x8cUVRE", None, 42, 3.5, "  Paris  "),
        ("642", "SKEZI", None, 7, None, "Grenoble"),
    ]
    propres, compte = assainir_lignes(lignes)
    assert propres[0] == ("141", "MEDEFŒUVRE", None, 42, 3.5, "Paris")
    assert propres[1] == lignes[1], "une ligne saine doit sortir inchangée"
    assert compte == 2
    # Les non-str traversent à l'identique, y compris None : `ecrire_db` écrit
    # dans des colonnes NOT NULL, et l'ingestion est tout-ou-rien.
    assert propres[0][2] is None and propres[0][3] == 42 and propres[0][4] == 3.5
    assert assainir_lignes([]) == ([], 0)


def test_le_compte_d_hygiene_remonte_reellement_dans_stats(monkeypatch):
    """MUTATION TUÉE : `valeurs_assainies` figé à zéro dans `stats`.

    🛑 CE TEST A DÛ ÊTRE RÉÉCRIT. Sa première version se contentait de
    `stats["valeurs_assainies"] >= 0` : la mutation « compteur figé à zéro » y
    SURVIVAIT, ce qui est exactement le compteur débranché que la règle de la
    PR #100 veut empêcher. Un compteur ne se teste pas par son existence.

    Deux prises, pour ne pas dépendre d'une seule :
    1. la valeur RÉELLE de la fixture, mesurée le 30/08/2026 — la fixture est
       un sous-ensemble réel des vues HATVP du 19/08, et elle porte bien 3
       valeurs à assainir ;
    2. une preuve de chaînage indépendante de la propreté de la fixture : si
       chacun des huit jeux rend 7 de plus, le total doit monter de 56.
    """
    reel = construire(FIXTURE, AUJOURDHUI)["stats"]["valeurs_assainies"]
    assert reel == 3, "3 valeurs à assainir dans la fixture au 30/08/2026"

    from pipelines import ingest_lobbying

    vraie = ingest_lobbying.assainir_lignes

    def majoree(lignes):
        propres, n = vraie(lignes)
        return propres, n + 7

    monkeypatch.setattr(ingest_lobbying, "assainir_lignes", majoree)
    assert construire(FIXTURE, AUJOURDHUI)["stats"]["valeurs_assainies"] == reel + 8 * 7


def test_hygiene_posee_EN_AVAL_des_appariements_de_fragments(monkeypatch):
    """MUTATION TUÉE : passage d'hygiène remonté avant les appariements.

    🛑 `groupe_institution`, `portefeuille_ministeriel` et `verifier_fragments`
    apparient des libellés BRUTS sur la table fermée `FRAGMENTS_MINISTERIELS`,
    par `.strip()` et `.replace("’", "'")`. Assainir en amont d'eux changerait
    ce qu'ils apparient, et `verifier_fragments` signalerait des fragments
    « absents » qui ne le sont pas. Ce test le prouve par différence : neutraliser
    l'hygiène ne doit RIEN changer aux appariements.
    """
    from pipelines import ingest_lobbying

    avec = construire(FIXTURE, AUJOURDHUI)
    monkeypatch.setattr(ingest_lobbying, "assainir_lignes", lambda lignes: (lignes, 0))
    sans = construire(FIXTURE, AUJOURDHUI)

    assert (avec["stats"]["fragments_ministeres_absents"]
            == sans["stats"]["fragments_ministeres_absents"])
    assert {t[0] for t in avec["agg_ministeres"]} == {t[0] for t in sans["agg_ministeres"]}
    assert {t[1] for t in avec["agg_institutions"]} == {t[1] for t in sans["agg_institutions"]}
    # … et l'instrument n'est pas muet : la neutralisation a bien eu lieu.
    assert sans["stats"]["valeurs_assainies"] == 0


def test_les_huit_jeux_de_lignes_passent_par_l_hygiene(monkeypatch):
    """MUTATION TUÉE : un des huit jeux oublié dans le passage.

    `lobby_agg_top_entites` n'est PAS dérivée de `lobby_entites` : c'est une
    requête duckdb séparée sur le CSV brut (`t_act JOIN t_inf`). Nettoyer les
    entités ne la nettoie donc pas — d'où le comptage des appels.
    """
    from pipelines import ingest_lobbying

    vus = []
    vraie = ingest_lobbying.assainir_lignes

    def espion(lignes):
        vus.append(len(lignes))
        return vraie(lignes)

    monkeypatch.setattr(ingest_lobbying, "assainir_lignes", espion)
    donnees = construire(FIXTURE, AUJOURDHUI)
    assert len(vus) == 8, "les huit jeux de lignes doivent être assainis"
    assert sorted(vus) == sorted(
        len(donnees[cle]) for cle in (
            "entites", "activites", "agg_institutions", "agg_ministeres",
            "agg_top", "agg_budgets", "agg_trimestres", "alertes_defaut",
        )
    )


def test_aucun_controle_c1_reparable_dans_les_colonnes_servies(base):
    """Contrôle d'acceptation, FORMULÉ JUSTE : « plus aucun `Cc` de la plage
    cp1252 ATTRIBUÉE », jamais « plus aucun `Cc` » — cinq octets
    (0x81, 0x8D, 0x8F, 0x90, 0x9D) sont irréparables par spécification.
    """
    conn, _ = base
    reparables = {chr(o) for o in range(0x80, 0xA0)} - {
        chr(o) for o in (0x81, 0x8D, 0x8F, 0x90, 0x9D)
    }
    colonnes = (
        ("lobby_entites", ("denomination", "nom_usage", "sigle", "ville")),
        ("lobby_activites", ("objet", "decisions")),
        ("lobby_agg_top_entites", ("denomination",)),
    )
    total = 0
    for table, cols in colonnes:
        for col in cols:
            valeurs = [r[0] for r in conn.execute(
                f"SELECT {col} FROM {table} WHERE {col} IS NOT NULL")]
            total += len(valeurs)
            for v in valeurs:
                assert not (set(v) & reparables), (table, col, repr(v))
    # 🛑 Sans cette garde, le test passerait sur une base vide et ne prouverait
    # rien : c'est le « zéro vide » que ce dépôt refuse. La fixture (5 entités,
    # 19 activités) en rend 38 au 30/08/2026 ; le seuil est calé DESSOUS, pour
    # qu'il signale une fixture vidée sans rougir au premier enrichissement.
    assert total >= 30, f"population trop maigre pour conclure : {total}"

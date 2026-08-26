"""Tests du pipeline P7 (ingest_integrite) : HATVP liste.csv × RNE.

Fixtures : extraits RÉELS des fichiers du 14/08/2026 (HATVP) et du 11/08/2026
(RNE) — voir fixtures/hatvp_extrait.csv et fixtures/rne_*_extrait.csv. Les deux
seules lignes construites (homonyme LEFEVRE, délai non écoulé CONTE) sont
assemblées à partir de lignes réelles (gabarit GUERZA + maires réels du RNE).

La règle A1 étant calée sur des dates réelles de 2026, les tests la jouent avec
`aujourd_hui = date(2026, 8, 19)` (date de l'épreuve réelle), jamais date.today().

Les tests réseau sont marqués `@pytest.mark.reseau` (désélection : -m "not reseau").
"""

import ast
import json
import sqlite3
from collections import Counter
from datetime import date
from pathlib import Path

import pytest

from pipelines import db
from pipelines import ingest_integrite as p7

FIXTURES = Path(__file__).parent / "fixtures"
AUJOURD_HUI = date(2026, 8, 19)


def charger_rne():
    return {
        "deputes": p7.lire_rne(FIXTURES / "rne_deputes_extrait.csv", p7._COLS_BASE),
        "senateurs": p7.lire_rne(FIXTURES / "rne_senateurs_extrait.csv", p7._COLS_BASE),
        "maires": p7.lire_rne(FIXTURES / "rne_maires_extrait.csv",
                              p7._COLS_BASE + ("Date de début de la fonction",)),
        "cd": p7.lire_rne(FIXTURES / "rne_cd_extrait.csv",
                          p7._COLS_BASE + ("Libellé de la fonction",)),
        "cr": p7.lire_rne(FIXTURES / "rne_cr_extrait.csv",
                          p7._COLS_BASE + ("Libellé de la fonction",)),
        "epci": p7.lire_rne(FIXTURES / "rne_epci_extrait.csv",
                            p7._COLS_BASE + ("Libellé de la fonction",)),
    }


@pytest.fixture()
def dossiers():
    return p7.parser_liste_hatvp(FIXTURES / "hatvp_extrait.csv")


@pytest.fixture()
def resultat_a1(dossiers):
    index = p7.construire_index_rne(charger_rne())
    return p7.calculer_a1(dossiers, index, AUJOURD_HUI)


@pytest.fixture()
def conn(tmp_path):
    c = db.init_db(chemin=tmp_path / "test_integrite.db")
    c.executescript(p7.SCHEMA_P7)
    yield c
    c.close()


# ---------------------------------------------------------------------------
# Parsing (fixture réelle)
# ---------------------------------------------------------------------------


def test_parser_liste_hatvp_fixture_reelle(dossiers):
    assert len(dossiers) == 17
    statuts = Counter(d["statut_publication"] for d in dossiers)
    assert statuts["Déclaration non déposée"] == 4      # les 4 cas réels du 14/08/2026
    assert statuts["En cours"] == 8
    assert statuts["Livrée"] == 2
    guerza = [d for d in dossiers if d["nom"] == "GUERZA" and d["type_mandat"] == "commune"][0]
    assert guerza == {
        "civilite": "M.", "prenom": "Abdel-Kader", "nom": "GUERZA",
        "classement": "GUERZA Abdel-Kader9874", "type_mandat": "commune",
        "qualite": "Maire de Dreux", "type_document": "di", "departement": "28",
        "date_publication": "", "date_depot": "", "nom_fichier": "",
        "url_dossier": "/pages_nominatives/guerza-abdel-kader-9874", "open_data": "",
        "statut_publication": "En cours", "id_origine": "", "url_photo": "",
    }


def test_parser_liste_hatvp_refuse_entete_inconnu(tmp_path):
    mauvais = tmp_path / "liste.csv"
    mauvais.write_text("a;b;c\n1;2;3\n", encoding="utf-8")
    with pytest.raises(ValueError, match="en-tête"):
        p7.parser_liste_hatvp(mauvais)


def test_lire_rne_verifie_les_colonnes(tmp_path):
    mauvais = tmp_path / "rne.csv"
    mauvais.write_text("Nom de l'élu;Prénom de l'élu\nX;Y\n", encoding="utf-8")
    with pytest.raises(ValueError, match="colonnes manquantes"):
        p7.lire_rne(mauvais, p7._COLS_BASE)


def test_agreger_hatvp_statuts_types_et_mois(dossiers):
    agregats = p7.agreger_hatvp(dossiers, AUJOURD_HUI)
    par_cat = {}
    for cat, cle, nb in agregats:
        par_cat.setdefault(cat, {})[cle] = nb
    assert par_cat["statut_publication"]["Déclaration non déposée"] == 4
    assert par_cat["type_document"]["di"] == 13
    mois = par_cat["depots_par_mois"]
    assert len(mois) == 24                       # fenêtre complète, mois vides = 0
    assert "2026-08" in mois and "2024-09" in mois
    assert mois["2026-06"] == 1                  # dépôt réel HAMIDA du 2026-06-09
    assert "2022-03" not in mois                 # dépôt MACRON hors fenêtre


# ---------------------------------------------------------------------------
# Règle A1 (cas construits à partir de lignes réelles)
# ---------------------------------------------------------------------------


def test_a1_retard_vrai_maire_et_senatrice(resultat_a1):
    _, retards, stats = resultat_a1
    cles = {(d["nom"], d["type_mandat"], d["type_document"]) for d in retards}
    # GUERZA, maire de Dreux, fonction 2026-03-28 + 60 j < 19/08/2026, di « En cours »
    assert ("GUERZA", "commune", "di") in cles
    # BOURGUIGNON, sénatrice depuis le 01/09/2025 : dia ET dsp « En cours »
    assert ("BOURGUIGNON", "senateur", "dia") in cles
    assert ("BOURGUIGNON", "senateur", "dsp") in cles
    assert stats["retard_presume"] == 3 == len(retards)


def test_a1_epci_toujours_exclus(resultat_a1):
    _, retards, stats = resultat_a1
    assert stats["exclu_epci"] == 2              # CHAARI + dossier epci de GUERZA
    assert all(d["type_mandat"] != "epci" for d in retards)


def test_a1_homonyme_non_tranche_est_une_non_alerte(resultat_a1):
    _, retards, stats = resultat_a1
    # Deux maires réels « LEFEVRE Philippe » dans l'Aisne (02) → non tranché.
    assert stats["homonyme_non_tranche"] == 1
    assert all(d["nom"] != "LEFEVRE" for d in retards)


def test_a1_delai_de_60_jours_non_ecoule(resultat_a1):
    _, retards, stats = resultat_a1
    # CONTE Yoann, fonction du 25/07/2026 : + 60 j non dépassés au 19/08/2026.
    assert stats["delai_non_ecoule"] == 1
    assert all(d["nom"] != "CONTE" for d in retards)


def test_a1_qualite_hors_population_appariee(resultat_a1):
    _, retards, stats = resultat_a1
    # « Adjoint au maire de Montpellier » (KANTÉ) : hors population maires → exclu.
    assert stats["exclu_qualite_hors_population"] == 1
    assert all(d["nom"] != "KANTÉ" for d in retards)


def test_a1_nominatif_reserve_aux_non_deposees(resultat_a1):
    nominatives, retards, _ = resultat_a1
    assert len(nominatives) == 4
    assert {d["statut_publication"] for d in nominatives} == {"Déclaration non déposée"}
    lignes = p7.construire_alertes(nominatives, retards, AUJOURD_HUI,
                                   "2026-08-14", "2026-08-11")
    nd = [l for l in lignes if l[1] == p7.TYPE_ALERTE_NON_DEPOSEE]
    rp = [l for l in lignes if l[1] == p7.TYPE_ALERTE_RETARD]
    assert len(nd) == 4 and len(rp) == 2         # agrégats : commune + senateur
    assert any("FEROUSSIER" in l[3] for l in nd)  # nominatif = constat officiel
    for l in nd:
        assert "constat officiel" in l[3]
    for l in rp:                                  # agrégats : libellé « présumé »…
        assert "présumée" in l[3]
        assert "RNE du 2026-08-11" in l[5]        # date des données, jamais en dur
        # … et JAMAIS nominatifs :
        for nom in ("GUERZA", "BOURGUIGNON"):
            assert nom not in l[3] and nom not in (l[4] or "")
    assert all(l[6] == p7.BASE_LEGALE_A1 for l in lignes)
    ids = [l[0] for l in lignes]
    assert len(ids) == len(set(ids))              # ids déterministes et uniques


def test_ecrire_alertes_preserve_les_autres_pipelines(conn, resultat_a1):
    nominatives, retards, _ = resultat_a1
    conn.execute(
        "INSERT INTO alertes (id, type, gravite, titre, date_calcul)"
        " VALUES ('X1', 'A2_lobbying_defaut', 'haute', 'alerte d''un autre pipeline',"
        " '2026-08-19')")
    lignes = p7.construire_alertes(nominatives, retards, AUJOURD_HUI,
                                   "2026-08-14", "2026-08-11")
    p7.ecrire_alertes(conn, lignes)
    p7.ecrire_alertes(conn, lignes)              # rejouable : pas de doublon
    n_autres = conn.execute(
        "SELECT count(*) AS n FROM alertes WHERE type = 'A2_lobbying_defaut'").fetchone()["n"]
    n_p7 = conn.execute(
        "SELECT count(*) AS n FROM alertes WHERE type IN (?, ?)",
        p7.TYPES_ALERTES_P7).fetchone()["n"]
    assert n_autres == 1                          # l'alerte étrangère survit
    assert n_p7 == len(lignes)


# ---------------------------------------------------------------------------
# elus : upsert prudent, croisement hatvp_flag
# ---------------------------------------------------------------------------


def test_upsert_elus_prudent_et_idempotent(conn):
    rne = charger_rne()
    # Un autre pipeline (P9/AN) a déjà inséré LAHMAR avec uid_an et un mandat AN.
    lahmar = [r for r in rne["deputes"] if r["Nom de l'élu"] == "LAHMAR"][0]
    conn.execute(
        "INSERT INTO elus (id, nom, prenom, date_naissance, uid_an, mandats)"
        " VALUES ('an-PA841729', ?, ?, ?, 'PA841729',"
        " '[{\"source\": \"AN\", \"type\": \"depute\", \"groupe\": \"LFI-NFP\"}]')",
        (lahmar["Nom de l'élu"], lahmar["Prénom de l'élu"], lahmar["Date de naissance"]))
    personnes = p7.preparer_personnes(rne)
    inseres, maj = p7.upsert_elus(conn, personnes)
    assert maj == 1 and inseres == len(personnes) - 1
    ligne = conn.execute("SELECT * FROM elus WHERE id = 'an-PA841729'").fetchone()
    assert ligne["uid_an"] == "PA841729"          # jamais écrasé
    mandats = json.loads(ligne["mandats"])
    assert {m["source"] for m in mandats} == {"AN", "RNE"}   # fusion, pas remplacement
    # Présidents seulement pour cd/cr/epci : FEROUSSIER (VP) et ARMOUGOM absents.
    assert conn.execute("SELECT count(*) AS n FROM elus WHERE nom = 'FEROUSSIER'"
                        ).fetchone()["n"] == 0
    assert conn.execute("SELECT count(*) AS n FROM elus WHERE nom = 'AMRANE'"
                        ).fetchone()["n"] == 1
    # Rejouable : aucun doublon, pas d'empilement des mandats RNE.
    inseres2, _ = p7.upsert_elus(conn, p7.preparer_personnes(rne))
    assert inseres2 == 0
    mandats2 = json.loads(conn.execute(
        "SELECT mandats FROM elus WHERE id = 'an-PA841729'").fetchone()["mandats"])
    assert len(mandats2) == len(mandats)


def test_croiser_hatvp_flag_unique_des_deux_cotes(conn, dossiers):
    p7.upsert_elus(conn, p7.preparer_personnes(charger_rne()))
    n = p7.croiser_hatvp_flag(conn, dossiers)
    assert n >= 1
    guerza = conn.execute(
        "SELECT hatvp_flag, hatvp_url FROM elus WHERE nom = 'GUERZA'").fetchone()
    assert guerza["hatvp_flag"] == 1
    assert guerza["hatvp_url"] == "https://www.hatvp.fr/pages_nominatives/guerza-abdel-kader-9874"
    # Homonymie côté élus (deux LEFEVRE Philippe) → pas de flag.
    for r in conn.execute("SELECT hatvp_flag FROM elus WHERE nom = 'LEFEVRE'"):
        assert r["hatvp_flag"] == 0


# ---------------------------------------------------------------------------
# Conseillers municipaux : agrégats seulement
# ---------------------------------------------------------------------------


def test_agreger_conseillers_municipaux(tmp_path):
    lignes, total = p7.agreger_conseillers_municipaux(
        FIXTURES / "rne_cm_extrait.csv", AUJOURD_HUI)
    assert total == 8
    par_dep = {l[0]: l for l in lignes}
    assert par_dep["01"][2] == 5 and par_dep["28"][2] == 3
    for _, _, nb, f, h, age in lignes:
        assert f + h == nb                       # sexes réels M/F, pas d'inconnu ici
        assert age is None or 18 < age < 100


# ---------------------------------------------------------------------------
# Intégration réseau (désélection : -m "not reseau")
# ---------------------------------------------------------------------------


@pytest.mark.reseau
def test_reseau_liste_csv_hatvp():
    from pipelines.common import session_http, telecharger
    session = session_http()
    chemin = telecharger(p7.URL_HATVP_LISTE, p7.REP_RAW / "liste.csv",
                         max_age_heures=24, session=session)
    dossiers = p7.parser_liste_hatvp(chemin)
    assert len(dossiers) >= 10_000
    statuts = Counter(d["statut_publication"] for d in dossiers)
    assert statuts["En cours"] > 0
    date_lm = p7.date_derniere_modification(session, p7.URL_HATVP_LISTE)
    assert date_lm and len(date_lm) == 10        # Last-Modified réel, ISO


@pytest.mark.reseau
def test_reseau_resolution_rne_data_gouv():
    from pipelines.common import session_http
    ressources = p7.resoudre_ressources_rne(session_http())
    assert set(ressources) == set(p7.RESSOURCES_RNE.values())
    for r in ressources.values():
        assert r["url"].startswith("https://static.data.gouv.fr/")
        assert len(r["last_modified"]) == 10     # re-résolution des URLs horodatées


# ---------------------------------------------------------------------------
# Hygiène de liste.csv (§ M4 de doc/QUALITE-DONNEES.md)
# ---------------------------------------------------------------------------


def _dossier(**surcharges):
    """Ligne HATVP minimale — toutes les colonnes, valeurs vides par défaut."""
    base = {c: "" for c in p7.COLONNES_HATVP}
    base.update(statut_publication="Livrée")
    base.update(surcharges)
    return base


def test_dedoublonner_hatvp_ecarte_les_lignes_strictement_identiques():
    a = _dossier(nom="DUPONT", prenom="Jean", type_document="DI", date_depot="2025-01-02")
    b = dict(a)                                   # doublon strict
    c = _dossier(nom="DUPONT", prenom="Jean", type_document="DSP", date_depot="2025-01-02")
    uniques = p7.dedoublonner_hatvp([a, b, c])
    assert len(uniques) == 2
    # Premier exemplaire gagnant : l'ordre d'origine est préservé, donc
    # l'ingestion est reproductible d'un run à l'autre.
    assert uniques[0] is a and uniques[1] is c


def test_dedoublonner_hatvp_ne_touche_pas_aux_declarations_distinctes():
    """Deux déclarations d'une même personne peuvent partager beaucoup.

    C'est POURQUOI le dédoublonnage est strict (les seize colonnes) et non
    fondé sur une clé métier : ici seule la date de dépôt diffère, et les
    deux lignes sont deux dépôts réels.
    """
    a = _dossier(nom="DUPONT", prenom="Jean", type_document="DI", date_depot="2022-01-02")
    b = _dossier(nom="DUPONT", prenom="Jean", type_document="DI", date_depot="2025-06-30")
    assert len(p7.dedoublonner_hatvp([a, b])) == 2


def test_controler_dates_hatvp_compte_les_impossibilites(caplog):
    auj = date(2026, 8, 20)
    dossiers = [
        _dossier(nom="VIDAL", date_depot="2026-11-27"),                 # dépôt futur
        _dossier(nom="ROUSSET", date_depot="2022-02-18",
                 date_publication="2022-02-17"),                        # publication < dépôt
        _dossier(nom="NASROU", date_depot="2026-08-01",
                 date_publication="2026-08-21"),                        # publication programmée
        _dossier(nom="SAIN", date_depot="2025-01-02",
                 date_publication="2025-02-02"),
    ]
    assert p7.controler_dates_hatvp(dossiers, auj) == {
        "depots_futurs": 1, "publications_futures": 1, "publications_avant_depot": 1,
    }


def test_controler_dates_hatvp_ne_corrige_rien():
    """Aucune date n'est devinée : le contrôle journalise, point."""
    dossiers = [_dossier(nom="VIDAL", date_depot="2026-11-27")]
    avant = [dict(d) for d in dossiers]
    p7.controler_dates_hatvp(dossiers, date(2026, 8, 20))
    assert dossiers == avant


# ---------------------------------------------------------------------------
# Atomicité de l'écriture (SCHEMA_P7 appliqué DANS la transaction)
# ---------------------------------------------------------------------------

TABLES_DROPPEES_P7 = ("hatvp_declarations", "hatvp_agregats", "rne_cm_agregats")


def compteurs_sur_disque(chemin):
    """Compte les lignes depuis une connexion NEUVE, donc ce qui est validé.

    Relire par la connexion de travail ne prouverait rien : elle voit sa propre
    transaction. Le seul témoin utile de « ce qui survit à l'incident » est une
    seconde connexion, et le fichier de test n'en avait aucune avant celle-ci.
    """
    neuve = sqlite3.connect(chemin)
    try:
        return {t: neuve.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
                for t in TABLES_DROPPEES_P7}
    finally:
        neuve.close()


def test_le_schema_se_decoupe_en_dix_instructions():
    """Le découpage rend bien les 10 instructions, dont les 3 `DROP`.

    ⚠️ Cette mesure est celle de CE littéral, pas celle de `SCHEMA_P15` : elle
    n'a pas été recopiée. Les deux assertions du bas figent l'ABSENCE des deux
    pièges qui condamnent un découpage naïf dans l'autre pipeline (des `;` en
    commentaire, des apostrophes impaires). Elles sont là pour que la docstring
    d'`instructions_schema` ne devienne pas fausse en silence : le jour où l'on
    annotera ce schéma, ce test tombera, et il faudra relire cette docstring —
    pas la contourner.
    """
    instructions = p7.instructions_schema()
    debuts = [" ".join(i.split()[:2]) for i in instructions]
    assert len(instructions) == 10
    assert debuts.count("DROP TABLE") == 3
    assert debuts.count("CREATE TABLE") == 4
    assert debuts.count("CREATE INDEX") == 3
    # `alertes` est PARTAGÉE avec ingest_financement ET ingest_lobbying, qui
    # portent chacun leur propre `CREATE TABLE IF NOT EXISTS alertes` et ne
    # suppriment que leurs propres types : aucun DROP ne doit jamais la viser.
    assert not any("alertes" in i for i in instructions if i.startswith("DROP"))
    assert sum(1 for l in p7.SCHEMA_P7.splitlines() if l.strip().startswith("--")) == 0
    assert p7.SCHEMA_P7.count("'") == 0


def test_le_decoupage_ignore_un_point_virgule_en_commentaire():
    """La raison d'être de `complete_statement` plutôt que `split(";")`.

    Le piège n'existe pas dans `SCHEMA_P7` aujourd'hui — c'est mesuré et écrit.
    Ce test éprouve donc le CONTRAT de la fonction, pas le littéral : sans lui,
    un retour au découpage naïf resterait vert, et ne casserait qu'après les
    trois `DROP`, le jour où l'on annoterait le schéma.
    """
    # ⚠️ Le « ; » est en FIN de ligne, et c'est tout l'enjeu : avec un « ; »
    # au MILIEU du commentaire, un découpeur naïf `endswith(";")` rend le même
    # résultat que `complete_statement`, et le test ne discrimine rien. C'est
    # une revue adversariale qui l'a montré, sur ce test-ci, écrit d'abord
    # avec un « ; » médian. La forme ci-dessous est celle que porte
    # réellement `SCHEMA_P15` (« … (un FAIT, affichable) ; »).
    script = "-- attention au point-virgule ;\nCREATE TABLE t (x);\n"
    assert p7.instructions_schema(script) == [script.strip()]
    # Et rien ne se perd au découpage : recollées, les instructions rendent le
    # littéral entier. Sans cela, un découpeur qui en avalerait une resterait
    # vert sur les comptes du test voisin.
    assert "".join("".join(i.split()) for i in p7.instructions_schema()) == \
        "".join(p7.SCHEMA_P7.split())


def test_un_schema_non_termine_leve_avant_toute_ecriture():
    """Une instruction non close échoue bruyamment, elle ne saute pas en silence."""
    with pytest.raises(ValueError, match="pas terminée"):
        p7.instructions_schema("DROP TABLE t;\nCREATE TABLE t (x)")


def test_appliquer_schema_ne_valide_pas(tmp_path):
    """Après le schéma, la transaction est OUVERTE — c'est toute la différence.

    `executescript` la validait : `in_transaction` retombait à False et les
    trois `DROP` étaient sur disque. Ce test est le témoin le plus direct du
    retour en arrière.
    """
    conn = db.init_db(chemin=tmp_path / "t.db")
    try:
        assert not conn.in_transaction
        p7.appliquer_schema(conn)
        assert conn.in_transaction
    finally:
        conn.close()


def test_appliquer_schema_prend_le_verrou_des_le_debut(tmp_path):
    """`BEGIN IMMEDIATE`, pas `BEGIN` — et voici pourquoi c'est testable.

    Les deux premières instructions de `SCHEMA_P7` sont des
    `... IF NOT EXISTS` : dans le cas nominal ce sont des NO-OP. Avec un
    `BEGIN` nu (*deferred*), la transaction ne tiendrait alors AUCUN verrou
    d'écriture, un écrivain concurrent pourrait valider, et la montée
    lecture→écriture du premier `DROP` échouerait « database is locked » en
    0,00 s — sans appeler le busy handler, donc sans rien devoir au
    `timeout=30` de `db.connexion()`. Mesuré dans les deux modes de
    journalisation.

    Le test applique un script réduit aux seuls NO-OP pour observer la fenêtre
    de l'intérieur : après lui, le verrou doit DÉJÀ être tenu.
    """
    conn = db.connexion(tmp_path / "t.db")
    autre = sqlite3.connect(tmp_path / "t.db")
    try:
        p7.appliquer_schema(conn)          # crée `alertes`…
        conn.commit()                      # …et la valide, pour que le NO-OP en soit un
        p7.appliquer_schema(
            conn, "CREATE TABLE IF NOT EXISTS alertes (id TEXT PRIMARY KEY);\n")
        autre.execute("PRAGMA busy_timeout=0")
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            autre.execute("INSERT INTO alertes (id) VALUES ('x')")
            autre.commit()
        conn.rollback()
    finally:
        conn.close()
        autre.close()


def test_appliquer_schema_se_greffe_sur_une_transaction_deja_ouverte(tmp_path):
    """Un `BEGIN` de plus ferait échouer le cycle pour rien.

    Mesuré : un `BEGIN` inconditionnel lève « cannot start a transaction within
    a transaction ». Sur le chemin réel de `main()` le cas ne se présente pas —
    `db.init_db()` valide, puis rien ne touche la base avant l'appel — mais rien
    n'interdit à un futur appelant d'ouvrir la sienne.
    """
    conn = db.init_db(chemin=tmp_path / "t.db")
    try:
        conn.execute("CREATE TABLE t_temoin (x)")
        conn.execute("INSERT INTO t_temoin VALUES (1)")
        assert conn.in_transaction
        p7.appliquer_schema(conn)
        assert conn.execute("SELECT count(*) FROM hatvp_declarations").fetchone()[0] == 0
    finally:
        conn.close()


def test_appliquer_schema_cree_reellement_les_dix_objets(tmp_path):
    """Le schéma est APPLIQUÉ, pas seulement découpé.

    Le test voisin éprouve le découpeur ; celui-ci éprouve l'exécution. Sans
    lui, une boucle qui sauterait des instructions — `instructions_schema()[2:]`
    suffit, et fait disparaître la table PARTAGÉE `alertes` — laisserait toute
    la suite verte. C'est une revue adversariale qui a trouvé ce trou.
    """
    conn = db.init_db(chemin=tmp_path / "t.db")
    try:
        p7.appliquer_schema(conn)
        objets = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table', 'index')")}
        assert {"alertes", "hatvp_declarations", "hatvp_agregats",
                "rne_cm_agregats"} <= objets
        assert {"idx_alertes_type", "idx_hatvp_decl_statut",
                "idx_hatvp_decl_nom"} <= objets
    finally:
        conn.close()


def test_un_echec_apres_le_drop_laisse_la_base_intacte(tmp_path, dossiers):
    """C'EST LE TEST QUI TIENT LA PROMESSE, et il appelle le VRAI `ecrire()`.

    Il n'aurait pas pu passer avant : le cycle commençait par
    `conn.executescript(SCHEMA_P7)`, qui valide implicitement, si bien que les
    trois `DROP TABLE` étaient sur disque avant le premier `INSERT`. Un échec
    plus loin laissait `hatvp_declarations`, `hatvp_agregats` et
    `rne_cm_agregats` existantes et VIDES — le `rollback()` du bloc `except`
    n'annulant que les insertions. Rejoué le 26/08/2026 sur une COPIE de la
    base servie : 13 277 / 37 / 104 lignes devenaient 0 / 0 / 0.

    ⚠️ CE TEST A ÉTÉ RÉÉCRIT APRÈS DEUX REVUES ADVERSARIALES. Sa première
    version rejouait les écritures par une réplique de `main()` écrite à la
    main dans ce fichier : elle prouvait que SQLite fait du DDL transactionnel
    — ce que personne ne contestait — et PAS que le cycle P7 est atomique. Les
    deux revues ont trouvé la même faille : un `conn.commit()` d'UNE ligne
    ajouté dans `main()` juste après le schéma restaurait intégralement le
    défaut, tests verts. C'est pour ce test-ci que `ecrire()` a été extraite de
    `main()`. Ne pas revenir à une réplique.

    Le déclencheur n'est pas théorique : `agreger_conseillers_municipaux` est
    appelée APRÈS le schéma et lève sur un CSV RNE dont les colonnes ont
    dérivé. C'est cette levée-là que le test provoque, dans la vraie fonction.
    """
    chemin = tmp_path / "test_integrite.db"
    conn = db.init_db(chemin=chemin)
    rne = charger_rne()
    reels = {"cm": FIXTURES / "rne_cm_extrait.csv"}
    try:
        # --- cycle précédent, réussi -----------------------------------
        p7.ecrire(conn, dossiers, rne, reels, AUJOURD_HUI, "2026-08-14", "2026-08-11")
        conn.commit()
        avant = compteurs_sur_disque(chemin)
        assert all(c > 0 for c in avant.values()), avant

        # --- cycle suivant, qui échoue APRÈS le schéma -----------------
        derive = tmp_path / "rne_cm_derive.csv"
        derive.write_text("Code du departement;Nom\n01;Ain\n", encoding="utf-8")
        with pytest.raises(ValueError, match="colonnes attendues absentes"):
            p7.ecrire(conn, dossiers, rne, {"cm": derive},
                      AUJOURD_HUI, "2026-08-14", "2026-08-11")
        conn.rollback()

        assert compteurs_sur_disque(chemin) == avant
        # Les index reviennent AVEC les tables : une base entière mais
        # désindexée passerait sinon, et rien ne le dirait.
        neuve = sqlite3.connect(chemin)
        try:
            index = {r[0] for r in neuve.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index'"
                " AND name LIKE 'idx_hatvp%'")}
        finally:
            neuve.close()
        assert index == {"idx_hatvp_decl_statut", "idx_hatvp_decl_nom"}
    finally:
        conn.close()


def test_ecrire_ne_valide_pas_la_transaction(tmp_path, dossiers):
    """`ecrire()` laisse la transaction OUVERTE : c'est son contrat.

    Un `conn.commit()` glissé n'importe où dans `ecrire()` — la mutation d'une
    ligne que les deux revues ont trouvée — referme la transaction et rend le
    `DROP` irréversible. Ce test le voit tout de suite, là où l'inspection de
    la source ne voyait que le mot `executescript`.
    """
    conn = db.init_db(chemin=tmp_path / "t.db")
    try:
        p7.ecrire(conn, dossiers, charger_rne(),
                  {"cm": FIXTURES / "rne_cm_extrait.csv"},
                  AUJOURD_HUI, "2026-08-14", "2026-08-11")
        assert conn.in_transaction
    finally:
        conn.close()


def test_le_module_n_appelle_plus_jamais_executescript():
    """Ceinture : dans CE module, aucun `executescript` n'est légitime.

    ⚠️ CE TEST NE SUFFIT PAS, ET SA PREMIÈRE VERSION PRÉTENDAIT LE CONTRAIRE.
    Elle affirmait garder « le seul endroit où la régression peut revenir » :
    c'était faux, et les deux revues adversariales l'ont montré de la même
    façon — un `conn.commit()`, ou un `db.init_db(conn)` (qui valide dans
    `db.py`, hors de ce module, donc invisible à l'AST), produit exactement le
    même effet que `executescript` et passait ce contrôle sans broncher. Ce
    n'était pas un garde-fou de site d'appel, c'était un garde-fou d'un MOT.

    Ce qui tient réellement la promesse, c'est
    `test_un_echec_apres_le_drop_laisse_la_base_intacte`, qui appelle la vraie
    `ecrire()`, et `test_ecrire_ne_valide_pas_la_transaction`. Ce test-ci ne
    garde plus qu'une chose, et c'est écrit sans l'exagérer : le mot
    `executescript` ne revient pas dans le module.
    """
    arbre = ast.parse(Path(p7.__file__).read_text(encoding="utf-8"))
    appels = [f"l.{n.lineno}" for n in ast.walk(arbre)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
              and n.func.attr == "executescript"]
    assert appels == [], appels
    # Et le remplaçant est bien appelé, sinon le schéma ne serait plus posé
    # du tout et le contrôle ci-dessus resterait vert sur un module cassé.
    appliques = [n.lineno for n in ast.walk(arbre)
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                 and n.func.id == "appliquer_schema"]
    assert len(appliques) == 1, appliques

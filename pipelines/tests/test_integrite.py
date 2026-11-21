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
from pipelines import ingest_hatvp_declarations as p15
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
    assert stats["delai_ecoule"] == 3 == len(retards)


def test_a1_epci_toujours_exclus(resultat_a1):
    _, retards, stats = resultat_a1
    assert stats["exclu_epci"] == 2              # CHAARI + dossier epci de GUERZA
    assert all(d["type_mandat"] != "epci" for d in retards)


def test_a1_homonyme_non_tranche_est_une_non_alerte(resultat_a1):
    _, retards, stats = resultat_a1
    # Deux maires réels « LEFEVRE Philippe » dans l'Aisne (02) → non tranché.
    assert stats["homonyme_non_tranche"] == 1
    assert all(d["nom"] != "LEFEVRE" for d in retards)


def test_a1_delai_de_2_mois_non_ecoule(resultat_a1):
    _, retards, stats = resultat_a1
    # CONTE Yoann, fonction du 25/07/2026 : 2 mois non écoulés au 19/08/2026.
    assert stats["delai_non_ecoule"] == 1
    assert all(d["nom"] != "CONTE" for d in retards)


@pytest.mark.parametrize(("lecture", "ecoule"), [
    (date(2026, 8, 30), False),   # 60 jours pile : l'ancienne règle comptait dès le 31/08
    (date(2026, 8, 31), False),
    (date(2026, 9, 1), False),    # échéance légale, jour compris
    (date(2026, 9, 2), True),
])
def test_a1_delai_legal_en_mois_calendaires(lecture, ecoule):
    """Audit du 20/11/2026, C3 : entrée en fonction le 01/07, le dépôt est dû
    « dans les 2 mois », soit le 01/09. Avant, `+ 60 jours` comptait le
    dossier dès le 31/08."""
    assert p7.delai_legal_ecoule(date(2026, 7, 1), lecture) is ecoule


def test_a1_delai_legal_fin_de_mois_et_fevrier():
    # 31/12 + 2 mois = dernier jour de février (59 jours, 60 en année bissextile).
    assert not p7.delai_legal_ecoule(date(2026, 12, 31), date(2027, 2, 28))
    assert p7.delai_legal_ecoule(date(2026, 12, 31), date(2027, 3, 1))
    assert not p7.delai_legal_ecoule(date(2027, 12, 31), date(2028, 2, 29))


def test_a1_borne_reelle_conte(dossiers):
    """La même borne, sur la ligne de la fixture : CONTE, fonction du 25/07/2026."""
    index = p7.construire_index_rne(charger_rne())
    _, avant, _ = p7.calculer_a1(dossiers, index, date(2026, 9, 25))
    _, apres, _ = p7.calculer_a1(dossiers, index, date(2026, 9, 26))
    assert all(d["nom"] != "CONTE" for d in avant)
    assert any(d["nom"] == "CONTE" for d in apres)


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
    ec = [l for l in lignes if l[1] == p7.TYPE_ALERTE_EN_COURS]
    assert len(nd) == 4
    # GUERZA (commune) et BOURGUIGNON (senateur) : 1 personne chacun, 2 une fois
    # regroupés. Sous le seuil de 3 personnes, aucun agrégat n'est publié.
    assert ec == []
    assert any("FEROUSSIER" in l[3] for l in nd)  # nominatif = constat officiel
    for l in nd:
        assert "constat officiel" in l[3]
    assert all(l[6] == p7.BASE_LEGALE_A1 for l in lignes)
    # date_fait = date du fichier HATVP lu, jamais l'instant du cycle
    assert all(l[9] == "2026-08-14" for l in lignes)
    ids = [l[0] for l in lignes]
    assert len(ids) == len(set(ids))              # ids déterministes et uniques


def _dossier_en_cours(classement, type_mandat, type_document="di"):
    """Dossier « En cours » au gabarit de la ligne réelle GUERZA."""
    return {"classement": classement, "type_mandat": type_mandat,
            "type_document": type_document, "nom": classement.upper(),
            "prenom": "X", "statut_publication": "En cours"}


def test_a1_aucun_agregat_sous_3_personnes():
    """Audit du 20/11/2026, C3 : « 1 personne(s) — mandat depute » se lisait
    nominativement dans liste.csv. Un type sous 3 personnes rejoint « autres
    mandats », publié seulement s'il atteint lui-même 3 personnes."""
    en_cours = (
        [_dossier_en_cours(f"maire{i}", "commune") for i in range(4)]
        + [_dossier_en_cours("depute0", "depute", "dsp"),
           _dossier_en_cours("depute0", "depute", "di")]   # 2 dossiers, 1 personne
    )
    lignes = p7.construire_alertes([], en_cours, AUJOURD_HUI, "2026-08-14", "2026-08-11")
    assert [l[0] for l in lignes] == ["A1-EC-commune"]
    assert "4 déclarations" in lignes[0][3] and "pour 4 personnes" in lignes[0][4]
    assert not any("depute" in (l[3] + l[4]) for l in lignes)
    # Deux autres personnes sous le seuil chacune : le regroupement atteint 3.
    en_cours += [_dossier_en_cours("senateur0", "senateur"),
                 _dossier_en_cours("pcd0", "departement")]
    lignes = p7.construire_alertes([], en_cours, AUJOURD_HUI, "2026-08-14", "2026-08-11")
    assert [l[0] for l in lignes] == ["A1-EC-commune", "A1-EC-autres"]
    autres = lignes[1]
    assert "autres mandats" in autres[3] and "pour 3 personnes" in autres[4]
    assert "« depute »" not in autres[3] + autres[4]


def test_a1_textes_sans_retard_ni_non_depose():
    """Décision du 20/11/2026 : le mot « retard » est retiré, et « En cours »
    n'est plus présenté comme une déclaration non déposée."""
    en_cours = [_dossier_en_cours(f"maire{i}", "commune") for i in range(3)]
    (ligne,) = p7.construire_alertes([], en_cours, AUJOURD_HUI, "2026-08-14", "2026-08-11")
    texte = " ".join(str(v) for v in ligne[2:6]).lower()
    assert "retard" not in texte and "présum" not in texte
    assert "non déposée" not in texte
    assert "60 jours" not in texte and "2 mois" in texte
    assert "RNE du 2026-08-11" in ligne[5]       # date des données, jamais en dur
    assert ligne[2] == "info"
    assert ";" not in ligne[3] + ligne[4]


# ---------------------------------------------------------------------------
# Garde-fou n° 7 : RNE antérieur au dernier renouvellement d'une chambre
#
# Constat du 15/10/2026 : alerte publique « 216 déclaration(s) HATVP
# présumée(s) en retard — mandat « senateur » ». Le RNE ingéré (millésime
# d'août) date les sénateurs réélus le 27/09/2026 de leur mandat PRÉCÉDENT
# (2020-10-01) ; leurs dia/dsp « En cours » relèvent du mandat ouvert le
# 01/10/2026, dont l'échéance n'est pas échue.
# ---------------------------------------------------------------------------


def _chambre(conn, table, debuts):
    """Table de chambre minimale, telle que P9 l'écrit (colonnes lues ici)."""
    cle = "uid_an" if table == "deputes" else "matricule"
    conn.execute(f"CREATE TABLE {table} ({cle} TEXT PRIMARY KEY,"
                 " date_debut_mandat TEXT)")
    conn.executemany(f"INSERT INTO {table} VALUES (?, ?)",
                     [(f"X{i}", d) for i, d in enumerate(debuts)])


def test_a1_pas_de_retard_senateur_quand_le_rne_precede_le_renouvellement(
        conn, dossiers):
    # Sénat du 15/10/2026 en proportions : moitié entrée le 01/10/2026,
    # moitié en 2023, un remplaçant isolé. RNE de la fixture : 2025-09-01.
    _chambre(conn, "senateurs", ["2026-10-01"] * 4 + ["2023-10-02"] * 4
             + ["2026-04-13"])
    _chambre(conn, "deputes", ["2024-07-07"] * 3)
    perimes = p7.types_rne_anterieurs(conn, charger_rne())
    assert perimes == {"senateur": ("2026-10-01", "2025-09-01")}
    _, retards, stats = p7.calculer_a1(dossiers, p7.construire_index_rne(charger_rne()),
                                       AUJOURD_HUI, frozenset(perimes))
    assert not [d for d in retards if d["type_mandat"] == "senateur"]
    assert stats["rne_anterieur_au_renouvellement"] == 2   # dia + dsp BOURGUIGNON
    assert ("GUERZA", "commune", "di") in {
        (d["nom"], d["type_mandat"], d["type_document"]) for d in retards}


def test_a1_retard_senateur_maintenu_quand_le_rne_suit_le_renouvellement(
        conn, dossiers):
    """Contre-épreuve : renouvellement de 2023, RNE de 2025 — l'alerte reste.
    Un remplaçant isolé (une voix sur neuf) ne fait pas un renouvellement."""
    _chambre(conn, "senateurs", ["2023-10-02"] * 8 + ["2026-04-13"])
    _chambre(conn, "deputes", ["2024-07-07"] * 3)
    assert p7.types_rne_anterieurs(conn, charger_rne()) == {}


def test_a1_chambre_non_verifiable_n_ecarte_rien(conn, caplog):
    """Sans table de P9, rien n'est prouvé : aucune chambre n'est écartée,
    et le journal le dit."""
    with caplog.at_level("INFO"):
        assert p7.types_rne_anterieurs(conn, charger_rne()) == {}
    assert any("non vérifiable" in m and "senateur" in m for m in caplog.messages)


def _seuil_un(monkeypatch):
    """Agrégats publiés dès 1 personne : la fixture n'a que deux personnes
    « En cours », sous le seuil réel de 3. Sans cela, `ecrire()` ne
    publierait rien dans aucun cas et le test ne prouverait rien."""
    reel = p7.regrouper_sous_seuil
    monkeypatch.setattr(p7, "regrouper_sous_seuil",
                        lambda par_mandat, seuil=1: reel(par_mandat, 1))


def _alertes_en_cours(conn):
    return {r[0]: r[1] for r in conn.execute(
        "SELECT id, titre FROM alertes WHERE type = ?", (p7.TYPE_ALERTE_EN_COURS,))}


def test_a1_garde_fou_branche_dans_ecrire(tmp_path, dossiers, monkeypatch):
    """Le vrai `ecrire()` : les dossiers de sénateurs ne sont plus comptés
    quand la table `senateurs` montre un renouvellement postérieur au RNE.
    Preuve par les alertes écrites, avec sa contre-épreuve : sans
    renouvellement récent, la même base publie l'agrégat des sénateurs."""
    _seuil_un(monkeypatch)
    rne_cm = {"cm": FIXTURES / "rne_cm_extrait.csv"}

    conn = db.init_db(chemin=tmp_path / "garde.db")
    _chambre(conn, "senateurs", ["2026-10-01"] * 5 + ["2023-10-02"] * 4)
    _chambre(conn, "deputes", ["2024-07-07"] * 3)
    conn.commit()
    p7.ecrire(conn, dossiers, charger_rne(), rne_cm,
              AUJOURD_HUI, "2026-08-14", "2026-08-11")
    avec_garde = _alertes_en_cours(conn)
    conn.close()

    conn = db.init_db(chemin=tmp_path / "contre.db")
    _chambre(conn, "senateurs", ["2023-10-02"] * 9)
    _chambre(conn, "deputes", ["2024-07-07"] * 3)
    conn.commit()
    p7.ecrire(conn, dossiers, charger_rne(), rne_cm,
              AUJOURD_HUI, "2026-08-14", "2026-08-11")
    sans_garde = _alertes_en_cours(conn)
    conn.close()

    assert set(avec_garde) == {"A1-EC-commune"}          # GUERZA seul
    assert set(sans_garde) == {"A1-EC-commune", "A1-EC-senateur"}
    assert sans_garde["A1-EC-senateur"].startswith("2 déclarations")  # dia + dsp


def test_a1_delai_juge_a_la_date_du_fichier_hatvp(tmp_path, dossiers, monkeypatch):
    """Revue du 21/11/2026 : entrée en fonction le 15/09, fichier HATVP du
    14/11, cycle du 20/11. L'échéance du 15/11 n'est pas passée à la date du
    fichier : le dossier n'est pas compté, même si le cycle tourne après."""
    _seuil_un(monkeypatch)
    rne = charger_rne()
    (conte,) = [r for r in rne["maires"] if r["Nom de l'élu"] == "CONTE"]
    conte["Date de début de la fonction"] = "2026-09-15"
    rne_cm = {"cm": FIXTURES / "rne_cm_extrait.csv"}

    conn = db.init_db(chemin=tmp_path / "t.db")
    p7.ecrire(conn, dossiers, rne, rne_cm, date(2026, 11, 20), "2026-11-14", "2026-11-01")
    titre = _alertes_en_cours(conn)["A1-EC-commune"]
    assert titre.startswith("1 déclarations"), titre    # GUERZA seul, pas CONTE
    conn.rollback()
    # Contre-épreuve : un fichier du 16/11 dépasse l'échéance, CONTE compte.
    p7.ecrire(conn, dossiers, rne, rne_cm, date(2026, 11, 20), "2026-11-16", "2026-11-01")
    titre = _alertes_en_cours(conn)["A1-EC-commune"]
    assert titre.startswith("2 déclarations"), titre
    conn.close()


def test_ecrire_alertes_purge_l_ancien_type_retard(conn):
    """L'ancien type « A1_hatvp_retard_presume » ne survit pas au cycle."""
    conn.execute(
        "INSERT INTO alertes (id, type, gravite, titre, date_calcul) VALUES"
        " ('A1-RP-depute', 'A1_hatvp_retard_presume', 'moyenne',"
        " '1 déclaration(s) HATVP présumée(s) en retard', '2026-11-20')")
    p7.ecrire_alertes(conn, [])
    assert conn.execute("SELECT COUNT(*) FROM alertes").fetchone()[0] == 0
    assert "date_fait" in {r[1] for r in conn.execute("PRAGMA table_info(alertes)")}


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


def test_ecrire_alertes_garde_la_date_de_detection(conn, resultat_a1):
    """`date_fait` suit le fichier HATVP lu (il change), `date_detection` reste
    celle du premier cycle qui a vu l'id : elle date le flux Atom."""
    nominatives, retards, _ = resultat_a1
    lignes = p7.construire_alertes(nominatives, retards, AUJOURD_HUI,
                                   "2026-08-14", "2026-08-11")
    p7.ecrire_alertes(conn, lignes, date(2026, 8, 15))
    premier = {r["id"]: r["date_detection"] for r in conn.execute(
        "SELECT id, date_detection FROM alertes")}
    assert premier and set(premier.values()) == {"2026-08-15"}
    # Cycle suivant, nouveau fichier HATVP : mêmes id, date_fait déplacée.
    lignes2 = p7.construire_alertes(nominatives, retards, AUJOURD_HUI,
                                    "2026-08-21", "2026-08-11")
    p7.ecrire_alertes(conn, lignes2, date(2026, 8, 22))
    apres = {r["id"]: (r["date_detection"], r["date_fait"]) for r in conn.execute(
        "SELECT id, date_detection, date_fait FROM alertes")}
    assert set(apres) == set(premier)             # identifiants stables
    assert all(v == ("2026-08-15", "2026-08-21") for v in apres.values())


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
    inseres, maj, rattrapes = p7.upsert_elus(conn, personnes)
    assert maj == 1 and inseres == len(personnes) - 1 and rattrapes == 0
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
    inseres2, _, rattrapes2 = p7.upsert_elus(conn, p7.preparer_personnes(rne))
    assert inseres2 == 0 and rattrapes2 == 0
    mandats2 = json.loads(conn.execute(
        "SELECT mandats FROM elus WHERE id = 'an-PA841729'").fetchone()["mandats"])
    assert len(mandats2) == len(mandats)


def _poser_fiche(conn, ident, nom, prenom, naissance, uid="uid-x"):
    """Insère une fiche AN/Sénat comme le ferait P9, sans mandat RNE."""
    conn.execute(
        "INSERT INTO elus (id, nom, prenom, date_naissance, uid_an, mandats)"
        " VALUES (?, ?, ?, ?, ?, '[{\"source\": \"AN\", \"type\": \"depute\"}]')",
        (ident, nom, prenom, naissance, uid))


@pytest.mark.parametrize("motif, nom_an, prenom_an, decalage_date", [
    # RNE « FAVENNEC » / AN « Favennec-Bécot » — 4 cas mesurés.
    ("nom composé tronqué au RNE", "{nom}-Bécot", "{prenom}", None),
    # RNE « VAGINAY » / AN « Ricourt Vaginay » — composante commune en FIN.
    ("composante commune en fin", "Ricourt {nom}", "{prenom}", None),
    # AN « Martin (Gironde) » — suffixe de désambiguïsation entre parenthèses.
    ("parenthèses de désambiguïsation", "{nom} (Gironde)", "{prenom}", None),
    # RNE « KBIDI » / AN « K/Bidi » — ponctuation interne divergente.
    ("ponctuation interne", "{nom_coupe}", "{prenom}", None),
    # RNE « Frédéric » / AN « Frédéric-Pierre » — prénom composé tronqué.
    ("prénom composé tronqué", "{nom}", "{prenom}-Pierre", None),
])
def test_rattrapage_les_ecritures_divergentes_de_letat_civil(
        conn, caplog, motif, nom_an, prenom_an, decalage_date):
    """Chaque motif d'écriture divergente mesuré sur la base servie.

    La clé exacte échoue sur chacun. Ce sont des cas à date de naissance
    EXACTE : la règle stricte du 20/11/2026 les trouve. Depuis le 21/11/2026
    elle ne fait que les PROPOSER au journal, sans rien appliquer. Inscrit
    dans la liste blanche, le rattrapage retrouve la fiche AN, y verse le
    mandat RNE, et ne crée aucune ligne `rne-*` pour cette personne. Les deux
    cas de date divergente qui figuraient ici sont refusés par la règle
    (`test_rattrapage_refuse_une_date_divergente_hors_liste_blanche`).
    """
    import logging
    depute = charger_rne()["deputes"][0]
    nom, prenom = depute["Nom de l'élu"], depute["Prénom de l'élu"]
    naissance = depute["Date de naissance"]

    cible_nom = nom_an.format(nom=nom, prenom=prenom,
                              nom_coupe=nom[:2] + "/" + nom[2:].capitalize())
    cible_prenom = prenom_an.format(nom=nom, prenom=prenom)
    cible_date = naissance
    if decalage_date == "mois":
        cible_date = naissance[:5] + ("01" if naissance[5:7] != "01" else "02") + naissance[7:]
    elif decalage_date == "jour":
        cible_date = naissance[:8] + ("01" if naissance[8:] != "01" else "02")

    _poser_fiche(conn, "PA-cible", cible_nom, cible_prenom, cible_date, uid="PA-cible")
    ident = _identifiant(nom, prenom, naissance)

    # Sans la ligne relue : proposé au journal, pas appliqué.
    with caplog.at_level(logging.INFO):
        _, _, rattrapes = p7.upsert_elus(conn, p7.preparer_personnes(charger_rne()),
                                         liste_blanche={})
    assert rattrapes == 0, f"appliqué hors liste : {motif}"
    assert f"{ident} -> PA-cible" in caplog.text, f"non proposé : {motif}"
    assert "NON appliqué" in caplog.text
    assert "RNE" not in conn.execute(
        "SELECT mandats FROM elus WHERE id = 'PA-cible'").fetchone()["mandats"]
    conn.execute("DELETE FROM elus WHERE id LIKE 'rne-%'")

    avant = conn.execute("SELECT count(*) AS n FROM elus").fetchone()["n"]
    inseres, maj, rattrapes = p7.upsert_elus(conn, p7.preparer_personnes(charger_rne()),
                                             liste_blanche={ident: "PA-cible"})

    assert rattrapes == 1, f"non rattrapé : {motif}"
    ligne = conn.execute("SELECT mandats FROM elus WHERE id = 'PA-cible'").fetchone()
    # La fiche AN porte désormais les DEUX sources : rien n'est perdu.
    assert {m["source"] for m in json.loads(ligne["mandats"])} == {"AN", "RNE"}
    # Aucune fiche rne-* n'a été créée pour cette personne.
    assert conn.execute(
        "SELECT count(*) AS n FROM elus WHERE id LIKE 'rne-%' AND nom = ?",
        (nom,)).fetchone()["n"] == 0
    # Une seule personne de plus en base : l'autre député de la fixture.
    assert conn.execute("SELECT count(*) AS n FROM elus").fetchone()["n"] == avant + inseres


def test_rattrapage_supprime_le_doublon_deja_en_base(conn):
    """Le geste qui rend le correctif VISIBLE sur le site.

    La base servie survit d'un déploiement à l'autre, contrairement à celle de
    l'intégration continue qui naît neuve. Une clé corrigée cesserait d'ajouter
    des doublons sans effacer ceux qui sont déjà là : le site continuerait de
    servir deux fiches pour une seule personne. Ce test pose le doublon tel
    qu'une ingestion précédente l'a créé, et exige sa disparition.
    """
    depute = charger_rne()["deputes"][0]
    nom, prenom, naissance = (depute["Nom de l'élu"], depute["Prénom de l'élu"],
                              depute["Date de naissance"])
    _poser_fiche(conn, "PA-cible", nom + "-Bécot", prenom, naissance, uid="PA-cible")

    # Première ingestion, AVANT le correctif : elle a créé une ligne rne-*.
    cle = (p7.normaliser_texte(nom), p7.normaliser_texte(prenom), naissance)
    import hashlib
    ancien = "rne-" + hashlib.sha1("|".join(cle).encode()).hexdigest()[:16]
    conn.execute(
        "INSERT INTO elus (id, nom, prenom, date_naissance, mandats)"
        " VALUES (?, ?, ?, ?, '[{\"source\": \"RNE\", \"type\": \"depute\"}]')",
        (ancien, nom, prenom, naissance))
    assert conn.execute("SELECT count(*) AS n FROM elus WHERE id = ?",
                        (ancien,)).fetchone()["n"] == 1

    _, _, rattrapes = p7.upsert_elus(conn, p7.preparer_personnes(charger_rne()),
                                     liste_blanche={ancien: "PA-cible"})

    assert rattrapes == 1
    # Le doublon a disparu, et son mandat vit désormais sur la fiche AN.
    assert conn.execute("SELECT count(*) AS n FROM elus WHERE id = ?",
                        (ancien,)).fetchone()["n"] == 0
    ligne = conn.execute("SELECT mandats FROM elus WHERE id = 'PA-cible'").fetchone()
    assert {m["source"] for m in json.loads(ligne["mandats"])} == {"AN", "RNE"}


def test_rattrapage_refuse_de_trancher_une_homonymie(conn):
    """Deux fiches AN également plausibles : on renonce, on n'en choisit pas une.

    C'est le garde-fou n° 3. Attribuer la déclaration d'intérêts d'une
    personne à son homonyme serait la faute la plus grave possible ici.
    """
    depute = charger_rne()["deputes"][0]
    nom, prenom, naissance = (depute["Nom de l'élu"], depute["Prénom de l'élu"],
                              depute["Date de naissance"])
    _poser_fiche(conn, "PA-jumeau-1", nom + "-Martin", prenom, naissance, uid="PA-jumeau-1")
    _poser_fiche(conn, "PA-jumeau-2", nom + "-Durand", prenom, naissance, uid="PA-jumeau-2")

    _, _, rattrapes = p7.upsert_elus(conn, p7.preparer_personnes(charger_rne()))
    assert rattrapes == 0
    for r in conn.execute("SELECT mandats FROM elus WHERE uid_an LIKE 'PA-jumeau-%'"):
        assert "RNE" not in r["mandats"]


def test_rattrapage_exige_lannee_de_naissance(conn):
    """Même nom, même prénom, autre ANNÉE : deux personnes, pas une.

    C'est ce qui empêche la tolérance de date de dégénérer en appariement par
    le seul patronyme — 588 couples nom+prénom sont partagés par au moins deux
    personnes dans `elus`.
    """
    depute = charger_rne()["deputes"][0]
    autre_annee = str(int(depute["Date de naissance"][:4]) + 3) + depute["Date de naissance"][4:]
    _poser_fiche(conn, "PA-autre-annee", depute["Nom de l'élu"] + "-Bis",
                 depute["Prénom de l'élu"], autre_annee, uid="PA-autre-annee")

    _, _, rattrapes = p7.upsert_elus(conn, p7.preparer_personnes(charger_rne()))
    assert rattrapes == 0


def test_rattrapage_ne_touche_jamais_un_elu_local(conn):
    """Le rattrapage ne cherche que parmi les fiches AN/Sénat.

    Élargir aux 35 000 élus locaux ferait fusionner des homonymes que plus
    rien ne distinguerait. Ici, une ligne rne-* préexistante au nom voisin ne
    doit pas être rattrapée : elle reste intacte, et la personne RNE est
    insérée à part.
    """
    depute = charger_rne()["deputes"][0]
    conn.execute(
        "INSERT INTO elus (id, nom, prenom, date_naissance, mandats)"
        " VALUES ('rne-voisin', ?, ?, ?, '[{\"source\": \"RNE\", \"type\": \"maire\"}]')",
        (depute["Nom de l'élu"] + "-Voisin", depute["Prénom de l'élu"],
         depute["Date de naissance"]))

    _, _, rattrapes = p7.upsert_elus(conn, p7.preparer_personnes(charger_rne()))
    assert rattrapes == 0
    reste = conn.execute("SELECT mandats FROM elus WHERE id = 'rne-voisin'").fetchone()
    assert json.loads(reste["mandats"]) == [{"source": "RNE", "type": "maire"}]


def test_composantes():
    """La primitive d'index, sur les écritures réellement mesurées."""
    assert "favennec" in p7._composantes("Favennec-Bécot")
    assert "becot" in p7._composantes("Favennec-Bécot")
    # Le suffixe de désambiguïsation de l'AN n'appartient pas au patronyme.
    assert p7._composantes("Martin (Alpes-Maritimes)") == p7._composantes("MARTIN")
    # La forme recollée absorbe une ponctuation interne divergente.
    assert p7._composantes("K/Bidi") & p7._composantes("KBIDI")
    # Une composante commune en FIN de nom compte autant qu'en tête.
    assert p7._composantes("Ricourt Vaginay") & p7._composantes("VAGINAY")


# ---------------------------------------------------------------------------
# Repli strict et liste blanche (audit du 20/11/2026, constat C1)
# ---------------------------------------------------------------------------


def _rne_un_seul(nom, prenom, naissance):
    """La fixture RNE réduite à UN député, à l'état civil choisi."""
    rne = {k: [] for k in charger_rne()}
    depute = dict(charger_rne()["deputes"][0])
    depute.update({"Nom de l'élu": nom, "Prénom de l'élu": prenom,
                   "Date de naissance": naissance})
    rne["deputes"] = [depute]
    return rne


def _identifiant(nom, prenom, naissance):
    return p7._identifiant_rne((p7.normaliser_texte(nom), p7.normaliser_texte(prenom),
                                naissance))


@pytest.mark.parametrize("motif, rne_prenom, rne_date, fiche_prenom, fiche_date", [
    # Le cas de l'audit : même nom, prénoms composés partageant « Jean », nés à
    # 9 jours d'écart. L'ancien repli fusionnait.
    ("prénom voisin né 9 jours après", "Jean-Paul", "1960-05-12", "Jean-Luc", "1960-05-21"),
    # Les jumeaux : même nom, même date, « Jean-Marc » et « Jean-Luc ».
    ("jumeaux", "Jean-Marc", "1960-05-21", "Jean-Luc", "1960-05-21"),
    # Une seule composante de date divergente, même nom et même prénom : un
    # cas juste possible (OLIVE, GALZY), mais que seule la liste blanche admet.
    ("date : le mois diverge", "Jean-Luc", "1960-03-21", "Jean-Luc", "1960-05-21"),
    ("date : le jour diverge", "Jean-Luc", "1960-05-20", "Jean-Luc", "1960-05-21"),
])
def test_rattrapage_refuse_une_date_divergente_hors_liste_blanche(
        conn, caplog, motif, rne_prenom, rne_date, fiche_prenom, fiche_date):
    """Zéro fusion fausse : aucun de ces cas ne rattrape, aucune fiche ne bouge.

    La règle ne les propose même pas : rien n'est signalé à vérifier.
    """
    import logging
    _poser_fiche(conn, "SEN-1", "Martin", fiche_prenom, fiche_date, uid="SEN-1")

    with caplog.at_level(logging.INFO):
        inseres, _, rattrapes = p7.upsert_elus(
            conn, p7.preparer_personnes(_rne_un_seul("MARTIN", rne_prenom, rne_date)),
            liste_blanche={})

    assert "NON appliqué" not in caplog.text, f"proposé : {motif}"
    assert rattrapes == 0, f"fusion fausse : {motif}"
    assert inseres == 1                   # la personne RNE a sa propre fiche
    assert "RNE" not in conn.execute(
        "SELECT mandats FROM elus WHERE id = 'SEN-1'").fetchone()["mandats"]


def test_identifiant_rne_valeur_de_reference():
    """Valeur figée, calculée une fois à la main (sha1 de « DUPONT|ANNE|1970-01-01 »).

    La liste blanche versionnée porte ces identifiants : si leur construction
    change, toutes ses lignes deviennent mortes sans qu'aucun calcul le voie.
    """
    assert p7._identifiant_rne(("DUPONT", "ANNE", "1970-01-01")) == "rne-32d79d5ee1530c2c"


def test_rattraper_exige_l_inclusion_du_nom_et_du_prenom():
    """Date exacte et un mot commun ne suffisent pas : il faut l'inclusion.

    Appelé sans `upsert_elus`, pour que le refus ne dépende que de la règle.
    """
    fiche = {"id": "SEN-1", "nom": "Martin-Lefebvre", "prenom": "Jean-Luc",
             "date_naissance": "1960-05-21"}
    index = {("1960", c): [fiche] for c in p7._composantes(fiche["nom"])}

    def personne(nom, prenom):
        return {"nom": nom, "prenom": prenom, "date_naissance": "1960-05-21"}

    # Témoin : nom inclus, même prénom, même date.
    assert p7._rattraper(personne("MARTIN", "Jean-Luc"), index, set()) is fiche
    # Noms distincts qui partagent « MARTIN » : aucune écriture n'inclut l'autre.
    assert p7._rattraper(personne("DURAND MARTIN", "Jean-Luc"), index, set()) is None
    assert p7._rattraper(personne("MARTIN DUPUIS", "Jean-Luc"), index, set()) is None
    # Prénoms distincts qui partagent « JEAN ».
    assert p7._rattraper(personne("MARTIN", "Jean-Paul"), index, set()) is None
    # Fiche déjà prise : jamais une cible.
    assert p7._rattraper(personne("MARTIN", "Jean-Luc"), index, {"SEN-1"}) is None


def test_la_liste_blanche_rattrape_un_cas_relu_hors_de_la_regle(conn, caplog):
    """Une ligne relue rattrape ce que la règle stricte refuse, sans alerte.

    Identité fictive : même nom, même prénom, le mois de naissance diverge
    entre les deux sources.
    """
    import logging
    _poser_fiche(conn, "PA-fictif", "Valmont", "Lucien", "1971-03-14", uid="PA-fictif")
    rne = _rne_un_seul("VALMONT", "Lucien", "1971-09-14")
    ident = _identifiant("VALMONT", "Lucien", "1971-09-14")
    # Figé à la main : sha1 de « valmont|lucien|1971-09-14 », clé normalisée.
    assert ident == "rne-518ce50dbd1db28d"

    with caplog.at_level(logging.INFO):
        inseres, _, rattrapes = p7.upsert_elus(conn, p7.preparer_personnes(rne),
                                               liste_blanche={ident: "PA-fictif"})

    assert (inseres, rattrapes) == (0, 1)
    assert {m["source"] for m in json.loads(conn.execute(
        "SELECT mandats FROM elus WHERE id = 'PA-fictif'").fetchone()["mandats"])} == {"AN", "RNE"}
    assert "1 par la liste blanche" in caplog.text
    assert "NON appliqué" not in caplog.text and "sans effet" not in caplog.text


def test_la_liste_blanche_ne_vise_qu_une_fiche_an_senat_libre(conn, caplog):
    """Une ligne dont la cible n'est pas une fiche AN/Sénat libre ne fait rien.

    Cible absente, cible `rne-*`, cible déjà atteinte par la clé exacte d'une
    autre personne : dans les trois cas, aucun rattrapage, et la ligne
    refusée est journalisée.
    """
    import logging
    rne = _rne_un_seul("VALMONT", "Lucien", "1971-09-14")
    ident = _identifiant("VALMONT", "Lucien", "1971-09-14")
    conn.execute("INSERT INTO elus (id, nom, prenom, date_naissance, mandats)"
                 " VALUES ('rne-autre', 'DURAND', 'Paul', '1950-01-01', '[]')")
    for cible in ("PA-absente", "rne-autre"):
        caplog.clear()
        with caplog.at_level(logging.INFO):
            _, _, rattrapes = p7.upsert_elus(conn, p7.preparer_personnes(rne),
                                             liste_blanche={ident: cible})
        assert rattrapes == 0, cible
        assert "ligne refusée" in caplog.text and "sans effet" in caplog.text
        conn.execute("DELETE FROM elus WHERE id LIKE 'rne-%' AND id != 'rne-autre'")

    # Fiche déjà prise par la clé exacte d'une autre personne RNE.
    _poser_fiche(conn, "PA-prise", "DUPONT", "Anne", "1970-01-01", uid="PA-prise")
    rne2 = _rne_un_seul("VALMONT", "Lucien", "1971-09-14")
    autre = dict(rne2["deputes"][0])
    autre.update({"Nom de l'élu": "DUPONT", "Prénom de l'élu": "Anne",
                  "Date de naissance": "1970-01-01"})
    rne2["deputes"].append(autre)
    _, _, rattrapes = p7.upsert_elus(conn, p7.preparer_personnes(rne2),
                                     liste_blanche={ident: "PA-prise"})
    assert rattrapes == 0
    mandats = json.loads(conn.execute(
        "SELECT mandats FROM elus WHERE id = 'PA-prise'").fetchone()["mandats"])
    assert len([m for m in mandats if m.get("source") == "RNE"]) == 1


def test_un_rattrapage_hors_liste_blanche_est_signale_pas_applique(conn, caplog):
    """La règle trouve un cas exact, mais sans ligne relue rien n'est appliqué.

    Le journal dit quoi faire : vérifier, puis ajouter une ligne prouvée.
    """
    import logging
    _poser_fiche(conn, "PA-cible", "Favennec-Bécot", "Yannick", "1958-06-10",
                 uid="PA-cible")
    rne = _rne_un_seul("FAVENNEC", "Yannick", "1958-06-10")
    ident = _identifiant("FAVENNEC", "Yannick", "1958-06-10")

    with caplog.at_level(logging.INFO):
        inseres, _, rattrapes = p7.upsert_elus(conn, p7.preparer_personnes(rne),
                                               liste_blanche={})
    assert (inseres, rattrapes) == (1, 0)
    assert "RNE" not in conn.execute(
        "SELECT mandats FROM elus WHERE id = 'PA-cible'").fetchone()["mandats"]
    assert "1 rattachement(s) que la règle ferait, NON appliqué(s)" in caplog.text
    assert "Vérifier chaque cas" in caplog.text and "ajouter au fichier" in caplog.text
    assert f"{ident} -> PA-cible" in caplog.text

    # Relu et inscrit : appliqué au cycle suivant, plus de signalement. La
    # ligne `rne-*` créée au premier passage disparaît.
    caplog.clear()
    with caplog.at_level(logging.INFO):
        _, _, rattrapes = p7.upsert_elus(conn, p7.preparer_personnes(rne),
                                         liste_blanche={ident: "PA-cible"})
    assert rattrapes == 1
    assert "NON appliqué" not in caplog.text
    assert conn.execute("SELECT count(*) AS n FROM elus WHERE id = ?",
                        (ident,)).fetchone()["n"] == 0


def test_rattrapage_exige_un_mandat_parlementaire_au_rne(conn, caplog):
    """Un maire homonyme né le même jour n'atteint jamais une fiche AN/Sénat.

    Même avec une ligne dans la liste blanche : la personne RNE doit porter
    elle-même un mandat de député ou de sénateur. Rien n'est proposé non plus.
    """
    import logging
    _poser_fiche(conn, "SEN-1", "Martin", "Jean-Marc", "1960-05-21", uid="SEN-1")
    rne = {k: [] for k in charger_rne()}
    maire = dict(charger_rne()["maires"][0])
    maire.update({"Nom de l'élu": "MARTIN", "Prénom de l'élu": "Jean",
                  "Date de naissance": "1960-05-21"})
    rne["maires"] = [maire]
    ident = _identifiant("MARTIN", "Jean", "1960-05-21")

    with caplog.at_level(logging.INFO):
        inseres, _, rattrapes = p7.upsert_elus(conn, p7.preparer_personnes(rne),
                                               liste_blanche={ident: "SEN-1"})
    assert (inseres, rattrapes) == (1, 0)
    assert "RNE" not in conn.execute(
        "SELECT mandats FROM elus WHERE id = 'SEN-1'").fetchone()["mandats"]
    assert "NON appliqué" not in caplog.text
    assert f"{ident} -> SEN-1" in caplog.text and "sans effet" in caplog.text


def test_la_liste_blanche_refuse_une_cle_sans_date_complete(conn, caplog):
    """Une clé calculée sans date de naissance complète ne rattrape rien."""
    import logging
    _poser_fiche(conn, "PA-fictif", "Valmont", "Lucien", "1971-03-14", uid="PA-fictif")
    rne = _rne_un_seul("VALMONT", "Lucien", "")
    ident = _identifiant("VALMONT", "Lucien", "")
    with caplog.at_level(logging.INFO):
        _, _, rattrapes = p7.upsert_elus(conn, p7.preparer_personnes(rne),
                                         liste_blanche={ident: "PA-fictif"})
    assert rattrapes == 0
    assert "sans date de naissance complète" in caplog.text


def test_les_listes_blanches_versionnees_sont_lisibles_et_concordent():
    """Les deux fichiers du dépôt se chargent, et P7 concorde avec les 301.

    Chaque fiche `rne-*` retirée par rattrapage et redirigée par
    `redirections-elus.tsv` doit viser la MÊME fiche dans la liste blanche :
    une divergence voudrait dire qu'une des deux tables se trompe de personne.
    """
    p7_liste = p7.charger_rattrapages_verifies()
    p15_liste = p15.charger_liste_blanche(p15.CHEMIN_RATTACHEMENTS_VERIFIES)
    assert len(p7_liste) == 16 and len(p15_liste) == 33
    redirections = {}
    for ligne in (p7.RACINE / "deploy" / "redirections-elus.tsv").read_text(
            encoding="utf-8").splitlines():
        if ligne.startswith("rne-"):
            source, cible = ligne.split("\t")[:2]
            redirections[source] = cible
    for source, cible in redirections.items():
        assert p7_liste.get(source) == cible, source


@pytest.mark.parametrize("motif, contenu, attendu", [
    ("sans preuve", "rne-0000000000000001\tPA1\tX Y\t\n", "quatre champs"),
    ("trois champs", "rne-0000000000000001\tPA1\tX Y\n", "quatre champs"),
    ("cinq champs", "rne-0000000000000001\tPA1\tX Y\tpreuve\tde trop\n", "quatre champs"),
    ("clé hors format", "rne-00000000000000zz\tPA1\tX Y\tpreuve\n", "clé"),
    ("clé de P15 dans P7", "hatvp-0000000000000001\tPA1\tX Y\tpreuve\n", "clé"),
    ("cible hors format", "rne-0000000000000001\tPA-1\tX Y\tpreuve\n", "fiche"),
    ("cible rne-* dans P7", "rne-0000000000000001\trne-0000000000000002\tX Y\tpreuve\n",
     "fiche"),
    ("clé en double", "rne-0000000000000001\tPA1\tX Y\tpreuve\n"
                      "rne-0000000000000001\tSEN-12345A\tX Y\tpreuve\n", "en double"),
])
def test_une_liste_blanche_invalide_refuse_de_charger(tmp_path, motif, contenu, attendu):
    """Une ligne invalide fait échouer le chargement : rien n'est rattaché."""
    chemin = tmp_path / "liste.tsv"
    chemin.write_text("# commentaire\n" + contenu, encoding="utf-8")
    with pytest.raises(ValueError, match=attendu):
        p7.charger_rattrapages_verifies(chemin)


def test_une_liste_blanche_valide_se_charge(tmp_path):
    """Témoin des refus ci-dessus : les mêmes lignes, bien formées, passent."""
    chemin = tmp_path / "liste.tsv"
    chemin.write_text("# commentaire\n\nrne-0000000000000001\tPA1\tX Y\tpreuve\n"
                      "rne-0000000000000002\tSEN-12345A\tX Y\tpreuve\n", encoding="utf-8")
    assert p7.charger_rattrapages_verifies(chemin) == {
        "rne-0000000000000001": "PA1", "rne-0000000000000002": "SEN-12345A"}


def _rne_avec_jumeau(nom_jumeau: str, **surcharges):
    """La fixture RNE, plus un second député dérivé du premier.

    Sert aux cas où il faut DEUX personnes RNE distinctes visant la même fiche
    AN : la fixture n'en porte que deux, aux états civils sans rapport.
    """
    rne = charger_rne()
    jumeau = dict(rne["deputes"][0])
    jumeau["Nom de l'élu"] = nom_jumeau
    jumeau.update(surcharges)
    rne = dict(rne)
    rne["deputes"] = rne["deputes"] + [jumeau]
    return rne


def test_rattrapage_ne_vole_pas_une_fiche_que_la_cle_exacte_atteint_deja(conn):
    """Ajustement n° 3 : la collision clé exacte × rattrapage.

    Le set `pris` de la boucle n'interdit qu'un DOUBLE rattrapage. Il laisse
    ouvert le cas où une fiche AN est atteinte par la CLÉ EXACTE d'une personne
    et, en plus, choisie comme cible de rattrapage pour une AUTRE : les deux y
    écrivent leurs mandats, et la seconde efface en silence les entrées
    "source": "RNE" de la première — le mandat d'une personne disparaît sans un
    mot. Reproduit ici ; 0 occurrence sur les données du 26/08/2026, c'est donc
    un trou latent, pas un défaut mesuré.

    La bonne réponse n'est pas de choisir : c'est de RENONCER au rattrapage.
    Deux personnes qui prétendent à la même fiche, c'est exactement l'homonymie
    contre laquelle le garde-fou n° 3 existe.
    """
    depute = charger_rne()["deputes"][0]
    nom, prenom, naissance = (depute["Nom de l'élu"], depute["Prénom de l'élu"],
                              depute["Date de naissance"])
    # La fiche AN porte EXACTEMENT l'état civil du premier député : la clé
    # exacte l'atteint, sans passer par le rattrapage.
    _poser_fiche(conn, "PA-cible", nom, prenom, naissance, uid="PA-cible")
    # Un second élu RNE, écrit autrement, que le repli enverrait sur la MÊME.
    rne = _rne_avec_jumeau(nom + "-Bis")

    _, _, rattrapes = p7.upsert_elus(conn, p7.preparer_personnes(rne))

    assert rattrapes == 0, "la fiche était déjà prise par la clé exacte"
    # Le mandat du premier est intact sur la fiche AN…
    mandats = json.loads(conn.execute(
        "SELECT mandats FROM elus WHERE id = 'PA-cible'").fetchone()["mandats"])
    rne_sur_cible = [m for m in mandats if m.get("source") == "RNE"]
    assert len(rne_sur_cible) == 1
    assert rne_sur_cible[0]["departement"] == depute["Code du département"]
    # …et le second vit sur sa propre ligne, au lieu d'avoir écrasé le premier.
    assert conn.execute(
        "SELECT count(*) AS n FROM elus WHERE id LIKE 'rne-%' AND nom = ?",
        (nom + "-Bis",)).fetchone()["n"] == 1


def test_rattrapage_ordre_indifferent_la_cible_prise_lest_dans_les_deux_sens(conn):
    """Le garde-fou de l'ajustement n° 3 ne dépend pas de l'ordre d'itération.

    Interdire la cible seulement quand la clé exacte l'a DÉJÀ rencontrée
    laisserait passer le cas inverse — le rattrapage arrivant en premier. Le
    dictionnaire `personnes` est ordonné : ce test place le jumeau AVANT la
    personne à clé exacte, l'autre ordre étant couvert par le test précédent.
    """
    depute = charger_rne()["deputes"][0]
    nom, prenom, naissance = (depute["Nom de l'élu"], depute["Prénom de l'élu"],
                              depute["Date de naissance"])
    _poser_fiche(conn, "PA-cible", nom, prenom, naissance, uid="PA-cible")
    rne = _rne_avec_jumeau(nom + "-Bis")
    personnes = p7.preparer_personnes(rne)
    # On inverse l'ordre : le jumeau (rattrapable) est traité en premier.
    inverse = {c: personnes[c] for c in reversed(list(personnes))}

    _, _, rattrapes = p7.upsert_elus(conn, inverse)

    assert rattrapes == 0
    mandats = json.loads(conn.execute(
        "SELECT mandats FROM elus WHERE id = 'PA-cible'").fetchone()["mandats"])
    assert len([m for m in mandats if m.get("source") == "RNE"]) == 1


def test_les_particules_ne_sont_jamais_appariantes(conn):
    """Ajustement n° 2 : la faille que la PR #89 avait fermée ailleurs.

    Le `_composantes` d'origine de ce correctif rendait `frozenset(mots) |
    {recolle}` SANS filtre : « LE MAIRE » et « LE GAC » se seraient appariés sur
    la seule syllabe « le », et « DE RUGY » avec « DE COURSON » sur « de ».
    Mesuré sur les fiches servies : « LE » est porté par 18 d'entre elles,
    « DE » par 14. Ici le chemin ne se contente pas de rattacher : il SUPPRIME
    une fiche. C'était une faille armée.

    Le remède retenu est de n'avoir qu'une seule primitive — celle de P15, qui
    porte déjà le filtre — ramenée au casefold de P7 (voir `_composantes`).
    """
    # La primitive elle-même : la particule ne survit pas, la recollée oui.
    assert p7._composantes("LE MAIRE") & p7._composantes("LE GAC") == frozenset()
    assert p7._composantes("DE RUGY") & p7._composantes("DE COURSON") == frozenset()
    assert "lemaire" in p7._composantes("Le Maire")
    # Et la casse : tout P7 est en casefold, P15 en MAJUSCULES. Deux jeux qui
    # ne s'intersectent jamais — le casefold est posé à la frontière.
    assert all(c == c.casefold() for c in p7._composantes("Favennec-Bécot"))

    # Bout en bout : deux élus dont seule une particule est commune ne se
    # rattrapent pas, et aucune fiche n'est supprimée.
    depute = charger_rne()["deputes"][0]
    _poser_fiche(conn, "PA-particule", "LE GAC", depute["Prénom de l'élu"],
                 depute["Date de naissance"], uid="PA-particule")
    rne = _rne_avec_jumeau("LE MAIRE")

    _, _, rattrapes = p7.upsert_elus(conn, p7.preparer_personnes(rne))
    assert rattrapes == 0
    assert "RNE" not in conn.execute(
        "SELECT mandats FROM elus WHERE id = 'PA-particule'").fetchone()["mandats"]


def test_rattrapage_refuse_un_homonyme_de_meme_patronyme_et_meme_annee(conn):
    """Le cas BELLAMY — le seul tendu de la base servie, et il n'était pas testé.

    `rne-9d8eafca03bfb18c` BELLAMY côtoie un `SEN-21125C Bellamy` de MÊME
    patronyme et MÊME année de naissance. Sur les quatre garde-fous, deux
    seulement le protègent : aucune composante de prénom commune, et des dates
    qui ne sont pas voisines. La protection tient, mais sans marge — d'où ce
    test, qui la rend explicite au lieu de la laisser à la chance.
    """
    depute = charger_rne()["deputes"][0]
    nom, naissance = depute["Nom de l'élu"], depute["Date de naissance"]
    # Même patronyme, même ANNÉE, prénom sans aucune composante commune.
    autre_jour = naissance[:8] + ("07" if naissance[8:] != "07" else "08")
    _poser_fiche(conn, "PA-homonyme", nom, "Marie-Jeanne", autre_jour,
                 uid="PA-homonyme")

    _, _, rattrapes = p7.upsert_elus(conn, p7.preparer_personnes(charger_rne()))

    assert rattrapes == 0, "un homonyme de même patronyme ne doit jamais suffire"
    assert "RNE" not in conn.execute(
        "SELECT mandats FROM elus WHERE id = 'PA-homonyme'").fetchone()["mandats"]


def test_le_volume_des_suppressions_est_borne(conn):
    """Ajustement n° 4 : sans plafond, un millésime RNE abîmé effacerait en masse.

    Le rattrapage est le SEUL endroit où ce pipeline retire une ligne de sa
    table noyau, et la suppression ne se répare pas : les déclarations que P15
    rattachait à la fiche partie basculent sur son chemin `hors_fiche`, qui
    journalise sans faire échouer et efface la mémoire du garde-fou SANS RETOUR.
    `ft-deploy` ne rattraperait pas non plus : ses deux seuls seuils de
    volumétrie sont `NB_ELUS >= 900` et un plafond de taille d'export.

    Le contrôle est éprouvé ici directement — l'appeler avec une liste construite
    est la seule façon de franchir un plancher de 50 sans une fixture de 1 000
    élus. Le passage par `upsert_elus` est couvert par les tests voisins.
    """
    # Sous le plancher : muet, quelle que soit la proportion (le cas de l'IC,
    # dont la base naît neuve et ne porte qu'une poignée de fiches).
    p7._controler_volume_supprimees([f"rne-{i:016x}" for i in range(50)], 2)
    # Au-dessus du plancher mais sous la proportion : muet aussi.
    p7._controler_volume_supprimees([f"rne-{i:016x}" for i in range(51)], 5_000)
    # Les deux franchis : il mord, et il NOMME les identifiants.
    trop = [f"rne-{i:016x}" for i in range(500)]
    with pytest.raises(ValueError) as excinfo:
        p7._controler_volume_supprimees(trop, 925)
    message = str(excinfo.value)
    assert "500 fiche(s)" in message and "Base NON modifiée" in message
    assert trop[0] in message
    assert p7.ENV_RATTRAPAGES_ACQUITTES in message


def test_les_suppressions_sacquittent_une_par_une(monkeypatch):
    """L'issue de secours ne desserre aucun seuil : elle NOMME ce qu'on assume.

    Même forme qu'en P15 (`FT_P15_PERTES_ACQUITTEES`), et pour la même raison :
    une levée arrête les 21 pipelines en aval et tout le rafraîchissement du
    site jusqu'à intervention humaine. Il fallait une sortie utilisable en une
    commande, pas un correctif de code à écrire dans l'urgence.
    """
    trop = [f"rne-{i:016x}" for i in range(500)]
    # Acquitter 449 laisse 51 : au-dessus du plancher, sous la proportion.
    monkeypatch.setenv(p7.ENV_RATTRAPAGES_ACQUITTES, ",".join(trop[:449]))
    p7._controler_volume_supprimees(trop, 5_000)
    # Acquitter TOUT : muet quel que soit le dénominateur.
    monkeypatch.setenv(p7.ENV_RATTRAPAGES_ACQUITTES, ", ".join(trop))
    p7._controler_volume_supprimees(trop, 1)
    # N'acquitter que la moitié : il mord encore, sur le reste seulement.
    monkeypatch.setenv(p7.ENV_RATTRAPAGES_ACQUITTES, ",".join(trop[:100]))
    with pytest.raises(ValueError, match="400 fiche"):
        p7._controler_volume_supprimees(trop, 925)


def test_upsert_elus_arme_reellement_le_garde_fou_de_volume(conn, monkeypatch):
    """Le contrôle est BRANCHÉ, pas seulement écrit.

    Le test voisin éprouve la fonction de contrôle en l'appelant ; celui-ci
    éprouve le CÂBLAGE — sans quoi retirer son appel dans `upsert_elus`
    laisserait toute la suite verte. Les seuils sont abaissés plutôt que la
    fixture gonflée à mille élus : c'est le branchement qu'on mesure ici, pas
    la valeur du plancher.
    """
    monkeypatch.setattr(p7, "PLANCHER_RATTRAPAGES", 0)
    monkeypatch.setattr(p7, "PROPORTION_RATTRAPAGES", 0.0)
    depute = charger_rne()["deputes"][0]
    nom, prenom, naissance = (depute["Nom de l'élu"], depute["Prénom de l'élu"],
                              depute["Date de naissance"])
    _poser_fiche(conn, "PA-cible", nom + "-Bécot", prenom, naissance, uid="PA-cible")
    cle = (p7.normaliser_texte(nom), p7.normaliser_texte(prenom), naissance)
    import hashlib
    ancien = "rne-" + hashlib.sha1("|".join(cle).encode()).hexdigest()[:16]
    conn.execute(
        "INSERT INTO elus (id, nom, prenom, date_naissance, mandats)"
        " VALUES (?, ?, ?, ?, '[{\"source\": \"RNE\", \"type\": \"depute\"}]')",
        (ancien, nom, prenom, naissance))

    with pytest.raises(ValueError, match="rattrapage invraisemblable"):
        p7.upsert_elus(conn, p7.preparer_personnes(charger_rne()),
                       liste_blanche={ancien: "PA-cible"})

    # Et l'acquittement traverse bien le même câblage.
    monkeypatch.setenv(p7.ENV_RATTRAPAGES_ACQUITTES, ancien)
    _, _, rattrapes = p7.upsert_elus(conn, p7.preparer_personnes(charger_rne()),
                                     liste_blanche={ancien: "PA-cible"})
    assert rattrapes == 1


def test_la_suppression_tombe_dans_la_transaction_de_ecrire(conn):
    """La fiche supprimée revient si le cycle échoue APRÈS.

    C'est la propriété que les PR #91 et #92 ont achetée, et le rattrapage ne
    doit pas la défaire : le `DELETE FROM elus` est le premier ordre destructeur
    que ce pipeline émette sur sa table noyau, et il doit être annulé comme le
    reste. Sans le `BEGIN IMMEDIATE` d'`appliquer_schema`, il partirait sur
    disque et la fiche serait perdue alors même que le cycle a échoué.
    """
    depute = charger_rne()["deputes"][0]
    nom, prenom, naissance = (depute["Nom de l'élu"], depute["Prénom de l'élu"],
                              depute["Date de naissance"])
    _poser_fiche(conn, "PA-cible", nom + "-Bécot", prenom, naissance, uid="PA-cible")
    cle = (p7.normaliser_texte(nom), p7.normaliser_texte(prenom), naissance)
    import hashlib
    ancien = "rne-" + hashlib.sha1("|".join(cle).encode()).hexdigest()[:16]
    conn.execute(
        "INSERT INTO elus (id, nom, prenom, date_naissance, mandats)"
        " VALUES (?, ?, ?, ?, '[{\"source\": \"RNE\", \"type\": \"depute\"}]')",
        (ancien, nom, prenom, naissance))
    conn.commit()

    conn.execute("BEGIN IMMEDIATE")
    _, _, rattrapes = p7.upsert_elus(conn, p7.preparer_personnes(charger_rne()),
                                     liste_blanche={ancien: "PA-cible"})
    assert rattrapes == 1
    assert conn.execute("SELECT count(*) AS n FROM elus WHERE id = ?",
                        (ancien,)).fetchone()["n"] == 0
    conn.rollback()

    # Le cycle a échoué : la fiche est revenue, et son mandat avec.
    assert conn.execute("SELECT count(*) AS n FROM elus WHERE id = ?",
                        (ancien,)).fetchone()["n"] == 1
    assert "RNE" not in conn.execute(
        "SELECT mandats FROM elus WHERE id = 'PA-cible'").fetchone()["mandats"]


# ---------------------------------------------------------------------------
# Contrôle d'après-cycle : collisions de clé d'état civil
# ---------------------------------------------------------------------------


def _poser_ligne(conn, ident, nom, prenom, naissance):
    """Pose une ligne brute de `elus`, sans passer par aucun pipeline.

    `_poser_fiche` impose un `uid_an` et un mandat AN : elle ne sait pas
    fabriquer une ligne `rne-*`, qui est justement la moitié intéressante d'une
    collision.
    """
    conn.execute(
        "INSERT INTO elus (id, nom, prenom, date_naissance) VALUES (?, ?, ?, ?)",
        (ident, nom, prenom, naissance))


def test_les_collisions_de_cle_sont_comptees_nommees_et_ordonnees(conn):
    """Deux graphies que `normaliser_texte` confond = UNE collision.

    Le contrôle ne peut pas être trois lignes de SQL : `nom = nom` laisserait
    passer « ZZTE KERVAN » contre « Zzté-Kervan », et `prenom = prenom`
    laisserait passer « Jean-Pierre » contre « Jean Pierre ».

    ⚠️ LES QUATRE TRANSFORMATIONS SONT EXERCÉES SUR LE CHAMP `nom`, ET C'EST
    DÉLIBÉRÉ. Une première version de ce test réservait l'accent et le tiret au
    PRÉNOM et ne mettait qu'une différence de casse sur le nom : une réfutation
    du 28/08/2026 a montré qu'elle restait VERTE si l'on remplaçait
    `normaliser_texte(nom)` par un simple `.casefold()`. Le contrôle serait
    alors devenu aveugle à sa cible principale — les graphies de PATRONYME, dont
    la docstring de `_rattraper` liste dix-sept cas. Le rembourrage de la date
    garde de son côté le `.strip()`, sans lequel le contrôle divergerait de
    `upsert_elus`.
    """
    _poser_ligne(conn, "PA-collision", "Zzté-Kervan", "Jean-Pierre", "1969-10-22")
    _poser_ligne(conn, "rne-0000000000000001", "ZZTE KERVAN", "Jean Pierre",
                 " 1969-10-22 ")
    _poser_ligne(conn, "PA-voisine", "Zzté-Kervan", "Jean-Pierre", "1970-01-01")

    collisions = p7.controler_collisions_de_cle(conn)

    assert len(collisions) == 1
    (c,) = collisions
    assert c["cle"] == ("zzte kervan", "jean pierre", "1969-10-22")
    # Ordre de BALAYAGE, pas ordre alphabétique : c'est lui qui décide.
    assert c["ids"] == ["PA-collision", "rne-0000000000000001"]
    assert c["retenu"] == "PA-collision"


def test_le_controle_compte_des_cles_pas_des_lignes(conn):
    """Trois lignes sur une clé, ce n'est pas trois collisions, c'est une.

    Un compteur de LIGNES rendrait 5 là où le défaut n'a que deux occurrences :
    le nombre journalisé n'aurait plus de sens, et le seuil « attendu 0 »
    perdrait sa lisibilité dès la première collision réelle.
    """
    for ident in ("PA-a", "rne-000000000000000a", "rne-000000000000000b"):
        _poser_ligne(conn, ident, "Zztestov", "Ana", "1960-01-01")
    _poser_ligne(conn, "PA-b", "Ykerman", "Bo", "1961-02-02")
    _poser_ligne(conn, "rne-000000000000000c", "Ykerman", "Bo", "1961-02-02")

    collisions = p7.controler_collisions_de_cle(conn)

    assert len(collisions) == 2
    assert sorted(len(c["ids"]) for c in collisions) == [2, 3]


def test_une_base_sans_collision_ne_dit_rien(conn, caplog):
    """Contre-épreuve du SILENCE — sans elle, un contrôle toujours bavard
    passerait pour un contrôle qui voit.

    Le pendant de cette épreuve vit dans `ecrire()` : le compte part au journal
    même à zéro, pour qu'un contrôle débranché ne se confonde pas avec un
    contrôle au vert. Les deux vont ensemble.
    """
    import logging
    _poser_ligne(conn, "PA-a", "Zztestov", "Ana", "1960-01-01")
    _poser_ligne(conn, "rne-000000000000000a", "Zztestov", "Ana", "1960-01-02")
    _poser_ligne(conn, "rne-000000000000000b", "Zztestov", "Anna", "1960-01-01")

    with caplog.at_level(logging.WARNING):
        assert p7.controler_collisions_de_cle(conn) == []
    assert caplog.text == ""


def test_le_doublon_rne_condamne_est_nomme(conn, caplog):
    """Le SENS de la collision change tout, et le journal doit le dire.

    Quand la ligne retenue par le balayage n'est pas une fiche `rne-*`, la
    branche `if e is None or e["id"].startswith("rne-")` de `upsert_elus` n'est
    jamais prise : pas de rattrapage, pas de `DELETE`, et le doublon `rne-*`
    reste servi pour toujours. C'est le sens MAJORITAIRE du biais et le seul
    qu'aucun compteur de cycle ne peut voir. Dans l'autre sens, le rattrapage
    reste possible : le second avertissement ne doit PAS partir, sans quoi il
    crierait au loup une nuit sur deux.
    """
    import logging
    _poser_ligne(conn, "PA-cible", "Zztestov", "Ana", "1960-01-01")
    _poser_ligne(conn, "rne-000000000000000a", "ZZTESTOV", "ANA", "1960-01-01")
    with caplog.at_level(logging.WARNING):
        p7.controler_collisions_de_cle(conn)
    assert "collision de clé d'état civil" in caplog.text
    assert "plus jamais purgés" in caplog.text
    assert "rne-000000000000000a" in caplog.text

    # Sens inverse : la fiche `rne-*` est rencontrée la première.
    caplog.clear()
    conn.execute("DELETE FROM elus")
    _poser_ligne(conn, "rne-000000000000000a", "ZZTESTOV", "ANA", "1960-01-01")
    _poser_ligne(conn, "PA-cible", "Zztestov", "Ana", "1960-01-01")
    with caplog.at_level(logging.WARNING):
        p7.controler_collisions_de_cle(conn)
    assert "collision de clé d'état civil" in caplog.text
    assert "plus jamais purgés" not in caplog.text

    # Troisième sens : DEUX fiches AN/Sénat, aucune `rne-*`. La retenue n'est
    # pas une fiche `rne-*`, mais il n'y a aucun doublon `rne-*` à condamner :
    # sans la garde `doublons_rne and`, le message partirait avec une liste
    # VIDE. Réfutation du 28/08/2026 : rien ne tenait cette garde.
    caplog.clear()
    conn.execute("DELETE FROM elus")
    _poser_ligne(conn, "PA-un", "Zztestov", "Ana", "1960-01-01")
    _poser_ligne(conn, "SEN-deux", "ZZTESTOV", "ANA", "1960-01-01")
    with caplog.at_level(logging.WARNING):
        p7.controler_collisions_de_cle(conn)
    assert "collision de clé d'état civil" in caplog.text
    assert "plus jamais purgés" not in caplog.text


def test_le_controle_ne_leve_jamais_et_ne_modifie_rien(conn):
    """Il SIGNALE, il ne tranche pas — et `ft-deploy` est en tout-ou-rien.

    Une levée ici gèlerait la publication entière du site. Et une correction
    automatique trancherait une question d'identité que `redirections-elus.tsv`
    laisse délibérément ouverte : l'appariement y serait une INFÉRENCE, pas une
    source d'état civil.
    """
    _poser_ligne(conn, "PA-cible", "Zztestov", "Ana", "1960-01-01")
    _poser_ligne(conn, "rne-000000000000000a", "ZZTESTOV", "ANA", "1960-01-01")
    avant = conn.execute("SELECT id, nom, prenom, date_naissance FROM elus"
                         " ORDER BY id").fetchall()

    assert len(p7.controler_collisions_de_cle(conn)) == 1        # ne lève pas

    apres = conn.execute("SELECT id, nom, prenom, date_naissance FROM elus"
                         " ORDER BY id").fetchall()
    assert [tuple(r) for r in apres] == [tuple(r) for r in avant]


def test_les_fiches_sans_date_de_naissance_collapsent_sur_une_seule_cle(conn):
    """Propriété RÉELLE de la clé, écrite ici pour qu'elle ne surprenne pas.

    `(e["date_naissance"] or "").strip()` fait de l'absence de date une valeur
    de clé comme une autre : deux homonymes stricts sans date de naissance
    collisionnent, alors que ce sont peut-être deux personnes. Ce n'est pas un
    défaut du contrôle, c'est le défaut qu'il révèle — `upsert_elus` les
    confond DÉJÀ, et son `setdefault` en écarte une en silence. Mesuré le
    28/08/2026 sur la base servie : 0 ligne de `elus` sans date de naissance,
    donc 0 occurrence. Si l'amont en livre un jour, le compte s'allumera, et il
    aura raison.
    """
    _poser_ligne(conn, "rne-000000000000000a", "Zztestov", "Ana", None)
    _poser_ligne(conn, "rne-000000000000000b", "ZZTESTOV", "ANA", "")

    collisions = p7.controler_collisions_de_cle(conn)

    assert len(collisions) == 1
    assert collisions[0]["cle"] == ("zztestov", "ana", "")


def test_le_controle_lit_la_meme_requete_que_upsert_elus():
    """La fidélité du contrôle tient à UNE chose : la projection partagée.

    ⚠️ Mesuré le 28/08/2026 : abréger la projection ne suffit PAS à changer
    l'ordre — `SELECT id, nom, prenom, date_naissance FROM elus` reste
    `SCAN elus`. Seule une projection ENTIÈREMENT couverte par un index bascule
    (`SELECT rowid` → `SCAN … USING COVERING INDEX idx_elus_uid_an`), et
    celle-là rend bien un autre ordre. Le partage ferme donc une porte étroite,
    que l'ajout d'un index un jour élargirait. Ce test le garde, et rien
    d'autre ne le garderait.
    """
    arbre = ast.parse(Path(p7.__file__).read_text(encoding="utf-8"))
    fonctions = {n.name: n for n in ast.walk(arbre)
                 if isinstance(n, ast.FunctionDef)}
    for nom in ("upsert_elus", "controler_collisions_de_cle"):
        partagees = [a for a in ast.walk(fonctions[nom])
                     if isinstance(a, ast.Call)
                     and isinstance(a.func, ast.Attribute)
                     and a.func.attr == "execute"
                     and a.args and isinstance(a.args[0], ast.Name)
                     and a.args[0].id == "REQUETE_ETAT_CIVIL"]
        assert partagees, f"{nom} n'exécute plus REQUETE_ETAT_CIVIL"
    # Et la constante projette bien l'état civil complet, pas un rowid nu.
    assert "id, nom, prenom, date_naissance" in p7.REQUETE_ETAT_CIVIL
    assert "rowid" not in p7.REQUETE_ETAT_CIVIL


def test_le_controle_mesure_l_etat_d_APRES_upsert_elus(tmp_path, dossiers, caplog,
                                                      monkeypatch):
    """Il compte l'état d'APRÈS le rattrapage, pas celui d'avant.

    ⚠️ CE TEST EXISTE PARCE QU'UNE RÉFUTATION A MONTRÉ QU'IL MANQUAIT. Le
    28/08/2026, déplacer l'appel du contrôle AVANT `upsert_elus` laissait toute
    la suite VERTE : la collision que le test de câblage voisin pose n'est
    portée par aucune personne du lot RNE, donc l'état d'avant et l'état d'après
    y sont identiques et rien ne pouvait distinguer les deux positions.

    L'état fabriqué ici les sépare : trois lignes, dont deux `rne-*` de MÊME
    clé. Avant le cycle, ces deux-là sont une collision. Pendant le cycle, la
    première est rattrapée sur `PA-cible` et SUPPRIMÉE — la seconde reste seule
    sur sa clé, et la collision n'existe plus. Le contrôle doit donc compter
    **0** ; s'il tirait avant l'UPSERT, il compterait 1.

    L'état est synthétique — deux `rne-*` de même clé ne peuvent pas naître du
    pipeline, dont l'identifiant EST le sha1 de la clé. C'est assumé : ce qu'on
    épingle ici est le site d'appel, pas une population réelle.
    """
    import hashlib
    import logging
    conn = db.init_db(chemin=tmp_path / "t.db")
    try:
        depute = charger_rne()["deputes"][0]
        nom, prenom, naissance = (depute["Nom de l'élu"], depute["Prénom de l'élu"],
                                  depute["Date de naissance"])
        _poser_fiche(conn, "PA4242", nom + "-Bécot", prenom, naissance,
                     uid="PA4242")
        cle = (p7.normaliser_texte(nom), p7.normaliser_texte(prenom), naissance)
        ancien = "rne-" + hashlib.sha1("|".join(cle).encode()).hexdigest()[:16]
        # Le rattrapage n'est appliqué que par la liste blanche, que `ecrire`
        # lit dans son fichier : une liste d'une ligne, pour ce test.
        liste = tmp_path / "rattrapages.tsv"
        liste.write_text(f"{ancien}\tPA4242\tX Y\tpreuve du test\n", encoding="utf-8")
        monkeypatch.setattr(p7, "CHEMIN_RATTRAPAGES_VERIFIES", liste)
        _poser_ligne(conn, ancien, nom, prenom, naissance)
        _poser_ligne(conn, "rne-000000000000jum", nom, prenom, naissance)
        conn.commit()

        # Avant le cycle, la collision est bien là — sinon le test ne prouverait
        # rien : il faut que les deux positions donnent des comptes DIFFÉRENTS.
        assert len(p7.controler_collisions_de_cle(conn)) == 1

        with caplog.at_level(logging.INFO):
            p7.ecrire(conn, dossiers, charger_rne(),
                      {"cm": FIXTURES / "rne_cm_extrait.csv"},
                      AUJOURD_HUI, "2026-08-14", "2026-08-11")

        assert "1 rattrapés sur une fiche AN/Sénat" in caplog.text
        assert conn.execute("SELECT count(*) AS n FROM elus WHERE id = ?",
                            (ancien,)).fetchone()["n"] == 0
        assert "0 collision(s) de clé" in caplog.text
        assert len(p7.controler_collisions_de_cle(conn)) == 0
    finally:
        conn.close()


def test_le_controle_est_branche_dans_ecrire(tmp_path, dossiers, caplog):
    """Le contrôle est BRANCHÉ, pas seulement écrit — et il compte À ZÉRO.

    Le test voisin éprouve la fonction en l'appelant ; celui-ci éprouve le
    CÂBLAGE dans le vrai `ecrire()`, sans quoi retirer son appel laisserait
    toute la suite verte. Il tient les deux moitiés du contrat : la collision
    posée est vue, ET le compte part au journal même quand il vaut zéro — c'est
    cette seconde moitié qui distingue, dans `deploiement.log`, un contrôle au
    vert d'un contrôle débranché.
    """
    import logging
    conn = db.init_db(chemin=tmp_path / "t.db")
    try:
        # --- cycle SAIN : le compte doit être journalisé, à zéro -------
        with caplog.at_level(logging.INFO):
            p7.ecrire(conn, dossiers, charger_rne(),
                      {"cm": FIXTURES / "rne_cm_extrait.csv"},
                      AUJOURD_HUI, "2026-08-14", "2026-08-11")
        assert "0 collision(s) de clé" in caplog.text
        conn.commit()

        # --- collision posée à la main, cycle rejoué -------------------
        caplog.clear()
        _poser_ligne(conn, "PA-collision", "Zztestov", "Jean-Pierre", "1969-10-22")
        _poser_ligne(conn, "rne-0000000000000001", "ZZTESTOV", "Jean Pierre",
                     "1969-10-22")
        conn.commit()
        with caplog.at_level(logging.INFO):
            p7.ecrire(conn, dossiers, charger_rne(),
                      {"cm": FIXTURES / "rne_cm_extrait.csv"},
                      AUJOURD_HUI, "2026-08-14", "2026-08-11")
        assert "1 collision(s) de clé" in caplog.text
        assert "collision de clé d'état civil" in caplog.text
        assert "plus jamais purgés" in caplog.text
    finally:
        conn.close()


def test_croiser_hatvp_flag_unique_des_deux_cotes(conn, dossiers):
    p7.upsert_elus(conn, p7.preparer_personnes(charger_rne()))
    n, _ecartes = p7.croiser_hatvp_flag(conn, dossiers)
    assert n >= 1
    guerza = conn.execute(
        "SELECT hatvp_flag, hatvp_url FROM elus WHERE nom = 'GUERZA'").fetchone()
    assert guerza["hatvp_flag"] == 1
    assert guerza["hatvp_url"] == "https://www.hatvp.fr/pages_nominatives/guerza-abdel-kader-9874"
    # Homonymie côté élus (deux LEFEVRE Philippe) → pas de flag.
    for r in conn.execute("SELECT hatvp_flag FROM elus WHERE nom = 'LEFEVRE'"):
        assert r["hatvp_flag"] == 0


def _dossier_hatvp(nom, prenom, type_mandat, departement, qualite,
                   classement=None):
    """Dossier au gabarit de parser_liste_hatvp (colonnes réelles)."""
    return {"civilite": "M.", "prenom": prenom, "nom": nom,
            "classement": classement or f"{nom}{prenom}1",
            "type_mandat": type_mandat, "qualite": qualite,
            "type_document": "di", "departement": departement,
            "date_publication": "", "date_depot": "", "nom_fichier": "",
            "url_dossier": f"/pages_nominatives/{nom.lower()}-1",
            "open_data": "", "statut_publication": "Livrée", "id_origine": "",
            "url_photo": ""}


def _fiche(conn, ident, nom, prenom, mandats):
    conn.execute("INSERT INTO elus (id, nom, prenom, mandats) VALUES (?, ?, ?, ?)",
                 (ident, nom, prenom, json.dumps(mandats)))


def _fiche_nee(conn, ident, nom, prenom, naissance, mandats):
    conn.execute("INSERT INTO elus (id, nom, prenom, date_naissance, mandats)"
                 " VALUES (?, ?, ?, ?, ?)",
                 (ident, nom, prenom, naissance, json.dumps(mandats)))


def test_hatvp_flag_va_a_la_fiche_senat_du_depute_passe_au_senat(conn, caplog):
    """Constat du 21/11/2026 : 8 sénateurs, anciens députés, n'avaient aucun
    lien HATVP. Leur fiche PA retirée portait le même nom et le même prénom :
    deux candidats, donc rien. La table des redirections dit que c'est la même
    personne, la fiche SEN reçoit le lien. Dates de naissance différentes :
    ce n'est pas la paire décrite, on ne départage rien."""
    import logging
    depute = [{"source": "AN-P9", "type": "depute", "date_fin": "2026-09-30"}]
    senateur = [{"source": "SENAT-P9", "type": "senateur"}]
    _fiche_nee(conn, "PA796034", "Giletti", "Frank", "1973-03-01", depute)
    _fiche_nee(conn, "SEN-20874F", "Giletti", "Frank", "1973-03-01", senateur)
    _fiche_nee(conn, "PA841131", "Bouquin", "Manon", "1992-06-02", depute)
    _fiche_nee(conn, "SEN-21223D", "Bouquin", "Manon", "1990-01-01", senateur)
    hatvp = [_dossier_hatvp("GILETTI", "Frank", "senateur", "83", "Sénateur"),
             _dossier_hatvp("BOUQUIN", "Manon", "senateur", "21", "Sénatrice")]
    passees = {"PA796034": "SEN-20874F", "PA841131": "SEN-21223D"}
    with caplog.at_level(logging.INFO):
        assert p7.croiser_hatvp_flag(conn, hatvp, passees=passees) == (1, 0)
    liens = dict(conn.execute("SELECT id, hatvp_url FROM elus").fetchall())
    assert liens == {"PA796034": None, "PA841131": None, "SEN-21223D": None,
                     "SEN-20874F": "https://www.hatvp.fr/pages_nominatives/giletti-1"}
    assert "PA796034 -> SEN-20874F" in caplog.text
    # Sans la table : l'ancien comportement, aucun lien.
    assert p7.croiser_hatvp_flag(conn, hatvp, passees={}) == (0, 0)


@pytest.mark.parametrize("pa_en_premier", [True, False])
def test_upsert_elus_pose_le_mandat_rne_sur_la_fiche_senat(conn, pa_en_premier):
    """Constat du 21/11/2026 : `existants.setdefault` gardait la première des
    deux fiches de même clé. La fiche PA retirée d'un député passé au Sénat
    recevait donc les mandats RNE. Ils vont à la fiche SEN, quel que soit
    l'ordre de lecture, et ceux d'un cycle précédent sont ôtés de la PA."""
    fiches = [("PA1", [{"source": "AN-P9", "type": "depute"},
                       {"source": "RNE", "type": "senateur"}]),
              ("SEN-00001A", [{"source": "SENAT-P9", "type": "senateur"}])]
    for ident, mandats in (fiches if pa_en_premier else fiches[::-1]):
        _fiche_nee(conn, ident, "Valmont", "Lucien", "1971-03-14", mandats)
    rne = _rne_un_seul("VALMONT", "Lucien", "1971-03-14")
    p7.upsert_elus(conn, p7.preparer_personnes(rne), liste_blanche={},
                   passees={"PA1": "SEN-00001A"})
    sources = {i: [m["source"] for m in json.loads(m_)]
               for i, m_ in conn.execute("SELECT id, mandats FROM elus")}
    assert sources["PA1"] == ["AN-P9"]
    assert sources["SEN-00001A"][0] == "SENAT-P9" and "RNE" in sources["SEN-00001A"]


def test_hatvp_flag_refuse_un_homonyme_d_un_autre_departement(conn):
    """Constat du 15/10/2026 (cas relevé sur la base servie) : LEROY Gilles,
    maire de Courtrizy-et-Fussigny (02), recevait la fiche HATVP d'un
    vice-président du conseil départemental de Maine-et-Loire (49). Nom et
    prénom uniques des deux côtés : l'ancien code posait le flag."""
    _fiche(conn, "rne-leroy", "LEROY", "Gilles",
           [{"source": "RNE", "type": "maire", "departement": "02",
             "commune": "Courtrizy-Et-Fussigny"}])
    hatvp = [_dossier_hatvp("LEROY", "Gilles", "departement", "49",
                            "Vice-président du conseil départemental de Maine-et-Loire")]
    assert p7.croiser_hatvp_flag(conn, hatvp) == (0, 1)
    assert tuple(conn.execute("SELECT hatvp_flag, hatvp_url FROM elus"
                              " WHERE id = 'rne-leroy'").fetchone()) == (0, None)


def test_hatvp_flag_pose_quand_le_departement_concorde(conn):
    """Contre-épreuve : le même dossier, la fiche dans le 49 → flag."""
    _fiche(conn, "rne-leroy", "LEROY", "Gilles",
           [{"source": "RNE", "type": "maire", "departement": "49"}])
    hatvp = [_dossier_hatvp("LEROY", "Gilles", "departement", "49",
                            "Vice-président du conseil départemental de Maine-et-Loire")]
    assert p7.croiser_hatvp_flag(conn, hatvp) == (1, 0)


def test_hatvp_flag_concordance_par_chambre_et_par_nature(conn):
    """Français de l'étranger : « 99 » à la HATVP, « ZZ » au RNE, en toutes
    lettres à l'AN — la chambre suffit. Région sans département à la HATVP :
    la nature du mandat (présidence de région) suffit ; un maire, non."""
    _fiche(conn, "PA721004", "LAKRAFI", "Amélia",
           [{"source": "AN-P9", "type": "depute",
             "departement": "Français établis hors de France"},
            {"source": "RNE", "type": "depute", "departement": "ZZ"}])
    _fiche(conn, "rne-pcr", "PRESIDENTE", "Région",
           [{"source": "RNE", "type": "president_conseil_regional"}])
    _fiche(conn, "rne-maire", "MAIRE", "Ailleurs",
           [{"source": "RNE", "type": "maire", "departement": "87"}])
    hatvp = [
        _dossier_hatvp("LAKRAFI", "Amélia", "depute", "99", "Députée"),
        _dossier_hatvp("PRESIDENTE", "Région", "region", "",
                       "Présidente du conseil régional"),
        _dossier_hatvp("MAIRE", "Ailleurs", "region", "",
                       "Vice-président du conseil régional"),
    ]
    assert p7.croiser_hatvp_flag(conn, hatvp) == (2, 1)
    flags = dict(conn.execute("SELECT id, hatvp_flag FROM elus").fetchall())
    assert flags == {"PA721004": 1, "rne-pcr": 1, "rne-maire": 0}


def test_hatvp_flag_depute_au_departement_en_toutes_lettres(conn):
    """Cas réel relevé en relecture le 15/10/2026 : Melouka Hadj-Mimoune,
    députée du Rhône (PA794910), n'a à la HATVP qu'un dossier d'adjointe au
    maire de Villeurbanne, département « 69 ». Son mandat AN-P9 porte le NOM
    « Rhône » : sans le code écrit par P9, la concordance échouait et la
    députée perdait son lien HATVP."""
    mandat = {"type": "depute", "legislature": 17, "date_debut": "2024-07-07",
              "date_fin": None, "departement": "Rhône", "circonscription": "6",
              "groupe": "SOC", "source": "AN-P9"}
    hatvp = [_dossier_hatvp("HADJ-MIMOUNE", "Melouka", "commune", "69",
                            "Adjointe au maire de Villeurbanne",
                            classement="HADJ-MIMOUNE  Melouka19320")]
    _fiche(conn, "PA794910", "Hadj-Mimoune", "Melouka",
           [dict(mandat, code_departement="69")])
    assert p7.croiser_hatvp_flag(conn, hatvp) == (1, 0)
    # Mandat écrit avant le code (base d'avant ce correctif) : pas de
    # concordance — c'est le faux négatif, il disparaît au cycle P9 suivant.
    conn.execute("UPDATE elus SET mandats = ?", (json.dumps([mandat]),))
    assert p7.croiser_hatvp_flag(conn, hatvp) == (0, 1)


# Lignes réelles des fichiers RNE (conseillers régionaux) et HATVP du
# 15/10/2026, copiées telles quelles.
_CR_ENTETE = ("Code de la région;Libellé de la région;Code de la section départementale;"
              "Libellé de la section départementale;Nom de l'élu;Prénom de l'élu;Code sexe;"
              "Date de naissance;Code de la catégorie socio-professionnelle;"
              "Libellé de la catégorie socio-professionnelle;Date de début du mandat;"
              "Libellé de la fonction;Date de début de la fonction")
_CR_QUERNEZ = ("53;Bretagne;29;Finistère;QUERNEZ;Michaël;M;1971-01-11;85;Personne diverse "
               "sans activité professionnelle de moins de 60 ans (sauf retraité);2021-07-02;"
               "1er Vice-président du conseil régional;2021-07-02")


def _index_locaux_quernez(tmp_path):
    chemin = tmp_path / "rne_cr.csv"
    chemin.write_text(_CR_ENTETE + "\r\n" + _CR_QUERNEZ + "\r\n", encoding="utf-8")
    cr = p7.lire_rne(chemin, p7._COLS_BASE + ("Libellé de la fonction",))
    return p7.index_mandats_locaux({"cd": [], "cr": cr, "epci": []})


def test_hatvp_flag_corrobore_par_un_mandat_rne_de_la_meme_personne(conn, tmp_path):
    """Relecture du 15/10/2026 : sur 15 appariements écartés tirés au sort,
    14 désignaient vraisemblablement la bonne personne. Cas réel : QUERNEZ
    Michaël, maire de Quimperlé (29), déclare à la HATVP sa vice-présidence
    du conseil régional de Bretagne, SANS département. La fiche n'enregistre
    pas les mandats régionaux, mais le RNE des conseillers régionaux porte la
    même personne — même nom, prénom ET date de naissance."""
    _fiche(conn, "rne-9596fa92bf78518a", "QUERNEZ", "Michaël",
           [{"source": "RNE", "type": "maire", "departement": "29",
             "code_commune": "29233", "commune": "Quimperlé"}])
    conn.execute("UPDATE elus SET date_naissance = '1971-01-11'")
    hatvp = [_dossier_hatvp("QUERNEZ", "Michaël", "region", "",
                            "Vice-Président du conseil régional de Bretagne",
                            classement="quernezaaamichael7502")]
    assert p7.croiser_hatvp_flag(conn, hatvp) == (0, 1)        # sans l'index
    locaux = _index_locaux_quernez(tmp_path)
    assert p7.croiser_hatvp_flag(conn, hatvp, locaux) == (1, 0)
    # Contre-épreuve : une autre date de naissance, ce n'est plus la même
    # personne pour le RNE — on renonce.
    conn.execute("UPDATE elus SET date_naissance = '1971-01-12'")
    assert p7.croiser_hatvp_flag(conn, hatvp, locaux) == (0, 1)


def test_hatvp_flag_d_un_cycle_precedent_ne_survit_pas(conn):
    """Le flag était « jamais remis à 0 » : un flag posé à tort restait servi
    sur la base persistante même une fois l'appariement corrigé."""
    _fiche(conn, "rne-leroy", "LEROY", "Gilles",
           [{"source": "RNE", "type": "maire", "departement": "02"}])
    conn.execute("ALTER TABLE elus ADD COLUMN hatvp_url TEXT")  # comme un cycle passé
    conn.execute("UPDATE elus SET hatvp_flag = 1, hatvp_url ="
                 " 'https://www.hatvp.fr/pages_nominatives/leroy-1'")
    hatvp = [_dossier_hatvp("LEROY", "Gilles", "departement", "49",
                            "Vice-président du conseil départemental de Maine-et-Loire")]
    p7.croiser_hatvp_flag(conn, hatvp)
    assert tuple(conn.execute("SELECT hatvp_flag, hatvp_url FROM elus").fetchone()) == (0, None)


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
# Hygiène de liste.csv (docs/SCHEMA-DB.md, § « Conventions de valeurs »)
# ---------------------------------------------------------------------------


def _dossier(**surcharges):
    """Ligne HATVP minimale — toutes les colonnes, valeurs vides par défaut."""
    base = {c: "" for c in p7.COLONNES_HATVP}
    base.update(statut_publication="Livrée")
    base.update(surcharges)
    return base


def _non_deposee(**surcharges):
    return _dossier(statut_publication="Déclaration non déposée", type_document="di",
                    qualite="Maire de Saint-Martin", type_mandat="commune",
                    departement="974", **surcharges)


def _ecrire_nd(nominatives):
    conn = sqlite3.connect(":memory:")
    conn.executescript(p7.SCHEMA_P7.split("DROP TABLE")[0])
    lignes = p7.construire_alertes(nominatives, [], AUJOURD_HUI, "2026-08-14", "2026-08-11")
    p7.ecrire_alertes(conn, lignes, AUJOURD_HUI)
    return [r[0] for r in conn.execute("SELECT id FROM alertes ORDER BY id")]


def test_a1_nd_deux_homonymes_sans_url_ont_deux_identifiants():
    """Deux homonymes sans URL de dossier, même type de document : avant,
    `A1-ND-{nom}-di` deux fois, la clé primaire refusait la seconde et le
    pipeline HATVP tombait. `classement` les distingue."""
    a = _non_deposee(nom="HOARAU", prenom="Jean", classement="HOARAU Jean101")
    b = _non_deposee(nom="HOARAU", prenom="Jean", classement="HOARAU Jean202")
    assert _ecrire_nd([a, b]) == ["A1-ND-hoarau-jean101-di", "A1-ND-hoarau-jean202-di"]


def test_a1_nd_sans_classement_les_homonymes_ne_se_heurtent_pas():
    """Repli : ni `classement` ni URL. Chacun reçoit l'empreinte de sa ligne,
    la même quel que soit l'ordre de lecture."""
    a = _non_deposee(nom="HOARAU", prenom="Jean", date_publication="2026-05-02")
    b = _non_deposee(nom="HOARAU", prenom="Jean", date_publication="2026-06-03")
    ids = _ecrire_nd([a, b])
    assert len(ids) == 2 and all(i.startswith("A1-ND-hoarau-jean-di-") for i in ids)
    assert _ecrire_nd([b, a]) == ids


def test_a1_nd_l_identifiant_ne_change_pas_quand_l_url_parait():
    """L'URL du dossier publiée après coup ne change plus l'identifiant, donc
    plus la date de détection de l'alerte."""
    sans = _non_deposee(nom="GÂTÉ", prenom="Sylvie", classement="GÂTÉ Sylvie23162")
    avec = dict(sans, url_dossier="/pages_nominatives/gate-sylvie-23162")
    assert p7.identifiants_non_deposees([sans]) == p7.identifiants_non_deposees([avec]) \
        == ["A1-ND-gate-sylvie23162-di"]


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

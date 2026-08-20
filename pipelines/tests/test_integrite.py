"""Tests du pipeline P7 (ingest_integrite) : HATVP liste.csv × RNE.

Fixtures : extraits RÉELS des fichiers du 14/08/2026 (HATVP) et du 11/08/2026
(RNE) — voir fixtures/hatvp_extrait.csv et fixtures/rne_*_extrait.csv. Les deux
seules lignes construites (homonyme LEFEVRE, délai non écoulé CONTE) sont
assemblées à partir de lignes réelles (gabarit GUERZA + maires réels du RNE).

La règle A1 étant calée sur des dates réelles de 2026, les tests la jouent avec
`aujourd_hui = date(2026, 8, 19)` (date de l'épreuve réelle), jamais date.today().

Les tests réseau sont marqués `@pytest.mark.reseau` (désélection : -m "not reseau").
"""

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

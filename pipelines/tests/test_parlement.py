"""Tests du pipeline P9 Parlement.

Fixtures 100 % réelles (extraites des dumps du 19/08/2026, < 50 Ko chacune) :
- acteur_PA841605.json : fiche AMO10 complète d'un député en exercice ;
- scrutin_VTANR5L17V8434.json : dernier scrutin de la législature (21/07/2026),
  contient à la fois des listes de votants et un votant unique (dict) ;
- odsen_extrait.csv : lignes réelles d'ODSEN_GENERAL.csv, encodage ISO-8859-1
  et commentaires « % » conservés tels quels.

Le calcul du taux de participation est éprouvé sur un cas construit (c'est un
test de logique, pas une donnée affichée).
"""

import json
from pathlib import Path

import pytest

from pipelines import db
from pipelines import ingest_parlement as p9

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Parsing d'un acteur AN réel
# ---------------------------------------------------------------------------


def test_parser_acteur_reel():
    data = json.loads((FIXTURES / "acteur_PA841605.json").read_text("utf-8"))
    a = p9.parser_acteur(data)
    assert a["uid"] == "PA841605"
    assert a["nom"] == "Golliot"
    assert a["prenom"] == "Antoine"
    assert a["sexe"] == "M"
    assert a["date_naissance"] == "1985-08-13"
    # le lien HATVP vient du JSON AN lui-même (champ uri_hatvp)
    assert a["url_hatvp"].startswith("https://www.hatvp.fr/pages_nominatives/")
    # mandats actifs : député, groupe, commission
    assert a["groupe_ref"] == "PO845401"       # Rassemblement National
    assert a["commission_ref"] == "PO59048"    # commission des finances
    ass = a["assemblee"]
    assert ass["date_debut"] == "2024-07-07"
    assert ass["date_fin"] is None
    assert ass["departement"] == "Pas-de-Calais"
    assert ass["num_departement"] == "62"
    assert ass["num_circo"] == "5"


def test_parser_acteur_mandat_unique_en_dict():
    """Piège AN documenté : un mandat unique arrive en dict, pas en liste."""
    data = {"acteur": {
        "uid": {"#text": "PA000001"},
        "etatCivil": {"ident": {"civ": "Mme", "prenom": "A", "nom": "B"},
                      "infoNaissance": {"dateNais": "1970-01-01"}},
        "mandats": {"mandat": {
            "typeOrgane": "GP", "dateFin": None,
            "organes": {"organeRef": "PO999999"},
        }},
    }}
    a = p9.parser_acteur(data)
    assert a["groupe_ref"] == "PO999999"
    assert a["sexe"] == "F"


def test_parser_acteur_uri_hatvp_nil():
    """Piège réel (PA717161 dans l'AMO10 du 19/08/2026) : uri_hatvp absent
    arrive en dict-nil XML, pas en null JSON."""
    data = {"acteur": {
        "uid": {"#text": "PA717161"},
        "etatCivil": {"ident": {"civ": "M.", "prenom": "X", "nom": "Y"}},
        "uri_hatvp": {"@xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
                      "@xsi:nil": "true"},
        "mandats": {"mandat": []},
    }}
    a = p9.parser_acteur(data)
    assert a["url_hatvp"] is None


# ---------------------------------------------------------------------------
# Parsing d'un scrutin AN réel
# ---------------------------------------------------------------------------


def test_parser_scrutin_reel():
    data = json.loads(
        (FIXTURES / "scrutin_VTANR5L17V8434.json").read_text("utf-8"))
    meta, votes = p9.parser_scrutin(data)
    assert meta["uid"] == "VTANR5L17V8434"
    assert meta["numero"] == 8434
    assert meta["legislature"] == 17
    assert meta["date_scrutin"] == "2026-07-21"
    assert meta["sort"] == "adopté"
    assert meta["adopte"] == 1
    assert meta["type_vote"] == "scrutin public solennel"
    # totaux du décompte officiel
    assert (meta["pour"], meta["contre"], meta["abstentions"],
            meta["non_votants"]) == (276, 86, 2, 2)
    assert meta["nombre_votants"] == 364
    # votes nominaux : exprimés + non-votants déclarés
    assert len(votes) == 364 + 2
    par_position = {}
    for uid, position, delegation, cause in votes:
        assert uid.startswith("PA")
        par_position[position] = par_position.get(position, 0) + 1
    assert par_position == {"pour": 276, "contre": 86,
                            "abstention": 2, "nonVotant": 2}
    # le votant unique (dict, pas liste) est bien parcouru : les deux
    # non-votants de ce scrutin réel sont des blocs à un seul votant
    causes = {cause for _, pos, _, cause in votes if pos == "nonVotant"}
    assert causes == {"PAN", "PSE"}  # présidence AN / présidence de séance


# ---------------------------------------------------------------------------
# Décodage ISO-8859-1 du CSV Sénat
# ---------------------------------------------------------------------------


def test_lire_csv_senat_iso8859():
    octets = (FIXTURES / "odsen_extrait.csv").read_bytes()
    # le fichier réel n'est PAS de l'UTF-8 valide (accents ISO-8859-1)
    with pytest.raises(UnicodeDecodeError):
        octets.decode("utf-8")
    lignes = p9.lire_csv_senat(octets)
    assert lignes, "extrait vide"
    aesch = next(l for l in lignes if l["Nom usuel"] == "Aeschlimann")
    assert aesch["État"] == "ACTIF"
    assert aesch["Circonscription"] == "Hauts-de-Seine"
    # accent décodé correctement (é de « ministériels », ISO-8859-1)
    assert "ministériels" in aesch["PCS INSEE"]
    assert p9.nettoyer_date_senat(aesch["Date naissance"]) == "1974-04-17"
    # les lignes de commentaire % (requête SQL d'export) sont sautées
    assert all(not (l.get("Matricule") or "").startswith("%") for l in lignes)
    # un ANCIEN est présent dans l'extrait : le filtre d'état a du grain à moudre
    assert any(l["État"] == "ANCIEN" for l in lignes)


def test_url_fiche_senateur_motif_reel():
    # motifs vérifiés HTTP 200 le 19/08/2026
    assert p9.construire_url_senateur("Aeschlimann", "Marie-Do", "21071F") == \
        "https://www.senat.fr/senateur/aeschlimann_marie_do21071f.html"
    assert p9.construire_url_senateur("Kerrouche", "Éric", "19489J") == \
        "https://www.senat.fr/senateur/kerrouche_eric19489j.html"


# ---------------------------------------------------------------------------
# Taux de participation : cas construit
# ---------------------------------------------------------------------------


def test_calcul_participation_cas_construit():
    scrutins = [
        ("2026-01-10", {"PA1", "PA2"}),
        ("2026-02-10", {"PA1"}),
        ("2026-03-10", {"PA2", "PA3"}),
        ("2026-04-10", set()),
    ]
    debuts = {
        "PA1": "2025-07-01",   # éligible aux 4 scrutins, en a voté 2
        "PA2": "2025-07-01",   # éligible aux 4, en a voté 2
        "PA3": "2026-03-01",   # entré en cours de période : 2 éligibles, 1 voté
        "PA4": "2025-07-01",   # n'a jamais voté : 0/4
    }
    r = p9.calculer_participation(scrutins, debuts)
    assert r["PA1"] == (2, 4, 50.0)
    assert r["PA2"] == (2, 4, 50.0)
    assert r["PA3"] == (1, 2, 50.0)   # pas pénalisé des scrutins d'avant mandat
    assert r["PA4"] == (0, 4, 0.0)


def test_calcul_participation_sans_scrutin_eligible():
    r = p9.calculer_participation([("2026-01-10", {"PA1"})],
                                  {"PA9": "2026-06-01"})
    assert r["PA9"] == (0, 0, None)   # jamais de division par zéro ni de 0 % inventé


# ---------------------------------------------------------------------------
# Fusion des mandats dans elus (ne pas écraser les autres pipelines)
# ---------------------------------------------------------------------------


def test_upsert_elu_preserve_hatvp_flag_et_mandats(tmp_path):
    conn = db.init_db(chemin=tmp_path / "t.db")
    conn.executescript(p9._SCHEMA_P9)
    # un autre pipeline a déjà posé cet élu avec hatvp_flag et un mandat RNE
    conn.execute(
        "INSERT INTO elus (id, nom, uid_an, hatvp_flag, mandats)"
        " VALUES ('PA841605', 'GOLLIOT', 'PA841605', 1,"
        " '[{\"source\": \"RNE\", \"type\": \"conseiller\"}]')")
    conn.commit()
    p9.upsert_elu(
        conn, cle="uid_an", valeur_cle="PA841605", id_defaut="PA841605",
        nom="Golliot", prenom="Antoine", sexe="M",
        date_naissance="1985-08-13", profession="Technicien",
        mandat={"type": "depute", "legislature": 17},
        source_mandat="AN-P9",
    )
    ligne = conn.execute(
        "SELECT * FROM elus WHERE uid_an = 'PA841605'").fetchone()
    assert ligne["hatvp_flag"] == 1            # jamais écrasé par P9
    assert ligne["nom"] == "Golliot"
    mandats = json.loads(ligne["mandats"])
    sources = sorted(m["source"] for m in mandats)
    assert sources == ["AN-P9", "RNE"]         # fusion, pas remplacement
    # ré-upsert : idempotent, pas de doublon AN-P9
    p9.upsert_elu(
        conn, cle="uid_an", valeur_cle="PA841605", id_defaut="PA841605",
        nom="Golliot", prenom="Antoine", sexe="M",
        date_naissance="1985-08-13", profession="Technicien",
        mandat={"type": "depute", "legislature": 17},
        source_mandat="AN-P9",
    )
    mandats = json.loads(conn.execute(
        "SELECT mandats FROM elus WHERE uid_an = 'PA841605'"
    ).fetchone()["mandats"])
    assert len(mandats) == 2
    conn.close()


# ---------------------------------------------------------------------------
# Intégration réelle (réseau) : pipeline complet sur base jetable
# ---------------------------------------------------------------------------


@pytest.mark.reseau
def test_pipeline_complet_reel(tmp_path, monkeypatch):
    """Joue le pipeline entier contre les sources réelles (base jetable)."""
    chemin_db = tmp_path / "parlement_reseau.db"
    monkeypatch.setenv("FT_DB_PATH", str(chemin_db))
    code = p9.main()
    assert code == 0
    conn = db.connexion(chemin_db)
    n_dep = conn.execute("SELECT count(*) AS n FROM deputes").fetchone()["n"]
    n_sen = conn.execute("SELECT count(*) AS n FROM senateurs").fetchone()["n"]
    n_scr = conn.execute("SELECT count(*) AS n FROM scrutins").fetchone()["n"]
    assert n_dep == 577                      # sièges de l'AN, tous pourvus
    assert 300 <= n_sen <= 348               # 348 sièges (vacances possibles)
    assert n_scr >= 8434                     # au moins l'état du 19/08/2026
    metas = {r["source_id"] for r in conn.execute("SELECT source_id FROM meta_sources")}
    assert {"S5-AMO10", "S5-SCRUTINS", "S6-ODSEN", "S7-DATAN"} <= metas
    conn.close()

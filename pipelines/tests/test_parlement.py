"""Tests du pipeline P9 Parlement.

Fixtures 100 % réelles (extraites des dumps du 19/08/2026, < 50 Ko chacune) :
- acteur_PA841605.json : fiche AMO10 complète d'un député en exercice ;
- scrutin_VTANR5L17V8434.json : dernier scrutin de la législature (21/07/2026),
  contient à la fois des listes de votants et un votant unique (dict) ;
- odsen_extrait.csv : lignes réelles d'ODSEN_GENERAL.csv, encodage ISO-8859-1
  et commentaires « % » conservés tels quels ;
- dosleg_extrait.sql : COPY PostgreSQL `scr` + `votsen` au gabarit du dump
  Dosleg du 25/08/2026 (UTF-8, pas ISO-8859-1).

Le calcul du taux de participation est éprouvé sur un cas construit (c'est un
test de logique, pas une donnée affichée).
"""

import io
import json
import zipfile
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
# Dosleg : COPY PostgreSQL sans serveur
# ---------------------------------------------------------------------------


def test_decoder_champ_copy():
    assert p9.decoder_champ_copy(r"\N") is None
    assert p9.decoder_champ_copy("abc") == "abc"
    assert p9.decoder_champ_copy(r"a\tb") == "a\tb"
    assert p9.decoder_champ_copy(r"a\nb") == "a\nb"
    assert p9.decoder_champ_copy(r"a\\b") == r"a\b"
    assert p9.decoder_ligne_copy(b"1\t\\N\tpour") == ["1", None, "pour"]


def test_iterer_copy_saute_les_autres_tables():
    sql = (
        "COPY posvot (posvotcod, posvotlib) FROM stdin;\n"
        "1\tpour\n"
        "\\.\n"
        "COPY scr (sesann, scrnum, scrdat, scrpou, scrcon) FROM stdin;\n"
        "2025\t1\t2026-07-21 00:00:00\t10\t5\n"
        "\\.\n"
    )
    rows = list(p9.iterer_copy_postgres(io.BytesIO(sql.encode()), {"scr"}))
    assert len(rows) == 1
    table, row = rows[0]
    assert table == "scr"
    assert row["sesann"] == "2025"
    assert row["scrnum"] == "1"
    assert row["scrdat"].startswith("2026-07-21")


def _zip_dosleg(tmp_path: Path) -> Path:
    sql = (FIXTURES / "dosleg_extrait.sql").read_bytes()
    chemin = tmp_path / "dosleg.zip"
    with zipfile.ZipFile(chemin, "w") as z:
        z.writestr("dosleg.sql", sql)
    return chemin


def test_ingerer_dosleg_extrait(tmp_path, monkeypatch):
    """Ingestion d'un COPY réel (gabarit Dosleg) sur base jetable.

    Vérifie : tables nouvelles, pas d'écriture sur scrutins/votes_recents,
    mapping posvot, délégation, padding character(6), fenêtre 365 j,
    même formule de participation que l'AN.
    """
    conn = db.init_db(chemin=tmp_path / "t.db")
    conn.executescript(p9._SCHEMA_P9)
    conn.executemany(
        """INSERT INTO senateurs (matricule, nom, date_debut_mandat)
           VALUES (?, ?, ?)""",
        [
            ("21071F", "Aeschlimann", "2020-10-01"),
            ("19489J", "Kerrouche", "2020-10-01"),
            ("01008M", "Del", "2020-10-01"),
            ("98046X", "Nonvotant", "2020-10-01"),
            ("99999Z", "Absent", "2020-10-01"),
            ("88888Y", "Nouveau", "2026-08-01"),
        ],
    )
    conn.commit()
    zip_path = _zip_dosleg(tmp_path)
    monkeypatch.setattr(p9, "telecharger", lambda *a, **k: zip_path)
    p9.ingerer_dosleg(conn, session=None)

    n_scr = conn.execute("SELECT count(*) FROM scrutins_senat").fetchone()[0]
    assert n_scr == 4
    dernier = conn.execute(
        """SELECT sesann, numero, date_scrutin, pour, contre, abstentions,
                  suffrages_exprimes, nombre_votants, adopte, sort, titre
           FROM scrutins_senat
           ORDER BY date_scrutin DESC, sesann DESC, numero DESC"""
    ).fetchone()
    assert tuple(dernier)[:10] == (
        2025, 340, "2026-07-21", 214, 111, 20, 325, 345, 1, "adopté",
    )
    # U+0092 du dump → apostrophe ; abstentions = votants − exprimés
    assert "ordre public" in conn.execute(
        "SELECT titre FROM scrutins_senat WHERE numero = 338"
    ).fetchone()[0]
    assert "'" in conn.execute(
        "SELECT titre FROM scrutins_senat WHERE numero = 338"
    ).fetchone()[0]

    # Tables AN intactes
    assert conn.execute("SELECT count(*) FROM scrutins").fetchone()[0] == 0
    assert conn.execute("SELECT count(*) FROM votes_recents").fetchone()[0] == 0

    # 4 scrutins < 100 → tout le détail nominal est conservé
    n_vot = conn.execute("SELECT count(*) FROM votes_senat").fetchone()[0]
    assert n_vot == 12
    delg = conn.execute(
        """SELECT par_delegation, position FROM votes_senat
           WHERE matricule = '19489J' AND numero = 339"""
    ).fetchone()
    assert tuple(delg) == (1, "pour")
    # padding character(6) : '98046X ' → 98046X
    assert conn.execute(
        "SELECT count(*) FROM votes_senat WHERE matricule = '98046X'"
    ).fetchone()[0] == 2

    part = {
        r["matricule"]: (r["nb_votes_12m"], r["nb_scrutins_12m"],
                         r["taux_participation_12m"])
        for r in conn.execute("SELECT * FROM participation_senat")
    }
    # 3 scrutins dans la fenêtre (2026-07-21) ; 2024-01-10 hors 365 j
    assert part["21071F"] == (3, 3, 100.0)
    assert part["19489J"] == (3, 3, 100.0)          # délégation = exprimé
    assert part["01008M"] == (2, 3, 66.67)          # abstention compte, non-votant non
    assert part["98046X"] == (0, 3, 0.0)
    assert part["99999Z"] == (0, 3, 0.0)
    assert part["88888Y"] == (0, 0, None)           # entré après les scrutins

    meta = conn.execute(
        "SELECT source_id, date_donnees, lignes FROM meta_sources WHERE source_id = 'S6-DOSLEG'"
    ).fetchone()
    assert tuple(meta) == ("S6-DOSLEG", "2026-07-21", 4)
    notes = conn.execute(
        "SELECT notes FROM meta_sources WHERE source_id = 'S6-DOSLEG'"
    ).fetchone()[0].lower()
    assert "sondage" not in notes
    assert "baromètre" not in notes and "barometre" not in notes
    conn.close()


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
    assert {"S5-AMO10", "S5-SCRUTINS", "S6-ODSEN", "S6-DOSLEG", "S7-DATAN"} <= metas
    n_scr_sen = conn.execute("SELECT count(*) AS n FROM scrutins_senat").fetchone()["n"]
    assert n_scr_sen >= 4764
    conn.close()


# ---------------------------------------------------------------------------
# Garde-fou d'état civil : une valeur amont vide n'efface jamais la base
#
# Les trois sites d'écriture de P9 réécrivaient sans condition le nom, le
# prénom et la date de naissance de fiches EXISTANTES à chaque cycle :
# elus (UPDATE), deputes (ON CONFLICT DO UPDATE) et senateurs (INSERT OR
# REPLACE). Une valeur amont vide ou entièrement blanche effaçait donc une
# identité en silence — et c'est `deputes.nom` que le site affiche.
#
# Le cas de l'INSÉCABLE n'est pas théorique : `lire_csv_senat` décode ODSEN
# en ISO-8859-1, où l'octet 0xA0 EST U+00A0. Il est ici le test qui
# discrimine la normalisation Python d'un `TRIM` SQL, lequel ne coupe que
# l'espace ASCII 0x20 et laisserait donc passer l'effacement.
# ---------------------------------------------------------------------------


def _elu_seme(conn, **surcharges):
    """Fiche d'élu peuplée, telle qu'un cycle précédent l'a laissée."""
    champs = {"id": "PA841605", "nom": "Golliot", "prenom": "Antoine",
              "date_naissance": "1985-08-13", "uid_an": "PA841605"}
    champs.update(surcharges)
    colonnes = ", ".join(champs)
    conn.execute(f"INSERT INTO elus ({colonnes}) VALUES"
                 f" ({', '.join('?' * len(champs))})", tuple(champs.values()))
    conn.commit()


def _upsert(conn, **surcharges):
    appel = {"cle": "uid_an", "valeur_cle": "PA841605",
             "id_defaut": "PA841605", "nom": "Golliot", "prenom": "Antoine",
             "sexe": "M", "date_naissance": "1985-08-13",
             "profession": "Technicien",
             "mandat": {"type": "depute", "legislature": 17},
             "source_mandat": "AN-P9"}
    appel.update(surcharges)
    return p9.upsert_elu(conn, **appel)


def _etat_civil(conn, table="elus", cle="uid_an", valeur="PA841605"):
    colonnes = "nom, prenom" + (", date_naissance" if table != "deputes" else "")
    ligne = conn.execute(
        f"SELECT {colonnes} FROM {table} WHERE {cle} = ?", (valeur,)).fetchone()
    return None if ligne is None else tuple(ligne)


@pytest.mark.parametrize("vide", ["", "   ", "\xa0", " ", "\t\n", "\r", None])
def test_upsert_elu_refuse_effacer_le_nom(tmp_path, vide):
    """Aucune valeur amont vide, quel que soit le blanc, n'efface le nom."""
    conn = db.init_db(chemin=tmp_path / "t.db")
    conn.executescript(p9._SCHEMA_P9)
    _elu_seme(conn)
    bilan = _upsert(conn, nom=vide)
    assert _etat_civil(conn) == ("Golliot", "Antoine", "1985-08-13")
    assert bilan["preserves"] == 1        # le compteur VOIT le refus
    conn.close()


def test_upsert_elu_refuse_effacer_prenom_et_naissance(tmp_path):
    """prenom et date_naissance sont NULLABLES : un None les effaçait sans
    rien lever ni journaliser — l'effacement le plus silencieux des trois."""
    conn = db.init_db(chemin=tmp_path / "t.db")
    conn.executescript(p9._SCHEMA_P9)
    _elu_seme(conn)
    bilan = _upsert(conn, prenom=None, date_naissance="")
    assert _etat_civil(conn) == ("Golliot", "Antoine", "1985-08-13")
    assert bilan["preserves"] == 2
    conn.close()


def test_upsert_elu_laisse_passer_une_correction_de_graphie(tmp_path):
    """CONTRE-ÉPREUVE DU SILENCE : la garde ne doit pas geler la colonne.

    C'est la réécriture par P9 qui apporte la casse propre de l'AN par-dessus
    la graphie RNE en capitales. Une garde qui refuserait aussi les
    corrections légitimes éteindrait cette correction-là avec le défaut.
    """
    conn = db.init_db(chemin=tmp_path / "t.db")
    conn.executescript(p9._SCHEMA_P9)
    _elu_seme(conn, nom="GOLLIOT", prenom="ANTOINE")
    bilan = _upsert(conn, nom="Golliot-Dupont", prenom="Antoine",
                    date_naissance="1985-08-14")
    assert _etat_civil(conn) == ("Golliot-Dupont", "Antoine", "1985-08-14")
    assert bilan["preserves"] == 0        # le compteur sait aussi rendre ZÉRO
    conn.close()


def test_upsert_elu_ne_leve_pas_sur_fiche_neuve_sans_nom(tmp_path):
    """Refus par NON-ÉCRITURE, jamais par levée.

    elus.nom est NOT NULL et l'appel est dans le `with conn:` de l'appelant :
    une levée annulerait les 577 (ou 348) écritures du bloc, ferait rendre 1
    à main(), arrêterait make au 8e pipeline sur 31 et ne publierait RIEN de
    la nuit. Une fiche non créée est réparée par le cycle suivant.
    """
    conn = db.init_db(chemin=tmp_path / "t.db")
    conn.executescript(p9._SCHEMA_P9)
    bilan = _upsert(conn, valeur_cle="PA999999", id_defaut="PA999999", nom="")
    assert _etat_civil(conn, valeur="PA999999") is None
    assert bilan["refus_insertion"] == 1
    # la fiche saine du cycle suivant est bien créée : la garde n'est pas un gel
    bilan = _upsert(conn, valeur_cle="PA999999", id_defaut="PA999999",
                    nom="Dupont")
    assert _etat_civil(conn, valeur="PA999999") == (
        "Dupont", "Antoine", "1985-08-13")
    assert bilan["refus_insertion"] == 0
    conn.close()


def _zip_amo10(tmp_path, nom, prenom="Antoine"):
    """Zip AMO10 minimal bâti sur la fiche réelle PA841605, nom substitué."""
    data = json.loads((FIXTURES / "acteur_PA841605.json").read_text("utf-8"))
    ident = data["acteur"]["etatCivil"]["ident"]
    ident["nom"], ident["prenom"] = nom, prenom
    data["acteur"]["mandats"] = {"mandat": []}     # aucun organe à résoudre
    chemin = tmp_path / "amo10.zip"
    with zipfile.ZipFile(chemin, "w") as z:
        z.writestr("json/acteur/PA841605.json", json.dumps(data))
    return chemin


def test_ingerer_amo10_refuse_effacer_le_nom_servi(tmp_path, monkeypatch):
    """deputes.nom est ce que le SITE AFFICHE (queries/elus.ts:244,250).

    Une garde posée sur la seule table elus protégerait la clé de
    rattachement HATVP et laisserait le nom servi sans défense.
    """
    conn = db.init_db(chemin=tmp_path / "t.db")
    conn.executescript(p9._SCHEMA_P9)
    conn.execute("INSERT INTO deputes (uid_an, legislature, nom, prenom)"
                 " VALUES ('PA841605', ?, 'Golliot', 'Antoine')",
                 (p9.LEGISLATURE,))
    _elu_seme(conn)
    monkeypatch.setattr(p9, "_date_last_modified", lambda *a, **k: "2026-08-29")
    monkeypatch.setattr(p9, "telecharger",
                        lambda *a, **k: _zip_amo10(tmp_path, "\xa0", ""))
    p9.ingerer_amo10(conn, session=None)
    assert _etat_civil(conn, table="deputes") == ("Golliot", "Antoine")
    assert _etat_civil(conn) == ("Golliot", "Antoine", "1985-08-13")
    conn.close()


# Colonnes d'ODSEN_GENERAL, dans l'ordre réel de l'export du Sénat.
ODSEN_NOM, ODSEN_PRENOM, ODSEN_NAISSANCE = 2, 3, 5


def _csv_odsen(**substitutions: bytes) -> bytes:
    """ODSEN_GENERAL réel, colonnes du 1er ACTIF substituées (ISO-8859-1).

    Les octets passent tels quels : c'est ainsi qu'on met `b"\xa0"` dans le
    fichier, où il DEVIENDRA l'insécable U+00A0 au décodage ISO-8859-1.
    """
    index = {"nom": ODSEN_NOM, "prenom": ODSEN_PRENOM,
             "naissance": ODSEN_NAISSANCE}
    lignes = (FIXTURES / "odsen_extrait.csv").read_bytes().split(b"\n")
    for i, l in enumerate(lignes):
        if l.startswith(b"21071F,"):
            champs = l.rstrip(b"\r").split(b",")
            for cle, octets in substitutions.items():
                champs[index[cle]] = octets
            lignes[i] = b",".join(champs) + b"\r"
            break
    else:                                   # pragma: no cover - fixture figée
        raise AssertionError("ligne 21071F absente de la fixture ODSEN")
    return b"\n".join(lignes)


def _senat_jetable(tmp_path, monkeypatch, **substitutions):
    """Câble ingerer_senat sur des fichiers locaux, sans réseau."""
    general = tmp_path / "ODSEN_GENERAL.csv"
    general.write_bytes(_csv_odsen(**substitutions))
    elusen = tmp_path / "ODSEN_ELUSEN.csv"
    elusen.write_bytes(b"Matricule,Date de fin de mandat\r\n")
    monkeypatch.setattr(p9, "_date_last_modified", lambda *a, **k: "2026-08-29")
    monkeypatch.setattr(
        p9, "telecharger",
        lambda url, dest, **k: general if "GENERAL" in dest else elusen)


def _senateur_seme(conn):
    conn.execute("INSERT INTO senateurs (matricule, nom, prenom,"
                 " date_naissance) VALUES ('21071F', 'Aeschlimann',"
                 " 'Marie-Do', '1974-04-17')")
    conn.execute("INSERT INTO elus (id, nom, prenom, date_naissance,"
                 " matricule_senat) VALUES ('SEN-21071F', 'Aeschlimann',"
                 " 'Marie-Do', '1974-04-17', '21071F')")
    conn.commit()


def test_ingerer_senat_refuse_l_insecable_iso8859(tmp_path, monkeypatch):
    """L'octet 0xA0 d'un CSV Sénat EST l'insécable U+00A0 une fois décodé.

    C'est le cas qui distingue la normalisation Python d'un TRIM SQL : TRIM
    ne coupe que l'espace ASCII 0x20, laisse passer 0xA0, et remplacerait le
    patronyme par une insécable sans levée et sans journal.
    """
    conn = db.init_db(chemin=tmp_path / "t.db")
    conn.executescript(p9._SCHEMA_P9)
    _senateur_seme(conn)
    _senat_jetable(tmp_path, monkeypatch, nom=b"\xa0")
    p9.ingerer_senat(conn, session=None)
    assert _etat_civil(conn, "senateurs", "matricule", "21071F") == (
        "Aeschlimann", "Marie-Do", "1974-04-17")
    assert _etat_civil(conn, "elus", "matricule_senat", "21071F") == (
        "Aeschlimann", "Marie-Do", "1974-04-17")
    conn.close()


def test_valeur_amont_ne_convertit_pas_ce_qui_n_est_pas_du_texte():
    """Une garde ne doit pas remplacer une levée bruyante par une valeur
    fausse et muette.

    `_texte` ne démêle que les dicts : une LISTE de l'amont AN traverse. Avant
    cette garde, sqlite3 levait au bind. Convertir en `str` écrirait un repr
    Python dans la colonne affichée, sans que personne ne le voie jamais.
    """
    assert p9.valeur_amont(" Golliot ") == "Golliot"
    assert p9.valeur_amont("\xa0") is None
    assert p9.valeur_amont(None) is None
    for brut in (False, True, 0, b"Ok", ["A", "B"], {"a": 1}):
        assert p9.valeur_amont(brut) is brut      # rendu INCHANGÉ


def test_preserver_ne_compte_pas_une_preservation_qui_n_a_rien_sauve():
    """CONTRE-ÉPREUVE DU MENSONGE DU COMPTEUR.

    Une base laissée par un cycle d'AVANT cette garde peut porter `''`.
    Compter une « préservation » du vide ferait lire « la garde a agi » à un
    exploitant dont le nom servi est resté vide.
    """
    etat, n = p9.preserver_etat_civil(
        {"nom": "", "prenom": ""}, {"nom": "", "prenom": ""},
        p9.ETAT_CIVIL_DEPUTES)
    assert etat == {"nom": "", "prenom": ""}      # statu quo, rien d'écrasé
    assert n == 0                                 # et RIEN de compté
    # contre-épreuve du positif : le compteur sait rendre du non-nul
    etat, n = p9.preserver_etat_civil(
        {"nom": "", "prenom": ""}, {"nom": "Golliot", "prenom": "Antoine"},
        p9.ETAT_CIVIL_DEPUTES)
    assert etat == {"nom": "Golliot", "prenom": "Antoine"} and n == 2


def test_preserver_tolere_une_colonne_absente_de_la_projection():
    """Une projection désynchronisée ne doit pas LEVER dans le `with conn:`.

    Le coût d'une levée ici serait le rollback des 577 (ou 348) écritures et
    la nuit non publiée ; ce sont les tests des trois sites qui verrouillent
    la concordance, pas une exception en production.
    """
    etat, n = p9.preserver_etat_civil(
        {"nom": "", "date_naissance": ""}, {"nom": "Golliot"},
        p9.ETAT_CIVIL_ELUS)
    assert etat["nom"] == "Golliot" and etat["date_naissance"] is None
    assert n == 1


def test_upsert_elu_ne_saute_jamais_une_fiche_existante(tmp_path):
    """Le refus par non-écriture ne peut PAS priver une fiche existante de sa
    mise à jour de mandats. `nom` étant NOT NULL, la valeur préservée d'une
    ligne existante n'est jamais vide : le chemin de refus n'est atteignable
    que sur une fiche NEUVE. Éprouvé plutôt que déduit."""
    conn = db.init_db(chemin=tmp_path / "t.db")
    conn.executescript(p9._SCHEMA_P9)
    _elu_seme(conn)
    bilan = _upsert(conn, nom="\xa0", prenom="", date_naissance=None,
                    mandat={"type": "depute", "legislature": 18})
    assert bilan["refus_insertion"] == 0 and bilan["preserves"] == 3
    ligne = conn.execute(
        "SELECT nom, mandats FROM elus WHERE uid_an = 'PA841605'").fetchone()
    assert ligne["nom"] == "Golliot"
    assert json.loads(ligne["mandats"])[0]["legislature"] == 18
    conn.close()


def test_ingerer_amo10_met_a_jour_elus_meme_si_deputes_est_refuse(tmp_path,
                                                                  monkeypatch):
    """Le refus d'écrire dans `deputes` ne doit pas emporter la fiche `elus`.

    Cas atteignable : `deputes` est purgée chaque nuit par le
    `DELETE … NOT IN`, `elus` ne l'est jamais. Un député absent un jour et
    revenu le lendemain avec un nom vide a donc une fiche `elus` mais pas de
    ligne `deputes` — ses mandats doivent quand même être fusionnés.
    """
    conn = db.init_db(chemin=tmp_path / "t.db")
    conn.executescript(p9._SCHEMA_P9)
    _elu_seme(conn)                       # elus existe, deputes ABSENT
    monkeypatch.setattr(p9, "_date_last_modified", lambda *a, **k: "2026-08-29")
    monkeypatch.setattr(p9, "telecharger",
                        lambda *a, **k: _zip_amo10(tmp_path, "", ""))
    p9.ingerer_amo10(conn, session=None)
    ligne = conn.execute("SELECT nom, mandats FROM elus"
                         " WHERE uid_an = 'PA841605'").fetchone()
    assert ligne["nom"] == "Golliot"                       # non effacé
    assert "AN-P9" in ligne["mandats"]                     # et MIS À JOUR
    conn.close()


def test_ingerer_amo10_ne_laisse_pas_un_depute_sans_fiche_elus(tmp_path,
                                                               monkeypatch):
    """`queries/elus.ts:244` joint `deputes` à `elus` en JOINTURE INTERNE.

    Un député écrit dans `deputes` mais refusé dans `elus` disparaîtrait de
    la liste servie. Quand le nom est connu de `deputes`, il doit servir aussi
    à créer la fiche `elus`.
    """
    conn = db.init_db(chemin=tmp_path / "t.db")
    conn.executescript(p9._SCHEMA_P9)
    conn.execute("INSERT INTO deputes (uid_an, legislature, nom, prenom)"
                 " VALUES ('PA841605', ?, 'Golliot', 'Antoine')",
                 (p9.LEGISLATURE,))
    conn.commit()                          # deputes existe, elus ABSENT
    monkeypatch.setattr(p9, "_date_last_modified", lambda *a, **k: "2026-08-29")
    monkeypatch.setattr(p9, "telecharger",
                        lambda *a, **k: _zip_amo10(tmp_path, "\xa0", ""))
    p9.ingerer_amo10(conn, session=None)
    assert _etat_civil(conn, table="deputes") == ("Golliot", "Antoine")
    ligne = conn.execute(
        "SELECT nom FROM elus WHERE uid_an = 'PA841605'").fetchone()
    assert ligne is not None and ligne["nom"] == "Golliot"
    conn.close()


def test_ingerer_amo10_laisse_passer_une_correction_sur_le_nom_servi(
        tmp_path, monkeypatch):
    """CONTRE-ÉPREUVE DU GEL sur `deputes` — la table que le site AFFICHE.

    Sans ce test, la colonne pourrait être rendue write-once sans qu'un seul
    test ne rougisse : c'est exactement le coût que le projet a refusé.
    """
    conn = db.init_db(chemin=tmp_path / "t.db")
    conn.executescript(p9._SCHEMA_P9)
    conn.execute("INSERT INTO deputes (uid_an, legislature, nom, prenom)"
                 " VALUES ('PA841605', ?, 'GOLLIOT', 'ANTOINE')",
                 (p9.LEGISLATURE,))
    _elu_seme(conn, nom="GOLLIOT", prenom="ANTOINE")
    monkeypatch.setattr(p9, "_date_last_modified", lambda *a, **k: "2026-08-29")
    monkeypatch.setattr(p9, "telecharger",
                        lambda *a, **k: _zip_amo10(tmp_path, "Golliot"))
    p9.ingerer_amo10(conn, session=None)
    assert _etat_civil(conn, table="deputes") == ("Golliot", "Antoine")
    assert _etat_civil(conn)[:2] == ("Golliot", "Antoine")
    conn.close()


def test_ingerer_amo10_journalise_le_compte_meme_a_zero(tmp_path, monkeypatch,
                                                        caplog):
    """Un contrôle muet au vert est indiscernable d'un contrôle débranché."""
    conn = db.init_db(chemin=tmp_path / "t.db")
    conn.executescript(p9._SCHEMA_P9)
    monkeypatch.setattr(p9, "_date_last_modified", lambda *a, **k: "2026-08-29")
    monkeypatch.setattr(p9, "telecharger",
                        lambda *a, **k: _zip_amo10(tmp_path, "Golliot"))
    with caplog.at_level("INFO"):
        p9.ingerer_amo10(conn, session=None)
    bilan = [m for m in caplog.messages if m.startswith("AMO10 :") and "état civil" in m]
    assert bilan and "0 champ(s) préservé(s) sur deputes, 0 sur elus" in bilan[0]
    assert "0 fiche(s) deputes et 0 fiche(s) elus non écrite(s)" in bilan[0]
    # contre-épreuve du positif : le même bilan sait rendre du NON-nul
    caplog.clear()
    monkeypatch.setattr(p9, "telecharger",
                        lambda *a, **k: _zip_amo10(tmp_path, "\xa0", ""))
    with caplog.at_level("INFO"):
        p9.ingerer_amo10(conn, session=None)
    bilan = [m for m in caplog.messages if m.startswith("AMO10 :") and "état civil" in m]
    assert bilan and "2 champ(s) préservé(s) sur deputes" in bilan[0]
    conn.close()


def test_ingerer_senat_refuse_effacer_la_date_de_naissance(tmp_path,
                                                           monkeypatch):
    """`Date naissance` vide : la route la plus exposée, sur le champ le plus
    silencieux. Une ligne ODSEN tronquée APRÈS `État` passe le filtre `actifs`
    et livre `Date naissance = None` — `date_naissance` étant nullable, elle
    passait à NULL sans levée et sans trace."""
    conn = db.init_db(chemin=tmp_path / "t.db")
    conn.executescript(p9._SCHEMA_P9)
    _senateur_seme(conn)
    _senat_jetable(tmp_path, monkeypatch, naissance=b"")
    p9.ingerer_senat(conn, session=None)
    assert _etat_civil(conn, "senateurs", "matricule", "21071F") == (
        "Aeschlimann", "Marie-Do", "1974-04-17")
    assert _etat_civil(conn, "elus", "matricule_senat", "21071F") == (
        "Aeschlimann", "Marie-Do", "1974-04-17")
    conn.close()


def test_ingerer_senat_laisse_passer_une_correction(tmp_path, monkeypatch):
    """CONTRE-ÉPREUVE DU GEL sur `senateurs` et sur la fiche `elus` liée."""
    conn = db.init_db(chemin=tmp_path / "t.db")
    conn.executescript(p9._SCHEMA_P9)
    conn.execute("INSERT INTO senateurs (matricule, nom, prenom,"
                 " date_naissance) VALUES ('21071F', 'AESCHLIMANN', 'M.-D.',"
                 " '1900-01-01')")
    conn.execute("INSERT INTO elus (id, nom, prenom, date_naissance,"
                 " matricule_senat) VALUES ('SEN-21071F', 'AESCHLIMANN',"
                 " 'M.-D.', '1900-01-01', '21071F')")
    conn.commit()
    _senat_jetable(tmp_path, monkeypatch)          # fixture non modifiée
    p9.ingerer_senat(conn, session=None)
    assert _etat_civil(conn, "senateurs", "matricule", "21071F") == (
        "Aeschlimann", "Marie-Do", "1974-04-17")
    assert _etat_civil(conn, "elus", "matricule_senat", "21071F") == (
        "Aeschlimann", "Marie-Do", "1974-04-17")
    conn.close()


def test_ingerer_senat_journalise_le_compte_meme_a_zero(tmp_path, monkeypatch,
                                                        caplog):
    conn = db.init_db(chemin=tmp_path / "t.db")
    conn.executescript(p9._SCHEMA_P9)
    _senateur_seme(conn)
    _senat_jetable(tmp_path, monkeypatch)
    with caplog.at_level("INFO"):
        p9.ingerer_senat(conn, session=None)
    bilan = [m for m in caplog.messages if m.startswith("Sénat :") and "état civil" in m]
    assert bilan and "0 champ(s) préservé(s) sur senateurs, 0 sur elus" in bilan[0]
    assert "0 fiche(s) senateurs et 0 fiche(s) elus non écrite(s)" in bilan[0]
    caplog.clear()
    _senat_jetable(tmp_path, monkeypatch, nom=b"\xa0", naissance=b"")
    with caplog.at_level("INFO"):
        p9.ingerer_senat(conn, session=None)
    bilan = [m for m in caplog.messages if m.startswith("Sénat :") and "état civil" in m]
    assert bilan and "2 champ(s) préservé(s) sur senateurs" in bilan[0]
    conn.close()


def test_ingerer_senat_ne_leve_pas_sur_nom_vide_du_csv(tmp_path, monkeypatch):
    """`senateurs.nom` est NOT NULL et l'`INSERT OR REPLACE` est dans le
    `with conn:`. Un CSV ne peut rendre que `''` : le cas est atteignable, et
    il ne doit ni lever ni emporter les AUTRES sénateurs."""
    conn = db.init_db(chemin=tmp_path / "t.db")
    conn.executescript(p9._SCHEMA_P9)
    _senat_jetable(tmp_path, monkeypatch, nom=b"")
    p9.ingerer_senat(conn, session=None)           # ne lève pas
    assert conn.execute("SELECT count(*) FROM senateurs WHERE matricule ="
                        " '21071F'").fetchone()[0] == 0
    assert conn.execute("SELECT count(*) FROM senateurs").fetchone()[0] >= 1
    assert conn.execute("SELECT count(*) FROM meta_sources WHERE source_id ="
                        " 'S6-ODSEN'").fetchone()[0] == 1
    conn.close()


def test_ingerer_amo10_ne_leve_pas_sur_nom_nul_de_l_an(tmp_path, monkeypatch):
    """`_texte()` rend None sur un dict-nil {'@xsi:nil': 'true'} — cas
    constaté sur `uri_hatvp` d'un acteur réel. Avant ce correctif, un seul
    None dans le JSON de l'AN annulait les 577 écritures du `with conn:`,
    faisait rendre 1 à main(), arrêtait make au 8e pipeline sur 31 et ne
    publiait RIEN de la nuit."""
    conn = db.init_db(chemin=tmp_path / "t.db")
    conn.executescript(p9._SCHEMA_P9)
    data = json.loads((FIXTURES / "acteur_PA841605.json").read_text("utf-8"))
    data["acteur"]["etatCivil"]["ident"]["nom"] = {"@xsi:nil": "true"}
    data["acteur"]["mandats"] = {"mandat": []}
    chemin = tmp_path / "nil.zip"
    with zipfile.ZipFile(chemin, "w") as z:
        z.writestr("json/acteur/PA841605.json", json.dumps(data))
    monkeypatch.setattr(p9, "_date_last_modified", lambda *a, **k: "2026-08-29")
    monkeypatch.setattr(p9, "telecharger", lambda *a, **k: chemin)
    p9.ingerer_amo10(conn, session=None)           # ne lève pas
    assert conn.execute("SELECT count(*) FROM deputes").fetchone()[0] == 0
    assert conn.execute("SELECT count(*) FROM elus").fetchone()[0] == 0
    assert conn.execute("SELECT count(*) FROM meta_sources WHERE source_id ="
                        " 'S5-AMO10'").fetchone()[0] == 1
    conn.close()


def test_upsert_elu_normalise_aussi_a_l_insertion_d_une_fiche_neuve(tmp_path):
    """La normalisation vaut à l'INSERT autant qu'à l'UPDATE.

    Sur une fiche neuve il n'y a rien à préserver, mais il y a à nettoyer :
    un `prenom` vide doit entrer en NULL, pas en `''` — sinon la garde du
    cycle SUIVANT verra une valeur « déjà en base » qu'elle ne pourra pas
    préserver, et la colonne restera vide sans que rien ne le signale.
    """
    conn = db.init_db(chemin=tmp_path / "t.db")
    conn.executescript(p9._SCHEMA_P9)
    bilan = _upsert(conn, valeur_cle="PA999999", id_defaut="PA999999",
                    nom="  Dupont  ", prenom="", date_naissance="\xa0")
    assert bilan == {"preserves": 0, "refus_insertion": 0}
    assert _etat_civil(conn, valeur="PA999999") == ("Dupont", None, None)
    conn.close()

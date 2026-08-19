"""Tests P10 financement (CNCCFP) : décodage réel, nettoyage, alertes, intégration.

Les fixtures sont des EXTRAITS OCTET POUR OCTET des fichiers publiés
(data.gouv.fr, téléchargés le 19/08/2026) :
- extrait-comptes-campagne-legislatives-2024.csv : cp1252 + CRLF, 6 lignes de
  garde, 10 candidats couvrant les décisions A/AR/ARM/R/AD/HD/DD, 2 lignes à
  mojibake réel (« ErgÃ¼n », « DÃ” ») et 1 nuance placeholder ;
- extrait-comptes-partis-2024.csv : UTF-8 BOM, 6 partis dont RN (résultat
  négatif), MDC (sigle) et ENSEMBLE ! (aide publique ≈ 100 % des produits) ;
- extrait-comptes-partis-2023.csv : 4 partis dont 2 en XPF et 1 sans unité.
"""

from pathlib import Path

import pytest

from pipelines import db
from pipelines import ingest_financement as fin

FIXTURES = Path(__file__).parent / "fixtures"
FIX_CAMPAGNES = FIXTURES / "extrait-comptes-campagne-legislatives-2024.csv"
FIX_PARTIS_2024 = FIXTURES / "extrait-comptes-partis-2024.csv"
FIX_PARTIS_2023 = FIXTURES / "extrait-comptes-partis-2023.csv"


@pytest.fixture()
def conn(tmp_path):
    """Base jetable initialisée (noyau + tables P10)."""
    c = db.init_db(chemin=tmp_path / "test_financement.db")
    fin.creer_tables(c)
    yield c
    c.close()


# ---------------------------------------------------------------------------
# Décodage et nettoyage — comptes de campagne (fixture réelle)
# ---------------------------------------------------------------------------


def test_fixture_campagnes_nest_pas_de_l_utf8():
    """Le fichier publié n'est PAS de l'UTF-8 (constat, pas une hypothèse)."""
    with pytest.raises(UnicodeDecodeError):
        FIX_CAMPAGNES.read_bytes().decode("utf-8")


def test_decodage_campagnes_retient_cp1252():
    texte, encodage = fin.decoder_campagnes(FIX_CAMPAGNES.read_bytes())
    assert encodage == "cp1252"
    assert "candidat;nom;scrutin" in texte


def test_parser_campagnes_saute_les_lignes_de_garde():
    lignes = fin.parser_campagnes(FIX_CAMPAGNES.read_bytes())
    # 10 candidats dans la fixture, aucune ligne de garde ingérée.
    assert len(lignes) == 10
    assert all(l["candidat_id"].isdigit() for l in lignes)


def test_parser_campagnes_valeurs_reelles():
    lignes = fin.parser_campagnes(FIX_CAMPAGNES.read_bytes())
    breton = next(l for l in lignes if l["candidat_id"] == "202408090")
    assert breton["nom"] == "M. BRETON Xavier"
    assert breton["circonscription"] == "Ain - 1re circonscription"
    assert breton["code_departement"] == "1"
    assert breton["nuance"] == "Les Républicains"
    assert breton["depenses_declarees"] == 21571.0
    assert breton["depenses_retenues"] == 21571.0
    assert breton["recettes_declarees"] == 21571.0
    assert breton["remboursement_etat"] == 838.0
    assert breton["decision"] == "A"
    assert breton["decision_famille"] == "approuve"
    # Réformation à la hausse constatée : retenu > déclaré.
    gueraud = next(l for l in lignes if l["candidat_id"] == "202408091")
    assert gueraud["decision"] == "AR"
    assert gueraud["depenses_declarees"] == 5274.0
    assert gueraud["depenses_retenues"] == 6416.0


def test_parser_campagnes_repare_le_mojibake():
    lignes = fin.parser_campagnes(FIX_CAMPAGNES.read_bytes())
    noms = [l["nom"] for l in lignes]
    assert any("Ergün" in n for n in noms)          # « ErgÃ¼n » réparé
    assert any("DÔ" in n for n in noms)             # « DÃ” » réparé
    for l in lignes:
        for v in l.values():
            assert "Ã" not in str(v)


def test_parser_campagnes_neutralise_le_placeholder_nuance():
    lignes = fin.parser_campagnes(FIX_CAMPAGNES.read_bytes())
    leboucher = next(l for l in lignes if l["candidat_id"] == "202407962")
    assert leboucher["nuance"] is None  # « Choisir une nuance déjà enregistrée... »


def test_parser_campagnes_exige_l_entete():
    with pytest.raises(ValueError, match="en-tête"):
        fin.parser_campagnes("pas;un;fichier;cnccfp\n1;2;3;4\n".encode("cp1252"))


# ---------------------------------------------------------------------------
# Nettoyage bas niveau
# ---------------------------------------------------------------------------


def test_montant():
    assert fin.montant("21571") == 21571.0
    assert fin.montant("31609023,7") == 31609023.7
    assert fin.montant("12 345") == 12345.0        # espace insécable U+00A0
    assert fin.montant("-516005") == -516005.0
    assert fin.montant("-") is None                 # marqueur d'absence CNCCFP
    assert fin.montant("") is None
    assert fin.montant("  ") is None
    with pytest.raises(ValueError):
        fin.montant("n.c.")


def test_famille_decision():
    attendu = {
        "A": "approuve", "AM": "approuve",
        "AR": "approuve_apres_reformation", "ARM": "approuve_apres_reformation",
        "ARR": "approuve_apres_reformation", "ARRR": "approuve_apres_reformation",
        "ARRRM": "approuve_apres_reformation",
        "R": "rejete", "AD": "absence_depot", "HD": "hors_delai",
        "DD": "dispense_depot", "": "autre",
    }
    for code, famille in attendu.items():
        assert fin.famille_decision(code) == famille, code


def test_extraire_sigle():
    assert fin.extraire_sigle("MOUVEMENT DES CITOYENS (MDC)") == "MDC"
    assert fin.extraire_sigle("ENSEMBLE ! (MAJORITÉ PRÉSIDENTIELLE)") is None  # trop long
    assert fin.extraire_sigle("RASSEMBLEMENT NATIONAL") is None
    assert fin.extraire_sigle("L'ÉVEIL OCÉANIEN (LE'O)") == "LE'O"


def test_reparer_mojibake():
    assert fin.reparer_mojibake("M. TOPARSLAN ErgÃ¼n") == "M. TOPARSLAN Ergün"
    assert fin.reparer_mojibake("déjÃ\xa0 enregistrée") == "déjà enregistrée"
    assert fin.reparer_mojibake("Ain - 1re circonscription") == "Ain - 1re circonscription"


# ---------------------------------------------------------------------------
# Comptes des partis (fixtures réelles)
# ---------------------------------------------------------------------------


def test_parser_partis_valeurs_reelles():
    lignes = fin.parser_partis(FIX_PARTIS_2024.read_bytes(), 2024)
    assert len(lignes) == 6
    rn = next(l for l in lignes if l["code"] == "40")
    assert rn["nom"] == "RASSEMBLEMENT NATIONAL"
    assert rn["unite"] == "EUR"
    assert rn["cotisations_adherents"] == 3071583.0
    assert rn["cotisations_elus"] == 1007630.0
    assert rn["aide_publique_f1"] == 6797831.0
    assert rn["aide_publique_f2"] == 3377855.0
    assert rn["autres_aides_publiques"] == 0.0
    assert rn["dons"] == 1030789.0
    assert rn["contributions_recues"] == 0.0
    assert rn["produits_total"] == 18704246.0
    assert rn["charges_total"] == 19220251.0
    assert rn["resultat"] == -516005.0


def test_parser_partis_refuse_un_fichier_sans_le_millesime_attendu():
    with pytest.raises(ValueError, match="aucune ligne datée 2023"):
        fin.parser_partis(FIX_PARTIS_2024.read_bytes(), 2023)


def test_charger_partis_dedoublonne_les_couples_code_exercice(conn):
    """Cas réel du corpus : un même (code, exercice) publié dans deux fichiers
    (code 671, exercice 2022, montants différents) → la publication dédiée à
    l'exercice gagne, l'autre ligne est écartée."""
    lignes_2024 = fin.parser_partis(FIX_PARTIS_2024.read_bytes(), 2024)
    rn = next(l for l in lignes_2024 if l["code"] == "40")
    doublon_hors_millesime = dict(rn, millesime=2023)  # même code, même exercice
    nb_partis, nb_comptes = fin.charger_partis(
        conn, {2023: [doublon_hors_millesime], 2024: lignes_2024}
    )
    assert nb_comptes == len(lignes_2024)  # le doublon n'a pas produit de ligne
    garde = conn.execute(
        "SELECT produits_total FROM partis_comptes WHERE parti_id = 'PARTI-40'"
    ).fetchall()
    assert len(garde) == 1
    assert garde[0]["produits_total"] == rn["produits_total"]


def test_charger_partis_referentiel_et_unites(conn):
    comptes = {
        2023: fin.parser_partis(FIX_PARTIS_2023.read_bytes(), 2023),
        2024: fin.parser_partis(FIX_PARTIS_2024.read_bytes(), 2024),
    }
    nb_partis, nb_comptes = fin.charger_partis(conn, comptes)
    assert nb_comptes == 10  # 4 lignes 2023 + 6 lignes 2024
    assert nb_partis == 10   # codes tous distincts entre les deux extraits
    # sigle extrait, lien entites posé
    mdc = conn.execute("SELECT * FROM partis WHERE sigle = 'MDC'").fetchone()
    assert mdc is not None
    ent = conn.execute(
        "SELECT type, nom FROM entites WHERE id = ?", (mdc["id"],)
    ).fetchone()
    assert ent["type"] == "parti"
    assert ent["nom"] == mdc["nom"]
    # les lignes XPF sont conservées telles quelles en table…
    assert conn.execute(
        "SELECT COUNT(*) AS n FROM partis_comptes WHERE unite = 'XPF'"
    ).fetchone()["n"] == 2
    # … mais exclues des agrégats en euros
    fin.creer_vues(conn)
    evolution = {
        r["exercice"]: r
        for r in conn.execute("SELECT * FROM v_partis_aide_publique_evolution")
    }
    nb_eur_2023 = conn.execute(
        "SELECT COUNT(*) AS n FROM partis_comptes WHERE exercice = 2023 AND unite = 'EUR'"
    ).fetchone()["n"]
    assert nb_eur_2023 == 1  # PS seul (Force du 13 : unité vide, 2 XPF)
    # idempotence : rejouer ne duplique rien
    fin.charger_partis(conn, comptes)
    assert conn.execute("SELECT COUNT(*) AS n FROM partis_comptes").fetchone()["n"] == 10
    assert evolution  # la vue répond


# ---------------------------------------------------------------------------
# Règles d'alerte (A4, A5) sur données réelles
# ---------------------------------------------------------------------------


def test_alertes_campagnes_et_partis(conn):
    fin.charger_campagnes(conn, fin.parser_campagnes(FIX_CAMPAGNES.read_bytes()))
    fin.charger_partis(
        conn, {2024: fin.parser_partis(FIX_PARTIS_2024.read_bytes(), 2024)}
    )
    # une alerte d'un autre pipeline doit survivre au recalcul
    conn.execute(
        """INSERT INTO alertes (id, type, gravite, titre, regle, date_calcul)
           VALUES ('X-1', 'autre_pipeline', 'info', 't', 'r', '2026-08-19T00:00:00+00:00')"""
    )
    conn.commit()

    nb = fin.calculer_alertes(conn, "https://exemple.invalid/avis-2024.pdf")
    alertes = {
        r["id"]: r for r in conn.execute("SELECT * FROM alertes")
    }

    # A5 — rejet : KOUASSI (décision R), gravité haute
    rejet = alertes["FIN-CAMP-REJ-202409066"]
    assert rejet["type"] == "financement_campagne_rejetee"
    assert rejet["gravite"] == "haute"
    assert "KOUASSI" in rejet["titre"]
    assert rejet["base_legale"].startswith("Code électoral")
    # A5 — réformés : AR (GUERAUD, DÔ, LEBOUCHER) + ARM (PRIé) = 4
    reformes = [a for a in alertes.values() if a["type"] == "financement_campagne_reformee"]
    assert len(reformes) == 4
    assert "écart" in alertes["FIN-CAMP-REF-202408091"]["detail"]
    # DD / AD / HD ne déclenchent pas l'alerte A5
    assert not any("202408093" in i for i in alertes)  # DD
    assert not any("202407468" in i for i in alertes)  # AD
    # A4 calculable — ENSEMBLE ! financé ~100 % par l'aide publique
    deps = [a for a in alertes.values() if a["type"] == "financement_parti_dependance_aide"]
    assert any("ENSEMBLE !" in a["titre"] for a in deps)
    assert all(a["gravite"] == "info" for a in deps)
    # RN : 10,2 M€ d'aide pour 18,7 M€ de produits (54 %) → PAS d'alerte
    assert not any("RASSEMBLEMENT NATIONAL" in a["titre"] for a in deps)
    # A4 documentaire — liste des privés d'aide en PDF seulement
    prive = alertes["FIN-PARTI-PRIVE-2024"]
    assert prive["type"] == "financement_parti_prive_aide"
    assert prive["source_url"] == "https://exemple.invalid/avis-2024.pdf"
    # l'alerte étrangère est intacte, le recalcul est idempotent
    assert "X-1" in alertes
    nb2 = fin.calculer_alertes(conn, "https://exemple.invalid/avis-2024.pdf")
    assert nb2 == nb
    total = conn.execute("SELECT COUNT(*) AS n FROM alertes").fetchone()["n"]
    assert total == nb + 1  # + l'alerte de l'autre pipeline


# ---------------------------------------------------------------------------
# Faits sourcés 2026
# ---------------------------------------------------------------------------


def test_aide_2026_total_seul(conn):
    fin.charger_aide_2026(conn)
    fin.charger_aide_2026(conn)  # idempotent
    lignes = conn.execute("SELECT * FROM partis_aide_2026").fetchall()
    assert len(lignes) == 1
    assert lignes[0]["annee"] == 2026
    assert lignes[0]["montant_total_eur"] == 64262871.05
    assert "2026-149" in lignes[0]["reference"]
    assert lignes[0]["source_url"].startswith("https://www.legifrance.gouv.fr/jorf/id/")


# ---------------------------------------------------------------------------
# Intégration réelle (réseau) — exclure avec -m 'not reseau'
# ---------------------------------------------------------------------------


@pytest.mark.reseau
def test_ingestion_reelle_complete(tmp_path, monkeypatch):
    monkeypatch.setenv("FT_DB_PATH", str(tmp_path / "financement-reseau.db"))
    assert fin.main() == 0

    conn = db.connexion(tmp_path / "financement-reseau.db")
    try:
        # volumétries publiées (données figées : 4 CSV annuels + 1 scrutin)
        assert conn.execute(
            "SELECT COUNT(*) AS n FROM campagnes_2024"
        ).fetchone()["n"] == 4010
        assert conn.execute(
            "SELECT COUNT(*) AS n FROM partis_comptes WHERE exercice = 2024"
        ).fetchone()["n"] == 575
        assert conn.execute(
            "SELECT COUNT(*) AS n FROM partis_comptes"
        ).fetchone()["n"] == 2179  # 519 + 551 + 535 + 575 − 1 doublon (code 671)
        assert conn.execute("SELECT COUNT(*) AS n FROM partis").fetchone()["n"] == \
            conn.execute("SELECT COUNT(DISTINCT parti_id) AS n FROM partis_comptes").fetchone()["n"]
        # décisions CNCCFP réparties (85 rejets constatés)
        assert conn.execute(
            "SELECT COUNT(*) AS n FROM campagnes_2024 WHERE decision = 'R'"
        ).fetchone()["n"] == 85
        # aide publique 2024 dans l'ordre de grandeur du décret annuel
        aide = conn.execute(
            "SELECT aide_f1_f2 FROM v_partis_aide_publique_evolution WHERE exercice = 2024"
        ).fetchone()["aide_f1_f2"]
        assert 60_000_000 < aide < 75_000_000
        # méta-fraîcheur des 3 sources
        metas = {
            r["source_id"]: r
            for r in conn.execute("SELECT * FROM meta_sources")
        }
        assert {"S25", "S29", "S37"} <= set(metas)
        assert metas["S25"]["date_donnees"] == "2024-12-31"
        assert metas["S29"]["lignes"] == 4010
        # alertes calculées
        nb_rejets = conn.execute(
            "SELECT COUNT(*) AS n FROM alertes WHERE type = 'financement_campagne_rejetee'"
        ).fetchone()["n"]
        assert nb_rejets == 85
    finally:
        conn.close()

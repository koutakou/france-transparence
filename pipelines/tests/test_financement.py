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

import re
import string
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
    # Le CSV publie « 1 » ; le pipeline rend le code COG « 01 », seul
    # joignable à ref_departements (§ M5 de doc/QUALITE-DONNEES.md).
    assert breton["code_departement"] == "01"
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
# Casse des noms : un défaut de la SOURCE, distinct du mojibake
# ---------------------------------------------------------------------------

#: Noms cassés relevés dans le CSV publié (octets cp1252 : 0xE9 = « é »
#: minuscule là où « É » majuscule serait 0xC9) → forme réparée attendue.
CASSE_A_REPARER = {
    "M. ELéLOUé-VALMAR Loïc": "M. ELÉLOUÉ-VALMAR Loïc",
    "Mme PRIé Lola": "Mme PRIÉ Lola",
    "M. DAUBIé Romain": "M. DAUBIÉ Romain",
    "Mme DAUFèS-ROUX Catherine": "Mme DAUFÈS-ROUX Catherine",
    "Mme MOGHIR NAïMA": "Mme MOGHIR NAÏMA",
    "Mme éTORé-MANIKA Edwina": "Mme ÉTORÉ-MANIKA Edwina",
    # famille 2 — prénom entièrement en bas de casse à initiale accentuée
    "M. LAHY éric": "M. LAHY Éric",
    "Mme CHALAS émilie": "Mme CHALAS Émilie",
    "M. BAUDE édouard": "M. BAUDE Édouard",
    # les deux familles dans le même nom
    "M. BéNARD édouard": "M. BÉNARD Édouard",
}

#: Graphies LÉGITIMES : la réparation ne doit RIEN y changer. C'est le
#: garde-fou « aucune minuscule ASCII dans le token » qui les protège.
CASSE_A_NE_PAS_TOUCHER = (
    "M. ACQUAVIVA Jean-Félix",
    "Mme FIRMIN LE BODO Agnès",
    "Mme de COSSÉ BRISSAC Céline",       # particule « de » conservée
    "M. van der WEYDEN Éric",            # particules néerlandaises
    "M. d'ORNANO Michel",                # élision
    "Mme SAINT-PÉ Séverine",
    "M. TOPARSLAN Ergün",                # déjà réparé par reparer_mojibake
    "Mme LEBOUCHER Elise",
    "M. BRETON Xavier",
    "LE 12éme EN ACTION",                # parti : « 12éme » a des minuscules ASCII
    "SoCARRIÈRES",
    "ENSEMBLE ! (MAJORITÉ PRÉSIDENTIELLE)",
    "RASSEMBLEMENT NATIONAL",
    "",
)


def test_normaliser_casse_nom_repare():
    for casse, attendu in CASSE_A_REPARER.items():
        assert fin.normaliser_casse_nom(casse) == attendu, casse


def test_normaliser_casse_nom_ne_touche_pas_aux_graphies_legitimes():
    for nom in CASSE_A_NE_PAS_TOUCHER:
        assert fin.normaliser_casse_nom(nom) == nom, nom


def test_normaliser_casse_nom_est_idempotente():
    for casse, attendu in CASSE_A_REPARER.items():
        assert fin.normaliser_casse_nom(attendu) == attendu
        assert fin.normaliser_casse_nom(fin.normaliser_casse_nom(casse)) == attendu


def test_normaliser_casse_nom_et_mojibake_sont_deux_defauts_distincts():
    """`reparer_mojibake` ne voit même pas le motif : aucun « Ã »/« Â »."""
    casse = "M. ELéLOUé-VALMAR Loïc"
    assert fin.reparer_mojibake(casse) == casse          # inopérant, comme prévu
    assert fin.normaliser_casse_nom(casse) != casse      # l'autre fonction agit
    # et réciproquement : la casse ne défait pas le mojibake
    assert fin.normaliser_casse_nom("M. TOPARSLAN ErgÃ¼n") == "M. TOPARSLAN ErgÃ¼n"


def test_extraire_marqueur_etoile():
    assert fin.extraire_marqueur_etoile("Mme YADAN Caroline (*)") == (
        "Mme YADAN Caroline",
        True,
    )
    assert fin.extraire_marqueur_etoile("Mme DORé-LUCAS Marie Madeleine (*)") == (
        "Mme DORé-LUCAS Marie Madeleine",
        True,
    )
    # sans marqueur : le nom est rendu tel quel
    assert fin.extraire_marqueur_etoile("M. BRETON Xavier") == (
        "M. BRETON Xavier",
        False,
    )
    # une étoile qui n'est pas le marqueur suffixé n'est pas touchée
    assert fin.extraire_marqueur_etoile("M. (*) DUPONT") == ("M. (*) DUPONT", False)


def test_legende_marqueur_etoile_dit_qu_elle_n_est_pas_documentee():
    legende = fin.legende_marqueur_etoile(1)
    assert "(*)" in legende
    assert "n'est pas documentée" in legende
    assert fin.legende_marqueur_etoile(0) == ""


# ---------------------------------------------------------------------------
# Format monétaire : une donnée absente n'est jamais rendue en zéro
# ---------------------------------------------------------------------------

FINE = "\u202f"


def test_formater_euros():
    assert fin.formater_euros(19474807.0) == f"19{FINE}474{FINE}807{FINE}€"
    assert fin.formater_euros(773.0) == f"773{FINE}€"
    assert fin.formater_euros(1234.56) == f"1{FINE}234,56{FINE}€"
    assert fin.formater_euros(-83.0) == f"-83{FINE}€"
    # séparateur de milliers ET espace avant l'unité : espace fine insécable,
    # même convention que app/src/lib/format.ts (jamais d'espace ordinaire).
    assert " " not in fin.formater_euros(19474807.0)
    # plus aucun point décimal anglo-saxon
    assert "." not in fin.formater_euros(1234.56)


def test_formater_euros_distingue_absence_et_zero():
    """Le cœur de la correction : None n'est PAS 0."""
    assert fin.formater_euros(None) == "non renseigné"
    assert fin.formater_euros(0.0) == f"0{FINE}€"
    assert fin.formater_euros(0) != fin.formater_euros(None)


def test_compte_sans_montant_est_conjonctif():
    """Un seul poste à zéro ne suffit pas — sinon on écraserait de vrais zéros."""
    zero = dict.fromkeys(fin.POSTES_COMPTE_CAMPAGNE, 0.0)
    assert fin.compte_sans_montant(zero) is True
    # 152 comptes réels : dépenses > 0 et remboursement à 0 (vrai zéro,
    # juridiquement obligatoire pour un compte rejeté)
    remb_zero = dict(zero, depenses_declarees=773.0, depenses_retenues=773.0,
                     recettes_declarees=773.0)
    assert fin.compte_sans_montant(remb_zero) is False
    # un NULL quelque part : la règle ne se déclenche pas non plus
    avec_null = dict(zero, depenses_retenues=None)
    assert fin.compte_sans_montant(avec_null) is False


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


def _tokens_a_casse_cassee(nom: str) -> list[str]:
    """Détecteur INDÉPENDANT de la fonction testée (règle réécrite à la main).

    Un token est « cassé » s'il mélange des capitales ASCII et des minuscules
    accentuées sans aucune minuscule ASCII, ou s'il est entièrement en bas de
    casse en commençant par une minuscule accentuée.
    """
    maj = set(string.ascii_uppercase)
    minu = set(string.ascii_lowercase)

    def accentuee_min(c: str) -> bool:
        return c.isalpha() and c.islower() and c not in minu

    casses = []
    for t in nom.split(" "):
        sans_min_ascii = not any(c in minu for c in t)
        if (
            len(t) >= 3
            and sans_min_ascii
            and sum(1 for c in t if c in maj) >= 2
            and any(accentuee_min(c) for c in t)
        ):
            casses.append(t)
        elif t and accentuee_min(t[0]) and t == t.lower():
            casses.append(t)
    return casses


def test_apres_ingestion_aucun_nom_a_casse_cassee(conn):
    """Non-régression : zéro nom cassé en base après chargement réel."""
    lignes = fin.parser_campagnes(FIX_CAMPAGNES.read_bytes())
    fin.charger_campagnes(conn, lignes)
    noms = [r["nom"] for r in conn.execute("SELECT nom FROM campagnes_2024")]
    casses = {n: _tokens_a_casse_cassee(n) for n in noms}
    assert not any(casses.values()), {k: v for k, v in casses.items() if v}
    # les deux familles de la fixture sont bien réparées
    assert "Mme PRIÉ Lola" in noms      # « Mme PRIé Lola » dans le CSV publié
    assert "M. LAHY Éric" in noms       # « M. LAHY éric » dans le CSV publié
    # … et les noms sains sont identiques au caractère près
    assert "M. BRETON Xavier" in noms
    assert "Mme LEBOUCHER Elise" in noms
    assert "M. TOPARSLAN Ergün" in noms  # mojibake réparé, casse inchangée


def test_marqueur_etoile_sorti_du_nom_et_stocke(conn):
    lignes = fin.parser_campagnes(FIX_CAMPAGNES.read_bytes())
    marquee = dict(lignes[0], candidat_id="999999999",
                   nom="Mme YADAN Caroline", marqueur_etoile=True,
                   decision="R", decision_famille="rejete")
    fin.charger_campagnes(conn, lignes + [marquee])
    ligne = conn.execute(
        "SELECT nom, marqueur_etoile FROM campagnes_2024 WHERE candidat_id = '999999999'"
    ).fetchone()
    assert ligne["nom"] == "Mme YADAN Caroline"   # le marqueur n'est plus dans le nom
    assert ligne["marqueur_etoile"] == 1
    # aucun nom ne porte plus « (*) »
    assert conn.execute(
        "SELECT COUNT(*) AS n FROM campagnes_2024 WHERE nom LIKE '%(*)%'"
    ).fetchone()["n"] == 0
    fin.calculer_alertes(conn, None)
    detail = conn.execute(
        "SELECT detail FROM alertes WHERE id = 'FIN-CAMP-REJ-999999999'"
    ).fetchone()["detail"]
    assert "(*)" in detail and "n'est pas documentée" in detail


# ---------------------------------------------------------------------------
# Montants des alertes : format français, et l'absence n'est pas un zéro
# ---------------------------------------------------------------------------


def _charger_corpus_alertes(conn):
    lignes = fin.parser_campagnes(FIX_CAMPAGNES.read_bytes())
    # compte intégralement à zéro : 55 cas réels sur les 85 rejets publiés —
    # absence de compte exploitable, souvent le motif même du rejet.
    tout_zero = dict(
        lignes[0], candidat_id="900000001", nom="M. SANSCOMPTE Jean",
        depenses_declarees=0.0, depenses_retenues=0.0, recettes_declarees=0.0,
        recettes_retenues=0.0, remboursement_etat=0.0,
        decision="R", decision_famille="rejete",
    )
    fin.charger_campagnes(conn, lignes + [tout_zero])
    fin.charger_partis(conn, {2024: fin.parser_partis(FIX_PARTIS_2024.read_bytes(), 2024)})
    fin.calculer_alertes(conn, None)


def test_alerte_compte_tout_a_zero_ne_publie_pas_de_montant(conn):
    _charger_corpus_alertes(conn)
    detail = conn.execute(
        "SELECT detail FROM alertes WHERE id = 'FIN-CAMP-REJ-900000001'"
    ).fetchone()["detail"]
    assert "aucun montant renseigné" in detail
    assert "tous les postes du compte sont à zéro" in detail
    assert "ne signifie PAS que le candidat n'a rien dépensé" in detail
    # surtout : aucun montant chiffré n'est affirmé
    assert "0 €" not in detail
    assert "0.0" not in detail
    assert "€" not in detail  # aucun montant n'est affirmé du tout


def test_alerte_remboursement_zero_legitime_garde_son_zero(conn):
    """KOUASSI : dépenses > 0, remboursement 0 € — un VRAI zéro, à conserver."""
    _charger_corpus_alertes(conn)
    detail = conn.execute(
        "SELECT detail FROM alertes WHERE id = 'FIN-CAMP-REJ-202409066'"
    ).fetchone()["detail"]
    assert f"dépenses déclarées : 773{FINE}€" in detail
    assert f"remboursement État : 0{FINE}€" in detail
    assert "aucun montant renseigné" not in detail


def test_aucun_montant_serialise_a_l_anglo_saxonne(conn):
    _charger_corpus_alertes(conn)
    details = [
        r["detail"]
        for r in conn.execute(
            "SELECT detail FROM alertes WHERE type LIKE 'financement_%'"
        )
        if r["detail"]
    ]
    assert details
    for d in details:
        assert ".0 €" not in d
        assert not re.search(r"\d\.\d+\s*€", d), d
        assert not re.search(r"\d \d{3}\s*€", d), d  # espace ordinaire interdite


def test_regle_de_dependance_en_format_francais(conn):
    """La règle affichée au public suit la même convention que les montants."""
    _charger_corpus_alertes(conn)
    regle = conn.execute(
        "SELECT regle FROM alertes WHERE type = 'financement_parti_dependance_aide' LIMIT 1"
    ).fetchone()["regle"]
    assert f"1{FINE}000{FINE}000{FINE}€" in regle
    assert "1,000,000" not in regle


def test_motif_ratio_conserve_mot_pour_mot_et_reste_triable(conn):
    """PIÈGE : `(ratio ` est une clé de tri SQL côté front — à ne pas casser.

    app/src/lib/queries/financement.ts ordonne les alertes de dépendance par
    CAST(substr(detail, instr(detail,'(ratio ') + 7) AS REAL) : le séparateur
    décimal doit rester un POINT (SQLite lit '92,7' comme 92.0).
    """
    _charger_corpus_alertes(conn)
    lignes = conn.execute(
        """SELECT detail,
                  CAST(substr(detail, instr(detail, '(ratio ') + 7) AS REAL) AS cle
           FROM alertes
           WHERE type = 'financement_parti_dependance_aide'
           ORDER BY cle DESC, id"""
    ).fetchall()
    assert lignes
    for l in lignes:
        assert "(ratio " in l["detail"]
        assert re.search(r"\(ratio \d+\.\d%\)\.", l["detail"]), l["detail"]
        assert l["cle"] > 0  # la clé de tri est bien numérique, pas 0
    assert [l["cle"] for l in lignes] == sorted(
        (l["cle"] for l in lignes), reverse=True
    )


# ---------------------------------------------------------------------------
# Enveloppes légales sourcées (décrets)
# ---------------------------------------------------------------------------


def test_decrets_aide_publique_table_annuelle(conn):
    """Une ligne par décret RÉELLEMENT consulté — aucune année inventée."""
    assert fin.charger_decrets_aide(conn) == 2
    fin.charger_decrets_aide(conn)  # idempotent
    lignes = conn.execute(
        "SELECT * FROM partis_aide_annuelle ORDER BY annee"
    ).fetchall()
    assert [l["annee"] for l in lignes] == [2024, 2026]
    par_annee = {l["annee"]: l for l in lignes}
    assert par_annee[2024]["montant_total_eur"] == 66438848.34
    assert "2024-77" in par_annee[2024]["reference"]
    assert par_annee[2026]["montant_total_eur"] == 64262871.05
    assert "2026-149" in par_annee[2026]["reference"]
    # fractions non dépouillées → NULL, jamais 0
    for l in lignes:
        assert l["fraction1_eur"] is None
        assert l["fraction2_eur"] is None
        assert l["source_url"].startswith("https://www.legifrance.gouv.fr/")


def test_decret_2024_reverifie_sur_legifrance(conn):
    """Réserve levée le 20/08/2026 : lien direct JORF et note positive."""
    fin.charger_decrets_aide(conn)
    ligne = conn.execute(
        "SELECT note, source_url FROM partis_aide_annuelle WHERE annee = 2024"
    ).fetchone()
    assert "re-vérifié" in ligne["note"] and "20/08/2026" in ligne["note"]
    assert "à confirmer" not in ligne["note"].lower()
    assert ligne["source_url"] == (
        "https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000049085148"
    )


def test_ancienne_table_mono_annee_supprimee(conn):
    """partis_aide_2026 laissait comparer un décret à des déclarations."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS partis_aide_2026 (annee INTEGER PRIMARY KEY)"
    )
    conn.commit()
    fin.creer_tables(conn)  # rejoue le schéma : le DROP doit passer
    restantes = {
        r["name"]
        for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    assert "partis_aide_2026" not in restantes
    assert "partis_aide_annuelle" in restantes


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


# ---------------------------------------------------------------------------
# Rattachement géographique des comptes de campagne (§ M5 QUALITE-DONNEES.md)
# ---------------------------------------------------------------------------


def test_code_departement_ramene_au_cog():
    """Les trois familles d'écart constatées, et rien d'autre."""
    assert fin.normaliser_code_departement("1") == "01"     # zéro initial perdu
    assert fin.normaliser_code_departement("9") == "09"
    assert fin.normaliser_code_departement("20A") == "2A"   # Corse-du-Sud
    assert fin.normaliser_code_departement("20B") == "2B"   # Haute-Corse
    assert fin.normaliser_code_departement("ZX") == "977"   # Saint-Barthélemy
    # Codes déjà conformes : rendus tels quels.
    for code in ("01", "54", "2A", "971", "976", "988"):
        assert fin.normaliser_code_departement(code) == code
    assert fin.normaliser_code_departement("") is None
    assert fin.normaliser_code_departement(None) is None


def test_ordinaux_de_circonscription_unifies():
    assert fin.normaliser_ordinaux("8ème circonscription") == "8e circonscription"
    assert fin.normaliser_ordinaux("1ère circonscription") == "1re circonscription"
    # Formes déjà correctes et libellés sans ordinal : inchangés.
    assert fin.normaliser_ordinaux("6e circonscription") == "6e circonscription"
    assert fin.normaliser_ordinaux("1re circonscription") == "1re circonscription"
    assert fin.normaliser_ordinaux("Circonscription unique") == "Circonscription unique"


def test_sentinelle_zz_explicitee_et_code_75_ecarte():
    """125 lignes du CSV rattachent les Français de l'étranger au 75 (Paris).

    C'est faux : aucun département français ne leur correspond. Le libellé
    est restitué, le code passe à NULL — on ne remplace pas un code faux par
    un autre code.
    """
    circ, dep, code = fin.normaliser_geographie_campagne(
        "Français établis hors de France - 8ème circonscription", "ZZ", "75"
    )
    assert circ == "Français établis hors de France - 8e circonscription"
    assert dep == "Français établis hors de France"
    assert code is None


def test_geographie_campagne_laisse_intact_un_departement_normal():
    assert fin.normaliser_geographie_campagne(
        "Meurthe-et-Moselle - 6e circonscription", "Meurthe-et-Moselle", "54"
    ) == ("Meurthe-et-Moselle - 6e circonscription", "Meurthe-et-Moselle", "54")


# ---------------------------------------------------------------------------
# Contrôles comptables des comptes de partis (§ M7 QUALITE-DONNEES.md)
# ---------------------------------------------------------------------------


def test_controle_comptes_partis_detecte_les_impossibilites():
    lignes = [
        # Sain : l'identité produits − charges = résultat est vérifiée.
        {"nom": "OK", "exercice": 2024, "unite": "EUR",
         "produits_total": 1000.0, "charges_total": 400.0, "resultat": 600.0},
        # Un TOTAL de produits ne peut pas être négatif.
        {"nom": "NEG", "exercice": 2021, "unite": "EUR",
         "produits_total": -661.54, "charges_total": 0.0, "resultat": -661.54},
        # Identité comptable rompue de 44 126 €.
        {"nom": "DESEQ", "exercice": 2021, "unite": "EUR",
         "produits_total": 79260.0, "charges_total": 101323.0, "resultat": 22063.0},
        # Coquille vide ou dépôt incomplet : compté, pas dénoncé.
        {"nom": "ZERO", "exercice": 2023, "unite": "EUR",
         "produits_total": 0.0, "charges_total": 0.0, "resultat": 0.0},
    ]
    assert fin.controler_comptes_partis(lignes) == {
        "produits_negatifs": 1, "desequilibres": 1, "produits_nuls": 1,
    }


def test_controle_comptes_partis_ignore_les_unites_non_euro():
    """L'identité comptable ne se teste pas à cheval sur deux monnaies."""
    lignes = [{"nom": "XPF", "exercice": 2021, "unite": "XPF",
               "produits_total": 79260.0, "charges_total": 101323.0,
               "resultat": 22063.0}]
    assert fin.controler_comptes_partis(lignes)["desequilibres"] == 0


def test_controle_comptes_partis_ne_modifie_rien():
    """Le contrôle SIGNALE : les montants publiés par la CNCCFP sont intacts."""
    lignes = [{"nom": "NEG", "exercice": 2021, "unite": "EUR",
               "produits_total": -70.0, "charges_total": 0.0, "resultat": -70.0}]
    avant = [dict(l) for l in lignes]
    fin.controler_comptes_partis(lignes)
    assert lignes == avant


# ---------------------------------------------------------------------------
# Contrôles C1 de la source CNCCFP — défaut MESURÉ ET SERVI le 29/08/2026
# ---------------------------------------------------------------------------
#
# Le CSV des comptes de partis 2024 publie « LEVALLOIS AU C\x8cUR » et
# « UNION ROSNÉENNE D\x92ACTION MUNICIPALE » : des octets cp1252 (0x8C = Œ,
# 0x92 = ’) décodés par l'amont avec la table iso-8859-1, donc devenus des
# contrôles C1, puis réencodés en UTF-8 VALIDE. Vérifié octet pour octet sur
# la ressource data.gouv (md5 identique au fichier local), et absent des
# millésimes 2021-2023 : la régression est amont et datée.
#
# Le nom traverse `parser_partis` vers TROIS colonnes — `entites.nom`,
# `partis.nom`, `partis_comptes.nom_declare` — ce qui est la raison de
# réparer au parseur et non aux sites d'écriture SQL.


def _fixture_corrompue() -> bytes:
    """La fixture 2024, avec un nom remplacé par le cas réel corrompu."""
    brut = FIX_PARTIS_2024.read_bytes()
    assert b"RASSEMBLEMENT NATIONAL" in brut
    return brut.replace(b"RASSEMBLEMENT NATIONAL", b"LEVALLOIS AU C\xc2\x8cUR")


def test_parser_partis_repare_les_controles_c1():
    lignes = fin.parser_partis(_fixture_corrompue(), 2024)
    nom = next(l for l in lignes if l["code"] == "40")["nom"]
    assert nom == "LEVALLOIS AU CŒUR"
    assert "\x8c" not in nom


def test_parser_partis_ne_touche_pas_aux_noms_sains():
    """Contre-épreuve : la réparation ne doit RIEN changer d'autre."""
    avant = fin.parser_partis(FIX_PARTIS_2024.read_bytes(), 2024)
    assert next(l for l in avant if l["code"] == "40")["nom"] == "RASSEMBLEMENT NATIONAL"
    assert all("\u0152" not in l["nom"] for l in avant)


def test_charger_partis_ne_sert_aucun_controle_c1_dans_les_trois_colonnes(conn):
    """Le défaut se propage à trois colonnes : les trois doivent être propres."""
    import unicodedata

    lignes = fin.parser_partis(_fixture_corrompue(), 2024)
    fin.charger_partis(conn, {2024: lignes})
    for table, colonne in (
        ("entites", "nom"),
        ("partis", "nom"),
        ("partis_comptes", "nom_declare"),
    ):
        valeurs = [
            r[0] for r in conn.execute(f"SELECT {colonne} FROM {table}").fetchall()
        ]
        assert valeurs, f"{table}.{colonne} vide : le test ne prouverait rien"
        fautives = [
            v for v in valeurs
            if v and any(unicodedata.category(c) == "Cc" for c in v)
        ]
        assert fautives == [], f"{table}.{colonne} sert encore {fautives!r}"
        assert "LEVALLOIS AU CŒUR" in valeurs


def test_parser_partis_journalise_son_compte_meme_a_zero(caplog):
    """CONTRE-ÉPREUVE DU SILENCE : un compteur muet au vert est indiscernable
    d'un compteur débranché. Le segment doit être au journal des DEUX côtés,
    et porter un compte différent."""
    import logging

    with caplog.at_level(logging.INFO):
        fin.parser_partis(FIX_PARTIS_2024.read_bytes(), 2024)
    sain = [m for m in caplog.messages if "réparé(s)" in m]
    assert len(sain) == 1 and "0 nom(s) réparé(s)" in sain[0]

    caplog.clear()
    with caplog.at_level(logging.INFO):
        fin.parser_partis(_fixture_corrompue(), 2024)
    corrompu = [m for m in caplog.messages if "réparé(s)" in m]
    assert len(corrompu) == 1 and "1 nom(s) réparé(s)" in corrompu[0]

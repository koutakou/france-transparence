"""Tests P1/P2 budget de l'État : transformations pures sur extraits RÉELS
(fixtures tirées des fichiers sources du 19/08/2026, pièges inclus : colonne
`24_04_2024`, UTF-16 + décimales `,` de la pièce jointe 2013-2023, SIREN
« NR\\nCHORUS », U+00A0, lignes Chorus décalées) + intégration réseau complète
(@pytest.mark.reseau, base jetable via FT_DB_PATH)."""

from __future__ import annotations

import csv
import socket
import sqlite3
from pathlib import Path

import pytest

from pipelines import ingest_budget_mensuel as p1
from pipelines import ingest_budget_structure as p2

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# P1 — briques pures
# ---------------------------------------------------------------------------


def test_analyser_colonne_date():
    assert p1.analyser_colonne_date("31_01_2024") == (2024, 1)
    # anomalie réelle du dataset : avril 2024 s'appelle 24_04_2024
    assert p1.analyser_colonne_date("24_04_2024") == (2024, 4)
    assert p1.analyser_colonne_date("31/01/2013") == (2013, 1)
    assert p1.analyser_colonne_date("30_11_2025") == (2025, 11)
    assert p1.analyser_colonne_date("categorie") is None
    assert p1.analyser_colonne_date("") is None
    assert p1.analyser_colonne_date("31_13_2024") is None  # mois impossible


def test_parser_montant():
    assert p1.parser_montant("-42864859134.71") == pytest.approx(-42864859134.71)
    assert p1.parser_montant("-12817067246,53") == pytest.approx(-12817067246.53)
    assert p1.parser_montant("991265739") == pytest.approx(991265739.0)
    assert p1.parser_montant("1 234,5") == pytest.approx(1234.5)  # insécable
    assert p1.parser_montant("1 234.5") == pytest.approx(1234.5)  # fine insécable
    assert p1.parser_montant("") is None
    assert p1.parser_montant(None) is None


def test_fin_de_mois():
    assert p1.fin_de_mois(2024, 2) == "2024-02-29"  # bissextile
    assert p1.fin_de_mois(2026, 6) == "2026-06-30"
    assert p1.fin_de_mois(2013, 1) == "2013-01-31"


def test_normaliser_libelle_reconcilie_export_et_piece_jointe():
    # libellés réels : export (apostrophe ’) vs pièce jointe (espaces de fin)
    assert (p1.normaliser_libelle("Charges de la dette de l’Etat  ")
            == p1.normaliser_libelle("Charges de la dette de l’Etat")
            == "Charges de la dette de l'Etat")
    assert p1.normaliser_libelle("Solde des comptes spéciaux ") == \
        "Solde des comptes spéciaux"


def test_identifiant_ligne():
    assert p1.identifiant_ligne("Dépenses", "Budget général",
                                "Dépenses de personnel") == \
        "depenses/budget-general/depenses-de-personnel"


def _tableau(nom: str, encodage: str):
    return p1.extraire_tableau(p1.lire_csv(FIXTURES / nom, encodage))


def test_extraire_tableau_export_reel():
    tableau, mois = _tableau("smb_export_extrait.csv", "utf-8-sig")
    assert len(tableau) == 26
    assert len(mois) == 30  # 01/2024 → 06/2026
    solde = next(l for l in tableau if l["ligne"] == "Solde budgétaire")
    assert solde["valeurs"][(2024, 1)] == pytest.approx(-25741980707.95)
    assert (2024, 4) in solde["valeurs"]  # colonne anormale 24_04_2024 captée


def test_extraire_tableau_historique_utf16():
    tableau, mois = _tableau("smb_2013_2023_extrait.csv", "utf-16")
    assert len(tableau) == 26  # lignes de remplissage vides ignorées
    assert set(a for a, _ in mois) == {2013, 2023}
    perso = next(l for l in tableau if l["ligne"] == "Dépenses de personnel")
    assert perso["valeurs"][(2013, 1)] == pytest.approx(10710235456.84)


def test_construire_serie_flux_et_n1():
    export, _ = _tableau("smb_export_extrait.csv", "utf-8-sig")
    hist, _ = _tableau("smb_2013_2023_extrait.csv", "utf-16")
    serie = p1.construire_serie(export, hist)
    # 26 lignes × (24 mois hist extrait + 30 mois export) = 1404
    assert len(serie) == 26 * 54
    par_cle = {(e["ligne_id"], e["annee"], e["mois"]): e for e in serie}
    dep = "depenses/budget-general/total-depenses-nettes-du-budget-general"
    jan24 = par_cle[(dep, 2024, 1)]
    fev24 = par_cle[(dep, 2024, 2)]
    # janvier : flux = cumul ; février : flux = cumul(2) − cumul(1)
    assert jan24["montant_mois"] == pytest.approx(jan24["montant_cumul"])
    assert fev24["montant_mois"] == pytest.approx(
        fev24["montant_cumul"] - jan24["montant_cumul"])
    # couture 2023 (pièce jointe) → 2024 (export) : N−1 traverse les fichiers
    jan23 = par_cle[(dep, 2023, 1)]
    assert jan24["montant_cumul_n1"] == pytest.approx(jan23["montant_cumul"])
    assert jan24["montant_mois_n1"] == pytest.approx(jan23["montant_mois"])
    # 2013 : pas d'année précédente → NULL, jamais 0 inventé
    assert par_cle[(dep, 2013, 5)]["montant_cumul_n1"] is None
    # 2023 : 2022 absent de l'extrait → NULL
    assert par_cle[(dep, 2023, 5)]["montant_cumul_n1"] is None
    # ordre de grandeur : cumul décembre 2023 ≈ 454,6 Md€
    dec23 = par_cle[(dep, 2023, 12)]
    assert dec23["montant_cumul"] == pytest.approx(454565410321.53)
    assert dec23["date_fin_mois"] == "2023-12-31"


def test_construire_serie_refuse_lignes_divergentes():
    export, _ = _tableau("smb_export_extrait.csv", "utf-8-sig")
    hist, _ = _tableau("smb_2013_2023_extrait.csv", "utf-16")
    hist[0]["ligne"] = "Ligne renommée par la DGFiP"
    with pytest.raises(ValueError, match="divergentes"):
        p1.construire_serie(export, hist)


def test_controler_serie_detecte_erreur_unite():
    export, _ = _tableau("smb_export_extrait.csv", "utf-8-sig")
    hist, _ = _tableau("smb_2013_2023_extrait.csv", "utf-16")
    serie = p1.construire_serie(export, hist)
    p1.controler_serie(serie)  # la vraie série passe
    # même série en k€ (montants ÷ 1000) → détectée
    for e in serie:
        e["montant_cumul"] /= 1000
    with pytest.raises(ValueError, match="unité"):
        p1.controler_serie(serie)


# ---------------------------------------------------------------------------
# P1 — rupture de périmètre d'une cellule de total (septembre 2026)
# ---------------------------------------------------------------------------
# Fixture : extrait RÉEL de l'export du 11/11/2026 (jeu modifié en amont le
# 04/11/2026), les 26 lignes, colonnes 31/08/2025, 30/09/2025, 31/08/2026 et
# 30/09/2026. Au 30/09/2026 la ligne « Total recettes nettes du budget
# général » vaut 219 136 720 375,64 €, alors que fiscales + non fiscales =
# 269 997 985 377,18 € — l'identité tient sur les 164 autres mois de la série.

_RECETTES_NETTES = "recettes/budget-general/total-recettes-nettes-du-budget-general"


def _serie_septembre_2026():
    export, _ = _tableau("smb_export_2026_09_extrait.csv", "utf-8-sig")
    hist, _ = _tableau("smb_2013_2023_extrait.csv", "utf-16")
    return p1.construire_serie(export, hist)


def test_detecter_ruptures_isole_la_seule_cellule_de_septembre_2026():
    ruptures = p1.detecter_ruptures(_serie_septembre_2026())
    # UNE rupture, pas « au moins une » : les 27 autres mois de l'extrait
    # (24 de 2013/2023, 3 de 2025-2026) et les trois autres identités tiennent.
    assert len(ruptures) == 1
    r = ruptures[0]
    assert (r["ligne_id"], r["date_fin_mois"]) == (_RECETTES_NETTES, "2026-09-30")
    assert r["montant_publie"] == pytest.approx(219136720375.64, abs=0.01)
    assert r["somme_composantes"] == pytest.approx(269997985377.18, abs=0.01)
    assert r["identite"] == "recettes fiscales + non fiscales"
    # La cellule est redonnée EXACTEMENT par une autre combinaison publiée :
    # 250,47 + 19,53 − 55,86 (PSR) + 5,00 (fonds de concours) = 219,14 Md€.
    assert r["definition_constatee"] == (
        "recettes fiscales + non fiscales − prélèvements sur recettes "
        "+ fonds de concours")


def test_detecter_ruptures_ne_signale_rien_sur_l_export_d_aout_2026():
    # Contre-épreuve : l'extrait du 19/08/2026 (01/2024 → 06/2026) est
    # conforme partout — le contrôle ne crie pas au loup.
    export, _ = _tableau("smb_export_extrait.csv", "utf-8-sig")
    hist, _ = _tableau("smb_2013_2023_extrait.csv", "utf-16")
    assert p1.detecter_ruptures(p1.construire_serie(export, hist)) == []


def test_detecter_ruptures_ne_nomme_pas_une_definition_qui_ne_tient_pas():
    serie = _serie_septembre_2026()
    for e in serie:
        if e["ligne_id"] == _RECETTES_NETTES and e["date_fin_mois"] == "2026-09-30":
            e["montant_cumul"] += 1000.0  # plus aucune combinaison ne tombe juste
    (r,) = p1.detecter_ruptures(serie)
    assert r["definition_constatee"] is None


def test_neutraliser_flux_a_travers_la_cellule_en_rupture():
    serie = _serie_septembre_2026()
    ruptures = p1.detecter_ruptures(serie)
    par_cle = {(e["ligne_id"], e["date_fin_mois"]): e for e in serie}
    sept26 = par_cle[(_RECETTES_NETTES, "2026-09-30")]
    # Avant : cumul septembre − cumul août = −5,73 Md€ de recettes « du mois ».
    assert sept26["montant_mois"] == pytest.approx(-5726389987.27, abs=0.01)
    assert p1.neutraliser_flux(serie, ruptures) == 1
    assert sept26["montant_mois"] is None
    assert sept26["montant_cumul"] == pytest.approx(219136720375.64, abs=0.01)
    # Le reste n'est pas touché : septembre 2025, et les composantes de 2026.
    assert par_cle[(_RECETTES_NETTES, "2025-09-30")]["montant_mois"] is not None
    fis = par_cle[("recettes/budget-general/total-recettes-fiscales", "2026-09-30")]
    assert fis["montant_mois"] is not None


def test_neutraliser_flux_suit_le_mois_precedent_et_l_annee_precedente():
    # Rupture POSÉE à la main sur des cellules réelles, pour éprouver les deux
    # autres chemins : le flux de septembre dépend du cumul d'août, et le flux
    # N−1 de septembre 2026 est celui de septembre 2025.
    serie = _serie_septembre_2026()
    par_cle = {(e["ligne_id"], e["date_fin_mois"]): e for e in serie}
    pose = [{"ligne_id": _RECETTES_NETTES, "annee": 2026, "mois": 8},
            {"ligne_id": _RECETTES_NETTES, "annee": 2025, "mois": 9}]
    sept26 = par_cle[(_RECETTES_NETTES, "2026-09-30")]
    assert sept26["montant_mois"] is not None
    assert sept26["montant_mois_n1"] is not None
    p1.neutraliser_flux(serie, pose)
    assert sept26["montant_mois"] is None      # via août 2026
    assert sept26["montant_mois_n1"] is None   # via septembre 2025
    assert par_cle[(_RECETTES_NETTES, "2025-09-30")]["montant_mois"] is None


def test_bilan_compte_les_mois_reellement_controles():
    # 28 mois dans l'extrait (24 de 2013/2023, 4 de 2025-2026) : chacune des
    # quatre identités est contrôlée sur les 28, aucune n'est muette. Tue la
    # mutation qui ajoute à une identité une composante que la source ne
    # publie pas (le mois devenait « ignoré » et le journal le disait
    # contrôlé).
    bilan = {}
    p1.detecter_ruptures(_serie_septembre_2026(), bilan)
    assert set(bilan) == set(p1.IDENTITES)
    for total, b in bilan.items():
        assert (b["controles"], b["non_controlables"]) == (28, []), total


def test_bilan_dit_le_mois_dont_une_composante_manque():
    psr_ue = "depenses/prelevements-sur-recettes/psr-au-profit-de-l-union-europeenne"
    serie = [e for e in _serie_septembre_2026()
             if not (e["ligne_id"] == psr_ue and e["date_fin_mois"] == "2026-08-31")]
    bilan = {}
    p1.detecter_ruptures(serie, bilan)
    psr = bilan["depenses/prelevements-sur-recettes/total-prelevements-sur-recettes"]
    assert (psr["controles"], psr["non_controlables"]) == (27, ["2026-08-31"])
    # Les autres identités ne sont pas touchées.
    assert bilan[_RECETTES_NETTES]["controles"] == 28


def test_main_vide_les_ruptures_d_un_cycle_precedent(monkeypatch, tmp_path):
    """Le cycle suivant réécrit la table : une rupture corrigée en amont n'y
    survit pas (tue la mutation qui retire le DELETE de la transaction)."""
    base = tmp_path / "budget.db"
    monkeypatch.setenv("FT_DB_PATH", str(base))
    for export, attendu in (("smb_export_2026_09_extrait.csv", 1),
                            ("smb_export_extrait.csv", 0)):
        fixtures = {"budget/smb_export.csv": FIXTURES / export,
                    "budget/smb_2013_2023.csv": FIXTURES / "smb_2013_2023_extrait.csv"}
        monkeypatch.setattr(p1, "telecharger",
                            lambda url, dest, f=fixtures, **_: f[dest])
        assert p1.main() == 0
        conn = sqlite3.connect(base)
        n = conn.execute("SELECT count(*) FROM budget_mensuel_ruptures").fetchone()[0]
        conn.close()
        assert n == attendu, export


def test_main_ecrit_la_rupture_et_ne_publie_pas_le_flux(monkeypatch, tmp_path):
    fixtures = {
        "budget/smb_export.csv": FIXTURES / "smb_export_2026_09_extrait.csv",
        "budget/smb_2013_2023.csv": FIXTURES / "smb_2013_2023_extrait.csv",
    }
    monkeypatch.setattr(p1, "telecharger", lambda url, dest, **_: fixtures[dest])
    base = tmp_path / "budget.db"
    monkeypatch.setenv("FT_DB_PATH", str(base))
    assert p1.main() == 0
    conn = sqlite3.connect(base)
    ruptures = conn.execute(
        "SELECT ligne_id, date_fin_mois, definition_constatee "
        "FROM budget_mensuel_ruptures").fetchall()
    assert ruptures == [(_RECETTES_NETTES, "2026-09-30",
                         "recettes fiscales + non fiscales − prélèvements "
                         "sur recettes + fonds de concours")]
    cumul, flux = conn.execute(
        "SELECT montant_cumul, montant_mois FROM budget_mensuel "
        "WHERE ligne_id = ? AND date_fin_mois = '2026-09-30'",
        (_RECETTES_NETTES,)).fetchone()
    assert cumul == pytest.approx(219136720375.64, abs=0.01)  # jamais rectifié
    assert flux is None
    conn.close()


# ---------------------------------------------------------------------------
# P2 — briques pures
# ---------------------------------------------------------------------------


def test_nettoyer_texte():
    assert p2.nettoyer_texte("IA VAI MA NOA") == "IA VAI MA NOA"
    assert p2.nettoyer_texte("CENTRE FAMIL \nACCUEIL") == "CENTRE FAMIL ACCUEIL"
    assert p2.nettoyer_texte("  x  ") == "x"
    assert p2.nettoyer_texte("") is None
    assert p2.nettoyer_texte(None) is None


def test_normaliser_siren():
    assert p2.normaliser_siren("399990696") == "399990696"
    assert p2.normaliser_siren("NR\nCHORUS") is None
    assert p2.normaliser_siren(" 399 990 696 ") == "399990696"
    assert p2.normaliser_siren("39999069") is None  # 8 chiffres
    assert p2.normaliser_siren(None) is None
    assert p2.normaliser_nic("00037") == "00037"
    assert p2.normaliser_nic("Actif") is None


def test_departement_depuis_cog():
    cas = {
        "75117": "75", "01001": "01", "95500": "95",
        "2A228": "2A", "2B087": "2B",
        "97209": "972", "97616": "976",     # DROM
        "97701": None, "98714": None,       # COM (St-Barth, Polynésie)
        "99326": None,                      # pays étranger
        "Oui": None, "0": None, None: None,  # lignes Chorus décalées / vide
        "20167": None, "00000": None, "96000": None,
    }
    for cog, attendu in cas.items():
        assert p2.departement_depuis_cog(cog) == attendu, cog


def _dicts(nom: str):
    with open(FIXTURES / nom, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def test_transformer_vert_extrait_reel():
    lignes = [p2.transformer_vert(l) for l in _dicts("vert_extrait.csv")]
    assert {l["type_depense"] for l in lignes} == {
        "Crédits budgétaires", "Taxes affectées plafonnées", "Dépenses fiscales"}
    # ligne réelle 110-02-20 (APD), montants du 19/08/2026
    apd = next(l for l in lignes if l["code_depense"] == "110-02-20")
    assert apd["mission"] == "Aide publique au développement"
    assert apd["numero_programme"] == 110
    assert apd["execution_2024_cp"] == pytest.approx(11108676.03)
    assert apd["plf_2026_cp"] == pytest.approx(17200000.0)
    assert "PLF 2026" in apd["etiquette_2026"]
    # champs vides → None, jamais 0 (ligne réelle 181-15, exécution absente)
    vide = next(l for l in lignes if l["code_depense"] == "181-15")
    assert vide["execution_2024_cp"] is None
    assert vide["plf_2026_cp"] == pytest.approx(15000000.0)


def test_transformer_destination_extrait_reel():
    lignes = [p2.transformer_destination(l) for l in _dicts("dest_extrait.csv")]
    assert {l["typebudget"] for l in lignes} == {"BG", "BA", "CAS", "CCF"}
    premier = lignes[0]  # Travail et emploi, apprentissage
    assert premier["exercice"] == 2025
    assert premier["loi"] == "PLF"
    assert premier["autorisation_engagement"] == pytest.approx(3243144901.0)
    assert premier["credit_de_paiement"] == pytest.approx(3464537422.0)
    assert premier["libelle_sous_action"] == "Aides aux employeurs d'apprentis"


def test_transformer_subvention_extrait_reel():
    lignes = [p2.transformer_subvention(l) for l in _dicts("assos_extrait.csv")]
    par_cog = {l["cog_code"]: l for l in lignes}
    # SIREN « NR\nCHORUS » → NULL ; dénomination débarrassée des U+00A0
    nr = par_cog["98714"]
    assert nr["siren"] is None
    assert " " not in (nr["denomination"] or "")
    assert "\n" not in (nr["denomination"] or "")
    # départements dérivés du COG
    assert par_cog["75117"]["departement"] == "75"
    assert par_cog["2A228"]["departement"] == "2A"
    assert par_cog["2B087"]["departement"] == "2B"
    assert par_cog["97616"]["departement"] == "976"
    assert par_cog["98714"]["departement"] is None   # Polynésie : pas un dept
    assert par_cog["99326"]["departement"] is None   # étranger
    assert par_cog["Oui"]["departement"] is None     # ligne Chorus décalée
    # montants typés, année du millésime posée
    assert all(isinstance(l["montant"], float) for l in lignes)
    assert all(l["annee_versement"] == 2023 for l in lignes)
    assert par_cog["75117"]["siren"] == "399990696"


def test_controler_p2_refuse_echantillon_incomplet():
    verts = [p2.transformer_vert(l) for l in _dicts("vert_extrait.csv")]
    dests = [p2.transformer_destination(l) for l in _dicts("dest_extrait.csv")]
    assos = [p2.transformer_subvention(l) for l in _dicts("assos_extrait.csv")]
    with pytest.raises(ValueError, match="lignes"):
        p2.controler(verts, dests, assos)  # extraits trop petits : refusés


# ---------------------------------------------------------------------------
# Intégration réelle (réseau) — base jetable via FT_DB_PATH
# ---------------------------------------------------------------------------


def _reseau_disponible() -> bool:
    try:
        socket.create_connection(("data.economie.gouv.fr", 443), timeout=5).close()
        return True
    except OSError:
        return False


@pytest.mark.reseau
def test_integration_p1_p2_base_jetable(monkeypatch, tmp_path):
    if not _reseau_disponible():
        pytest.skip("pas de réseau vers data.economie.gouv.fr")
    chemin = tmp_path / "test_budget.db"
    monkeypatch.setenv("FT_DB_PATH", str(chemin))

    assert p1.main() == 0
    assert p2.main() == 0

    conn = sqlite3.connect(chemin)
    conn.row_factory = sqlite3.Row
    # P1 : série mensuelle 2013 → ≥ 06/2026, 26 lignes
    n, lignes, date_max = conn.execute(
        "SELECT count(*), count(DISTINCT ligne_id), max(date_fin_mois) "
        "FROM budget_mensuel").fetchone()
    assert lignes == 26
    assert n >= 26 * 160
    assert date_max >= "2026-06-30"
    cumul = conn.execute(
        "SELECT montant_cumul, montant_cumul_n1 FROM budget_mensuel "
        "WHERE ligne = 'Total dépenses nettes du budget général' "
        "AND date_fin_mois = ?", (date_max,)).fetchone()
    assert 100e9 <= cumul["montant_cumul"] <= 800e9   # ordre de grandeur
    assert cumul["montant_cumul_n1"] is not None      # variation N−1 servie
    # P2 : structure et subventions
    assert conn.execute("SELECT count(DISTINCT mission) FROM budget_vert "
                        ).fetchone()[0] >= 40
    total_plf26 = conn.execute(
        "SELECT sum(plf_2026_cp) FROM budget_vert "
        "WHERE type_depense = 'Crédits budgétaires'").fetchone()[0]
    assert 300e9 <= total_plf26 <= 800e9
    assert conn.execute("SELECT count(*) FROM budget_destination_2025"
                        ).fetchone()[0] >= 2000
    n_subv, total_subv = conn.execute(
        "SELECT count(*), sum(montant) FROM subventions_associations").fetchone()
    assert n_subv >= 100_000
    assert 3e9 <= total_subv <= 40e9
    # fraîcheur par source
    metas = {r["source_id"]: r for r in conn.execute(
        "SELECT * FROM meta_sources WHERE source_id IN ('S13','S20','S21','S23')")}
    assert set(metas) == {"S13", "S20", "S21", "S23"}
    assert metas["S13"]["date_donnees"] >= "2026-06-30"
    assert metas["S23"]["date_donnees"] == "2023-12-31"
    conn.close()


# ---------------------------------------------------------------------------
# Scories Chorus du jaune budgétaire
# ---------------------------------------------------------------------------


def test_nettoyer_texte_repare_le_mojibake_du_jaune():
    """Défaut PRÉSENT DANS LE CSV publié, pas introduit par le pipeline :
    `grep Ivoire jaune_associations_2023.csv` rend « Côte dâ€™Ivoire »."""
    assert p2.nettoyer_texte("Côte dâ€™Ivoire") == "Côte d’Ivoire"


def test_nettoyer_texte_ne_touche_pas_aux_libelles_legitimes():
    assert p2.nettoyer_texte("BÂTIMENT DE FRANCE") == "BÂTIMENT DE FRANCE"


def test_etat_administratif_zero_devient_null():
    """« 0 » est l'absence d'état, pas un état : 3 638 lignes sur 112 722."""
    assert p2.nettoyer_etat_administratif("0") is None
    assert p2.nettoyer_etat_administratif("") is None


def test_etat_administratif_conserve_les_vraies_valeurs():
    """« Non déterminé » appartient à la nomenclature source : on le garde."""
    assert p2.nettoyer_etat_administratif("Actif") == "Actif"
    assert p2.nettoyer_etat_administratif("Non déterminé") == "Non déterminé"
    # « Fermé <nombre> » : numéro de série de date, époque non documentée.
    # On ne convertit pas — publier une date devinée serait pire que le
    # laisser tel quel (cf. § M6).
    assert p2.nettoyer_etat_administratif("Fermé  \n17532") == "Fermé 17532"

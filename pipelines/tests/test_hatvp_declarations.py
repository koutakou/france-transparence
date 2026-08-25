"""Tests du pipeline P15 (ingest_hatvp_declarations) : declarations.xml (S15).

Deux fixtures, de deux natures différentes — et cette différence est le sujet
même du lot de tests :

- `fixtures/hatvp/declarations_extrait.xml` : extrait RÉEL du fichier du
  14/08/2026, deux déclarations d'intérêts et d'activités publiées, rubriques
  d'intérêts reprises octet pour octet. Seuls les blocs de TIERS (conjoint,
  collaborateurs) et les coordonnées du déclarant y portent des témoins
  fabriqués — le dépôt n'a pas à republier ce que le pipeline refuse.
- `fixtures/hatvp/declarations_patrimoine_fabrique.xml` : ENTIÈREMENT inventé.
  Il porte des blocs patrimoniaux, et le contenu d'une déclaration de
  situation patrimoniale ne se recopie pas dans un dépôt public (art. LO 135-2
  du code électoral). Copier un vrai bloc patrimonial pour vérifier qu'on ne
  le publie pas serait le publier.

Le test central du lot est `test_double_barriere_*` : il vérifie non seulement
que le patrimoine est refusé, mais que chacune des deux barrières suffit SEULE,
et — c'est le point le plus important — que le test échouerait vraiment si la
barrière par nom de balise sautait (`test_barriere_2_est_bien_porteuse`).

Les tests réseau sont marqués `@pytest.mark.reseau` (désélection : -m "not reseau").
"""

import sqlite3
from pathlib import Path

import pytest

from pipelines import db
from pipelines import ingest_hatvp_declarations as p15

FIXTURES = Path(__file__).parent / "fixtures" / "hatvp"
EXTRAIT_REEL = FIXTURES / "declarations_extrait.xml"
PATRIMOINE_FABRIQUE = FIXTURES / "declarations_patrimoine_fabrique.xml"

# Identités des deux déclarations réelles de la fixture, normalisées comme le
# fait la clé d'appariement (nom + prénom sans accents en majuscules +
# naissance ISO). Elles servent d'index d'élus « de laboratoire ».
ELU_UN = (p15.normaliser_identite("Nosbé"), p15.normaliser_identite("Sandrine"), "1972-10-29")
ELU_DEUX = (p15.normaliser_identite("AVIRAGNET"), p15.normaliser_identite("joel"), "1956-06-16")

# Témoins plantés dans la fixture réelle à la place des données de tiers et des
# coordonnées : s'ils apparaissent quelque part en sortie, une exclusion a sauté.
TEMOINS_INTERDITS = ("TEMOIN-TIERS-", "TEMOIN-CONTACT-")

# Témoins des blocs patrimoniaux fabriqués : même principe, pour le patrimoine.
TEMOIN_PATRIMOINE = "PATRIMOINE-FABRIQUE-"


@pytest.fixture()
def index_deux_elus():
    """Index d'appariement contenant les deux déclarants réels de la fixture."""
    return {ELU_UN: "elu-un", ELU_DEUX: "elu-deux"}


@pytest.fixture()
def index_fixture_patrimoine():
    """Index couvrant les trois déclarants fabriqués de la fixture patrimoine.

    Ils sont TOUS appariés à dessein : si une déclaration est écartée, ce ne
    peut donc être que par une barrière, jamais par défaut d'appariement.
    """
    return {
        (p15.normaliser_identite("PERSONNE-FIXTURE-UN"),
         p15.normaliser_identite("Fictive"), "1970-01-01"): "fixture-un",
        (p15.normaliser_identite("PERSONNE-FIXTURE-DEUX"),
         p15.normaliser_identite("Fictif"), "1971-02-02"): "fixture-deux",
        (p15.normaliser_identite("PERSONNE-FIXTURE-TROIS"),
         p15.normaliser_identite("Fictive"), "1972-03-03"): "fixture-trois",
    }


@pytest.fixture()
def conn(tmp_path):
    c = db.init_db(chemin=tmp_path / "test_hatvp_declarations.db")
    yield c
    c.close()


def toutes_les_valeurs(donnees: dict) -> list[str]:
    """Toutes les chaînes réellement produites (entêtes, lignes, montants).

    Sert aux tests « rien de tel n'a survécu » : on ne cherche pas dans les
    colonnes que l'on soupçonne, on cherche PARTOUT.
    """
    valeurs: list[str] = []
    for entete in donnees["entetes"]:
        valeurs += [str(v) for v in entete.values() if v is not None]
    for rubrique in donnees["rubriques"]:
        valeurs += [str(v) for v in rubrique if v is not None]
    for ligne in donnees["lignes"]:
        valeurs += [str(v) for k, v in ligne.items() if v is not None and k != "montants"]
        for annee, montant, brut_net in ligne["montants"]:
            valeurs += [annee, montant, str(brut_net)]
    return valeurs


# ---------------------------------------------------------------------------
# Parsing en flux, fixture réelle
# ---------------------------------------------------------------------------


def test_parcours_en_flux_de_la_fixture_reelle(index_deux_elus):
    donnees = p15.parcourir(EXTRAIT_REEL, index_deux_elus)
    stats = donnees["stats"]
    assert stats["declarations_lues"] == 2
    assert stats["rattachees"] == 2
    assert stats["elus_apparies"] == 2
    assert stats["refus_type_declaration"] == 0
    # 5 activités professionnelles + (2 mandats, 3 organes dirigeants,
    # 1 participation financière) : les valeurs sont celles du fichier réel.
    assert stats["lignes"] == 11 == len(donnees["lignes"])
    # Les sept rubriques sont décrites pour chacune des deux déclarations,
    # qu'elles soient renseignées ou « néant » : c'est ce qui permettra à
    # l'écran de dire « rien à déclarer » sans jamais l'inventer.
    assert len(donnees["rubriques"]) == 14
    assert stats["rubriques_neant"] == 6 + 4


def test_rubriques_verbatim_et_montants_dates(index_deux_elus):
    donnees = p15.parcourir(EXTRAIT_REEL, index_deux_elus)
    par_cle = {(l["declaration_uuid"], l["rubrique"], l["rang"]): l for l in donnees["lignes"]}
    activite = par_cle[("0031372d-bbfc-4cf2-913a-4b7b31ae3603", "activite_5ans", 1)]
    assert activite["libelle"] == "XPPER"
    assert activite["description"] == "Gestionnaire de paie"
    assert activite["date_debut"] == "10/2022"          # verbatim, jamais recomposé
    assert activite["montants"] == [
        ("2022", "5 755", "Net"),
        ("2023", "24 720", "Net"),
        ("2024", "12 125", "Net"),
    ]


def test_zero_declare_reste_un_zero_declare(index_deux_elus):
    """« 0 » saisi par la personne est une donnée ; il ne doit pas devenir NULL.

    Le pendant de la règle du projet (une absence ne s'affiche jamais « 0 »)
    est qu'un zéro RÉELLEMENT déclaré ne doit pas être effacé : la deuxième
    déclaration de la fixture porte un mandat de conseiller municipal
    rémunéré 0 € cinq années de suite, et c'est ce qu'elle dit.
    """
    donnees = p15.parcourir(EXTRAIT_REEL, index_deux_elus)
    mandats = [l for l in donnees["lignes"] if l["rubrique"] == "mandat_electif"]
    zeros = [m for m in mandats if all(v == "0" for _, v, _ in m["montants"])]
    assert len(zeros) == 1
    assert [a for a, _, _ in zeros[0]["montants"]] == ["2018", "2019", "2020", "2021", "2022"]
    # Et le champ vide, lui, reste vide : `evaluation` vaut « 0 » (déclaré),
    # tandis qu'un champ non renseigné vaut None (cf. test_nettoyer_*).
    participation = [l for l in donnees["lignes"]
                     if l["rubrique"] == "participation_financiere"][0]
    assert participation["evaluation"] == "0"


# ---------------------------------------------------------------------------
# LE test du lot : la double barrière
# ---------------------------------------------------------------------------


def test_double_barriere_refuse_le_patrimoine(index_fixture_patrimoine):
    """Le cas complet, sur la fixture fabriquée : rien de patrimonial ne passe.

    - la DSP est refusée ENTIÈREMENT par la barrière 1, y compris sa rubrique
      d'intérêts pourtant légitime ;
    - la DIAM (type hors liste blanche) est refusée par la même barrière ;
    - la DI MENTEUSE — type d'intérêts annoncé, cinq blocs patrimoniaux à
      l'intérieur — passe la barrière 1 et se fait arrêter par la barrière 2 :
      elle laisse exactement une ligne, son mandat électif.
    """
    donnees = p15.parcourir(PATRIMOINE_FABRIQUE, index_fixture_patrimoine)
    stats = donnees["stats"]
    assert stats["declarations_lues"] == 3
    assert stats["refus_type_declaration"] == 2          # la DSP et la DIAM
    assert stats["rattachees"] == 1                      # la seule DI menteuse
    assert [e["uuid"] for e in donnees["entetes"]] == ["DI-MENTEUSE-0000-0000-000000000002"]
    # La barrière 2 a réellement travaillé : cinq blocs refusés par leur nom.
    assert stats["refus_balise_patrimoine"] == 5
    assert stats["lignes"] == 1
    assert donnees["lignes"][0]["rubrique"] == "mandat_electif"
    # Et surtout : aucune trace, nulle part, du contenu patrimonial fabriqué.
    assert not [v for v in toutes_les_valeurs(donnees) if TEMOIN_PATRIMOINE in v]


def test_barriere_1_seule_suffit(monkeypatch, index_fixture_patrimoine):
    """Barrière 2 démontée : la barrière 1 tient encore sur la DSP.

    On vide la liste noire des balises ET on inscrit les balises patrimoniales
    parmi les rubriques ingérées — c'est-à-dire le pire scénario de
    négligence. La déclaration typée DSP est malgré tout refusée en entier :
    elle n'a jamais franchi le contrôle de type.
    """
    monkeypatch.setattr(p15, "BALISES_PATRIMOINE", frozenset())
    monkeypatch.setattr(p15, "RUBRIQUES", dict(p15.RUBRIQUES, **{
        "immeubleDto": p15.Rubrique("immeuble", 90, "Immeuble", "designation", None, False, False),
    }))
    donnees = p15.parcourir(PATRIMOINE_FABRIQUE, index_fixture_patrimoine)
    uuids = {e["uuid"] for e in donnees["entetes"]}
    assert "DSP-FABRIQUE-0000-0000-000000000001" not in uuids
    assert "DIAM-FABRIQUE-0000-0000-00000000003" not in uuids


def test_barriere_2_seule_suffit(monkeypatch, index_fixture_patrimoine):
    """Barrière 1 démontée : la barrière 2 tient encore sur les balises.

    On force l'acceptation du type DSP (liste blanche élargie, liste noire des
    types vidée). Les deux déclarations patrimoniales entrent donc dans le
    parcours — et leurs blocs patrimoniaux se font refuser un par un, par leur
    seul nom de balise. Aucune ligne patrimoniale n'est produite.
    """
    monkeypatch.setattr(p15, "TYPES_INTERETS", frozenset({"DI", "DIA", "DSP", "DIAM"}))
    monkeypatch.setattr(p15, "TYPES_PATRIMOINE", frozenset())
    donnees = p15.parcourir(PATRIMOINE_FABRIQUE, index_fixture_patrimoine)
    stats = donnees["stats"]
    assert stats["refus_type_declaration"] == 0          # la barrière 1 ne filtre plus rien
    assert stats["rattachees"] == 3                      # les trois déclarations entrent
    assert stats["refus_balise_patrimoine"] == 6         # 1 (DSP) + 5 (DI menteuse)
    assert {l["rubrique"] for l in donnees["lignes"]} == {"mandat_electif"}
    assert not [v for v in toutes_les_valeurs(donnees) if TEMOIN_PATRIMOINE in v]


def test_barriere_2_est_bien_porteuse(monkeypatch, index_fixture_patrimoine):
    """Preuve que le test précédent n'est pas creux : sans elle, ça fuit.

    On démonte la barrière 2 pour de bon — liste noire vidée ET balise
    patrimoniale inscrite parmi les rubriques ingérées — sur la déclaration
    MENTEUSE, celle que la barrière 1 laisse passer par construction. Le
    contenu patrimonial fabriqué apparaît alors dans les lignes produites.
    C'est exactement ce que `test_double_barriere_refuse_le_patrimoine`
    interdit : ce test-ci mesure ce que l'autre protège.
    """
    monkeypatch.setattr(p15, "BALISES_PATRIMOINE", frozenset())
    monkeypatch.setattr(p15, "RUBRIQUES", dict(p15.RUBRIQUES, **{
        "immeubleDto": p15.Rubrique("immeuble", 90, "Immeuble", "designation", None, False, False),
    }))
    donnees = p15.parcourir(PATRIMOINE_FABRIQUE, index_fixture_patrimoine)
    fuites = [v for v in toutes_les_valeurs(donnees) if TEMOIN_PATRIMOINE in v]
    assert fuites, ("la barrière 2 démontée ne laisse rien fuir : la fixture "
                    "ne prouve plus rien, elle doit être revue")
    assert stats_rubriques(donnees) == {"mandat_electif", "immeuble"}


def stats_rubriques(donnees: dict) -> set[str]:
    return {l["rubrique"] for l in donnees["lignes"]}


def test_barrieres_en_fonctions_pures():
    """Les deux barrières, prises isolément, disent bien ce qu'elles doivent."""
    assert p15.type_declaration_accepte("DI")
    assert p15.type_declaration_accepte("dia")           # casse indifférente
    for refuse in ("DSP", "DSPM", "DSPFM", "DIM", "DIAM", "", None, "INCONNU"):
        assert not p15.type_declaration_accepte(refuse)
    for balise in p15.RUBRIQUES:
        assert p15.balise_acceptee(balise)
    for balise in p15.BALISES_PATRIMOINE | p15.BALISES_TIERS:
        assert not p15.balise_acceptee(balise)
    assert not p15.balise_acceptee("evenementMajeurDto")  # inconnu = refusé


def test_listes_blanche_et_noire_disjointes():
    """Une balise ne peut pas être des deux côtés — vérifié aussi à l'import."""
    assert not set(p15.RUBRIQUES) & p15.BALISES_PATRIMOINE
    assert not set(p15.RUBRIQUES) & p15.BALISES_TIERS
    assert len(p15.BALISES_PATRIMOINE) == 14


# ---------------------------------------------------------------------------
# Exclusions éthiques et coordonnées
# ---------------------------------------------------------------------------


def test_blocs_de_tiers_et_coordonnees_jamais_persistes(index_deux_elus):
    """Conjoint, collaborateurs, e-mail, téléphone, adresse : rien ne sort.

    Les témoins sont plantés dans la fixture réelle à la place exacte de ces
    données. On les cherche dans TOUTES les valeurs produites, pas seulement
    dans les colonnes où on les attendrait.
    """
    donnees = p15.parcourir(EXTRAIT_REEL, index_deux_elus)
    valeurs = toutes_les_valeurs(donnees)
    assert valeurs, "la fixture ne produit rien : le test ne prouverait rien"
    for temoin in TEMOINS_INTERDITS:
        assert not [v for v in valeurs if temoin in v]


# ---------------------------------------------------------------------------
# Hygiène du texte source
# ---------------------------------------------------------------------------


def test_nettoyer_retire_le_marqueur_de_caviardage():
    # Le marqueur seul : le champ n'a pas de valeur, il devient une absence.
    assert p15.nettoyer("[Données non publiées]") is None
    assert p15.nettoyer("\n        [Données non publiées]\n    ") is None
    # Le marqueur qui DÉBORDE : le texte métier survit, le marqueur part.
    assert p15.nettoyer("SCEA [Données non publiées]") == "SCEA"
    assert p15.nettoyer("SCI [Données non publiées]") == "SCI"
    assert p15.nettoyer("Credit Agricole [Données non publiées]") == "Credit Agricole"
    # Une chaîne vide est une absence, jamais une chaîne vide stockée.
    assert p15.nettoyer("") is None
    assert p15.nettoyer(None) is None
    assert p15.nettoyer("   ") is None
    # Un « 0 » déclaré n'est PAS une absence.
    assert p15.nettoyer("0") == "0"


def test_marqueur_retire_dans_la_fixture_reelle(index_deux_elus):
    donnees = p15.parcourir(EXTRAIT_REEL, index_deux_elus)
    assert not [v for v in toutes_les_valeurs(donnees) if "non publi" in v.lower()]
    # La société dont le libellé source est « SCI [Données non publiées] »
    # ressort « SCI » : le texte métier n'a pas été perdu avec le marqueur.
    libelles = {l["libelle"] for l in donnees["lignes"]}
    assert "SCI" in libelles


def test_montant_vide_nest_jamais_un_zero(index_fixture_patrimoine):
    """Une année sans montant est écartée, pas stockée à 0.

    La DI menteuse déclare un montant pour 2025 et une année 2024 SANS
    montant : seul 2025 doit ressortir. Écrire « 2024 : 0 € » serait
    affirmer, sous le nom de quelqu'un, une rémunération nulle qu'il n'a
    jamais déclarée.
    """
    donnees = p15.parcourir(PATRIMOINE_FABRIQUE, index_fixture_patrimoine)
    montants = donnees["lignes"][0]["montants"]
    assert montants == [("2025", "22 222", "Brut")]


def test_date_iso_ne_devine_jamais():
    assert p15.date_iso("29/11/2024 18:54:22") == "2024-11-29"
    assert p15.date_iso("01/04/2024") == "2024-04-01"
    for illisible in ("", None, "2024-11-29", "31/02/2024", "novembre 2024"):
        assert p15.date_iso(illisible) is None


def test_normaliser_identite():
    assert p15.normaliser_identite("Nosbé") == "NOSBE"
    assert p15.normaliser_identite("d'Ornano") == "D ORNANO"
    assert p15.normaliser_identite("Jean-Luc") == "JEAN LUC"
    assert p15.normaliser_identite(None) == ""


# ---------------------------------------------------------------------------
# Appariement
# ---------------------------------------------------------------------------


def _inserer_elu(conn, ident, nom, prenom, naissance, type_mandat="depute"):
    conn.execute(
        "INSERT INTO elus (id, nom, prenom, date_naissance, mandats)"
        " VALUES (?, ?, ?, ?, ?)",
        (ident, nom, prenom, naissance,
         '[{"source": "RNE", "type": "%s"}]' % type_mandat))


def test_index_elus_restreint_aux_fiches_et_sans_homonyme(conn):
    _inserer_elu(conn, "PA1", "Nosbé", "Sandrine", "1972-10-29")
    _inserer_elu(conn, "SEN-1", "AVIRAGNET", "joel", "1956-06-16", "senateur")
    # Un maire : hors population des fiches publiées → hors index.
    _inserer_elu(conn, "rne-1", "Dupont", "Jean", "1960-01-01", "maire")
    # Deux homonymes nés le même jour, tous deux députés : non tranchables.
    _inserer_elu(conn, "PA2", "Martin", "Camille", "1965-05-05")
    _inserer_elu(conn, "PA3", "Martin", "Camille", "1965-05-05")
    index = p15.construire_index_elus(conn)
    assert index[ELU_UN] == "PA1"
    assert index[ELU_DEUX] == "SEN-1"
    assert (p15.normaliser_identite("Dupont"), "JEAN", "1960-01-01") not in index
    assert (p15.normaliser_identite("Martin"), "CAMILLE", "1965-05-05") not in index


def _souple(fiches):
    """Index souple bâti à la main : [(id, nom, prénom, naissance)]."""
    index = {}
    for ident, nom, prenom, naissance in fiches:
        fiche = {"id": ident, "naissance": naissance,
                 "prenom": p15.composantes_identite(prenom)}
        for composante in p15.composantes_identite(nom):
            index.setdefault((naissance[:4], composante), []).append(fiche)
    return index


@pytest.mark.parametrize("motif, nom_fiche, prenom_fiche, naissance_fiche", [
    # L'Assemblée écrit « Borchio Fontimp » là où `declarations.xml` écrit « FONTIMP ».
    ("nom composé porté en entier d'un seul côté", "Nosbé-Durand", "Sandrine", "1972-10-29"),
    # « Ricourt Vaginay » / « Vaginay » : la composante commune est en FIN de nom.
    ("composante commune en fin de nom", "Ricourt Nosbé", "Sandrine", "1972-10-29"),
    # L'Assemblée désambiguïse ses homonymes par le département.
    ("suffixe entre parenthèses", "Nosbé (Gironde)", "Sandrine", "1972-10-29"),
    # « K/Bidi » / « KBIDI » : ponctuation interne divergente.
    ("ponctuation interne", "No/sbé", "Sandrine", "1972-10-29"),
    # « Robert Wienie » / « Robert » : prénom composé tronqué à la source.
    ("prénom composé tronqué", "Nosbé", "Sandrine-Claire", "1972-10-29"),
    # Deux sources officielles qui divergent d'un chiffre sur l'état civil.
    ("date : le mois diverge", "Nosbé", "Sandrine", "1972-03-29"),
    ("date : le jour diverge", "Nosbé", "Sandrine", "1972-10-28"),
])
def test_repli_rattache_les_orthographes_divergentes(
        motif, nom_fiche, prenom_fiche, naissance_fiche):
    """Chaque écart d'écriture mesuré entre `declarations.xml` et l'amont.

    Sans le repli, la déclaration est JETÉE en silence (`non_apparie`) alors
    que la personne a une fiche sur le site.
    """
    souple = _souple([("elu-souple", nom_fiche, prenom_fiche, naissance_fiche)])
    # Clé exacte vide : seul le repli peut rattacher.
    donnees = p15.parcourir(EXTRAIT_REEL, {}, souple)
    assert donnees["stats"]["rattachees_par_repli"] >= 1, f"non rattaché : {motif}"
    assert {e["elu_id"] for e in donnees["entetes"]} == {"elu-souple"}


def test_repli_est_strictement_additif_jamais_prioritaire():
    """La clé exacte gagne toujours. Le repli n'est consulté qu'après son échec.

    C'est ce qui garantit qu'activer le repli ne DÉPLACE aucune déclaration
    déjà rattachée : il ne peut qu'en ajouter.
    """
    souple = _souple([("elu-souple", "Nosbé-Durand", "Sandrine", "1972-10-29")])
    donnees = p15.parcourir(EXTRAIT_REEL, {ELU_UN: "elu-un"}, souple)
    entetes = [e for e in donnees["entetes"] if e["elu_id"] in ("elu-un", "elu-souple")]
    assert entetes, "la fixture doit rattacher au moins une déclaration"
    assert all(e["elu_id"] == "elu-un" for e in entetes)


def test_repli_rejette_une_date_a_deux_composantes_decart():
    """L'année seule ne suffit pas : la date doit AUSSI être voisine.

    Test né d'un mutation-testing : retirer l'appel à `dates_voisines` de
    `apparier_souple` ne faisait tomber AUCUN test, parce que l'année est
    portée par la clé d'index et que les autres cas ne varient que d'une
    composante. Ici la fiche a la même année mais le mois ET le jour
    diffèrent — seul `dates_voisines` peut la rejeter.
    """
    souple = _souple([("elu-souple", "Nosbé-Durand", "Sandrine", "1972-03-28")])
    donnees = p15.parcourir(EXTRAIT_REEL, {}, souple)
    assert donnees["stats"]["rattachees_par_repli"] == 0
    assert donnees["entetes"] == []


def test_repli_dans_lautre_sens_xml_composé_fiche_simple():
    """Le nom composé peut être du côté de la DÉCLARATION, pas de la fiche.

    Huit des trente-deux cas réels sont dans ce sens — « TACHE DE LA PAGERIE »,
    « GILLES EPOUSE VASSAL », « JULIEN EMMANUEL LUREL », « DE MARCO TRUEL » —
    et aucun test ne l'exerçait : les fixtures mettaient toujours le nom
    composé du côté de la fiche. L'intersection de composantes est symétrique,
    ce test le verrouille.
    """
    # La fiche porte le nom SIMPLE ; c'est la déclaration qui est composée.
    # `EXTRAIT_REEL` déclare « Nosbé / Sandrine », donc on inverse en donnant à
    # la fiche un nom dont « NOSBE » n'est qu'une composante.
    souple = _souple([("elu-simple", "Nosbé de la Pagerie", "Sandrine", "1972-10-29")])
    donnees = p15.parcourir(EXTRAIT_REEL, {}, souple)
    assert donnees["stats"]["rattachees_par_repli"] >= 1
    assert {e["elu_id"] for e in donnees["entetes"]} == {"elu-simple"}


def test_le_repli_reste_un_appoint_mesure():
    """Le repli doit rester marginal — sinon c'est la clé exacte qui est tombée.

    Contre-épreuve mesurée le 26/08/2026 sur `declarations.xml` : clé exacte
    anéantie, le repli SEUL rattache 2 308 déclarations, très au-dessus du
    plancher de 1 000 de `main()`. Sans le garde-fou de proportion, une panne
    totale de l'appariement passerait donc inaperçue. Ce test verrouille le
    seuil pour que personne ne le desserre sans le vouloir.
    """
    souple = _souple([("elu-souple", "Nosbé-Durand", "Sandrine", "1972-10-29")])
    donnees = p15.parcourir(EXTRAIT_REEL, {}, souple)
    stats = donnees["stats"]
    # Sur cette fixture, tout passe par le repli : la proportion vaut 100 %,
    # donc très au-dessus du seuil que `main()` refuse.
    assert stats["rattachees"] > 0
    assert stats["rattachees_par_repli"] == stats["rattachees"]
    assert stats["rattachees_par_repli"] > 0.15 * stats["rattachees"]


def test_repli_refuse_de_trancher_une_homonymie():
    """Deux fiches également plausibles : on renonce, on n'en choisit pas une.

    Attribuer la déclaration d'intérêts d'une personne à son homonyme est la
    faute la plus grave que ce pipeline puisse commettre.
    """
    souple = _souple([("elu-a", "Nosbé-Durand", "Sandrine", "1972-10-29"),
                      ("elu-b", "Nosbé-Martin", "Sandrine", "1972-10-29")])
    donnees = p15.parcourir(EXTRAIT_REEL, {}, souple)
    assert donnees["stats"]["rattachees_par_repli"] == 0
    assert donnees["entetes"] == []


def test_repli_exige_lannee_de_naissance():
    """Même nom, même prénom, autre ANNÉE : deux personnes, pas une.

    C'est ce qui empêche la tolérance de dégénérer en appariement par le seul
    patronyme, sur un vivier où 4 200 déclarations non appariées frottent
    contre un millier de fiches.
    """
    souple = _souple([("elu-souple", "Nosbé-Durand", "Sandrine", "1975-10-29")])
    donnees = p15.parcourir(EXTRAIT_REEL, {}, souple)
    assert donnees["stats"]["rattachees_par_repli"] == 0


def test_repli_exige_une_composante_de_prenom_commune():
    """Le nom seul ne suffit jamais : deux frères ne sont pas la même personne."""
    souple = _souple([("elu-souple", "Nosbé", "Bertrand", "1972-10-29")])
    donnees = p15.parcourir(EXTRAIT_REEL, {}, souple)
    assert donnees["stats"]["rattachees_par_repli"] == 0


def test_composantes_identite_et_dates_voisines():
    """Les deux primitives du repli, sur les écritures réellement mesurées."""
    ci = p15.composantes_identite
    assert {"FAVENNEC", "BECOT"} <= ci("Favennec-Bécot")
    # Le suffixe de désambiguïsation de l'AN n'appartient pas au patronyme.
    assert ci("Martin (Alpes-Maritimes)") == ci("MARTIN")
    # La forme recollée absorbe une ponctuation interne divergente.
    assert ci("K/Bidi") & ci("KBIDI")
    # Une composante commune en FIN de nom compte autant qu'en tête.
    assert ci("Ricourt Vaginay") & ci("VAGINAY")
    assert ci("") == frozenset()
    # Les particules ne sont JAMAIS appariantes : « LE » est porté par 18 fiches
    # servies et « DE » par 14. Sans ce filtre, « LE MEUR Marie » pourrait
    # s'apparier à « LE GAC Marie » de la même année sur la seule syllabe.
    assert "LE" not in ci("Le Meur") and "MEUR" in ci("Le Meur")
    assert "DE" not in ci("de Courson") and "COURSON" in ci("de Courson")
    assert not (ci("Le Meur") & ci("Le Gac"))
    # Un nom d'un seul mot, fût-il court, reste apparaissant tel quel.
    assert ci("Vos") == frozenset({"VOS"})

    assert p15.dates_voisines("1969-09-29", "1969-03-29")    # le mois diverge
    assert p15.dates_voisines("1981-10-21", "1981-10-20")    # le jour diverge
    assert not p15.dates_voisines("1969-09-29", "1972-09-29")    # l'année, jamais
    assert not p15.dates_voisines("1969-09-29", "1969-03-28")    # deux composantes
    assert not p15.dates_voisines("1969-09-29", None)
    assert not p15.dates_voisines("1969-09-29", "29/09/1969")    # format non ISO


def test_appariement_exige_la_date_de_naissance():
    """Même nom, même prénom, autre date de naissance = pas d'appariement.

    C'est le prix de la clé retenue, et la raison de la retenir : 588 couples
    nom+prénom sont partagés par au moins deux personnes dans `elus`, et
    attribuer une déclaration au mauvais homonyme serait la faute la plus
    grave possible ici.
    """
    presque = {(ELU_UN[0], ELU_UN[1], "1972-10-30"): "elu-un-decale"}
    donnees = p15.parcourir(EXTRAIT_REEL, presque)
    assert donnees["stats"]["rattachees"] == 0
    assert donnees["stats"]["non_apparie"] == 2
    assert donnees["lignes"] == []


# ---------------------------------------------------------------------------
# Écriture : idempotence et contrôle de sortie
# ---------------------------------------------------------------------------


def _compteurs(conn) -> tuple:
    return tuple(
        conn.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"]
        for table in ("hatvp_decl_interets", "hatvp_decl_rubriques",
                      "hatvp_decl_lignes", "hatvp_decl_montants")
    )


def test_ecriture_rejouable_sans_doubler(conn, index_deux_elus):
    donnees = p15.parcourir(EXTRAIT_REEL, index_deux_elus)
    p15.ecrire(conn, donnees)
    premiers = _compteurs(conn)
    assert premiers == (2, 14, 11, 28)
    p15.ecrire(conn, donnees)                    # rejoué à l'identique
    assert _compteurs(conn) == premiers
    # Les identifiants de lignes repartent de 1 : le résultat est reproductible
    # d'un run à l'autre, ce qui rend les fragments statiques stables.
    assert conn.execute(
        "SELECT min(id) AS m FROM hatvp_decl_lignes").fetchone()["m"] == 1


def test_ecriture_ne_stocke_ni_chaine_vide_ni_zero_fabrique(conn, index_deux_elus):
    p15.ecrire(conn, p15.parcourir(EXTRAIT_REEL, index_deux_elus))
    vides = conn.execute(
        "SELECT count(*) AS n FROM hatvp_decl_lignes"
        " WHERE libelle = '' OR description = '' OR commentaire = ''"
        "    OR evaluation = '' OR capital_detenu = '' OR nombre_parts = ''"
    ).fetchone()["n"]
    assert vides == 0
    assert conn.execute(
        "SELECT count(*) AS n FROM hatvp_decl_montants WHERE trim(montant) = ''"
    ).fetchone()["n"] == 0


def test_controle_de_sortie_refuse_une_rubrique_intruse(conn, index_deux_elus):
    p15.ecrire(conn, p15.parcourir(EXTRAIT_REEL, index_deux_elus))
    p15.controler_absence_patrimoine(conn)       # état nominal : rien à signaler
    # Simulation d'un chemin non prévu (migration, écriture manuelle) : une
    # ligne patrimoniale atterrit malgré les deux barrières.
    conn.execute(
        "INSERT INTO hatvp_decl_lignes (declaration_uuid, elu_id, rubrique,"
        " rubrique_ordre, rang, libelle) VALUES ('x', 'y', 'immeuble', 90, 1, 'z')")
    with pytest.raises(ValueError, match="LO 135-2"):
        p15.controler_absence_patrimoine(conn)


def test_aucune_colonne_numerique_pour_les_montants(conn):
    """Le schéma lui-même interdit l'agrégat : `montant` est du TEXTE.

    Ce n'est pas une coquetterie : les libellés amont ne supportent ni total
    ni classement (saisie libre, doublons, caviardage qui déborde). Ne pas
    créer la colonne numérique, c'est rendre l'agrégat impossible plutôt que
    déconseillé — et ce test empêche de la réintroduire par distraction.
    """
    conn.executescript(p15.SCHEMA_P15)
    types = {r["name"]: r["type"] for r in
             conn.execute("PRAGMA table_info(hatvp_decl_montants)")}
    assert types["montant"] == "TEXT"
    assert types["annee"] == "TEXT"
    types_lignes = {r["name"]: r["type"] for r in
                    conn.execute("PRAGMA table_info(hatvp_decl_lignes)")}
    for colonne in ("evaluation", "capital_detenu", "nombre_parts", "remuneration_libre"):
        assert types_lignes[colonne] == "TEXT"


def test_neant_distingue_le_rien_declare_de_la_donnee_absente(conn, index_deux_elus):
    """`neant` porte un FAIT ; l'absence de ligne porte une IGNORANCE.

    Une rubrique à `neant = 1` autorise l'écran à écrire « la personne a
    déclaré n'avoir rien à déclarer ». Une rubrique absente de la table, ou un
    élu absent de `hatvp_decl_interets`, n'autorise que « pas de donnée chez
    nous » — jamais « aucun intérêt déclaré ».
    """
    p15.ecrire(conn, p15.parcourir(EXTRAIT_REEL, index_deux_elus))
    lignes = conn.execute(
        "SELECT rubrique, neant, nb_lignes FROM hatvp_decl_rubriques"
        " WHERE declaration_uuid = '86ccc04e-6040-47ff-b499-26d30e51352f'"
        " ORDER BY rubrique_ordre").fetchall()
    par_rubrique = {r["rubrique"]: (r["neant"], r["nb_lignes"]) for r in lignes}
    assert par_rubrique["consultant"] == (1, 0)          # « néant » déclaré
    assert par_rubrique["mandat_electif"] == (0, 2)      # renseignée
    # L'élu qui n'a aucune déclaration chez nous n'a aucune rubrique : rien ne
    # permet d'écrire qu'il n'a rien déclaré, et c'est voulu.
    assert conn.execute(
        "SELECT count(*) AS n FROM hatvp_decl_interets WHERE elu_id = 'elu-absent'"
    ).fetchone()["n"] == 0


# ---------------------------------------------------------------------------
# Intégration réseau (désélection : -m "not reseau")
# ---------------------------------------------------------------------------


@pytest.mark.reseau
def test_reseau_url_reelle_et_ancienne_url_morte():
    from pipelines.common import session_http
    session = session_http()
    reponse = session.head(p15.URL_DECLARATIONS, timeout=60, allow_redirects=True)
    assert reponse.status_code == 200
    assert int(reponse.headers["Content-Length"]) > 50_000_000
    date_lm = p15.date_derniere_modification(session, p15.URL_DECLARATIONS)
    assert date_lm and len(date_lm) == 10
    # L'URL que l'on trouve encore citée ailleurs ne répond plus : le test le
    # dit, pour qu'on ne « corrige » pas l'URL du pipeline vers elle.
    morte = session.head("https://www.hatvp.fr/livraison/opendata/declarations.xml",
                         timeout=60, allow_redirects=True)
    assert morte.status_code == 404


@pytest.mark.reseau
def test_reseau_meme_generation_que_liste_csv():
    """Le Last-Modified suit celui de liste.csv (S14) : cadence hebdomadaire.

    C'est le fait qui tranche la cadence, data.gouv.fr annonçant « punctual ».
    Les deux fichiers sont régénérés dans la même minute ; on tolère un jour
    d'écart pour ne pas rendre le test fragile un soir de bascule de date.
    """
    from datetime import date as _date
    from pipelines.common import session_http
    session = session_http()
    xml = p15.date_derniere_modification(session, p15.URL_DECLARATIONS)
    csv = p15.date_derniere_modification(
        session, "https://www.hatvp.fr/livraison/opendata/liste.csv")
    assert xml and csv
    assert abs((_date.fromisoformat(xml) - _date.fromisoformat(csv)).days) <= 1

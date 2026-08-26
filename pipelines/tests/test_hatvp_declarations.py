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
# Perte de rattachement : le seul contrôle qui compare au cycle précédent
# ---------------------------------------------------------------------------


def test_uuids_vus_porte_aussi_les_declarations_non_appariees():
    """`parcourir` doit rendre les uuid QU'IL A JETÉS, pas seulement les gardés.

    C'est toute la matière du garde-fou : sans les uuid non appariés, on ne
    peut pas distinguer « la HATVP a retiré la déclaration » de « nous ne
    savons plus à qui elle appartient ».
    """
    donnees = p15.parcourir(EXTRAIT_REEL, {})          # aucun élu : rien n'apparie
    assert donnees["stats"]["rattachees"] == 0
    assert donnees["stats"]["non_apparie"] == 2
    assert len(donnees["uuids_vus"]) == 2
    # Et avec appariement, les mêmes uuid sont vus ET rattachés.
    avec = p15.parcourir(EXTRAIT_REEL, {ELU_UN: "PA1", ELU_DEUX: "PA2"})
    assert donnees["uuids_vus"] == avec["uuids_vus"]
    assert {e["uuid"] for e in avec["entetes"]} == avec["uuids_vus"]


def test_rattachements_precedents_se_tait_sur_une_base_neuve(conn):
    """Base sans table P15 — celle de la CI : le contrôle n'a rien à comparer.

    Il doit rendre un dictionnaire vide, jamais lever : une base neuve n'est
    pas une régression, et l'ingestion de la CI ne doit pas dépendre d'un état
    antérieur qui, par construction, n'existe pas.
    """
    conn.executescript("DROP TABLE IF EXISTS hatvp_decl_interets")
    assert p15.rattachements_precedents(conn) == {}
    p15.ecrire(conn, p15.parcourir(EXTRAIT_REEL, {ELU_UN: "PA1", ELU_DEUX: "PA2"}))
    precedents = p15.rattachements_precedents(conn)
    assert len(precedents) == 2
    assert set(precedents.values()) == {"PA1", "PA2"}


def test_perte_ignore_une_declaration_retiree_par_la_hatvp():
    """Le cas RÉEL du 21/08/2026 : la source retire, ce n'est pas une perte.

    Mesuré dans le journal de P15 : 6 611 → 6 608 déclarations dans le XML,
    2 263 → 2 261 rattachées (−0,088 %). Aucune régression : la donnée
    n'existe plus en amont. Ce test est aussi le témoin de mutation du
    garde-fou — retirer la condition « encore publiée » le fait tomber.
    """
    perdues, hors_fiche = p15.pertes_de_rattachement(
        precedents={"u-retiree": "PA1"},
        uuids_vus=set(),                       # la HATVP ne la publie plus
        rattachements={},
        fiches={"PA1"})
    assert perdues == []
    assert hors_fiche == []


def test_perte_voit_une_declaration_publiee_qui_se_detache():
    """Le cas mesuré par simulation le 26/08/2026 : −2 sur 2 332, et muet.

    Un homonyme de la même année entre dans `elus`, le garde-fou n° 3 du repli
    renonce, deux déclarations toujours publiées quittent la fiche de leur élu.
    Aucun seuil ne le voit (−0,086 % de rattachées, −0,03 % de lignes) : c'est
    la présence en amont, et elle seule, qui le rend visible.
    """
    perdues, hors_fiche = p15.pertes_de_rattachement(
        precedents={"u-1": "PA342384", "u-2": "PA342384", "u-3": "PA9"},
        uuids_vus={"u-1", "u-2", "u-3"},       # les trois sont toujours publiées
        rattachements={"u-3": "PA9"},          # PA342384 n'apparie plus
        fiches={"PA342384", "PA9"})
    assert perdues == [("u-1", "PA342384"), ("u-2", "PA342384")]
    assert hors_fiche == []


def test_perte_ignore_un_elu_qui_a_perdu_sa_fiche():
    """Fin de mandat : l'élu sort de `elus`, ses déclarations ne sont plus
    rattachables, et ce n'est pas une régression.

    Second témoin de mutation : retirer la restriction aux élus qui portent
    encore une fiche ferait échouer l'ingestion à chaque départ de député.
    Mais le cas ne doit pas pour autant être MUET — il ressort dans la seconde
    liste, que `executer()` journalise en avertissement.
    """
    perdues, hors_fiche = p15.pertes_de_rattachement(
        precedents={"u-1": "PA-parti"},
        uuids_vus={"u-1"},
        rattachements={},
        fiches=set())                          # plus aucune fiche
    assert perdues == []
    assert hors_fiche == [("u-1", "PA-parti")]


def test_perte_ignore_une_declaration_qui_change_delu():
    """La fusion des fiches `rne-*` DÉPLACE, elle ne détruit pas.

    Mesuré le 26/08/2026 sur une fusion simulée des six jumelles (FAVENNEC,
    VAGINAY, XOWIE, MARTIN, LUCAS, K/BIDI) : 14 déclarations déplacées,
    0 perdue, total inchangé à 2 332. Ce test verrouille le fait que le
    garde-fou ne bloquera pas cette fusion le jour où elle sera livrée.
    """
    perdues, hors_fiche = p15.pertes_de_rattachement(
        precedents={"u-1": "rne-abc", "u-2": "rne-abc"},
        uuids_vus={"u-1", "u-2"},
        rattachements={"u-1": "PA123", "u-2": "PA123"},   # déplacées vers le jumeau
        fiches={"rne-abc", "PA123"})
    assert perdues == []
    assert hors_fiche == []


def test_gardefou_detachement_dun_elu_sans_fiche_est_journalise(
        tmp_path, monkeypatch, caplog):
    """Fin de mandat : l'ingestion passe, mais elle le DIT.

    C'est la contrepartie de la restriction aux élus qui portent encore une
    fiche : elle évite de faire tomber le cycle à chaque départ de député, et
    elle ne doit pas pour autant rouvrir un chemin silencieux — un pipeline
    amont qui laisserait `elus` amputé détacherait des centaines de
    déclarations sans qu'aucun plancher ne morde.
    """
    import logging
    chemin = tmp_path / "p15_hors_fiche.db"
    monkeypatch.setenv("FT_DB_PATH", str(chemin))
    conn = db.init_db(chemin=chemin)
    _base_de_gardefou(conn, {"u-sans-fiche": "PA-inexistant"})
    conn.close()

    with caplog.at_level(logging.WARNING):
        stats = _executer_avec_parse_simule(monkeypatch, chemin,
                                            uuids_en_plus=("u-sans-fiche",))
    assert stats["pertes_hors_fiche"] == 1
    assert "ne figurent plus parmi les fiches publiées" in caplog.text
    # L'uuid ET l'élu : sans l'uuid, l'anomalie n'est pas instruisible depuis
    # le journal, et sans le compte d'élus distincts on lirait un chiffre faux.
    assert "u-sans-fiche" in caplog.text
    assert "PA-inexistant" in caplog.text
    assert "de 1 élu(s)" in caplog.text


def test_le_nom_de_la_variable_dacquittement_est_epingle():
    """Le nom est une INTERFACE d'exploitation : il ne se renomme pas par mégarde.

    Il vit dans un message d'échec, dans la docstring du module et dans le
    RUNBOOK ; un test qui passerait par la constante seule laisserait un
    renommage casser toutes les commandes déjà écrites sans rien faire tomber.
    """
    assert p15.ENV_PERTES_ACQUITTEES == "FT_P15_PERTES_ACQUITTEES"


def test_libelle_elu_nomme_lelu_et_encaisse_son_absence(conn):
    """Le message d'échec doit être lisible tel quel, sans requête de l'exploitant."""
    _inserer_elu(conn, "PA1", "Nosbé", "Sandrine", "1972-10-29")
    assert p15._libelle_elu(conn, "PA1") == "Nosbé Sandrine"
    assert p15._libelle_elu(conn, "PA-inconnu") == "absent de elus"


def test_pertes_sont_rendues_dans_un_ordre_stable():
    """Deux exécutions doivent produire le MÊME message, mot pour mot.

    Sans tri, l'ordre suivrait celui du dictionnaire lu en base : le message
    d'échec changerait d'un cycle à l'autre pour la même anomalie, et deux
    journaux ne seraient plus comparables.
    """
    precedents = {"u-c": "PA3", "u-a": "PA1", "u-b": "PA2"}
    perdues, _ = p15.pertes_de_rattachement(
        precedents, {"u-a", "u-b", "u-c"}, {}, {"PA1", "PA2", "PA3"})
    assert perdues == [("u-a", "PA1"), ("u-b", "PA2"), ("u-c", "PA3")]


def test_le_message_dechec_nomme_les_elus_touches(tmp_path, monkeypatch):
    """Un message qui ne nommerait que des uuid obligerait à requêter la base."""
    chemin = tmp_path / "p15_message.db"
    monkeypatch.setenv("FT_DB_PATH", str(chemin))
    conn = db.init_db(chemin=chemin)
    _base_de_gardefou(conn, {"u-detachee": "PA1"})
    conn.close()
    with pytest.raises(ValueError) as leve:
        _executer_avec_parse_simule(monkeypatch, chemin,
                                    uuids_en_plus=("u-detachee",))
    assert "PA1 (Nosbé Sandrine)" in str(leve.value)
    assert "u-detachee" in str(leve.value)


def test_le_vivier_des_fiches_est_lindex_souple_pas_la_cle_exacte(
        tmp_path, monkeypatch):
    """Une fiche écartée de la clé exacte pour HOMONYMIE porte quand même une fiche.

    `construire_index_elus` retire les clés partagées par deux élus ; ces
    personnes existent pourtant sur le site. Bâtir `fiches` sur cet index-là
    ferait taire le garde-fou précisément sur les homonymes — la population la
    plus exposée au détachement, puisque c'est l'homonymie qui le provoque.
    """
    chemin = tmp_path / "p15_vivier.db"
    monkeypatch.setenv("FT_DB_PATH", str(chemin))
    conn = db.init_db(chemin=chemin)
    _base_de_gardefou(conn, {"u-detachee": "PA-jumeau-a"})
    # Deux élus qui partagent nom + prénom + date : la clé exacte les retire
    # tous les deux de son index, l'index souple les garde.
    _inserer_elu(conn, "PA-jumeau-a", "DUPONT", "Jean", "1960-03-04")
    _inserer_elu(conn, "PA-jumeau-b", "DUPONT", "Jean", "1960-03-04")
    conn.commit()
    exacte = p15.construire_index_elus(conn)
    souple = p15.construire_index_souple(conn)
    assert "PA-jumeau-a" not in set(exacte.values())          # écarté : homonymie
    assert "PA-jumeau-a" in {f["id"] for c in souple.values() for f in c}
    conn.close()
    # Le garde-fou doit donc voir la perte, et lever.
    with pytest.raises(ValueError, match="perte de rattachement"):
        _executer_avec_parse_simule(monkeypatch, chemin,
                                    uuids_en_plus=("u-detachee",))


# ---------------------------------------------------------------------------
# Rubrique effondrée : le contenu peut s'effondrer sans qu'un uuid bouge
# ---------------------------------------------------------------------------


def test_rubrique_effondree_voit_une_balise_amont_renommee():
    """Perdre une rubrique entière ne déplace aucun uuid et ne franchit aucun seuil.

    Mesuré le 26/08/2026 sur la base servie : `participation_financiere` pèse
    3 726 lignes sur 28 586, soit −13,0 % si elle disparaît — sous le seuil de
    rupture de −20 %. Zéro, lui, est sans ambiguïté.
    """
    avant = {"dirigeant": 13_552, "participation_financiere": 3_726}
    apres = {"dirigeant": 13_600}
    assert p15.rubriques_effondrees(avant, apres) == [
        ("participation_financiere", 3_726)]


def test_rubrique_effondree_ignore_une_rubrique_deja_vide_et_une_baisse():
    """Ni une rubrique jamais renseignée, ni une simple baisse, ne sont une rupture.

    Le contrôle n'a pas de seuil : il ne se déclenche QUE sur zéro, sinon il
    faudrait calibrer une tolérance — et la mesure a montré qu'aucune ne sépare
    un retrait amont légitime d'une régression.
    """
    assert p15.rubriques_effondrees({"consultant": 0}, {}) == []
    assert p15.rubriques_effondrees({"benevole": 1_185}, {"benevole": 3}) == []


def test_lignes_par_rubrique_precedentes_se_tait_sur_une_base_neuve(conn):
    """Base sans table P15 : rien à comparer, et surtout rien à deviner."""
    conn.executescript("DROP TABLE IF EXISTS hatvp_decl_lignes")
    assert p15.lignes_par_rubrique_precedentes(conn) == {}
    p15.ecrire(conn, p15.parcourir(EXTRAIT_REEL, {ELU_UN: "PA1", ELU_DEUX: "PA2"}))
    compte = p15.lignes_par_rubrique_precedentes(conn)
    assert compte and sum(compte.values()) == 11


def test_gardefou_rubrique_effondree_laisse_la_base_intacte(tmp_path, monkeypatch):
    """`executer()` refuse d'écrire, et n'a rien touché."""
    chemin = tmp_path / "p15_rubrique.db"
    monkeypatch.setenv("FT_DB_PATH", str(chemin))
    conn = db.init_db(chemin=chemin)
    _base_de_gardefou(conn, {})
    conn.execute("INSERT INTO hatvp_decl_lignes (declaration_uuid, elu_id,"
                 " rubrique, rubrique_ordre, rang) VALUES ('x', 'PA1',"
                 " 'consultant', 5, 1)")
    conn.commit()
    avant = _compteurs(conn)
    conn.close()
    # La fixture ne porte aucune ligne « consultant » : la rubrique tombe à 0.
    with pytest.raises(ValueError, match="rubrique effondrée"):
        _executer_avec_parse_simule(monkeypatch, chemin)
    conn = db.init_db(chemin=chemin)
    assert _compteurs(conn) == avant
    conn.close()


def test_memoire_vide_apres_incident_est_journalisee(conn, caplog):
    """Table présente mais VIDE : le garde-fou est aveugle, et il le dit.

    `ecrire()` passe par `executescript`, qui valide implicitement : un échec
    entre le DROP et le commit laisse les tables existantes et vides sur
    disque. Mesuré le 26/08/2026 — un uuid rattaché deux fois (la source en
    publie 6 en double) fait lever `UNIQUE constraint failed`, et une connexion
    neuve relit 0 déclaration. Le cycle suivant n'a alors aucune mémoire ; ce
    silence-là ne doit pas se confondre avec celui d'une base neuve.
    """
    import logging
    p15.ecrire(conn, p15.parcourir(EXTRAIT_REEL, {ELU_UN: "PA1", ELU_DEUX: "PA2"}))
    conn.execute("DELETE FROM hatvp_decl_interets")
    with caplog.at_level(logging.WARNING):
        assert p15.rattachements_precedents(conn) == {}
    assert "existe mais est VIDE" in caplog.text
    # Contre-épreuve : une base neuve, elle, ne dit rien.
    caplog.clear()
    conn.executescript("DROP TABLE IF EXISTS hatvp_decl_interets")
    with caplog.at_level(logging.WARNING):
        assert p15.rattachements_precedents(conn) == {}
    assert caplog.text == ""


def _base_de_gardefou(conn, precedentes):
    """Base plausible pour `executer()` : 500 fiches, plus un état antérieur.

    Le plancher `len(index_elus) >= 500` est un littéral non monkeypatchable :
    on peuple donc réellement `elus`, c'est moins fragile qu'un contournement.
    """
    for i in range(520):
        _inserer_elu(conn, f"PA{i}", f"NOM{i}", f"PRENOM{i}", f"19{50 + i % 40}-01-01")
    conn.execute("DELETE FROM elus WHERE id IN ('PA1', 'PA2')")
    _inserer_elu(conn, "PA1", "Nosbé", "Sandrine", "1972-10-29")
    _inserer_elu(conn, "PA2", "AVIRAGNET", "joel", "1956-06-16")
    p15.ecrire(conn, p15.parcourir(EXTRAIT_REEL, {ELU_UN: "PA1", ELU_DEUX: "PA2"}))
    for uuid, elu_id in precedentes.items():
        conn.execute("INSERT INTO hatvp_decl_interets (uuid, elu_id, type_declaration)"
                     " VALUES (?, ?, 'DI')", (uuid, elu_id))
    conn.commit()


def _executer_avec_parse_simule(monkeypatch, chemin, uuids_en_plus=()):
    """`executer()` sans réseau, avec un parse dont les compteurs franchissent
    les trois planchers hérités (5 000 lues, 1 000 rattachées, repli ≤ 15 %)."""
    monkeypatch.setattr(p15, "session_http", lambda *a, **k: None)
    monkeypatch.setattr(p15, "telecharger", lambda *a, **k: EXTRAIT_REEL)
    monkeypatch.setattr(p15, "date_derniere_modification", lambda *a, **k: "2026-08-21")
    vrai_parcourir = p15.parcourir          # capturé AVANT d'être remplacé

    def parse_simule(chemin_xml, index_elus, index_souple=None):
        donnees = vrai_parcourir(EXTRAIT_REEL, {ELU_UN: "PA1", ELU_DEUX: "PA2"})
        donnees["uuids_vus"] = set(donnees["uuids_vus"]) | set(uuids_en_plus)
        donnees["stats"]["declarations_lues"] = 6_608
        donnees["stats"]["rattachees"] = 2_332
        donnees["stats"]["rattachees_par_repli"] = 71
        return donnees

    monkeypatch.setattr(p15, "parcourir", parse_simule)
    return p15.executer(chemin_db=chemin, max_age_heures=None)


def test_gardefou_perte_de_rattachement_laisse_la_base_intacte(tmp_path, monkeypatch):
    """Le contrat entier : `executer()` refuse, et n'a rien touché.

    `ecrire()` DROPpe les quatre tables ; le garde-fou est posé AVANT lui.
    On le prouve en photographiant la table avant l'échec et après.
    """
    chemin = tmp_path / "p15_gardefou.db"
    monkeypatch.setenv("FT_DB_PATH", str(chemin))
    conn = db.init_db(chemin=chemin)
    _base_de_gardefou(conn, {"u-detachee": "PA1"})
    avant = conn.execute(
        "SELECT uuid, elu_id FROM hatvp_decl_interets ORDER BY uuid").fetchall()
    conn.close()

    with pytest.raises(ValueError, match="perte de rattachement"):
        _executer_avec_parse_simule(monkeypatch, chemin, uuids_en_plus=("u-detachee",))

    conn = db.init_db(chemin=chemin)
    apres = conn.execute(
        "SELECT uuid, elu_id FROM hatvp_decl_interets ORDER BY uuid").fetchall()
    conn.close()
    assert [tuple(l) for l in apres] == [tuple(l) for l in avant]
    assert ("u-detachee", "PA1") in [tuple(l) for l in apres]


def test_gardefou_perte_se_tait_quand_la_source_a_retire_la_declaration(
        tmp_path, monkeypatch):
    """Même état antérieur, mais l'uuid n'est plus publié : l'ingestion passe.

    C'est la contre-épreuve du test précédent : sans elle, un garde-fou qui
    lèverait TOUJOURS passerait pour bon.
    """
    chemin = tmp_path / "p15_retrait.db"
    monkeypatch.setenv("FT_DB_PATH", str(chemin))
    conn = db.init_db(chemin=chemin)
    _base_de_gardefou(conn, {"u-retiree": "PA1"})
    conn.close()

    stats = _executer_avec_parse_simule(monkeypatch, chemin)   # uuid non publié
    assert stats["rattachees"] == 2_332
    conn = db.init_db(chemin=chemin)
    # `ecrire()` a bien tourné : l'état antérieur a été remplacé.
    assert conn.execute(
        "SELECT count(*) AS n FROM hatvp_decl_interets WHERE uuid = 'u-retiree'"
    ).fetchone()["n"] == 0
    conn.close()


def test_la_liste_complete_des_pertes_part_au_journal(tmp_path, monkeypatch, caplog):
    """Le message d'exception tronque à huit ; l'acquittement, lui, exige TOUT.

    Sans cette ligne de journal, au-delà de huit pertes les uuid manquants ne
    seraient écrits nulle part — ni en base, puisque le cycle échoue avant
    d'écrire, ni à l'écran. L'issue de secours serait alors inutilisable
    exactement dans le régime qu'elle vise, celui d'une anomalie de masse.
    """
    import logging
    chemin = tmp_path / "p15_liste.db"
    monkeypatch.setenv("FT_DB_PATH", str(chemin))
    conn = db.init_db(chemin=chemin)
    dix = {f"u-perdue-{i:02d}": "PA1" for i in range(10)}
    _base_de_gardefou(conn, dix)
    conn.close()
    with caplog.at_level(logging.ERROR):
        with pytest.raises(ValueError, match="perte de rattachement"):
            _executer_avec_parse_simule(monkeypatch, chemin,
                                        uuids_en_plus=tuple(dix))
    assert "liste complète (10)" in caplog.text
    # Les DIX, pas les huit du message d'exception.
    for uuid in dix:
        assert uuid in caplog.text


def test_le_message_dechec_est_borne_et_annonce_ce_quil_tronque(
        tmp_path, monkeypatch, caplog):
    """Le message nomme au plus huit uuid et huit élus, et le DIT.

    Deux exigences contraires : un message d'exception qui déverserait 800 uuid
    est illisible, et un message qui en tronque sans le dire fait croire que la
    liste est complète. La borne est donc tenue par ce test dans les DEUX sens
    — la première réfutation avait montré qu'on pouvait la supprimer sans faire
    tomber quoi que ce soit.
    """
    import logging
    chemin = tmp_path / "p15_borne.db"
    monkeypatch.setenv("FT_DB_PATH", str(chemin))
    conn = db.init_db(chemin=chemin)
    dix = {f"u-perdue-{i:02d}": f"PA{i}" for i in range(10)}
    _base_de_gardefou(conn, dix)
    conn.close()
    with caplog.at_level(logging.ERROR):
        with pytest.raises(ValueError) as leve:
            _executer_avec_parse_simule(monkeypatch, chemin,
                                        uuids_en_plus=tuple(dix))
    message = str(leve.value)
    assert message.count("u-perdue-") == 8          # huit uuid, pas dix
    assert message.count("PA") == 8                 # huit élus, pas dix
    assert "…" in message                           # et la troncature est dite
    assert "u-perdue-09" not in message             # le neuvième n'y est pas
    assert "PA9" not in message
    assert "u-perdue-09" in caplog.text             # mais il est au journal


def test_rubriques_effondrees_sont_rendues_dans_un_ordre_stable():
    """Même exigence que pour les pertes : deux cycles, le même message.

    Sans tri, l'ordre suivrait celui du dictionnaire lu en base et deux
    journaux ne seraient plus comparables.
    """
    avant = {"observation": 354, "benevole": 1_185, "consultant": 256}
    assert p15.rubriques_effondrees(avant, {}) == [
        ("benevole", 1_185), ("consultant", 256), ("observation", 354)]


def test_libelle_elu_encaisse_un_nom_absent(conn):
    """Une fiche sans nom ne doit pas produire un libellé vide dans le message.

    Le repli existe parce qu'un message « PA123 () » n'apprend rien à
    l'exploitant. `elus.nom` est NOT NULL, mais rien n'interdit la chaîne vide :
    c'est l'état que ce test exerce, et le seul atteignable.
    """
    conn.execute("INSERT INTO elus (id, nom, prenom, date_naissance, mandats)"
                 " VALUES ('PA-vide', '', '', '1970-01-01', '[]')")
    assert p15._libelle_elu(conn, "PA-vide") == "sans nom"


def test_lavertissement_hors_fiche_compte_les_ELUS_pas_les_declarations(
        tmp_path, monkeypatch, caplog):
    """Deux déclarations d'un même élu font UN élu, pas deux.

    Un compte d'élus faussé par un compte de déclarations conduirait
    l'exploitant à surestimer l'ampleur d'un incident amont — le chiffre est
    celui sur lequel il décidera d'intervenir ou non.
    """
    import logging
    chemin = tmp_path / "p15_compte.db"
    monkeypatch.setenv("FT_DB_PATH", str(chemin))
    conn = db.init_db(chemin=chemin)
    _base_de_gardefou(conn, {"u-a": "PA-parti", "u-b": "PA-parti"})
    conn.close()
    with caplog.at_level(logging.WARNING):
        stats = _executer_avec_parse_simule(monkeypatch, chemin,
                                            uuids_en_plus=("u-a", "u-b"))
    assert stats["pertes_hors_fiche"] == 2
    assert "2 déclaration(s)" in caplog.text
    assert "de 1 élu(s)" in caplog.text


def test_memoire_des_lignes_vide_apres_incident_est_journalisee(conn, caplog):
    """Les DEUX contrôles inter-cycles perdent la mémoire au même incident.

    `rattachements_precedents` le disait déjà ; son jumeau se taisait, et le
    silence d'un contrôle ne doit jamais se confondre avec un contrôle qui a
    regardé.
    """
    import logging
    p15.ecrire(conn, p15.parcourir(EXTRAIT_REEL, {ELU_UN: "PA1", ELU_DEUX: "PA2"}))
    conn.execute("DELETE FROM hatvp_decl_lignes")
    with caplog.at_level(logging.WARNING):
        assert p15.lignes_par_rubrique_precedentes(conn) == {}
    assert "hatvp_decl_lignes existe mais est VIDE" in caplog.text
    caplog.clear()
    conn.executescript("DROP TABLE IF EXISTS hatvp_decl_lignes")
    with caplog.at_level(logging.WARNING):
        assert p15.lignes_par_rubrique_precedentes(conn) == {}
    assert caplog.text == ""


def test_le_vivier_des_fiches_est_restreint_aux_mandats_a_fiche(conn):
    """Le vivier n'est pas « tous les élus » : c'est ceux que le site publie.

    Les 36 018 élus de `elus` n'ont pas de page ; seuls les quatre types de
    `TYPES_FICHE` en ont une. Sans ce filtre, un maire dont une déclaration se
    détacherait ferait échouer le cycle pour une page qui n'existe pas.
    """
    _inserer_elu(conn, "PA-depute", "DURAND", "Marie", "1970-01-01")
    _inserer_elu(conn, "RNE-maire", "MARTIN", "Paul", "1965-02-03",
                 type_mandat="maire")
    conn.commit()
    vivier = p15.elus_avec_fiche(conn)
    assert "PA-depute" in vivier
    assert "RNE-maire" not in vivier


def test_le_vivier_des_fiches_ignore_la_date_de_naissance(conn):
    """Porter une fiche et être appariable sont DEUX choses différentes.

    C'est la faute que la seconde réfutation a mise au jour : le vivier tiré de
    l'index souple écarte les élus dont `date_naissance` n'est pas une date ISO
    de dix caractères — or `ingest_parlement` réécrit cette colonne à chaque
    cycle et peut y mettre `None`. Ces élus-là gardent leur fiche : leurs
    déclarations qui se détachent sont une PERTE, pas une fin de mandat.
    """
    _inserer_elu(conn, "PA-sans-date", "DUPONT", "Jean", None)
    _inserer_elu(conn, "PA-datee", "DURAND", "Marie", "1970-01-01")
    conn.commit()
    vivier = p15.elus_avec_fiche(conn)
    assert {"PA-sans-date", "PA-datee"} <= vivier
    # L'index souple, lui, écarte le premier — c'était le piège.
    souple = {f["id"] for c in p15.construire_index_souple(conn).values() for f in c}
    assert "PA-sans-date" not in souple
    assert "PA-datee" in souple


def test_gardefou_une_date_de_naissance_perdue_est_une_PERTE_pas_une_fin_de_mandat(
        tmp_path, monkeypatch):
    """Le scénario mesuré : un cycle amont abîmé ne doit pas passer en SUCCÈS.

    Mesuré sur copie de la base servie le 26/08/2026 : 200 dates de naissance
    mises à NULL, fiches conservées, faisaient disparaître 798 déclarations et
    11 812 lignes (−41,3 %) avec un cycle en SUCCÈS et pour seul mot un
    avertissement disant « fin de mandat attendue ». Aucun autre garde-fou ne
    mordait : 1 534 rattachées (plancher 1 000), aucune rubrique à zéro.
    """
    chemin = tmp_path / "p15_date_nulle.db"
    monkeypatch.setenv("FT_DB_PATH", str(chemin))
    conn = db.init_db(chemin=chemin)
    _base_de_gardefou(conn, {"u-detachee": "PA1"})
    conn.execute("UPDATE elus SET date_naissance = NULL WHERE id = 'PA1'")
    conn.commit()
    conn.close()
    with pytest.raises(ValueError, match="perte de rattachement"):
        _executer_avec_parse_simule(monkeypatch, chemin,
                                    uuids_en_plus=("u-detachee",))


def test_gardefou_perte_acquittee_une_par_une_laisse_passer(tmp_path, monkeypatch):
    """L'acquittement nomme les uuid ; il ne desserre aucun seuil.

    Sans cette issue, une perte légitime mais irréparable dans la journée
    gèlerait l'ingestion des 44 sources — elle est tout-ou-rien.
    """
    chemin = tmp_path / "p15_acquit.db"
    monkeypatch.setenv("FT_DB_PATH", str(chemin))
    conn = db.init_db(chemin=chemin)
    _base_de_gardefou(conn, {"u-detachee": "PA1", "u-autre": "PA2"})
    conn.close()

    monkeypatch.setenv(p15.ENV_PERTES_ACQUITTEES, "u-detachee")
    with pytest.raises(ValueError, match="perte de rattachement"):
        _executer_avec_parse_simule(monkeypatch, chemin,
                                    uuids_en_plus=("u-detachee", "u-autre"))
    monkeypatch.setenv(p15.ENV_PERTES_ACQUITTEES, "u-detachee, u-autre")
    stats = _executer_avec_parse_simule(monkeypatch, chemin,
                                        uuids_en_plus=("u-detachee", "u-autre"))
    assert stats["pertes_acquittees"] == 2


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

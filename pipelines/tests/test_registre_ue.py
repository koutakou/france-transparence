"""Tests du pipeline P16 — registre de transparence de l'Union européenne (S40).

La fixture `fixtures/registre_ue/organisations_extrait.xml` est un extrait
RÉEL de l'export du 19/08/2026 (42 Ko) : sept `<interestRepresentative>`
recopiés octet pour octet depuis le fichier de 115 Mo, dans son enveloppe
d'origine — déclaration `version='1.1'` comprise. La seule valeur ajustée est
`<numberOfIR>`, ramenée de 17 711 à 7 : c'est le compte des inscrits présents
dans le fichier, il reste donc vrai de CE fichier, et c'est ce que le
garde-fou de `executer()` vérifie.

Les sept enregistrements couvrent, sans qu'aucune ligne ne soit fabriquée :
- Saper Vedere (9761005100555-43, Belgique) : contient une référence de
  caractère `&#xb;` — LÉGALE en XML 1.1, INTERDITE en XML 1.0. C'est le
  document qui échoue si la tolérance du parseur régresse ;
- Ogival Public Affairs (488647147874-39, France) : « Self-employed
  individuals », donc une personne physique — comptée dans les agrégats,
  exclue de la table nominative ;
- CESIN (787105794254-32, France) : fourchette de coûts ouverte vers le bas
  (« < 10 000 € ») ;
- INFINITE ORBITS (8630271103981-12, France) : dernière fourchette, non
  bornée (« ≥ 10 000 000 € ») ;
- Expertise France (877833843416-03, France) : aucun coût déclaré ;
- BVES (028362550210-63, Allemagne) : fourchette bornée des deux côtés ;
- UIH (352325223827-36, Bulgarie) : porte un `nameInLatinAlphabet`.

Le test réseau (marque `reseau`) joue le pipeline complet contre
transparency-register.europa.eu : `pytest -m reseau` pour l'exécuter,
`-m "not reseau"` pour l'exclure.
"""

from pathlib import Path

import pytest

from pipelines import db
from pipelines.ingest_registre_ue import (
    CATEGORIE_PERSONNES_PHYSIQUES,
    COLONNES_ORGANISATION,
    ID_SOURCE,
    construire,
    date_iso,
    ecrire_db,
    est_personne_physique,
    executer,
    flux_xml_tolerant,
    libelle_fourchette,
    lire_export,
    nombre,
    normaliser_declaration,
    url_fiche_ue,
)

FIXTURE = (
    Path(__file__).parent / "fixtures" / "registre_ue" / "organisations_extrait.xml"
)

# Espaces typographiques employées par `libelle_fourchette` : fine insécable
# pour les milliers, insécable avant le symbole monétaire.
FINE = " "
INSEC = " "


# ---------------------------------------------------------------------------
# Tolérance XML 1.1 — la raison d'être du parseur maison
# ---------------------------------------------------------------------------


def test_normaliser_declaration():
    """`version='1.1'` → `version='1.0'`, les deux formes de guillemets."""
    assert normaliser_declaration(b"<?xml version='1.1' encoding='UTF-8'?>") == (
        b"<?xml version='1.0' encoding='UTF-8'?>"
    )
    assert normaliser_declaration(b'<?xml version = "1.1"?>') == (
        b'<?xml version = "1.0"?>'
    )
    # déjà en 1.0 : rendu inchangé, la fonction ne « corrige » rien d'autre
    inchange = b"<?xml version='1.0' encoding='UTF-8'?>"
    assert normaliser_declaration(inchange) == inchange
    # une version 1.1 citée dans du texte n'est pas une déclaration
    assert normaliser_declaration(b"<p>norme version='1.1'</p>") == (
        b"<p>norme version='1.1'</p>"
    )


def _filtre(
    octets: bytes, taille_bloc: int, tmp_path: Path, taille_entete: int = 256
) -> bytes:
    """Passe `octets` dans le flux tolérant et recolle le résultat."""
    chemin = tmp_path / "extrait.xml"
    chemin.write_bytes(octets)
    return b"".join(
        flux_xml_tolerant(
            chemin, taille_bloc=taille_bloc, taille_entete=taille_entete
        )
    )


def test_refs_de_controle_xml11_retirees_et_les_autres_gardees(tmp_path):
    """Seules les références interdites en XML 1.0 disparaissent.

    `&#x9;` (tabulation), `&#xa;` (saut de ligne) et `&#xd;` (retour chariot)
    sont légales dans les deux versions et DOIVENT survivre : la fixture
    réelle en contient 37, les retirer altérerait le texte source.
    """
    entree = (
        b"<?xml version='1.1'?><r>a&#x2;b&#xb;c&#x1d;d&#11;e&#31;f"
        b"|&#x9;&#xa;&#xd;&#9;&#10;&#13;&#x20;&#x96;</r>"
    )
    sortie = _filtre(entree, 1 << 20, tmp_path)
    assert b"&#x2;" not in sortie and b"&#xb;" not in sortie
    assert b"&#x1d;" not in sortie and b"&#11;" not in sortie
    assert b"&#31;" not in sortie
    assert sortie.endswith(b"|&#x9;&#xa;&#xd;&#9;&#10;&#13;&#x20;&#x96;</r>")
    assert b"<?xml version='1.0'?>" in sortie
    # le texte utile est conservé, seule la référence saute
    assert b"<r>abcdef|" in sortie


def test_ref_a_cheval_sur_deux_blocs(tmp_path):
    """Une référence coupée par une frontière de bloc est quand même filtrée.

    C'est le seul bug que la lecture par blocs peut introduire, et il est
    silencieux : le filtre laisserait passer la moitié d'une référence, et
    le parseur échouerait 100 Mo plus loin. Un bloc d'UN octet met le
    mécanisme de queue à l'épreuve maximale. Le décalage varie sur toute une
    fenêtre pour que la référence tombe à cheval quelle que soit la taille
    de bloc, et une référence LÉGALE voisine (`&#xd;`) vérifie au passage
    que le recollage ne mange rien d'autre.
    """
    entete = b"<?xml version='1.1'?>"
    for taille in (1, 2, 5, 7, 13, 16, 64):
        for decalage in range(40):
            corps = b"<r>" + b"a" * decalage + b"&#x2;b&#xd;c</r>"
            sortie = _filtre(
                entete + corps, taille, tmp_path, taille_entete=len(entete)
            )
            attendu = b"<?xml version='1.0'?><r>" + b"a" * decalage + b"b&#xd;c</r>"
            assert sortie == attendu, (taille, decalage)


def test_la_fixture_reelle_est_illisible_sans_la_tolerance():
    """Preuve par l'échec : la stdlib refuse le fichier tel qu'il est publié.

    Sans ce test, rien ne dirait que le parseur maison sert à quelque chose.
    """
    import xml.etree.ElementTree as ET

    with pytest.raises(ET.ParseError):
        ET.parse(FIXTURE)


def test_lire_export_rend_les_balises_attendues():
    balises = [nom for nom, _ in lire_export(FIXTURE)]
    assert balises[0] == "exportDate"
    assert balises[1] == "numberOfIR"
    assert balises.count("interestRepresentative") == 7


# ---------------------------------------------------------------------------
# Helpers purs
# ---------------------------------------------------------------------------


def test_date_iso():
    assert date_iso("2026-08-19T20:00:00.069+00:00") == "2026-08-19"
    assert date_iso("2025-01-01") == "2025-01-01"
    assert date_iso("") is None
    assert date_iso(None) is None
    assert date_iso("19/08/2026") is None  # jamais de date devinée


def test_nombre():
    assert nombre("10000") == 10000.0
    assert nombre("0.75") == 0.75
    assert nombre("") is None
    assert nombre(None) is None
    assert nombre("n/a") is None


def test_libelle_fourchette():
    """Les trois formes réellement publiées, et rien de plus."""
    assert libelle_fourchette(None, 10000.0) == f"< 10{FINE}000{INSEC}€"
    assert libelle_fourchette(25000.0, 49999.0) == (
        f"25{FINE}000{INSEC}€ – 49{FINE}999{INSEC}€"
    )
    assert libelle_fourchette(10000000.0, None) == f"≥ 10{FINE}000{FINE}000{INSEC}€"
    # rien de déclaré : surtout pas « 0 € »
    assert libelle_fourchette(None, None) is None


def test_url_fiche_ue():
    assert url_fiche_ue("880143435725-46") == (
        "https://transparency-register.europa.eu/search-register-or-update/"
        "organisation-detail_en?organisationNumber=880143435725-46"
    )
    assert url_fiche_ue("") is None
    assert url_fiche_ue(None) is None


def test_est_personne_physique():
    assert est_personne_physique(CATEGORIE_PERSONNES_PHYSIQUES)
    assert not est_personne_physique("Companies & groups")
    assert not est_personne_physique(None)


# ---------------------------------------------------------------------------
# Lecture de la fixture réelle
# ---------------------------------------------------------------------------


@pytest.fixture()
def donnees():
    return construire(FIXTURE)


@pytest.fixture()
def base(tmp_path, donnees):
    """Base jetable remplie depuis la fixture réelle."""
    conn = db.init_db(chemin=tmp_path / "registre_ue.db")
    ecrire_db(conn, donnees)
    yield conn
    conn.close()


def test_fraicheur_lue_dans_export_date(donnees):
    """La fraîcheur vient de `<exportDate>`, jamais du catalogue DCAT.

    La métadonnée DCAT de data.europa.eu était périmée de deux ans au
    20/08/2026 ; c'est la balise du fichier qui fait foi.
    """
    assert donnees["date_donnees"] == "2026-08-19"


def test_comptes_de_la_fixture(donnees):
    stats = donnees["stats"]
    assert stats["organisations_total"] == 7
    assert stats["nombre_annonce"] == 7
    assert stats["sans_identifiant"] == 0
    assert stats["france_total"] == 4


def test_personnes_physiques_exclues_du_nominatif(donnees):
    """Les « Self-employed individuals » comptent, mais ne sont pas nommés."""
    stats = donnees["stats"]
    assert stats["personnes_physiques_exclues"] == 1
    assert stats["organisations_ecrites"] == 6  # 7 − 1
    assert stats["france_personnes_physiques"] == 1
    assert stats["france_nominatives"] == 3  # 4 inscrits FR − 1 personne physique

    noms = {ligne[COLONNES_ORGANISATION.index("nom")] for ligne in donnees["organisations"]}
    assert "Ogival Public Affairs" not in noms

    # ... alors que l'agrégat, lui, la compte : l'écart est publié, pas caché.
    categories = dict((c, n) for c, n, _ in donnees["agg_categories"])
    assert categories[CATEGORIE_PERSONNES_PHYSIQUES] == 1
    pays = {p: (n, npp) for p, n, npp in donnees["agg_pays"]}
    assert pays["FRANCE"] == (4, 1)


def test_champs_d_une_organisation(donnees):
    par_id = {
        ligne[0]: dict(zip(COLONNES_ORGANISATION, ligne))
        for ligne in donnees["organisations"]
    }

    cesin = par_id["787105794254-32"]
    assert cesin["nom"] == "Club des Experts de la Sécurité de l'Information et du Numérique"
    assert cesin["acronyme"] == "CESIN"
    assert cesin["siege_pays"] == "FRANCE"
    assert cesin["siege_ville"] == "PARIS"
    assert cesin["date_inscription"] == "2024-10-17"
    assert cesin["cout_libelle"] == f"< 10{FINE}000{INSEC}€"
    assert (cesin["cout_min"], cesin["cout_max"]) == (None, 10000.0)
    assert (cesin["exercice_debut"], cesin["exercice_fin"]) == ("2024-01-01", "2024-12-01")

    orbits = par_id["8630271103981-12"]
    assert orbits["cout_libelle"] == f"≥ 10{FINE}000{FINE}000{INSEC}€"
    assert (orbits["cout_min"], orbits["cout_max"]) == (10000000.0, None)

    # aucun coût déclaré → aucun montant inventé
    expertise = par_id["877833843416-03"]
    assert expertise["cout_libelle"] is None
    assert expertise["cout_min"] is None and expertise["cout_max"] is None

    # le seul enregistrement portant un nom translittéré de la fixture
    uih = par_id["352325223827-36"]
    assert uih["nom_latin"] == "Union of International Haulers"

    # l'organisation qui contient la référence XML 1.1 est lue intégralement
    saper = par_id["9761005100555-43"]
    assert saper["nom"] == "Saper Vedere"
    assert saper["siege_pays"] == "BELGIUM"


def test_agregats(donnees):
    couts = {libelle: (bmin, bmax, n, nf) for libelle, bmin, bmax, n, nf in donnees["agg_couts"]}
    assert couts[f"< 10{FINE}000{INSEC}€"] == (None, 10000.0, 2, 1)
    assert couts[f"≥ 10{FINE}000{FINE}000{INSEC}€"] == (10000000.0, None, 1, 1)
    # tri par borne basse, fourchette d'entrée (sans borne basse) en tête
    assert donnees["agg_couts"][0][1] is None

    # les fourchettes ne sont JAMAIS sommées : un total de fourchettes ne
    # veut rien dire, seuls les effectifs par fourchette sont publiés.
    assert sum(n for *_, n, _ in donnees["agg_couts"]) == 4

    interets = dict((d, n) for d, n, _ in donnees["agg_interets"])
    assert interets["Business and industry"] == 6

    pays = [p for p, *_ in donnees["agg_pays"]]
    assert pays[0] == "FRANCE"  # tri par effectif décroissant


# ---------------------------------------------------------------------------
# Écriture en base et cloisonnement
# ---------------------------------------------------------------------------


def test_ecriture_des_tables(base):
    conn = base
    compte = lambda t: conn.execute(f"SELECT count(*) n FROM {t}").fetchone()["n"]  # noqa: E731
    assert compte("ue_registre_organisations") == 6
    assert compte("ue_registre_agg_categories") == 6
    assert compte("ue_registre_agg_pays") == 4
    assert compte("ue_registre_agg_couts") == 3
    assert compte("ue_registre_agg_interets") == 40


def test_ecriture_idempotente(base, donnees):
    """Rejouer l'écriture ne duplique rien (remplacement complet)."""
    conn = base
    ecrire_db(conn, donnees)
    ecrire_db(conn, donnees)
    assert conn.execute(
        "SELECT count(*) n FROM ue_registre_organisations"
    ).fetchone()["n"] == 6


def test_meta_source_s40(base):
    ligne = base.execute(
        "SELECT * FROM meta_sources WHERE source_id = ?", (ID_SOURCE,)
    ).fetchone()
    assert ligne is not None
    assert ligne["frequence"] == "quotidienne"
    assert ligne["date_donnees"] == "2026-08-19"
    assert ligne["lignes"] == 7  # total du registre, personnes physiques comprises
    assert "2011/833" in ligne["licence"]
    # la note porte le cloisonnement et l'absence de clé de rapprochement
    assert "CLOISONNÉ" in ligne["notes"]
    assert "SIREN" in ligne["notes"]


def test_cloisonnement_aucune_cle_de_rapprochement(base):
    """Le schéma ne peut PAS être joint au répertoire HATVP, par construction.

    L'export UE ne publie ni SIREN ni numéro de TVA : ce test fige le
    constat en interdisant qu'une colonne d'identifiant national réapparaisse
    un jour dans ces tables — ce serait forcément une valeur devinée, donc
    un rapprochement fabriqué entre deux registres qui n'en ont pas.
    """
    colonnes = {
        ligne["name"].lower()
        for ligne in base.execute("PRAGMA table_info(ue_registre_organisations)")
    }
    for interdite in ("siren", "siret", "tva", "identifiant_national", "entite_id"):
        assert interdite not in colonnes


def test_cloisonnement_aucune_table_lobby_touchee(base):
    """Le pipeline UE n'écrit que des tables `ue_registre_*`.

    Les tables `lobby_*` (source S4, HATVP) appartiennent à un autre
    registre et à un autre cadre juridique ; aucune n'est créée ni modifiée
    ici, pas même la table partagée `alertes` — être inscrit à un registre
    de transparence n'est le signalement de rien.
    """
    tables = {
        ligne["name"]
        for ligne in base.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    assert not [t for t in tables if t.startswith("lobby_")]
    assert "alertes" not in tables
    assert {t for t in tables if t.startswith("ue_registre_")} == {
        "ue_registre_organisations",
        "ue_registre_agg_categories",
        "ue_registre_agg_pays",
        "ue_registre_agg_interets",
        "ue_registre_agg_couts",
    }


# ---------------------------------------------------------------------------
# Intégration réseau (exclue par défaut)
# ---------------------------------------------------------------------------


@pytest.mark.reseau
def test_pipeline_complet_reseau(tmp_path):
    """Joue le pipeline contre l'export réel (~115 Mo téléchargés)."""
    stats = executer(chemin_db=tmp_path / "reel.db", max_age_heures=24.0)
    assert stats["organisations_total"] > 10_000
    assert stats["organisations_total"] == stats["nombre_annonce"]
    assert stats["france_total"] > 500
    assert stats["organisations_ecrites"] == (
        stats["organisations_total"] - stats["personnes_physiques_exclues"]
        - stats["sans_identifiant"]
    )
    assert date_iso(stats["date_donnees"]) == stats["date_donnees"]

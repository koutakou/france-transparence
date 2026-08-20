"""Tests du pipeline P16 (avis et conseils de la CADA, source S38).

Ce pipeline a deux façons de mentir, et les tests ci-dessous existent pour
les rendre impossibles :

1. **Découper le champ « Sens et motivation » de travers.** Le séparateur du
   champ (la virgule) appartient aussi au vocabulaire des motivations
   (« Irrecevable/Documentation, établissement de document »). Une découpe
   naïve produirait des sens inventés et des agrégats faux sans lever la
   moindre erreur. Les tests fixent la règle de recollage ET l'échec franc
   sur un vocabulaire inconnu.

2. **Faire passer la date de modification du dataset pour une fraîcheur.**
   Le jeu amont est « modifié » régulièrement alors que sa dernière séance a
   deux ans. `date_donnees` doit porter la séance, jamais la modification —
   c'est ce qui fait sonner l'alerte de fraîcheur au lieu de la masquer.

S'y ajoute la garantie de discrétion : le texte intégral des décisions ne
doit jamais atteindre la base, sous aucune colonne.

Le tout tourne hors ligne sur `fixtures/cada_extrait.csv` : 23 lignes
RÉELLES du CSV consolidé publié, choisies pour couvrir tous les pièges
(graphies concurrentes d'un même ministère, motivation à virgule, slash
espacé, trois sens sur une décision, sens vide, trois types de saisine,
première et dernière séance du corpus, une administration par catégorie de
la typologie, plus un ordre professionnel qui ne doit PAS être pris pour un
département). Seule la colonne « Avis » y est tronquée : le pipeline ne la
lit jamais, et une fixture verbatim pèserait plusieurs mégaoctets.
"""

from pathlib import Path

import pytest

from pipelines import db
from pipelines.ingest_cada import (
    CATEGORIES,
    SENS,
    SOURCE_ID,
    TYPES,
    categorie_administration,
    cle_administration,
    decouper_motivations,
    executer,
    resoudre_ressource,
)

FIXTURE = Path(__file__).parent / "fixtures" / "cada_extrait.csv"

# Valeurs de la fixture, recomptées à la main sur ses 23 lignes.
DECISIONS = 23
CONSEILS = 3
SANCTIONS = 1
AVIS = DECISIONS - CONSEILS - SANCTIONS
# 23 lignes mais 21 administrations : « Ministère de la Justice » et
# « Ministère de la justice » sont la même, « ministre de la défense »
# apparaît deux fois.
ADMINISTRATIONS = 21
DERNIERE_SEANCE = "2024-04-18"


@pytest.fixture()
def conn(tmp_path):
    """Base jetable, fixture CADA ingérée, connexion rendue au test."""
    chemin = tmp_path / "test_cada.db"
    executer(chemin_db=chemin, chemin_csv=FIXTURE)
    c = db.connexion(chemin)
    yield c
    c.close()


# ---------------------------------------------------------------------------
# Découpe de « Sens et motivation » — le piège n° 1
# ---------------------------------------------------------------------------


def test_recolle_une_motivation_qui_contient_une_virgule():
    """Le séparateur du champ appartient aussi au vocabulaire.

    Cas réel du corpus : « Documentation, établissement de document » est UNE
    motivation. Découpée naïvement sur la virgule, elle fabriquerait un sens
    « établissement de document » qui n'existe pas (262 dossiers concernés).
    """
    assert decouper_motivations(
        "Sans objet/Communiqué, Irrecevable/Documentation, établissement de document"
    ) == ["Sans objet/Communiqué", "Irrecevable/Documentation, établissement de document"]


def test_normalise_les_espaces_autour_du_premier_slash():
    """« Favorable / Sauf vie privée » et « Favorable/Sauf vie privée » sont
    la même motivation, écrite différemment selon le millésime du versement.

    Sans ce repli, le vocabulaire compterait 165 motivations au lieu de 89 et
    la même règle de droit apparaîtrait deux fois dans la carte des verrous.
    """
    assert decouper_motivations("Favorable / Sauf vie privée") == [
        "Favorable/Sauf vie privée"
    ]
    assert decouper_motivations("Incompétence / Loi spéciale") == [
        "Incompétence/Loi spéciale"
    ]


def test_decoupe_plusieurs_sens_sur_une_meme_decision():
    assert decouper_motivations(
        "Irrecevable/Imprécise, Défavorable/Défense, Incompétence/Renseignement"
    ) == [
        "Irrecevable/Imprécise",
        "Défavorable/Défense",
        "Incompétence/Renseignement",
    ]


def test_un_sens_nu_est_une_motivation_valide():
    """La CADA publie des sens sans motivation (« Défavorable » seul)."""
    assert decouper_motivations("Défavorable") == ["Défavorable"]


def test_champ_vide_ne_produit_rien():
    assert decouper_motivations("") == []
    assert decouper_motivations(None) == []


def test_vocabulaire_inconnu_fait_echouer_au_lieu_de_deviner():
    """Un sens hors vocabulaire = changement amont, pas une ligne à ignorer.

    Sans cette levée, une évolution du référentiel CADA produirait
    silencieusement des agrégats amputés.
    """
    with pytest.raises(ValueError):
        decouper_motivations("Partiellement favorable/Vie privée")


# ---------------------------------------------------------------------------
# Administrations : repli des graphies, typologie
# ---------------------------------------------------------------------------


def test_cle_replie_casse_accents_et_ponctuation():
    assert cle_administration("Ministère de la Justice") == cle_administration(
        "Ministère de la justice"
    )
    assert cle_administration("Ministère des Armées") == cle_administration(
        "Ministère des armées"
    )
    assert cle_administration("  Mairie   de  Paris ") == "mairie de paris"


def test_la_cle_ne_rapproche_jamais_deux_libelles_differents():
    """Faute de référentiel, deux dénominations restent deux entrées.

    « Ministère de la défense » et « Ministère des Armées » désignent le même
    ministère à deux époques : les fusionner serait une reconstitution, pas
    une normalisation.
    """
    assert cle_administration("Ministère de la défense") != cle_administration(
        "Ministère des Armées"
    )
    assert cle_administration("Mairie de Lyon") != cle_administration("Ville de Lyon")


@pytest.mark.parametrize(
    ("libelle", "attendu"),
    [
        ("Ministère de la Justice", "ministere"),
        ("ministre de la défense", "ministere"),
        ("Premier ministre", "ministere"),
        ("Préfecture des Landes", "prefecture"),
        ("préfet de la Nièvre", "prefecture"),
        # La préfecture de police relève de l'ordre public, pas du corps
        # préfectoral territorial : règle placée AVANT celle des préfectures.
        ("Préfecture de police de Paris", "justice_police"),
        ("Tribunal judiciaire de Paris", "justice_police"),
        ("Mairie de Paris", "commune"),
        ("maire de Dunkerque", "commune"),
        ("Communauté d'agglomération de Quimperlé", "commune"),
        ("Conseil départemental du Nord (CD 59)", "departement_region"),
        ("Conseil régional d'Ile-de-France", "departement_region"),
        ("Centre hospitalier universitaire de Bordeaux", "sante"),
        ("Assistance Publique-Hôpitaux de Paris (AP-HP)", "sante"),
        ("Rectorat de l'académie de Lille (AC 59)", "enseignement"),
        ("Caisse primaire d'assurance maladie de Paris (CPAM 75)", "securite_sociale"),
        ("Direction générale des finances publiques (DGFIP)", "finances"),
        ("Commission nationale de l'informatique et des libertés (CNIL)",
         "autorite_independante"),
        ("La Poste", "autre"),
        ("X, député", "autre"),
    ],
)
def test_typologie_des_administrations(libelle, attendu):
    assert categorie_administration(cle_administration(libelle)) == attendu


def test_un_ordre_professionnel_n_est_pas_un_departement():
    """« Conseil départemental de l'ordre des médecins » est un ordre.

    Le préfixe est trompeur : sans exclusion explicite, 48 libellés (80
    dossiers du corpus publié) seraient comptés comme des collectivités
    départementales dans la carte des verrous.
    """
    assert (
        categorie_administration(
            cle_administration("Conseil départemental de l'ordre des médecins de la Charente")
        )
        == "autre"
    )


# ---------------------------------------------------------------------------
# Ingestion : volumes, réconciliation, contraintes
# ---------------------------------------------------------------------------


def test_volumes_de_la_fixture(conn):
    total = conn.execute("SELECT SUM(nb_dossiers) AS n FROM cada_saisines").fetchone()["n"]
    assert total == DECISIONS
    nb_admin = conn.execute(
        "SELECT COUNT(*) AS n FROM cada_administrations"
    ).fetchone()["n"]
    assert nb_admin == ADMINISTRATIONS


def test_les_graphies_concurrentes_sont_repliees_sur_une_entree(conn):
    """Les deux graphies du ministère de la Justice font UNE administration
    de deux dossiers, et le libellé retenu est la graphie majoritaire."""
    lignes = conn.execute(
        "SELECT libelle, nb_dossiers FROM cada_administrations "
        "WHERE lower(libelle) = 'ministère de la justice'"
    ).fetchall()
    assert len(lignes) == 1
    assert lignes[0]["nb_dossiers"] == 2


def test_repartition_par_type_de_saisine(conn):
    par_type = {
        r["type_saisine"]: r["n"]
        for r in conn.execute(
            "SELECT type_saisine, SUM(nb_dossiers) AS n FROM cada_saisines "
            "GROUP BY type_saisine"
        )
    }
    assert par_type == {"Avis": AVIS, "Conseil": CONSEILS, "Sanction": SANCTIONS}


def test_les_saisines_sont_le_seul_denominateur_legitime(conn):
    """La somme de `cada_sens` dépasse le nombre de dossiers, par construction.

    Une décision porte souvent plusieurs sens ; additionner `cada_sens` pour
    obtenir un total de dossiers donnerait un chiffre gonflé. Ce test fige
    l'écart pour que personne ne prenne l'une des deux tables pour l'autre.
    """
    dossiers = conn.execute("SELECT SUM(nb_dossiers) AS n FROM cada_saisines").fetchone()["n"]
    mentions = conn.execute("SELECT SUM(nb_dossiers) AS n FROM cada_sens").fetchone()["n"]
    assert mentions > dossiers


def test_chaque_agregat_de_sens_a_son_administration(conn):
    orphelins = conn.execute(
        "SELECT COUNT(*) AS n FROM cada_sens s "
        "LEFT JOIN cada_administrations a ON a.id = s.administration_id "
        "WHERE a.id IS NULL"
    ).fetchone()["n"]
    assert orphelins == 0


def test_vocabulaires_fermes_en_base(conn):
    sens = {r["sens"] for r in conn.execute("SELECT DISTINCT sens FROM cada_sens")}
    assert sens <= set(SENS)
    types = {
        r["type_saisine"] for r in conn.execute("SELECT DISTINCT type_saisine FROM cada_saisines")
    }
    assert types <= set(TYPES)
    cats = {
        r["categorie"]
        for r in conn.execute("SELECT DISTINCT categorie FROM cada_administrations")
    }
    assert cats <= set(CATEGORIES)


def test_un_sens_hors_vocabulaire_est_refuse_par_le_schema(conn):
    import sqlite3

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO cada_sens "
            "(administration_id, annee, type_saisine, sens, nb_dossiers) "
            "VALUES (1, 2024, 'Avis', 'Partiellement favorable', 1)"
        )


def test_la_decision_a_trois_sens_est_comptee_une_fois_par_sens(conn):
    """« ministre de la défense », 1984 : une décision porte Irrecevable,
    Défavorable et Incompétence ; une seconde porte Défavorable seul."""
    lignes = {
        r["sens"]: r["nb_dossiers"]
        for r in conn.execute(
            "SELECT s.sens, s.nb_dossiers FROM cada_sens s "
            "JOIN cada_administrations a ON a.id = s.administration_id "
            "WHERE a.libelle = 'ministre de la défense' AND s.annee = 1984"
        )
    }
    assert lignes == {"Irrecevable": 1, "Défavorable": 2, "Incompétence": 1}


# ---------------------------------------------------------------------------
# Discrétion : le texte intégral ne doit jamais entrer en base
# ---------------------------------------------------------------------------


def test_aucun_texte_de_decision_en_base(conn):
    """Aucune colonne des tables cada_* ne transporte le texte des avis.

    C'est la garantie qui justifie l'ingestion : le corpus nomme des
    responsables publics dans ses motivations, la base ne doit en garder
    aucune phrase.
    """
    tables = [
        r["name"]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'cada%'"
        )
    ]
    assert tables, "aucune table cada_* créée"
    empreinte = "commission d'accès aux documents administratifs a examiné"
    for table in tables:
        colonnes = [
            r["name"]
            for r in conn.execute(f"PRAGMA table_info({table})")
            if r["type"] == "TEXT"
        ]
        for colonne in colonnes:
            trouve = conn.execute(
                f"SELECT COUNT(*) AS n FROM {table} "
                f"WHERE lower({colonne}) LIKE ?", (f"%{empreinte}%",)
            ).fetchone()["n"]
            assert trouve == 0, f"{table}.{colonne} contient du texte de décision"
            # Un libellé d'administration dépasse rarement 200 caractères ;
            # au-delà, ce n'est plus un nom, c'est du récit.
            long = conn.execute(
                f"SELECT COUNT(*) AS n FROM {table} WHERE length({colonne}) > 250"
            ).fetchone()["n"]
            assert long == 0, f"{table}.{colonne} porte une valeur anormalement longue"


# ---------------------------------------------------------------------------
# Fraîcheur : la séance, jamais la date de modification du dataset
# ---------------------------------------------------------------------------


def test_meta_sources_porte_la_date_de_la_derniere_seance(conn):
    meta = conn.execute(
        "SELECT * FROM meta_sources WHERE source_id = ?", (SOURCE_ID,)
    ).fetchone()
    assert meta is not None, "ligne S38 absente de meta_sources"
    assert meta["date_donnees"] == DERNIERE_SEANCE
    assert meta["licence"].lower().startswith("licence ouverte")
    assert meta["url"].startswith("https://")
    assert meta["notes"] and "AGRÉGATS SEULEMENT" in meta["notes"]


def test_meta_lignes_suit_le_volume_des_agregats(conn):
    """`lignes` doit suivre la table de fait : c'est ce que la supervision
    compare d'une exécution à l'autre pour détecter un effondrement."""
    meta = conn.execute(
        "SELECT lignes FROM meta_sources WHERE source_id = ?", (SOURCE_ID,)
    ).fetchone()
    agregats = conn.execute("SELECT COUNT(*) AS n FROM cada_sens").fetchone()["n"]
    assert meta["lignes"] == agregats


def test_la_date_de_donnees_est_bien_anterieure_au_present(conn):
    """Garde-fou du piège éditorial : la fraîcheur affichée est celle de la
    séance la plus récente du corpus, pas celle du fichier amont."""
    from datetime import date

    meta = conn.execute(
        "SELECT date_donnees, date_ingestion FROM meta_sources WHERE source_id = ?",
        (SOURCE_ID,),
    ).fetchone()
    assert meta["date_donnees"] < date.today().isoformat()
    assert meta["date_donnees"] < meta["date_ingestion"][:10]


# ---------------------------------------------------------------------------
# Idempotence et robustesse du format
# ---------------------------------------------------------------------------


def test_rejouer_ne_duplique_rien(tmp_path):
    chemin = tmp_path / "idempotence.db"
    premier = executer(chemin_db=chemin, chemin_csv=FIXTURE)
    second = executer(chemin_db=chemin, chemin_csv=FIXTURE)
    assert premier == second
    conn = db.connexion(chemin)
    try:
        for table in ("cada_administrations", "cada_saisines", "cada_sens", "cada_motifs"):
            n = conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]
            assert n == second[
                {"cada_administrations": "administrations", "cada_saisines": "saisines",
                 "cada_sens": "sens", "cada_motifs": "motifs"}[table]
            ]
        meta = conn.execute(
            "SELECT COUNT(*) AS n FROM meta_sources WHERE source_id = ?", (SOURCE_ID,)
        ).fetchone()["n"]
        assert meta == 1
    finally:
        conn.close()


def test_un_entete_qui_bouge_fait_echouer(tmp_path):
    """Une colonne renommée en amont doit casser bruyamment.

    Lue par position sans ce contrôle, la même ligne produirait des agrégats
    parfaitement formés et parfaitement faux.
    """
    truque = tmp_path / "entete_modifie.csv"
    lignes = FIXTURE.read_text("utf-8").split("\r\n")
    lignes[0] = lignes[0].replace('"Administration"', '"Autorite"')
    truque.write_text("\r\n".join(lignes), "utf-8")
    with pytest.raises(RuntimeError, match="en-tête"):
        executer(chemin_db=tmp_path / "ko.db", chemin_csv=truque)


# ---------------------------------------------------------------------------
# Réseau (marqueur `reseau`)
# ---------------------------------------------------------------------------


@pytest.mark.reseau
def test_la_ressource_consolidee_existe_toujours():
    """La ressource est repérée par son TITRE : son URL porte l'horodatage du
    versement et change à chaque lot."""
    ressource = resoudre_ressource()
    assert ressource["url"].startswith("https://")
    assert ressource["url"].endswith(".csv")
    assert len(ressource["derniere_modification"]) == 10

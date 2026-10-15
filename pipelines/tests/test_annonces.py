"""Tests P4/P5 (BOAMP + APProch) : parsing d'enregistrements RÉELS captés le
19/08/2026 (fixtures/annonces_reelles.json, aucune valeur modifiée) et tests
d'intégration réseau (@pytest.mark.reseau) qui vérifient que le contrat des
API tient toujours."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from pipelines import ingest_approch, ingest_boamp

FIXTURE = Path(__file__).parent / "fixtures" / "annonces_reelles.json"


@pytest.fixture(scope="module")
def reels() -> dict:
    """Enregistrements réels BOAMP (AO JOUE, AO FNS, attribution) + APProch."""
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Import / surface des modules
# ---------------------------------------------------------------------------


def test_modules_importables_et_executables():
    for module in (ingest_boamp, ingest_approch):
        assert callable(module.main)
        assert module.SOURCE_ID in ("S2", "S9")
    assert ingest_boamp.SOURCE_ID == "S2"
    assert ingest_approch.SOURCE_ID == "S9"


# ---------------------------------------------------------------------------
# BOAMP — extraction du montant (JSON `donnees`, schémas hétérogènes)
# ---------------------------------------------------------------------------


def test_extraire_montant_eforms_niveau_avis(reels):
    # 26-81222 : eForms avec montant global 168 000 € au niveau avis et
    # 0.00 au niveau lot — le montant global doit gagner, jamais le 0.
    montant, devise = ingest_boamp.extraire_montant(reels["boamp_ao_joue"]["donnees"])
    assert montant == pytest.approx(168000.0)
    assert devise == "EUR"


def test_extraire_montant_fns_valeur_estimee(reels):
    # 26-81510 : schéma FNS, valeurEstimee 220 000 €.
    montant, devise = ingest_boamp.extraire_montant(reels["boamp_ao_fns"]["donnees"])
    assert montant == pytest.approx(220000.0)
    assert devise == "EUR"


def test_extraire_montant_absent_reste_null(reels):
    # Attribution réelle sans montant estimé + entrées dégénérées :
    # jamais de montant inventé.
    assert ingest_boamp.extraire_montant(
        reels["boamp_attribution"]["donnees"]
    ) == (None, None)
    assert ingest_boamp.extraire_montant(None) == (None, None)
    assert ingest_boamp.extraire_montant("") == (None, None)
    assert ingest_boamp.extraire_montant("pas du json") == (None, None)


# ---------------------------------------------------------------------------
# BOAMP — parsing des annonces
# ---------------------------------------------------------------------------


def test_parser_ao_enregistrement_reel(reels):
    ligne = ingest_boamp.parser_ao(reels["boamp_ao_joue"])
    assert ligne is not None
    assert ligne["idweb"] == "26-81222"
    assert ligne["acheteur"] == "GHT DU CHER"
    assert ligne["objet"]
    assert ligne["nature"] == "APPEL_OFFRE"
    assert ligne["date_parution"].startswith("2026-")
    assert ligne["date_limite_reponse"] > ligne["date_parution"]
    assert ligne["montant_estime"] == pytest.approx(168000.0)
    assert ligne["url_avis"].startswith("https://www.boamp.fr/")
    # Champs multivalués stockés en JSON valide.
    assert isinstance(json.loads(ligne["type_marche"]), list)
    assert isinstance(json.loads(ligne["departements"]), list)


def test_parser_ao_sans_date_limite_est_ecarte(reels):
    tronque = dict(reels["boamp_ao_joue"], datelimitereponse=None)
    assert ingest_boamp.parser_ao(tronque) is None


def test_parser_annonce_attribution_reelle(reels):
    ligne = ingest_boamp.parser_annonce(reels["boamp_attribution"])
    assert ligne is not None
    assert ligne["nature"] == "ATTRIBUTION"
    titulaires = json.loads(ligne["titulaires"])
    assert titulaires == ["ATMOS"]
    # Une attribution n'a pas de date limite de réponse : NULL, pas inventée.
    assert ligne["date_limite_reponse"] is None


def test_indexer_liens_annulation_et_dernier_rectificatif():
    # Formes réelles constatées : annonce_lie = liste d'idweb d'origine.
    liens = [
        {"idweb": "26-1", "nature": "ANNULATION", "annonce_lie": ["26-100"],
         "dateparution": "2026-08-10"},
        {"idweb": "26-2", "nature": "RECTIFICATIF", "annonce_lie": ["26-200"],
         "dateparution": "2026-08-01"},
        {"idweb": "26-3", "nature": "RECTIFICATIF", "annonce_lie": ["26-200"],
         "dateparution": "2026-08-15"},
        {"idweb": "26-4", "nature": "RECTIFICATIF", "annonce_lie": None,
         "dateparution": "2026-08-15"},
    ]
    annules, rectifs = ingest_boamp.indexer_liens(liens)
    assert annules == {"26-100"}
    assert rectifs == {"26-200": "26-3"}  # le plus récent gagne


# ---------------------------------------------------------------------------
# APProch — parsing d'un projet réel
# ---------------------------------------------------------------------------


def test_parser_projet_reel(reels):
    ligne = ingest_approch.parser_projet(reels["approch_projet"])
    assert ligne is not None
    # L'export livre code et SIREN en entiers : re-typés/re-paddés.
    assert ligne["code"] == "64516"
    assert ligne["acheteur_siren"] == "110014016"
    assert len(ligne["acheteur_siren"]) == 9
    assert ligne["intitule"].startswith("06 – MENTON")
    assert ligne["montant_estime_tranche"] == "1M - 5M€"  # texte, pas de somme
    assert ligne["date_prev_publication"] == "2027-01-09"
    assert ligne["duree_prev_mois"] == 24
    deps = json.loads(ligne["departements"])
    assert "2A" in deps and "" not in deps
    # Champs réellement absents → NULL.
    assert ligne["type_procedure"] is None
    assert ligne["lien_consultation"] is None


def test_parser_projet_siren_reppade_et_cdl():
    rec = dict(
        code=7, date_previsionnelle_de_publication="2026-12-01",
        siren_de_l_entite_acheteuse=1401252,  # zéros de tête perdus par l'export
        montant_estime_du_marche="CDL",       # remplissage data.economie = null
    )
    ligne = ingest_approch.parser_projet(rec)
    assert ligne["acheteur_siren"] == "001401252"
    assert ligne["montant_estime_tranche"] is None


def test_parser_projet_sans_date_est_ecarte():
    assert ingest_approch.parser_projet({"code": 1}) is None


# ---------------------------------------------------------------------------
# Intégration réseau (contrat des API, appels légers)
# ---------------------------------------------------------------------------


@pytest.mark.reseau
def test_boamp_api_contrat_ao_en_cours():
    from pipelines.common import session_http

    r = session_http().get(
        "https://boamp-datadila.opendatasoft.com"
        "/api/explore/v2.1/catalog/datasets/boamp/records",
        params={
            "where": "datelimitereponse>now() AND nature='APPEL_OFFRE'",
            "select": ingest_boamp.CHAMPS_AO,
            "limit": 3,
        },
        timeout=60,
    )
    r.raise_for_status()
    corps = r.json()
    assert corps["total_count"] > 1000  # ~9 000 constatés le 19/08/2026
    maintenant = datetime.now(timezone.utc).isoformat()
    for rec in corps["results"]:
        ligne = ingest_boamp.parser_ao(rec)
        assert ligne is not None
        assert ligne["date_limite_reponse"] > maintenant


@pytest.mark.reseau
def test_approch_api_contrat_projets_futurs():
    from pipelines.common import session_http

    aujourdhui = date.today().isoformat()
    r = session_http().get(
        "https://data.economie.gouv.fr"
        "/api/explore/v2.1/catalog/datasets/projets-dachats-publics/records",
        params={
            "where": f"date_previsionnelle_de_publication>=date'{aujourdhui}'",
            "limit": 3,
        },
        timeout=60,
    )
    r.raise_for_status()
    corps = r.json()
    assert corps["total_count"] > 100  # 4 060 constatés le 19/08/2026
    for rec in corps["results"]:
        ligne = ingest_approch.parser_projet(rec)
        assert ligne is not None
        assert ligne["date_prev_publication"] >= aujourdhui


# ---------------------------------------------------------------------------
# Garde-fou sur la date limite de réponse (docs/SCHEMA-DB.md, § « Conventions de valeurs »)
# ---------------------------------------------------------------------------


def test_limite_plausible_accepte_les_ecarts_reels():
    """Cas réels relevés en production : tout doit passer.

    Le 15 ans pile est le SAD paru le 03/08/2025 et ouvert jusqu'au
    01/09/2040 — un avis parfaitement légitime, qui se trouvait exactement
    sur l'ancien couperet de 15 ans. Le 18 ans garde la marge rendue par
    ECART_MAX_LIMITE_ANNEES : un SAD n'a pas de durée maximale légale, le
    prochain peut aller plus loin sans cesser d'être valable.
    """
    assert ingest_boamp._limite_plausible("2025-06-26", "2025-07-23")
    assert ingest_boamp._limite_plausible("2024-03-24", "2034-04-15")  # 10 ans
    assert ingest_boamp._limite_plausible("2025-08-03", "2040-09-01")  # 15 ans, cas réel
    assert ingest_boamp._limite_plausible("2025-08-03", "2043-09-01")  # 18 ans


def test_limite_plausible_rejette_les_millesimes_fautifs():
    """Cas réels relevés dans la base de production le 20/08/2026."""
    assert not ingest_boamp._limite_plausible("2017-06-23", "7017-07-24")
    assert not ingest_boamp._limite_plausible("2024-03-24", "2924-04-15")
    assert not ingest_boamp._limite_plausible("2025-02-28", "2099-03-02")


def test_limite_plausible_ne_rejette_pas_sur_un_format_illisible():
    """On ne rejette que sur une preuve, jamais sur une incertitude."""
    assert ingest_boamp._limite_plausible("2025-06-26", "")
    assert ingest_boamp._limite_plausible("", "2025-07-23")
    assert ingest_boamp._limite_plausible("date inconnue", "2025-07-23")


def test_parser_ao_ecarte_l_avis_a_echeance_impossible():
    rec = {
        "idweb": "17-88555",
        "dateparution": "2017-06-23",
        "datelimitereponse": "7017-07-24",
        "nomacheteur": "Mairie Saint-Cyprien",
    }
    assert ingest_boamp.parser_ao(rec) is None
    # Même avis, échéance corrigée : il est ingéré.
    rec_sain = dict(rec, datelimitereponse="2017-07-24")
    assert ingest_boamp.parser_ao(rec_sain)["idweb"] == "17-88555"


# ---------------------------------------------------------------------------
# BOAMP — hygiène à l'entrée (`_assainir_champs`)
#
# MUTATIONS TUÉES PAR CE BLOC (jouées le 30/08/2026, chacune re-vérifiée en la
# réintroduisant et en exigeant que CE test-là rougisse) :
#   M8   appel à `_assainir_champs` retiré de `parser_ao`
#   M9   appel retiré de `parser_annonce`
#   M10  appel retiré d'`indexer_liens` (un seul côté du rapprochement assaini)
#   M11  éléments de liste non assainis (revient à n'assainir que le JSON sérialisé)
#   M12  `"donnees"` ajouté à `CHAMPS_TEXTE`
#   M13  compteur figé à zéro
# ---------------------------------------------------------------------------


def test_parser_ao_assainit_les_controles_c1(reels):
    """Le défaut visé par la tranche : un contrôle C1 cp1252 dans `objet`.

    L'enregistrement réel est DÉRIVÉ, jamais réécrit : seule la valeur fautive
    est substituée, et par un octet réellement observé sur ce chemin
    (`0x8C` = « Œ », 7 occurrences en base servie au 30/08/2026).
    """
    sale = dict(reels["boamp_ao_joue"], objet="MAITRISE D'\x8cUVRE et diagnostic")
    ligne = ingest_boamp.parser_ao(sale)
    assert ligne["objet"] == "MAITRISE D'ŒUVRE et diagnostic"
    # … et l'instrument n'est pas muet : sans hygiène, le C1 arriverait tel quel
    assert "\x8c" in sale["objet"]


def test_parser_annonce_assainit_les_espaces_de_acheteur(reels):
    """`acheteur` : blancs de bord, insécables et sauts de ligne internes.

    ARBITRAGE ASSUMÉ : `normaliser_espaces` écrase la structure de ligne des
    adresses postales que BOAMP glisse parfois dans `nomacheteur` (6 valeurs
    sur 19 à saut de ligne, mesuré le 30/08/2026). Le contenu n'est pas perdu,
    seul le séparateur devient une espace — et AUCUNE page ne rend ce champ
    en multiligne : `app/src` ne porte pas une seule règle `white-space`, donc
    le HTML servi collapsait déjà ces sauts de ligne. Ce qui est gagné en
    échange vaut plus : les tris, les `GROUP BY` et la recherche plein texte
    cessent de distinguer deux acheteurs identiques.
    """
    sale = dict(
        reels["boamp_attribution"],
        nomacheteur="  FOUGERES HABITAT\n21 RUE DE LA CASERNE\xa0\n35300 FOUGERES ",
    )
    ligne = ingest_boamp.parser_annonce(sale)
    assert ligne["acheteur"] == "FOUGERES HABITAT 21 RUE DE LA CASERNE 35300 FOUGERES"


def test_parser_annonce_assainit_les_ELEMENTS_de_la_liste_titulaires(reels):
    """MUTATION TUÉE : hygiène appliquée à la chaîne JSON, pas aux éléments.

    `titulaires` est sérialisé par `_liste_json`. Un saut de ligne dans un
    élément devient `\\n` dans le JSON — DEUX caractères ASCII qu'aucune classe
    `\\s` n'attrape. Assainir après sérialisation ne le voit donc pas.

    Ce n'est pas un cas d'école : au 30/08/2026, sur les 17 valeurs sales de
    `annonces_recentes.titulaires` (2 052 non nulles), 16 portent des blancs
    réels — mais UNE est un communiqué entier collé derrière le nom du
    titulaire par un saut de ligne, et celle-là n'est visible qu'ici.
    """
    sale = dict(
        reels["boamp_attribution"],
        titulaire=["PROTECT SECURITE\nLe marché a été notifié le 12 août 2026",
                   "ATMOS\x8cUVRE"],
    )
    titulaires = json.loads(ingest_boamp.parser_annonce(sale)["titulaires"])
    assert titulaires == [
        "PROTECT SECURITE Le marché a été notifié le 12 août 2026",
        "ATMOSŒUVRE",
    ]
    # Contre-épreuve : la chaîne JSON, elle, ne portait aucun blanc réel à
    # normaliser — c'est bien l'élément, et lui seul, qui devait être assaini.
    assert "\\n" in json.dumps(sale["titulaire"], ensure_ascii=False)


def test_assainir_champs_ne_touche_pas_au_blob_donnees(reels):
    """MUTATION TUÉE : `"donnees"` ajouté à `CHAMPS_TEXTE`.

    `donnees` n'est pas une colonne : c'est le blob eForms que lit
    `extraire_montant`. En normaliser les espaces changerait ce que ses
    expressions rationnelles apparient, et le montant servi avec.
    """
    assert "donnees" not in ingest_boamp.CHAMPS_TEXTE
    rec = reels["boamp_ao_joue"]
    propre, _ = ingest_boamp._assainir_champs(rec)
    assert propre["donnees"] == rec["donnees"]
    # Le montant reste celui que le test nominal fige.
    assert ingest_boamp.parser_ao(rec)["montant_estime"] == pytest.approx(168000.0)


def test_assainir_champs_compte_les_valeurs_modifiees(reels):
    """MUTATION TUÉE : compteur figé à zéro.

    Un élément de liste compte pour une valeur — c'est la seule convention qui
    permette de recomposer le total à partir des colonnes.
    """
    rec = reels["boamp_ao_joue"]
    _, zero = ingest_boamp._assainir_champs(rec)
    assert zero == 0, "l'enregistrement réel est sain : le compteur doit rendre 0"
    sale = dict(rec, objet="A\x8cB", nomacheteur="  X  ", type_marche=["S\x8cT", "SAIN"])
    propre, compte = ingest_boamp._assainir_champs(sale)
    assert compte == 3          # objet + nomacheteur + 1 élément sur 2
    assert propre["type_marche"] == ["SŒT", "SAIN"]


def test_assainir_champs_ne_leve_pas_sur_des_champs_nuls(reels):
    """L'ingestion est tout-ou-rien : une levée gèlerait la publication de la
    nuit. `reparer_controles_cp1252` lève `AttributeError` sur `None`, d'où le
    garde `isinstance` d'`assainir_texte_integral`."""
    vide = {cle: None for cle in ingest_boamp.CHAMPS_TEXTE}
    propre, compte = ingest_boamp._assainir_champs(vide)
    assert compte == 0 and all(v is None for v in propre.values())
    assert ingest_boamp._assainir_champs({})[1] == 0
    # Une liste dont un élément est None passe aussi.
    assert ingest_boamp._assainir_champs({"titulaire": [None, "X"]})[1] == 0


def test_indexer_liens_apparie_apres_hygiene_DES_DEUX_COTES():
    """MUTATION TUÉE : hygiène retirée d'`indexer_liens`.

    🛑 `cible` (issu d'`annonce_lie`) est comparée à `ligne["idweb"]`, que
    `parser_ao` assainit. Assainir un seul côté d'un rapprochement DÉPLACE les
    appariements au lieu de les corriger : l'AO cesserait d'être marqué annulé.
    """
    idweb_sale = "26-55241\xa0"
    annules, _ = ingest_boamp.indexer_liens(
        [{"idweb": "26-90000", "nature": "ANNULATION",
          "annonce_lie": [idweb_sale], "dateparution": "2026-08-20"}]
    )
    ao = ingest_boamp.parser_ao({
        "idweb": "26-55241", "dateparution": "2026-08-01",
        "datelimitereponse": "2026-09-01",
    })
    assert ao["idweb"] in annules
    # … et l'instrument n'est pas muet : la clé brute, elle, n'apparie pas.
    assert idweb_sale != ao["idweb"]


# ---------------------------------------------------------------------------
# BOAMP — fourchette d'estimation FNS (`valeurEstimee.fourchette`)
#
# Mesuré le 15/10/2026 sur l'export des AO en cours : 555 avis portaient une
# clé `fourchette` et étaient TOUS servis « non publié ». 134 d'entre eux
# publient une fourchette vide — pour ceux-là, « non publié » est vrai ; les
# 421 autres publient une ou deux bornes. Trois formes réelles figées dans
# fixtures/boamp_fourchettes_reelles.json.
# ---------------------------------------------------------------------------

FIXTURE_FOURCHETTES = Path(__file__).parent / "fixtures" / "boamp_fourchettes_reelles.json"


@pytest.fixture(scope="module")
def fourchettes() -> dict:
    return json.loads(FIXTURE_FOURCHETTES.read_text(encoding="utf-8"))


def test_fourchette_a_deux_bornes_lue_sans_devenir_un_montant(fourchettes):
    rec = fourchettes["fourchette_deux_bornes"]
    assert rec["idweb"] == "26-99937"
    ligne = ingest_boamp.parser_ao(rec)
    assert ligne["montant_fourchette_basse"] == pytest.approx(60000.0)
    assert ligne["montant_fourchette_haute"] == pytest.approx(140000.0)
    # Une fourchette n'est pas un montant : aucune valeur ponctuelle fabriquée.
    assert ligne["montant_estime"] is None
    assert ligne["devise"] is None


def test_fourchette_a_borne_haute_seule_ne_complete_pas_la_basse(fourchettes):
    rec = fourchettes["fourchette_haute_seule"]
    assert rec["idweb"] == "26-100064"
    ligne = ingest_boamp.parser_ao(rec)
    assert ligne["montant_fourchette_basse"] is None
    assert ligne["montant_fourchette_haute"] == pytest.approx(200000.0)
    assert ligne["montant_estime"] is None


def test_fourchette_vide_reste_non_publiee(fourchettes):
    rec = fourchettes["fourchette_vide"]
    assert rec["idweb"] == "26-100118"
    assert '"fourchette": ""' in rec["donnees"]
    ligne = ingest_boamp.parser_ao(rec)
    assert ligne["montant_fourchette_basse"] is None
    assert ligne["montant_fourchette_haute"] is None
    assert ligne["montant_estime"] is None


def test_aucune_borne_publiee_n_est_perdue(fourchettes, reels):
    """Invariant, sur toutes les formes réelles disponibles : un AO qui publie
    une borne numérique dans une fourchette ne ressort jamais avec montant,
    basse et haute tous NULL."""
    recs = [v for k, v in fourchettes.items() if not k.startswith("_")]
    recs += [reels["boamp_ao_joue"], reels["boamp_ao_fns"]]
    for rec in recs:
        donnees = json.loads(rec["donnees"])
        publiee = []

        def chercher(noeud):
            if isinstance(noeud, dict):
                f = noeud.get("fourchette")
                if isinstance(f, dict) and any(
                    str(f.get(k) or "").strip() for k in ("valeurBasse", "valeurHaute")
                ):
                    publiee.append(f)
                for v in noeud.values():
                    chercher(v)
            elif isinstance(noeud, list):
                for v in noeud:
                    chercher(v)

        chercher(donnees)
        ligne = ingest_boamp.parser_ao(rec)
        if publiee:
            assert (ligne["montant_estime"], ligne["montant_fourchette_basse"],
                    ligne["montant_fourchette_haute"]) != (None, None, None), rec["idweb"]


def test_les_formes_a_montant_ponctuel_n_ont_pas_de_fourchette(reels):
    for cle in ("boamp_ao_joue", "boamp_ao_fns"):
        assert ingest_boamp.extraire_fourchette(reels[cle]["donnees"]) == (None, None)


def test_fourchette_inversee_n_est_pas_reprise(fourchettes):
    """Jamais constatée : documente le refus. Bornes échangées sur l'AO réel."""
    rec = dict(fourchettes["fourchette_deux_bornes"])
    rec["donnees"] = rec["donnees"].replace(
        '"valeurBasse": "60000", "valeurHaute": "140000"',
        '"valeurBasse": "140000", "valeurHaute": "60000"',
    )
    assert '"valeurBasse": "140000"' in rec["donnees"]
    ligne = ingest_boamp.parser_ao(rec)
    assert ligne["montant_fourchette_basse"] is None
    assert ligne["montant_fourchette_haute"] is None


def _base_ao_ancien_schema(chemin):
    """`ao_en_cours` telle que la base servie la porte avant les fourchettes."""
    from pipelines import db
    conn = db.init_db(chemin=chemin)
    conn.executescript(
        """
        CREATE TABLE ao_en_cours (
            idweb TEXT PRIMARY KEY, objet TEXT, acheteur TEXT,
            nature TEXT NOT NULL, nature_libelle TEXT, famille TEXT,
            famille_libelle TEXT, type_marche TEXT, type_procedure TEXT,
            procedure_libelle TEXT, descripteurs TEXT, departements TEXT,
            montant_estime REAL, devise TEXT, date_parution TEXT NOT NULL,
            date_limite_reponse TEXT NOT NULL, url_avis TEXT,
            annulee INTEGER NOT NULL DEFAULT 0, rectifiee_par TEXT
        );
        INSERT INTO ao_en_cours (idweb, nature, date_parution, date_limite_reponse)
        VALUES ('26-1', 'APPEL_OFFRE', '2026-08-01', '2026-09-01');
        """
    )
    conn.commit()
    return conn


def test_migrer_ao_en_cours_ajoute_les_colonnes_en_fin_et_est_idempotente(tmp_path):
    conn = _base_ao_ancien_schema(tmp_path / "ancien.db")
    try:
        assert ingest_boamp.migrer_ao_en_cours(conn) == [
            "montant_fourchette_basse", "montant_fourchette_haute",
        ]
        colonnes = [r[1] for r in conn.execute("PRAGMA table_info(ao_en_cours)")]
        assert colonnes[-2:] == ["montant_fourchette_basse", "montant_fourchette_haute"]
        # Une base neuve a le même ordre de colonnes qu'une base migrée.
        neuve = ingest_boamp.db.connexion(tmp_path / "neuve.db")
        neuve.executescript(ingest_boamp.SCHEMA)
        assert [r[1] for r in neuve.execute("PRAGMA table_info(ao_en_cours)")] == colonnes
        neuve.close()
        assert ingest_boamp.migrer_ao_en_cours(conn) == []
    finally:
        conn.close()


def test_pipeline_ecrit_les_bornes_sur_une_base_servie_anterieure(
    tmp_path, monkeypatch, fourchettes, reels
):
    """Bout en bout, sur une base au schéma d'avant : sans migration, l'INSERT
    échouerait sur la base servie alors que la CI, base neuve, resterait verte."""
    chemin = tmp_path / "servie.db"
    _base_ao_ancien_schema(chemin).close()
    monkeypatch.setenv("FT_DB_PATH", str(chemin))
    aos = [v for k, v in fourchettes.items() if not k.startswith("_")]
    bruts = {
        "boamp_ao_en_cours.json": aos,
        "boamp_annonces_recentes.json": [reels["boamp_attribution"]],
        "boamp_annonces_liees.json": [],
    }
    monkeypatch.setattr(ingest_boamp, "_exporter", lambda where, select, dest: bruts[dest])
    assert ingest_boamp.main() == 0

    import sqlite3
    conn = sqlite3.connect(chemin)
    try:
        lignes = dict(
            (r[0], r[1:]) for r in conn.execute(
                "SELECT idweb, montant_estime, montant_fourchette_basse, "
                "montant_fourchette_haute FROM ao_en_cours"
            )
        )
        notes = conn.execute(
            "SELECT notes FROM meta_sources WHERE source_id = 'S2'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert lignes["26-99937"] == (None, 60000.0, 140000.0)
    assert lignes["26-100064"] == (None, None, 200000.0)
    assert lignes["26-100118"] == (None, None, None)
    # Le compte des fourchettes est publié À PART de celui des montants.
    assert "0 avec montant publié dans l'annonce, 2 autres avec seulement une fourchette" in notes


# ---------------------------------------------------------------------------
# BOAMP — fenêtre « 30 j » = 30 jours civils, aujourd'hui compris
# ---------------------------------------------------------------------------


def test_debut_fenetre_couvre_trente_jours_civils_aujourdhui_compris():
    # Le 15/10/2026, l'ancien calcul (today - 30) commençait au 15/09 :
    # 31 dates distinctes dans annonces_par_jour, pour une note « 30 j ».
    debut = ingest_boamp.debut_fenetre(date(2026, 10, 15))
    assert debut == date(2026, 9, 16)
    assert (date(2026, 10, 15) - debut).days + 1 == ingest_boamp.FENETRE_JOURS


def test_le_filtre_amont_part_du_debut_de_fenetre(
    tmp_path, monkeypatch, fourchettes, reels
):
    class Jour(date):
        @classmethod
        def today(cls):
            return cls(2026, 10, 15)

    monkeypatch.setattr(ingest_boamp, "date", Jour)
    monkeypatch.setenv("FT_DB_PATH", str(tmp_path / "fenetre.db"))
    filtres = {}

    def exporter(where, select, dest):
        filtres[dest] = where
        return {
            "boamp_ao_en_cours.json": [fourchettes["fourchette_deux_bornes"]],
            "boamp_annonces_recentes.json": [reels["boamp_attribution"]],
            "boamp_annonces_liees.json": [],
        }[dest]

    monkeypatch.setattr(ingest_boamp, "_exporter", exporter)
    assert ingest_boamp.main() == 0
    assert filtres["boamp_annonces_recentes.json"] == "dateparution>=date'2026-09-16'"


# ---------------------------------------------------------------------------
# BOAMP — motifs de rejet comptés séparément
# ---------------------------------------------------------------------------

AO_ECHEANCE_IMPOSSIBLE = {
    # Avis réel (base de production du 20/08/2026, cf. ECART_MAX_LIMITE_ANNEES).
    "idweb": "17-88555",
    "dateparution": "2017-06-23",
    "datelimitereponse": "7017-07-24",
    "nomacheteur": "Mairie Saint-Cyprien",
}


def test_parser_aos_compte_les_rejets_par_motif(reels):
    sans_limite = dict(reels["boamp_ao_joue"], datelimitereponse=None)
    lignes, rejets = ingest_boamp.parser_aos(
        [AO_ECHEANCE_IMPOSSIBLE, sans_limite, reels["boamp_ao_fns"]]
    )
    assert [l["idweb"] for l in lignes] == [reels["boamp_ao_fns"]["idweb"]]
    assert rejets == {"champs": 1, "limite": 1}
    # Zéro compris : les deux motifs sont toujours présents.
    assert ingest_boamp.parser_aos([reels["boamp_ao_fns"]])[1] == {"champs": 0, "limite": 0}


def test_le_journal_attribue_le_rejet_a_la_date_limite(
    tmp_path, monkeypatch, caplog, reels
):
    monkeypatch.setenv("FT_DB_PATH", str(tmp_path / "rejets.db"))
    bruts = {
        "boamp_ao_en_cours.json": [AO_ECHEANCE_IMPOSSIBLE, reels["boamp_ao_fns"]],
        "boamp_annonces_recentes.json": [reels["boamp_attribution"]],
        "boamp_annonces_liees.json": [],
    }
    monkeypatch.setattr(ingest_boamp, "_exporter", lambda where, select, dest: bruts[dest])
    with caplog.at_level("INFO", logger="ingest_boamp"):
        assert ingest_boamp.main() == 0
    messages = [r.getMessage() for r in caplog.records]
    assert (
        "enregistrements écartés : AO 0 pour champs indispensables absents, "
        "1 pour date limite implausible (> 20 ans) ; annonces 0 pour champs "
        "indispensables absents"
    ) in messages

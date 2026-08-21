#!/usr/bin/env python3
"""Fabrique `stock_unites_legales_mini.parquet`, fixture de S18 (stock Sirene).

Pourquoi un générateur versionné plutôt qu'un parquet tombé du ciel
------------------------------------------------------------------
Le vrai `StockUniteLegale.parquet` pèse 705 Mo pour 29,9 M de lignes : il ne
peut pas entrer au dépôt. Un extrait binaire opaque, lui, ne se relit pas :
personne ne saurait plus quelle ligne éprouve quel piège, ni pourquoi telle
colonne porte tel type. Ce script est donc la source de vérité de la fixture ;
le parquet n'en est que la compilation, régénérable par :

    /srv/france-transparence/app/.venv/bin/python \
        pipelines/tests/fixtures/sirene/fabriquer_fixture.py

DuckDB écrit le parquet (`COPY ... TO ... (FORMAT PARQUET)`) : c'est déjà la
dépendance du pipeline, et ni pandas ni pyarrow ne sont installés.

Fidélité du schéma
------------------
Les 35 colonnes reprennent le nom ET l'ordre exact de l'en-tête du fichier
publié (relevé sur `StockUniteLegale_utf8.csv`, millésime du 01/08/2026) :

    siren,statutDiffusionUniteLegale,unitePurgeeUniteLegale,
    dateCreationUniteLegale,sigleUniteLegale,sexeUniteLegale,prenom1…

Les types sont ceux du parquet réel, et plusieurs sont des pièges :
- `categorieJuridiqueUniteLegale` est un BIGINT alors que c'est un code à
  quatre chiffres — d'où le `lpad(CAST(... AS VARCHAR), 4, '0')` du pipeline ;
- `dateDernierTraitementUniteLegale` est un TIMESTAMP (le millésime en est
  déduit par un CAST en DATE), `dateCreationUniteLegale` une DATE ;
- `anneeEffectifsUniteLegale` est un BIGINT, pas un texte ;
- `economieSocialeSolidaireUniteLegale`, `societeMissionUniteLegale`,
  `statutDiffusionUniteLegale` et `etatAdministratifUniteLegale` sont des
  VARCHAR à valeurs conventionnelles ('O'/'N', 'O'/'P', 'A'/'C').

Contenu : données de personnes physiques inventées, à dessein
-------------------------------------------------------------
Les noms, prénoms et pseudonymes ci-dessous sont fabriqués. Le vrai fichier
en contient de réels, mais faire entrer au dépôt public l'identité de vraies
personnes physiques pour éprouver une règle de minimisation serait exactement
la faute que cette règle prévient. Ils sont volontairement longs et sans
homonymie avec le reste de la fixture : le test de minimisation balaye toutes
les colonnes de la table à la recherche de ces chaînes, et un jeton qui serait
sous-chaîne d'une dénomination légitime le rendrait faux positif.

Le reste (SIREN, catégories juridiques, codes NAF) suit les nomenclatures
réelles : 1000 = personne physique, 5710 = SAS, 7113 = ministère,
9220 = association déclarée, 72xx = collectivités.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import duckdb

SORTIE = Path(__file__).with_name("stock_unites_legales_mini.parquet")

# En-tête réel du fichier publié, avec les types du parquet. L'ordre compte :
# une fixture qui réordonnerait les colonnes ne prouverait plus rien d'un
# pipeline qui, lui, les nomme (mais dont le `SELECT s.*` intermédiaire les
# recopie telles quelles).
COLONNES = [
    ("siren", "VARCHAR"),
    ("statutDiffusionUniteLegale", "VARCHAR"),
    ("unitePurgeeUniteLegale", "BOOLEAN"),
    ("dateCreationUniteLegale", "DATE"),
    ("sigleUniteLegale", "VARCHAR"),
    ("sexeUniteLegale", "VARCHAR"),
    ("prenom1UniteLegale", "VARCHAR"),
    ("prenom2UniteLegale", "VARCHAR"),
    ("prenom3UniteLegale", "VARCHAR"),
    ("prenom4UniteLegale", "VARCHAR"),
    ("prenomUsuelUniteLegale", "VARCHAR"),
    ("pseudonymeUniteLegale", "VARCHAR"),
    ("identifiantAssociationUniteLegale", "VARCHAR"),
    ("trancheEffectifsUniteLegale", "VARCHAR"),
    ("anneeEffectifsUniteLegale", "BIGINT"),
    ("dateDernierTraitementUniteLegale", "TIMESTAMP"),
    ("nombrePeriodesUniteLegale", "BIGINT"),
    ("categorieEntreprise", "VARCHAR"),
    ("anneeCategorieEntreprise", "BIGINT"),
    ("dateDebut", "DATE"),
    ("etatAdministratifUniteLegale", "VARCHAR"),
    ("nomUniteLegale", "VARCHAR"),
    ("nomUsageUniteLegale", "VARCHAR"),
    ("denominationUniteLegale", "VARCHAR"),
    ("denominationUsuelle1UniteLegale", "VARCHAR"),
    ("denominationUsuelle2UniteLegale", "VARCHAR"),
    ("denominationUsuelle3UniteLegale", "VARCHAR"),
    ("categorieJuridiqueUniteLegale", "BIGINT"),
    ("activitePrincipaleUniteLegale", "VARCHAR"),
    ("nomenclatureActivitePrincipaleUniteLegale", "VARCHAR"),
    ("nicSiegeUniteLegale", "VARCHAR"),
    ("economieSocialeSolidaireUniteLegale", "VARCHAR"),
    ("societeMissionUniteLegale", "VARCHAR"),
    ("caractereEmployeurUniteLegale", "VARCHAR"),
    ("activitePrincipaleNAF25UniteLegale", "VARCHAR"),
]


def _unite(siren, **champs):
    """Une ligne de stock : tous les champs à NULL sauf ceux nommés.

    Écrire les 35 positions à la main pour chaque cas rendrait la fixture
    illisible et les erreurs de décalage indétectables ; on nomme donc, et le
    défaut est NULL — ce qu'est massivement le vrai fichier.
    """
    inconnues = set(champs) - {nom for nom, _ in COLONNES}
    if inconnues:
        raise ValueError(f"colonnes hors schéma Sirene : {sorted(inconnues)}")
    champs["siren"] = siren
    return tuple(champs.get(nom) for nom, _ in COLONNES)


# ---------------------------------------------------------------------------
# Les lignes. Chaque bloc éprouve une règle précise du pipeline.
# ---------------------------------------------------------------------------

LIGNES = [
    # --- Personne morale ordinaire, diffusible : le cas nominal. ------------
    _unite(
        "110014016", statutDiffusionUniteLegale="O",
        denominationUniteLegale="MINISTERE DE L INTERIEUR",
        categorieJuridiqueUniteLegale=7113,
        activitePrincipaleUniteLegale="84.11Z",
        nomenclatureActivitePrincipaleUniteLegale="NAFRev2",
        trancheEffectifsUniteLegale="53", anneeEffectifsUniteLegale=2023,
        categorieEntreprise="GE", etatAdministratifUniteLegale="A",
        dateCreationUniteLegale=date(1900, 1, 1),
        dateDernierTraitementUniteLegale=datetime(2026, 7, 15, 9, 0, 0),
        nicSiegeUniteLegale="00015", caractereEmployeurUniteLegale="O",
    ),
    # --- Personne physique (catégorie 1000) PORTANT une identité complète. --
    # Elle doit entrer au référentiel avec est_personne_physique = 1 et
    # denomination NULL, et rien de son identité ne doit atteindre la base.
    _unite(
        "000325175", statutDiffusionUniteLegale="O",
        categorieJuridiqueUniteLegale=1000,
        nomUniteLegale="VERGNIAUDIER", prenom1UniteLegale="ANTHELME",
        prenomUsuelUniteLegale="ANTHELME", sexeUniteLegale="M",
        activitePrincipaleUniteLegale="32.12Z",
        nomenclatureActivitePrincipaleUniteLegale="NAFRev2",
        trancheEffectifsUniteLegale="NN", categorieEntreprise="PME",
        etatAdministratifUniteLegale="A",
        dateCreationUniteLegale=date(2000, 9, 26),
        dateDernierTraitementUniteLegale=datetime(2025, 12, 6, 10, 43, 55),
        nicSiegeUniteLegale="00065",
    ),
    # --- Personne physique « au complet » : quatre prénoms, nom d'usage,
    # pseudonyme. C'est la ligne qui rend le balayage RGPD non trivial.
    _unite(
        "005410220", statutDiffusionUniteLegale="O",
        categorieJuridiqueUniteLegale=1000,
        nomUniteLegale="BOISSELIERE", nomUsageUniteLegale="TARDIVAULX",
        prenom1UniteLegale="ODILONNE", prenom2UniteLegale="MARCELINETTE",
        prenom3UniteLegale="HORTENSIANE", prenom4UniteLegale="SIDONIEVE",
        prenomUsuelUniteLegale="ODILONNE",
        pseudonymeUniteLegale="CHOUETTE DE MINERVIA",
        sexeUniteLegale="F", etatAdministratifUniteLegale="C",
        activitePrincipaleUniteLegale="85.59A",
        nomenclatureActivitePrincipaleUniteLegale="NAFRev2",
        dateCreationUniteLegale=date(1972, 5, 1),
        dateDernierTraitementUniteLegale=datetime(2024, 3, 22, 14, 26, 6),
        nicSiegeUniteLegale="00022",
    ),
    # --- Non diffusible ('P') ET personne physique nommée. Doit disparaître
    # entièrement : c'est le droit d'opposition (art. A123-96 c. com.).
    _unite(
        "402398372", statutDiffusionUniteLegale="P",
        categorieJuridiqueUniteLegale=1000,
        nomUniteLegale="QUILLEVEREC", prenom1UniteLegale="GWENDALIN",
        prenomUsuelUniteLegale="GWENDALIN", sexeUniteLegale="M",
        etatAdministratifUniteLegale="A",
        dateDernierTraitementUniteLegale=datetime(2026, 8, 18, 11, 0, 0),
    ),
    # --- Non diffusible ('P') mais personne MORALE : l'exclusion ne dépend
    # pas de la nature de l'unité. Sa date de traitement est la plus récente
    # de tous les SIREN cités : si le millésime la retenait, il serait faux.
    _unite(
        "799478602", statutDiffusionUniteLegale="P",
        denominationUniteLegale="ENTREPRISE OPPOSEE A LA DIFFUSION",
        categorieJuridiqueUniteLegale=5710,
        etatAdministratifUniteLegale="A",
        dateDernierTraitementUniteLegale=datetime(2026, 8, 19, 7, 30, 0),
    ),
    # --- Économie sociale et solidaire = 'O' → 1. Porte aussi la date de
    # traitement la plus récente PARMI LES RETENUES : c'est elle, et elle
    # seule, qui doit devenir `date_donnees`.
    _unite(
        "775665912", statutDiffusionUniteLegale="O",
        denominationUniteLegale="ASSOCIATION SOLIDAIRE DU MILLESIME",
        sigleUniteLegale="ASM", categorieJuridiqueUniteLegale=9220,
        identifiantAssociationUniteLegale="W751000001",
        economieSocialeSolidaireUniteLegale="O",
        societeMissionUniteLegale="N",
        activitePrincipaleUniteLegale="88.99B",
        nomenclatureActivitePrincipaleUniteLegale="NAFRev2",
        etatAdministratifUniteLegale="A",
        dateCreationUniteLegale=date(1945, 11, 15),
        dateDernierTraitementUniteLegale=datetime(2026, 8, 10, 8, 0, 0),
    ),
    # --- ESS = 'N' → 0 (et non NULL : « non » est une information). ---------
    _unite(
        "552032534", statutDiffusionUniteLegale="O",
        denominationUniteLegale="SOCIETE A MISSION DECLAREE",
        categorieJuridiqueUniteLegale=5710,
        economieSocialeSolidaireUniteLegale="N",
        societeMissionUniteLegale="O",
        categorieEntreprise="ETI", etatAdministratifUniteLegale="A",
        activitePrincipaleUniteLegale="46.90Z",
        nomenclatureActivitePrincipaleUniteLegale="NAFRev2",
        anneeEffectifsUniteLegale=2024, trancheEffectifsUniteLegale="31",
        dateDernierTraitementUniteLegale=datetime(2026, 5, 4, 16, 20, 0),
    ),
    # --- Champs vides (chaîne vide, pas NULL) : le vrai fichier mélange les
    # deux. `nullif(trim(coalesce(...)))` doit tout ramener à NULL, et l'ESS
    # non renseignée doit rester NULL — surtout pas 0.
    _unite(
        "843701234", statutDiffusionUniteLegale="O",
        denominationUniteLegale="STRUCTURE SANS AUCUN ATTRIBUT",
        categorieJuridiqueUniteLegale=5499,
        sigleUniteLegale="", activitePrincipaleUniteLegale="",
        nomenclatureActivitePrincipaleUniteLegale="",
        trancheEffectifsUniteLegale="", categorieEntreprise="",
        etatAdministratifUniteLegale="",
        economieSocialeSolidaireUniteLegale="",
        dateDernierTraitementUniteLegale=datetime(2023, 11, 2, 9, 15, 0),
    ),
    # --- Espaces parasites autour de la dénomination, sigle fait d'espaces :
    # la dénomination doit être rognée, le sigle devenir NULL.
    _unite(
        "213105554", statutDiffusionUniteLegale="O",
        denominationUniteLegale="  COMMUNE DE FIXTURELLES  ",
        sigleUniteLegale="   ", categorieJuridiqueUniteLegale=7210,
        activitePrincipaleUniteLegale="84.11Z",
        nomenclatureActivitePrincipaleUniteLegale="NAFRev2",
        etatAdministratifUniteLegale="A",
        dateDernierTraitementUniteLegale=datetime(2026, 1, 20, 12, 0, 0),
    ),
    # --- Catégorie juridique qui, en BIGINT, s'écrit sur moins de quatre
    # positions. Cas défensif : l'échantillon mesuré (3 M de lignes du CSV
    # réel) n'en contient aucun, mais c'est précisément ce que le `lpad` du
    # pipeline promet de tenir, et rien d'autre ne l'éprouverait.
    _unite(
        "388554702", statutDiffusionUniteLegale="O",
        denominationUniteLegale="UNITE A CATEGORIE JURIDIQUE COURTE",
        categorieJuridiqueUniteLegale=0,
        etatAdministratifUniteLegale="C",
        dateDernierTraitementUniteLegale=datetime(2022, 6, 30, 10, 0, 0),
    ),
    # --- Trois collectivités : elles ne sont citées que par les tables
    # `collectivites_*`, ce qui éprouve autant de branches de la semi-jointure.
    _unite(
        "200054781", statutDiffusionUniteLegale="O",
        denominationUniteLegale="COMMUNAUTE D AGGLOMERATION DE FIXTURIE",
        categorieJuridiqueUniteLegale=7344,
        etatAdministratifUniteLegale="A",
        dateDernierTraitementUniteLegale=datetime(2026, 3, 3, 3, 3, 3),
    ),
    _unite(
        "225000019", statutDiffusionUniteLegale="O",
        denominationUniteLegale="DEPARTEMENT DE FIXTURIE",
        categorieJuridiqueUniteLegale=7220,
        etatAdministratifUniteLegale="A",
        dateDernierTraitementUniteLegale=datetime(2026, 2, 2, 2, 2, 2),
    ),
    _unite(
        "234500023", statutDiffusionUniteLegale="O",
        denominationUniteLegale="REGION DE FIXTURIE",
        categorieJuridiqueUniteLegale=7230,
        etatAdministratifUniteLegale="A",
        dateDernierTraitementUniteLegale=datetime(2026, 4, 4, 4, 4, 4),
    ),
    # --- Unités que la base ne cite PAS. Elles ne doivent jamais entrer : le
    # référentiel est restreint, c'est tout son intérêt (0,55 % du stock).
    # La première porte la date de traitement la plus récente du fichier :
    # un millésime calculé en max global la prendrait, à tort.
    _unite(
        "652014051", statutDiffusionUniteLegale="O",
        denominationUniteLegale="ENTREPRISE JAMAIS CITEE PAR LA BASE",
        categorieJuridiqueUniteLegale=5499,
        etatAdministratifUniteLegale="A",
        dateDernierTraitementUniteLegale=datetime(2026, 8, 20, 23, 59, 59),
    ),
    # La seconde est une personne physique non citée : son identité non plus
    # ne doit apparaître nulle part.
    _unite(
        "380129866", statutDiffusionUniteLegale="O",
        categorieJuridiqueUniteLegale=1000,
        nomUniteLegale="MERLUSSANDRE", prenom1UniteLegale="BASTIENNOEL",
        prenomUsuelUniteLegale="BASTIENNOEL", sexeUniteLegale="M",
        etatAdministratifUniteLegale="A",
        dateDernierTraitementUniteLegale=datetime(2026, 8, 20, 22, 0, 0),
    ),
]

# Remplissage : d'autres unités non citées, pour que le fichier ressemble à
# un stock (où 99,45 % des lignes ne servent à rien) et non à une liste
# choisie. Aucune n'est citée par la base de test.
LIGNES += [
    _unite(
        f"9{numero:08d}", statutDiffusionUniteLegale="O" if numero % 4 else "P",
        denominationUniteLegale=f"UNITE DE REMPLISSAGE NUMERO {numero}",
        categorieJuridiqueUniteLegale=5710 if numero % 2 else 9220,
        etatAdministratifUniteLegale="A" if numero % 3 else "C",
        economieSocialeSolidaireUniteLegale="O" if numero % 5 == 0 else None,
        dateDernierTraitementUniteLegale=datetime(2024, 1, 1 + numero, 12, 0, 0),
        dateCreationUniteLegale=date(1990 + numero, 1, 1),
        nicSiegeUniteLegale=f"{numero:05d}",
    )
    for numero in range(1, 11)
]


def fabriquer(sortie: Path = SORTIE) -> Path:
    """Écrit le parquet de fixture et retourne son chemin."""
    duck = duckdb.connect()
    colonnes_ddl = ", ".join(f'"{nom}" {type_}' for nom, type_ in COLONNES)
    duck.execute(f"CREATE TABLE stock ({colonnes_ddl})")
    marques = ", ".join("?" for _ in COLONNES)
    duck.executemany(f"INSERT INTO stock VALUES ({marques})", LIGNES)
    # ZSTD : le fichier tient en quelques kilo-octets, et c'est aussi la
    # compression du fichier amont.
    duck.execute(
        "COPY (SELECT * FROM stock ORDER BY siren) TO ? "
        "(FORMAT PARQUET, COMPRESSION ZSTD)",
        [str(sortie)],
    )
    duck.close()
    return sortie


if __name__ == "__main__":
    chemin = fabriquer()
    print(f"{chemin} — {len(LIGNES)} lignes, {chemin.stat().st_size} octets")

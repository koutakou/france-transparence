"""P15 — Contenu des déclarations d'intérêts HATVP (`declarations.xml`, S15).

Module UI alimenté : « Élus & Institutions », onglet des fiches d'élus.

Ce pipeline complète P7 (`ingest_integrite`, S14) : `liste.csv` dit qu'une
déclaration EXISTE et à quelle date, ce fichier-ci dit ce qu'elle CONTIENT.

Source : `https://www.hatvp.fr/livraison/merge/declarations.xml`
(88 825 812 octets constatés le 20/08/2026, 6 611 déclarations). ⚠ L'URL
`https://www.hatvp.fr/livraison/opendata/declarations.xml` — celle que l'on
trouve encore citée ici ou là — répond **404** : ne pas y revenir.

Licence : Licence Ouverte Etalab (`fr-lo`), SANS clause de partage à
l'identique. C'est ce qui rend nos propres agrégats republiables en LO 2.0.
Fondement de la publication amont : lois n° 2013-906 et 2013-907 du
11 octobre 2013, qui rendent ces déclarations « librement réutilisables ».

PÉRIMÈTRE : INTÉRÊTS SEULEMENT, JAMAIS LE PATRIMOINE
----------------------------------------------------
Le fichier mélange deux natures juridiques radicalement différentes :

- la déclaration d'INTÉRÊTS (DI) et la déclaration d'intérêts et d'ACTIVITÉS
  (DIA) sont publiées en open data et librement réutilisables ;
- la déclaration de situation PATRIMONIALE des parlementaires relève de
  l'**article LO 135-2 du code électoral** : elle n'est consultable qu'en
  préfecture, par les seuls électeurs inscrits dans le département, et
  **toute publication ou divulgation de son contenu est punie de 45 000 €
  d'amende**.

Le fichier applique déjà ce droit à la source : au 14/08/2026, les 75
déclarations portant des blocs patrimoniaux sont toutes des DSP (64) ou des
DSPFM (11) de membres du gouvernement (59), d'AAI (15) ou d'un cabinet de la
présidence (1) — zéro parlementaire, zéro élu local. **Nous ne dépendons pas
de ça.** Un fichier amont peut changer, une erreur de génération peut faire
déborder un bloc patrimonial dans une déclaration typée DI. Le refus est donc
posé DEUX FOIS, indépendamment :

  barrière 1 — par TYPE de déclaration : seuls DI et DIA sont acceptés, et
               DSP/DSPM/DSPFM/DIM/DIAM sont explicitement refusés ;
  barrière 2 — par NOM DE BALISE : les quatorze balises patrimoniales sont
               refusées quel que soit le type annoncé de la déclaration.

Les deux barrières sont deux chemins de code distincts : si l'une tombe (un
type inconnu apparaît, un renommage de balise passe inaperçu), l'autre suffit
encore. Le test `test_double_barriere_*` de
`pipelines/tests/test_hatvp_declarations.py` en fait la démonstration en
neutralisant chaque barrière à tour de rôle.

Deux blocs sont exclus pour une raison ÉTHIQUE, non juridique — la HATVP les
publie, nous choisissons de ne pas les republier : `activProfConjointDto`
(employeur et profession du conjoint) et `activCollaborateursDto` (identité
des collaborateurs). Ce sont des données sur des TIERS qui n'ont pas de
mandat ; notre finalité est le contrôle des responsables publics, pas de leur
entourage. Et l'on ne persiste jamais `adresseDec`, `email`, `telephoneDec`
ni `pieceIdentite`, qui n'ont aucun usage éditorial.

QUALITÉ DU TEXTE SOURCE — MESURÉE, ET CONTRAIGNANTE POUR L'AFFICHAGE
--------------------------------------------------------------------
Les champs libres ne sont normalisés d'aucune façon : « Education Nationale »,
« Education nationale » et « ASSEMBLEE NATIONALE » cohabitent, les doublons de
saisie sont fréquents, et le marqueur de caviardage `[Données non publiées]`
DÉBORDE dans les champs métier (« SCI [Données non publiées] », « GFA [Données
non publiées] » : 5 677 champs des sept rubriques retenues le portent en plus
d'un texte réel, 5 854 autres ne contiennent que lui). Le marqueur est donc
retiré systématiquement, et un champ qui n'en garde rien devient NULL — une
absence, jamais une chaîne vide et JAMAIS un zéro.

Conséquence éditoriale, inscrite dans le schéma lui-même : **aucune colonne
numérique**. Les montants sont stockés tels qu'ils sont écrits
(`montant TEXT`), ce qui rend structurellement impossible un total, un
classement ou une moyenne construits sur des libellés qui ne les supportent
pas. L'affichage est verbatim, daté, et rien d'autre.

APPARIEMENT
-----------
Clé : nom + prénom normalisés (NFD, sans accents, majuscules) + date de
naissance. `dateNaissance` est renseigné à 100 % côté HATVP comme côté `elus`
(mesuré). Nom + prénom SEULS ne gagneraient que 8 fiches sur 1 053 (+0,8 pt)
et rouvriraient l'homonymie — 588 couples nom+prénom sont partagés par au
moins deux personnes dans `elus`. On n'y retombe pas.

Le rattachement est restreint à la population qui a une fiche publiée
(députés, sénateurs, présidents de conseil départemental et régional — cf.
`app/src/app/elus/[id]/page.tsx`). POURQUOI : ce sont des données personnelles
nominatives ; en persister pour 662 élus de plus qui n'ont aucune page serait
un stock sans usage, contraire à la minimisation de l'article 5(1)(c) du RGPD.
Si la population des fiches change, la dégradation est propre : la donnée
manque, et l'interface dit « pas de donnée » — jamais « rien à déclarer ».

Tables produites (remplacement complet, idempotent) :
- hatvp_decl_interets  : 1 ligne = 1 déclaration DI/DIA rattachée à un élu ;
- hatvp_decl_rubriques : 1 ligne = 1 (déclaration × rubrique), porte le
  `neant` natif — c'est LUI qui permet de distinguer à l'écran « la personne
  a déclaré n'avoir rien à déclarer » de « nous n'avons pas la donnée » ;
- hatvp_decl_lignes    : 1 ligne = 1 intérêt déclaré, verbatim ;
- hatvp_decl_montants  : 1 ligne = 1 montant de rémunération ANNUEL et DATÉ.

meta_sources : S15 (date_donnees = Last-Modified HTTP réel).

Exécution : `python -m pipelines.ingest_hatvp_declarations`
(`FT_DB_PATH` pour rediriger la base). Échec net (exit ≠ 0) si la source est
indisponible, difforme ou invraisemblable — ou si une déclaration TOUJOURS
publiée en amont cesse d'être rattachée à un élu qui porte encore une fiche
(voir `pertes_de_rattachement` : c'est le seul contrôle du lot qui compare au
cycle précédent). Après examen, une telle perte s'acquitte uuid par uuid :
`FT_P15_PERTES_ACQUITTEES=<uuid,uuid> python -m pipelines.ingest_hatvp_declarations`.
"""

from __future__ import annotations

import os
import re
import sqlite3
import sys
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from email.utils import parsedate_to_datetime
from pathlib import Path

from pipelines import db
from pipelines.common import RAW_DIR, assainir_texte, obtenir_logger, session_http, telecharger

log = obtenir_logger("ingest_hatvp_declarations")

# ---------------------------------------------------------------------------
# Constantes source
# ---------------------------------------------------------------------------

ID_SOURCE = "S15"
NOM_SOURCE = "HATVP — contenu des déclarations d'intérêts (declarations.xml)"
URL_DECLARATIONS = "https://www.hatvp.fr/livraison/merge/declarations.xml"
LICENCE = "Licence Ouverte Etalab"

# Cadence : data.gouv.fr annonce « punctual » pour cette ressource, ce qui ne
# calibre aucun seuil de fraîcheur. Le fait observable dit autre chose : le
# Last-Modified de declarations.xml (14/08/2026 10:03:28 GMT) et celui de
# liste.csv (S14, 10:03:29 GMT) sont séparés d'UNE SECONDE — les deux fichiers
# sortent de la même génération hebdomadaire. On retient donc la cadence
# réelle, pas la cadence déclarée : « hebdomadaire », seuils alignés sur S14.
FREQUENCE = "hebdomadaire"

REP_RAW = RAW_DIR / "hatvp_declarations"

# ---------------------------------------------------------------------------
# BARRIÈRE 1 — refus par TYPE de déclaration
# ---------------------------------------------------------------------------

# Seuls ces deux types sont ingérés. Tout autre type — connu ou non — est
# écarté : la liste blanche ne laisse pas passer l'inconnu.
TYPES_INTERETS = frozenset({"DI", "DIA"})

# Refus explicite, redondant AVEC la liste blanche et c'est le but : si un
# jour quelqu'un élargit TYPES_INTERETS sans réfléchir, ce garde-fou-ci
# refuse encore les types qui portent, ou peuvent porter, du patrimoine.
# DIM/DIAM sont des intérêts modificatifs, mais on ne les accepte pas non
# plus tant qu'on n'a pas vérifié qu'ils ne transportent aucun bloc
# patrimonial : au 14/08/2026 le fichier n'en contient aucun (types présents :
# DI 4 469, DIA 2 067, DSP 64, DSPFM 11).
TYPES_PATRIMOINE = frozenset({"DSP", "DSPM", "DSPFM", "DIM", "DIAM"})

# ---------------------------------------------------------------------------
# BARRIÈRE 2 — refus par NOM DE BALISE
# ---------------------------------------------------------------------------
#
# POURQUOI CETTE SECONDE BARRIÈRE, alors que la première suffirait « en
# théorie » : la déclaration de situation patrimoniale des parlementaires
# relève de l'article LO 135-2 du code électoral — consultation en préfecture
# par les seuls électeurs du département, et TOUTE PUBLICATION OU DIVULGATION
# DE SON CONTENU EST PUNIE DE 45 000 € D'AMENDE. Le fichier amont applique
# déjà le droit à la source (aucun parlementaire n'y porte de bloc
# patrimonial), mais faire reposer le respect d'une interdiction pénale sur la
# bonne santé d'un fichier tiers n'est pas une garantie, c'est un pari. On
# refuse donc ces balises pour ce qu'elles sont, quel que soit le type
# annoncé de la déclaration qui les porte : une déclaration typée « DI » qui
# contiendrait un `immeubleDto` verrait ce bloc refusé ici.
BALISES_PATRIMOINE = frozenset({
    "immeubleDto",              # biens immobiliers
    "sciDto",                   # parts de sociétés civiles immobilières
    "valeursEnBourseDto",       # instruments financiers cotés
    "valeursNonEnBourseDto",    # instruments financiers non cotés
    "assuranceVieDto",          # contrats d'assurance-vie
    "comptesBancaireDto",       # comptes bancaires
    "bienDiverDto",             # biens mobiliers divers
    "vehiculeDto",              # véhicules
    "fondDto",                  # fonds de commerce, clientèles
    "autreBienDto",             # autres biens
    "bienEtrangerDto",          # biens détenus à l'étranger
    "passifDto",                # emprunts et dettes
    "observationPatrimoineDto", # observations sur le patrimoine
    "revenuMandatDto",          # revenus perçus au titre du mandat
})

# Exclusion ÉTHIQUE, et non juridique : la HATVP publie bel et bien ces deux
# blocs, et les republier serait licite. Nous ne le faisons pas parce qu'ils
# décrivent des TIERS — un conjoint, des collaborateurs — qui n'exercent
# aucun mandat et n'ont pas choisi la vie publique. Notre finalité est le
# contrôle des responsables publics, elle s'arrête à eux.
BALISES_TIERS = frozenset({
    "activProfConjointDto",     # employeur et profession du conjoint
    "activCollaborateursDto",   # identité des collaborateurs
})

# Champs du déclarant qui ne sont JAMAIS lus ni persistés : ils n'ont aucun
# usage éditorial et sont, pour la plupart, déjà caviardés par la HATVP.
CHAMPS_DECLARANT_INTERDITS = frozenset({
    "adresseDec", "email", "telephoneDec", "pieceIdentite",
})

# ---------------------------------------------------------------------------
# LISTE BLANCHE des rubriques d'intérêts
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Rubrique:
    """Une rubrique d'intérêts : sa clé interne, son intitulé, ses champs.

    `champ_libelle` porte l'entité déclarée (société, employeur, structure),
    `champ_description` ce qui y est fait. Les deux peuvent être absents : la
    rubrique « Observations » n'a qu'un texte libre.
    """

    cle: str
    ordre: int
    libelle: str
    champ_libelle: str | None
    champ_description: str | None
    dates: bool
    remuneration: bool


# L'ordre est celui de la déclaration papier : il est stocké (`rubrique_ordre`)
# pour que l'affichage soit stable sans que l'interface ait à le redéfinir.
RUBRIQUES: dict[str, Rubrique] = {
    "mandatElectifDto": Rubrique(
        "mandat_electif", 1,
        "Mandats électifs et fonctions électives",
        "descriptionMandat", None, True, True),
    "participationDirigeantDto": Rubrique(
        "dirigeant", 2,
        "Participations aux organes dirigeants d'un organisme",
        "nomSociete", "activite", True, True),
    "participationFinanciereDto": Rubrique(
        "participation_financiere", 3,
        "Participations financières directes dans le capital d'une société",
        "nomSociete", None, False, False),
    "activProfCinqDerniereDto": Rubrique(
        "activite_5ans", 4,
        "Activités professionnelles des cinq dernières années",
        "employeur", "description", True, True),
    "activConsultantDto": Rubrique(
        "consultant", 5,
        "Activités de consultant",
        "nomEmployeur", "description", True, True),
    "fonctionBenevoleDto": Rubrique(
        "benevole", 6,
        "Fonctions bénévoles susceptibles de faire naître un conflit d'intérêts",
        "nomStructure", "descriptionActivite", False, False),
    "observationInteretDto": Rubrique(
        "observation", 7,
        "Observations",
        None, "contenu", False, False),
}

# Garde-fou de cohérence, vérifié au chargement du module : une balise ne peut
# pas être à la fois sur la liste blanche et sur une liste noire. Une faute de
# frappe qui ferait passer un bloc patrimonial pour une rubrique d'intérêts
# fait donc échouer l'import, pas l'ingestion silencieusement.
assert not (set(RUBRIQUES) & (BALISES_PATRIMOINE | BALISES_TIERS)), (
    "liste blanche et liste noire se recouvrent : refus de démarrer"
)

# Types de mandat (JSON `elus.mandats`) ouvrant droit à une fiche publiée.
# Copie DÉLIBÉRÉE de TYPES_FICHE_STATIQUE de app/src/app/elus/[id]/page.tsx :
# le pipeline ne peut pas lire le front, et l'inverse serait pire (ingérer des
# données personnelles « au cas où »). Si les deux divergent, il manque de la
# donnée — cas déjà géré à l'écran — jamais l'inverse.
TYPES_FICHE = ("depute", "senateur",
               "president_conseil_departemental", "president_conseil_regional")

# ---------------------------------------------------------------------------
# Schéma
# ---------------------------------------------------------------------------

SCHEMA_P15 = """
DROP TABLE IF EXISTS hatvp_decl_montants;
DROP TABLE IF EXISTS hatvp_decl_lignes;
DROP TABLE IF EXISTS hatvp_decl_rubriques;
DROP TABLE IF EXISTS hatvp_decl_interets;

CREATE TABLE hatvp_decl_interets (
    uuid                     TEXT PRIMARY KEY,   -- uuid natif de la déclaration
    elu_id                   TEXT NOT NULL,      -- elus.id (appariement nom+prénom+naissance)
    type_declaration         TEXT NOT NULL,      -- 'DI' | 'DIA', jamais autre chose
    type_declaration_libelle TEXT,               -- label natif HATVP
    date_depot               TEXT,               -- ISO (jour), depuis dateDepot
    modificative             INTEGER NOT NULL DEFAULT 0,
    qualite_declarant        TEXT,               -- « Vice-président délégué à… », verbatim
    organe_libelle           TEXT,               -- « Ain (01) », « Assemblée nationale »…
    type_mandat              TEXT,               -- codTypeMandatFichier natif
    nb_lignes                INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_hatvp_decl_interets_elu ON hatvp_decl_interets(elu_id);

CREATE TABLE hatvp_decl_rubriques (
    declaration_uuid TEXT NOT NULL,
    rubrique         TEXT NOT NULL,
    rubrique_ordre   INTEGER NOT NULL,
    -- 1 = « néant » déclaré par la personne (un FAIT, affichable) ;
    -- 0 = rubrique renseignée ; NULL = rubrique absente de la déclaration.
    -- Une rubrique absente de cette table = donnée que NOUS n'avons pas.
    neant            INTEGER,
    nb_lignes        INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (declaration_uuid, rubrique)
);

CREATE TABLE hatvp_decl_lignes (
    id                   INTEGER PRIMARY KEY,
    declaration_uuid     TEXT NOT NULL,
    elu_id               TEXT NOT NULL,
    rubrique             TEXT NOT NULL,
    rubrique_ordre       INTEGER NOT NULL,
    rang                 INTEGER NOT NULL,   -- ordre d'apparition dans la rubrique
    libelle              TEXT,               -- société, employeur, structure, mandat
    description          TEXT,               -- activité exercée / texte libre
    date_debut           TEXT,               -- verbatim ('11/2019'), jamais recomposé
    date_fin             TEXT,
    commentaire          TEXT,
    conservee            INTEGER,            -- 1/0/NULL — activité conservée pendant le mandat
    evaluation           TEXT,               -- participation financière : évaluation déclarée
    capital_detenu       TEXT,               -- … part du capital détenue
    nombre_parts         TEXT,               -- … nombre de parts
    remuneration_libre   TEXT,               -- … champ texte libre (« Néant », « 0 », « NS »)
    activite_conseil     TEXT,               -- 'Oui' | 'Non' natifs
    organisation_conseil TEXT
);
CREATE INDEX idx_hatvp_decl_lignes_elu  ON hatvp_decl_lignes(elu_id);
CREATE INDEX idx_hatvp_decl_lignes_decl ON hatvp_decl_lignes(declaration_uuid, rubrique_ordre, rang);

-- Montants de rémunération : ANNUELS et DATÉS, stockés en TEXTE.
-- POURQUOI aucune colonne numérique : les libellés amont ne supportent ni
-- total, ni classement, ni moyenne (saisie libre, doublons, caviardage qui
-- déborde). Ne pas créer la colonne, c'est rendre l'agrégat impossible plutôt
-- que déconseillé.
CREATE TABLE hatvp_decl_montants (
    ligne_id INTEGER NOT NULL,
    annee    TEXT NOT NULL,
    montant  TEXT NOT NULL,   -- verbatim, ex. '70 676' (espace fine insécable native)
    brut_net TEXT,            -- 'Net' | 'Brut' natifs
    PRIMARY KEY (ligne_id, annee)
);
"""


def instructions_schema(script: str = SCHEMA_P15) -> list[str]:
    """Découpe un script SQL en instructions, pour les passer UNE À UNE.

    POURQUOI ne plus confier ce travail à `executescript`, qui le faisait : il
    VALIDE implicitement la transaction en cours avant de lancer son script.
    Comme `SCHEMA_P15` commence par quatre `DROP TABLE`, la destruction partait
    sur disque d'emblée et aucun `rollback()` ne pouvait la reprendre. Passées
    une à une à `conn.execute`, les mêmes instructions restent dans la
    transaction ouverte par `ecrire()` : SQLite fait du DDL transactionnel,
    `DROP TABLE` compris, index et lignes revenant ensemble (mesuré).

    POURQUOI `sqlite3.complete_statement` plutôt qu'un découpage à la main :
    le littéral porte 13 points-virgules dont DEUX vivent dans un commentaire
    `--` (« un FAIT, affichable ; », « 0 = rubrique renseignée ; NULL = … ») —
    un `split(";")` en ferait des fragments invalides, et l'échec surviendrait
    APRÈS les quatre `DROP`. Suivre l'état « dans une chaîne » sans retirer
    d'abord les commentaires serait pire : le littéral porte 20 apostrophes,
    toutes en commentaire, dont deux impaires (« n'avons », « d'apparition »),
    entre lesquelles un tel découpeur avalerait deux fins d'instruction et
    fusionnerait `hatvp_decl_rubriques` avec `hatvp_decl_lignes`.
    `complete_statement` est l'outil de la bibliothèque standard pour cela —
    celui du shell `sqlite3` — et il ignore les commentaires : 11 instructions,
    mesuré (4 `DROP`, 4 `CREATE TABLE`, 3 `CREATE INDEX`).

    Lève `ValueError` sur un script qui se termine hors instruction : mieux
    vaut un échec bruyant AVANT le `BEGIN` qu'un schéma appliqué à moitié.
    """
    instructions: list[str] = []
    tampon = ""
    for ligne in script.splitlines(keepends=True):
        tampon += ligne
        if sqlite3.complete_statement(tampon):
            instructions.append(tampon.strip())
            tampon = ""
    reste = [l for l in tampon.splitlines()
             if l.strip() and not l.strip().startswith("--")]
    if reste:
        raise ValueError(
            "script SQL mal formé : la dernière instruction n'est pas terminée "
            f"par « ; » — {reste[0].strip()[:60]!r}")
    return instructions

# ---------------------------------------------------------------------------
# Hygiène des chaînes
# ---------------------------------------------------------------------------

# Marqueur de caviardage de la HATVP. Il apparaît seul (le champ n'a pas été
# publié) MAIS AUSSI collé à un texte métier réel — « SCI [Données non
# publiées] », « SCEA [Données non publiées] ». Mesuré le 20/08/2026 sur les
# sept rubriques retenues : 5 854 champs ne contiennent que lui, 5 677 le
# portent en plus d'un texte. Il est retiré dans les deux cas : ce n'est pas
# une donnée, c'est une mention de service.
RE_NON_PUBLIE = re.compile(r"\[\s*Donn[ée]es\s+non\s+publi[ée]es\s*\]", re.IGNORECASE)


def nettoyer(valeur: str | None) -> str | None:
    """Texte source prêt à stocker, ou None s'il ne reste rien.

    Enchaîne l'hygiène commune (mojibake, insécables, retours ligne) puis le
    retrait du marqueur de caviardage. Retourne None — et jamais une chaîne
    vide — pour que l'absence reste une absence jusque dans l'interface : un
    champ vide affiché « 0 » ou « — » sans nuance serait une affirmation.
    """
    propre = assainir_texte(valeur)
    if propre is None:
        return None
    propre = " ".join(RE_NON_PUBLIE.sub(" ", propre).split())
    return propre or None


def normaliser_identite(valeur: str | None) -> str:
    """NFD sans accents, tirets/apostrophes → espace, majuscules.

    C'est la moitié « nom » de la clé d'appariement. Les majuscules (et non
    le casefold de P7) suivent la convention retenue pour cette source, où le
    nom arrive déjà en capitales côté HATVP.
    """
    s = unicodedata.normalize("NFD", valeur or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.replace("-", " ").replace("'", " ").replace("’", " ")
    return " ".join(s.split()).upper()


_PARENTHESES = re.compile(r"\([^)]*\)")
_NON_ALPHANUM = re.compile(r"[^A-Z0-9]+")
_LONGUEUR_PARTICULE = 2      # « LE », « DE », « EL », « DU »… jamais appariantes


def composantes_identite(valeur: str | None) -> frozenset[str]:
    """Mots d'un nom ou d'un prénom, plus la forme recollée sans séparateur.

    Sert au SEUL repli de `construire_index_souple`, jamais à la clé exacte.
    Le contenu entre parenthèses est retiré : l'Assemblée désambiguïse ses
    députés homonymes par le département (« Martin (Gironde) »), ce qui
    n'appartient pas au patronyme. La forme recollée rattrape les graphies que
    les sources coupent différemment (« K/Bidi » côté Assemblée, « KBIDI »
    côté RNE).

    ⚠️ Ni le retrait des parenthèses, ni la forme recollée, ni le filtre des
    particules ne rattrapent quoi que ce soit AUJOURD'HUI : mesuré le
    26/08/2026, les 71 rattachements sortent tous de la seule intersection de
    mots, et retirer l'un de ces trois mécanismes n'en fait perdre aucun. Ils
    sont là par prophylaxie — le premier deviendra utile à la fusion des
    doublons, le troisième ferme une faille réelle (voir _LONGUEUR_PARTICULE).
    Ne pas les présenter comme des correctifs mesurés.
    """
    t = _NON_ALPHANUM.sub(" ", normaliser_identite(_PARENTHESES.sub(" ", valeur or "")))
    mots = t.split()
    if not mots:
        return frozenset()
    recolle = "".join(mots)
    if len(mots) == 1:
        return frozenset(mots)
    # Les PARTICULES ne sont jamais appariantes. Mesuré sur les fiches servies :
    # « LE » est porté par 18 d'entre elles et « DE » par 14 ; sans ce filtre,
    # une déclaration « LE MEUR Marie » pourrait s'apparier à une fiche
    # « LE GAC Marie » de la même année sur la seule syllabe « LE ». Elles
    # restent dans la forme recollée, qui, elle, discrimine.
    return frozenset(m for m in mots if len(m) > _LONGUEUR_PARTICULE) | {recolle}


def dates_voisines(a: str | None, b: str | None) -> bool:
    """Même ANNÉE, et au plus une des trois composantes qui diverge.

    Deux sources officielles se contredisent parfois d'un chiffre sur l'état
    civil d'une même personne — mesuré entre `declarations.xml` et l'AN :
    Gisèle Lelouis, 1952-05-10 contre 1952-03-10 ; Nicolas Metzdorf,
    1988-02-20 contre 1988-05-20 ; Daniel Chasseing, 1945-04-19 contre
    1945-04-10. L'année reste EXIGÉE : c'est elle qui empêche la tolérance de
    dégénérer en appariement par le seul patronyme.
    """
    a, b = (a or "").strip(), (b or "").strip()
    if len(a) != 10 or len(b) != 10:
        return False
    pa, pb = a.split("-"), b.split("-")
    if len(pa) != 3 or len(pb) != 3 or pa[0] != pb[0]:
        return False
    return sum(1 for x, y in zip(pa, pb) if x != y) <= 1


_RE_DATE_FR = re.compile(r"(\d{2})/(\d{2})/(\d{4})")


def date_iso(valeur: str | None) -> str | None:
    """'29/11/2024 18:54:22' → '2024-11-29'. Rien de reconnaissable → None.

    Aucune date n'est devinée : une saisie hors format ressort NULL plutôt
    que réparée au jugé.
    """
    m = _RE_DATE_FR.match((valeur or "").strip())
    if not m:
        return None
    try:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat()
    except ValueError:
        return None


def _texte(element: ET.Element | None, chemin: str) -> str | None:
    """Texte nettoyé d'un sous-élément, ou None (élément absent compris)."""
    if element is None:
        return None
    return nettoyer(element.findtext(chemin))


def _booleen(valeur: str | None) -> int | None:
    """'true'/'false' natifs → 1/0 ; toute autre valeur (dont l'absence) → None.

    Le None est significatif : il dit « la source ne s'est pas prononcée »,
    ce qui n'est pas la même chose que « non ».
    """
    v = (valeur or "").strip().lower()
    return 1 if v == "true" else 0 if v == "false" else None


# ---------------------------------------------------------------------------
# Les deux barrières, en fonctions séparées et testables
# ---------------------------------------------------------------------------


def type_declaration_accepte(type_id: str | None) -> bool:
    """BARRIÈRE 1. Vrai pour les seules déclarations d'intérêts (DI, DIA).

    Deux conditions, volontairement redondantes : appartenir à la liste
    blanche ET ne pas figurer sur la liste des types patrimoniaux. La seconde
    ne sert à rien tant que la première est juste — c'est précisément ce qu'on
    veut d'un garde-fou.
    """
    t = (type_id or "").strip().upper()
    return t in TYPES_INTERETS and t not in TYPES_PATRIMOINE


def balise_acceptee(balise: str) -> bool:
    """BARRIÈRE 2. Vrai pour les seules rubriques d'intérêts retenues.

    Le refus patrimonial est testé EN PREMIER et pour lui-même : il ne
    dépend ni du type de la déclaration, ni de la liste blanche. Une balise
    patrimoniale trouvée dans une déclaration typée « DI » est refusée ici.
    """
    if balise in BALISES_PATRIMOINE or balise in BALISES_TIERS:
        return False
    return balise in RUBRIQUES


# ---------------------------------------------------------------------------
# Extraction d'une déclaration
# ---------------------------------------------------------------------------


def lire_identite(declaration: ET.Element) -> tuple[str, str, str | None]:
    """(nom normalisé, prénom normalisé, date de naissance ISO) du déclarant.

    Seuls ces trois champs de `declarant` sont lus. `adresseDec`, `email`,
    `telephoneDec` et `pieceIdentite` ne sont ni lus ni stockés (cf.
    CHAMPS_DECLARANT_INTERDITS) : ils n'ont aucun usage éditorial.
    """
    d = declaration.find("general/declarant")
    if d is None:
        return "", "", None
    return (
        normaliser_identite(d.findtext("nom")),
        normaliser_identite(d.findtext("prenom")),
        date_iso(d.findtext("dateNaissance")),
    )


def extraire_montants(item: ET.Element) -> list[tuple[str, str, str | None]]:
    """(année, montant verbatim, brut/net) d'un item, années dédoublonnées.

    Un montant vide est ÉCARTÉ : 81 items du fichier du 14/08/2026 portent une
    année sans montant. Les stocker à 0 fabriquerait une rémunération nulle
    déclarée qui n'existe pas — c'est exactement l'erreur que ce projet
    s'interdit.
    """
    remuneration = item.find("remuneration")
    if remuneration is None or len(remuneration) == 0:
        return []
    brut_net = nettoyer(remuneration.findtext("brutNet"))
    vus: set[str] = set()
    lignes: list[tuple[str, str, str | None]] = []
    for montant in remuneration.findall("montant/montant"):
        annee = nettoyer(montant.findtext("annee"))
        valeur = nettoyer(montant.findtext("montant"))
        if not annee or not valeur or annee in vus:
            continue
        vus.add(annee)
        lignes.append((annee, valeur, brut_net))
    return lignes


def extraire_declaration(declaration: ET.Element) -> dict | None:
    """Contenu retenu d'une déclaration, ou None si elle est refusée.

    Retourne un dict : entete, rubriques, lignes (chacune avec ses montants),
    plus les compteurs de refus utiles à la traçabilité.
    """
    general = declaration.find("general")
    if general is None:
        return None

    type_id = (general.findtext("typeDeclaration/id") or "").strip().upper()
    # BARRIÈRE 1 : une DSP, une DSPFM ou un type inconnu s'arrête ici, et
    # aucune de ses balises n'est même regardée.
    if not type_declaration_accepte(type_id):
        return None

    uuid = nettoyer(declaration.findtext("uuid"))
    if not uuid:
        return None

    entete = {
        "uuid": uuid,
        "type_declaration": type_id,
        "type_declaration_libelle": _texte(general, "typeDeclaration/label"),
        "date_depot": date_iso(declaration.findtext("dateDepot")),
        "modificative": 1 if _booleen(general.findtext("declarationModificative")) == 1 else 0,
        "qualite_declarant": _texte(general, "qualiteDeclarant"),
        "organe_libelle": _texte(general, "organe/labelOrgane"),
        "type_mandat": _texte(general, "qualiteMandat/codTypeMandatFichier"),
    }

    rubriques: list[dict] = []
    lignes: list[dict] = []
    refus_patrimoine = 0

    # On parcourt ce que le FICHIER contient, et non la liste blanche : c'est
    # ce qui rend la barrière 2 vivante. Un bloc patrimonial est vu, compté,
    # puis refusé — au lieu de n'avoir jamais été cherché.
    for bloc in declaration:
        if bloc.tag in BALISES_PATRIMOINE:
            refus_patrimoine += 1
            continue
        if not balise_acceptee(bloc.tag):
            continue
        rubrique = RUBRIQUES[bloc.tag]
        items = bloc.findall("items/items")
        rubriques.append({
            "rubrique": rubrique.cle,
            "rubrique_ordre": rubrique.ordre,
            "neant": _booleen(bloc.findtext("neant")),
            "nb_lignes": len(items),
        })
        for rang, item in enumerate(items, start=1):
            lignes.append({
                "rubrique": rubrique.cle,
                "rubrique_ordre": rubrique.ordre,
                "rang": rang,
                "libelle": _texte(item, rubrique.champ_libelle) if rubrique.champ_libelle else None,
                "description": (_texte(item, rubrique.champ_description)
                                if rubrique.champ_description else None),
                "date_debut": _texte(item, "dateDebut") if rubrique.dates else None,
                "date_fin": _texte(item, "dateFin") if rubrique.dates else None,
                "commentaire": _texte(item, "commentaire"),
                "conservee": _booleen(item.findtext("conservee")),
                "evaluation": _texte(item, "evaluation"),
                "capital_detenu": _texte(item, "capitalDetenu"),
                "nombre_parts": _texte(item, "nombreParts"),
                # `remuneration` est un sous-arbre pour les rubriques à
                # montants datés, et un simple texte pour les participations
                # financières : on ne lit le texte que dans le second cas.
                "remuneration_libre": (None if rubrique.remuneration
                                       else _texte(item, "remuneration")),
                "activite_conseil": _texte(item, "actiConseil"),
                "organisation_conseil": _texte(item, "nomOrganisationConseil"),
                "montants": extraire_montants(item) if rubrique.remuneration else [],
            })

    entete["nb_lignes"] = len(lignes)
    return {"entete": entete, "rubriques": rubriques, "lignes": lignes,
            "refus_patrimoine": refus_patrimoine}


# ---------------------------------------------------------------------------
# Appariement
# ---------------------------------------------------------------------------


def construire_index_elus(conn) -> dict[tuple[str, str, str], str]:
    """{(nom, prénom, naissance) → elus.id} pour les élus AYANT une fiche.

    Une clé partagée par deux élus est retirée de l'index : un homonyme né le
    même jour n'est pas tranchable, et attribuer une déclaration à la
    mauvaise personne est la faute la plus grave que ce pipeline puisse
    commettre. Mesuré le 20/08/2026 : zéro collision sur les 1 053 fiches.
    """
    marques = ", ".join("?" for _ in TYPES_FICHE)
    index: dict[tuple[str, str, str], str] = {}
    collisions: set[tuple[str, str, str]] = set()
    for r in conn.execute(
        f"""SELECT DISTINCT e.id, e.nom, e.prenom, e.date_naissance
            FROM elus e, json_each(e.mandats) je
            WHERE json_extract(je.value, '$.type') IN ({marques})""",
        TYPES_FICHE,
    ):
        naissance = (r["date_naissance"] or "").strip()
        if not naissance:
            continue
        cle = (normaliser_identite(r["nom"]), normaliser_identite(r["prenom"]), naissance)
        if cle in index and index[cle] != r["id"]:
            collisions.add(cle)
        index[cle] = r["id"]
    for cle in collisions:
        index.pop(cle, None)
    if collisions:
        log.warning("appariement : %d clé(s) nom+prénom+naissance partagée(s) par "
                    "plusieurs élus, écartée(s) — homonyme non tranché = non apparié",
                    len(collisions))
    return index


def construire_index_souple(conn) -> dict[tuple[str, str], list[dict]]:
    """{(année de naissance, composante de nom) → [fiches]} — REPLI SEULEMENT.

    POURQUOI ce repli existe. La clé exacte `(nom, prénom, naissance)` est
    juste et doit le rester : elle est ce qui empêche d'attribuer la
    déclaration d'une personne à son homonyme. Mais elle exige que
    `declarations.xml` écrive l'état civil exactement comme la source qui a
    posé la fiche — l'Assemblée et le Sénat via P9, le RNE via P7 — et mesuré
    sur le fichier servi, ce n'est pas le cas. **71 déclarations d'intérêts,
    portant 875 lignes et concernant 32 parlementaires, étaient jetées en
    silence** pour cette seule raison.

    Les écarts mesurés le 26/08/2026, tous entre deux graphies d'une même
    personne, avec les cas que le repli rattrape RÉELLEMENT :
      · nom composé porté en entier par la chambre, tronqué par la HATVP
        (« Borchio Fontimp » / « FONTIMP », « Parmentier-Lecocq » / « LECOCQ »,
        « Vermorel-Marques » / « VERMOREL », « Dogor-Such » / « DOGOR ») —
        c'est le motif dominant ;
      · composante commune en FIN de nom (« Corbière Naminzo » / « CORBIERE »,
        « Berthet » / « BERTHET COTTAREL ») ;
      · nom d'épouse ajouté d'un seul côté (« Féret » / « FERET EPOUSE
        EL ADNANI », « Jacques » / « BLANCHARD EPOUSE JACQUES ») ;
      · prénoms inversés ou composés tronqués à la source (« Carlos Martens »
        / « MARTENS CARLOS », « Charles » / « CHARLES AMEDEE », « Marie-Do »
        / « MARIE DOMINIQUE ») ;
      · date de naissance divergeant d'une composante — 3 cas seulement
        (Chasseing, Lelouis, Metzdorf), et pour deux d'entre eux
        `declarations.xml` porte lui-même les DEUX dates sous le même nom :
        c'est une coquille de la source, pas deux personnes.

    Ce que le repli NE fait PAS aujourd'hui, contrairement à ce qu'on pourrait
    croire : il ne traite pas les fiches en double `rne-*` / `PA*` (Favennec,
    Vaginay, K/Bidi, Xowie…). Pour celles-là la clé exacte réussit déjà, sur
    le jumeau `rne-*`. Le repli est en revanche ce qui rendra leur fusion SANS
    PERTE le jour où elle sera faite : mesuré sur une fusion simulée,
    2 247 par clé exacte + 85 par repli = **2 332, le même total qu'ici**.
    Livrer cette fusion sans ce repli détruirait 14 déclarations.

    Trois garde-fous, sans lesquels le remède serait pire que le mal :
      1. l'index ne contient que les élus AYANT une fiche, comme la clé
         exacte — le vivier reste celui des personnes que le site publie ;
      2. il faut une composante de NOM **et** une de PRÉNOM en commun,
         l'année identique, et au plus une composante de date divergente ;
      3. **un seul candidat**, sinon on renonce. Deux candidats, c'est une
         homonymie, et la trancher au hasard serait la faute la plus grave
         que ce pipeline puisse commettre.

    ⚠️ Limite connue du garde-fou n° 3 : « un seul candidat » se mesure sur
    l'état de `elus` du jour. Six des 32 appariements ne tiennent que par
    l'unicité de leur patronyme dans le vivier — MARTIN/Élisa (9 fiches
    portent « MARTIN »), PETIT/Maud, ROUSSET/Alain, TACHE/Emmanuel (contre
    Aurélien Taché, 1984), CORBIERE/Evelyne (contre Alexis Corbière, 1968) et
    JACQUES/Micheline. Le jour où un homonyme de la MÊME ANNÉE entre dans
    `elus`, leur déclaration se détache — et c'est précisément le cas mesuré
    sur Martin/Élisa. ⚠️ Ce paragraphe a longtemps fini par « SANS BRUIT.
    Aucun contrôle ne le verrait : les garde-fous de `main()` sont un plancher
    et une proportion, pas un delta. » Les deux moitiés étaient fausses, et le
    sont restées après le correctif qui les démentait. **Ce détachement est
    désormais vu** : c'est exactement le trou que `pertes_de_rattachement`
    ferme, sans seuil ni tolérance. Et les garde-fous n'ont jamais été dans
    `main()` — ils sont tous dans `executer()`, posés avant `ecrire()` ;
    `main()` ne fait qu'attraper et journaliser.

    Ce repli n'écrase JAMAIS la clé exacte : il n'est consulté qu'après son
    échec. Il est donc strictement additif — il rattache des déclarations
    aujourd'hui jetées, il n'en déplace aucune.
    """
    marques = ", ".join("?" for _ in TYPES_FICHE)
    index: dict[tuple[str, str], list[dict]] = defaultdict(list)
    vus: set[str] = set()
    for r in conn.execute(
        f"""SELECT DISTINCT e.id, e.nom, e.prenom, e.date_naissance
            FROM elus e, json_each(e.mandats) je
            WHERE json_extract(je.value, '$.type') IN ({marques})""",
        TYPES_FICHE,
    ):
        naissance = (r["date_naissance"] or "").strip()
        if len(naissance) != 10 or r["id"] in vus:
            continue
        vus.add(r["id"])
        fiche = {"id": r["id"], "naissance": naissance,
                 "prenom": composantes_identite(r["prenom"])}
        for composante in composantes_identite(r["nom"]):
            index[(naissance[:4], composante)].append(fiche)
    return index


def apparier_souple(index_souple: dict, nom: str | None, prenom: str | None,
                    naissance: str | None) -> str | None:
    """Un identifiant d'élu, ou None si aucun candidat — ou plus d'un."""
    naissance = (naissance or "").strip()
    if len(naissance) != 10:
        return None
    composantes_prenom = composantes_identite(prenom)
    if not composantes_prenom:
        return None
    candidats: dict[str, dict] = {}
    for composante in composantes_identite(nom):
        for fiche in index_souple.get((naissance[:4], composante), ()):
            if fiche["id"] in candidats:
                continue
            if not dates_voisines(naissance, fiche["naissance"]):
                continue
            if not (composantes_prenom & fiche["prenom"]):
                continue
            candidats[fiche["id"]] = fiche
    if len(candidats) != 1:            # garde-fou n° 3 : homonymie non tranchée
        return None
    return next(iter(candidats))


# ---------------------------------------------------------------------------
# Parcours EN FLUX du fichier
# ---------------------------------------------------------------------------


def parcourir(chemin: str | Path, index_elus: dict[tuple[str, str, str], str],
              index_souple: dict | None = None) -> dict:
    """Lit declarations.xml EN FLUX et retourne les lignes prêtes à écrire.

    POURQUOI iterparse et pas ET.parse : le fichier pèse 88,8 Mo et grossit
    à chaque publication ; un chargement intégral construirait un arbre de
    plusieurs centaines de Mo pour n'en garder que 6,5. Chaque `<declaration>`
    est traitée puis libérée, et la racine est vidée dans la foulée — sans
    quoi elle conserverait 6 611 coquilles vides et l'on aurait juste déplacé
    la fuite.
    """
    contexte = ET.iterparse(chemin, events=("start", "end"))
    _, racine = next(contexte)

    entetes: list[dict] = []
    rubriques: list[tuple] = []
    lignes: list[dict] = []
    # Les uuid de TOUTES les déclarations que la source publie encore et que la
    # barrière de type accepte — rattachées ou non. C'est l'observable qui
    # sépare un retrait amont légitime d'une perte d'appariement : voir
    # `pertes_de_rattachement`. Coût mesuré le 26/08/2026 sur le fichier servi :
    # 6 527 uuid distincts (6 608 déclarations lues, 75 refusées par type, et
    # 6 uuid que la source publie en double), soit ≈ 1 Mo retenu jusqu'au
    # contrôle — 0,5 Mo de `set` et 0,5 Mo de chaînes que `element.clear()`
    # libérerait sans lui, contre 131 Mo de RSS pour le processus.
    # Les trois relectures du cycle précédent coûtent 1,9 ms (2 332
    # rattachements), 9,7 ms (28 586 lignes groupées) et 108 ms (le vivier des
    # fiches) — contre 5,4 s de parcours cache chaud, 12,9 s au premier accès
    # au fichier de 88,8 Mo. Toutes ces valeurs sont mesurées le 26/08/2026.
    uuids_vus: set[str] = set()
    stats: Counter = Counter()

    for evenement, element in contexte:
        if evenement != "end" or element.tag != "declaration":
            continue
        stats["declarations_lues"] += 1
        extrait = extraire_declaration(element)
        if extrait is None:
            stats["refus_type_declaration"] += 1
            element.clear()
            racine.clear()
            continue
        stats["refus_balise_patrimoine"] += extrait["refus_patrimoine"]
        uuids_vus.add(extrait["entete"]["uuid"])

        nom, prenom, naissance = lire_identite(element)
        if not naissance:
            stats["sans_date_naissance"] += 1
        elu_id = index_elus.get((nom, prenom, naissance or ""))
        if elu_id is None and index_souple is not None:
            # Repli : les deux sources n'écrivent pas l'état civil pareil.
            # Voir construire_index_souple pour le pourquoi et les garde-fous.
            elu_id = apparier_souple(index_souple, nom, prenom, naissance)
            if elu_id is not None:
                stats["rattachees_par_repli"] += 1
        if elu_id is None:
            stats["non_apparie"] += 1
            element.clear()
            racine.clear()
            continue
        stats["rattachees"] += 1

        entete = extrait["entete"]
        entete["elu_id"] = elu_id
        entetes.append(entete)
        for r in extrait["rubriques"]:
            rubriques.append((entete["uuid"], r["rubrique"], r["rubrique_ordre"],
                              r["neant"], r["nb_lignes"]))
            if r["neant"] == 1:
                stats["rubriques_neant"] += 1
        for ligne in extrait["lignes"]:
            ligne["declaration_uuid"] = entete["uuid"]
            ligne["elu_id"] = elu_id
            lignes.append(ligne)
            if ligne["montants"]:
                stats["lignes_avec_montant"] += 1
            stats["montants"] += len(ligne["montants"])

        element.clear()
        racine.clear()

    stats["lignes"] = len(lignes)
    stats["elus_apparies"] = len({e["elu_id"] for e in entetes})
    return {"entetes": entetes, "rubriques": rubriques, "lignes": lignes,
            "uuids_vus": uuids_vus, "stats": stats}


# ---------------------------------------------------------------------------
# Écriture
# ---------------------------------------------------------------------------

_COLONNES_LIGNE = (
    "declaration_uuid", "elu_id", "rubrique", "rubrique_ordre", "rang",
    "libelle", "description", "date_debut", "date_fin", "commentaire",
    "conservee", "evaluation", "capital_detenu", "nombre_parts",
    "remuneration_libre", "activite_conseil", "organisation_conseil",
)


def ecrire(conn, donnees: dict) -> None:
    """Remplacement complet des quatre tables, dans UNE transaction — mesuré.

    Le schéma DROPpe puis recrée : rejouer le pipeline sur la même base
    redonne exactement les mêmes compteurs, jamais des lignes en double.

    🛑 CE FICHIER A ANNONCÉ TROIS FOIS UNE ATOMICITÉ QU'IL N'AVAIT PAS ; les
    deux lignes ci-dessous sont ce qui la lui donne. Ce qu'il ne faut jamais
    remettre à leur place, c'est `conn.executescript(SCHEMA_P15)` :
    `executescript` VALIDE implicitement la transaction en cours avant de
    lancer son script, si bien que les quatre `DROP TABLE` partaient sur
    disque avant le premier `INSERT`. Mesuré le 26/08/2026 sur Python 3.14.6
    et SQLite 3.37.2, ceux de la production : 2 déclarations en base, un uuid
    rattaché deux fois — la source en publie 6 en double — faisait lever
    `UNIQUE constraint failed`, et une connexion neuve relisait **0**. Même
    mesure après ce correctif : elle relit **2**, avec les mêmes uuid et les
    trois index, en WAL comme hors WAL. La propriété est tenue par
    `test_un_echec_apres_le_drop_laisse_la_base_intacte` — sans lui elle
    régresserait en silence, ce qui est déjà arrivé une fois.

    Ce que `ecrire()` ne fait pas : valider. Elle laisse la transaction
    ouverte ; `executer()` commit après le contrôle de sortie et rollback sur
    toute exception. Un contrôle posé APRÈS elle — c'est le cas du seul
    `controler_absence_patrimoine` — rend donc bien la base à son état
    antérieur en échouant, et les deux contrôles inter-cycles gardent leur
    mémoire par-dessus l'incident.

    ⚠️ Si l'appelant a DÉJÀ une transaction ouverte, `ecrire()` s'y greffe :
    un second `BEGIN` lèverait « cannot start a transaction within a
    transaction » (mesuré). Le prix, à connaître avant d'appeler : le
    `rollback()` qui suit un échec annule alors AUSSI le travail non validé de
    l'appelant. Sur le chemin réel le cas ne se présente pas — entre
    `db.init_db()`, qui valide, et cet appel, `executer()` ne fait que des
    `SELECT`, qui n'ouvrent pas de transaction en contrôle hérité (mesuré :
    `in_transaction` est faux à l'entrée).
    """
    if not conn.in_transaction:
        conn.execute("BEGIN")
    for instruction in instructions_schema():
        conn.execute(instruction)

    conn.executemany(
        "INSERT INTO hatvp_decl_interets (uuid, elu_id, type_declaration,"
        " type_declaration_libelle, date_depot, modificative, qualite_declarant,"
        " organe_libelle, type_mandat, nb_lignes)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [(e["uuid"], e["elu_id"], e["type_declaration"], e["type_declaration_libelle"],
          e["date_depot"], e["modificative"], e["qualite_declarant"],
          e["organe_libelle"], e["type_mandat"], e["nb_lignes"])
         for e in donnees["entetes"]])

    conn.executemany(
        "INSERT INTO hatvp_decl_rubriques (declaration_uuid, rubrique,"
        " rubrique_ordre, neant, nb_lignes) VALUES (?, ?, ?, ?, ?)",
        donnees["rubriques"])

    marques = ", ".join("?" for _ in _COLONNES_LIGNE)
    for ligne in donnees["lignes"]:
        curseur = conn.execute(
            f"INSERT INTO hatvp_decl_lignes ({', '.join(_COLONNES_LIGNE)})"
            f" VALUES ({marques})",
            tuple(ligne[c] for c in _COLONNES_LIGNE))
        if ligne["montants"]:
            conn.executemany(
                "INSERT INTO hatvp_decl_montants (ligne_id, annee, montant, brut_net)"
                " VALUES (?, ?, ?, ?)",
                [(curseur.lastrowid, annee, montant, brut_net)
                 for annee, montant, brut_net in ligne["montants"]])


def controler_absence_patrimoine(conn) -> None:
    """Contrôle de sortie : aucune rubrique hors liste blanche en base.

    POURQUOI un contrôle APRÈS écriture, alors que deux barrières filtrent
    déjà en amont : les barrières protègent le chemin nominal, celui-ci
    protège du chemin qu'on n'a pas prévu (écriture manuelle, migration,
    reprise partielle). Il échoue franc, et depuis le 26/08/2026 son échec est
    sans dommage : il est posé APRÈS `ecrire()`, mais `ecrire()` n'a rien
    validé, si bien que le `rollback()` de `executer()` rend la base à son état
    antérieur — le cycle précédent reste servi. Ce fut faux pendant tout le
    temps où `ecrire()` passait par `executescript` : le contrôle laissait
    alors les tables vides. Conforme à l'intention dans les deux cas (mieux
    vaut pas de données du tout qu'une ligne patrimoniale publiée sous le nom
    de quelqu'un), mais un exploitant qui diagnostique a besoin du vrai.
    """
    autorisees = {r.cle for r in RUBRIQUES.values()}
    trouvees = {r["rubrique"] for r in
                conn.execute("SELECT DISTINCT rubrique FROM hatvp_decl_lignes")}
    intruses = trouvees - autorisees
    if intruses:
        raise ValueError(
            f"rubriques hors liste blanche en base : {sorted(intruses)} — "
            "abandon (art. LO 135-2 du code électoral)")
    trouvees_rub = {r["rubrique"] for r in
                    conn.execute("SELECT DISTINCT rubrique FROM hatvp_decl_rubriques")}
    intruses_rub = trouvees_rub - autorisees
    if intruses_rub:
        raise ValueError(
            f"rubriques hors liste blanche dans hatvp_decl_rubriques : "
            f"{sorted(intruses_rub)} — abandon")


# ---------------------------------------------------------------------------
# Fraîcheur
# ---------------------------------------------------------------------------


def date_derniere_modification(session, url: str) -> str | None:
    """Date (ISO) du Last-Modified HTTP, via HEAD puis GET en secours.

    POURQUOI le Last-Modified et non la date interne la plus récente (que le
    projet préfère partout ailleurs) : la donnée la plus fraîche du fichier
    est `max(dateDepot)`, soit le 28/07/2026 pour un fichier régénéré le
    14/08/2026 — l'écart mesure le délai de PUBLICATION de la HATVP (dépôt,
    instruction, mise en ligne), pas la fraîcheur du fichier. S'en servir
    ferait passer pour « en retard » une source parfaitement à jour. Le
    Last-Modified, lui, est à une seconde de celui de liste.csv : les deux
    fichiers sortent de la même génération hebdomadaire. `max(dateDepot)` est
    consigné dans les notes de meta_sources, pour que ce délai reste visible.
    """
    try:
        r = session.head(url, timeout=60, allow_redirects=True)
        lm = r.headers.get("Last-Modified")
        if not lm:
            with session.get(url, stream=True, timeout=60) as g:
                lm = g.headers.get("Last-Modified")
        return parsedate_to_datetime(lm).date().isoformat() if lm else None
    except (ValueError, TypeError, OSError):
        return None


# ---------------------------------------------------------------------------
# Garde-fou de rattachement : ce qu'aucun seuil de volume ne peut voir
# ---------------------------------------------------------------------------

# Variable d'environnement d'acquittement, en dernier recours. Elle ne
# « desserre » aucun seuil : elle nomme, un par un, les uuid qu'un exploitant a
# ouverts et dont il assume la perte. Ce qui est acquitté est donc TRACÉ dans la
# commande, pas effacé du code.
#
# ⚠️ POURQUOI CETTE ISSUE EXISTE — l'asymétrie du coût, à connaître avant de
# toucher au garde-fou. `hatvp_declarations` est le 10ᵉ des 31 pipelines de la
# variable `PIPELINES` du Makefile ; la règle `ingest-%` n'avale aucune erreur
# et `ft-deploy` n'appelle pas `make -k`. Une levée arrête donc les 21 pipelines
# en aval ET tout le rafraîchissement du site, chaque nuit, jusqu'à intervention
# humaine — pour protéger l'exactitude de quelques fiches d'élus. Le choix
# assumé est celui de la maison (« l'ingestion est tout-ou-rien »), mais il
# fallait une sortie utilisable en une commande plutôt qu'un correctif de code
# à écrire dans l'urgence.
ENV_PERTES_ACQUITTEES = "FT_P15_PERTES_ACQUITTEES"


def pertes_de_rattachement(
    precedents: dict[str, str], uuids_vus: set[str],
    rattachements: dict[str, str], fiches: set[str],
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Les déclarations qui étaient rattachées, le sont TOUJOURS publiées, et ne le sont plus.

    Rend DEUX listes : celles qui font échouer le cycle, et celles qui sont
    seulement journalisées parce que leur élu a perdu sa fiche. La seconde
    n'est pas un détail de présentation : sans elle, la restriction aux élus
    qui portent encore une fiche rouvrirait un chemin MUET, celui-là même que
    ce garde-fou existe pour fermer — un pipeline amont qui laisse `elus`
    amputé sans faire échouer le cycle détacherait des centaines de
    déclarations sans un mot (le plancher de 1 000 rattachées ne mord pas à
    600 fiches, et la rupture de `ft-fraicheur` n'alerte que le lendemain).

    POURQUOI CE CONTRÔLE N'EST PAS UN DELTA DE VOLUME, ET NE PEUT PAS L'ÊTRE.
    Les deux événements suivants sont, en volume, LE MÊME ÉVÉNEMENT :

      · 21/08/2026, retrait amont LÉGITIME. La HATVP retire 3 déclarations du
        fichier (6 611 → 6 608). Effet mesuré dans le journal de P15 :
        2 263 → 2 261 rattachées (**−0,088 %**), 27 731 → 27 711 lignes
        (−0,072 %). Rien à signaler : la donnée n'existe plus en amont.
      · Un homonyme de la même année entre dans `elus` et fait renoncer le
        garde-fou n° 3 du repli (voir `construire_index_souple`). Mesuré le
        26/08/2026 en injectant une fiche jumelle de Martin/Élisa dans l'index :
        2 332 → 2 330 rattachées (**−0,086 %**), 28 586 → 28 578 lignes
        (−0,03 %). Deux déclarations toujours publiées disparaissent des
        fiches du site.

    Un seuil en pourcentage ne peut pas séparer −0,088 % de −0,086 %. Et les
    quatre contrôles qui existaient étaient tous aveugles à ce cas, vérifié :
    plancher `rattachees ≥ 1 000` → 2 330 passe ; proportion du repli ≤ 15 %
    → 69/2 330 = 3,0 % passe ; `declarations_lues ≥ 5 000` → 6 608 passe ; et
    la rupture de volume de `ft-fraicheur` (S15, seuil −20 % sur `lignes`,
    `fraicheur.conf` l. 87) → −0,03 % passe. La perte serait donc MUETTE de
    bout en bout, ce que la docstring de `construire_index_souple` annonçait
    déjà : « leur déclaration se détache SANS BRUIT ».

    L'observable qui sépare les deux n'est pas l'AMPLEUR, c'est la PRÉSENCE EN
    AMONT : dans le premier cas la déclaration a quitté `declarations.xml`,
    dans le second elle y est toujours. D'où la règle, sans seuil ni tolérance :

        perte = uuid déjà rattaché  ∩  uuid encore publié  −  uuid rattaché

    restreinte aux élus qui PORTENT ENCORE UNE FICHE (`fiches`) : un
    parlementaire dont le mandat s'achève sort de `elus`, ses déclarations
    cessent d'être rattachables, et ce n'est pas une régression.

    Ce que ce contrôle laisse VOLONTAIREMENT passer, pour ne pas hurler à tort :
      · la déclaration retirée de la source (cas 1 ci-dessus) ;
      · l'élu qui perd sa fiche (fin de mandat) — chemin `hors_fiche`, qui
        n'avertit que et laisse le cycle réussir. 🛑 Le prix de ce silence :
        parce que le cycle réussit, `ecrire()` réécrit `hatvp_decl_interets`
        sans ces uuid, qui quittent alors `precedents` POUR TOUJOURS. C'est le
        même effacement que l'acquittement, mais SANS DÉCISION HUMAINE : si
        l'élu retrouve sa fiche pendant que la déclaration reste détachée, plus
        rien ne le dira jamais. Voir le bloc `if hors_fiche:` de `executer` ;
      · la déclaration qui CHANGE d'élu sans disparaître — c'est exactement ce
        que produira la fusion des fiches `rne-*` en double : mesuré le
        26/08/2026 sur une fusion simulée des six jumelles (FAVENNEC, VAGINAY,
        XOWIE, MARTIN, LUCAS, K/BIDI), **14 déclarations déplacées, 0 perdue**,
        total inchangé à 2 332. Ce garde-fou ne bloquera donc pas cette fusion.

    DEUX LIMITES CONNUES, mesurées, à ne pas confondre avec des oublis :

      · `uuids_vus` ne contient que les déclarations acceptées par la barrière
        de type (DI/DIA). Une déclaration re-typée en amont serait lue comme un
        retrait, donc tolérée en silence.
      · **Ce contrôle raisonne sur des en-têtes, pas sur du contenu.** Les
        2 332 déclarations peuvent rester rattachées pendant que leurs lignes
        s'effondrent, et le pipeline n'a AUCUN plancher sur `lignes`. Mesuré le
        26/08/2026 sur la base servie : perdre toute la rubrique
        `participation_financiere` — celle qui porte `evaluation`,
        `capital_detenu`, `nombre_parts` — coûterait 3 726 lignes sur 28 586,
        soit **−13,0 %**, sous le seuil de rupture de −20 % de la supervision ;
        les quatre plus petites rubriques réunies font 5 005 lignes, **−17,5 %**,
        encore dessous. Le cas le plus probable est le renommage d'une balise
        amont hors de la liste blanche `RUBRIQUES` : il est fermé par
        `rubriques_effondrees` ci-dessous. Une érosion PARTIELLE des lignes,
        elle, reste non couverte.
    """
    detachees = sorted(
        (uuid, elu_id)
        for uuid, elu_id in precedents.items()
        if uuid in uuids_vus and uuid not in rattachements
    )
    perdues = [(u, e) for u, e in detachees if e in fiches]
    hors_fiche = [(u, e) for u, e in detachees if e not in fiches]
    return perdues, hors_fiche


def elus_avec_fiche(conn) -> set[str]:
    """Les élus qui PORTENT une fiche publiée. Rien d'autre — surtout pas
    « ceux que P15 sait apparier ».

    🛑 La nuance a été une faute, corrigée le 26/08/2026 après mesure. Le
    vivier avait d'abord été tiré de `index_souple`, qui écarte tout élu dont
    `date_naissance` ne fait pas exactement dix caractères — or
    `ingest_parlement.upsert_elu` réécrit cette colonne à CHAQUE cycle et ses
    deux extracteurs amont peuvent rendre `None`. Un cycle amont abîmé aurait
    donc rangé des centaines de déclarations dans la liste « l'élu a perdu sa
    fiche », qui ne fait qu'avertir. Rejoué le 26/08/2026 sur copie de la base
    servie, 200 dates de naissance mises à NULL, fiches conservées :
    **419 déclarations et 4 409 lignes (−15,4 %) disparaissaient dans un cycle
    en SUCCÈS**, sous un message qui parlait de « fin de mandat » — et aucun
    autre contrôle ne mordait (1 913 rattachées contre un plancher de 1 000,
    repli à 3,3 %, aucune rubrique à zéro, et −15,4 % reste sous le seuil de
    rupture de −20 % de la supervision). Avec le vivier corrigé, le même dégât
    rend 419 pertes et fait échouer le cycle. L'écart entre les deux viviers est
    nul aujourd'hui (1 055 = 1 055, mesuré) : c'était un trou latent, pas
    ouvert — et c'est exactement le régime d'incident que ce garde-fou couvre.

    La requête est celle des deux index d'appariement, sans AUCUN de leurs
    filtres : c'est la population que le site publie.
    """
    marques = ", ".join("?" for _ in TYPES_FICHE)
    return {r["id"] for r in conn.execute(
        f"""SELECT DISTINCT e.id
            FROM elus e, json_each(e.mandats) je
            WHERE json_extract(je.value, '$.type') IN ({marques})""",
        TYPES_FICHE)}


def rubriques_effondrees(precedentes: dict[str, int],
                         nouvelles: dict[str, int]) -> list[tuple[str, int]]:
    """Les rubriques qui portaient des lignes et n'en portent plus AUCUNE.

    Symétrique de `controler_absence_patrimoine`, qui vérifie qu'aucune
    rubrique INTRUSE n'entre : celui-ci vérifie qu'aucune rubrique ATTENDUE ne
    sort. Le trou qu'il ferme est réel et chiffré (voir
    `pertes_de_rattachement`) : la liste blanche `RUBRIQUES` est indexée sur des
    NOMS DE BALISE amont (`participationFinanciereDto`…) ; qu'une seule soit
    renommée et la rubrique disparaît entièrement, sans qu'un seul uuid bouge
    et sans qu'aucun seuil de volume ne morde.

    Pas de seuil ici non plus : **zéro** est sans ambiguïté. Les sept rubriques
    portent aujourd'hui de 256 (`consultant`) à 13 552 lignes (`dirigeant`) sur
    2 332 déclarations ; qu'une d'elles tombe exactement à 0 n'est pas une
    variation, c'est une rupture de lecture. Une rubrique qui n'avait déjà
    aucune ligne au cycle précédent n'est pas signalée.
    """
    return sorted((rubrique, avant) for rubrique, avant in precedentes.items()
                  if avant > 0 and nouvelles.get(rubrique, 0) == 0)


def lignes_par_rubrique_precedentes(conn) -> dict[str, int]:
    """`{rubrique: nombre de lignes}` du cycle précédent, `{}` s'il n'y en a pas.

    Même angle mort que `rattachements_precedents`, et il faut le dire ici
    aussi : les DEUX contrôles sont sans mémoire quand leur table est présente
    mais vide, et le silence de l'un ne doit pas passer pour un contrôle qui a
    regardé. Depuis que `ecrire()` est atomique, un cycle mort en cours
    d'écriture n'est plus une cause possible de cet état.
    """
    existe = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='hatvp_decl_lignes'"
    ).fetchone()
    if not existe:
        return {}
    compte = {r[0]: r[1] for r in conn.execute(
        "SELECT rubrique, count(*) FROM hatvp_decl_lignes GROUP BY rubrique")}
    if not compte:
        log.warning(
            "hatvp_decl_lignes existe mais est VIDE : le contrôle de rubrique "
            "effondrée n'a aucune mémoire pour ce cycle-ci et ne verra rien. "
            "L'écriture étant atomique, un cycle en échec n'est plus une cause "
            "possible : chercher une restauration partielle ou une écriture "
            "manuelle.")
    return compte


def _libelle_elu(conn, elu_id: str) -> str:
    """« NOM Prénom » d'un élu : le message d'échec doit être lisible tel quel.

    Appelée au plus 8 fois (les huit premiers élus touchés), et seulement sur
    le chemin d'échec — jamais dans le cycle nominal.
    """
    ligne = conn.execute(
        "SELECT nom, prenom FROM elus WHERE id = ?", (elu_id,)).fetchone()
    if ligne is None:
        return "absent de elus"
    return " ".join(str(c) for c in ligne if c) or "sans nom"


def rattachements_precedents(conn) -> dict[str, str]:
    """`{uuid: elu_id}` du cycle précédent, `{}` s'il n'y en a pas.

    Lisible tant que `ecrire()` n'a pas tourné : c'est lui, et lui seul, qui
    DROPpe les quatre tables (`SCHEMA_P15`). Sur une base neuve — celle de la
    CI à chaque fois que `pipelines/*.py` change — la table est absente et le
    contrôle n'a rien à comparer : il se tait, il ne devine pas.

    🛑 « VIDE » N'EST PAS « ABSENTE », ET LA DIFFÉRENCE COMPTE TOUJOURS. Une
    table présente et vide fait taire ce garde-fou exactement comme une base
    neuve, alors qu'elle ne dit pas du tout la même chose. Ce cas avait une
    cause structurelle jusqu'au 26/08/2026 : `ecrire()` passait par
    `executescript`, qui valide implicitement, et un échec entre le `DROP` et
    le `conn.commit()` laissait les quatre tables existantes et vides sur
    disque (mesuré : une connexion neuve relisait 0 déclaration). La mémoire de
    ce garde-fou disparaissait donc **au lendemain d'un incident**, au moment
    où elle sert le plus. Cette cause-là est fermée — l'écriture est atomique,
    un cycle qui meurt laisse le cycle précédent intact — mais l'avertissement
    reste : « vide » peut encore venir d'ailleurs (restauration partielle,
    écriture manuelle, migration), et ce silence-là ne doit pas passer pour un
    contrôle qui a regardé.
    """
    existe = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='hatvp_decl_interets'"
    ).fetchone()
    if not existe:
        return {}
    precedents = {r[0]: r[1] for r in
                  conn.execute("SELECT uuid, elu_id FROM hatvp_decl_interets")}
    if not precedents:
        log.warning(
            "hatvp_decl_interets existe mais est VIDE : le contrôle de perte "
            "de rattachement n'a aucune mémoire pour ce cycle-ci et ne verra "
            "rien ; il redeviendra opérant au cycle suivant. L'écriture étant "
            "atomique, un cycle en échec n'est plus une cause possible : "
            "chercher une restauration partielle ou une écriture manuelle.")
    return precedents


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def executer(chemin_db=None, max_age_heures: float | None = 6.0) -> dict:
    """Pipeline complet : télécharge, parse en flux, apparie, écrit. Stats."""
    session = session_http()
    chemin = telecharger(URL_DECLARATIONS, REP_RAW / "declarations.xml",
                         max_age_heures=max_age_heures, session=session)
    date_donnees = date_derniere_modification(session, URL_DECLARATIONS)
    if not date_donnees:
        log.warning("declarations.xml : Last-Modified indisponible, "
                    "date d'ingestion utilisée")
        date_donnees = date.today().isoformat()

    conn = db.init_db(chemin=chemin_db)
    try:
        index_elus = construire_index_elus(conn)
        if len(index_elus) < 500:
            raise ValueError(
                f"appariement impossible : {len(index_elus)} élus avec fiche et date "
                "de naissance (≥ 500 attendus) — P7/P9 ont-ils tourné ? Abandon")
        index_souple = construire_index_souple(conn)
        # Lu AVANT `ecrire()`, seul endroit du fichier qui DROPpe les tables.
        precedents = rattachements_precedents(conn)
        lignes_avant = lignes_par_rubrique_precedentes(conn)
        donnees = parcourir(chemin, index_elus, index_souple)
        stats = donnees["stats"]

        # Garde-fous de plausibilité : mieux vaut ne rien écrire qu'écrire une
        # base amputée qui ferait dire au site « aucun intérêt déclaré ».
        if stats["declarations_lues"] < 5_000:
            raise ValueError(f"declarations.xml : {stats['declarations_lues']} "
                             "déclarations lues (≥ 5 000 attendues) — source suspecte")
        # Le repli ne doit rester qu'un APPOINT. S'il devient la voie
        # principale, ce n'est pas qu'il travaille bien : c'est que la clé
        # exacte est tombée — et le plancher ci-dessous ne le verrait pas.
        # Mesuré le 26/08/2026 : 71 rattachements par repli sur 2 332, soit
        # 3,0 %. Contre-épreuve, clé exacte anéantie : le repli seul en
        # rattache 2 308, très au-dessus du plancher de 1 000 — la panne
        # serait donc MUETTE sans ce garde-fou.
        if stats["rattachees"] and \
                stats["rattachees_par_repli"] > 0.15 * stats["rattachees"]:
            raise ValueError(
                f"appariement suspect : {stats['rattachees_par_repli']} déclarations "
                f"sur {stats['rattachees']} rattachées par le repli d'orthographe "
                f"(> 15 %) — la clé exacte est-elle tombée ? Abandon")
        if stats["rattachees"] < 1_000:
            raise ValueError(f"appariement anormal : {stats['rattachees']} déclarations "
                             "rattachées (≥ 1 000 attendues)")
        # ORDRE VOULU — la rupture de lecture d'abord. Elle n'est JAMAIS
        # acquittable (c'est un correctif de pipeline), alors qu'une perte de
        # rattachement l'est. Dans l'ordre inverse, un cycle qui cumule les deux
        # ne montrerait que la perte ; l'exploitant acquitterait des uuid — donc
        # abandonnerait des déclarations, irréversiblement, puisqu'un uuid
        # acquitté quitte `precedents` au cycle suivant — pour découvrir ensuite
        # que le vrai défaut était ailleurs. Le message bénin masquerait le grave.
        lignes_apres: Counter = Counter(l["rubrique"] for l in donnees["lignes"])
        effondrees = rubriques_effondrees(lignes_avant, lignes_apres)
        if effondrees:
            raise ValueError(
                "rubrique effondrée : " + ", ".join(
                    f"{rubrique} passe de {avant} lignes à 0"
                    for rubrique, avant in effondrees) +
                " — une balise amont a-t-elle été renommée hors de RUBRIQUES ? "
                "Base NON modifiée.")

        # Le seul contrôle du lot qui ne soit ni un plancher ni une proportion :
        # il compare au cycle précédent, déclaration par déclaration. Voir
        # `pertes_de_rattachement` pour la mesure qui rend les seuils inopérants.
        rattachements = {e["uuid"]: e["elu_id"] for e in donnees["entetes"]}
        fiches = elus_avec_fiche(conn)
        perdues, hors_fiche = pertes_de_rattachement(
            precedents, donnees["uuids_vus"], rattachements, fiches)
        stats["pertes_hors_fiche"] = len(hors_fiche)
        if hors_fiche:
            # L'élu ne figure plus du tout parmi les fiches publiées : fin de
            # mandat, cas légitime et fréquent, donc pas un échec — mais jamais
            # muet. Les uuid sont nommés, pas seulement les élus : sans eux
            # l'anomalie n'est pas instruisible depuis le journal.
            #
            # 🛑 CE CHEMIN EFFACE LA MÉMOIRE DU GARDE-FOU, POUR TOUJOURS, ET
            # TOUT SEUL. Le cycle réussit, donc `ecrire()` tourne — et il
            # DROPpe `hatvp_decl_interets` pour la réécrire depuis les seuls
            # `entetes`. Un uuid rangé ici n'y est pas : il quitte `precedents`
            # et ne sera plus jamais comparé à rien. Si l'élu retrouve sa fiche
            # — P7/P9 réparé, renouvellement du Sénat du 27/09/2026, fusion des
            # doublons `rne-*` — pendant que sa déclaration reste détachée, le
            # garde-fou restera MUET sur elle, définitivement.
            #
            # C'est exactement l'effet de `FT_P15_PERTES_ACQUITTEES`, à ceci
            # près que l'acquittement exige qu'un exploitant nomme chaque uuid,
            # là où ce chemin-ci se déclenche sans que personne n'ait rien
            # décidé. Des trois voies qui font oublier un uuid, c'est la seule
            # automatique — d'où cet avertissement, seule trace qu'il en reste.
            log.warning(
                "%d déclaration(s) toujours publiées se détachent de %d élu(s) "
                "qui ne figurent plus parmi les fiches publiées (fin de mandat "
                "attendue) — SANS RETOUR : ces uuid quittent la mémoire du "
                "garde-fou au commit de ce cycle et n'y reviendront pas — %s",
                len(hors_fiche), len({e for _, e in hors_fiche}),
                "; ".join(f"{u} ({e})" for u, e in hors_fiche))
        acquittees = {u.strip() for u in
                      os.environ.get(ENV_PERTES_ACQUITTEES, "").split(",") if u.strip()}
        stats["pertes_acquittees"] = sum(1 for u, _ in perdues if u in acquittees)
        perdues = [(u, e) for u, e in perdues if u not in acquittees]
        if perdues:
            elus_touches = sorted({e for _, e in perdues})
            # La liste COMPLÈTE part au journal avant la levée : le message
            # d'exception tronque à huit, et l'acquittement exige de nommer
            # chaque uuid. Sans cette ligne, au-delà de huit pertes l'issue de
            # secours serait inutilisable — les uuid manquants ne seraient
            # écrits nulle part.
            log.error("perte de rattachement, liste complète (%d) : %s",
                      len(perdues), " ".join(u for u, _ in perdues))
            noms = ", ".join(f"{e} ({_libelle_elu(conn, e)})"
                             for e in elus_touches[:8])
            raise ValueError(
                f"perte de rattachement : {len(perdues)} déclaration(s) toujours "
                f"publiées par la HATVP ne sont plus rattachées, sur "
                f"{len(elus_touches)} élu(s) qui portent pourtant encore une fiche "
                f"— {noms}{' …' if len(elus_touches) > 8 else ''}. "
                f"uuid : {', '.join(u for u, _ in perdues[:8])}"
                f"{' …' if len(perdues) > 8 else ''}. Base NON modifiée. "
                f"Cause probable : l'état civil de ces élus a changé dans `elus`, "
                f"ou un homonyme de la même année y est entré et fait renoncer le "
                f"repli. Après examen, acquitter uuid par uuid avec "
                f"{ENV_PERTES_ACQUITTEES}=<uuid,uuid> — la liste complète est "
                f"dans le journal, ligne « perte de rattachement, liste "
                f"complète ».")

        ecrire(conn, donnees)
        controler_absence_patrimoine(conn)
        conn.commit()

        taux = 100.0 * stats["elus_apparies"] / max(len(index_elus), 1)
        db.upsert_meta(
            conn, source_id=ID_SOURCE, nom=NOM_SOURCE, url=URL_DECLARATIONS,
            licence=LICENCE, frequence=FREQUENCE, date_donnees=date_donnees,
            lignes=stats["lignes"],
            notes=(
                f"{stats['declarations_lues']} déclarations lues, "
                f"{stats['refus_type_declaration']} refusées par type (patrimoine et "
                f"types non retenus), {stats['refus_balise_patrimoine']} blocs "
                f"patrimoniaux refusés par nom de balise ; {stats['rattachees']} "
                f"déclarations d'intérêts rattachées à {stats['elus_apparies']} élus "
                f"sur {len(index_elus)} fiches ({taux:.1f} %), {stats['lignes']} lignes "
                f"dont {stats['lignes_avec_montant']} avec au moins un montant annuel "
                f"daté ({stats['montants']} montants). Intérêts SEULEMENT : aucun bloc "
                f"patrimonial (art. LO 135-2 du code électoral), ni activité du "
                f"conjoint, ni collaborateurs. Texte source non normalisé : affichage "
                f"verbatim, aucun agrégat. Dépôt le plus récent parmi les "
                f"déclarations rattachées : "
                f"{max((e['date_depot'] or '') for e in donnees['entetes']) or '—'} "
                f"(le délai de publication de la HATVP explique l'écart avec la date "
                f"de régénération du fichier, seule retenue comme date_donnees)."
            ))
        log.info(
            "P15 terminé : %d déclarations lues, %d refusées par type, %d blocs "
            "patrimoniaux refusés par balise ; %d rattachées à %d élus (%.1f %%), "
            "dont %d par le repli d'orthographe ; %d lignes, %d montants, "
            "%d rubriques « néant » ; %d perte(s) de rattachement acquittée(s), "
            "%d détachement(s) d'élus sans fiche",
            stats["declarations_lues"], stats["refus_type_declaration"],
            stats["refus_balise_patrimoine"], stats["rattachees"],
            stats["elus_apparies"], taux, stats["rattachees_par_repli"],
            stats["lignes"], stats["montants"], stats["rubriques_neant"],
            stats["pertes_acquittees"], stats["pertes_hors_fiche"])
        stats["date_donnees"] = date_donnees
        stats["fiches"] = len(index_elus)
        return dict(stats)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def main() -> int:
    try:
        executer()
    except Exception:
        # Ce message a promis « aucune écriture partielle », a dû se dédire
        # quand la mesure a montré qu'`executescript` validait implicitement,
        # et peut le promettre de nouveau depuis le 26/08/2026 : ce qui tient
        # la promesse est le `BEGIN` de `ecrire()` et le test qui l'éprouve,
        # jamais cette phrase.
        log.exception(
            "P15 en échec. La base n'est PAS modifiée : les six contrôles posés "
            "avant l'écriture lèvent sans rien toucher, l'écriture elle-même "
            "est atomique, et le contrôle de sortie est annulé avec elle. Le "
            "cycle précédent reste servi, avec la mémoire des deux contrôles "
            "inter-cycles")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

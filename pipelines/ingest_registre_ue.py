"""P16 — Registre de transparence de l'Union européenne (S40).

Source : export XML intégral des ORGANISATIONS inscrites au registre de
transparence commun Parlement européen / Commission européenne
(`https://transparency-register.europa.eu/odplastorganisationxml_en`, ~115 Mo,
régénéré chaque jour). Licence : décision 2011/833/UE (« European Commission
reuse notice », `COM_REUSE` dans la réponse DCAT de data.europa.eu) —
réutilisation y compris commerciale avec mention de la source, sans clause de
partage à l'identique, donc compatible avec la Licence Ouverte 2.0 des
agrégats du site.

CE PIPELINE N'EST PAS LE PIPELINE LOBBYING (P8, S4, HATVP)
---------------------------------------------------------
Le registre de l'Union et le répertoire français des représentants d'intérêts
sont DEUX registres distincts, adossés à DEUX cadres juridiques distincts
(accord interinstitutionnel du 20/05/2021 pour l'un, loi « Sapin II » du
09/12/2016 pour l'autre), avec des périmètres d'inscription, des obligations
déclaratives et des unités de coût différentes. Rien de ce que ce pipeline
écrit ne doit être fusionné avec les tables `lobby_*`, ni comparé à elles :
- préfixe de tables `ue_registre_*`, jamais `lobby_*` ;
- aucune jointure n'est possible de toute façon : l'export UE ne porte NI
  SIREN NI numéro de TVA (77 balises inventoriées le 20/08/2026, aucune ne
  contient d'identifiant national d'entreprise) — c'est un constat de la
  donnée, pas une limite de ce code ;
- les montants sont des FOURCHETTES de coûts annuels de représentation
  d'intérêts déclarées au registre de l'Union ; ils ne mesurent pas la même
  chose que les fourchettes de dépenses déclarées à la HATVP et ne doivent
  jamais être additionnés ni rapportés les uns aux autres.

PÉRIMÈTRE VOLONTAIREMENT MINIMAL
--------------------------------
- ORGANISATIONS seulement. Le second export du registre — les personnes
  physiques accréditées auprès du Parlement européen — n'est PAS téléchargé,
  n'est PAS ingéré, et ne doit pas l'être : ce sont des données personnelles
  sans utilité pour le propos du site.
- Les inscrits de la catégorie « Self-employed individuals » (travailleurs
  indépendants, donc des personnes physiques) sont comptés dans les agrégats
  mais EXCLUS de la table nominative `ue_registre_organisations`.
- Le champ `goals` (description libre des objectifs, 630 octets en moyenne,
  soit ~11 Mo à lui seul) n'est pas ingéré : il ferait tripler le poids en
  base pour un texte promotionnel rédigé par l'inscrit.

Tables écrites (remplacement complet, idempotent) :
- ue_registre_organisations : une ligne par organisation inscrite (personnes
  morales uniquement) — identifiant du registre, dénomination, acronyme,
  catégorie d'inscription, siège (ville, code postal, pays), dates
  d'inscription et de mise à jour, équivalents temps plein consacrés à la
  représentation d'intérêts, nombre d'accréditations au Parlement européen,
  exercice clos déclaré et sa fourchette de coûts. Le jeu de colonnes est
  volontairement serré : forme juridique, site web, bureau de liaison UE et
  niveaux d'intérêt déclarés ont été écartés après mesure (ils coûtaient
  2,1 Mo en base pour des champs qu'aucune restitution n'emploie ; le détail
  complet reste à un clic sur la fiche officielle de chaque organisation).
- ue_registre_agg_categories : catégorie d'inscription × nombre d'inscrits
  (total registre / siège en France).
- ue_registre_agg_pays : pays du siège × nombre d'inscrits, dont personnes
  physiques (colonne qui rend l'exclusion vérifiable ligne à ligne).
- ue_registre_agg_interets : domaine d'intérêt déclaré × nombre d'inscrits
  (total / siège en France).
- ue_registre_agg_couts : fourchette de coûts annuels × nombre d'inscrits
  (total / siège en France).
- meta_sources : source_id 'S40', fréquence quotidienne, `date_donnees` lue
  dans la balise `<exportDate>` du fichier lui-même.

Aucune alerte n'est produite : être inscrit à un registre de transparence
est une démarche de conformité, pas un manquement.

PARSEUR : POURQUOI IL NE PEUT PAS ÊTRE `ET.parse()`
---------------------------------------------------
1. L'export est déclaré `<?xml version='1.1' ...?>`. La bibliothèque standard
   (expat) refuse net une déclaration 1.1 (`XML_ERROR_XML_DECL`).
2. Il contient des références de caractères que XML 1.1 autorise et que
   XML 1.0 interdit — mesurées sur l'export du 19/08/2026 : `&#x2;` (×5),
   `&#xb;` (×2), `&#x1d;` (×1), toutes dans des champs de texte libre.
   Rebaptiser la déclaration en 1.0 sans les traiter déplace simplement
   l'échec (`reference to invalid character number`).
3. 115 Mo en DOM, c'est ~1,5 Go de mémoire résidente pour un `Element` par
   balise. La lecture se fait donc en flux (`XMLPullParser`), un
   `interestRepresentative` à la fois, chaque élément étant vidé après usage.

`flux_xml_tolerant()` répond aux trois : il réécrit la déclaration en 1.0,
retire les références de caractères de contrôle propres à XML 1.1, et rend le
tout par blocs — en gardant entre deux blocs une queue assez longue pour
qu'une référence à cheval sur la frontière ne passe jamais au travers.

Exécution : `python -m pipelines.ingest_registre_ue` (échec → exit ≠ 0).
Base : data/france.db, ou FT_DB_PATH pour les épreuves sur base jetable.
"""

from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterator

from pipelines import db
from pipelines.common import RAW_DIR, assainir_texte, obtenir_logger, telecharger

log = obtenir_logger("registre_ue")

ID_SOURCE = "S40"
NOM_SOURCE = "Registre de transparence de l'Union européenne — organisations"
URL_EXPORT = "https://transparency-register.europa.eu/odplastorganisationxml_en"
URL_CATALOGUE = "https://data.europa.eu/api/hub/search/datasets/transparency-register"
LICENCE = "Décision 2011/833/UE (réutilisation des documents de la Commission)"
FREQUENCE = "quotidienne"

DOSSIER_RAW = RAW_DIR / "registre_ue"
NOM_FICHIER = "organisations.xml"

# Catégorie d'inscription des travailleurs indépendants : des PERSONNES
# PHYSIQUES, exclues de toute restitution nominative (elles restent comptées
# dans les agrégats, où elles ne sont pas identifiables).
CATEGORIE_PERSONNES_PHYSIQUES = "Self-employed individuals"

# Pays du siège tel qu'écrit par le registre (libellés anglais en capitales).
PAYS_FRANCE = "FRANCE"

# Fiche publique d'une organisation sur le site du registre (motif d'URL
# vérifié HTTP 200 le 20/08/2026).
_MOTIF_FICHE = (
    "https://transparency-register.europa.eu/search-register-or-update/"
    "organisation-detail_en?organisationNumber={}"
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ue_registre_organisations (
    id                  TEXT PRIMARY KEY,   -- identificationCode du registre UE
    nom                 TEXT NOT NULL,
    nom_latin           TEXT,
    acronyme            TEXT,
    categorie           TEXT,
    siege_ville         TEXT,
    siege_code_postal   TEXT,
    siege_pays          TEXT,
    date_inscription    TEXT,
    date_maj            TEXT,
    etp                 REAL,               -- membersFTE : ETP consacrés
    accredites_pe       INTEGER,            -- nb d'accréditations au PE (compte seul)
    exercice_debut      TEXT,
    exercice_fin        TEXT,
    cout_libelle        TEXT,               -- fourchette rendue en euros
    cout_min            REAL,               -- borne native, NULL si non bornée
    cout_max            REAL
);
-- Un seul index, sur le pays du siège : c'est la seule sélection servie par
-- le site (le bloc /lobbying ne restitue nominativement que les inscrits à
-- siège en France). Un index sur la catégorie coûtait 0,9 Mo pour une
-- requête que l'agrégat `ue_registre_agg_categories` rend déjà.
CREATE INDEX IF NOT EXISTS idx_ue_registre_orgs_pays
    ON ue_registre_organisations(siege_pays);

CREATE TABLE IF NOT EXISTS ue_registre_agg_categories (
    categorie        TEXT PRIMARY KEY,
    nb_organisations INTEGER NOT NULL,
    nb_france        INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS ue_registre_agg_pays (
    pays                  TEXT PRIMARY KEY,
    nb_organisations      INTEGER NOT NULL,
    nb_personnes_physiques INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS ue_registre_agg_interets (
    domaine          TEXT PRIMARY KEY,
    nb_organisations INTEGER NOT NULL,
    nb_france        INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS ue_registre_agg_couts (
    fourchette       TEXT PRIMARY KEY,
    borne_min        REAL,
    borne_max        REAL,
    nb_organisations INTEGER NOT NULL,
    nb_france        INTEGER NOT NULL
);
"""

# ---------------------------------------------------------------------------
# Lecture tolérante du flux XML 1.1
# ---------------------------------------------------------------------------

# Références de caractères LÉGALES EN XML 1.1, INTERDITES EN XML 1.0 : les
# contrôles C0 hors tabulation (#x9), saut de ligne (#xA) et retour chariot
# (#xD). Le motif couvre les formes hexadécimale et décimale, avec zéros de
# tête, et laisse volontairement passer #x9/#xA/#xD, légaux partout.
_REFS_CONTROLE_XML11 = re.compile(
    rb"&#(?:"
    rb"[xX]0{0,6}(?:[0-8bBcCeEfF]|1[0-9a-fA-F])"
    rb"|0{0,6}(?:[0-8]|1[124-9]|2[0-9]|3[01])"
    rb");"
)

# Fenêtre de sécurité en fin de bloc. Une référence reconnue par le motif
# ci-dessus fait au plus 12 octets (« &# » + « x » + 6 zéros + 2 chiffres +
# « ; ») ; on ne coupe donc jamais un bloc à moins de 32 octets d'une
# esperluette encore sans point-virgule.
_QUEUE_OCTETS = 32

_DECLARATION = re.compile(rb"""(<\?xml[^>]*?version\s*=\s*["'])1\.1(["'])""")


def normaliser_declaration(entete: bytes) -> bytes:
    """Réécrit `version='1.1'` en `version='1.0'` dans la déclaration XML.

    POURQUOI : expat, donc `xml.etree`, refuse une déclaration 1.1 et échoue
    avant d'avoir lu le premier élément. Les seules différences 1.0/1.1 qui
    portent sur ce document sont les références de caractères de contrôle
    (traitées par `_REFS_CONTROLE_XML11`) et la normalisation de fins de
    ligne exotiques (absentes : ni NEL U+0085 ni contrôle brut dans l'export
    mesuré). Rebaptiser la déclaration ne dénature donc rien.

    Un document déjà déclaré en 1.0 est rendu inchangé.
    """
    return _DECLARATION.sub(rb"\g<1>1.0\g<2>", entete, count=1)


def _coupe_sure(tampon: bytes) -> int:
    """Indice où couper `tampon` sans scinder une référence de caractère.

    Le filtre s'applique bloc par bloc : une référence à cheval sur deux
    blocs ne serait reconnue dans aucun des deux et passerait au travers
    (`&#` d'un côté, `x2;` de l'autre), pour faire échouer le parseur des
    dizaines de méga-octets plus loin. On recule donc jusqu'à la dernière
    esperluette de la fenêtre de fin qui n'a pas encore reçu son
    point-virgule — au plus `_QUEUE_OCTETS` en arrière, l'empreinte mémoire
    reste donc bornée.
    """
    depart = max(0, len(tampon) - _QUEUE_OCTETS)
    ouverture = tampon.rfind(b"&", depart)
    if ouverture == -1 or b";" in tampon[ouverture:]:
        return len(tampon)
    return ouverture


def flux_xml_tolerant(
    chemin: Path, taille_bloc: int = 1 << 20, taille_entete: int = 256
) -> Iterator[bytes]:
    """Rend le fichier par blocs, lisibles par un parseur XML 1.0.

    Deux transformations, et deux seulement :
    1. la déclaration `version='1.1'` devient `version='1.0'` — d'où la
       lecture d'un en-tête d'un seul tenant, la déclaration ne pouvant pas
       être réécrite si elle est coupée entre deux blocs ;
    2. les références de caractères de contrôle propres à XML 1.1 sont
       retirées (elles n'apparaissent que dans du texte libre : URL coupées,
       descriptions collées depuis un traitement de texte).

    Aucun autre octet n'est touché : le texte utile reste fidèle à la source.
    """
    with open(chemin, "rb") as f:
        tampon = normaliser_declaration(f.read(taille_entete))
        while True:
            bloc = f.read(taille_bloc)
            if not bloc:
                yield _REFS_CONTROLE_XML11.sub(b"", tampon)
                return
            tampon += bloc
            coupe = _coupe_sure(tampon)
            tete, tampon = tampon[:coupe], tampon[coupe:]
            yield _REFS_CONTROLE_XML11.sub(b"", tete)


def _local(balise: str) -> str:
    """Nom local d'une balise, espace de noms éventuel retiré.

    L'export place `metaData` et `resultList` dans l'espace de noms vide
    (`xmlns=""`) alors que la racine en déclare un. Ce helper rend la lecture
    indifférente à un changement de ce réglage côté producteur.
    """
    return balise.rsplit("}", 1)[-1]


def lire_export(chemin: Path) -> Iterator[tuple[str, ET.Element]]:
    """Parcourt l'export en flux et rend `(nom_local, élément)` à chaque fin
    de `exportDate`, `numberOfIR` et `interestRepresentative`.

    L'appelant DOIT vider (`clear()`) les éléments `interestRepresentative`
    qu'il a fini d'exploiter : c'est ce qui maintient l'empreinte mémoire
    constante sur un fichier de 115 Mo.
    """
    parseur = ET.XMLPullParser(["end"])
    interessants = {"exportDate", "numberOfIR", "interestRepresentative"}
    for bloc in flux_xml_tolerant(chemin):
        parseur.feed(bloc)
        for _evenement, element in parseur.read_events():
            nom = _local(element.tag)
            if nom in interessants:
                yield nom, element
    parseur.close()


# ---------------------------------------------------------------------------
# Helpers purs (testés unitairement)
# ---------------------------------------------------------------------------


def date_iso(valeur: str | None) -> str | None:
    """'2026-08-19T20:00:00.069+00:00' → '2026-08-19'.

    Valeur absente ou non datée → None : jamais de date fabriquée.
    """
    if not valeur:
        return None
    jour = str(valeur).strip()[:10]
    return jour if re.fullmatch(r"\d{4}-\d{2}-\d{2}", jour) else None


def nombre(valeur: str | None) -> float | None:
    """Texte numérique natif → float, sinon None (jamais de 0 de remplissage)."""
    if valeur is None:
        return None
    texte = str(valeur).strip()
    if not texte:
        return None
    try:
        return float(texte)
    except ValueError:
        return None


def _euros(montant: float) -> str:
    """1250000.0 → '1 250 000 €' (espaces insécables étroites, comme l'UI)."""
    return f"{int(round(montant)):,}".replace(",", " ") + " €"


def libelle_fourchette(borne_min: float | None, borne_max: float | None) -> str | None:
    """Rend une fourchette de coûts native en euros, sans rien y ajouter.

    Le registre publie les bornes, pas un libellé : trois formes existent
    dans la donnée réelle et sont rendues telles quelles —
    `(None, 10000)` → « < 10 000 € » (la fourchette d'entrée est ouverte
    vers le bas), `(10000, 24999)` → « 10 000 € – 24 999 € »,
    `(10000000, None)` → « ≥ 10 000 000 € » (dernière fourchette, non
    bornée). Deux bornes absentes = rien n'a été déclaré → None, et surtout
    pas « 0 € ».
    """
    if borne_min is None and borne_max is None:
        return None
    if borne_min is None:
        return f"< {_euros(borne_max)}"  # type: ignore[arg-type]
    if borne_max is None:
        return f"≥ {_euros(borne_min)}"
    return f"{_euros(borne_min)} – {_euros(borne_max)}"


def url_fiche_ue(identifiant: str | None) -> str | None:
    """Fiche publique de l'organisation sur transparency-register.europa.eu."""
    if not identifiant or not str(identifiant).strip():
        return None
    return _MOTIF_FICHE.format(str(identifiant).strip())


def est_personne_physique(categorie: str | None) -> bool:
    """Vrai pour la catégorie des travailleurs indépendants (personnes
    physiques), exclue de toute restitution nominative."""
    return (categorie or "").strip() == CATEGORIE_PERSONNES_PHYSIQUES


# ---------------------------------------------------------------------------
# Extraction d'une organisation
# ---------------------------------------------------------------------------


def _texte(element: ET.Element, chemin: str) -> str | None:
    """Texte assaini d'un sous-élément (None si absent ou vide)."""
    return assainir_texte(element.findtext(chemin))


def extraire_organisation(element: ET.Element) -> dict:
    """Champs retenus d'un `<interestRepresentative>`.

    Rend un dict plat ; les champs non ingérés (goals, activités de
    communication, membres, sources de financement, intermédiaires…) sont
    ignorés ici — voir l'en-tête du module pour le pourquoi.
    """
    identifiant = _texte(element, "identificationCode")
    categorie = _texte(element, "registrationCategory")

    exercice = element.find("financialData/closedYear")
    cout_min = cout_max = None
    exercice_debut = exercice_fin = None
    if exercice is not None:
        exercice_debut = date_iso(exercice.findtext("startDate"))
        exercice_fin = date_iso(exercice.findtext("endDate"))
        couts = exercice.find("costs")
        if couts is not None:
            cout_min = nombre(couts.findtext("range/min"))
            cout_max = nombre(couts.findtext("range/max"))

    domaines = sorted(
        {
            texte
            for i in element.findall("interests/interest")
            if (texte := (assainir_texte(i.findtext("name")) or ""))
        }
    )

    accredites = nombre(element.findtext("EPAccreditedNumber"))

    return {
        "id": identifiant,
        "nom": _texte(element, "name/originalName"),
        "nom_latin": _texte(element, "name/nameInLatinAlphabet"),
        "acronyme": _texte(element, "acronym"),
        "categorie": categorie,
        "siege_ville": _texte(element, "headOffice/city"),
        "siege_code_postal": _texte(element, "headOffice/postCode"),
        "siege_pays": _texte(element, "headOffice/country"),
        "date_inscription": date_iso(element.findtext("registrationDate")),
        "date_maj": date_iso(element.findtext("lastUpdateDate")),
        "etp": nombre(element.findtext("members/membersFTE")),
        "accredites_pe": None if accredites is None else int(accredites),
        "exercice_debut": exercice_debut,
        "exercice_fin": exercice_fin,
        "cout_libelle": libelle_fourchette(cout_min, cout_max),
        "cout_min": cout_min,
        "cout_max": cout_max,
        # hors table : servent aux agrégats puis sont oubliés
        "_domaines": domaines,
    }


COLONNES_ORGANISATION = (
    "id", "nom", "nom_latin", "acronyme", "categorie",
    "siege_ville", "siege_code_postal", "siege_pays",
    "date_inscription", "date_maj", "etp", "accredites_pe",
    "exercice_debut", "exercice_fin", "cout_libelle", "cout_min", "cout_max",
)


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def construire(chemin: Path) -> dict:
    """Lit l'export en flux et construit toutes les lignes à écrire.

    Les AGRÉGATS portent sur la TOTALITÉ des inscrits (les travailleurs
    indépendants compris : un compte n'identifie personne), la table
    NOMINATIVE sur les seules personnes morales. L'écart est publié : la
    colonne `nb_personnes_physiques` de `ue_registre_agg_pays` le rend
    vérifiable pays par pays.
    """
    organisations: list[tuple] = []
    categories: dict[str, list[int]] = {}
    pays: dict[str, list[int]] = {}
    interets: dict[str, list[int]] = {}
    couts: dict[tuple[float | None, float | None], list[int]] = {}
    export_date = None
    nombre_annonce = None
    total = 0
    personnes_physiques = 0
    sans_identifiant = 0

    for nom_balise, element in lire_export(chemin):
        if nom_balise == "exportDate":
            export_date = date_iso(element.text)
            continue
        if nom_balise == "numberOfIR":
            nombre_annonce = int((element.text or "0").strip() or 0)
            continue

        organisation = extraire_organisation(element)
        element.clear()
        total += 1

        if not organisation["id"] or not organisation["nom"]:
            sans_identifiant += 1
            continue

        physique = est_personne_physique(organisation["categorie"])
        francaise = organisation["siege_pays"] == PAYS_FRANCE
        personnes_physiques += int(physique)

        cle_cat = organisation["categorie"] or "Catégorie non renseignée"
        compte = categories.setdefault(cle_cat, [0, 0])
        compte[0] += 1
        compte[1] += int(francaise)

        cle_pays = organisation["siege_pays"] or "Pays non renseigné"
        compte = pays.setdefault(cle_pays, [0, 0])
        compte[0] += 1
        compte[1] += int(physique)

        for domaine in organisation["_domaines"]:
            compte = interets.setdefault(domaine, [0, 0])
            compte[0] += 1
            compte[1] += int(francaise)

        if organisation["cout_libelle"]:
            cle_cout = (organisation["cout_min"], organisation["cout_max"])
            compte = couts.setdefault(cle_cout, [0, 0])
            compte[0] += 1
            compte[1] += int(francaise)

        if not physique:
            organisations.append(
                tuple(organisation[colonne] for colonne in COLONNES_ORGANISATION)
            )

    agg_categories = sorted(
        ((c, n, nf) for c, (n, nf) in categories.items()),
        key=lambda ligne: (-ligne[1], ligne[0]),
    )
    agg_pays = sorted(
        ((p, n, npp) for p, (n, npp) in pays.items()),
        key=lambda ligne: (-ligne[1], ligne[0]),
    )
    agg_interets = sorted(
        ((d, n, nf) for d, (n, nf) in interets.items()),
        key=lambda ligne: (-ligne[1], ligne[0]),
    )
    agg_couts = sorted(
        (
            (libelle_fourchette(bmin, bmax), bmin, bmax, n, nf)
            for (bmin, bmax), (n, nf) in couts.items()
        ),
        # Tri par borne basse ; la fourchette d'entrée (pas de borne basse)
        # vient en premier, elle est bien la plus basse de toutes.
        key=lambda ligne: (ligne[1] is not None, ligne[1] or 0.0),
    )

    france = pays.get(PAYS_FRANCE, [0, 0])
    stats = {
        "organisations_total": total,
        "organisations_ecrites": len(organisations),
        "personnes_physiques_exclues": personnes_physiques,
        "france_total": france[0],
        "france_personnes_physiques": france[1],
        "france_nominatives": france[0] - france[1],
        "sans_identifiant": sans_identifiant,
        "nombre_annonce": nombre_annonce,
        "categories": len(agg_categories),
        "pays": len(agg_pays),
        "domaines": len(agg_interets),
        "fourchettes": len(agg_couts),
    }

    return {
        "organisations": organisations,
        "agg_categories": agg_categories,
        "agg_pays": agg_pays,
        "agg_interets": agg_interets,
        "agg_couts": agg_couts,
        "date_donnees": export_date,
        "stats": stats,
    }


# ---------------------------------------------------------------------------
# Écriture SQLite
# ---------------------------------------------------------------------------


def ecrire_db(conn, donnees: dict) -> None:
    """Écrit les cinq tables (remplacement complet) + meta_sources. Commit."""
    conn.executescript(_SCHEMA)
    stats = donnees["stats"]
    try:
        conn.execute("DELETE FROM ue_registre_organisations")
        conn.executemany(
            "INSERT INTO ue_registre_organisations VALUES ("
            + ",".join("?" * len(COLONNES_ORGANISATION))
            + ")",
            donnees["organisations"],
        )
        conn.execute("DELETE FROM ue_registre_agg_categories")
        conn.executemany(
            "INSERT INTO ue_registre_agg_categories VALUES (?,?,?)",
            donnees["agg_categories"],
        )
        conn.execute("DELETE FROM ue_registre_agg_pays")
        conn.executemany(
            "INSERT INTO ue_registre_agg_pays VALUES (?,?,?)", donnees["agg_pays"]
        )
        conn.execute("DELETE FROM ue_registre_agg_interets")
        conn.executemany(
            "INSERT INTO ue_registre_agg_interets VALUES (?,?,?)",
            donnees["agg_interets"],
        )
        conn.execute("DELETE FROM ue_registre_agg_couts")
        conn.executemany(
            "INSERT INTO ue_registre_agg_couts VALUES (?,?,?,?,?)",
            donnees["agg_couts"],
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    db.upsert_meta(
        conn,
        source_id=ID_SOURCE,
        nom=NOM_SOURCE,
        url=URL_EXPORT,
        licence=LICENCE,
        frequence=FREQUENCE,
        date_donnees=donnees["date_donnees"],
        lignes=stats["organisations_total"],
        notes=(
            "Registre de transparence commun Parlement européen / Commission "
            "européenne (accord interinstitutionnel du 20/05/2021). BLOC "
            "CLOISONNÉ : cadre juridique distinct de celui du répertoire "
            "français des représentants d'intérêts (S4, loi « Sapin II ») — "
            "les tables ue_registre_* ne doivent jamais être fusionnées avec "
            "les tables lobby_*, ni leurs montants comparés. Aucune clé de "
            "rapprochement n'existe de toute façon : l'export ne porte ni "
            "SIREN ni numéro de TVA. Organisations seulement : le second "
            "export du registre (personnes physiques accréditées auprès du "
            f"Parlement européen) n'est pas ingéré. {stats['organisations_total']} "
            f"inscrits, dont {stats['france_total']} à siège en France ; "
            f"{stats['personnes_physiques_exclues']} travailleurs indépendants "
            "(personnes physiques) comptés dans les agrégats mais exclus de la "
            "table nominative. Coûts annuels de représentation d'intérêts en "
            "fourchettes natives. Fraîcheur = balise <exportDate> du fichier, "
            "jamais la métadonnée DCAT du catalogue (périmée de deux ans au "
            "20/08/2026)."
        ),
    )


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def executer(chemin_db=None, max_age_heures: float | None = 6.0) -> dict:
    """Pipeline complet : télécharge, lit en flux, écrit. Retourne les stats."""
    chemin = telecharger(
        URL_EXPORT, DOSSIER_RAW / NOM_FICHIER, max_age_heures=max_age_heures
    )
    donnees = construire(chemin)
    stats = donnees["stats"]

    # Garde-fous : données réelles plausibles, sinon échec franc.
    if stats["organisations_total"] < 10_000:
        raise RuntimeError(
            f"volumétrie anormale : {stats['organisations_total']} organisations "
            f"(≥ 10 000 attendues)"
        )
    if not donnees["date_donnees"]:
        raise RuntimeError("balise <exportDate> absente ou illisible")
    annonce = stats["nombre_annonce"]
    if annonce and annonce != stats["organisations_total"]:
        # Le fichier annonce lui-même son compte : un écart signale une
        # troncature de téléchargement ou un changement de format.
        raise RuntimeError(
            f"le fichier annonce {annonce} inscrits, {stats['organisations_total']} "
            f"ont été lus — export incomplet ou format modifié"
        )
    if stats["sans_identifiant"]:
        log.warning(
            "%d inscrit(s) sans identifiant ou sans dénomination (ignorés)",
            stats["sans_identifiant"],
        )
    if stats["france_total"] < 500:
        raise RuntimeError(
            f"volumétrie anormale : {stats['france_total']} organisations à siège "
            f"en France (≥ 500 attendues)"
        )

    conn = db.init_db(chemin=chemin_db)
    try:
        ecrire_db(conn, donnees)
    finally:
        conn.close()

    log.info(
        "registre UE OK : %d inscrits (%d écrits, %d personnes physiques exclues), "
        "%d à siège en France dont %d nominatives, exportDate=%s",
        stats["organisations_total"], stats["organisations_ecrites"],
        stats["personnes_physiques_exclues"], stats["france_total"],
        stats["france_nominatives"], donnees["date_donnees"],
    )
    stats["date_donnees"] = donnees["date_donnees"]
    return stats


def main() -> int:
    try:
        executer()
    except Exception:
        log.exception("échec du pipeline registre_ue")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

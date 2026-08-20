"""Tests du pipeline P6 Journal officiel (pipelines/ingest_jorf.py).

Fixtures : XML réels extraits du tarball DILA JORFSIMPLE_20260819-003035.tar.gz
(JORF n°0192 du 19 août 2026) — aucune donnée fabriquée.
"""

import tarfile
from pathlib import Path

import pytest

from pipelines import db
from pipelines.ingest_jorf import (
    _SCHEMA,
    URL_JORFSIMPLE,
    construire_lien,
    est_nomination,
    ingerer_tarball,
    livraisons_nocturnes,
    ministere_du_chemin,
    parser_sommaire,
    parser_texte,
    reconstruire_agregats,
)

FIXTURES = Path(__file__).parent / "fixtures"
SOMMAIRE = FIXTURES / "jorf_sommaire_JORFCONT000054706874.xml"
TEXTE_NOMINATION = FIXTURES / "jorf_texte_nomination_JORFTEXT000054708776.xml"
TEXTE_ARRETE = FIXTURES / "jorf_texte_arrete_JORFTEXT000054708438.xml"

# Extrait VERBATIM de l'index Apache réel https://echanges.dila.gouv.fr/OPENDATA/JORFSIMPLE/
# (téléchargé le 19/08/2026) : PDF, Freemium, nocturne, correctif 13h53, soir.
INDEX_EXTRAIT = """<h1>Index of /OPENDATA/JORFSIMPLE</h1>
<pre><img src="/icons/blank.gif" alt="Icon "> <a href="?C=N;O=D">Name</a>                                                     <a href="?C=M;O=A">Last modified</a>      <a href="?C=S;O=A">Size</a>  <hr><img src="/icons/back.gif" alt="[PARENTDIR]"> <a href="/OPENDATA/">Parent Directory</a>                                                              -
<img src="/icons/layout.gif" alt="[   ]"> <a href="Avertissement_metadonnees_textes_entreprise_20181019.pdf">Avertissement_metadonnees_textes_entreprise_20181019.pdf</a> 2018-10-19 14:17  185K
<img src="/icons/compressed.gif" alt="[   ]"> <a href="Freemium_jorf_simple_20250713-140000.tar.gz">Freemium_jorf_simple_20250713-140000.tar.gz</a>              2025-07-13 10:14  1.0G
<img src="/icons/compressed.gif" alt="[   ]"> <a href="JORFSIMPLE_20260728-003542.tar.gz">JORFSIMPLE_20260728-003542.tar.gz</a>                        2026-07-28 00:36  328K
<img src="/icons/compressed.gif" alt="[   ]"> <a href="JORFSIMPLE_20260728-135307.tar.gz">JORFSIMPLE_20260728-135307.tar.gz</a>                        2026-07-28 13:53   16K
<img src="/icons/compressed.gif" alt="[   ]"> <a href="JORFSIMPLE_20260728-220005.tar.gz">JORFSIMPLE_20260728-220005.tar.gz</a>                        2026-07-28 22:08  4.5M
<img src="/icons/compressed.gif" alt="[   ]"> <a href="JORFSIMPLE_20260819-003035.tar.gz">JORFSIMPLE_20260819-003035.tar.gz</a>                        2026-08-19 00:30  392K
"""


# ---------------------------------------------------------------------------
# Index des livraisons
# ---------------------------------------------------------------------------


def test_livraisons_nocturnes_filtre_soir_et_correctifs():
    noms = livraisons_nocturnes(INDEX_EXTRAIT)
    # Seules les nocturnes (heure < 12) : ni soir (22h00), ni correctif 13h53,
    # ni Freemium, ni PDF.
    assert noms == [
        "JORFSIMPLE_20260728-003542.tar.gz",
        "JORFSIMPLE_20260819-003035.tar.gz",
    ]


# ---------------------------------------------------------------------------
# Sommaire (JORFCONT) : rubriques et nominations
# ---------------------------------------------------------------------------


def test_parser_sommaire_reel():
    som = parser_sommaire(SOMMAIRE.read_bytes())
    assert som.conteneur_id == "JORFCONT000054706874"
    assert som.num_jo == "0192"
    assert som.date_publi == "2026-08-19"
    assert som.titre == "JORF n°0192 du 19 août 2026"
    # Le JO n°0192 contient 83 textes au sommaire.
    assert len(som.rubriques) == 83
    # La loi « aide à mourir » est en rubrique LOIS (l'ombrelle niv 1 exclue).
    assert som.rubriques["JORFTEXT000054706877"] == ["LOIS"]
    # Le décret de nomination Cour des comptes passe par « Mesures nominatives ».
    chemin = som.rubriques["JORFTEXT000054708776"]
    assert chemin == [
        "Décrets, arrêtés, circulaires",
        "Mesures nominatives",
        "Premier ministre",
    ]


def test_detection_nomination_depuis_le_sommaire():
    som = parser_sommaire(SOMMAIRE.read_bytes())
    nominations = {t for t, c in som.rubriques.items() if est_nomination(c)}
    # Comptage réel du 19/08/2026 : 41 textes sous « Mesures nominatives ».
    assert len(nominations) == 41
    assert "JORFTEXT000054708776" in nominations
    # L'arrêté de délégation de signature n'en est pas une.
    assert "JORFTEXT000054708438" not in nominations
    # Ministère porté par le sommaire.
    assert (
        ministere_du_chemin(som.rubriques["JORFTEXT000054708776"])
        == "Premier ministre"
    )
    assert ministere_du_chemin(som.rubriques["JORFTEXT000054708438"]) is None


# ---------------------------------------------------------------------------
# Texte (JORFTEXT autocontenu)
# ---------------------------------------------------------------------------


def test_parser_texte_nomination_reel():
    t = parser_texte(TEXTE_NOMINATION.read_bytes())
    assert t is not None
    assert t["texte_id"] == "JORFTEXT000054708776"
    assert t["conteneur_id"] == "JORFCONT000054706874"
    assert t["nature"] == "DECRET"
    assert t["nor"] == "CPTP2618404D"
    assert t["num_jo"] == "0192"
    assert t["date_publi"] == "2026-08-19"
    assert t["date_texte"] == "2026-08-17"
    assert t["titre"] == "Décret du 17 août 2026 portant nomination (Cour des comptes)"
    assert t["ministere"] == "Premier ministre"
    assert t["num_sequence"] == 36
    # Ce décret n'a pas d'ID_ELI dans le XML source (cas fréquent : 57/83).
    assert t["id_eli"] is None


def test_parser_texte_arrete_reel():
    t = parser_texte(TEXTE_ARRETE.read_bytes())
    assert t is not None
    assert t["texte_id"] == "JORFTEXT000054708438"
    assert t["nature"] == "ARRETE"
    assert t["nor"] == "ARMM2621619A"
    assert t["ministere"] == "Ministère des armées et des anciens combattants"
    # L'ELI est fourni par la DILA quand il existe.
    assert (
        t["id_eli"]
        == "https://www.legifrance.gouv.fr/eli/arrete/2026/8/11/ARMM2621619A/jo/texte"
    )


def test_parser_texte_rejette_autre_racine():
    assert parser_texte(SOMMAIRE.read_bytes()) is None  # racine <JO>


# ---------------------------------------------------------------------------
# Lien Légifrance
# ---------------------------------------------------------------------------


def test_construction_lien_legifrance():
    assert (
        construire_lien("JORFTEXT000054708776")
        == "https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000054708776"
    )


# ---------------------------------------------------------------------------
# Ingestion d'un tarball (reconstruit depuis les fixtures réelles) + idempotence
# ---------------------------------------------------------------------------

CHEMIN_CONT = (
    "20260819-003035/jorf/simple/JORF/CONT/00/00/54/70/68/JORFCONT000054706874"
)


@pytest.fixture()
def mini_tarball(tmp_path):
    """tar.gz à l'arborescence réelle JORFSIMPLE, membres = fixtures réelles."""
    chemin = tmp_path / "JORFSIMPLE_20260819-003035.tar.gz"
    with tarfile.open(chemin, "w:gz") as tar:
        tar.add(SOMMAIRE, arcname=f"{CHEMIN_CONT}/JORFCONT000054706874.xml")
        tar.add(TEXTE_NOMINATION, arcname=f"{CHEMIN_CONT}/JORFTEXT000054708776.xml")
        tar.add(TEXTE_ARRETE, arcname=f"{CHEMIN_CONT}/JORFTEXT000054708438.xml")
    return chemin


@pytest.fixture()
def conn(tmp_path):
    c = db.init_db(chemin=tmp_path / "test.db")
    c.executescript(_SCHEMA)
    c.commit()
    yield c
    c.close()


def test_ingestion_et_idempotence(conn, mini_tarball):
    n, dates = ingerer_tarball(mini_tarball, conn)
    assert n == 2
    assert dates == ["2026-08-19"]

    ligne = conn.execute(
        "SELECT * FROM jorf_textes WHERE texte_id = 'JORFTEXT000054708776'"
    ).fetchone()
    assert ligne["is_nomination"] == 1
    assert ligne["nature"] == "DECRET"
    assert ligne["ministere"] == "Premier ministre"
    assert (
        ligne["rubrique"]
        == "Décrets, arrêtés, circulaires > Mesures nominatives > Premier ministre"
    )
    assert (
        ligne["lien_legifrance"]
        == "https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000054708776"
    )

    # Réexécution : aucun doublon (clé JORFTEXT).
    n2, _ = ingerer_tarball(mini_tarball, conn)
    assert n2 == 2
    assert conn.execute("SELECT count(*) FROM jorf_textes").fetchone()[0] == 2

    # Agrégats reconstruits depuis la table.
    reconstruire_agregats(conn)
    jn = conn.execute(
        "SELECT nature, nb FROM jorf_par_jour_nature WHERE date_publi='2026-08-19' ORDER BY nature"
    ).fetchall()
    assert [(r["nature"], r["nb"]) for r in jn] == [("ARRETE", 1), ("DECRET", 1)]
    nm = conn.execute("SELECT ministere, nb FROM jorf_nominations_ministere").fetchall()
    assert [(r["ministere"], r["nb"]) for r in nm] == [("Premier ministre", 1)]


# ---------------------------------------------------------------------------
# Intégration réseau : index réel + dernier tarball nocturne réel
# ---------------------------------------------------------------------------


@pytest.mark.reseau
def test_integration_index_et_dernier_jo(tmp_path):
    from pipelines.common import session_http, telecharger

    session = session_http()
    r = session.get(URL_JORFSIMPLE, timeout=60)
    r.raise_for_status()
    nocturnes = livraisons_nocturnes(r.text)
    # Historique profond côté DILA : il y a toujours largement plus de 10 nocturnes.
    assert len(nocturnes) > 10

    dernier = nocturnes[-1]
    chemin = telecharger(
        URL_JORFSIMPLE + dernier, tmp_path / dernier, session=session
    )
    c = db.init_db(chemin=tmp_path / "test.db")
    c.executescript(_SCHEMA)
    n, dates = ingerer_tarball(chemin, c)
    # Un JO réel compte typiquement ~50-150 textes.
    assert n >= 20
    assert dates and all(d.startswith("20") for d in dates)
    exemple = c.execute(
        "SELECT titre, lien_legifrance FROM jorf_textes LIMIT 1"
    ).fetchone()
    assert exemple["titre"]
    assert exemple["lien_legifrance"].startswith(
        "https://www.legifrance.gouv.fr/jorf/id/JORFTEXT"
    )
    c.close()

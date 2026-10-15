"""Tests du pipeline P6 Journal officiel (pipelines/ingest_jorf.py).

Fixtures : XML réels extraits du tarball DILA JORFSIMPLE_20260819-003035.tar.gz
(JORF n°0192 du 19 août 2026) — aucune donnée fabriquée.
"""

import tarfile
from pathlib import Path

import pytest

from pipelines import db, ingest_jorf
from pipelines.ingest_jorf import (
    _SCHEMA,
    URL_JORFSIMPLE,
    construire_lien,
    est_nomination,
    ingerer_tarball,
    jour_de_livraison,
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
# Tarball RÉEL, tel que servi par la DILA (téléchargé le 15/10/2026) : le
# correctif de 10h54 du 01/10/2026. Deux textes du JO du 01/10/2026, plus
# un texte du JO du 29/03/2024 et le décret 2007-1665 du JO du 27/11/2007.
CORRECTIF_20261001 = FIXTURES / "jorf" / "JORFSIMPLE_20261001-105421.tar.gz"

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

# Extrait VERBATIM (noms, dates, tailles) du même index relu le 15/10/2026 :
# correctifs de 07h04 et de 10h54, nocturnes tardives de 04h21 (la plus
# tardive de l'index) et de 02h30, et le lundi
# 01/06/2026 (pas de JO) où le correctif de 10h49 est la seule livraison
# avant le soir.
INDEX_EXTRAIT_15_10 = """
<img src="/icons/compressed.gif" alt="[   ]"> <a href="JORFSIMPLE_20250909-042110.tar.gz">JORFSIMPLE_20250909-042110.tar.gz</a>                        2025-09-09 04:21  367K
<img src="/icons/compressed.gif" alt="[   ]"> <a href="JORFSIMPLE_20250909-220116.tar.gz">JORFSIMPLE_20250909-220116.tar.gz</a>                        2025-09-09 22:08  6.5M
<img src="/icons/compressed.gif" alt="[   ]"> <a href="JORFSIMPLE_20260312-002858.tar.gz">JORFSIMPLE_20260312-002858.tar.gz</a>                        2026-03-12 00:29  204K
<img src="/icons/compressed.gif" alt="[   ]"> <a href="JORFSIMPLE_20260312-070417.tar.gz">JORFSIMPLE_20260312-070417.tar.gz</a>                        2026-03-12 07:05   12K
<img src="/icons/compressed.gif" alt="[   ]"> <a href="JORFSIMPLE_20260312-214147.tar.gz">JORFSIMPLE_20260312-214147.tar.gz</a>                        2026-03-12 21:47  3.0M
<img src="/icons/compressed.gif" alt="[   ]"> <a href="JORFSIMPLE_20260601-104919.tar.gz">JORFSIMPLE_20260601-104919.tar.gz</a>                        2026-06-01 10:50   15K
<img src="/icons/compressed.gif" alt="[   ]"> <a href="JORFSIMPLE_20260601-220831.tar.gz">JORFSIMPLE_20260601-220831.tar.gz</a>                        2026-06-01 22:16  4.5M
<img src="/icons/compressed.gif" alt="[   ]"> <a href="JORFSIMPLE_20261001-012453.tar.gz">JORFSIMPLE_20261001-012453.tar.gz</a>                        2026-10-01 01:25  277K
<img src="/icons/compressed.gif" alt="[   ]"> <a href="JORFSIMPLE_20261001-105421.tar.gz">JORFSIMPLE_20261001-105421.tar.gz</a>                        2026-10-01 10:55   20K
<img src="/icons/compressed.gif" alt="[   ]"> <a href="JORFSIMPLE_20261001-214554.tar.gz">JORFSIMPLE_20261001-214554.tar.gz</a>                        2026-10-01 21:51  2.9M
<img src="/icons/compressed.gif" alt="[   ]"> <a href="JORFSIMPLE_20261002-023011.tar.gz">JORFSIMPLE_20261002-023011.tar.gz</a>                        2026-10-02 02:30  203K
"""


# ---------------------------------------------------------------------------
# Index des livraisons
# ---------------------------------------------------------------------------


def test_livraisons_nocturnes_filtre_soir_et_correctifs():
    noms = livraisons_nocturnes(INDEX_EXTRAIT)
    # Seules les nocturnes (heure < HEURE_MAX_NOCTURNE) : ni soir (22h00), ni correctif 13h53,
    # ni Freemium, ni PDF.
    assert noms == [
        "JORFSIMPLE_20260728-003542.tar.gz",
        "JORFSIMPLE_20260819-003035.tar.gz",
    ]


def test_livraisons_nocturnes_ecarte_les_correctifs_de_matinee():
    """Cas réel du 01/10/2026 : le correctif de 10h54 passait le seuil de
    12 h et reculait la fenêtre au JO du 27/11/2007. Celui de 07h04 du
    12/03/2026 réécrivait des JO de 2024. Le lundi 01/06/2026 sans JO, le
    correctif de 10h49 aurait occupé une place de la fenêtre. La nocturne
    tardives de 04h21 et de 02h30 restent retenues."""
    assert livraisons_nocturnes(INDEX_EXTRAIT_15_10) == [
        "JORFSIMPLE_20250909-042110.tar.gz",
        "JORFSIMPLE_20260312-002858.tar.gz",
        "JORFSIMPLE_20261001-012453.tar.gz",
        "JORFSIMPLE_20261002-023011.tar.gz",
    ]


def test_livraisons_nocturnes_une_seule_par_jour():
    """Deux livraisons avant le seuil le même jour : la plus précoce compte
    seule, sinon un jour pèserait deux JO dans la fenêtre de --jours."""
    html = (
        '<a href="JORFSIMPLE_20261001-012453.tar.gz">'
        '<a href="JORFSIMPLE_20261001-035959.tar.gz">'
    )
    assert livraisons_nocturnes(html) == ["JORFSIMPLE_20261001-012453.tar.gz"]


def test_jour_de_livraison():
    assert jour_de_livraison("JORFSIMPLE_20261001-105421.tar.gz").isoformat() \
        == "2026-10-01"
    with pytest.raises(ValueError):
        jour_de_livraison("Freemium_jorf_simple_20250713-140000.tar.gz")


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


def test_correctif_reel_n_entre_que_pour_le_jo_de_sa_livraison(conn):
    """Le tarball réel du 01/10/2026 10h54 : les textes des JO de 2007 et
    de 2024 sont des réécritures, ils n'entrent pas et ne comptent pas
    comme JO de la fenêtre. Les deux textes du JO du 01/10 entrent."""
    n, dates = ingerer_tarball(CORRECTIF_20261001, conn)
    assert (n, dates) == (2, ["2026-10-01"])
    assert [r[0] for r in conn.execute(
        "SELECT DISTINCT date_publi FROM jorf_textes")] == ["2026-10-01"]
    assert conn.execute(
        "SELECT count(*) FROM jorf_textes WHERE texte_id IN"
        " ('JORFTEXT000000341494', 'JORFTEXT000049339022')"
    ).fetchone()[0] == 0


class _Reponse:
    def __init__(self, texte):
        self.text = texte

    def raise_for_status(self):
        pass


def _jouer_main(monkeypatch, tmp_path, index_html, tarballs, base=None):
    """main() hors ligne : index et tarballs servis depuis le disque."""
    chemin_db = base or tmp_path / "jorf.db"
    monkeypatch.setenv("FT_DB_PATH", str(chemin_db))

    class _Session:
        def get(self, url, timeout=None):
            assert url == URL_JORFSIMPLE
            return _Reponse(index_html)

    monkeypatch.setattr(ingest_jorf, "session_http", lambda *a, **k: _Session())
    monkeypatch.setattr(
        ingest_jorf, "telecharger",
        lambda url, dest, **k: tarballs[url.rsplit("/", 1)[-1]],
    )
    code = ingest_jorf.main([])
    return code, db.connexion(chemin_db)


@pytest.mark.parametrize("seuil_horaire_neutralise", [False, True])
def test_fenetre_bornee_malgre_un_correctif_a_l_index(
    monkeypatch, tmp_path, mini_tarball, seuil_horaire_neutralise
):
    """Propriété de la fenêtre servie : MIN(date_publi) n'est jamais à plus
    de 60 jours de MAX(date_publi), et la note meta dit la vraie fenêtre.

    Le second cas neutralise le filtre horaire (seuil remis à 24 h) : le
    filtre par date de livraison doit borner la fenêtre À LUI SEUL. Les deux
    gardes se couvrent l'une l'autre."""
    if seuil_horaire_neutralise:
        monkeypatch.setattr(ingest_jorf, "HEURE_MAX_NOCTURNE", 24)
    index = (
        '<a href="JORFSIMPLE_20260819-003035.tar.gz">'
        '<a href="JORFSIMPLE_20261001-105421.tar.gz">'
    )
    code, c = _jouer_main(monkeypatch, tmp_path, index, {
        "JORFSIMPLE_20260819-003035.tar.gz": mini_tarball,
        "JORFSIMPLE_20261001-105421.tar.gz": CORRECTIF_20261001,
    })
    assert code == 0
    mini, maxi, ecart = c.execute(
        "SELECT MIN(date_publi), MAX(date_publi),"
        " julianday(MAX(date_publi)) - julianday(MIN(date_publi))"
        " FROM jorf_textes"
    ).fetchone()
    assert ecart <= 60, (mini, maxi)
    assert mini >= "2026-08-19"
    notes = c.execute(
        "SELECT notes FROM meta_sources WHERE source_id = 'S3'").fetchone()[0]
    assert "2007" not in notes and "2024" not in notes
    c.close()


def test_base_persistante_polluee_se_repare(monkeypatch, tmp_path, mini_tarball):
    """État de la base servie le 15/10/2026 : un texte du JO du 27/11/2007
    resté en table bloquait la purge, et les jours s'accumulaient (44 JO
    affichés sur /documents). Un cycle corrigé le sort de la fenêtre.

    Test documentaire : il passe aussi sur le code d'avant, dont la purge
    fonctionnait dès lors qu'aucun correctif n'entrait. Il fixe que la
    base servie se répare d'elle-même, sans geste sur le serveur."""
    base = tmp_path / "servie.db"
    c = db.init_db(chemin=base)
    c.executescript(_SCHEMA)
    c.execute(
        "INSERT INTO jorf_textes (texte_id, date_publi, titre, lien_legifrance)"
        " VALUES ('JORFTEXT000000341494', '2007-11-27', 'Décret n° 2007-1665',"
        " 'https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000000341494')"
    )
    c.commit()
    c.close()
    code, c = _jouer_main(
        monkeypatch, tmp_path, '<a href="JORFSIMPLE_20260819-003035.tar.gz">',
        {"JORFSIMPLE_20260819-003035.tar.gz": mini_tarball}, base=base,
    )
    assert code == 0
    assert [r[0] for r in c.execute(
        "SELECT DISTINCT date_publi FROM jorf_textes")] == ["2026-08-19"]
    assert c.execute(
        "SELECT count(*) FROM jorf_textes_archive"
        " WHERE texte_id = 'JORFTEXT000000341494'").fetchone()[0] == 1
    c.close()


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
    # Un JO réel compte typiquement ~50-150 textes, mais une livraison
    # légère existe (4 textes le 01/10/2026) : on n'exige que du contenu.
    assert n >= 1
    assert dates and all(d.startswith("20") for d in dates)
    exemple = c.execute(
        "SELECT titre, lien_legifrance FROM jorf_textes LIMIT 1"
    ).fetchone()
    assert exemple["titre"]
    assert exemple["lien_legifrance"].startswith(
        "https://www.legifrance.gouv.fr/jorf/id/JORFTEXT"
    )
    c.close()

"""Tests du pipeline P6 Journal officiel (pipelines/ingest_jorf.py).

Fixtures : XML réels extraits du tarball DILA JORFSIMPLE_20260819-003035.tar.gz
(JORF n°0192 du 19 août 2026) — aucune donnée fabriquée.
"""

import tarfile
from datetime import date, timedelta
from pathlib import Path

import pytest
import requests

from pipelines import db, ingest_jorf
from pipelines.ingest_jorf import (
    _SCHEMA,
    MARQUE_FENETRE_DISCONTINUE,
    MARQUE_FENETRE_REDUITE,
    URL_JORFSIMPLE,
    construire_lien,
    ecarts_anormaux,
    est_nomination,
    index_reconnu,
    ingerer_tarball,
    jour_de_livraison,
    livraisons_de_journee_sans_nocturne,
    livraisons_nocturnes,
    ministere_du_chemin,
    note_fenetre,
    parser_sommaire,
    parser_texte,
    reconstruire_agregats,
    stock_a_l_index,
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


def test_livraisons_de_journee_sans_nocturne_extrait_reel():
    """Sur l'extrait réel du 15/10/2026 : seul le lundi 01/06/2026 (pas de
    JO) n'a qu'un correctif de journée ; les correctifs du 12/03 et du
    01/10 tombent des jours qui ont leur nocturne, et le soir est ignoré."""
    assert livraisons_de_journee_sans_nocturne(INDEX_EXTRAIT_15_10) == [
        "JORFSIMPLE_20260601-104919.tar.gz",
    ]


# Nocturne en retard : le JO du jour livré à 06h12 (heure constatée nulle
# part à ce jour — la plus tardive de l'index est 04h21 ; cas construit).
INDEX_NOCTURNE_EN_RETARD = INDEX_EXTRAIT_15_10 + (
    '<a href="JORFSIMPLE_20261003-061204.tar.gz">'
    '<a href="JORFSIMPLE_20261003-214500.tar.gz">'
)


def test_nocturne_en_retard_est_signalee_au_journal(caplog):
    """Avant : la livraison de 06h12 était écartée par la règle des 06 h et
    le JO du 03/10 sautait de la fenêtre sans compteur ni avertissement."""
    from datetime import date
    assert "JORFSIMPLE_20261003-061204.tar.gz" not in livraisons_nocturnes(
        INDEX_NOCTURNE_EN_RETARD)
    with caplog.at_level("INFO"):
        noms = ingest_jorf.signaler_jours_sans_nocturne(
            INDEX_NOCTURNE_EN_RETARD, date(2026, 10, 1))
    assert noms == ["JORFSIMPLE_20261003-061204.tar.gz"]
    assert "1 livraison(s) de journée sur un jour sans nocturne" in caplog.text
    assert "JORFSIMPLE_20261003-061204.tar.gz" in caplog.text
    assert caplog.records[-1].levelname == "WARNING"


def test_compteur_journalise_a_zero(caplog):
    """Le compteur parle aussi quand il n'y a rien : le lundi 01/06/2026 est
    hors de la fenêtre qui commence le 01/10/2026."""
    from datetime import date
    with caplog.at_level("INFO"):
        assert ingest_jorf.signaler_jours_sans_nocturne(
            INDEX_EXTRAIT_15_10, date(2026, 10, 1)) == []
    assert "dans la fenêtre : 0" in caplog.text


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


def test_cycle_signale_une_nocturne_en_retard(monkeypatch, tmp_path, mini_tarball, caplog):
    """main() : le JO du 19/08 est ingéré, la livraison de 06h12 du 20/08
    (cas construit) est écartée ET nommée au journal du cycle."""
    index = (
        '<a href="JORFSIMPLE_20260819-003035.tar.gz">'
        '<a href="JORFSIMPLE_20260820-061204.tar.gz">'
    )
    with caplog.at_level("INFO"):
        code, c = _jouer_main(monkeypatch, tmp_path, index, {
            "JORFSIMPLE_20260819-003035.tar.gz": mini_tarball,
        })
    assert code == 0
    c.close()
    alertes = [r for r in caplog.records if r.levelname == "WARNING"
               and "JORFSIMPLE_20260820-061204.tar.gz" in r.getMessage()]
    assert len(alertes) == 1


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
# Serveur DILA injoignable (cas réel des 03 et 04/10/2026) : secours
# ---------------------------------------------------------------------------

RESET_DILA = (
    "HTTPSConnectionPool(host='echanges.dila.gouv.fr', port=443): Max retries"
    " exceeded with url: /OPENDATA/JORFSIMPLE/ (Caused by ProtocolError("
    "'Connection aborted.', ConnectionResetError(104, 'Connection reset by"
    " peer')))"
)


def _instantane(chemin_db):
    c = db.connexion(chemin_db)
    try:
        return (
            [tuple(r) for r in c.execute(
                "SELECT texte_id, date_publi FROM jorf_textes ORDER BY 1")],
            [tuple(r) for r in c.execute(
                "SELECT * FROM meta_sources WHERE source_id = 'S3'")],
        )
    finally:
        c.close()


def _base_de_la_veille(monkeypatch, tmp_path, mini_tarball):
    """Une base qu'un cycle réussi a remplie et datée (JO du 19/08/2026)."""
    code, c = _jouer_main(
        monkeypatch, tmp_path, '<a href="JORFSIMPLE_20260819-003035.tar.gz">',
        {"JORFSIMPLE_20260819-003035.tar.gz": mini_tarball},
    )
    c.close()
    assert code == 0
    return tmp_path / "jorf.db"


def test_index_injoignable_reprend_la_base_de_la_veille(
    monkeypatch, tmp_path, mini_tarball, caplog
):
    """Le cycle ne meurt plus à ingest-jorf : rien n'est écrit, la table et
    la ligne meta S3 (date des données ET date d'ingestion) restent celles
    du dernier cycle réussi, donc la fraîcheur affichée reste vraie."""
    base = _base_de_la_veille(monkeypatch, tmp_path, mini_tarball)
    avant = _instantane(base)
    assert avant[0] and "2026-08-19" in avant[1][0]   # date_donnees S3

    class _SessionCoupee:
        def get(self, url, timeout=None):
            raise requests.ConnectionError(RESET_DILA)

    monkeypatch.setattr(
        ingest_jorf, "session_http", lambda *a, **k: _SessionCoupee())
    assert ingest_jorf.main([]) == 0
    assert _instantane(base) == avant
    assert "secours" in caplog.text and "2026-08-19" in caplog.text


def test_coupure_en_cours_de_telechargement_n_ecrit_rien(
    monkeypatch, tmp_path, mini_tarball
):
    """Index joignable, coupure au second tarball : le premier, déjà
    téléchargé, n'entre PAS en base. Sinon la table mélangerait un JO neuf
    et la date de la veille dans meta_sources."""
    base = tmp_path / "jorf.db"
    c = db.init_db(chemin=base)
    c.executescript(_SCHEMA)
    c.execute(
        "INSERT INTO jorf_textes (texte_id, date_publi, titre, lien_legifrance)"
        " VALUES ('JORFTEXT000054708438', '2026-08-18', 'Arrêté',"
        " 'https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000054708438')"
    )
    db.upsert_meta(c, "S3", "DILA", URL_JORFSIMPLE, "fr-lo", "quotidienne",
                   date_donnees="2026-08-18", lignes=1)
    c.close()
    avant = _instantane(base)
    monkeypatch.setenv("FT_DB_PATH", str(base))

    class _Session:
        def get(self, url, timeout=None):
            return _Reponse(
                '<a href="JORFSIMPLE_20260819-003035.tar.gz">'
                '<a href="JORFSIMPLE_20261002-023011.tar.gz">'
            )

    def _telecharger(url, dest, **k):
        if url.endswith("JORFSIMPLE_20261002-023011.tar.gz"):
            raise requests.ConnectionError(RESET_DILA)
        return mini_tarball

    monkeypatch.setattr(ingest_jorf, "session_http", lambda *a, **k: _Session())
    monkeypatch.setattr(ingest_jorf, "telecharger", _telecharger)
    assert ingest_jorf.main([]) == 0
    assert _instantane(base) == avant


def test_dila_injoignable_sur_base_neuve_echoue(monkeypatch, tmp_path):
    """Rien d'un cycle précédent à reprendre : échec, tout-ou-rien. Test de
    la limite du secours ; il passe aussi sur le code d'avant."""
    base = tmp_path / "neuve.db"
    monkeypatch.setenv("FT_DB_PATH", str(base))

    class _SessionCoupee:
        def get(self, url, timeout=None):
            raise requests.ConnectionError(RESET_DILA)

    monkeypatch.setattr(
        ingest_jorf, "session_http", lambda *a, **k: _SessionCoupee())
    assert ingest_jorf.main([]) == 1
    c = db.init_db(chemin=base)
    assert c.execute(
        "SELECT count(*) FROM meta_sources WHERE source_id = 'S3'"
    ).fetchone()[0] == 0
    c.close()


# ---------------------------------------------------------------------------
# Index réduit par la DILA (cas réel du 08/11/2026) : la base porte la fenêtre
# ---------------------------------------------------------------------------

# Extrait VERBATIM de l'index réel relu le 11/11/2026 : la DILA a régénéré
# son stock le 08/11 et retiré toutes les livraisons antérieures. Restent
# trois livraisons du soir et deux nocturnes, dont celle de 04h43.
INDEX_11_11 = """
<img src="/icons/compressed.gif" alt="[   ]"> <a href="Freemium_jorf_simple_20261108-140000.tar.gz">Freemium_jorf_simple_20261108-140000.tar.gz</a>              2026-11-08 13:02  1.1G
<img src="/icons/compressed.gif" alt="[   ]"> <a href="JORFSIMPLE_20261108-210452.tar.gz">JORFSIMPLE_20261108-210452.tar.gz</a>                        2026-11-08 21:08  626K
<img src="/icons/compressed.gif" alt="[   ]"> <a href="JORFSIMPLE_20261109-212854.tar.gz">JORFSIMPLE_20261109-212854.tar.gz</a>                        2026-11-09 21:33  2.2M
<img src="/icons/compressed.gif" alt="[   ]"> <a href="JORFSIMPLE_20261110-002231.tar.gz">JORFSIMPLE_20261110-002231.tar.gz</a>                        2026-11-10 00:22   71K
<img src="/icons/compressed.gif" alt="[   ]"> <a href="JORFSIMPLE_20261110-213159.tar.gz">JORFSIMPLE_20261110-213159.tar.gz</a>                        2026-11-10 21:41  923K
<img src="/icons/compressed.gif" alt="[   ]"> <a href="JORFSIMPLE_20261111-044354.tar.gz">JORFSIMPLE_20261111-044354.tar.gz</a>                        2026-11-11 04:44   84K
"""
# Le même index tel qu'il se lisait au passage du cycle du 09/11 (05:17) :
# les deux premières lignes seulement, aucune nocturne.
INDEX_09_11 = "\n".join(INDEX_11_11.splitlines()[:3]) + "\n"

# Un texte RÉEL par JO (le premier du sommaire) pour les 30 JO parus du
# 14/07 au 19/08/2026, extrait des 30 nocturnes de cette période : de quoi
# poser une base persistante qui porte sa fenêtre entière.
TRENTE_JO = FIXTURES / "jorf" / "un_texte_par_jo_20260714_20260819.tsv"

# Le stock régénéré en tête d'un index construit : sert la note de la fenêtre.
LIGNE_STOCK = '<a href="Freemium_jorf_simple_20261108-140000.tar.gz">'


def _trente_jo():
    lignes = [l.split("\t") for l in TRENTE_JO.read_text(encoding="utf-8").splitlines()]
    assert len(lignes) == 30 and len({l[0] for l in lignes}) == 30
    return lignes


def _base_trente_jo(tmp_path):
    """Base persistante : 30 JO réels, ligne meta S3 datée du 19/08/2026."""
    base = tmp_path / "persistante.db"
    c = db.init_db(chemin=base)
    c.executescript(_SCHEMA)
    c.executemany(
        "INSERT INTO jorf_textes (date_publi, texte_id, nature, titre,"
        " lien_legifrance) VALUES (?, ?, ?, ?, ?)",
        [(d, i, n, t, construire_lien(i)) for d, i, n, t in _trente_jo()],
    )
    db.upsert_meta(c, "S3", "DILA", URL_JORFSIMPLE, "fr-lo", "quotidienne",
                   date_donnees="2026-08-19", lignes=30)
    c.close()
    return base


@pytest.fixture()
def nocturne_du_lendemain(tmp_path):
    """Cas construit : une nocturne stampée du 20/08 qui porte encore le JO
    du 19/08 (la veille est tolérée). Sert de SECONDE livraison d'un index
    réduit, sans inventer un JO."""
    chemin = tmp_path / "JORFSIMPLE_20260820-002500.tar.gz"
    with tarfile.open(chemin, "w:gz") as tar:
        tar.add(SOMMAIRE, arcname=f"{CHEMIN_CONT}/JORFCONT000054706874.xml")
        tar.add(TEXTE_ARRETE, arcname=f"{CHEMIN_CONT}/JORFTEXT000054708438.xml")
    return chemin


def _jo_en_base(c):
    return [r[0] for r in c.execute(
        "SELECT DISTINCT date_publi FROM jorf_textes ORDER BY 1")]


def _note_s3(c):
    return c.execute(
        "SELECT notes FROM meta_sources WHERE source_id = 'S3'").fetchone()[0]


def test_index_reel_du_11_11_reconnu():
    """L'index réduit reste un index que l'on sait lire : deux nocturnes,
    un stock daté. Aucune livraison de journée à signaler."""
    assert livraisons_nocturnes(INDEX_11_11) == [
        "JORFSIMPLE_20261110-002231.tar.gz",
        "JORFSIMPLE_20261111-044354.tar.gz",
    ]
    assert stock_a_l_index(INDEX_11_11) == "20261108"
    assert index_reconnu(INDEX_11_11) and index_reconnu(INDEX_09_11)
    assert livraisons_nocturnes(INDEX_09_11) == []
    assert stock_a_l_index(INDEX_EXTRAIT_15_10) is None
    assert not index_reconnu("<h1>Index of /OPENDATA/JORFSIMPLE</h1>")


def test_index_reduit_a_deux_nocturnes_la_base_garde_ses_trente_jo(
    monkeypatch, tmp_path, mini_tarball, nocturne_du_lendemain, caplog
):
    """LE cas du 08/11/2026. La base servie porte 30 JO, l'index n'en liste
    plus que deux livraisons : la fenêtre se calculait sur la plus ancienne
    livraison listée, et 29 JO partaient à l'archive en sortie 0. Ils sont
    parmi les 30 derniers JO en base : ils restent, rien n'est archivé."""
    base = _base_trente_jo(tmp_path)
    index = LIGNE_STOCK + (
        '<a href="JORFSIMPLE_20260819-003035.tar.gz">'
        '<a href="JORFSIMPLE_20260820-002500.tar.gz">'
    )
    with caplog.at_level("INFO"):
        code, c = _jouer_main(monkeypatch, tmp_path, index, {
            "JORFSIMPLE_20260819-003035.tar.gz": mini_tarball,
            "JORFSIMPLE_20260820-002500.tar.gz": nocturne_du_lendemain,
        }, base=base)
    assert code == 0
    assert _jo_en_base(c) == [l[0] for l in _trente_jo()]
    assert c.execute("SELECT count(*) FROM jorf_textes_archive").fetchone()[0] == 0
    # 30 textes de la base + les 2 du JO du 19/08 livrés cette nuit.
    assert c.execute("SELECT count(*) FROM jorf_textes").fetchone()[0] == 32
    note = _note_s3(c)
    assert note.startswith("30 JO en base, du 14/07/2026 au 19/08/2026")
    assert "liste 2 livraison(s) nocturne(s)" in note
    assert "Freemium du 08/11/2026" in note
    c.close()
    avert = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
    assert sum("index DILA réduit à 2 livraison(s) nocturne(s)" in m for m in avert) == 1
    assert not any("RÉDUITE" in m or "DISCONTINUE" in m for m in avert)


def test_la_fenetre_glisse_sur_les_jo_en_base_pas_sur_l_index(
    monkeypatch, tmp_path, mini_tarball
):
    """Même base de 30 JO, fenêtre demandée de 10 JO, UNE nocturne à l'index.
    Restent les 10 derniers JO en base, exactement ; les 20 autres sortent
    vers l'archive, comptés. Sur le code d'avant il n'en restait qu'un."""
    base = _base_trente_jo(tmp_path)
    monkeypatch.setenv("FT_DB_PATH", str(base))

    class _Session:
        def get(self, url, timeout=None):
            return _Reponse('<a href="JORFSIMPLE_20260819-003035.tar.gz">')

    monkeypatch.setattr(ingest_jorf, "session_http", lambda *a, **k: _Session())
    monkeypatch.setattr(ingest_jorf, "telecharger", lambda url, dest, **k: mini_tarball)
    assert ingest_jorf.main(["--jours", "10"]) == 0
    c = db.connexion(base)
    attendus = [l[0] for l in _trente_jo()][-10:]
    assert _jo_en_base(c) == attendus
    assert c.execute("SELECT count(*) FROM jorf_textes_archive").fetchone()[0] == 20
    assert c.execute(
        "SELECT MAX(date_publi) FROM jorf_textes_archive").fetchone()[0] < attendus[0]
    assert _note_s3(c).startswith("10 JO en base, du 07/08/2026 au 19/08/2026")
    c.close()


def test_index_sans_nocturne_mene_au_secours(monkeypatch, tmp_path, caplog):
    """Index réel du 09/11/2026 à l'heure du cycle : un stock, une livraison
    du soir, AUCUNE nocturne. Ce n'est pas un format inconnu : le cycle
    sortait en erreur à tort. Secours : rien n'est écrit, sortie 0, et le
    journal dit l'index réduit à zéro."""
    base = _base_trente_jo(tmp_path)
    avant = _instantane(base)
    code, c = _jouer_main(monkeypatch, tmp_path, INDEX_09_11, {}, base=base)
    c.close()
    assert code == 0
    assert _instantane(base) == avant
    avert = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
    assert len(avert) == 1
    assert "index DILA réduit à 0 livraison nocturne" in avert[0]
    assert "20261108" in avert[0] and "secours" in avert[0]
    assert "2026-08-19" in avert[0]


def test_index_sans_nocturne_sur_base_neuve_echoue(monkeypatch, tmp_path):
    """Limite du secours : sans JORF d'un cycle précédent il n'y a rien
    d'honnête à servir. Passe aussi sur le code d'avant (il échouait
    toujours)."""
    code, c = _jouer_main(monkeypatch, tmp_path, INDEX_09_11, {})
    c.close()
    assert code == 1


def test_index_illisible_echoue_meme_avec_une_base(monkeypatch, tmp_path):
    """Ni livraison ni stock reconnus : la page a changé de forme, et le
    secours masquerait une panne que personne ne réparerait. Échec, comme
    avant. Il tue la mutation qui envoie tout index vide au secours."""
    base = _base_trente_jo(tmp_path)
    code, c = _jouer_main(
        monkeypatch, tmp_path, "<h1>Index of /OPENDATA/JORFSIMPLE</h1>", {},
        base=base)
    c.close()
    assert code == 1


def test_base_vide_et_index_reduit_la_fenetre_se_dit_reduite(
    monkeypatch, tmp_path, mini_tarball, nocturne_du_lendemain, caplog
):
    """Base neuve (CI, premier déploiement) devant l'index réduit : elle n'a
    que ce que l'index liste. La note ne dit pas « 30 JO » : elle commence
    par la marque, donne le compteur, les bornes, la date du constat et
    l'état de l'index."""
    index = LIGNE_STOCK + (
        '<a href="JORFSIMPLE_20260819-003035.tar.gz">'
        '<a href="JORFSIMPLE_20260820-002500.tar.gz">'
    )
    code, c = _jouer_main(monkeypatch, tmp_path, index, {
        "JORFSIMPLE_20260819-003035.tar.gz": mini_tarball,
        "JORFSIMPLE_20260820-002500.tar.gz": nocturne_du_lendemain,
    })
    assert code == 0
    assert _jo_en_base(c) == ["2026-08-19"]
    note = _note_s3(c)
    constat = c.execute(
        "SELECT substr(date_ingestion, 1, 10) FROM meta_sources"
        " WHERE source_id = 'S3'").fetchone()[0]
    c.close()
    assert note.startswith(
        f"{MARQUE_FENETRE_REDUITE} : 1 JO en base sur les 30 visés,"
        " du 19/08/2026 au 19/08/2026 (constat du ")
    assert "liste 2 livraison(s) nocturne(s)" in note
    assert "Freemium du 08/11/2026" in note
    assert "les JO antérieurs ne sont pas dans cette base" in note
    # La date du constat est celle du cycle (UTC ou Paris : même jour ou veille).
    assert constat[:4] in note
    avert = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
    assert sum("fenêtre RÉDUITE : 1 JO en base sur 30 visés" in m for m in avert) == 1


def test_ecarts_entre_jo_mesures_sur_trente_jo_reels():
    """Sur les 30 JO réels du 14/07 au 19/08/2026 : aucun écart de plus de
    trois jours (le plus long : 15/08 → 18/08, pont du 15 août puis lundi).
    Retirer une semaine de JO en fait apparaître UN, nommé."""
    dates = [l[0] for l in _trente_jo()]
    assert ecarts_anormaux(dates) == []
    assert ("2026-08-15", "2026-08-18") in list(zip(dates, dates[1:]))
    troues = [d for d in dates if not "2026-08-01" <= d <= "2026-08-07"]
    assert ecarts_anormaux(troues) == [("2026-07-31", "2026-08-08", 8)]


def test_fenetre_discontinue_se_dit_dans_la_note_et_au_journal(
    monkeypatch, tmp_path, mini_tarball, caplog
):
    """Contrepartie de la nouvelle règle : une base qui garde ses JO pendant
    que l'ingestion est arrêtée peut avoir un TROU que l'index ne sait plus
    combler. Base arrêtée au JO du 31/07, index réduit à la nocturne du
    19/08 : la note commence par la marque et nomme l'intervalle."""
    base = _base_trente_jo(tmp_path)
    c = db.connexion(base)
    c.execute("DELETE FROM jorf_textes WHERE date_publi > '2026-07-31'")
    c.commit()
    c.close()
    code, c = _jouer_main(
        monkeypatch, tmp_path, '<a href="JORFSIMPLE_20260819-003035.tar.gz">',
        {"JORFSIMPLE_20260819-003035.tar.gz": mini_tarball}, base=base)
    assert code == 0
    note = _note_s3(c)
    assert _jo_en_base(c)[-2:] == ["2026-07-31", "2026-08-19"]
    c.close()
    assert note.startswith(f"{MARQUE_FENETRE_REDUITE} : 16 JO en base sur les 30 visés")
    assert "aucun JO en base entre le 31/07/2026 et le 19/08/2026 (19 jours)" in note
    avert = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
    assert sum("fenêtre DISCONTINUE : 1 écart(s)" in m for m in avert) == 1


def test_note_fenetre_pleine_mais_discontinue():
    """30 JO en base dont un intervalle sans JO : la marque passe en tête,
    le compte reste dit."""
    dates = [l[0] for l in _trente_jo()]
    troues = [d for d in dates if not "2026-08-01" <= d <= "2026-08-07"]
    note = note_fenetre(troues, len(troues), 400, None, "2026-08-19")
    assert note.startswith(
        f"{MARQUE_FENETRE_DISCONTINUE} : aucun JO en base entre le 31/07/2026"
        " et le 08/08/2026 (8 jours) (constat du 19/08/2026) ; 24 JO en base")
    pleine = note_fenetre(dates, 30, 400, None, "2026-08-19")
    assert pleine == (
        "30 JO en base, du 14/07/2026 au 19/08/2026 ; l'index de la DILA"
        " liste 400 livraison(s) nocturne(s)")


def test_compteurs_de_fenetre_journalises_a_chaque_cycle(
    monkeypatch, tmp_path, mini_tarball, caplog
):
    """Cycle sans rien à signaler sur les écarts : le compteur est écrit
    quand même, à zéro, ainsi que le nombre de textes purgés."""
    with caplog.at_level("INFO"):
        code, c = _jouer_main(
            monkeypatch, tmp_path, '<a href="JORFSIMPLE_20260819-003035.tar.gz">',
            {"JORFSIMPLE_20260819-003035.tar.gz": mini_tarball})
    c.close()
    assert code == 0
    messages = [r.getMessage() for r in caplog.records]
    assert sum("JO consécutifs de la fenêtre : 0" in m for m in messages) == 1
    assert sum("0 texte(s) plus ancien(s) archivé(s) puis purgé(s)" in m
               for m in messages) == 1


# ---------------------------------------------------------------------------
# Intégration réseau : index réel + dernier tarball nocturne réel
# ---------------------------------------------------------------------------


@pytest.mark.reseau
def test_integration_index_et_dernier_jo(tmp_path):
    from pipelines.common import session_http, telecharger

    session = session_http()
    r = session.get(URL_JORFSIMPLE, timeout=60)
    r.raise_for_status()
    # L'index est celui que l'on sait lire : au moins un fichier reconnu.
    # AUCUN nombre de livraisons n'est exigé — la DILA vide l'index à chaque
    # régénération de son stock (08/11/2026 : de 404 nocturnes à zéro, et
    # l'ancienne assertion « plus de 10 » échouait sur un amont sain).
    assert index_reconnu(r.text), r.text[:500]
    nocturnes = livraisons_nocturnes(r.text)
    # Ce que la règle horaire écarte n'est pas une nocturne, et inversement.
    for nom in nocturnes:
        assert jour_de_livraison(nom) <= date.today() + timedelta(days=1)
    assert nocturnes == sorted(nocturnes)
    if not nocturnes:
        pytest.skip(
            "index JORFSIMPLE lisible mais sans aucune nocturne (stock"
            f" Freemium : {stock_a_l_index(r.text)}) : rien à télécharger")

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

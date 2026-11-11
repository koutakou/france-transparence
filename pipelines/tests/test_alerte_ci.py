"""Le dispositif d'alerte : destinataire, diagnostic, sentinelles, vigie.

POURQUOI. Le 11/11/2026, la validation quotidienne était rouge depuis le
22/10 (vingt et un cycles planifiés) et le site en ligne figé depuis le
08/11. L'issue d'échec, #126, portait vingt commentaires identiques, sans
personne d'assigné ni de mentionné, sur un dépôt sans abonné : personne ne
l'avait vue. Huit des vingt et un runs étaient tombés pour une autre raison
que les autres, sans que rien ne le dise. Le job qui devait prévenir de
l'extinction du cron ne tournait que sur cycle vert.

Ces tests tiennent quatre choses :

1. `deploy/diagnostic_ci.py` nomme la cible et les lignes d'erreur, sur des
   EXTRAITS RÉELS des journaux de ces runs (`fixtures/alerte_ci/journal-*`,
   lignes non retouchées ; seules des lignes ont été retirées, entre
   l'en-tête de l'étape et le pipeline tombé) ;
2. `deploy/tenir_issue.py` assigne, mentionne, et ne répète pas un message
   identique — contre un `gh` factice qui tient ses issues dans un fichier ;
3. `deploy/vigie_site.py` lit la fraîcheur, le domaine et `security.txt` sur
   ce que le site et le registre servaient réellement le 11/11/2026 ;
4. les workflows gardent leur forme : aucune alerte sans destinataire, les
   sentinelles hors de portée d'un échec de `construire`, les actions
   épinglées.

Aucun de ces tests ne touche au réseau ni à GitHub.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).parent / "fixtures" / "alerte_ci"
WORKFLOWS = RACINE / ".github" / "workflows"

sys.path.insert(0, str(RACINE / "deploy"))
import diagnostic_ci  # noqa: E402
import tenir_issue  # noqa: E402
import vigie_site  # noqa: E402


def utc(annee, mois, jour, heure=0, minute=0):
    return datetime(annee, mois, jour, heure, minute, tzinfo=timezone.utc)


# --- 1. Diagnostic d'un run tombé -------------------------------------------

# Run planifié, cible attendue, début de la première et de la dernière ligne
# d'erreur — telles qu'elles figurent dans le journal du run.
PANNES_REELLES = [
    ("parlement", "ingest-parlement",
     "2026-11-10 13:01:08 ERROR [parlement] ÉCHEC Sénat ODSEN (sénateurs) : export_sens : table elusen absente ou vide",
     "2026-11-10 13:01:44 ERROR [parlement] bilan P9 : 1/5 sources en échec"),
    ("hatvp", "ingest-hatvp_declarations",
     "2026-11-08 11:35:05 ERROR [ingest_hatvp_declarations] P15 en échec.",
     "requests.exceptions.ChunkedEncodingError: (\"Connection broken: ConnectionResetError(104"),
    ("decp", "ingest-decp",
     "2026-11-09 13:28:42 ERROR [ingest_decp] échec avant écriture",
     "requests.exceptions.ConnectionError: HTTPSConnectionPool(host='static.data.gouv.fr', port=443): Read timed out."),
    ("collectivites", "ingest-collectivites",
     "2026-11-04 12:46:41 ERROR [ingest_collectivites] échec du pipeline finances locales",
     "requests.exceptions.HTTPError: 401 Client Error: Unauthorized for url: https://data.ofgl.fr/"),
    ("lobbying", "ingest-lobbying",
     "2026-10-23 09:40:46 ERROR [lobbying] échec du pipeline lobbying",
     "RuntimeError: vues CSV manquantes dans le zip HATVP"),
    ("pytest", "test",
     "E AttributeError: Relations no longer have fetchone()",
     "FAILED pipelines/tests/test_decp.py::test_normalisation_des_libelles_heterogenes - AttributeError"),
]


@pytest.mark.parametrize("nom, cible, premiere, derniere", PANNES_REELLES)
def test_le_diagnostic_nomme_la_cible_et_les_lignes_d_erreur(nom, cible, premiere, derniere):
    journal = (FIXTURES / f"journal-{nom}.txt").read_text(encoding="utf-8")
    trouve = diagnostic_ci.diagnostiquer(journal)
    assert trouve["cible"] == cible
    assert trouve["premiere"].startswith(premiere)
    assert trouve["derniere"].startswith(derniere)


def test_les_six_pannes_reelles_sont_distinguees():
    """Ce que les vingt commentaires identiques ne permettaient pas."""
    cibles = {
        diagnostic_ci.diagnostiquer(
            (FIXTURES / f"journal-{nom}.txt").read_text(encoding="utf-8"))["cible"]
        for nom, *_ in PANNES_REELLES
    }
    assert len(cibles) == len(PANNES_REELLES)


def test_une_ligne_citee_est_bornee_et_ne_ferme_pas_le_bloc_de_code():
    journal = (FIXTURES / "journal-lobbying.txt").read_text(encoding="utf-8")
    trouve = diagnostic_ci.diagnostiquer(journal)
    # La ligne réelle énumère les vues manquantes sur plus de 300 caractères.
    assert len(trouve["derniere"]) == diagnostic_ci.LONGUEUR_MAX
    assert trouve["derniere"].endswith("…")
    assert "`" not in diagnostic_ci._citer("un ```bloc``` et une `citation`")


def test_un_journal_sans_erreur_ne_fait_rien_deviner():
    """Job interrompu avant toute erreur : les champs restent vides."""
    journal = (FIXTURES / "journal-parlement.txt").read_text(encoding="utf-8")
    sans_erreur = "\n".join(
        l for l in journal.splitlines() if "##[error]" not in l and "make: ***" not in l
    )
    assert diagnostic_ci.diagnostiquer(sans_erreur) == {
        "cible": "", "premiere": "", "derniere": ""}


# --- 2. Tenue d'une issue, contre un `gh` factice ---------------------------

GH_FACTICE = r'''#!{python}
"""`gh` factice : issues tenues dans un fichier JSON, appels journalisés."""
import json, os, sys
etat_p, appels_p = os.environ["FAUX_GH_ETAT"], os.environ["FAUX_GH_APPELS"]
a = sys.argv[1:]
with open(appels_p, "a") as f:
    f.write(json.dumps(a, ensure_ascii=False) + "\n")
issues = json.load(open(etat_p))
def opt(nom, defaut=None):
    return a[a.index(nom) + 1] if nom in a else defaut
def tous(nom):
    return [a[i + 1] for i, x in enumerate(a) if x == nom]
maintenant = os.environ["FAUX_GH_MAINTENANT"]
if a[:2] == ["issue", "list"]:
    label, etat = opt("--label"), opt("--state", "open")
    print(json.dumps([
        {"number": i["number"], "title": i["title"], "createdAt": i["createdAt"],
         "state": i["state"], "assignees": [{"login": x} for x in i["assignees"]]}
        for i in issues if label in i["labels"] and (etat == "all" or i["state"] == "OPEN")]))
elif a[:2] == ["issue", "view"]:
    i = next(i for i in issues if i["number"] == int(a[2]))
    print(json.dumps({"body": i["body"], "createdAt": i["createdAt"], "comments": i["comments"]}))
elif a[:2] == ["issue", "create"]:
    if "--assignee" in a and os.environ.get("FAUX_GH_REFUS_ASSIGNATION"):
        sys.stderr.write("could not assign user: 'x' not found\n"); sys.exit(1)
    n = max([i["number"] for i in issues], default=0) + 1
    issues.append({"number": n, "title": opt("--title"), "body": opt("--body"),
                   "createdAt": maintenant, "state": "OPEN", "labels": tous("--label"),
                   "assignees": tous("--assignee"), "comments": []})
    print(f"https://github.com/exemple/depot/issues/{{n}}")
else:
    i = next((i for i in issues if a[:1] == ["issue"] and i["number"] == int(a[2])), None)
    if a[:2] == ["issue", "comment"]:
        i["comments"].append({{"body": opt("--body"), "createdAt": maintenant}})
    elif a[:2] == ["issue", "edit"]:
        i["title"] = opt("--title", i["title"])
        i["assignees"] += tous("--add-assignee")
    elif a[:2] == ["issue", "close"]:
        i["state"] = "CLOSED"
        i["comments"].append({{"body": opt("--comment"), "createdAt": maintenant}})
json.dump(issues, open(etat_p, "w"))
'''.replace("{{", "{").replace("}}", "}")


class FauxGitHub:
    def __init__(self, dossier, monkeypatch):
        self.etat = dossier / "issues.json"
        self.appels_p = dossier / "appels.jsonl"
        self.etat.write_text("[]")
        self.appels_p.write_text("")
        binaires = dossier / "bin"
        binaires.mkdir()
        gh = binaires / "gh"
        gh.write_text(GH_FACTICE.replace("{python}", sys.executable))
        gh.chmod(0o755)
        self.mp = monkeypatch
        monkeypatch.setenv("PATH", f"{binaires}:/usr/bin:/bin")
        monkeypatch.setenv("FAUX_GH_ETAT", str(self.etat))
        monkeypatch.setenv("FAUX_GH_APPELS", str(self.appels_p))

    def a(self, instant):
        self.mp.setenv("FAUX_GH_MAINTENANT", instant.strftime("%Y-%m-%dT%H:%M:%SZ"))
        return instant

    @property
    def issues(self):
        return json.loads(self.etat.read_text())

    def appels(self, *debut):
        lus = [json.loads(l) for l in self.appels_p.read_text().splitlines()]
        return [x for x in lus if x[: len(debut)] == list(debut)]


@pytest.fixture
def github(tmp_path, monkeypatch):
    return FauxGitHub(tmp_path, monkeypatch)


def signaler(github, instant, etat, relance_jours=0,
             titre="CI rouge depuis le {depuis} ({duree}) — aujourd'hui : {etat}"):
    return tenir_issue.signaler(
        "exemple/depot", "proprietaire", "publication-echec",
        titre.replace("{etat}", etat), "Hier : {precedent}.", etat,
        relance_jours=relance_jours, maintenant=github.a(instant))


def test_une_issue_naît_assignee_et_mentionne_son_destinataire(github):
    numero, geste = signaler(github, utc(2026, 10, 22, 10, 7), "test")
    assert (numero, geste) == (1, "ouverte")
    issue = github.issues[0]
    assert issue["assignees"] == ["proprietaire"]
    assert issue["labels"] == ["publication-echec"]
    assert issue["body"].startswith("@proprietaire\n")
    assert issue["body"].endswith("<!-- etat: test -->")
    assert issue["title"] == "CI rouge depuis le 22/10 (1 jour) — aujourd'hui : test"


def test_chaque_commentaire_mentionne_date_la_panne_et_nomme_la_precedente(github):
    """Les dates de #126 : ouverte le 22/10, vingt et unième jour le 11/11."""
    signaler(github, utc(2026, 10, 22, 10, 7), "test")
    signaler(github, utc(2026, 11, 10, 13, 2), "Tests pipelines (pytest)")
    _, geste = signaler(github, utc(2026, 11, 11, 12, 19), "test")
    assert geste == "commentée"
    issue = github.issues[0]
    assert issue["title"] == "CI rouge depuis le 22/10 (21 jours) — aujourd'hui : test"
    dernier = issue["comments"][-1]["body"]
    assert dernier.startswith("@proprietaire\n")
    assert "Hier : Tests pipelines (pytest)." in dernier
    assert issue["comments"][0]["body"].endswith("<!-- etat: Tests_pipelines_(pytest) -->")
    assert len(issue["comments"]) == 2


def test_une_issue_deja_ouverte_sans_personne_recoit_son_destinataire(github):
    """Le cas de #126 : ouverte avant ce dispositif, sans assignation ni marqueur."""
    github.etat.write_text(json.dumps([{
        "number": 126, "title": "Échec de la validation CI — le site en ligne n'est pas concerné",
        "body": "Le run a échoué.", "createdAt": "2026-10-22T10:07:36Z", "state": "OPEN",
        "labels": ["publication-echec"], "assignees": [],
        "comments": [{"body": "Le run a échoué.", "createdAt": "2026-11-11T12:19:11Z"}],
    }]))
    numero, geste = signaler(github, utc(2026, 11, 12, 12, 0), "ingest-jorf")
    assert (numero, geste) == (126, "commentée")
    issue = github.issues[0]
    assert issue["assignees"] == ["proprietaire"]
    assert issue["title"] == "CI rouge depuis le 22/10 (22 jours) — aujourd'hui : ingest-jorf"
    # Aucun état antérieur marqué : rien n'est déduit des anciens commentaires.
    assert "Hier : aucun relevé." in issue["comments"][-1]["body"]


def test_une_echeance_inchangee_n_est_relancee_qu_apres_sept_jours(github):
    depart = utc(2026, 11, 11, 11, 23)
    signaler(github, depart, "securitytxt", relance_jours=7, titre="Échéance")
    for jour in range(1, 7):
        _, geste = signaler(github, depart + timedelta(days=jour), "securitytxt",
                            relance_jours=7, titre="Échéance")
        assert geste == "inchangée", f"jour {jour}"
    assert github.issues[0]["comments"] == []
    _, geste = signaler(github, depart + timedelta(days=7), "securitytxt",
                        relance_jours=7, titre="Échéance")
    assert geste == "commentée"
    assert len(github.issues[0]["comments"]) == 1


def test_une_echeance_qui_change_est_dite_le_jour_meme(github):
    depart = utc(2026, 11, 11, 11, 23)
    signaler(github, depart, "securitytxt", relance_jours=7, titre="Échéance")
    _, geste = signaler(github, depart + timedelta(days=1), "tls-20270117+securitytxt",
                        relance_jours=7, titre="Échéance")
    assert geste == "commentée"


def test_un_refus_d_assignation_n_empeche_pas_l_alerte(github, monkeypatch):
    monkeypatch.setenv("FAUX_GH_REFUS_ASSIGNATION", "1")
    numero, geste = signaler(github, utc(2026, 11, 11), "test")
    assert geste == "ouverte"
    issue = github.issues[0]
    assert issue["assignees"] == [] and issue["labels"] == ["publication-echec"]
    assert issue["body"].startswith("@proprietaire\n")  # la mention, elle, reste


def test_une_description_de_label_trop_longue_est_refusee_avant_github(github):
    """Essai réel du 11/11/2026 : 101 caractères, HTTP 422, issue née sans label."""
    with pytest.raises(ValueError, match="101 caractères"):
        tenir_issue.signaler(
            "exemple/depot", "proprietaire", "site-echeances", "Titre", "Corps", "etat",
            description="Certificat, nom de domaine ou security.txt du site en ligne : "
                        "échéance proche ou fichier non conforme",
            maintenant=github.a(utc(2026, 11, 11)))
    assert github.issues == []


def test_les_descriptions_de_labels_ecrites_dans_le_depot_tiennent_en_cent_caracteres():
    sources = list(workflows().values()) + [
        (RACINE / "deploy" / f).read_text(encoding="utf-8")
        for f in ("vigie_site.py", "tenir_issue.py")]
    # Chaînes Python adjacentes recollées, puis toute `description` littérale.
    trouvees = []
    for texte in sources:
        recolle = re.sub(r'"\s*\n\s*"', "", texte)
        trouvees += re.findall(r'(?:--description[", ]+|description=)"([^"]+)"', recolle)
    assert len(trouvees) >= 6, trouvees
    for description in trouvees:
        assert len(description) <= tenir_issue.DESCRIPTION_LABEL_MAX, description


def test_le_retablissement_ferme_et_date_l_episode_dans_le_titre(github):
    signaler(github, utc(2026, 10, 22, 10, 7), "test")
    fermees = tenir_issue.retablir(
        "exemple/depot", "publication-echec", "Rétabli.",
        titre="CI rouge du {depuis} au 12/11 — rétablie",
        maintenant=github.a(utc(2026, 11, 12, 12, 0)))
    assert fermees == [1]
    issue = github.issues[0]
    assert issue["state"] == "CLOSED"
    assert issue["title"] == "CI rouge du 22/10 au 12/11 — rétablie"
    assert tenir_issue.retablir("exemple/depot", "publication-echec", "Rétabli.") == []


def test_la_relance_distincte_part_au_huitieme_jour_puis_une_fois_par_semaine(github):
    def relancer(instant):
        return tenir_issue.relancer(
            "exemple/depot", "proprietaire", "publication-echec", "ci-rouge-persistant",
            "La validation CI est rouge depuis {duree} — relance",
            maintenant=github.a(instant))

    ouverture = utc(2026, 10, 22, 10, 7)
    signaler(github, ouverture, "test")
    assert relancer(ouverture + timedelta(days=6)) is None  # 7e jour : pas encore
    premiere = relancer(ouverture + timedelta(days=7))      # 8e jour
    assert premiere == 2
    relance = github.issues[1]
    assert relance["title"] == "La validation CI est rouge depuis 8 jours — relance"
    assert relance["assignees"] == ["proprietaire"]
    assert relance["body"].startswith("@proprietaire\n") and "#1" in relance["body"]
    assert "- 22/10 : `test`" in relance["body"]
    for jour in range(8, 14):                                # pas une par jour
        assert relancer(ouverture + timedelta(days=jour)) is None
    seconde = relancer(ouverture + timedelta(days=14))
    assert seconde == 3
    etats = {i["number"]: i["state"] for i in github.issues}
    assert etats == {1: "OPEN", 2: "CLOSED", 3: "OPEN"}      # une seule relance ouverte


def test_une_alerte_deja_ancienne_recoit_une_relance_pas_une_par_semaine_ecoulee(github):
    """Rattrapage : #126 a vingt-deux jours le 12/11, une seule relance part."""
    github.etat.write_text(json.dumps([
        {"number": 90, "title": "ancienne relance", "body": "", "state": "CLOSED",
         "createdAt": "2026-09-20T10:00:00Z", "labels": ["ci-rouge-persistant"],
         "assignees": [], "comments": []},
        {"number": 126, "title": "t", "body": "", "state": "OPEN",
         "createdAt": "2026-10-22T10:07:36Z", "labels": ["publication-echec"],
         "assignees": [], "comments": []},
    ]))
    def relancer(instant):
        return tenir_issue.relancer(
            "exemple/depot", "proprietaire", "publication-echec",
            "ci-rouge-persistant", "Relance ({duree})", maintenant=github.a(instant))
    assert relancer(utc(2026, 11, 12, 12, 0)) == 127
    assert relancer(utc(2026, 11, 13, 12, 0)) is None
    assert [i["state"] for i in github.issues] == ["CLOSED", "OPEN", "OPEN"]


# --- 3. Vigie du site en ligne ----------------------------------------------

META_SERVI = (FIXTURES / "meta-servi-2026-11-11.json").read_text(encoding="utf-8")
SECURITY_SERVI = (FIXTURES / "security-servi-2026-11-11.txt").read_text(encoding="utf-8")
RDAP_SERVI = (FIXTURES / "rdap-francetransparence.fr.json").read_text(encoding="utf-8")
# `notAfter` du certificat présenté le 11/11/2026 (openssl s_client).
CERTIFICAT_SERVI = utc(2027, 1, 17, 5, 27)


def lire_servi(url):
    return {vigie_site.URL_META: META_SERVI, vigie_site.URL_SECURITY_TXT: SECURITY_SERVI,
            vigie_site.URL_RDAP: RDAP_SERVI}[url]


def test_le_site_du_11_11_est_dit_fige_depuis_le_08_11():
    assert vigie_site.generation_du_site(META_SERVI) == datetime(
        2026, 11, 8, 4, 26, 1, tzinfo=timezone.utc)
    verdict = vigie_site.verdict_fraicheur(utc(2026, 11, 11, 11, 23), lire_servi)
    assert verdict["anomalie"] is True
    assert verdict["etat"] == "fige-2026-11-08"
    assert verdict["titre"] == (
        "Le site en ligne n'est plus reconstruit depuis le 08/11 (3 jours)")


def test_le_seuil_de_fraicheur_est_de_trente_heures():
    genere = vigie_site.generation_du_site(META_SERVI)
    juste = genere + timedelta(hours=vigie_site.SEUIL_FIGE_HEURES)
    assert vigie_site.verdict_fraicheur(juste, lire_servi)["anomalie"] is False
    apres = juste + timedelta(minutes=1)
    assert vigie_site.verdict_fraicheur(apres, lire_servi)["anomalie"] is True


def test_un_seul_cycle_manque_est_vu_le_jour_meme_a_l_heure_du_cron():
    """L'heure du cron de vigie.yml et le seuil vont ensemble.

    Le site du 08/11 (heure d'hiver, le cas le plus serré : le serveur publie
    une heure plus tard en UTC) doit être sain à l'heure du cron le jour
    même, et figé à l'heure du cron le LENDEMAIN si le cycle du 09 a manqué.
    """
    cron = re.search(r'cron: "(\d+) (\d+) \* \* \*"', (WORKFLOWS / "vigie.yml").read_text())
    minute, heure = int(cron.group(1)), int(cron.group(2))
    jour_meme = utc(2026, 11, 8, heure, minute)
    assert vigie_site.verdict_fraicheur(jour_meme, lire_servi)["anomalie"] is False
    lendemain = jour_meme + timedelta(days=1)
    assert vigie_site.verdict_fraicheur(lendemain, lire_servi)["anomalie"] is True


def test_un_site_injoignable_est_une_anomalie_pas_un_silence():
    def panne(url):
        raise vigie_site.Illisible("injoignable après 3 essais")
    verdict = vigie_site.verdict_fraicheur(utc(2026, 11, 11), panne)
    assert verdict["anomalie"] is True and verdict["etat"] == "injoignable"

    def tronque(url):
        return '{"meta": {"total_sources": 44}}'
    assert vigie_site.verdict_fraicheur(utc(2026, 11, 11), tronque)["etat"] == "injoignable"


def test_le_security_txt_servi_le_11_11_renvoie_vers_les_issues_publiques():
    constats = vigie_site.anomalies_security_txt(SECURITY_SERVI, utc(2026, 11, 11))
    assert len(constats) == 1
    assert "premier `Contact:` n'est pas une adresse de courriel" in constats[0]
    assert "https://github.com/koutakou/france-transparence/issues" in constats[0]


def test_le_security_txt_que_le_depot_engendre_est_conforme_puis_expire():
    """Forme écrite par app/src/app/.well-known/security.txt/route.ts."""
    route = (RACINE / "app/src/app/.well-known/security.txt/route.ts").read_text(encoding="utf-8")
    assert "`Contact: mailto:${CONTACT_EMAIL}`" in route  # la forme attendue vient de là
    site = (RACINE / "app/src/lib/site.ts").read_text(encoding="utf-8")
    courriel = re.search(r'CONTACT_EMAIL = "([^"]+)"', site).group(1)
    conforme = SECURITY_SERVI.replace(
        "Contact: https://github.com/koutakou/france-transparence/issues",
        f"Contact: mailto:{courriel}")
    assert conforme != SECURITY_SERVI
    assert vigie_site.anomalies_security_txt(conforme, utc(2026, 11, 11)) == []
    # `Expires: 2027-08-19T22:03:40Z` : trente jours avant, le fichier est signalé.
    limite = utc(2027, 8, 19, 22, 3) - timedelta(days=vigie_site.SEUIL_SECURITY_TXT_JOURS)
    assert vigie_site.anomalies_security_txt(conforme, limite - timedelta(days=2)) == []
    tardif = vigie_site.anomalies_security_txt(conforme, limite + timedelta(days=1))
    assert len(tardif) == 1 and "expire dans" in tardif[0]


def test_l_echeance_du_domaine_est_lue_au_rdap_du_registre():
    assert vigie_site.echeance_du_domaine(RDAP_SERVI).date().isoformat() == "2029-08-19"
    with pytest.raises(vigie_site.Illisible):
        vigie_site.echeance_du_domaine('{"events": []}')
    with pytest.raises(vigie_site.Illisible):
        vigie_site.echeance_du_domaine("<html>503</html>")


def test_les_echeances_du_11_11_ne_relevent_que_le_security_txt():
    verdict = vigie_site.verdict_echeances(
        utc(2026, 11, 11, 11, 23), lire_servi, lambda hote: CERTIFICAT_SERVI)
    assert verdict["etat"] == "securitytxt"
    assert len(verdict["constats"]) == 1


def test_certificat_et_domaine_sont_signales_sous_leurs_seuils():
    def etat(maintenant):
        return vigie_site.verdict_echeances(
            maintenant, lire_servi, lambda hote: CERTIFICAT_SERVI)["etat"]
    # Certificat : 21 jours pleins restants = encore dans le seuil ; 20 = signalé.
    assert etat(CERTIFICAT_SERVI - timedelta(days=21, hours=1)) == "securitytxt"
    assert etat(CERTIFICAT_SERVI - timedelta(days=20, hours=23)) == "tls-20270117+securitytxt"
    # Domaine (19/08/2029) : signalé sous 60 jours. Le certificat et le
    # security.txt de la fixture sont alors échus depuis longtemps.
    assert "domaine-20290819" not in etat(utc(2029, 6, 20))
    assert "domaine-20290819" in etat(utc(2029, 6, 21))


def test_une_echeance_non_verifiable_est_dite():
    def rdap_en_panne(url):
        if url == vigie_site.URL_RDAP:
            raise vigie_site.Illisible("injoignable après 3 essais")
        return lire_servi(url)
    verdict = vigie_site.verdict_echeances(
        utc(2026, 11, 11), rdap_en_panne, lambda hote: CERTIFICAT_SERVI)
    assert verdict["etat"] == "domaine-illisible+securitytxt"
    assert any("non vérifiable" in c for c in verdict["constats"])


# --- 4. Forme des workflows --------------------------------------------------


def workflows():
    return {f.name: f.read_text(encoding="utf-8") for f in sorted(WORKFLOWS.glob("*.yml"))}


def jobs(texte: str) -> dict[str, str]:
    """Découpe un workflow en jobs (clés à deux espaces sous `jobs:`)."""
    corps = texte.split("\njobs:\n", 1)[1]
    morceaux = re.split(r"(?m)^  ([a-z0-9_-]+):\n", corps)
    return dict(zip(morceaux[1::2], morceaux[2::2]))


def test_aucune_issue_n_est_ouverte_ou_commentee_sans_destinataire():
    """Toute issue passe par deploy/tenir_issue.py, qui assigne et mentionne."""
    for nom, texte in workflows().items():
        code = "\n".join(l for l in texte.splitlines() if not l.lstrip().startswith("#"))
        assert "gh issue create" not in code, nom
        assert "gh issue comment" not in code, nom
        if "tenir_issue.py" in code or "vigie_site.py" in code:
            assert "PROPRIETAIRE: ${{ github.repository_owner }}" in code, nom


def test_les_sentinelles_ne_dependent_pas_du_succes_de_construire():
    """Échéance du cron et issue des 301 : sautées vingt et une fois de suite."""
    publication = jobs(workflows()["publication.yml"])
    porteurs = [nom for nom, corps in publication.items()
                if "Échéance d'extinction du cron" in corps]
    assert porteurs == ["veiller"]
    veiller = publication["veiller"]
    assert "redirections-301" in veiller
    condition = re.search(r"(?m)^    if: (.*)$", veiller).group(1)
    assert "always()" in condition and "schedule" in condition
    assert "needs.construire.result == 'success'" not in condition


def test_l_alerte_part_aussi_quand_construire_est_interrompu():
    alerter = jobs(workflows()["publication.yml"])["alerter"]
    condition = re.search(r"(?m)^    if: (.*)$", alerter).group(1)
    assert "always()" in condition and "cancelled" in condition and "failure" in condition
    assert "pull_request" in condition


def test_la_base_est_mise_en_cache_avant_les_tests_et_sa_cle_porte_les_dependances():
    construire = jobs(workflows()["publication.yml"])["construire"]
    assert construire.index("- name: Mettre la base en cache") < construire.index(
        "- name: Tests pipelines (pytest)")
    cles = re.findall(r"france-db-\$\{\{ hashFiles\(([^)]*)\) \}\}", construire)
    assert len(cles) == 2 and len(set(cles)) == 1, cles  # restauration et sauvegarde
    assert "'pipelines/*.py'" in cles[0] and "'requirements.txt'" in cles[0]


def test_les_workflows_gardent_image_epinglee_actions_epinglees_et_droits_par_job():
    for nom, texte in workflows().items():
        for ligne in texte.splitlines():
            if re.match(r"\s*(- )?uses: ", ligne):
                assert re.search(r"uses: [\w./-]+@[0-9a-f]{40} # v\d", ligne), (nom, ligne)
            if re.match(r"\s*runs-on: ", ligne):
                assert ligne.strip() == "runs-on: ubuntu-24.04", (nom, ligne)
        assert re.search(r"(?m)^permissions:\n  contents: read$", texte), nom
        for job, corps in jobs(texte).items():
            assert re.search(r"(?m)^    timeout-minutes: \d+$", corps), (nom, job)


def test_la_vigie_passe_une_fois_par_jour_et_n_ecrit_que_des_issues():
    texte = workflows()["vigie.yml"]
    assert len(re.findall(r"- cron: ", texte)) == 1
    veiller = jobs(texte)["veiller"]
    droits = re.search(r"(?m)^    permissions:\n((?:      .+\n)+)", veiller).group(1)
    assert sorted(d.strip() for d in droits.splitlines()) == [
        "contents: read", "issues: write"]

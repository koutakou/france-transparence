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
    bot = {"login": "github-actions"}
    print(json.dumps({"body": i["body"], "createdAt": i["createdAt"],
                      "author": {"login": i.get("auteur", "app/github-actions")},
                      "comments": [dict(c, author=c.get("author", bot)) for c in i["comments"]]}))
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
        i["comments"].append({{"body": opt("--body"), "createdAt": maintenant,
                              "author": {{"login": os.environ.get("FAUX_GH_AUTEUR", "github-actions")}}}})
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
        monkeypatch.setenv("DEPOT", "exemple/depot")
        monkeypatch.setenv("PROPRIETAIRE", "proprietaire")
        monkeypatch.setenv("LIEN", "https://exemple/run")

    def commentaire_d_un_tiers(self, numero, instant, corps):
        """Un commentaire écrit par un compte quelconque : le dépôt est public."""
        issues = self.issues
        cible = next(i for i in issues if i["number"] == numero)
        cible["comments"].append({
            "body": corps, "createdAt": instant.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "author": {"login": "un-tiers"}})
        self.etat.write_text(json.dumps(issues))

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
    assert geste == "relancée"
    assert len(github.issues[0]["comments"]) == 1


def test_la_relance_hebdomadaire_tolere_le_retard_du_cron(github):
    """Les cycles planifiés partent à des heures qui varient (11:19 à 13:22 UTC
    du 01/11 au 11/11/2026) : sept jours moins deux heures doivent relancer."""
    depart = utc(2026, 11, 4, 13, 22)
    signaler(github, depart, "securitytxt", relance_jours=7, titre="Échéance")
    _, geste = signaler(github, utc(2026, 11, 10, 13, 0), "securitytxt",
                        relance_jours=7, titre="Échéance")
    assert geste == "inchangée"  # six jours : trop tôt
    _, geste = signaler(github, utc(2026, 11, 11, 11, 19), "securitytxt",
                        relance_jours=7, titre="Échéance")
    assert geste == "relancée"   # sept jours moins deux heures


def test_un_tiers_ne_peut_pas_suspendre_une_relance(github):
    """Dépôt public : n'importe qui commente. Son marqueur ne compte pas."""
    depart = utc(2026, 11, 11, 11, 23)
    signaler(github, depart, "securitytxt", relance_jours=7, titre="Échéance")
    github.commentaire_d_un_tiers(1, depart + timedelta(days=6, hours=23),
                                  "<!-- etat: securitytxt -->")
    _, geste = signaler(github, depart + timedelta(days=7), "securitytxt",
                        relance_jours=7, titre="Échéance")
    assert geste == "relancée"


def test_un_tiers_ne_fait_rien_recopier_dans_le_message_suivant(github):
    signaler(github, utc(2026, 11, 10, 13, 2), "ingest-parlement")
    github.commentaire_d_un_tiers(1, utc(2026, 11, 10, 18, 0),
                                  "<!-- etat: @victime -->\n<!-- etat: ingest-faux -->")
    signaler(github, utc(2026, 11, 11, 12, 19), "test")
    dernier = github.issues[0]["comments"][-1]["body"]
    assert "Hier : ingest-parlement." in dernier
    assert "victime" not in dernier and "ingest-faux" not in dernier


def test_un_etat_ne_peut_porter_ni_mention_ni_lien_ni_balise():
    etat = tenir_issue.normaliser_etat("voir @tiers [ici](https://exemple.fr/x) `code` -->")
    assert not set(etat) & set("@[]/:`<> ")
    # Les noms d'étapes réels du workflow passent tels quels, aux espaces près.
    for nom in ("Tests pipelines (pytest)", "Types app (next typegen + tsc)",
                "Consolider la base (checkpoint WAL → fichier unique)",
                "Ouvrir ou commenter l'issue d'échec", "ingest-hatvp_declarations"):
        assert tenir_issue.normaliser_etat(nom) == nom.replace(" ", "_")
    # Un marqueur hors de cet alphabet n'est pas relu, même signé du bon compte.
    assert tenir_issue._MARQUEUR.findall("<!-- etat: @victime -->") == []


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
    # Sept jours moins deux heures après la première : le retard du cron est toléré.
    seconde = relancer(ouverture + timedelta(days=14) - timedelta(hours=2))
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


# --- 3 bis. Les points d'entrée réels, contre le `gh` factice ---------------


def test_la_commande_signaler_puis_retablir(github, tmp_path, capsys):
    """Ce que les workflows appellent : `python3 deploy/tenir_issue.py …`."""
    corps = tmp_path / "corps.txt"
    corps.write_text("Depuis le {depuis}.\n", encoding="utf-8")
    github.a(utc(2026, 11, 11, 12, 0))
    assert tenir_issue.main([
        "signaler", "--label", "cron-echeance", "--titre", "Extinction ({duree})",
        "--corps-fichier", str(corps), "--etat", "avant-2026-12-14",
        "--relance-jours", "7", "--couleur", "C5DEF5", "--description", "Échéance"]) == 0
    issue = github.issues[0]
    assert issue["labels"] == ["cron-echeance"] and issue["assignees"] == ["proprietaire"]
    assert issue["title"] == "Extinction (1 jour)"
    assert "@proprietaire" in issue["body"] and "<!-- etat: avant-2026-12-14 -->" in issue["body"]
    creation = github.appels("label", "create")[0]
    assert creation[creation.index("--color") + 1] == "C5DEF5"
    assert "--force" in creation  # un label déjà là est mis à jour, pas une erreur
    # Rappelée le jour même avec --relance-jours 7 : rien de neuf à écrire.
    tenir_issue.main([
        "signaler", "--label", "cron-echeance", "--titre", "Extinction ({duree})",
        "--corps-fichier", str(corps), "--etat", "avant-2026-12-14",
        "--relance-jours", "7"])
    assert github.issues[0]["comments"] == []
    assert tenir_issue.main([
        "retablir", "--label", "cron-echeance", "--message", "Échéance repoussée."]) == 0
    issue = github.issues[0]
    assert issue["state"] == "CLOSED"
    assert issue["comments"][-1]["body"] == "Échéance repoussée."


def test_la_commande_retablir_n_exige_pas_de_destinataire(github, monkeypatch):
    """`suivre` ferme sans PROPRIETAIRE dans son environnement."""
    signaler(github, utc(2026, 10, 22, 10, 7), "test")
    monkeypatch.delenv("PROPRIETAIRE")
    assert tenir_issue.main([
        "retablir", "--label", "publication-echec", "--message", "Rétabli.",
        "--titre", "CI rouge du {depuis} au 12/11 — rétablie"]) == 0
    assert github.issues[0]["state"] == "CLOSED"
    assert github.issues[0]["title"] == "CI rouge du 22/10 au 12/11 — rétablie"


def test_la_commande_relancer_puis_la_fermeture_de_la_relance(github):
    signaler(github, utc(2026, 10, 22, 10, 7), "test")
    github.a(datetime.now(timezone.utc))
    # L'issue factice a été ouverte le 22/10/2026 : elle a plus de sept jours
    # à toute date d'exécution de ce test postérieure au 29/10/2026.
    assert tenir_issue.main([
        "relancer", "--label", "publication-echec", "--label-relance",
        "ci-rouge-persistant", "--titre", "Rouge depuis {duree} — relance"]) == 0
    relance = github.issues[1]
    assert relance["labels"] == ["ci-rouge-persistant"]
    assert relance["assignees"] == ["proprietaire"]
    assert re.fullmatch(r"Rouge depuis \d+ jours — relance", relance["title"])
    tenir_issue.main(["retablir", "--label", "ci-rouge-persistant", "--message", "Rétabli."])
    assert [i["state"] for i in github.issues] == ["OPEN", "CLOSED"]


@pytest.fixture
def vigie(github, monkeypatch):
    """La vigie branchée sur ce que le site servait le 11/11/2026."""
    servi = {vigie_site.URL_META: META_SERVI, vigie_site.URL_SECURITY_TXT: SECURITY_SERVI,
             vigie_site.URL_RDAP: RDAP_SERVI}
    monkeypatch.setattr(vigie_site, "telecharger", lambda url: servi[url])
    monkeypatch.setattr(vigie_site, "expiration_du_certificat", lambda hote: CERTIFICAT_SERVI)

    class Vigie:
        def passer(self, instant, *arguments):
            return vigie_site.main(list(arguments), maintenant=github.a(instant))

        def reconstruire(self, instant):
            """Le serveur rebâtit : `genere_le` avance, rien d'autre ne change."""
            assert '"genere_le": "2026-11-08T04:26:01.375Z"' in META_SERVI
            servi[vigie_site.URL_META] = META_SERVI.replace(
                "2026-11-08T04:26:01.375Z", instant.strftime("%Y-%m-%dT%H:%M:%S.000Z"))

        def corriger_security_txt(self):
            servi[vigie_site.URL_SECURITY_TXT] = SECURITY_SERVI.replace(
                "Contact: https://github.com/koutakou/france-transparence/issues",
                "Contact: mailto:adresse@exemple.fr")

        def par_label(self, label):
            return [i for i in github.issues if label in i["labels"]]

    return Vigie()


def test_la_vigie_du_11_11_ouvre_les_deux_issues_et_finit_rouge(vigie, github):
    assert vigie.passer(utc(2026, 11, 11, 11, 23)) == 1
    fige, = vigie.par_label("site-fige")
    assert fige["title"] == "Le site en ligne n'est plus reconstruit depuis le 08/11 (3 jours)"
    assert fige["assignees"] == ["proprietaire"] and fige["body"].startswith("@proprietaire")
    assert "https://exemple/run" in fige["body"]
    echeances, = vigie.par_label("site-echeances")
    assert echeances["assignees"] == ["proprietaire"]
    assert "premier `Contact:`" in echeances["body"]
    assert vigie.par_label("site-fige-persistant") == []


def test_la_vigie_a_blanc_ne_touche_a_rien_et_reste_verte(vigie, github):
    assert vigie.passer(utc(2026, 11, 11, 11, 23), "--a-blanc") == 0
    assert github.issues == [] and github.appels() == []


def test_un_site_fige_garde_le_run_rouge_et_son_titre_compte_depuis_genere_le(vigie, github):
    vigie.passer(utc(2026, 11, 11, 11, 23))
    assert vigie.passer(utc(2026, 11, 12, 11, 23)) == 1
    fige, = vigie.par_label("site-fige")
    assert fige["title"] == "Le site en ligne n'est plus reconstruit depuis le 08/11 (4 jours)"
    assert len(fige["comments"]) == 1                          # un message par jour
    assert vigie.par_label("site-echeances")[0]["comments"] == []  # échéance : pas de redite
    # Neuvième jour de l'issue : relance distincte, datée du gel et non de l'issue.
    vigie.passer(utc(2026, 11, 19, 11, 23))
    relance, = vigie.par_label("site-fige-persistant")
    assert relance["title"] == "Le site en ligne est figé depuis le 08/11 (11 jours) — relance"


def test_le_site_reconstruit_ferme_site_fige_et_le_run_redevient_vert(vigie, github):
    """Une échéance DÉJÀ signalée ne rougit plus le run : seul le gel le faisait."""
    vigie.passer(utc(2026, 11, 11, 11, 23))
    vigie.passer(utc(2026, 11, 19, 11, 23))                 # ouvre la relance
    vigie.reconstruire(utc(2026, 11, 20, 4, 26))
    assert vigie.passer(utc(2026, 11, 20, 11, 23)) == 0
    assert vigie.par_label("site-fige")[0]["state"] == "CLOSED"
    assert vigie.par_label("site-fige-persistant")[0]["state"] == "CLOSED"
    echeances, = vigie.par_label("site-echeances")
    assert echeances["state"] == "OPEN"                     # tenue par son issue
    # Relance hebdomadaire de l'échéance (posée le 11/11, relancée le 19/11) : le run reste vert.
    assert len(echeances["comments"]) == 1


def test_une_echeance_rougit_le_run_quand_elle_apparait_ou_change_pas_ensuite(vigie, github):
    vigie.reconstruire(utc(2026, 11, 11, 4, 26))
    assert vigie.passer(utc(2026, 11, 11, 11, 23)) == 1     # security.txt : signalé ce jour
    assert vigie.par_label("site-fige") == []
    vigie.reconstruire(utc(2026, 11, 12, 4, 26))
    assert vigie.passer(utc(2026, 11, 12, 11, 23)) == 0     # déjà signalé
    # Le certificat (17/01/2027) passe sous son seuil : l'état change, le run rougit.
    vigie.reconstruire(utc(2026, 12, 28, 4, 26))
    assert vigie.passer(utc(2026, 12, 28, 11, 23)) == 1
    echeances, = vigie.par_label("site-echeances")
    assert "Certificat TLS" in echeances["comments"][-1]["body"]
    vigie.reconstruire(utc(2026, 12, 29, 4, 26))
    assert vigie.passer(utc(2026, 12, 29, 11, 23)) == 0


def test_une_echeance_reglee_ferme_son_issue(vigie, github):
    vigie.reconstruire(utc(2026, 11, 11, 4, 26))
    vigie.passer(utc(2026, 11, 11, 11, 23))
    vigie.corriger_security_txt()
    vigie.reconstruire(utc(2026, 11, 12, 4, 26))
    assert vigie.passer(utc(2026, 11, 12, 11, 23)) == 0
    assert vigie.par_label("site-echeances")[0]["state"] == "CLOSED"


def test_une_lecture_est_reessayee_avant_de_dire_le_site_injoignable(monkeypatch):
    pauses, essais = [], []
    monkeypatch.setattr(vigie_site.time, "sleep", pauses.append)

    def coupure_passagere():
        essais.append(1)
        if len(essais) < vigie_site.ESSAIS:
            raise OSError("Connection refused")
        return "lu"
    assert vigie_site._avec_essais(coupure_passagere, "site") == "lu"
    assert pauses == list(vigie_site.PAUSES_ENTRE_ESSAIS_S)
    assert sum(pauses) >= 180                               # plus de trois minutes

    def panne():
        raise OSError("Connection refused")
    with pytest.raises(vigie_site.Illisible, match=f"après {vigie_site.ESSAIS} essais"):
        vigie_site._avec_essais(panne, "site")


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


def cle(job: str, nom: str) -> str:
    """Valeur d'une clé de premier niveau d'un job (`if`, `needs`…)."""
    return re.search(rf"(?m)^    {nom}: (.*)$", job).group(1)


def etapes(job: str) -> dict[str, str]:
    """Les étapes nommées d'un job, chacune avec son texte."""
    morceaux = re.split(r"(?m)^      - name: (.*)\n", job.split("\n    steps:\n", 1)[1])
    return dict(zip(morceaux[1::2], morceaux[2::2]))


def test_l_alerte_part_aussi_quand_un_job_est_interrompu_et_attend_les_sentinelles():
    alerter = jobs(workflows()["publication.yml"])["alerter"]
    assert cle(alerter, "needs") == "[construire, tests-python-3-10, veiller]"
    assert cle(alerter, "if") == (
        "always() && github.event_name != 'pull_request' && "
        "(contains(needs.*.result, 'failure') || contains(needs.*.result, 'cancelled'))")
    appels = etapes(alerter)["Ouvrir ou commenter l'issue d'échec"]
    assert "tenir_issue.py signaler --label publication-echec" in appels
    assert "tenir_issue.py relancer --label publication-echec" in appels
    assert "--label-relance ci-rouge-persistant" in appels


def test_le_cycle_vert_ferme_l_issue_et_sa_relance_seulement_si_tout_est_vert():
    suivre = jobs(workflows()["publication.yml"])["suivre"]
    assert cle(suivre, "needs") == "[construire, tests-python-3-10, veiller]"
    assert cle(suivre, "if") == (
        "github.event_name == 'schedule' && needs.construire.result == 'success' && "
        "needs.tests-python-3-10.result == 'success' && needs.veiller.result == 'success'")
    fermetures = "".join(etapes(suivre).values())
    assert "retablir --label publication-echec" in fermetures
    assert "retablir --label ci-rouge-persistant" in fermetures


def test_les_deux_sentinelles_sont_independantes_l_une_de_l_autre():
    """Un `gh` refusé à l'étape des 301 ne doit pas faire sauter celle du cron."""
    veiller = jobs(workflows()["publication.yml"])["veiller"]
    assert cle(veiller, "needs") == "construire"
    pas = etapes(veiller)
    assert list(pas) == ["Tenir l'issue des redirections 301 d'élus",
                         "Échéance d'extinction du cron (60 jours sans activité)"]
    cron = pas["Échéance d'extinction du cron (60 jours sans activité)"]
    assert cron.startswith("        if: always()\n")
    assert "signaler --label cron-echeance" in cron
    assert "retablir --label cron-echeance" in cron
    assert 'if [ "$age" -lt 45 ]' in cron
    for fichier in ("publication.yml", "vigie.yml"):
        assert fichier in re.search(r"for fichier in (.*); do", cron).group(1)
    r301 = pas["Tenir l'issue des redirections 301 d'élus"]
    assert "signaler --label redirections-301" in r301
    assert "retablir --label redirections-301" in r301


def test_le_job_3_10_tourne_vraiment_sous_3_10_et_joue_pytest():
    publication = jobs(workflows()["publication.yml"])
    job = publication["tests-python-3-10"]
    assert re.search(r'setup-python@[0-9a-f]{40} # v\S+\n        with:\n'
                     r'          python-version: "3\.10"\n', job)
    pas, = etapes(job).values()
    verification = "assert sys.version_info[:2] == (3, 10)"
    assert pas.count(verification) == 2          # l'image, puis la venv
    assert pas.index(".venv/bin/python -c") < pas.index("make test PYTHON=python3")
    assert "make test PYTHON=python3 PYTEST_ARGS=\"-m 'not reseau'\"" in pas
    assert "if:" not in job and "continue-on-error" not in job
    # `construire`, lui, reste sur l'interpréteur de référence.
    assert 'python-version: "3.14"' in publication["construire"]


def test_la_vigie_n_est_a_blanc_que_sur_une_proposition_de_fusion():
    pas, = etapes(jobs(workflows()["vigie.yml"])["veiller"]).values()
    assert re.search(
        r'if \[ "\$EVENEMENT" = "pull_request" \]; then\n'
        r'\s+python3 deploy/vigie_site\.py --a-blanc\n'
        r'\s+else\n\s+python3 deploy/vigie_site\.py\n\s+fi', pas)
    assert "EVENEMENT: ${{ github.event_name }}" in pas


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

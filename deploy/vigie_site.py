"""Vigie externe du site en ligne : le regarder du dehors, une fois par jour.

POURQUOI. Le 11/11/2026, francetransparence.fr servait un export du 08/11 :
trois cycles de reconstruction manqués, et rien ne l'avait dit à personne.
La sonde du serveur vit sur la machine qu'elle sonde ; la validation
quotidienne (`publication.yml`) valide le code et les sources, pas le site —
« un site figé n'est jamais visible dans GitHub Actions », disait le RUNBOOK.
Cette vigie est le regard extérieur qui manquait. Elle lit quatre choses,
toutes publiques, toutes statiques, une requête chacune :

1. `/api/meta.json` : le champ `meta.genere_le` date la reconstruction. Plus
   vieux que SEUIL_FIGE_HEURES → le site est figé (issue `site-fige`).
2. le certificat TLS : moins de SEUIL_TLS_JOURS avant expiration → le
   renouvellement automatique a cessé de fonctionner.
3. l'échéance du nom de domaine, lue au RDAP du registre (pas de `whois` sur
   un runner) : moins de SEUIL_DOMAINE_JOURS.
4. `/.well-known/security.txt` : son premier `Contact:` doit être une adresse
   de courriel (jamais les issues publiques), et son `Expires` doit être à
   plus de SEUIL_SECURITY_TXT_JOURS.

Les points 2 à 4 partagent une issue `site-echeances`. Un contrôle qui ne
peut PAS conclure (serveur injoignable après trois essais, réponse
illisible) est une anomalie, pas un silence : un contrôle muet est
indiscernable d'un contrôle débranché. Chaque contrôle écrit une ligne à
chaque passage, au vert comme au rouge.

Ce n'est pas un traceur : aucun visiteur n'est observé, la vigie ne lit que
ce que le site publie pour tous.

Usage : python3 deploy/vigie_site.py [--a-blanc]
  --a-blanc : joue les contrôles, écrit ce qui serait fait, ne touche à
              aucune issue (vérification d'une proposition de fusion).
Environnement (hors --a-blanc) : GH_TOKEN, DEPOT, PROPRIETAIRE, LIEN (run).
Code de sortie : 0 si tout est sain (et toujours à blanc), 1 si une anomalie
est relevée.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import ssl
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tenir_issue  # noqa: E402

DOMAINE = "francetransparence.fr"
URL_META = f"https://{DOMAINE}/api/meta.json"
URL_SECURITY_TXT = f"https://{DOMAINE}/.well-known/security.txt"
URL_RDAP = f"https://rdap.nic.fr/domain/{DOMAINE}"

# Le serveur reconstruit le site une fois par jour (05:17, heure de Paris).
# 30 h = un cycle de 24 h plus six heures de marge : à l'heure où la vigie
# passe (voir vigie.yml), un seul cycle manqué dépasse déjà le seuil.
SEUIL_FIGE_HEURES = 30
# Le renouvellement automatique intervient trente jours avant l'expiration :
# sous 21 jours, il a échoué depuis plus d'une semaine.
SEUIL_TLS_JOURS = 21
SEUIL_DOMAINE_JOURS = 60
SEUIL_SECURITY_TXT_JOURS = 30

ESSAIS = 3
PAUSE_ENTRE_ESSAIS_S = 20
DELAI_S = 30
AGENT = "france-transparence-vigie (supervision quotidienne du site)"


class Illisible(Exception):
    """Le contrôle n'a pas pu conclure : réponse absente ou inexploitable."""


def lire_instant(texte: str) -> datetime:
    """Instant ISO 8601 → datetime UTC (accepte `Z` et les fractions longues)."""
    trouve = re.match(
        r"^(\d{4}-\d\d-\d\d)[T ](\d\d:\d\d:\d\d)(?:\.\d+)?\s*(Z|[+-]\d\d:?\d\d)?$",
        texte.strip(),
    )
    if not trouve:
        raise Illisible(f"date illisible : {texte[:60]!r}")
    jour, heure, zone = trouve.groups()
    zone = "+0000" if zone in (None, "Z") else zone.replace(":", "")
    return datetime.strptime(f"{jour}T{heure}{zone}", "%Y-%m-%dT%H:%M:%S%z").astimezone(
        timezone.utc
    )


def jours_restants(echeance: datetime, maintenant: datetime) -> int:
    """Jours pleins avant l'échéance (négatif si elle est passée)."""
    return int((echeance - maintenant).total_seconds() // 86400)


# --- Les quatre lectures, pures : un texte et une date en entrée -----------


def generation_du_site(meta_json: str) -> datetime:
    """`meta.genere_le` de /api/meta.json."""
    try:
        valeur = json.loads(meta_json)["meta"]["genere_le"]
    except (ValueError, KeyError, TypeError) as erreur:
        raise Illisible(f"meta.json sans meta.genere_le ({type(erreur).__name__})")
    return lire_instant(str(valeur))


def echeance_du_domaine(rdap_json: str) -> datetime:
    """Événement `expiration` de la réponse RDAP du registre."""
    try:
        evenements = json.loads(rdap_json)["events"]
        dates = [e["eventDate"] for e in evenements if e["eventAction"] == "expiration"]
    except (ValueError, KeyError, TypeError) as erreur:
        raise Illisible(f"réponse RDAP inexploitable ({type(erreur).__name__})")
    if not dates:
        raise Illisible("réponse RDAP sans événement « expiration »")
    return lire_instant(dates[0])


def anomalies_security_txt(texte: str, maintenant: datetime) -> list[str]:
    """Ce qui ne va pas dans le security.txt servi (liste vide = conforme)."""
    champs = [l.strip() for l in texte.splitlines()
              if l.strip() and not l.lstrip().startswith("#")]
    constats = []
    contacts = [l.split(":", 1)[1].strip() for l in champs
                if l.lower().startswith("contact:")]
    if not contacts:
        constats.append("security.txt : aucun champ `Contact:`")
    elif not contacts[0].lower().startswith("mailto:"):
        constats.append(
            "security.txt : le premier `Contact:` n'est pas une adresse de "
            f"courriel (`{contacts[0][:80]}`) — le fichier servi n'est pas "
            "celui que le dépôt engendre"
        )
    expirations = [l.split(":", 1)[1].strip() for l in champs
                   if l.lower().startswith("expires:")]
    if not expirations:
        constats.append("security.txt : aucun champ `Expires:`")
    else:
        reste = jours_restants(lire_instant(expirations[0]), maintenant)
        if reste <= SEUIL_SECURITY_TXT_JOURS:
            constats.append(
                f"security.txt : expire dans {reste} jour(s) "
                f"(`Expires: {expirations[0]}`, seuil {SEUIL_SECURITY_TXT_JOURS})"
            )
    return constats


# --- Réseau ----------------------------------------------------------------


def _avec_essais(lecture, quoi: str):
    """Trois essais espacés : une coupure d'une seconde n'est pas une panne."""
    derniere = None
    for essai in range(1, ESSAIS + 1):
        try:
            return lecture()
        except Illisible:
            raise
        except Exception as erreur:  # réseau, TLS, HTTP : tout ce qui empêche de lire
            derniere = erreur
            print(f"  {quoi} : essai {essai}/{ESSAIS} en échec "
                  f"({type(erreur).__name__}: {str(erreur)[:160]})")
            if essai < ESSAIS:
                time.sleep(PAUSE_ENTRE_ESSAIS_S)
    raise Illisible(f"{quoi} injoignable après {ESSAIS} essais "
                    f"({type(derniere).__name__}: {str(derniere)[:160]})")


def telecharger(url: str) -> str:
    def lecture() -> str:
        requete = urllib.request.Request(url, headers={"User-Agent": AGENT})
        with urllib.request.urlopen(requete, timeout=DELAI_S) as reponse:
            return reponse.read(5_000_000).decode("utf-8", errors="replace")
    return _avec_essais(lecture, url)


def expiration_du_certificat(hote: str) -> datetime:
    """`notAfter` du certificat présenté, chaîne et nom VÉRIFIÉS au passage."""
    def lecture() -> datetime:
        contexte = ssl.create_default_context()
        with socket.create_connection((hote, 443), timeout=DELAI_S) as brut:
            with contexte.wrap_socket(brut, server_hostname=hote) as tls:
                fin = tls.getpeercert()["notAfter"]
        return datetime.fromtimestamp(ssl.cert_time_to_seconds(fin), tz=timezone.utc)
    return _avec_essais(lecture, f"certificat TLS de {hote}")


# --- Verdicts --------------------------------------------------------------


def verdict_fraicheur(maintenant: datetime, lire=telecharger) -> dict:
    """État de la reconstruction : {'anomalie', 'etat', 'titre', 'detail'}."""
    try:
        genere = generation_du_site(lire(URL_META))
    except Illisible as erreur:
        print(f"ÉCHEC fraîcheur : {erreur}")
        return {
            "anomalie": True, "etat": "injoignable",
            "titre": "Le site en ligne ne répond pas à la vigie",
            "detail": f"`{URL_META}` n'a pas pu être lu : {erreur}.",
        }
    heures = (maintenant - genere).total_seconds() / 3600
    print(f"Fraîcheur : site généré le {genere:%d/%m/%Y à %H:%M} UTC, "
          f"il y a {heures:.1f} h (seuil {SEUIL_FIGE_HEURES} h).")
    if heures <= SEUIL_FIGE_HEURES:
        return {"anomalie": False, "etat": "sain", "titre": "",
                "detail": f"site généré le {genere:%d/%m/%Y à %H:%M} UTC"}
    jours = int(heures // 24)
    return {
        "anomalie": True, "etat": f"fige-{genere:%Y-%m-%d}",
        "titre": f"Le site en ligne n'est plus reconstruit depuis le "
                 f"{genere:%d/%m} ({jours} jour{'s' if jours > 1 else ''})",
        "detail": f"`{URL_META}` porte `genere_le` = {genere:%d/%m/%Y à %H:%M} UTC, "
                  f"soit {heures:.0f} h (seuil : {SEUIL_FIGE_HEURES} h). Le site "
                  "sert toujours cet export : ses dates de données restent "
                  "vraies, mais plus rien n'y entre.",
    }


def verdict_echeances(maintenant: datetime, lire=telecharger,
                      certificat=expiration_du_certificat) -> dict:
    """Certificat, domaine, security.txt : {'anomalie', 'etat', 'constats'}."""
    constats: list[str] = []
    cles: list[str] = []

    def echeance(nom: str, cle: str, seuil: int, lecture) -> None:
        try:
            fin = lecture()
        except Illisible as erreur:
            print(f"ÉCHEC {nom} : {erreur}")
            constats.append(f"{nom} : non vérifiable — {erreur}")
            cles.append(f"{cle}-illisible")
            return
        reste = jours_restants(fin, maintenant)
        print(f"{nom} : expire le {fin:%d/%m/%Y}, dans {reste} jour(s) (seuil {seuil}).")
        if reste < seuil:
            constats.append(f"{nom} : expire le {fin:%d/%m/%Y}, dans {reste} "
                            f"jour(s) (seuil : {seuil})")
            cles.append(f"{cle}-{fin:%Y%m%d}")

    echeance("Certificat TLS", "tls", SEUIL_TLS_JOURS, lambda: certificat(DOMAINE))
    echeance(f"Nom de domaine {DOMAINE}", "domaine", SEUIL_DOMAINE_JOURS,
             lambda: echeance_du_domaine(lire(URL_RDAP)))
    try:
        trouves = anomalies_security_txt(lire(URL_SECURITY_TXT), maintenant)
    except Illisible as erreur:
        trouves = [f"security.txt : non vérifiable — {erreur}"]
    print("security.txt servi : " + ("conforme." if not trouves else "; ".join(trouves)))
    if trouves:
        constats.extend(trouves)
        cles.append("securitytxt")
    return {"anomalie": bool(constats), "etat": "+".join(cles) or "sain",
            "constats": constats}


CORPS_FIGE = """{detail}

Relevé par la vigie quotidienne ({lien}), depuis l'extérieur du serveur.

À faire sur le serveur : `ft-etat`, puis `/var/log/france-transparence/deploiement.log` pour l'étape tombée — conduite par famille de panne dans docs/deploiement/RUNBOOK.md § 4. L'issue `publication-echec`, si elle est ouverte, nomme peut-être la même panne amont.

Cette issue se ferme d'elle-même dès que le site est de nouveau reconstruit."""

CORPS_ECHEANCES = """La vigie quotidienne ({lien}) relève, depuis l'extérieur du serveur :

{liste}

Aucune de ces échéances ne se règle depuis le dépôt : voir docs/ACTIONS-HUMAINES.md (certificat et `security.txt` : serveur ; nom de domaine : registrar).

Cette issue est relancée une fois par semaine tant que le constat ne change pas, et se ferme d'elle-même quand il disparaît."""


def main(argv: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    analyseur.add_argument("--a-blanc", action="store_true")
    a = analyseur.parse_args(argv)
    maintenant = datetime.now(timezone.utc)
    fraicheur = verdict_fraicheur(maintenant)
    echeances = verdict_echeances(maintenant)
    anomalie = fraicheur["anomalie"] or echeances["anomalie"]

    if a.a_blanc:
        # Toujours 0 : à blanc, on vérifie que la vigie FONCTIONNE, pas que
        # le site va bien — une proposition de fusion n'y peut rien.
        print(f"À BLANC, aucune issue touchée. site-fige : {fraicheur['etat']} ; "
              f"site-echeances : {echeances['etat']}.")
        return 0

    depot, proprietaire = os.environ["DEPOT"], os.environ["PROPRIETAIRE"]
    lien = os.environ.get("LIEN", "run non précisé")
    if fraicheur["anomalie"]:
        tenir_issue.signaler(
            depot, proprietaire, "site-fige", fraicheur["titre"],
            CORPS_FIGE.format(detail=fraicheur["detail"], lien=lien),
            fraicheur["etat"], relance_jours=0, couleur="B60205",
            description="Le site en ligne n'est plus reconstruit, ou ne répond plus",
        )
        tenir_issue.relancer(
            depot, proprietaire, "site-fige", "site-fige-persistant",
            "Le site en ligne est figé depuis {duree} — relance",
        )
    else:
        tenir_issue.retablir(
            depot, "site-fige",
            f"Rétabli : {fraicheur['detail']} (vigie : {lien}).",
        )
        tenir_issue.retablir(depot, "site-fige-persistant",
                             "Rétabli : le site est de nouveau reconstruit.")
    if echeances["anomalie"]:
        tenir_issue.signaler(
            depot, proprietaire, "site-echeances",
            "Site en ligne : une échéance approche ou un fichier servi n'est pas conforme",
            CORPS_ECHEANCES.format(
                lien=lien, liste="\n".join(f"- {c}" for c in echeances["constats"])),
            echeances["etat"], relance_jours=7, couleur="FBCA04",
            description="Certificat, nom de domaine ou security.txt du site en "
                        "ligne : échéance proche ou fichier non conforme",
        )
    else:
        tenir_issue.retablir(
            depot, "site-echeances",
            f"Rétabli : certificat, nom de domaine et security.txt sont dans "
            f"leurs seuils (vigie : {lien}).",
        )
    return 1 if anomalie else 0


if __name__ == "__main__":
    sys.exit(main())

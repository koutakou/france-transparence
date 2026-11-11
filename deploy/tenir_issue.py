"""Tenir une issue d'alerte : l'ouvrir, la relancer, la fermer — avec un destinataire.

POURQUOI. Le 11/11/2026, la validation quotidienne était rouge depuis vingt
et un jours et le site figé depuis trois ; l'issue d'échec portait vingt
commentaires. Personne ne l'avait vue : le dépôt n'avait aucun abonné,
l'issue aucune personne assignée, aucun commentaire aucune mention. GitHub ne
notifie que les abonnés, les assignés et les personnes mentionnées : une
alerte sans destinataire n'est pas une alerte.

Toute issue tenue ici est donc ASSIGNÉE au propriétaire du dépôt, et chaque
message le MENTIONNE. Trois règles tiennent le reste :

- une issue par label, ouverte tant que le constat demeure, fermée par
  `retablir` quand il cesse ;
- chaque message porte un MARQUEUR D'ÉTAT invisible (`<!-- etat: … -->`).
  Le message suivant lit le précédent : il peut dire « hier : … », et une
  issue de simple échéance ne se répète que si l'état change ou après
  `relance_jours` — un message identique chaque matin cesse d'être lu ;
- au-delà de sept jours, `relancer` ouvre une issue DISTINCTE, une par
  semaine : un nouveau fil ne se confond pas avec l'ancien dans une boîte
  de réception.

Tout passe par la commande `gh` (jeton dans `GH_TOKEN`), sans autre
dépendance. Le titre et le corps acceptent trois jalons, remplacés d'après
l'issue déjà ouverte (ou d'après aujourd'hui si elle naît) :
`{depuis}` (JJ/MM d'ouverture), `{duree}` (« 1 jour », « 21 jours », jour
d'ouverture compris) et `{precedent}` (état du message précédent, ou
« aucun relevé » : rien n'est déduit d'un message sans marqueur).

Usage :
  tenir_issue.py signaler --label L --titre T --corps-fichier F --etat E
                          [--relance-jours N] [--couleur C] [--description D]
  tenir_issue.py retablir --label L --message M [--titre T]
  tenir_issue.py relancer --label L --label-relance R --titre T
Environnement : DEPOT (propriétaire/nom), PROPRIETAIRE (compte à prévenir).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# GitHub refuse (HTTP 422) une description de label de plus de 100
# caractères. Le premier essai réel de la vigie, le 11/11/2026, en portait
# 101 : le label n'a pas été créé, et l'issue est née sans label ni personne
# assignée — donc introuvable au passage suivant, qui en aurait ouvert une
# autre chaque jour.
DESCRIPTION_LABEL_MAX = 100

# Au-delà de cette durée, un constat qui dure reçoit une issue de relance
# distincte, puis une nouvelle par période de même longueur.
RELANCE_DISTINCTE_JOURS = 7

_MARQUEUR = re.compile(r"<!-- etat: ([^ ]*) -->")


def gh(*arguments: str) -> str:
    """Appelle `gh` ; lève si la commande échoue."""
    fait = subprocess.run(
        ["gh", *arguments], check=True, capture_output=True, text=True
    )
    return fait.stdout


def _essayer(*arguments: str) -> bool:
    """Appelle `gh` pour un geste de confort : un échec est dit, pas levé."""
    try:
        gh(*arguments)
        return True
    except subprocess.CalledProcessError as erreur:
        print(f"  (geste non abouti : gh {' '.join(arguments[:3])} … — "
              f"{(erreur.stderr or '').strip()[:200]})")
        return False


def lire_date(texte: str) -> datetime:
    """Date ISO 8601 de l'API GitHub (`2026-10-22T10:07:36Z`)."""
    return datetime.strptime(texte[:19], "%Y-%m-%dT%H:%M:%S").replace(
        tzinfo=timezone.utc
    )


def normaliser_etat(etat: str) -> str:
    """Un état tient en un mot (espaces → `_`) : il est relu dans un commentaire HTML."""
    mot = re.sub(r"\s+", "_", etat.strip()).replace("--", "-").replace(">", "")
    return mot[:120] or "inconnu"


def duree(ouverture: datetime, maintenant: datetime) -> tuple[int, str]:
    """Nombre de jours civils (UTC), jour d'ouverture compris, et son libellé."""
    jours = (maintenant.date() - ouverture.date()).days + 1
    return jours, ("1 jour" if jours == 1 else f"{jours} jours")


def issue_ouverte(depot: str, label: str) -> dict | None:
    """L'issue ouverte la plus ancienne portant ce label, ou None."""
    issues = json.loads(gh(
        "issue", "list", "--repo", depot, "--label", label, "--state", "open",
        "--json", "number,title,createdAt,assignees", "--limit", "50",
    ))
    return min(issues, key=lambda i: i["createdAt"]) if issues else None


def messages(depot: str, numero: int) -> list[dict]:
    """Le corps de l'issue puis ses commentaires, dans l'ordre : date et état."""
    issue = json.loads(gh(
        "issue", "view", str(numero), "--repo", depot,
        "--json", "body,createdAt,comments",
    ))
    suite = []
    for message in [issue, *issue.get("comments", [])]:
        trouve = _MARQUEUR.findall(message.get("body") or "")
        suite.append({
            "date": lire_date(message["createdAt"]),
            "etat": trouve[-1] if trouve else None,
        })
    return suite


def _dernier_etat(suite: list[dict]) -> dict | None:
    return next((m for m in reversed(suite) if m["etat"]), None)


def _remplir(texte: str, depuis: datetime, maintenant: datetime, precedent: str) -> str:
    return (texte.replace("{depuis}", depuis.strftime("%d/%m"))
            .replace("{duree}", duree(depuis, maintenant)[1])
            .replace("{precedent}", precedent.replace("_", " ") or "aucun relevé"))


def signaler(depot: str, proprietaire: str, label: str, titre: str, corps: str,
             etat: str, relance_jours: int = 0, couleur: str = "D93F0B",
             description: str = "", maintenant: datetime | None = None,
             ) -> tuple[int, str]:
    """Ouvre l'issue du label, ou la tient à jour. Rend (numéro, geste).

    `relance_jours` = 0 : un commentaire à chaque appel (panne : chaque jour
    apporte un fait). Sinon : un commentaire seulement si l'état a changé ou
    si le dernier message marqué a au moins `relance_jours` jours. Le titre
    est tenu à jour dans tous les cas : il se lit dans la liste des issues.
    """
    maintenant = maintenant or datetime.now(timezone.utc)
    etat = normaliser_etat(etat)
    existante = issue_ouverte(depot, label)
    depuis = lire_date(existante["createdAt"]) if existante else maintenant
    precedent = None
    if existante:
        precedent = _dernier_etat(messages(depot, existante["number"]))
    titre = _remplir(titre, depuis, maintenant, precedent["etat"] if precedent else "")
    texte = (f"@{proprietaire}\n\n"
             + _remplir(corps, depuis, maintenant, precedent["etat"] if precedent else "")
             + f"\n\n<!-- etat: {etat} -->")

    if not existante:
        if len(description) > DESCRIPTION_LABEL_MAX:
            raise ValueError(
                f"description du label {label} : {len(description)} caractères, "
                f"GitHub en accepte {DESCRIPTION_LABEL_MAX}")
        _essayer("label", "create", label, "--repo", depot, "--color", couleur,
                 "--description", description, "--force")
        base = ["issue", "create", "--repo", depot, "--title", titre, "--body", texte]
        # Du plus complet au plus nu : une issue incomplète vaut mieux que pas
        # d'issue (la mention reste dans le corps). Mais sans son label, le
        # passage suivant ne la retrouvera pas : c'est dit en avertissement.
        for supplement in (["--label", label, "--assignee", proprietaire],
                           ["--label", label], ["--assignee", proprietaire], []):
            try:
                url = gh(*base, *supplement).strip()
                break
            except subprocess.CalledProcessError as erreur:
                print(f"  (création refusée avec {supplement} : "
                      f"{(erreur.stderr or '').strip()[:200]})")
        else:
            raise SystemExit("impossible d'ouvrir l'issue d'alerte")
        numero = int(url.rstrip("/").rsplit("/", 1)[-1])
        manques = [nom for nom, option in (("label", "--label"), ("assignation", "--assignee"))
                   if option not in supplement]
        if manques:
            print(f"::warning::Issue #{numero} ouverte SANS {' ni '.join(manques)} "
                  f"({label}) : à compléter à la main, sinon elle ne sera pas "
                  "retrouvée au prochain passage")
        print(f"Issue #{numero} ouverte ({label}"
              + (f", assignée à {proprietaire}" if "--assignee" in supplement else "")
              + f") : {titre}")
        return numero, "ouverte"

    numero = existante["number"]
    if existante["title"] != titre:
        _essayer("issue", "edit", str(numero), "--repo", depot, "--title", titre)
    if proprietaire not in [a["login"] for a in existante.get("assignees", [])]:
        _essayer("issue", "edit", str(numero), "--repo", depot,
                 "--add-assignee", proprietaire)
    if relance_jours > 0 and precedent and precedent["etat"] == etat:
        age = (maintenant - precedent["date"]).days
        if age < relance_jours:
            print(f"Issue #{numero} ({label}) : état inchangé depuis le "
                  f"{precedent['date']:%d/%m}, pas de nouveau commentaire avant "
                  f"{relance_jours} jours. Titre : {titre}")
            return numero, "inchangée"
    gh("issue", "comment", str(numero), "--repo", depot, "--body", texte)
    print(f"Issue #{numero} ({label}) commentée : {titre}")
    return numero, "commentée"


def retablir(depot: str, label: str, message: str, titre: str = "",
             maintenant: datetime | None = None) -> list[int]:
    """Ferme toute issue ouverte du label. Rend les numéros fermés."""
    maintenant = maintenant or datetime.now(timezone.utc)
    issues = json.loads(gh(
        "issue", "list", "--repo", depot, "--label", label, "--state", "open",
        "--json", "number,createdAt", "--limit", "50",
    ))
    if not issues:
        print(f"Aucune issue {label} ouverte.")
    for issue in issues:
        numero = str(issue["number"])
        if titre:
            _essayer("issue", "edit", numero, "--repo", depot, "--title",
                     _remplir(titre, lire_date(issue["createdAt"]), maintenant, ""))
        gh("issue", "close", numero, "--repo", depot, "--reason", "completed",
           "--comment", message)
        print(f"Issue #{numero} ({label}) fermée.")
    return [i["number"] for i in issues]


def relancer(depot: str, proprietaire: str, label: str, label_relance: str,
             titre: str, maintenant: datetime | None = None) -> int | None:
    """Ouvre une issue de relance DISTINCTE si le constat dure, une par semaine.

    Condition : l'issue du label est ouverte depuis plus de
    RELANCE_DISTINCTE_JOURS jours, et aucune relance n'a été ouverte dans les
    RELANCE_DISTINCTE_JOURS derniers jours (une alerte déjà ancienne quand ce
    code la rencontre reçoit donc UNE relance, pas une par semaine écoulée).
    La relance précédente est fermée : il n'en reste jamais qu'une ouverte.
    """
    maintenant = maintenant or datetime.now(timezone.utc)
    principale = issue_ouverte(depot, label)
    if not principale:
        print(f"Relance : aucune issue {label} ouverte.")
        return None
    ouverture = lire_date(principale["createdAt"])
    jours, libelle = duree(ouverture, maintenant)
    if jours <= RELANCE_DISTINCTE_JOURS:
        print(f"Relance : {label} ouverte depuis {libelle}, pas de relance "
              f"avant le {RELANCE_DISTINCTE_JOURS + 1}e jour.")
        return None
    relances = json.loads(gh(
        "issue", "list", "--repo", depot, "--label", label_relance,
        "--state", "all", "--json", "number,createdAt,state", "--limit", "100",
    ))
    recente = [r for r in relances
               if (maintenant - lire_date(r["createdAt"])).days < RELANCE_DISTINCTE_JOURS]
    if recente:
        print(f"Relance : #{recente[0]['number']} a moins de "
              f"{RELANCE_DISTINCTE_JOURS} jours, rien à ouvrir.")
        return None
    # Les états des derniers messages : la relance dit si c'est une panne
    # qui dure ou une suite de pannes différentes.
    suite = [m for m in messages(depot, principale["number"]) if m["etat"]]
    releve = "\n".join(f"- {m['date']:%d/%m} : `{m['etat'].replace('_', ' ')}`"
                       for m in suite[-RELANCE_DISTINCTE_JOURS:])
    corps = (f"@{proprietaire}\n\n"
             f"L'issue #{principale['number']} est ouverte depuis le "
             f"{ouverture:%d/%m/%Y} ({libelle}) et le constat demeure. Ceci est "
             f"une relance, ouverte à part pour ne pas se perdre dans le fil ; "
             f"le suivi quotidien reste dans #{principale['number']}.\n\n"
             + (f"Derniers états relevés :\n{releve}\n\n" if releve else "")
             + "Cette relance se ferme d'elle-même au rétablissement, ou quand "
             "la suivante la remplace.")
    _essayer("label", "create", label_relance, "--repo", depot, "--color", "B60205",
             "--description", "Relance hebdomadaire : une alerte dure depuis plus "
             "de sept jours", "--force")
    titre = _remplir(titre, ouverture, maintenant, "")
    url = gh("issue", "create", "--repo", depot, "--title", titre, "--body", corps,
             "--label", label_relance, "--assignee", proprietaire).strip()
    numero = int(url.rstrip("/").rsplit("/", 1)[-1])
    for ancienne in relances:
        if ancienne["state"].upper() == "OPEN":
            gh("issue", "close", str(ancienne["number"]), "--repo", depot,
               "--reason", "completed", "--comment", f"Relayée par #{numero}.")
    print(f"Relance #{numero} ouverte ({label_relance}) : {titre}")
    return numero


def main(argv: list[str] | None = None) -> int:
    analyseur = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    gestes = analyseur.add_subparsers(dest="geste", required=True)
    s = gestes.add_parser("signaler")
    s.add_argument("--label", required=True)
    s.add_argument("--titre", required=True)
    s.add_argument("--corps-fichier", required=True)
    s.add_argument("--etat", required=True)
    s.add_argument("--relance-jours", type=int, default=0)
    s.add_argument("--couleur", default="D93F0B")
    s.add_argument("--description", default="")
    r = gestes.add_parser("retablir")
    r.add_argument("--label", required=True)
    r.add_argument("--message", required=True)
    r.add_argument("--titre", default="")
    x = gestes.add_parser("relancer")
    x.add_argument("--label", required=True)
    x.add_argument("--label-relance", required=True)
    x.add_argument("--titre", required=True)
    a = analyseur.parse_args(argv)
    depot = os.environ["DEPOT"]
    if a.geste == "retablir":
        retablir(depot, a.label, a.message, a.titre)
        return 0
    proprietaire = os.environ["PROPRIETAIRE"]
    if a.geste == "signaler":
        corps = Path(a.corps_fichier).read_text(encoding="utf-8").strip()
        signaler(depot, proprietaire, a.label, a.titre, corps, a.etat,
                 a.relance_jours, a.couleur, a.description)
    else:
        relancer(depot, proprietaire, a.label, a.label_relance, a.titre)
    return 0


if __name__ == "__main__":
    sys.exit(main())

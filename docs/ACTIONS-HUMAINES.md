# ACTIONS HUMAINES — ce qui exige physiquement Mickael

État au 20/08/2026. Les deux actions les plus attendues (domaine, e-mail de contact) sont **faites** : le site vit sur https://francetransparence.fr, servi par nginx depuis un serveur dédié, et les pages légales portent une adresse de contact dédiée. Ce fichier ne garde que ce qui reste ouvert.

## Ce qui n'est plus à faire

### Domaine — FAIT

`francetransparence.fr` est enregistré et en service. Sa zone pointe l'apex **et** `www` vers l'adresse IPv4 du serveur dédié (Scaleway Dedibox, Ubuntu 22.04) qui sert le site ; TLS et redirection 301 HTTP→HTTPS sont posés côté nginx.

> **AVERTISSEMENT — l'ancienne consigne DNS de ce fichier est devenue dangereuse.**
> Jusqu'au 20/08/2026, ce document demandait de poser `CNAME www → koutakou.github.io.` et quatre `A` apex vers les adresses de GitHub Pages. **Ne posez pas ces enregistrements.** Ils détourneraient le domaine du serveur qui sert réellement le site, vers un hôte qui n'héberge plus qu'une page de redirection : le site entier deviendrait injoignable et la redirection tournerait en boucle sur elle-même. La zone actuelle est correcte ; la seule raison de la toucher serait un changement de serveur, et alors seule l'adresse IP change.

### E-mail de contact — FAIT

Une adresse dédiée est publiée sur `/mentions-legales` et `/donnees-personnelles` comme canal d'exercice des droits (elle vit dans `app/src/lib/site.ts`, constante `CONTACT_EMAIL`, et le script serveur `ft-localiser` vérifie à chaque déploiement qu'elle n'a pas dérivé). Les issues GitHub restent un canal secondaire.

### Montée en gamme d'hébergement — SANS OBJET

Le site n'est plus sur GitHub Pages : la question de la bande passante Pages (~100 Go/mois) et celle d'un « vrai » serveur pour retrouver des en-têtes HTTP maîtrisés sont réglées par le serveur dédié actuel, qui sert les en-têtes de sécurité complets (HSTS, CSP, `nosniff`, `frame-ancestors`) et pré-compresse le site au build. L'étude comparative de plateformes reste consultable comme document daté : [deploiement/plateformes.md](deploiement/plateformes.md).

## Ce qui reste ouvert

### 1. VPS OVH `51.83.96.83` : à vérifier au manager (peut-être de l'argent dépensé pour rien)

`~/.ssh/config` de la machine de travail référence un VPS OVH `51.83.96.83:24533` (ancien `koutakou.fr`, reverse `ns3147856.ip-51-83-96.eu`). Au **19/08/2026** : ping OK, mais tous ports fermés (24533, 22, 80, 443) — serveur pare-feuté, réinstallé ou réattribué. **Non re-vérifié depuis.** À vérifier sur https://www.ovh.com/manager/ : s'il est encore facturé sans servir, le résilier. Il n'a plus de rôle à jouer dans l'architecture : le site a son serveur.

### 2. Renouvellements à surveiller

Deux échéances peuvent éteindre le site sans prévenir, et aucune ne se règle depuis le dépôt :

- le **nom de domaine** `francetransparence.fr` (renouvellement annuel chez le registrar) ;
- l'**abonnement au serveur dédié** (facturation Scaleway).

Le certificat TLS, lui, se renouvelle automatiquement. Poser un rappel calendaire sur les deux premières échéances coûte cinq minutes et évite la panne la plus bête possible.

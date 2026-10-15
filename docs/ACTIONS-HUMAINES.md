# ACTIONS HUMAINES — ce qui exige physiquement Mickael

État au 20/08/2026, relu le 15/10/2026 (sections 1 et 2 mises à jour ce jour ; section datée du 15/10/2026 ajoutée en tête après l'audit du même jour). Les deux actions les plus attendues (domaine, e-mail de contact) sont **faites** : le site vit sur https://francetransparence.fr, servi par nginx depuis un serveur dédié, et les pages légales portent une adresse de contact dédiée. Ce fichier ne garde que ce qui reste ouvert.

## 15/10/2026 — À faire sur le serveur et sur GitHub

L'audit du 15/10/2026 et les quinze propositions fusionnées le même jour (JOURNAL.md, décisions 35-46) laissent des gestes qu'aucune fusion ne fait : les scripts `ft-*`, nginx, la zone DNS et les réglages GitHub vivent hors du dépôt. Les correctifs fusionnés le 15/10 n'arrivent en ligne qu'au cycle `ft-deploy` du 16/10 : sauf mention contraire, chaque geste serveur ci-dessous se fait **après** ce cycle.

### Serveur

1. **Poser les redirections d'élus** (PR #112 et #113), en régime « courant » de [REDIRECTIONS-ELUS.md](REDIRECTIONS-ELUS.md), donc APRÈS le déploiement de la table par `ft-deploy`, et jamais pendant qu'il tourne. La table passe à 23 lignes : 8 anciennes fiches de députés devenus sénateurs y entrent, et 2 lignes en sortent, dont les cibles ont quitté le Sénat le 27/09 (elles menaient à un 404 depuis le 05/10).
   ```sh
   /root/poser-301-d22.sh --essai
   /root/poser-301-d22.sh
   ```
   Lire ensuite la ligne `ft-controle-301` de `/var/log/france-transparence/deploiement.log`. Attendu : **23/23**. Si `poser-301-d22.sh` ou `ft-controle-301` porte un compte écrit en dur (le lot du 26/08 en avait 17), l'adapter.
2. **Retirer le `security.txt` posé à la main** (PR #114). Il est désormais généré au build (`Contact: mailto:` d'abord, puis le signalement privé GitHub), mais une configuration nginx hors dépôt sert encore l'ancien fichier, qui renvoie vers les issues publiques.
   ```sh
   sudo grep -rn 'security.txt\|well-known' /etc/nginx/
   ```
   Retirer la `location` ou le fichier dédié, **sans toucher à `acme-challenge`**, puis `ft-nginx-reload` (jamais `systemctl reload nginx` seul). Vérifier ensuite : `curl -s https://francetransparence.fr/.well-known/security.txt`, qui doit commencer par `Contact: mailto:`.
3. **Poser deux fois les gardes de la CI dans `ft-deploy`** (PR #119 et #122 ; « toute garde se pose deux fois »). Le `package.json` de l'app est dans le sous-dossier `app/` de l'arbre `/srv/france-transparence/app`.
   - `npm test`, juste après le `npm ci` de l'app et avant `npm run build`, dans le même répertoire et sous le même `set -e`. Essai préalable, sans base, environ 1 s : `cd /srv/france-transparence/app/app && npm test`.
   - Le budget de poids, juste après le build statique, dans le même répertoire : `node scripts/poids-pages.mjs out`, comme le joue la CI. La commande sort en échec si une page dépasse 500 Ko : **à décider** si, côté serveur, elle bloque la bascule ou avertit seulement, pour ne pas geler la publication. Dans les deux cas, garder sa sortie dans le journal du cycle : elle liste les pages les plus lourdes même au vert.
   - Vérifier au même passage que les comptages de fiches des scripts serveur supportent le nouveau sous-dossier `out/elus/annuaire/` (PR #118) : un script qui compte les dossiers de `out/elus` y voit une entrée de plus qu'il n'y a de fiches.
4. **Ne pas mettre en cache les fragments d'appels d'offres** (PR #115 et #122). Le navigateur charge la tranche horaire qu'il vit (`/data/marches/ao-toutes/<heure>.json`, `/data/accueil/ao-cloture/<heure>.json`), et `/data/marches/ao.json` au clic sur une famille. Ces fichiers sont servis aujourd'hui, comme tout `/data/`, avec `Cache-Control: public, max-age=3600, stale-while-revalidate=86400` (relevé le 15/10/2026). Or une tranche du même nom existe dans deux builds successifs, puisque la réserve couvre 48 h : un navigateur peut donc resservir la version de la veille, avec des avis annulés ou modifiés depuis. Poser `Cache-Control: no-cache` (revalidation à chaque chargement, 304 si rien n'a changé) sur ces trois chemins. ⚠️ Un `add_header` dans une `location` fille fait perdre TOUS les `add_header` hérités : y reprendre les en-têtes de sécurité (HSTS, CSP, `nosniff`…). Contrôle : `curl -sI https://francetransparence.fr/data/marches/ao.json`.
5. **HTTPS de `francetransparence.org`** (audit du site, constat 8 ; zone OVH). Le port 443 refuse la connexion, l'apex n'a aucun enregistrement A ni AAAA, et la redirection web OVH de `www` et `m` est en HTTP seul. Elle perd aussi la barre finale du chemin, ce qui ajoute un second 301. Deux voies :
   - pointer l'apex, `www` et `m` vers l'adresse du serveur, émettre un certificat pour les trois noms, et ajouter un bloc nginx qui renvoie `301 https://francetransparence.fr$request_uri` en HTTP comme en HTTPS (plus un CAA `letsencrypt.org`) ;
   - si le `.org` ne sert à rien : supprimer `www` et `m` plutôt que de servir du HTTP seul.
6. **Brotli** (constat 21) : `curl -H 'Accept-Encoding: br'` reçoit l'accueil non compressé, alors que gzip est servi partout. Il faut le module `ngx_brotli` avec `brotli_static on;` et des `.br` produits par `ft-precompresser` à côté des `.gz`, si le module existe pour la version de nginx installée. Gain typique de 15 à 20 % sur HTML et JS.
7. **IPv6** (constat 25, facultatif) : aucun AAAA pour l'apex ni `www`. Si le serveur dispose d'un bloc IPv6 : publier un AAAA et écouter `[::]:80` et `[::]:443`.
8. **Conservation réelle des journaux face à celle que publie `/donnees-personnelles`** (audit CI/docs, constat 17 ; **à trancher en priorité**, car une durée publiée fausse est un manquement à l'information due aux personnes). La page annonce `access.log` (IP complète) conservé 52 jours et `audience.log` (IP tronquée) 400 jours. Elle annonce aussi que la mesure d'audience lit `access.log` pour les périodes qu'`audience.log` ne couvre pas. Le serveur sert le site depuis le 20/08 ; la série d'audience commence pourtant au 15/09. Soit le repli sur `access.log` (fichiers tournés et compressés compris) n'est pas implémenté, soit la conservation réelle diffère de celle publiée. Établir lequel :
   ```sh
   grep -A10 -E 'access|audience' /etc/logrotate.d/nginx /etc/logrotate.d/nginx-audience
   ls -l --time-style=+%F /var/log/nginx/access.log* /var/log/nginx/audience.log*
   ```
   Lire la première ligne du plus ancien fichier de chaque série (`zcat -f <fichier> | head -1`) et la liste des fichiers qu'ouvre le script de série d'audience.
   - Si les journaux remontent bien au 20-24/08 : corriger le script (repli sur les rotations compressées).
   - S'ils commencent plus tard : la page publique et le registre art. 30 doivent dire la date de début réelle et sa cause (proposition de fusion sur `app/src/app/donnees-personnelles/page.tsx`).

   Au même passage :
   - établir pourquoi le 06/10 est une journée partielle dans les journaux ;
   - confirmer que `/var/log/nginx` est hors du périmètre de `ft-sauvegarde-distante`, puisque la page affirme que les journaux ne sont pas sauvegardés à l'extérieur.
9. **Basse priorité** (constats 22 à 24 de l'audit du site) :
   - `/api/` et `/data/` rendent la page 403 brute de nginx : `error_page 403 =404 /404.html;` ;
   - `http://francetransparence.fr/elus` fait deux sauts de 301 : rediriger le bloc `:80` directement vers l'URL canonique ;
   - retirer `interest-cohort=()` de `Permissions-Policy` (FLoC abandonné, Chromium le journalise).

### GitHub

1. **Protection de `main`** : activer `enforce_admins` (Settings → Branches → « Do not allow bypassing the above settings »). Relevé le 15/10/2026 : `enforce_admins: false` et `strict: false`. La PR #106 a été fusionnée avec `construire` en échec, et `main` est tombé dans la minute. Pour une panne amont passagère, relancer le check plutôt que contourner. Activer aussi `strict` (branche à jour avant fusion) est recommandé par l'audit.
2. **Dependabot** : `.github/dependabot.yml` propose les mises à jour, mais les **alertes** et **correctifs de sécurité** ne dépendent que des réglages (Settings → Code security → « Dependabot alerts » et « Dependabot security updates »), relevés désactivés le 15/10/2026.
3. **Label `publication-echec`** : sa description dit encore « le site sert la veille », alors que la CI ne publie rien.
   ```sh
   gh label edit publication-echec --repo koutakou/france-transparence --description "La validation CI a échoué — le site en ligne n'est pas concerné"
   ```
   L'issue #105 sera fermée par le premier cycle planifié vert qui suit la fusion du job `suivre`.
4. **Clé SSH de déploiement** (audit CI/docs, constat 20). La clé dite « dédiée » est une clé d'authentification du COMPTE, sans passphrase : elle donne l'écriture sur tous les dépôts du compte. Le dépôt n'a aucune deploy key (`gh api repos/koutakou/france-transparence/keys` rend `[]`). Remplacer par une vraie clé de déploiement du dépôt, en écriture :
   ```sh
   gh repo deploy-key add <clé publique>.pub --repo koutakou/france-transparence --allow-write --title france-transparence-deploy
   ```
   Supprimer ensuite la clé de compte (`gh ssh-key list` pour son identifiant, puis `gh ssh-key delete <identifiant>`), et adapter `deploy/creer-repo-github.sh` et le RUNBOOK.

### Décisions éditoriales

1. **Tri des particules** (PR #118) : « de Courson » se range aujourd'hui à la lettre D, nom trié tel qu'il s'écrit. Le ranger sous C (particule ignorée) serait une règle d'usage à choisir et à écrire.
2. **Adresse de contact et anonymat de l'éditeur** (audit du site, constat 27 ; PR #114). `/mentions-legales` invoque le régime de l'éditeur non professionnel non identifié (art. 1-1, II LCEN), mais l'adresse de contact publiée sur cette page et sur `/donnees-personnelles` contient le nom et le prénom de l'éditeur. Choisir : une adresse non nominative si l'anonymat est voulu, ou l'identification assumée et un texte simplifié. Ce n'est pas signalé comme une erreur légale, mais comme une incohérence à lever.
3. **Signaler à la HATVP l'organe erroné du dossier `rne-21dc0877411d1a6f`** (PR #123) : Jonathan ABIENSO est, au RNE, 1er vice-président de la CC de l'Ouest Guyanais ; la HATVP le déclare vice-président du « Territoire de la Côte Ouest » (La Réunion), dont les quinze vice-présidents du RNE sont exactement les quinze autres de la page HATVP. Le lien est conservé sur le site ; la valeur amont ne se rectifie pas ici, elle se signale au producteur.
4. **Choix pris au plus prudent par les correctifs, à valider** : date du module Frais (S31) au 11/06/2026, date des refus écrits AN/Sénat (#108) ; deux comparaisons aux enveloppes 2021-2023 retirées, « au moins » 18 mois de marchés dits incomplets, phrase des destinataires du lobbying reformulée (#115).

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

### 1. VPS OVH de l'ancien `koutakou.fr` : à vérifier au manager (peut-être de l'argent dépensé pour rien)

`~/.ssh/config` de la machine de travail référence un VPS OVH (hôte `koutakou.fr` ; adresse et port y figurent, ils ne sont pas recopiés dans ce dépôt public). Au **19/08/2026** : ping OK, mais tous ports fermés — serveur pare-feuté, réinstallé ou réattribué. **Toujours non vérifié au 15/10/2026**, près de deux mois plus tard. À vérifier sur https://www.ovh.com/manager/ : s'il est encore facturé sans servir, le résilier. Il n'a plus de rôle à jouer dans l'architecture : le site a son serveur.

### 2. Renouvellements à surveiller

Deux échéances peuvent éteindre le site sans prévenir, et aucune ne se règle depuis le dépôt :

- le **nom de domaine** `francetransparence.fr` (renouvellement annuel chez le registrar) ;
- l'**abonnement au serveur dédié** (facturation Scaleway).

Le certificat TLS, lui, se renouvelle automatiquement. Poser un rappel calendaire sur ces deux échéances coûte cinq minutes et évite la panne la plus bête possible.

Une troisième échéance n'éteint pas le site mais sa seule sentinelle indépendante : **GitHub désactive les workflows planifiés d'un dépôt public après 60 jours sans activité**. Faute de commit sur `main`, la validation CI quotidienne (`publication.yml`) cesserait de tourner, sans qu'aucune issue ne s'ouvre — un run qui n'a pas lieu n'échoue pas. Toute fusion sur `main` repousse l'échéance. Si GitHub l'a déjà désactivée : `gh workflow enable publication.yml --repo koutakou/france-transparence`, ou le bouton « Enable workflow » de l'onglet Actions.

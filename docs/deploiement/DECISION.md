# DÉCISION D'HÉBERGEMENT — France Transparence

*État courant : 20/08/2026. La décision initiale du 19/08/2026 (GitHub Pages) est conservée plus bas, en § « Historique » : elle explique pourquoi le projet est passé par là, et ce que la migration a coûté et rapporté.*

## Décision

**Le site est un export statique servi directement par nginx, sur un serveur dédié, à son propre nom de domaine.**

- **URL publique** : https://francetransparence.fr — site à la **racine** du domaine, plus de `basePath`.
- **Machine** : serveur dédié Scaleway Dedibox, Ubuntu 22.04. **Aucun process Node en production** : le HTML est pré-rendu au build, nginx ne sert que des fichiers déjà écrits sur disque. Il n'y a pas de serveur applicatif à surveiller, redémarrer ni mettre à jour, et cela ne coûte aucune fonctionnalité — toutes les routes de l'app sont statiques (`force-static`, `dynamicParams = false` sur `/elus/[id]`), l'export contient exactement le même site que le mode serveur.
- **Reconstruction quotidienne** : script `ft-deploy`, déclenché par la minuterie systemd `ft-deploy.timer` à **05:17 heure de Paris** (après les publications de la nuit, et volontairement décalé du cron GitHub Actions de 04:45 UTC pour ne pas les faire coïncider). Enchaînement : `git pull` → contrôle d'identité de déploiement (`ft-localiser`) → ingestion des 13 pipelines → tests → build statique → contrôles de santé du site généré → **bascule atomique** du lien symbolique `current`.
- **Tout ou rien** : le lien `current` ne bascule qu'après les contrôles de santé, par `ln -sfnT` sur un lien temporaire puis `mv -Tf` (un `rename(2)` sur le même système de fichiers). Aucune requête n'est servie « entre deux ». Toute étape en échec interrompt le cycle : la version précédente continue d'être servie sans interruption, et une alerte part.
- **Retour arrière** : les 5 dernières releases sont conservées ; `ft-rollback` rebascule `current` vers l'une d'elles en quelques secondes, sans rebuild.
- **Coût** : un serveur dédié est un abonnement payant. Le « 0 €/mois » de la première mise en ligne n'a plus cours — c'est le prix assumé de ce qui suit.

## Pourquoi ce choix

1. **Des en-têtes HTTP réellement maîtrisés.** C'était la limite structurelle de GitHub Pages : aucune possibilité d'en-tête personnalisé, donc CSP reléguée dans un `<meta http-equiv>` (où `frame-ancestors` est ignoré), ni HSTS ni `X-Content-Type-Options` servis. Sur le serveur, ces en-têtes sont posés par nginx et vérifiables d'un `curl -sI` : `Strict-Transport-Security`, `Content-Security-Policy`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Permissions-Policy`, `Cross-Origin-Opener-Policy`, `Cross-Origin-Resource-Policy`.
2. **Un nom de domaine qui appartient au projet.** L'ancienne adresse portait le nom d'un compte GitHub dans son chemin ; un site civique qui publie des mentions légales et un canal RGPD gagne à ne pas dépendre de l'identifiant d'une plateforme. Redirection 301 HTTP→HTTPS et certificat renouvelé automatiquement (certbot).
3. **La compression est faite une fois, au build, pas à chaque requête.** `ft-precompresser` écrit un `.gz` zopfli à côté de chaque fichier de la release ; nginx le sert tel quel (`gzip_static`, inclus dans le binaire de base). Plus petit qu'un `gzip -9` à la volée, et sans coût CPU par requête.
4. **L'atomicité reste structurelle**, comme sur Pages, mais à un endroit qu'on maîtrise : un lien symbolique qu'on renomme. Pas de bascule de base à orchestrer, pas de redémarrage, aucun état intermédiaire possible.
5. **Le produit est nativement statique-quotidien** : les données ne changent qu'à l'ingestion. Le HTML pré-rendu reste le cache parfait — l'argument qui valait pour Pages vaut toujours, il n'a fait que changer de serveur.

## Ce que la CI GitHub Actions devient

**Elle ne publie plus le site**, et ce n'est pas une perte. Ce qui reste vaut son poids :

- **Validation quotidienne de la chaîne complète** (cron 04:45 UTC) dans un runner éphémère : ingestion des 13 pipelines dans une base **neuve**, tests, build statique, contrôles de santé. C'est un environnement **indépendant du serveur** : si une source amont casse, on l'apprend là avant que `ft-deploy` ne rebuilde à 05:17.
- **Vérification de chaque proposition de fusion avant qu'elle n'atteigne `main`** — c'est `main` que le serveur tire chaque matin : une régression fusionnée est une régression en production le lendemain.
- Le job `deployer` est conditionné à `github.ref == 'refs/heads/main'` (et hors `pull_request`) : un `workflow_dispatch` lancé sur une branche de chantier joue toute la chaîne sans rien publier.
- Un contrôle de santé **échoue si l'export généré contient encore `koutakou.github.io`** : une canonique, un lien de sitemap ou une carte de partage restée sur l'ancienne adresse renverrait les moteurs vers un site qui n'existe plus.

## GitHub Pages : rétrogradé en page de redirection

Publier le site sur les deux hôtes aurait mis en ligne **deux copies identiques** : contenu dupliqué, et autorité de référencement partagée entre deux domaines pour chacune des ~1 066 pages. GitHub Pages ne sachant pas émettre de redirection **301**, les seuls instruments disponibles sont la balise `<link rel="canonical">` et le rafraîchissement méta — les deux sont portés par la page unique de `pages-redirection/`, qui remplace intégralement l'ancienne publication.

Pas de `Disallow: /` dans l'affaire : le `robots.txt` qui fait autorité pour cet hôte appartient au dépôt de pages *utilisateur*, pas à celui-ci ; et interdire la page à un robot l'empêcherait justement d'y lire la canonique.

`pages-redirection/` est le **seul** endroit du dépôt où l'ancienne adresse doit encore figurer.

## Identité de déploiement : paramétrable au build

Un fork ou un miroir change d'adresse et d'hébergeur **sans toucher une ligne de source** :

| Variable | Défaut | Effet |
|---|---|---|
| `NEXT_PUBLIC_SITE_URL` | `https://francetransparence.fr` | `SITE_URL` (`app/src/lib/site.ts`) — d'où dérivent canoniques, `metadataBase`, sitemap et l'adresse du sitemap annoncée dans `robots.txt` |
| `NEXT_PUBLIC_HEBERGEUR_*` | Scaleway SAS / Dedibox | Le bloc « Hébergeur » des mentions légales (`app/src/lib/hebergeur.ts`) : raison sociale, adresse, **téléphone**, forme juridique, service, support |
| `NEXT_PUBLIC_BASE_PATH` | vide | Sous-chemin éventuel, pour un hébergement qui ne serait pas à la racine d'un domaine |

`robots.txt` n'est plus un fichier statique : `app/src/app/robots.ts` le **génère** au build à partir de `SITE_URL`. C'est ce qui empêche l'adresse du sitemap de diverger silencieusement des canoniques — le fichier statique d'avant devait être réécrit à la main à chaque changement de domaine.

Le script serveur `ft-localiser` vérifie **53 contrôles** de cette identité avant chaque build (il ne modifie plus rien) et sort en code 4 si l'un échoue, ce qui interrompt `ft-deploy` : une mention légale fausse est une infraction, et une régression de référencement est invisible à l'œil nu.

## Limites acceptées et suivies

- **Une machine unique** : sa perte est la panne majeure. Elle est couverte par des sauvegardes chiffrées hors-site (la configuration serveur est ce qui ne se reconstruit pas ; la base, elle, se refait par `make ingest`), et par le fait que le site entier est régénérable depuis le dépôt public.
- **Un abonnement à renouveler**, serveur et domaine : deux échéances qui peuvent éteindre le site sans prévenir (voir `../ACTIONS-HUMAINES.md`).
- **L'exploitation est à notre charge** : mises à jour système, TLS, journaux, surveillance — là où Pages ne demandait rien. C'est le prix des en-têtes et du domaine. Les scripts `ft-*` et les minuteries systemd existent pour que ce coût reste une routine (voir `RUNBOOK.md`).
- **Pas de CDN devant le site** : les visiteurs parlent directement à la machine.

## Alternatives écartées

L'étude comparative des plateformes (VPS, PaaS, serverless) a été menée le 19/08/2026 et reste consultable telle quelle, avec ses prix datés et ses sources : [plateformes.md](plateformes.md). Son § 4 (« conteneur vs systemd nu ») recommandait systemd nu pour un serveur unique, avec un timer `OnCalendar=*-*-* 05:17:00` — c'est exactement ce qui a été mis en place.

Rappel des exclusions techniques, toujours valables : serverless écarté sur preuve (bundle Vercel 250 Mo contre une base de 447 Mo, crons ≤ 30 min contre une ingestion bien plus longue, D1 = réécriture complète).

---

## Historique — décision du 19/08/2026 (GitHub Pages)

Le site a d'abord été publié sur **GitHub Pages** (project page, `basePath` `/france-transparence`), reconstruit chaque matin par GitHub Actions, pour une raison qui était alors décisive : **c'était la seule option exécutable sans action humaine.** Seul GitHub était authentifié sur la machine de travail ; toutes les plateformes à disque persistant exigeaient compte + carte bancaire (tier gratuit Fly mort, Railway « post-paid », Render crons sans disque, Koyeb volumes « testing only », Clever FS incompatible better-sqlite3) ; le VPS OVH référencé dans `~/.ssh/config` était injoignable et `koutakou.fr` avait expiré.

Ce déploiement a fonctionné et a été vérifié depuis l'extérieur (23 routes en 200, zéro cookie, 301 HTTPS, atomicité observée — détail dans `../RAPPORT-MISSION.md` § 9). Ses limites étaient documentées dès le premier jour : aucun en-tête personnalisé possible, CSP en `<meta>` avec `frame-ancestors` ignoré, ni HSTS ni `nosniff` servis, `github.io` ne figurant plus dans la liste de préchargement HSTS de Chromium. Ce sont ces limites, et non un incident, qui ont motivé la migration du 20/08/2026 : lever le blocage « pas d'humain disponible » a suffi à rendre le serveur dédié accessible, et le serveur règle chacune d'elles.

Les conséquences techniques assumées à l'époque restent en vigueur, car elles décrivent le produit et non l'hébergeur : `output: 'export'`, aucun `force-dynamic`, fiches élus statiques limitées aux mandats nationaux et exécutifs (≈ 1 053), recherche convertie côté client sur index JSON pré-généré, exports JSON quotidiens en `.json` à la place des routes API paramétriques, filtres et pagination côté client sous un budget de 500 Ko de HTML par page.

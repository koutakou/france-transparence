# Politique de sécurité

## Signaler une vulnérabilité

**En privé, uniquement.** Une faille décrite dans une issue publique est une
faille publiée : tant qu'un correctif n'est pas déployé, la description
elle-même est une arme. N'ouvrez ni issue, ni proposition de fusion, ni
discussion publique pour une vulnérabilité.

Deux canaux :

- **Courriel** : `mickael.faust.pro@proton.me` — le canal de référence.
  Décrivez ce que vous avez constaté, les étapes pour le reproduire et, si
  vous en voyez un, l'impact. Pas besoin de forme particulière : un rapport
  clair vaut mieux qu'un rapport formaté.
- **Signalement privé GitHub** : si l'onglet **Security** du dépôt propose
  « Report a vulnerability », vous pouvez l'utiliser — il aboutit au même
  endroit, avec l'avantage d'un fil de discussion privé outillé.

## Délais

Accusé de réception sous **7 jours** en principe (le projet est maintenu par
une personne, sur son temps propre). Le correctif suit un délai proportionné à
la gravité ; vous serez tenu informé de son avancement et prévenu avant toute
publication. Si vous souhaitez être crédité une fois la faille corrigée,
dites-le : ce sera fait.

## Périmètre

Le périmètre du signalement, c'est **ce que ce dépôt produit** :

- le code de ce dépôt : pipelines d'ingestion (qui téléchargent et parsent
  des fichiers venus de l'extérieur), application web, workflow de CI ;
- le site public https://francetransparence.fr tel qu'il est servi (en-têtes,
  contenu généré, exports JSON) ;
- toute donnée personnelle qui serait exposée au-delà de ce que la page
  [/donnees-personnelles](https://francetransparence.fr/donnees-personnelles/)
  énumère — c'est une vulnérabilité au sens de ce document, même sans
  compromission technique.

**Le serveur qui héberge le site n'est pas un terrain de test d'intrusion.**
La lecture du site et de son code est libre et bienvenue ; en revanche,
tenter d'accéder au système ou de s'y maintenir, d'altérer son fonctionnement
ou ses données sans autorisation est une infraction pénale (articles 323-1 à
323-3 du code pénal, dite loi Godfrain) — l'existence de cette politique de
sécurité ne vaut pas autorisation. Aucun test actif (intrusion, déni de
service, fuzzing du serveur) n'a été autorisé à ce jour ; si vous pensez
qu'un test contrôlé serait utile, écrivez d'abord.

À noter : le site est un export statique servi par nginx, sans base de
données ni code exécuté à la requête. Les classes de failles les plus
plausibles sont donc côté chaîne de fabrication (pipelines qui parsent des
sources externes, dépendances, CI) et côté contenu généré — c'est là que
votre œil est le plus précieux.

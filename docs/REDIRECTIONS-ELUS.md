# Redirections 301 des fiches d'élus fusionnées

Le pipeline P7 (`pipelines/ingest_integrite.py`) retire de `elus` les fiches
`rne-*` qui font double emploi avec une fiche de l'Assemblée ou du Sénat, et
verse leurs mandats sur celle-ci (fonction `_rattraper`, garde-fous dans sa
docstring). Le site cesse alors de publier `/elus/<id-retiré>/`. Ce document dit
comment cette URL continue de mener quelque part.

## La règle n'est pas dans le dépôt, et c'est assumé

La redirection est servie par nginx, depuis
`/etc/nginx/snippets/ft-redirections-elus-pages.conf`, **hors du dépôt**.

Ce n'est pas un oubli. Mesuré : aucun script de `/usr/local/bin/` ni de
`/usr/local/sbin/` n'écrit dans `/etc/nginx` — la règle survit donc au
déploiement de 05:17 comme à `ft-rollback`, et `ft-sauvegarde` l'archive chaque
nuit avec le reste de `/etc/nginx`. *(Depuis le 29/08/2026, `ft-deploy` et
`ft-rollback` la **lisent** — voir « Le contrôle de dérive » plus bas. Aucun des
deux ne l'écrit : le seul script qui écrit dans `/etc/nginx` reste
`poser-301-d22.sh`, lancé à la main.)* L'alternative écartée est la clé `redirects`
de `next.config` : mesurée **inopérante** sous `output: export` dans le Next du
projet — un simple avertissement au journal, aucun fichier produit, et
`ft-deploy` ne contrôle pas les avertissements. Une règle qui a l'air posée et
ne l'est pas est pire que pas de règle.

La contrepartie — une règle non versionnée — est payée par ce couple :

| fichier | rôle |
|---|---|
| `deploy/redirections-elus.tsv` | **la source de vérité**, versionnée : quel id est retiré, vers lequel rediriger |
| `deploy/gen-redirections-elus.sh` | engendre le fichier nginx depuis cette table |

## Poser ou mettre à jour la règle

```sh
/root/poser-301-d22.sh --essai   # tout vérifier, ne RIEN écrire
/root/poser-301-d22.sh           # engendrer, installer, recharger, contrôler
```

🛑 **NE PAS appeler le générateur à la main, et surtout pas depuis
`travail/amont`.** La procédure que ce document a portée jusqu'au 29/08/2026
était celle-ci :

```sh
# ❌ PÉRIMÉE — conservée pour qu'on la reconnaisse, pas pour qu'on la rejoue
sudo -u ftweb git -C /srv/france-transparence/travail/amont pull --ff-only
/srv/france-transparence/travail/amont/deploy/gen-redirections-elus.sh > …
```

Elle est fautive sur **deux** points, chacun mesuré :

1. **Le mauvais arbre.** `travail/amont` est tiré à la main ; l'arbre qui
   PUBLIE est `/srv/france-transparence/app`, que `ft-deploy` avance par
   `git fetch` au début de chaque cycle. Engendrer depuis `amont` peut poser
   une règle issue d'une table **plus récente ou plus ancienne** que le site
   servi, silencieusement, puisque la table existe des deux côtés.
2. **La mauvaise redirection de sortie.** Le vhost inclut
   `snippets/ft-redirections-elus*.conf` — un **joker** que le nom du script
   (`gen-redirections-elus.conf`) ne satisfait pas. Écrire sous ce nom-là
   produit un fichier que nginx **n'inclut jamais**, `nginx -t` reste vert, et
   la régénération n'a aucun effet observable.

`poser-301-d22.sh` lit `app`, écrit au bon chemin, refuse bruyamment si une
cible n'est pas servie, recharge par `ft-nginx-reload` et contrôle les 17 paires
en HTTP réel. Son régime se choisit par `FT_DEPOT` — voir « L'ordre des gestes ».

Le vhost porte, une seule fois, un `include` **à joker** :

```nginx
include snippets/ft-redirections-elus*.conf;
```

Le joker n'est pas un détail de style : `nginx -t` reste vert quand aucun
fichier ne correspond, là où un `map` manquant casserait **tout** nginx.
`ft-nginx-reload` plutôt que `systemctl reload nginx` : un rechargement à chaud
peut être refusé en silence, nginx conservant l'ancienne configuration ;
`ft-nginx-reload` relit `error.log` et le dit.

## Deux blocs par fiche, et pourquoi pas un seul `location =`

Une fiche n'est pas servie par une URL mais par plusieurs. Mesuré sur les
journaux conservés, huit formes portent un identifiant de fiche, dont trois
charges RSC que le routeur client de Next demande
(`__next.elus.$d$id.__PAGE__.txt` — nom **littéral**, le `$d$id` n'est pas
substitué —, `__next._tree.txt`, `__next._index.txt`). Un `location =` exact
n'en couvrirait que deux : les autres rendraient 404 après suppression et
**casseraient la navigation côté client**. D'où, par fiche :

- un `location ^~ /elus/<id>/` qui **préserve le suffixe** (`rewrite … $1`) —
  sans quoi une charge RSC recevrait du HTML là où elle attend du texte ;
- un `location = /elus/<id>` pour la forme **sans barre finale**, que le
  préfixe n'attrape pas : elle retomberait sur la canonicalisation générique du
  vhost, qui teste `-d $document_root$1` et rend 404 dès que le répertoire a
  disparu.

## L'ordre des gestes — DEUX régimes, et le défaut a changé le 27/08/2026

Ce paragraphe prescrivait « **poser la règle AVANT** que le cycle ne retire les
fiches ». **Cet ordre est devenu inapplicable** le jour où `poser-301-d22.sh` a
cessé de lire `travail/amont` pour lire `app`, l'arbre qui publie : à l'instant
« juste avant `ft-deploy` », `app` porte encore la révision du déploiement
**précédent**. Pour un lot introduit par la PR qu'on s'apprête à déployer, le
script engendrerait donc la règle depuis l'**ancienne** table — sans rien dire.

| régime | quand | ce qu'on paie |
|---|---|---|
| **courant** *(défaut)* | **APRÈS** `ft-deploy` | une brève fenêtre de 404 entre la bascule de release et le rechargement de nginx |
| **migration** | AVANT `ft-deploy`, `FT_DEPOT=/srv/france-transparence/travail/amont poser-301-d22.sh` | rien en 404 (le 301 prime même quand la page existe encore), mais tant que la fusion n'est pas déployée les pages `rne-*` portent des déclarations que leurs jumelles ne portent pas encore : poser la règle trop tôt les rend inatteignables |

⚠️ **Ne jamais lancer `poser-301-d22.sh` et `ft-deploy` en même temps.**
`ft-deploy` fait `git reset --hard` puis `git clean -fd` sur `app` ; le script
lit le même arbre, et **aucun verrou n'est partagé entre les deux**. Fenêtre
étroite, geste manuel : il suffit de ne pas les croiser.

## Le contrôle de dérive vit CÔTÉ SERVEUR, et nulle part ailleurs

La chaîne met en jeu **trois** artefacts, pas deux :

| | artefact | où |
|---|---|---|
| ① | la **table** `deploy/redirections-elus.tsv` | ce dépôt, versionnée |
| ② | le **build** `app/out/elus/` | engendré à chaque cycle |
| ③ | le **snippet** `/etc/nginx/snippets/ft-redirections-elus-pages.conf` | hors dépôt, posé à la main |

`R1a` et `R1c` — présents **deux fois**, dans `ft-deploy` et dans
`.github/workflows/publication.yml` — rapprochent ① et ②. Personne ne
rapprochait ① et ③ : une table modifiée et déployée sans rejouer
`poser-301-d22.sh` laissait nginx servir l'ancien lot, et les deux contrôles
disaient « OK ».

Depuis le 29/08/2026, `/usr/local/bin/ft-controle-301` ferme ce trou. Il est
appelé par `ft-deploy` (après la bascule) et par `ft-rollback` (après la
sienne), **avertit sans jamais bloquer**, et journalise son compte à **chaque**
cycle, zéro compris, dans `/var/log/france-transparence/deploiement.log` :

```
[05:27:22] 301 d'élus (S1/S2, ft-deploy) : OK : 301 servis — 17/17 en 301,
           17/17 cibles conformes, 17/17 en 200 après suivi ; snippet 17 = table 17
```

Il mesure l'**effet**, pas le fichier : pour chaque ligne de la table, il exige
`301` sur les deux formes d'URL, **compare `%{redirect_url}` à la jumelle
attendue**, et exige `200` en suivant. La comparaison de cible n'est pas un
raffinement : une cible **permutée** vers une autre fiche réelle rend `301` puis
`200`, un contrôle par le seul code reste **muet**, et le visiteur atterrit sur
la mauvaise fiche en `301` *permanent*, mis en cache par son navigateur.

🛑 **CE CONTRÔLE N'A PAS DE JUMEAU EN CI, ET C'EST VOULU.** C'est une exception
assumée à la règle « toute garde se pose deux fois ». Le runner GitHub n'a ni
`/etc/nginx` ni le site servi, et ce fichier de workflow n'a ni `ssh` ni
`rsync` : il ne peut **ni lire ③ ni l'interroger**. Si tu cherches l'étape
manquante côté CI en lisant `publication.yml`, arrête — il n'y en a pas. Le même
avertissement est écrit dans `publication.yml` et en tête de `ft-controle-301`.

⚠️ Corollaire : `ft-controle-301` n'est **pas versionné**, comme `ft-deploy`,
`ft-rollback` et `poser-301-d22.sh`. **Toute réinstallation du serveur les
efface.** Aucun test de ce dépôt ne les couvre.

## Ce que la règle ne couvre pas

- `/data/elus/interets/<id>.json` — le fragment d'intérêts de la fiche retirée.
  Il disparaît au premier cycle, sans redirection : son contenu réapparaît sous
  l'identifiant de la jumelle, mais l'ancien chemin rend 404. Quinze requêtes
  sur huit jours, toutes automates.
- `sitemap.xml`, `data/recherche-index.json` et `api/elus.json` n'ont **rien à
  purger à la main** : ce sont des artefacts de build régénérés depuis `elus`.

## Le lot n'est pas un invariant

Il se mesure sur l'état de `elus` **du jour** et sur le millésime RNE **du
jour** — le garde-fou « un seul candidat » de `_rattraper` dépend des deux. Le
lot du 26/08/2026 porte 17 identifiants. **Le re-mesurer avant toute reprise**,
en rejouant `upsert_elus` sur une copie de la base servie ; ne jamais recopier
un compte d'une séance à l'autre.

## La paire laissée non appariée est désormais SURVEILLÉE

`rne-b4ef3c48aba5341f` (VIGIER Peter) est volontairement absente de **la table
des 301** — `deploy/redirections-elus.tsv`. Sa ligne est bel et bien dans `elus`
et sa page est servie : patronyme, date de naissance et siège concordent avec
`PA607090`, mais aucune composante de prénom n'est commune, et l'identité y
serait une INFÉRENCE, pas une source d'état civil. **Cette décision ne change
pas.** Ce qui change, c'est qu'on la voit maintenant bouger.

`ingest_parlement` réécrit `nom` et `prenom` des fiches AN/Sénat **sans aucune
condition** à chaque cycle (`UPDATE elus SET nom = ?, prenom = ?, …`, aucun
`COALESCE`), et le `Makefile` place `parlement` **avant** `integrite`. Le jour
où l'Assemblée écrit « Peter » — un seul champ, pas un seul caractère — la clé
`(nom, prénom, date de naissance)` normalisée converge, les deux lignes n'en
font plus qu'une pour `upsert_elus`, la fiche AN gagne son `setdefault`, la
branche de rattrapage n'est plus prise, et le doublon `rne-*` **n'est plus
jamais purgé** tout en restant servi.

`controler_collisions_de_cle` (`pipelines/ingest_integrite.py`) compte pour
cette raison les **clés portées par plus d'une ligne**, et non des suppressions :
dans ce pipeline, la collision est un non-événement — rien n'est inséré,
complété, rattrapé ni supprimé, donc aucun de ses compteurs ne bouge. Il
**avertit et ne bloque pas** : `ft-deploy` est en tout-ou-rien.

Le compte part dans `deploiement.log` à **chaque** cycle, zéro compris —
`elus : … , N collision(s) de clé` — pour qu'un contrôle au vert ne se confonde
jamais avec un contrôle débranché. Au-delà de zéro, chaque collision est nommée :
la clé, les identifiants **dans l'ordre de balayage**, celui que le `setdefault`
retiendrait, et — quand la retenue n'est pas une fiche `rne-*` — le ou les
doublons devenus impurgeables.

### 🛑 Sur CETTE paire, la convergence ne serait pas silencieuse : elle casserait le cycle

Une réfutation adversariale du 28/08/2026 a cassé le motif sur lequel ce
contrôle allait être écrit — « personne d'autre ne peut le voir ». C'est faux, et
la mesure le dit. `ingest_hatvp_declarations` (P15), lancé **après** `integrite`
dans le même cycle, indexe les fiches sur la MÊME clé et se défend déjà : il
écarte les clés partagées et il avertit. Rejoué sur la base servie avec le
prénom de `PA607090` forcé à « Peter » :

    index P15, base servie telle quelle      1039
    index P15, après convergence             1037   (les DEUX clés écartées)
    PA607090 joignable par clé exacte        non
    déclarations HATVP encore rattachées     2, toujours publiées sous « Jean-Pierre »

Ces deux déclarations basculent en « perte de rattachement », et P15 **lève** :
`make ingest` échoue, `ft-deploy` gèle la publication. La convergence n'arriverait
donc pas en silence — elle arrêterait le site à la nuit suivante.

**Ce que ce contrôle apporte quand même**, et c'est sa vraie justification :
- P15 n'indexe que les fiches à mandat `depute`/`senateur`/`president_*` —
  **1 039** lignes le 28/08/2026 sur **36 003**. Les quelque 35 000 autres
  (maires, exécutifs locaux) sont hors de sa vue ; elles sont dans celle-ci ;
- quand la personne en collision ne porte aucune déclaration publiée, P15 se
  contente d'un avertissement et le cycle passe ;
- P15 parle de SON index, jamais de `elus` : il ne nomme ni les identifiants, ni
  celui que le `setdefault` retiendra ;
- il arrive plus tard dans le cycle ; ce contrôle-ci tire plus tôt ;
- le compte part au journal chaque nuit, zéro compris.

### Ce que le contrôle ne fait pas

- Il ne lève **aucune** alerte `ft-alerte`. Le signal vit dans le journal de
  déploiement, et rien ne le relit : `ft-etat` n'y cherche que l'en-tête et
  l'issue du cycle, jamais une ligne `WARNING`. Router ce compte vers le canal
  d'alerte est un chantier distinct, et il devra se poser **deux fois** —
  `ft-deploy` n'est pas versionné.
- Il ne persiste rien : ni ligne `alertes`, ni `meta_sources`. Une convergence
  qui se ferait puis se déferait entre deux cycles ne laisserait qu'une ligne
  de journal, soumise à la rotation.
- Sur une collision entre deux fiches AN/Sénat, il signale la clé mais ne nomme
  pas le dommage : la fiche ignorée ne reçoit aucun mandat RNE et garde ceux de
  la veille.
- Quand la retenue EST une fiche `rne-*`, il n'annonce pas de purge — et il a
  raison de ne pas le faire : `_rattraper` peut encore renoncer sur homonymie.

Mesuré le 28/08/2026 sur la base servie : **0 collision** sur **36 003** lignes,
en ≈ 0,2 s (cinq mesures : 0,20 à 0,24 s ; une seconde série, sur une autre
charge, 0,17 à 0,18 s — le chiffre dérive, le re-mesurer). Contrôle **positif**
joué le même jour sur une copie en mémoire où le prénom de `PA607090` est forcé
à « Peter » : **1 collision**, retenue `PA607090`, doublon condamné
`rne-b4ef3c48aba5341f`, nommé par le journal. L'instrument sait donc rendre
autre chose que zéro.

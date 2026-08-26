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
nuit avec le reste de `/etc/nginx`. L'alternative écartée est la clé `redirects`
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
sudo -u ftweb git -C /srv/france-transparence/travail/amont pull --ff-only
/srv/france-transparence/travail/amont/deploy/gen-redirections-elus.sh \
  > /etc/nginx/snippets/ft-redirections-elus-pages.conf
nginx -t && ft-nginx-reload
```

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

## L'ordre des gestes

**Poser la règle AVANT que le cycle ne retire les fiches.** Mesuré : le 301
prime même quand la page existe encore. L'ordre inverse ouvrirait une fenêtre
de 404 entre la bascule de release et le rechargement de nginx.

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

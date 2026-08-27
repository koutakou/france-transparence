#!/usr/bin/env bash
# Produit, sur la sortie standard, le fichier d'inclusion nginx qui redirige en
# 301 les fiches d'élus retirées par la fusion des doublons vers leur jumelle.
#
# POURQUOI DEUX BLOCS PAR FICHE, ET PAS UN `location =`.
# Chaque fiche est servie par plusieurs chemins, pas un seul. Mesuré sur les
# journaux conservés (21 -> 26/08), huit formes portent un identifiant de fiche,
# dont `/elus/<id>/`, `/elus/<id>/index.txt` et trois charges RSC que le routeur
# client de Next demande (`__next.elus.$d$id.__PAGE__.txt` — nom LITTÉRAL, le
# `$d$id` n'est pas substitué —, `__next._tree.txt`, `__next._index.txt`).
# Un `location =` exact n'en couvrirait que deux : les six autres rendraient 404
# après suppression et casseraient la navigation côté client. D'où :
#
#   · un `location ^~ /elus/<id>/` qui PRÉSERVE LE SUFFIXE (`rewrite … $1`) —
#     sans quoi une charge RSC recevrait du HTML là où elle attend du texte ;
#   · un `location = /elus/<id>` pour la forme SANS barre finale, que le
#     préfixe n'attrape pas : elle retombe sinon sur la canonicalisation
#     générique du vhost, qui teste `-d $document_root$1` et rend 404 dès que
#     le répertoire a disparu. Le `$is_args$args` y est explicite : `return 301`
#     ne reporte PAS la chaîne de requête, là où `rewrite` la conserve seule —
#     mesuré sur instance d'essai, `?_rsc=…` était perdu sur cette forme et
#     conservé sur l'autre. L'asymétrie aurait envoyé une charge RSC sur la
#     page HTML de la jumelle.
#
# Le fichier est appelé par un `include` À JOKER : nginx tolère qu'il soit
# absent (`nginx -t` reste ok avec zéro fichier correspondant), là où un `map`
# manquant casserait TOUT nginx.
#
# Usage : deploy/gen-redirections-elus.sh [table.tsv] > \
#           /etc/nginx/snippets/ft-redirections-elus-pages.conf
set -euo pipefail

TABLE="${1:-$(dirname "$0")/redirections-elus.tsv}"
SITE="https://francetransparence.fr"
# Destination RÉELLE du fichier engendré. Elle est écrite en clair, et NON
# dérivée de "$0" : le vhost inclut `snippets/ft-redirections-elus*.conf`,
# un joker que le nom du SCRIPT (`gen-redirections-elus.conf`) ne satisfait
# pas. La ligne « Régénérer » du fichier engendré l'annonçait pourtant ainsi
# jusqu'au 27/08/2026 : un opérateur qui la suivait écrivait un fichier que
# nginx n'inclut jamais, `nginx -t` restait vert, et la régénération
# PARAISSAIT faite sans avoir eu le moindre effet. Échec silencieux.
CIBLE_NGINX=/etc/nginx/snippets/ft-redirections-elus-pages.conf

[ -r "$TABLE" ] || { echo "table illisible : $TABLE" >&2; exit 1; }

printf '# ENGENDRÉ — ne pas modifier à la main.\n'
printf '# Source de vérité : deploy/redirections-elus.tsv du dépôt.\n'
printf '# Régénérer : deploy/gen-redirections-elus.sh > %s\n' "$CIBLE_NGINX"
printf '#\n'

n=0
while IFS=$'\t' read -r retire conserve personne; do
  case "$retire" in ''|'#'*) continue ;; esac
  [ -n "${conserve:-}" ] || { echo "ligne sans cible : $retire" >&2; exit 1; }
  printf '\n# %s\n' "${personne:-$retire}"
  printf 'location ^~ /elus/%s/ {\n' "$retire"
  printf '    rewrite ^/elus/%s/(.*)$ %s/elus/%s/$1 permanent;\n' "$retire" "$SITE" "$conserve"
  printf '}\n'
  printf 'location = /elus/%s { return 301 %s/elus/%s/$is_args$args; }\n' "$retire" "$SITE" "$conserve"
  n=$((n + 1))
done < "$TABLE"

printf '\n# %d fiche(s) redirigée(s).\n' "$n"
echo "$n fiche(s) redirigée(s)." >&2

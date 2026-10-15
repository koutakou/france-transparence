#!/usr/bin/env bash
# Création REJOUABLE de l'infrastructure GitHub de France Transparence.
# Prérequis : gh authentifié (compte propriétaire), repo git local sur main.
# Le token gh usuel n'a pas le scope `workflow` : le push passe par une clé SSH
# dédiée (ajoutée au compte via l'API — scope admin:public_key), ce qui lève la
# restriction OAuth sur les fichiers .github/workflows/*.
set -euo pipefail

REPO="koutakou/france-transparence"
DESCRIPTION="Transparence de la vie politique française — dashboard 100 % open data officiel, reconstruit chaque matin. https://francetransparence.fr/"
CLE="$HOME/.ssh/id_ed25519_ft_deploy"

cd "$(git rev-parse --show-toplevel)"

# 1. Clé SSH de déploiement dédiée (sans passphrase, jamais commitée)
if [ ! -f "$CLE" ]; then
  ssh-keygen -t ed25519 -N "" -C "france-transparence-deploy" -f "$CLE"
fi
if ! gh ssh-key list | grep -q "france-transparence-deploy"; then
  gh ssh-key add "$CLE.pub" --title "france-transparence-deploy"
fi
export GIT_SSH_COMMAND="ssh -i $CLE -o IdentitiesOnly=yes"

# 2. Repo public
if ! gh repo view "$REPO" >/dev/null 2>&1; then
  gh repo create "$REPO" --public --description "$DESCRIPTION" --disable-wiki
fi

# 3. Remote + push
git remote get-url origin >/dev/null 2>&1 || git remote add origin "git@github.com:$REPO.git"
git push -u origin main

# 4. Label des issues d'échec de la validation CI (utilisé par publication.yml,
#    qui le recrée aussi s'il manque, comme `redirections-301` et `cron-echeance`).
#    La CI ne publie pas le site : son échec ne dit rien du site en ligne.
gh label create publication-echec --repo "$REPO" --color D93F0B \
  --description "La validation CI a échoué — le site en ligne n'est pas concerné" 2>/dev/null || true

# 5. GitHub Pages en mode « GitHub Actions » — pour la seule page de redirection
#    de l'ancienne adresse (pages-redirection/, publiée par pages-redirection.yml)
gh api -X POST "repos/$REPO/pages" -f build_type=workflow 2>/dev/null \
  || gh api -X PUT "repos/$REPO/pages" -f build_type=workflow

echo "OK — repo https://github.com/$REPO ; Pages en mode workflow."
echo "Le push ci-dessus a déclenché la validation CI (publication.yml) ; il ne met pas le site en ligne."
echo "Le site se publie par ft-deploy sur le serveur ; la page de redirection, par : gh workflow run pages-redirection.yml --repo $REPO"

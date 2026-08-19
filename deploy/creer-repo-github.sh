#!/usr/bin/env bash
# Création REJOUABLE de l'infrastructure GitHub de France Transparence.
# Prérequis : gh authentifié (compte propriétaire), repo git local sur main.
# Le token gh usuel n'a pas le scope `workflow` : le push passe par une clé SSH
# dédiée (ajoutée au compte via l'API — scope admin:public_key), ce qui lève la
# restriction OAuth sur les fichiers .github/workflows/*.
set -euo pipefail

REPO="koutakou/france-transparence"
DESCRIPTION="Transparence de la vie politique française — dashboard 100 % open data officiel, reconstruit chaque matin. https://koutakou.github.io/france-transparence/"
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

# 4. Label des issues d'échec de publication (utilisé par publication.yml)
gh label create publication-echec --repo "$REPO" --color D93F0B \
  --description "La publication quotidienne a échoué — le site sert la veille" 2>/dev/null || true

# 5. GitHub Pages en mode « GitHub Actions »
gh api -X POST "repos/$REPO/pages" -f build_type=workflow 2>/dev/null \
  || gh api -X PUT "repos/$REPO/pages" -f build_type=workflow

echo "OK — repo https://github.com/$REPO ; Pages en mode workflow."
echo "Premier déploiement : le push ci-dessus a déclenché le workflow « publication »."

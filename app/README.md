# app/ — le site France Transparence (Next.js, export statique)

La documentation du projet est dans le [README racine](../README.md) : c'est
de là que l'on construit, lance et teste le site.

- `make dev` (depuis la racine) : serveur de développement sur http://localhost:3620 ;
- `make build-static` : l'export statique réellement servi en production (`app/out/`) ;
- le code des pages est dans `src/app/`, les requêtes SQL dans `src/lib/queries/`
  (voir [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md)).

Avant d'écrire du code Next, lire la documentation livrée avec la version
installée (`node_modules/next/dist/docs/`) : la version épinglée dans
`package.json` a ses propres conventions (par exemple, `next build` n'y lance
plus ESLint : `npm run lint` est une étape à part).

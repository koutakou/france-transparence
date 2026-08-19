# STATUS — France Transparence

- **Phase courante** : REPRISE DÉPLOIEMENT — R1 close (décisions 20-21), R2 (durcissement statique) en cours.
- **Cible** : GitHub Pages statique + GitHub Actions cron quotidien — voir docs/deploiement/DECISION.md ; actions optionnelles restantes pour Mickael : docs/ACTIONS-HUMAINES.md.
- **v1 locale (intacte)** : `make ingest` vert (data/france.db 447 Mo, 51 tables, 25 sources) ; `make test` 150/150 ; `npm run build` vert ; 12 pages revues par screenshots.
- **R2 en cours** : 3 agents en worktrees — (A) export statique cœur (next.config, force-dynamic, fiches élus ~1 053, exports .json), (B) pages searchParams → filtres client + allègement < 500 Ko + recherche client, (C) façade publique (mentions légales, données personnelles, robots/sitemap/favicons/OG/404, footer sans ODbL).
- **Rapports R1** : docs/deploiement/{plateformes,machine-locale,exigences-publiques,audit-app}.md.
- **Reprise éventuelle** : lire JOURNAL.md (21 décisions) + docs/deploiement/DECISION.md, merger les branches worktree R2 si présentes, puis R3 = création repo GitHub public + workflows + premier déploiement réel vérifié.

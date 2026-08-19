# STATUS — France Transparence

- **Phase courante** : Phase 2 — ingestion : 11 sous-agents pipelines lancés en parallèle le 19/08/2026 (dév + épreuve sur base jetable via FT_DB_PATH).
- **Fait** : Phase 0 close (9 rapports + critique appliquée → docs/SOURCES.md révisé, 39 sources, 13 pipelines v1) ; Phase 1 close (docs/ARCHITECTURE.md + socle vert : Next 16.3.1/Tailwind 4/better-sqlite3 port 3620, Python 3.14 + duckdb, make test 5/5, build vert).
- **Prochaine étape** : câbler PIPELINES dans le Makefile, `make ingest` réel séquentiel, vérifier les stats de la base, committer ; puis Phase 3 (frontend par vagues, guide docs/DATAVIZ.md).
- **Reprise** : lire JOURNAL.md + docs/SOURCES.md (§5 périmètre v1) + docs/ARCHITECTURE.md ; pipelines dans `pipelines/ingest_<nom>.py`, app dans `app/`.

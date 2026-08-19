# JOURNAL — France Transparence

Décisions numérotées, une ligne chacune. Toute session de reprise lit ce fichier + STATUS.md et continue.

1. 2026-08-19 — Projet créé dans ~/france-transparence, `git init` branche main ; méthode : agent principal orchestrateur pur, sous-agents pour recherche/lecture/écriture lourdes, fichiers = mémoire partagée.
2. 2026-08-19 — Connectivité réseau vérifiée (curl → data.gouv.fr HTTP 200) : les sous-agents testeront les sources par appels réels (curl + WebFetch), jamais de mémoire seule.
3. 2026-08-19 — Phase 0 lancée : 9 sous-agents de recherche web en parallèle (un par axe), sortie `docs/recherche/NN-<axe>.md`, retour ≤ 30 lignes chacun.

# JOURNAL — France Transparence

Décisions numérotées, une ligne chacune. Toute session de reprise lit ce fichier + STATUS.md et continue.

1. 2026-08-19 — Projet créé dans ~/france-transparence, `git init` branche main ; méthode : agent principal orchestrateur pur, sous-agents pour recherche/lecture/écriture lourdes, fichiers = mémoire partagée.
2. 2026-08-19 — Connectivité réseau vérifiée (curl → data.gouv.fr HTTP 200) : les sous-agents testent les sources par appels réels (curl + WebFetch), jamais de mémoire seule.
3. 2026-08-19 — Phase 0 lancée : 9 sous-agents de recherche web en parallèle (un par axe), sortie `docs/recherche/NN-<axe>.md`, retour ≤ 30 lignes chacun.
4. 2026-08-19 — Signature GPG désactivée localement (repo seulement) : `commit.gpgsign` global bloquait les commits en mode non interactif.
5. 2026-08-19 — Recherche livrée (9 rapports + docs/DATAVIZ.md distillé du skill dataviz, palette validée par script pour fond #0a1628).
6. 2026-08-19 — Verdict budget État : AUCUN flux Chorus temps réel ; meilleure fraîcheur = exécution mensuelle M+~6 semaines (SMB DGFiP, au 30/06/2026) ; « en direct » de la maquette sera porté par BOAMP (quotidien) + DECP (quotidien) + JORF (quotidien) + lobbying HATVP (quotidien).
7. 2026-08-19 — Verdict notes de frais : justificatifs parlementaires ni publiés ni communicables (ord. 58-1100, CE mars 2025, refus écrits AN/Sénat 11/06/2026) → module converti en pédagogie chiffrée (enveloppes 2026 exactes, contrôles déontologue, Élysée/Cour des comptes 2024).
8. 2026-08-19 — Contexte politique vérifié : 17e législature en cours, gouvernement Lecornu II (remanié 26/02/2026), renouvellement Sénat 27/09/2026 ; NosDéputés figé 16e lég., NosSénateurs arrêté → open data officiel AN/Sénat + Datan (CSV quotidien).
9. 2026-08-19 — Sous-agent de synthèse lancé : croisement des 9 rapports → docs/SOURCES.md (catalogue, mapping module→sources, promesses intenables, fraîcheurs), puis critique de complétude.

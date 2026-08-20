## Quoi et pourquoi

<!-- Le pourquoi d'abord : quel problème, pourquoi cette solution.
     Une proposition de fusion = un sujet (CONTRIBUTING.md § 3).
     Une correction de DONNÉE ne passe jamais par ici : aucune donnée ne vit
     dans le dépôt — ouvrez une issue « Erreur dans une donnée affichée ». -->

## Vérifications réellement jouées

<!-- Cochez ce que vous avez exécuté vous-même, sur votre machine —
     pas ce qui « devrait passer ». La CI rejouera la chaîne complète. -->

- [ ] `make test` (ou `pytest pipelines/tests -m 'not reseau'` — précisez lequel)
- [ ] `make build` (si l'app est touchée)
- [ ] test ajouté ou mis à jour pour le cas corrigé (si pipeline touché)
- [ ] pipeline concerné rejoué sur une base de travail (`make ingest-<source>`), le cas échéant

## Règles non négociables — relues et respectées

<!-- Détail et pourquoi : CONTRIBUTING.md § 4. Elles font refuser du code
     par ailleurs correct. -->

- [ ] une donnée manquante s'affiche comme manquante, jamais comme un zéro
- [ ] aucune source à clause de partage à l'identique ingérée
- [ ] aucun superlatif, aucune affirmation d'inexistence ou d'antériorité ; « en direct » banni
- [ ] tout module ou source touché date ses données via `meta_sources`
- [ ] pas de juxtaposition de grandeurs de nature différente comme comparables
- [ ] aucune donnée personnelle au-delà de ce qu'énumère /donnees-personnelles
- [ ] aucun chiffre en dur qui dérivera à la prochaine ingestion

## Certificat d'origine

- [ ] chaque commit porte un `Signed-off-by:` (`git commit -s` — DCO 1.1, voir CONTRIBUTING.md § 6)

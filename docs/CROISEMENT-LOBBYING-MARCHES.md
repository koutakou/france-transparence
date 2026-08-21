# Croisement lobbying × marchés publics — méthode, exclusions, limites

Mesures rejouées sur la base réelle le **20/08/2026** (`data/france.db`, 469 Mo).
Sources croisées : **S4** — répertoire HATVP des représentants d'intérêts (AGORA), données au 18/08/2026 — et **S1** — DECP consolidées, données au 18/08/2026.
Code : `app/src/lib/queries/croisement-lobbying-marches.ts`. Affichage : `/lobbying`. Export : `/api/lobbying-marches.json`.

> **Chiffres datés.** Les deux sources sont quotidiennes : tous les volumes et montants de ce
> document (taille de la base, comptes d'entités, de marchés, de SIREN, montants agrégés, fenêtre
> DECP, temps de requête) décrivent la base **le 20/08/2026** et **ont dérivé depuis**. Ce qui ne
> dérive pas — la clé de jointure, les exclusions, la sémantique des montants, les trois périmètres,
> les pièges de plan de requête — est l'objet réel de ce document. Les valeurs du jour sont celles
> qu'affiche `/lobbying` et qu'exporte `/api/lobbying-marches.json`.

## 1. Ce que le croisement dit — et ne dit pas

Être inscrit au répertoire des représentants d'intérêts **et** être titulaire d'un marché public sont deux situations **légales, distinctes et courantes**. L'inscription au répertoire est une obligation de transparence (loi « Sapin II ») ; l'attribution d'un marché résulte d'une procédure d'achat encadrée. Le cumul n'est ni interdit, ni irrégulier, ni suspect en soi, et une entreprise, une association ou une chambre consulaire peut avoir des raisons parfaitement légitimes de figurer au répertoire.

Le module ne produit donc **aucune alerte** et ne qualifie personne. Le seul constat d'irrégularité qu'il relaie est le flag natif `lobby_entites.defaut_declaration` de la HATVP, déjà exploité tel quel par le module Lobbying (§6) — et ce constat porte sur la **déclaration de représentation d'intérêts**, jamais sur le marché.

## 2. La clé de jointure

`lobby_entites.identifiant_national` porte un SIREN quand `type_identifiant = 'SIREN'`. Les 9 premiers caractères d'un SIRET de titulaire DECP sont son SIREN : la jointure est **exacte**, sans rapprochement de noms, donc **sans homonymie**.

```sql
SELECT type_identifiant, COUNT(*) FROM lobby_entites GROUP BY 1 ORDER BY 2 DESC;
-- SIREN|3747   HATVP|203   RNA|118      (total 4068 entités)
SELECT COUNT(*), COUNT(DISTINCT identifiant_national)
FROM lobby_entites WHERE type_identifiant = 'SIREN';
-- 3747|3746
```

Deux pièges, tous deux traités dans le code :

- **3 747 inscriptions pour 3 746 SIREN distincts.** Une entité est inscrite deux fois sous le même SIREN (« MOUVEMENT DES ENTREPRISES DE FRANCE BFC »). Sans `GROUP BY identifiant_national`, ses marchés seraient comptés deux fois.
- **321 entités hors de portée** : 203 identifiées par un identifiant interne HATVP, 118 par un numéro RNA d'association. Elles ne sont pas « sans marchés » — elles sont **non raccordables**, ce qui n'est pas la même chose et doit être dit.

**Alignement des unités, noté le 21/08/2026.** Ce croisement joint par SIREN depuis l'origine (`substr(siret, 1, 9)`), alors que `/marches` classait ses attributaires par établissement : sur les mêmes données, le site comptait en entreprises sur `/lobbying` et en établissements sur `/marches`. `decp_top_acheteurs` et `decp_top_titulaires` portent maintenant une colonne `siren` et regroupent les établissements d'une même personne morale (`docs/SCHEMA-DB.md`, § `decp_top_*`) : les deux pages comptent la même unité. Rien ne change ici — ni la clé, ni les mesures de ce document, qui restent celles du 20/08/2026 — mais deux conséquences sont à connaître :

- La limite du § 8 « **le SIREN identifie une personne morale, pas un groupe** » vaut désormais des deux côtés du site, et non plus de ce seul module.
- **Les deux calculs ne filtrent pas les identifiants de la même façon, et ne portent donc pas exactement la même population.** Le classement de `/marches` n'admet que les identifiants de titulaire **conformes** (exactement 14 chiffres) et écarte les autres en les comptant à part (`decp_titulaires_qualite`). Ici, la conformité de l'identifiant n'est jamais testée : est retenu tout titulaire dont les 9 premiers caractères égalent le SIREN d'une entité inscrite au répertoire. Un identifiant malformé dont les 9 premiers caractères forment malgré tout un SIREN inscrit entre donc dans ce croisement et pas dans le classement — cas réels relevés le 21/08/2026 sur la base servie : `552046955403z` (13 caractères et une lettre), `056501711` (un SIREN nu, sans les 5 chiffres de l'établissement). Une vingtaine de valeurs d'identifiant et quelques dizaines de marchés étaient dans ce cas sur la fenêtre ≈ 24 mois de la base ce jour-là ; ces comptes dérivent. C'est un écart de périmètre assumé, pas un défaut : ici l'appariement porte sur l'entité inscrite au répertoire, et un identifiant d'établissement abîmé qui désigne sans ambiguïté un SIREN inscrit reste une information. Ne pas présenter les deux comptes comme le même.

## 3. Tous les titulaires, pas seulement le premier

`decp_marches.titulaire_siret` ne contient pas « le » titulaire : le pipeline y met `min(titulaire_id)`, le plus petit SIRET du marché (`pipelines/ingest_decp.py`). S'y limiter perd tout co-titulaire dont le SIRET n'est pas le plus petit. On déplie donc `titulaires_json` (liste complète `[{siret, nom}, …]`) avec `json_each`.

| Jointure | Marchés | SIREN titulaires |
|---|---:|---:|
| sur `titulaire_siret` seul | 24 080 | 546 |
| sur **tous** les titulaires (`titulaires_json`) | **25 191** | **566** |

Soit ~1 100 marchés et 20 représentants d'intérêts qu'une jointure naïve laisse tomber.

## 4. Sémantique des montants

Identique à celle du module `/marches` (voir `app/src/lib/queries/marches.ts`) :

- **Écrêtage** : `montant_retenu` plafonné à **100 M€ par marché** (plafond du pipeline, anti-saisie aberrante).
- **Ventilation** : le montant écrêté est **divisé par le nombre de co-titulaires**, convention déjà appliquée par `decp_top_titulaires` — le montant DECP est celui du marché entier, la source ne le ventile pas.
- **Sans montant** : un marché sans montant renseigné est compté dans le nombre de marchés et **exclu de toutes les sommes**. Aucune valeur n'est inventée.
- **Drapeau `montant_suspect`** (anomalie signalée à la source, ou montant au-delà du plafond) : le sous-total « hors suspects » est une **borne basse**, pas « le vrai montant ». Le drapeau n'a pas été audité marché par marché : il écarte aussi des montants exacts.

## 5. Les trois périmètres

Ils ne se confondent jamais dans l'affichage.

| Périmètre | Représentants d'intérêts | Marchés | Montant |
|---|---:|---:|---:|
| Tous marchés | 566 | 25 191 | 66,28 Md€ |
| dont accords-cadres | — | 14 017 | 47,96 Md€ |
| **Hors accords-cadres** (référence) | **435** | **11 174** | **18,32 Md€** |
| Hors AC, hors montants suspects (borne basse) | 431 | 10 723 | 12,04 Md€ |

**Pourquoi exclure les accords-cadres du périmètre de référence** : le montant notifié d'un accord-cadre est un **maximum contractuel**, pas une dépense — l'acheteur peut n'en consommer qu'une fraction, et la source ne publie pas ce qui a été réellement commandé. Les additionner au reste mélange des plafonds et des engagements fermes. Ils ne sont pas cachés pour autant : ils sont chiffrés à part, et la bascule du tableau de `/lobbying` permet de les afficher.

Qualité du total de référence (18,32 Md€, hors accords-cadres) :

| | Marchés | Montant |
|---|---:|---:|
| écrêtés (comptés au plafond, montant réel inconnu) | 39 | 3,61 Md€ |
| drapeau « montant suspect » | 451 | 6,28 Md€ |
| reste en les écartant (**borne basse**) | 10 723 | 12,04 Md€ |
| somme brute, sans aucun écrêtage | — | 33,13 Md€ |
| notifiés sans montant renseigné | 31 | — |

Mise en perspective, à convention de calcul identique : sur les 358 168 marchés hors accords-cadres des DECP (186,92 Md€) et les 95 181 SIREN titulaires d'au moins un marché, les 435 SIREN inscrits au répertoire (0,46 % des titulaires) portent 3,12 % des marchés et **9,80 % du montant notifié**.

## 6. Le sous-ensemble « en défaut de déclaration »

`lobby_entites.defaut_declaration` est un **flag public natif de la HATVP** (vue AGORA `15_exercices.csv`, champ `defautDeclaration`), repris tel quel, sans calcul de délai. Il désigne une entité inscrite sur la liste des représentants d'intérêts **n'ayant pas communiqué à la Haute Autorité tout ou partie des informations exigibles par la loi**, pour au moins un exercice. Base légale (reprise de la table `alertes`, jamais réécrite dans les pages) : loi n° 2016-1691 du 09/12/2016 « Sapin II » — art. 18-3 de la loi n° 2013-907 du 11/10/2013 ; sanctions pénales art. 18-9 et 18-10 ; décret n° 2017-867 du 09/05/2017.

316 entités sont en défaut au 18/08/2026, dont 283 portent un SIREN. Parmi elles :

| Périmètre | Entités | Marchés | Montant |
|---|---:|---:|---:|
| Tous marchés | 27 | 156 | 278,7 M€ |
| Tous marchés, hors montants suspects | 27 | 148 | 191,1 M€ |
| Hors accords-cadres | 15 | 36 | 27,6 M€ |

L'essentiel du montant de ce sous-ensemble tient donc à des accords-cadres : le dire est aussi important que le chiffrer. Le constat porte sur la déclaration, **jamais sur le marché** : rien n'indique une irrégularité dans l'attribution ou l'exécution de ces marchés, et le croisement n'en établit aucune.

## 7. Performance

Le build pré-rend plus de 1 000 pages : une requête lente coûte cher. Mesuré sur la base réelle (585 503 marchés, 662 340 lignes titulaires après dépliage), quatre requêtes jouées **une seule fois** :

| Requête | Temps |
|---|---:|
| couverture SIREN (`lobby_entites` seule) | 5 ms |
| dénominateur DECP hors accords-cadres | 233 ms |
| SIREN titulaires distincts (dépliage `json_each`) | 957 ms |
| agrégats du croisement | 1 049 ms |
| une ligne par représentant d'intérêts titulaire (566) | 906 ms |
| **total** | **3,15 s** |

Deux pièges de plan de requête, vérifiés en `EXPLAIN QUERY PLAN` et documentés dans le code :

1. **La liste des SIREN doit être une sous-requête**, pas la table `lobby_entites` : celle-ci n'a pas d'index sur `identifiant_national`, et SQLite ne construit son `AUTOMATIC COVERING INDEX` que sur une sous-requête matérialisée. Sans cela, la même requête passe de ~1 s à **4 min 56 s** (mesuré).
2. **L'ordre des boucles doit être forcé par `CROSS JOIN`**, `decp_marches` en tête. Laissé libre, SQLite met la liste des SIREN en boucle externe et rejoue `json_each` 3 746 fois — la requête ne rend pas la main.

Les deux passes lourdes lisent la même jointure ; elles restent séparées parce que la connexion est ouverte en `query_only = ON` (`app/src/lib/db.ts`) : **aucune table temporaire n'est possible**, y compris `CREATE TEMP TABLE`.

## 8. Limites connues

- **Fenêtre DECP ≈ 24 mois** (2024-08-21 → 2026-08-18 dans cette base), avec une latence légale de publication pouvant aller jusqu'à deux mois : les mois récents sont incomplets. Le croisement n'est donc pas un historique.
- **Marchés notifiés = engagements contractuels, pas des paiements.** Un marché notifié peut n'être jamais exécuté.
- **321 entités du répertoire (7,9 %) non raccordables** faute de SIREN (§2) : le croisement est un plancher, pas un compte exhaustif.
- **Le SIREN identifie une personne morale, pas un groupe.** Une filiale titulaire d'un marché n'est pas rattachée à la maison mère inscrite au répertoire, et réciproquement : les grands groupes sont donc mécaniquement sous-comptés.
- **Aucun lien de causalité n'est établi ni suggéré** entre les activités de représentation d'intérêts déclarées et les marchés obtenus. Les deux colonnes du tableau viennent de deux registres indépendants et sont affichées côte à côte, rien de plus.
- **Le drapeau `montant_suspect` n'est pas audité** ligne à ligne : la borne basse écarte aussi des montants exacts.
- Le montant d'un marché **n'est pas ventilé à la source** entre co-titulaires : la répartition à parts égales est une convention du site, pas une donnée.

## 9. Où ça vit

| | |
|---|---|
| Requêtes | `app/src/lib/queries/croisement-lobbying-marches.ts` |
| Page | `app/src/app/lobbying/page.tsx` (section `SectionCroisement`) |
| Bascule accords-cadres | `app/src/components/client/TitulairesLobbyistes.tsx` |
| Export JSON | `app/src/app/api/lobbying-marches.json/route.ts` |

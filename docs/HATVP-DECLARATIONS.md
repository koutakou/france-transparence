# Contenu des déclarations d'intérêts HATVP (S15) — périmètre, droit, limites

Pipeline : `pipelines/ingest_hatvp_declarations.py` (P15).
Tests : `pipelines/tests/test_hatvp_declarations.py`.
Requêtes : `app/src/lib/queries/declarations.ts`.
Affichage : `app/src/components/client/InteretsDeclares.tsx`, sur `/elus/[id]`.

Toutes les mesures de ce document ont été prises le **20/08/2026** sur le
fichier amont du **14/08/2026**. Elles sont reproductibles : chaque chiffre
sort soit du pipeline lui-même (`meta_sources.notes`), soit d'une requête sur
`data/france.db`.

> **Chiffres datés.** Les volumétries ci-dessous (nombre de fiches publiées,
> fiches appariées, fiches non appariées, déclarations rattachées) décrivent la
> base **le 20/08/2026** et **dérivent à chaque ingestion** : le parc de fiches
> suit le répertoire des élus, le fichier amont est republié chaque semaine. Ce
> qui ne dérive pas — la clé d'appariement, les raisons des non-appariements,
> les garde-fous d'affichage — est l'objet réel de ce document. Les valeurs du
> jour se lisent sur le site et sur sa page `/donnees`.

---

## 1. Source

| | |
|---|---|
| Identifiant interne | **S15** (catalogué dans `docs/SOURCES.md`) |
| URL | `https://www.hatvp.fr/livraison/merge/declarations.xml` |
| Taille | 88 825 812 octets (constatés) |
| `Last-Modified` | `Fri, 14 Aug 2026 10:03:28 GMT` |
| Contenu | 6 611 déclarations en texte intégral structuré |
| Licence | Licence Ouverte Etalab (`fr-lo`) |

⚠ L'URL `https://www.hatvp.fr/livraison/opendata/declarations.xml`, que l'on
trouve encore citée ailleurs, répond **404**. Un test réseau
(`test_reseau_url_reelle_et_ancienne_url_morte`) le vérifie à chaque exécution
de la suite, précisément pour qu'on ne « corrige » pas l'URL du pipeline vers
celle-là.

### Cadence retenue : hebdomadaire

data.gouv.fr annonce la ressource comme `punctual`, ce qui ne calibre aucun
seuil de fraîcheur — une source qui n'a pas de cadence attendue n'est jamais
« en retard », et une panne amont passerait inaperçue. Le fait observable dit
autre chose :

```
declarations.xml  Last-Modified: Fri, 14 Aug 2026 10:03:28 GMT
liste.csv (S14)   Last-Modified: Fri, 14 Aug 2026 10:03:29 GMT
```

**Une seconde d'écart** : les deux fichiers sortent de la même génération. S14
est hebdomadaire et calibré 10/18 jours calendaires ; S15 hérite de la même
cadence et des mêmes seuils. Un test réseau
(`test_reseau_meme_generation_que_liste_csv`) surveille que les deux dates ne
divergent pas.

### Fraîcheur : pourquoi le `Last-Modified` et non la date interne

Le projet préfère partout ailleurs la date de la donnée la plus récente
réellement ingérée (`docs/SOURCES.md` §0.2). Ici, cette date serait
`max(dateDepot)` = **28/07/2026**, pour un fichier régénéré le 14/08/2026.
L'écart de dix-sept jours ne mesure pas la fraîcheur du fichier : il mesure le
**délai de publication de la HATVP** (dépôt, instruction, mise en ligne).
S'en servir ferait passer pour « en retard » une source parfaitement à jour.
Le `Last-Modified` est donc retenu comme `date_donnees`, et
`max(dateDepot)` est consigné dans `meta_sources.notes` pour que ce délai
reste visible plutôt que d'être effacé.

---

## 2. Licence et fondement de la publication

La licence `fr-lo` est la **Licence Ouverte Etalab**, sans clause de partage à
l'identique : nos propres restitutions restent republiables en LO 2.0, licence
sous laquelle le site republie ses agrégats.

La publication amont elle-même découle des lois n° 2013-906 et n° 2013-907 du
11 octobre 2013 relatives à la transparence de la vie publique, qui rendent
les déclarations d'intérêts publiées « librement réutilisables ».

---

## 3. Périmètre : ce qui est ingéré, ce qui ne l'est pas

### 3.1 Liste blanche — sept rubriques, et seulement pour les DI et DIA

| Balise XML | Clé interne | Intitulé affiché |
|---|---|---|
| `mandatElectifDto` | `mandat_electif` | Mandats électifs et fonctions électives |
| `participationDirigeantDto` | `dirigeant` | Participations aux organes dirigeants d'un organisme |
| `participationFinanciereDto` | `participation_financiere` | Participations financières directes dans le capital d'une société |
| `activProfCinqDerniereDto` | `activite_5ans` | Activités professionnelles des cinq dernières années |
| `activConsultantDto` | `consultant` | Activités de consultant |
| `fonctionBenevoleDto` | `benevole` | Fonctions bénévoles susceptibles de faire naître un conflit d'intérêts |
| `observationInteretDto` | `observation` | Observations |

### 3.2 Liste noire patrimoniale — le raisonnement juridique

Quatorze balises sont refusées : `immeubleDto`, `sciDto`,
`valeursEnBourseDto`, `valeursNonEnBourseDto`, `assuranceVieDto`,
`comptesBancaireDto`, `bienDiverDto`, `vehiculeDto`, `fondDto`,
`autreBienDto`, `bienEtrangerDto`, `passifDto`, `observationPatrimoineDto`,
`revenuMandatDto`.

**Pourquoi.** La déclaration de situation patrimoniale d'un parlementaire
relève de l'**article LO 135-2 du code électoral** : elle n'est consultable
qu'en préfecture, par les seuls électeurs inscrits dans le département, sans
possibilité de copie, et **toute publication ou divulgation de son contenu est
punie de 45 000 € d'amende**. Ce n'est pas une donnée « sensible » au sens
d'une politique interne : c'est une interdiction pénale.

Le fichier applique déjà ce droit à la source. Au 14/08/2026, les
**75 déclarations** porteuses de blocs patrimoniaux sont toutes des `DSP` (64)
ou des `DSPFM` (11), et concernent des membres du gouvernement (59), des
autorités administratives indépendantes (15) et un cabinet de la présidence
(1) — **zéro parlementaire, zéro élu local**.

**Nous ne nous appuyons pas là-dessus.** Faire reposer le respect d'une
interdiction pénale sur la bonne santé d'un fichier tiers n'est pas une
garantie, c'est un pari. Le refus est donc posé **deux fois, par deux chemins
de code indépendants** :

1. **Barrière 1 — par type de déclaration** (`type_declaration_accepte`) :
   seuls `DI` et `DIA` entrent ; `DSP`, `DSPM`, `DSPFM`, `DIM`, `DIAM` sont
   refusés nommément, et tout type inconnu l'est par défaut.
2. **Barrière 2 — par nom de balise** (`balise_acceptee`) : les quatorze
   balises ci-dessus sont refusées **quel que soit le type annoncé**. Une
   déclaration typée « DI » qui transporterait un `immeubleDto` verrait ce
   bloc écarté.

Si l'une tombe, l'autre suffit. Le test
`test_barriere_1_seule_suffit` démonte la seconde et vérifie que la première
tient ; `test_barriere_2_seule_suffit` fait l'inverse ; et
`test_barriere_2_est_bien_porteuse` démonte la seconde **pour de bon** et
vérifie que le contenu patrimonial fuit alors — c'est la preuve que le test
principal n'est pas creux.

Un **troisième** garde-fou, `controler_absence_patrimoine()`, relit la base
après écriture et fait échouer le pipeline (avec rollback) si une rubrique
hors liste blanche s'y trouve. Il ne protège pas du chemin nominal, déjà
couvert : il protège du chemin qu'on n'a pas prévu — migration, reprise
partielle, écriture manuelle.

Les fixtures de test qui portent des blocs patrimoniaux sont **entièrement
fabriquées** (`fixtures/hatvp/declarations_patrimoine_fabrique.xml`). Copier
un vrai bloc patrimonial dans un dépôt public pour vérifier qu'on ne le publie
pas reviendrait à le publier.

### 3.3 Exclusions ÉTHIQUES — et non juridiques

Deux blocs sont publiés par la HATVP, et leur republication serait licite.
Nous choisissons de ne pas les reprendre :

- `activProfConjointDto` — employeur et profession du **conjoint** ;
- `activCollaborateursDto` — identité des **collaborateurs**.

Ce sont des données sur des **tiers** qui n'exercent aucun mandat et n'ont pas
choisi la vie publique. La finalité du site est le contrôle des responsables
publics ; elle s'arrête à eux. C'est un choix éditorial assumé, pas une
obligation légale, et il est écrit comme tel dans le code.

Ne sont par ailleurs **jamais lus ni persistés** : `adresseDec`, `email`,
`telephoneDec`, `pieceIdentite`. Ils n'ont aucun usage éditorial (et sont, le
plus souvent, déjà caviardés par la HATVP).

---

## 4. Clé d'appariement et taux obtenu

**Clé : nom + prénom normalisés (NFD, sans accents, tirets et apostrophes
réduits à des espaces, majuscules) + date de naissance.**

| Mesure (20/08/2026) | Valeur |
|---|---|
| `dateNaissance` renseigné côté HATVP | 100 % des DI/DIA |
| `date_naissance` renseigné côté `elus` | 100 % des 1 053 fiches |
| Collisions de la clé complète sur les fiches | **0** |
| Fiches appariées | **949 / 1 053 = 90,1 %** |
| Déclarations DI/DIA rattachées | **2 263** (2,38 par élu apparié, max 9) |

**Pourquoi la date de naissance est indispensable.** Sans elle, la clé
nom + prénom gagnerait **8 fiches** (+0,8 point) et rouvrirait l'homonymie :
**588 couples nom + prénom** sont partagés par au moins deux personnes dans
`elus`. Attribuer une déclaration d'intérêts au mauvais homonyme est la faute
la plus grave que ce pipeline puisse commettre ; +0,8 point ne l'achète pas.
Une clé partagée par deux élus est d'ailleurs **retirée de l'index** plutôt
qu'arbitrée.

**Les 104 fiches non appariées**, mesurées :

- **96** dont le nom + prénom n'apparaît dans **aucune** DI/DIA du fichier
  amont — la déclaration n'y est simplement pas ;
- **8** dont le nom + prénom apparaît, mais avec une **autre date de
  naissance** ; ce sont les huit que la clé coûte, et qu'elle protège ;
- parmi les 104, **48** ont au moins un dossier S14 au statut
  « Déclaration déposée — publication (en préfecture) à venir » (128 dossiers
  au total), et 7 un dossier « En cours ».

**Conséquence à l'écran, non négociable** : une fiche non appariée n'affiche
**jamais** « aucun intérêt déclaré ». Elle affiche que *nous* n'avons pas la
donnée, et pourquoi c'est possible. Voir §6.

**Périmètre du rattachement** : les seuls élus ayant une fiche publiée
(députés, sénateurs, présidents de conseil départemental et régional). Ingérer
les 3 461 déclarations que la clé rattache à l'ensemble des 36 018 élus
donnerait 662 personnes de plus sans aucune page — un stock de données
personnelles sans usage, contraire à la minimisation de l'article 5(1)(c) du
RGPD. La liste des types de mandat est dupliquée entre le pipeline
(`TYPES_FICHE`) et `app/src/app/elus/[id]/page.tsx` (`TYPES_FICHE_STATIQUE`) ;
si les deux divergent, il **manque** de la donnée — cas déjà géré à l'écran —
jamais l'inverse.

---

## 5. Qualité du texte source — mesurée, et contraignante

Les champs libres ne sont normalisés d'aucune façon. Constaté dans le fichier
du 14/08/2026 :

- **casse et orthographe flottantes** : « Education Nationale », « Education
  nationale », « ASSEMBLEE NATIONALE » cohabitent ;
- **espaces manquantes dans la source elle-même** : `Isère(38)`,
  `Conseillermunicipal` sont des valeurs réelles, vérifiées octet par octet ;
- **doublons de saisie** fréquents d'une déclaration à l'autre ;
- **le marqueur de caviardage `[Données non publiées]` déborde dans les champs
  métier** : `SCI [Données non publiées]`, `SCEA [Données non publiées]`,
  `GFA [Données non publiées]`. Mesure sur les sept rubriques retenues :
  **5 854 champs** ne contiennent que le marqueur, **5 677** le portent **en
  plus** d'un texte réel.

Le marqueur est retiré dans les deux cas (`nettoyer()`), le texte métier
survit, et un champ qui ne garde rien devient `NULL` — une absence, jamais une
chaîne vide.

### Conséquence éditoriale, inscrite dans le schéma

**Affichage verbatim uniquement. Aucun agrégat, aucun classement, aucun total.**

Ce n'est pas une consigne, c'est une propriété du schéma : la table
`hatvp_decl_montants` stocke `montant` en **TEXTE**, et il n'existe **aucune
colonne numérique** dans les quatre tables. Un total est donc impossible à
écrire, pas seulement déconseillé. Le test
`test_aucune_colonne_numerique_pour_les_montants` empêche de réintroduire une
colonne numérique par distraction.

### Zéros déclarés contre données absentes

C'est le piège principal de cette source, et la règle la plus importante du
projet s'y applique dans les deux sens :

- un champ **vide** (`capitalDetenu` vide 2 996 fois, un montant d'année sans
  valeur 81 fois) devient `NULL` et s'affiche « non renseigné » — **jamais
  « 0 € »**. Écrire zéro là où quelqu'un n'a rien déclaré est une affirmation
  de fait fausse sous son nom ;
- un **« 0 » réellement saisi** (`remuneration` = `0` 4 170 fois,
  `evaluation` = `0` 410 fois, mandats municipaux rémunérés 0 € plusieurs
  années de suite) est conservé et affiché « 0 » : c'est une déclaration, pas
  une absence.

---

## 6. « Néant déclaré » n'est pas « pas de donnée chez nous »

La distinction est portée par la donnée elle-même, pas par une convention
d'affichage.

| Situation | Ce qui est en base | Ce que l'écran dit |
|---|---|---|
| La personne a coché « néant » pour une rubrique | `hatvp_decl_rubriques.neant = 1` (8 572 cas) | « **Néant déclaré** — la personne a indiqué n'avoir rien à déclarer dans cette rubrique. » |
| La source ne s'est pas prononcée sur la rubrique | `neant IS NULL` ou rubrique absente | « Rubrique non renseignée dans cette déclaration. » |
| Aucune déclaration rattachée à la fiche | Aucune ligne dans `hatvp_decl_interets` (104 fiches) | « Aucune déclaration d'intérêts n'a pu être rattachée à cette fiche dans notre base. **Cela ne veut pas dire que cette personne n'a rien déclaré.** » + rappel des causes possibles |
| Pipeline jamais exécuté / tables absentes | — | « Le contenu des déclarations n'est pas encore ingéré dans cette base. » |

Le premier cas est un **fait publié par la HATVP**. Les trois autres sont des
**ignorances de notre côté**, et se disent comme telles.

---

## 7. Garde-fous d'affichage

- **Verbatim** : aucun libellé n'est reformulé, aucune casse n'est corrigée.
- **Daté** : chaque déclaration porte sa `dateDepot`, chaque montant son année
  et sa mention « net » / « brut » telles que déclarées.
- **Déclaratif, non vérifié** : la fiche l'écrit explicitement — « son contenu
  a été renseigné par la personne elle-même et publié tel quel par la HATVP.
  France Transparence ne l'a pas vérifié et n'en garantit pas l'exactitude ».
- **Lien vers la source** : la fiche HATVP nominative (`elus.hatvp_url`) est
  citée à côté du bloc.
- **Toutes les déclarations sont montrées**, la plus récente dépliée, les
  autres d'un clic. On ne montre jamais la seule dernière : une déclaration
  **modificative** ne remplace pas les précédentes, elle en corrige une partie
  — la donner seule ferait passer pour « néant » des rubriques qui ne le sont
  pas. 645 des 949 élus appariés ont une modificative en tête de liste.
- **Troncature annoncée** : au-delà de 8 lignes par rubrique, « Affichage des
  8 premières lignes sur N » + bouton « Tout afficher (N) ». Aucune donnée
  n'est chargée en plus au clic : tout est déjà là.
- **Aucune juxtaposition trompeuse** : les montants de rémunération déclarés
  ne sont mis en regard d'aucune autre grandeur du site.
- **Aucun croisement avec les titulaires de marchés publics (DECP)** :
  décision antérieure, close.

---

## 8. Tables produites

```
hatvp_decl_interets   (uuid, elu_id, type_declaration, …, nb_lignes)   2 263 lignes
hatvp_decl_rubriques  (declaration_uuid, rubrique, neant, nb_lignes)  15 841 lignes
hatvp_decl_lignes     (id, declaration_uuid, elu_id, rubrique, …)     27 731 lignes
hatvp_decl_montants   (ligne_id, annee, montant TEXT, brut_net)       94 507 lignes
```

Remplacement complet à chaque exécution (`DROP` + `CREATE` dans une
transaction) : le pipeline est **idempotent**, deux passages donnent les mêmes
compteurs et le même poids.

Répartition des 27 731 lignes par rubrique : organes dirigeants 13 147,
mandats électifs 6 141, participations financières 3 601, activités
professionnelles 3 107, fonctions bénévoles 1 154, observations 342,
consultant 239. **22 582 lignes** portent au moins un montant annuel daté.

---

## 9. Limites connues

1. **Le fichier ne contient que ce qui est publié.** Une déclaration déposée
   mais en cours d'instruction n'y figure pas : son existence est visible via
   S14 (`liste.csv`), son contenu ne l'est pas.
2. **Délai de publication** : ~2 à 3 semaines entre le dépôt le plus récent du
   fichier et sa régénération (28/07 contre 14/08 au moment de la mesure).
3. **Aucun identifiant de personne stable** dans la source : l'appariement
   repose sur l'état civil, donc sur son orthographe. Huit fiches sont perdues
   pour une date de naissance divergente.
4. **Les libellés ne sont pas comparables entre eux.** Aucun regroupement par
   employeur, par secteur ou par société ne serait honnête sur cette donnée —
   c'est pourquoi le schéma ne le permet pas.
5. **`motif` est toujours `CREATION`** dans le fichier (84 480 items sur
   84 480) : ce champ ne distingue rien et n'est pas ingéré.
6. **Les modificatives ne disent pas ce qu'elles modifient** : elles
   re-déclarent des rubriques entières, « néant » compris. D'où la règle
   d'affichage du §7.

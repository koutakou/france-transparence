# Guide dataviz — France Transparence

Guide opérationnel pour toute visualisation de données du dashboard (React/Next.js).
Il est **autoporteur** : tout ce qu'il faut est ici — valeurs hex, px, seuils, règles.
Chaque couleur de ce guide a été **calculée et validée** contre nos fonds réels
(bande de luminosité OKLCH, plancher de chroma, séparation daltonisme simulée
Machado 2009, plancher vision normale, contraste WCAG). N'ajoutez jamais une
couleur « au jugé » : voir l'annexe A pour re-valider.

> **Thème unique.** L'application assume un seul thème, sombre : page `#0a1628`,
> cartes `#0f1d33`. Il n'existe **pas de mode clair** et il ne faut pas en préparer
> un : toutes les valeurs de ce guide sont définies pour ce fond et n'ont pas de
> jumelle claire. Déclarez `color-scheme: dark` sur `:root` (formulaires et
> scrollbars natifs rendus sombres), ne mettez aucun `prefers-color-scheme`, et ne
> laissez jamais un composant tiers injecter ses couleurs par défaut « light ».

---

## 0. Les jetons — à coller tel quel

Tout graphique référence ces custom properties, jamais un hex en dur dans le JSX.

```css
:root {
  color-scheme: dark; /* thème sombre unique */

  /* Surfaces */
  --surface-page:   #0a1628;   /* fond de page */
  --surface-card:   #0f1d33;   /* cartes — le fond sur lequel les marques se dessinent */
  --surface-raised: #16263f;   /* tooltips, popovers, menus */
  --surface-hover:  #1a2b47;   /* survol de ligne de tableau, ghost wash */
  --border-card:    rgba(148, 178, 224, 0.12);  /* bordure subtile des cartes */
  --border-raised:  rgba(148, 178, 224, 0.18);  /* bordure des tooltips */

  /* Encres (texte) — contraste mesuré sur le PIRE fond, --surface-hover #1a2b47 */
  --ink-primary:   #e8eef8;    /* 12,2:1 — valeurs, titres */
  --ink-secondary: #a9b7cc;    /* 6,98:1 — libellés, légendes */
  --ink-muted:     #8798b1;    /* 4,83:1 — axes, ticks. MINIMUM pour du texte */

  /* Chrome graphique (non-donnée : discret par construction) */
  --viz-grid:      #1e2f4d;    /* lignes de grille, filet 1px plein */
  --viz-axis:      #2c405f;    /* ligne de base / axe */
  --viz-crosshair: #44597e;    /* réticule vertical au survol */
  --focus-ring:    #5eb0ff;    /* anneau de focus clavier, 7,3:1 */

  /* Palette catégorielle — ORDRE FIXE, attribution 1→N, jamais recyclée */
  --viz-serie-1: #2f96f7;   /* bleu électrique (accent de marque) — 5,49:1 */
  --viz-serie-2: #d95926;   /* orange   — 4,35:1 */
  --viz-serie-3: #199e70;   /* turquoise — 4,96:1 */
  --viz-serie-4: #c98500;   /* ocre     — 5,50:1 */
  --viz-serie-5: #d55181;   /* magenta  — 4,28:1 */
  --viz-serie-6: #008300;   /* vert     — 3,41:1 */
  --viz-serie-7: #9085e9;   /* violet   — 5,40:1 */
  --viz-serie-8: #e66767;   /* rouge    — 5,23:1 — voir règle rouge, § 3.5 */
  --viz-autre:   #4c5f80;   /* « Autre » + séries de contexte (dé-emphase) */

  /* Rampe séquentielle (magnitude) — bleu électrique, sombre → lumineux */
  --seq-1: #132a4d;  --seq-2: #1a3d74;  --seq-3: #22539c;  --seq-4: #2c6cc4;
  --seq-5: #3f8ae8;  --seq-6: #6bacf5;  --seq-7: #a3d1ff;

  /* Divergente (polarité : baisse ↔ hausse) — extrêmes lumineux, milieu neutre */
  --div-baisse-3: #7cc0ff;  --div-baisse-2: #4b93e8;  --div-baisse-1: #2c5f9e;
  --div-zero:     #3a4a63;   /* gris-bleu neutre : « rien » */
  --div-hausse-1: #9e4352;  --div-hausse-2: #e05a55;  --div-hausse-3: #ff8b7e;

  /* Statuts (réservés : jamais utilisés comme couleur de série) */
  --status-good:     #0ca30c;   /* 5,03:1 */
  --status-warning:  #fab219;   /* 9,20:1 */
  --status-serious:  #ec835a;   /* 6,40:1 */
  --status-critical: #d03b3b;   /* 3,51:1 */

  /* Sémantique deltas & montants — lire IMPÉRATIVEMENT le § 3.5 */
  --delta-bon:     #0ca30c;   /* évolution POSITIVE (jugement explicite) */
  --delta-mauvais: #f26b6b;   /* évolution NÉGATIVE (jugement explicite) — 5,7:1 */
  --montant:       #f26b6b;   /* montants vedettes : KPI, héros, totaux */

  /* Typographie */
  --font-ui: system-ui, -apple-system, "Segoe UI", sans-serif; /* partout, héros compris */
}
```

> **Sur quel fond se mesure un contraste — la question qui a fait passer un jeton sous le seuil.**
> Ce document annonçait ses ratios d'encre « mesurés sur la carte `#0f1d33` ». C'est le fond le
> plus SOMBRE des trois sur lesquels du texte apparaît, donc le plus flatteur. Or les mêmes
> encres servent sur `--surface-raised` (`#16263f`) et sur `--surface-hover` (`#1a2b47`), plus
> clairs : le contraste réel y est plus faible que le chiffre annoncé.
>
> `--ink-muted` en a fait les frais. Annoté « 4,55:1 — MINIMUM pour du texte », il ne valait
> que **4,09:1** sur `raised` et **3,82:1** sur `hover`, sous le seuil AA de 4,5:1 — un audit
> Lighthouse sur la version en ligne l'a relevé sur quatre pages. Il vaut désormais `#8798b1`,
> soit **4,83:1 sur le pire fond**.
>
> **Règle : une encre destinée à du texte se calibre sur le fond le plus CLAIR où elle peut
> apparaître.** Les ratios des jetons d'ENCRE ci-dessus sont donc désormais donnés contre
> `--surface-hover`.
>
> Les jetons de STATUT gardent leurs ratios mesurés sur la carte, et c'est volontaire : ils ne
> colorent que des pastilles, jamais du texte (`AlertItem.tsx` le dit et s'y tient — le libellé
> d'une alerte critique reste en encre, précisément parce que `--status-critical` est à 3,51:1).
> Un contraste de pastille relève de la règle « éléments non textuels » (3:1), pas de AA.

En SVG/Recharts, les custom properties passent directement :
`<Line stroke="var(--viz-serie-1)" />`, `<Bar fill="var(--viz-serie-2)" />`.

---

## 1. La procédure — dans cet ordre, la couleur en DERNIER

La plupart des mauvais graphiques choisissent leurs couleurs d'abord. Interdit ici.

1. **Choisir la forme** (§ 2). Quel est le travail de la donnée — magnitude,
   identité, polarité, un chiffre-titre, évolution ? Parfois la réponse n'est
   *pas un graphique* (stat tile).
2. **Attribuer la couleur selon son rôle** (§ 3) : catégorielle (identité),
   séquentielle (magnitude), divergente (polarité), statut (état). Un rôle, une règle.
3. **Ne jamais inventer de couleur** : uniquement les jetons du § 0, déjà validés.
   Une couleur nouvelle = re-validation complète (annexe A), pas une estimation.
4. **Appliquer les specs de marques** (§ 4) : traits fins, bouts arrondis 4px,
   lignes 2px, écarts de 2px couleur carte.
5. **Ajouter la couche de survol par défaut** (§ 5) : réticule + tooltip sur les
   lignes, tooltip par marque sur barres/points/cellules. Seule une stat tile nue
   s'en dispense.
6. **Passe d'accessibilité** (§ 9) : légende dès 2 séries, jamais l'information
   par la couleur seule, vue tableau jumelle, focus clavier.
7. **Regarder le rendu.** Ouvrir la vue et vérifier à l'œil : collisions
   d'étiquettes, débordements, géométrie. Puis balayer la checklist du § 10.

---

## 2. Choisir la forme : quelle donnée → quel graphique

### Est-ce seulement un graphique ?

| La donnée est… | Utiliser | Pas |
|---|---|---|
| Une valeur courante unique (+ tendance) | **Stat tile** (valeur + delta + sparkline) | Un bar chart à une barre |
| Une poignée de chiffres-titres | **Rangée de KPI** (stat tiles) | Des barres groupées |
| LE chiffre par lequel la vue commence | **Chiffre héros** (≥ 48px, sans-serif) | — |
| Un ratio unique contre une limite (ex. exécution du budget voté) | **Jauge/meter** (piste de la même rampe) | Un camembert à 2 parts |
| Plus de ~7 classes qui comptent toutes | Un **tableau** (ou tableau + graphique) | Plus de couleurs |

### Le travail du lecteur → le type

| Travail (ce que le lecteur doit faire) | Forme par défaut | Rôle couleur |
|---|---|---|
| Comparer des magnitudes (dépenses par ministère) | barres **horizontales** (noms longs) ; heatmap pour une grille | séquentielle (1 teinte) |
| Tendance dans le temps | ligne ; aire pour une série unique | 1 catégorielle |
| Distinguer des séries | multi-lignes, barres groupées/empilées | **catégorielle** |
| Une série est le sujet, le reste est contexte | **emphase** : 1 série en `--viz-serie-1`, le reste en `--viz-autre` | 1 teinte + gris |
| Au-dessus/en-dessous d'une base ; écart au budget voté | barres divergentes, ligne vs base | divergente |
| Part-du-tout (répartition) | **barres empilées** ; donut toléré, voir règle ci-dessous | catégorielle |
| Avant → après par entité (budget N-1 → N) | dumbbell | 1 teinte, 2 pas de la rampe |

**Règles derrière la table :**
- **La séquentielle est le défaut sûr.** Une teinte, plus-c'est-lumineux (sur notre
  fond sombre, l'intensité = la luminosité). Difficile à mal lire.
- **La catégorielle sert quand les séries SONT le sujet** — elle a un coût : elle
  peut noyer le point qui compte. Si l'histoire est « celui-ci a explosé », c'est
  de l'**emphase**, pas de la catégorielle.
- **L'emphase est la forme la plus sous-employée.** Souvent la réponse honnête à
  « rends ce graphique plus clair ».
- **Donut de répartition** : uniquement part-du-tout en
  ordre de grandeur, **≤ 6 segments**, segments dans l'ordre des slots, écarts de
  2px en `--surface-card`, anneau de 24px d'épaisseur, total au centre en chiffre
  héros. **Jamais** pour comparer des parts proches (< 5 points d'écart) →
  barres horizontales.

### Échelle du nombre de séries (catégorielle)

| Séries | Traitement |
|---|---|
| 1 à 3 | la couleur seule suffit à tous ; étiquettes directes |
| 4 | encore sûr pour barres/empilements/lignes (voisins seulement), mais **étiquettes directes obligatoires** ; les formes « toutes paires » (nuage de points, bulles, carte, small multiples) **plafonnent à 3** — replier en « Autre » ou facetter |
| 5–6 | plafond souple ; légende ou small multiples |
| 7–8 | plafond dur ; au-delà : « Autre », small multiples, ou teinte × forme |

**Jamais** résoudre « trop de séries » en générant une 9e teinte : elle serait
indiscernable d'un slot existant en vision daltonienne.

---

## 3. La couleur — quatre rôles, une règle chacun

Chaque couleur d'un graphique fait exactement un de ces travaux. Aucun mélange.

### 3.1 Catégorielle (identité : quelle série)

La palette du § 0, **dans l'ordre, sans sauter, sans recycler**. Elle a été
validée par calcul sur `#0f1d33` **et** `#0a1628` : bande OKLCH L 0,48–0,67,
chroma ≥ 0,10, pire paire adjacente en vision daltonienne ΔE 8,4 (cible ≥ 8,
protan/deutan simulés), pire paire en vision normale ΔE 19,3 (plancher ≥ 15),
contraste ≥ 3:1 pour les 8 slots (valeurs par slot en commentaire au § 0).

Règles impératives :
- **La couleur suit l'entité, jamais son rang.** Un filtre qui retire une série ne
  repeint pas les survivantes : si « Justice » est turquoise, elle le reste.
- **L'ordre des slots est le mécanisme de sécurité daltonisme** — le réordonner
  annule la validation. Ne le faites pas.
- **Formes « toutes paires »** (points sur carte, nuage, bulles, small multiples
  colorés) : 3 séries maximum (validé : pire paire ΔE 9,4 daltonisme / 21,4
  normale). La 4e se replie ou se facette — vérifié : à 4, ocre↔orange tombe à
  ΔE 4,8, illisible.
- **Le slot 8 (rouge `#e66767`)** n'apparaît qu'en 8e position, donc en pratique
  jamais : à ≥ 8 séries on replie en « Autre » dès la 7e, car le rouge porte déjà
  la sémantique montants/alertes de l'app (§ 3.5). Pas de série rouge dans une vue
  qui contient des marques d'alerte.
- **Le texte ne porte jamais la couleur de série** : libellés, valeurs, légendes en
  encres (`--ink-*`) ; l'identité vient d'une pastille/trait coloré À CÔTÉ du texte.
  Exception unique : une étiquette posée DANS un remplissage (segment empilé, tuile)
  prend `#0a1628` ou `#e8eef8` selon la luminance du remplissage.

### 3.2 Séquentielle (magnitude : combien)

Une seule teinte — le bleu électrique — du sombre vers le lumineux. Sur fond
sombre **l'ancre s'inverse** : « proche de zéro » = proche du fond (`--seq-1`),
« maximum » = le plus lumineux (`--seq-7`). C'est la rampe de la heatmap et de la
carte de France.

| pas | hex | contraste /carte | usage |
|---|---|---|---|
| 1 | `#132a4d` | 1,18:1 | aplat « quasi nul » uniquement (choroplèthe) |
| 2 | `#1a3d74` | 1,58:1 | aplat faible ; piste de jauge |
| 3 | `#22539c` | 2,24:1 | premier pas autorisé en **ordinal** |
| 4 | `#2c6cc4` | 3,26:1 | premier pas autorisé pour **petites marques** (points) |
| 5 | `#3f8ae8` | 4,83:1 | |
| 6 | `#6bacf5` | 7,11:1 | |
| 7 | `#a3d1ff` | 10,55:1 | maximum |

- **Continu** (choroplèthe, heatmap) : interpoler sur les 7 pas ; les pas 1–2 ont le
  droit de se fondre dans le fond (ils signifient « presque rien »).
- **Ordinal** (paliers discrets : tranches, tiers, quintiles) : 5 classes maximum,
  pas 3→7 (`#22539c #2c6cc4 #3f8ae8 #6bacf5 #a3d1ff`) — validé : luminosité
  monotone, ΔL ≥ 0,06 entre pas, extrémité côté fond à 2,24:1, teinte unique.
- **Petites marques** (points, traits fins) : jamais sous le pas 4 (`#2c6cc4`,
  3,26:1) — les pas 1–3 sont réservés aux grands aplats.
- Deux contextes séquentiels sur la même vue : le second prend la teinte du slot 2
  (orange) en rampe propre — jamais deux magnitudes dans la même teinte.
- **Jamais de rampe multi-teintes (arc-en-ciel) pour une magnitude.**
- **Jamais de rampe de valeur sur des catégories nominales** : colorer chaque barre
  ministère plus foncée quand elle est plus grande double-encode la longueur. Une
  série de barres nominales = UNE couleur (`--viz-serie-1`) pour toutes.

### 3.3 Divergente (polarité : de quel côté de la base)

Deux pôles chaud/froid + un milieu **gris neutre** (jamais une teinte au milieu,
jamais deux pôles froids). La nôtre : **bleu ↔ rouge**, milieu `--div-zero`
`#3a4a63` (1,88:1 — il recule dans le fond : c'est voulu, il signifie « rien »).
Nombre de pas égal par bras ; sur fond sombre les **extrêmes sont les plus
lumineux**. Les deux bras sont validés (luminosité monotone, ΔL ≥ 0,06, pas
proches du milieu ≥ 2:1, teinte unique par bras).

- Bras « baisse » : `#2c5f9e` → `#4b93e8` → `#7cc0ff` (du milieu vers l'extrême)
- Bras « hausse » : `#9e4352` → `#e05a55` → `#ff8b7e`

Usage type : évolution des dépenses par territoire, écart au budget voté, solde.
**La légende nomme toujours les deux pôles** (« baisse ← → hausse ») : la
polarité n'est jamais portée par la couleur seule.

### 3.4 Statuts (état : bon → critique) — réservés

`--status-good #0ca30c` · `--status-warning #fab219` · `--status-serious #ec835a`
· `--status-critical #d03b3b`. Tous ≥ 3:1 sur nos deux fonds (valeurs au § 0).

- **Toujours icône + libellé**, jamais la couleur seule.
- Un statut ne colore **jamais** une « série 4 » ; une série ne porte **jamais** un
  statut. Quand une série *signifie* bon/mauvais (taux de conformité, retards de
  publication), elle porte les jetons statut ; quand c'est juste une identité,
  la catégorielle — jamais les deux dans un même graphique.

### 3.5 Sémantique budgétaire — deltas, montants, le point délicat

**Une hausse de dépense publique n'est pas « positive », une baisse n'est pas
« bonne ».** Le vert/rouge est un *jugement* ; l'appliquer mécaniquement au signe
d'un delta budgétaire est un biais éditorial. Règle absolue :

1. Chaque métrique déclare explicitement `upIsGood: true | false | null`.
2. `couleur du delta = signe × upIsGood` :
   - `upIsGood: true` (taux de publication des déclarations, délais tenus…) :
     hausse `--delta-bon`, baisse `--delta-mauvais`.
   - `upIsGood: false` (retards, non-conformités, dépassements du voté) : inversé.
   - `upIsGood: null` (**cas par défaut des montants de dépense**) : le delta est
     **neutre** — flèche + signe en `--ink-secondary`, PAS de vert ni de rouge.
     Pour une vue en polarité (carte des évolutions), la paire divergente
     bleu↔rouge du § 3.3, qui se lit « baisse/hausse », pas « bien/mal ».
3. Tout delta porte **flèche + signe + période nommée** (`▲ +4,2 % vs 2024`) —
   jamais la couleur seule, même quand elle est légitime.
4. **Le rouge « montant »** (`--montant #f26b6b`, 5,7:1) est l'accent de marque des
   montants **vedettes** : valeur d'un KPI montant, chiffre héros, total d'un
   donut. Dans les tableaux denses, les colonnes de montants restent en
   `--ink-primary` — du rouge partout fatiguerait l'alerte et se lirait comme
   « tout est négatif » ; le rouge n'y marque que dépassements et alertes, avec
   icône (§ 3.4).
5. Ne confondez pas les trois rouges, ils sont distincts à dessein :
   `#e66767` = série 8 (identité), `#d03b3b` = statut critique, `#f26b6b` =
   montant/delta-mauvais (texte). Aucun ne remplace un autre.

---

## 4. Marques et anatomie — les specs fixes

La donnée est la seule chose autorisée à être « bruyante ». Le chrome est discret.

| Marque | Spec |
|---|---|
| Barre / colonne | **≤ 24px d'épaisseur** (jamais remplir la bande : l'air restant respire) ; **bout de donnée arrondi 4px, carré à la ligne de base** (`radius={[4,4,0,0]}` en colonnes Recharts) ; pousse depuis une base unique |
| Ligne | **2px**, jointures et bouts arrondis (`stroke-linejoin/linecap: round`) |
| Marqueur / point | **≥ 8px de diamètre** (r ≥ 4), rempli de la couleur de série |
| Aplat d'aire | teinte de série à **10 % d'opacité** (un voile, jamais un bloc saturé) |
| Grille / axes | `--viz-grid` **1px plein** (jamais pointillé), 3 à 6 lignes horizontales, pas de grille verticale par défaut ; ligne de base `--viz-axis` 1px |

### Les deux séparateurs (le fond fait le travail)

- **Écart de fond, 2px** : entre chaque segment d'une pile ET entre barres qui se
  touchent — un trait de 2px en `--surface-card` (en SVG : `stroke: var(--surface-card);
  stroke-width: 2` sur les segments). Largeur constante dans toute la pile.
- **Anneau de fond, 2px** : chaque point/marqueur porte un anneau `--surface-card`
  de 2px, pour rester lisible en croisant une ligne. L'anneau fait partie de la
  cible de survol.
- **Jamais de bordure dessinée autour d'une marque** pour la séparer : l'écart et
  l'anneau sont le mécanisme ; un contour ajoute de l'encre non-donnée.

### Étiquettes et légende

- **Légende toujours présente dès 2 séries** (swatch 12×12px pour barres/aires,
  trait 16×2px pour lignes ; texte 12px `--ink-secondary`). **Une série unique :
  pas de boîte de légende** — le titre du graphique la nomme.
- **Étiqueter sélectivement — jamais un chiffre sur chaque point.** Le point
  d'arrivée, l'extrême, la série dont on parle ; l'axe, la légende et le tooltip
  portent le reste. Jusqu'à 4 séries : étiquettes directes en bout de ligne.
- **Une étiquette qui ne tient pas ne se coupe pas — mesurer d'abord.** Dans une
  barre seulement si le texte tient avec marge des deux côtés ; sinon dehors au
  bout de la barre ; sinon tooltip. Segment intérieur d'une pile trop petit :
  pas d'étiquette inline (légende + tooltip). **Jamais `overflow: hidden`** pour
  « résoudre » un débordement d'étiquette.
- Barres → valeur au bout. Colonnes → valeur au sommet. Lignes → valeur en fin.
- Ticks Y : nombres ronds (0, 1 000, 2 000…), portés par `--ink-muted`, 11–12px.
- Étiquettes de fin qui se percutent : traits de rappel fins, ou small multiples
  au-delà de ~4 séries convergentes — jamais d'étiquettes empilées décollées.
- Titre de carte 14px semibold `--ink-primary` ; sous-titre 12px `--ink-secondary` ;
  padding de carte 16–20px ; carte `--surface-card`, bordure 1px `--border-card`,
  rayon 12px.
- **La hauteur fixe d'un conteneur inclut la bande d'axe X** (hauteur du tracé +
  étiquettes) — sinon la carte gagne un mini-scroll vertical interne.

### Formats de nombres (français)

`Intl.NumberFormat('fr-FR')` partout : espace insécable pour les milliers
(`1 284`), virgule décimale, `%` précédé d'une espace insécable (`12,4 %`).
Compaction des montants : `4,2 M€`, `1,3 Md€` (jamais `4.2M`).
`font-variant-numeric: tabular-nums` **uniquement** dans ce qui s'aligne
verticalement (colonnes de tableau, ticks d'axe) — jamais sur un grand nombre
isolé (chiffres proportionnels sur héros et valeurs de KPI).

---

## 5. Interaction — livrée par défaut

Un graphique HTML est interactif d'office ; la couche de survol fait partie du
livrable. Seule une stat tile sans tracé s'en dispense.

- **Le réticule trouve le X** (lignes/aires) : un filet vertical 1px
  `--viz-crosshair` suit le pointeur et s'aimante à la position de donnée la plus
  proche. On vise une date, pas une ligne de 2px.
- **Sur barres et cellules, la marque est la cible** : pas de réticule ; chaque
  barre/segment/cellule porte son tooltip (`pointermove`/`focus`) et la marque
  survolée se soulève (`filter: brightness(1.18)`).
- **Un tooltip, toutes les séries** : le relevé liste chaque série à ce X.
- Tooltip : fond `--surface-raised`, bordure 1px `--border-raised`, rayon 8px,
  ombre `0 8px 24px rgba(0,0,0,0.45)`, padding 8px 10px. **La valeur d'abord**
  (semibold `--ink-primary`), le nom de série en second (`--ink-secondary`), clé
  de série = trait 12×2px de la couleur (pas de boîte pleine à cette densité).
- **Cible de clic > marque peinte** : zone transparente d'au moins **24px** par
  point ; nuages denses → couche « point le plus proche » (Voronoï).
- **Le tooltip enrichit, il ne conditionne jamais** : toute valeur du tooltip est
  aussi accessible par étiquette directe ou vue tableau. Le focus clavier montre
  la même chose que le survol.
- **Noms de séries = données non fiables** : injection dans tooltip/légende/tableau
  via `textContent`, jamais `innerHTML` concaténé.
- **Filtres : une seule rangée, au-dessus des graphiques**, alignée à gauche —
  jamais dans une carte, jamais par graphique. Plage de dates en premier, presets
  avant calendrier (Aujourd'hui, 7 j, 30 j, 90 j, Année, Personnalisé), sélection
  marquée d'une coche 16px bold, survol en voile `--surface-hover`.
- **Les filtres scopent tout ce qui est en dessous** : tous les graphiques, KPI et
  tableaux se re-rendent sur la même tranche — les chiffres concordent toujours.
- **Re-fetch : garder le cadre** — rendu précédent maintenu à opacité 0,5, pas de
  skeleton, pas de saut de layout.

---

## 6. KPI, stat tiles, héros, jauges

Contrat de la **stat tile** :
- `label` : 12px `--ink-secondary`, casse de phrase, pas de deux-points final.
- `value` : 24–32px semibold `--font-ui`, `--ink-primary`, auto-compacté
  (`1 284` / `12,9 k` / `4,2 M€`), chiffres **proportionnels**. Un KPI « montant
  vedette » peut porter `--montant`.
- `delta` (optionnel) : 12–13px, signé, vs une période **nommée**
  (`▲ +4,2 % vs 2024`), couleur = signe × `upIsGood` (§ 3.5 — neutre par défaut
  pour une dépense).
- `trend` (optionnel) : sparkline **12 points**, trait 2px `--viz-autre`, période
  courante en `--viz-serie-1`, hauteur ~32px, sans axes ni grille.
- `perimetre` (optionnel) : 11px `--ink-muted`, sous la valeur et avant le delta.
  **Une tuile dont le chiffre est BORNÉ le porte, sans exception** — fenêtre
  glissante (« notifiés sur les 24 derniers mois »), strate (« les 200 plus
  grandes communes »), filtre de source (« budgets principaux seuls »),
  population exclue (« hors conseillers municipaux »).

  Cette ligne existe parce que son absence a produit des chiffres faux. Une
  `Card` offre trois endroits où qualifier une valeur — `sousTitre`, `droite`,
  note de bas de carte — et les vues qui passent par `Card` disent leurs bornes.
  La tuile n'en offrait aucun : les seuls chiffres du site qui laissaient croire
  à un total étaient exactement ceux que le composant empêchait de qualifier.
  Une restriction dite ailleurs sur la page ne compte pas : elle doit être lue
  au même endroit que le chiffre.

**Chiffre héros** : LE chiffre par lequel la vue commence. ≥ 48px, même sans-serif
que tout le reste (jamais de display/serif : ça se lit comme un décor hors-marque),
chiffres proportionnels, **exactement un par vue**.

**Jauge/meter** (ex. exécution du budget voté) : le remplissage porte la sévérité
(`--viz-serie-1` → `--status-warning` → `--status-critical` selon seuils
déclarés) ; la piste vide est un pas sombre de la même rampe (`--seq-2 #1a3d74`)
pour que l'état se lise sur toute la barre. Hauteur 8px, rayon 4px.

---

## 7. Tableaux denses

- Rangées de **36px** (dense) à 40px, padding horizontal 12px.
- En-tête : 11px, majuscules, letter-spacing 0,04em, `--ink-muted`, sticky.
- Séparateurs horizontaux 1px `--viz-grid` ; **pas de filets verticaux, pas de
  zébrage** — le survol `--surface-hover` suffit à suivre la ligne.
- Nombres **alignés à droite** en `tabular-nums`, texte à gauche ; unité dans
  l'en-tête de colonne (`Montant (M€)`), pas répétée dans chaque cellule.
- Montants en `--ink-primary` (§ 3.5) ; `--montant` + icône ▲ seulement pour
  dépassements/alertes ; deltas avec flèche + signe, couleur selon `upIsGood`.
- Mini-barres en cellule (comparaison rapide) : hauteur 6px, `--viz-serie-1` sur
  piste `--seq-2`, même échelle sur toute la colonne.
- Tri visible (chevron dans l'en-tête), première colonne sticky autorisée,
  virtualiser au-delà de ~100 lignes.
- Le tableau est aussi la **vue jumelle** de chaque graphique (§ 9) : chaque carte
  graphique offre un toggle « Tableau » qui rend les mêmes données.

---

## 8. La carte de France

Fond de carte sur `--surface-card` ; contours des départements 1px `#22375a`.

**Points lumineux** (implantations, déclarations, élus…) :
- L'**aire** encode la valeur, pas le rayon : `r = rmin + (rmax − rmin) ×
  sqrt(v / vmax)`, r de 3 à 14px.
- Couleur d'intensité : rampe séquentielle **pas 4 à 7 seulement** (`#2c6cc4` →
  `#a3d1ff`) — les pas 1–3 sont trop proches du fond pour de petites marques.
- Halo « lumineux » : radial-gradient de la même teinte, opacité 0,35 → 0, rayon
  2,5× le point. Pas d'animation de pulsation si `prefers-reduced-motion`.
- Encodage **catégoriel** sur la carte : **3 séries maximum** (plafond « toutes
  paires », § 3.1), au-delà repli ou facettes.
- Cible de survol ≥ 24px par point, tooltip nom + valeur.

**Choroplèthe** :
- Magnitude : rampe séquentielle en 5 classes ordinales max (`--seq-3` → `--seq-7`),
  seuils ronds ou quantiles, légende d'échelle obligatoire (barres + bornes chiffrées).
- Évolution (hausse/baisse des dépenses) : la divergente du § 3.3, milieu
  `--div-zero`, légende nommant les pôles — pas de vert/rouge (§ 3.5).
- **Donnée manquante** : `#0d1930` (plus sombre que le pas 1, hors rampe) +
  mention « donnée manquante » dans le tooltip et la légende — jamais un gris
  confondable avec un pas de la rampe.

---

## 9. Accessibilité — les pièges sur fond `#0a1628`

Seuils impératifs (WCAG, mesurés contre `#0f1d33` puisque les marques vivent sur
les cartes — le fond page étant plus sombre, ce qui passe sur carte passe sur page) :

- **Marques (barres, lignes, points) : ≥ 3:1** contre leur fond. Tous les jetons du
  § 0 sont déjà conformes ; c'est la raison de la règle « pas de point sous
  `--seq-4` ».
- **Texte courant : ≥ 4,5:1.** `--ink-muted` (4,55:1) est le MINIMUM absolu — rien
  de plus sombre ne porte du texte. `--delta-mauvais` 5,7:1 et `--delta-bon` 5,03:1
  passent en petit corps.
- **Grand texte (≥ 24px, ou ≥ 18,5px gras) : ≥ 3:1.**
- **Jamais l'information par la couleur seule** — le piège n°1 :
  - identité : légende + étiquettes directes, jamais « retrouvez la série à sa couleur » ;
  - statut : icône + libellé toujours ;
  - delta : flèche + signe toujours ;
  - polarité (carte divergente) : légende nommant les pôles ;
  - repli ultime : remplissage texturé (hachures à 45°/135° uniquement, ton sur
    ton, ordonné avec la magnitude) activé par réglage d'accessibilité,
    impression ou `forced-colors` — jamais décoratif, jamais par défaut.
- **Vue tableau jumelle pour chaque graphique** — l'équivalent WCAG propre ; c'est
  elle qui rend les tooltips « non conditionnants ».
- **Clavier** : chaque marque focusable, le focus montre le tooltip du survol,
  anneau de focus 2px `--focus-ring` offset 2px.
- **Ne jamais poser l'ocre `#c98500`, le turquoise ou toute couleur de série en
  couleur de TEXTE** : encres seulement (§ 3.1).
- Texte d'axe ≥ 11px ; cibles ≥ 24px ; `prefers-reduced-motion` respecté (halos,
  transitions de re-render).
- La palette est validée pour protanopie/deutéranopie **dans cet ordre** ; toute
  modification (teinte, ordre, ajout) repasse par l'annexe A.

---

## 10. Anti-patterns — si votre graphique coche une ligne, il est faux

- **Double axe (deux échelles Y sur un tracé)** — l'erreur n°1 : l'alignement des
  échelles est arbitraire, la corrélation est inventée. → Deux graphiques, small
  multiples, ou indexer base 100 sur UN axe.
- Recolorer au filtrage (couleur = rang courant). → La couleur suit l'entité.
- Générer/recycler une 9e teinte. → « Autre », facettes, teinte × forme.
- Rampe de valeur sur des catégories nominales (barres ministères plus foncées
  quand plus grandes). → Une couleur pour la série ; ordinal seulement si l'ordre
  a un sens.
- Arc-en-ciel séquentiel ; teinte au milieu d'une divergente ; deux pôles froids.
- Statut utilisé comme série, série utilisée comme statut.
- 8 teintes quand l'histoire est UN chiffre. → Emphase ou stat tile.
- Bar chart à une barre ; camembert à 2 parts. → Stat tile.
- Donut pour comparer des parts proches. → Barres. (Donut : ≤ 6 segments, § 2.)
- Plus de ~7 classes de couleur porteuses de sens. → Tableau.
- Blocs épais saturés, grille lourde, zéro respiration ; grilles/axes pointillés.
- Un chiffre sur chaque point. → Étiquetage sélectif + légende.
- Bordure autour des marques. → Écart 2px + anneau 2px en couleur de fond.
- Étiquette rognée par sa barre (`overflow: hidden` compris). → Mesurer, déplacer,
  ou tooltip.
- Hauteur fixe qui exclut la bande d'axe X (mini-scroll interne).
- Serif/display sur le héros ; `tabular-nums` sur un grand nombre isolé.
- Texture par défaut ou décorative.
- Valeur accessible uniquement au survol ; cibles de 8px à viser au pixel.
- Filtres par graphique ou dans une carte ; skeleton qui flashe au re-fetch.
- Pas de vue tableau ; information portée par la couleur seule sur une échelle
  continue.
- **Spécifique à nous** : vert/rouge appliqué au signe d'une dépense sans
  `upIsGood` explicite (§ 3.5) ; série rouge dans une vue qui contient des
  alertes ; texte en couleur de série ; couleur ajoutée sans re-validation.

---

## 11. Note d'implémentation « thème unique »

- Un seul jeu de jetons, défini une fois sur `:root` (§ 0). Pas de
  `prefers-color-scheme`, pas de `data-theme`, pas de valeurs « light » en réserve.
- `color-scheme: dark` sur `:root` pour que contrôles natifs, scrollbars et
  `<select>` suivent.
- Les bibliothèques de charts arrivent avec des défauts pensés pour fond blanc
  (grilles `#ccc`, tooltips blancs, encre noire) : **tout défaut de couleur doit
  être écrasé** par nos jetons — un composant non thémé se voit immédiatement.
- Toute nouvelle couleur est validée contre `#0f1d33` (et `#0a1628` si elle se
  dessine sur la page) — annexe A. Il n'y a pas d'« équivalent clair » à fournir.

---

## Annexe A — valider une couleur sans outillage externe

Les six vérifications d'une palette catégorielle (seuils utilisés pour valider
celle du § 0) :
1. Ordre de teintes fixe (structurel — ne pas réordonner).
2. Bande de luminosité OKLCH : L entre **0,48 et 0,67** (fond sombre).
3. Plancher de chroma OKLCH : **C ≥ 0,10** (en-dessous, la teinte lit « gris »).
4. Séparation daltonisme : ΔE OKLab ×100 sous simulation protan/deutan
   (Machado–Oliveira–Fernandes 2009, sévérité 1,0) — **≥ 8** entre voisins
   (6–8 toléré UNIQUEMENT avec encodage secondaire : étiquettes, écarts, texture) ;
   toutes-paires pour nuage/carte/small multiples. Plancher vision normale :
   pire paire **≥ 15**, non négociable.
5. Contraste WCAG contre la surface : **≥ 3:1** pour une marque.
6. Uniquement des hex documentés ici — pas de valeur « au jugé ».

Pour le contraste (le seul contrôle à refaire souvent), autonome en 6 lignes :

```js
const lin = c => { c /= 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; };
const lum = hex => { const [r, g, b] = [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16));
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b); };
const contrast = (a, b) => { const [h, l] = [lum(a), lum(b)].sort((x, y) => y - x);
  return (h + 0.05) / (l + 0.05); };
// contrast('#2f96f7', '#0f1d33') → 5.49 ; marque ≥ 3, texte ≥ 4.5
```

Pour les contrôles 2–4 (OKLCH, simulation daltonisme), ne pas estimer à l'œil :
utiliser un convertisseur OKLab/OKLCH et la matrice Machado 2009, ou repartir des
palettes déjà validées de ce guide — c'est leur raison d'être.

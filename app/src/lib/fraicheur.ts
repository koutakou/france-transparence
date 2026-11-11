/**
 * Fraîcheur des sources : seuils calibrés source par source, âge, niveau, et
 * les phrases qui les disent. Module PUR, sans base ni réseau : le même code
 * calcule l'état au build (rendu serveur, `/api/meta.json`) et le recalcule
 * dans le navigateur à la date de lecture (`components/client/FraicheurLecture`).
 * Une seule source de vérité pour les seuils, testée par `npm test`
 * (`tests/donnees.test.mjs`, `tests/fraicheur-lecture.test.mjs`).
 *
 * POURQUOI recalculer chez le lecteur : le site est un export statique. Un
 * âge ou un « à jour » calculé au build est vrai le jour du build et faux dès
 * qu'un cycle de publication saute — la page témoin de fraîcheur restait
 * alors d'autant plus verte que le site était en panne (site figé au
 * 08/11/2026, page encore « 33 sources sur 44 à jour » le 11/11). Sans
 * JavaScript, le rendu serveur reste vrai parce qu'il DATE son calcul.
 */
import { formatDateFr, formatNombre } from "@/lib/format";

/* ------------------------------------------------------------------ */
/* Fraîcheur des sources — un seuil calibré PAR SOURCE                  */
/* ------------------------------------------------------------------ */

/**
 * État de fraîcheur d'une source, par gravité croissante.
 *
 * `attente_edition` ne dépend que de l'ÂGE de la donnée : il dit qu'à la
 * date du calcul, aucune édition plus récente n'avait été INGÉRÉE. Il ne dit
 * rien de l'amont — le site ne vérifie pas qu'aucune édition n'y a paru —,
 * ni de l'intention de l'éditeur, ni de l'avenir. Pour une source dont le
 * pipeline vise un millésime FIGÉ (`editionFigee`), une édition plus récente
 * ne serait de toute façon pas vue sans modifier le pipeline : la page le dit.
 */
export type NiveauFraicheur =
  | "a_jour"
  | "a_surveiller"
  | "en_retard"
  | "attente_edition"
  | "non_calibre";

/** Unité de comptage de l'âge : jours ouvrés (« jo ») ou calendaires (« jc »). */
export type UniteAge = "jo" | "jc";

export type Fraicheur = {
  niveau: NiveauFraicheur;
  /**
   * Âge de la donnée (jour du calcul − date_donnees), dans l'unité `unite`.
   * Le jour du calcul est celui que l'appelant passe : la construction du
   * site au rendu serveur, la date de lecture dans le navigateur.
   */
  ageJours: number;
  unite: UniteAge;
  /** Seuils appliqués, `null` si la source n'est pas calibrée. */
  seuilRetardJours: number | null;
  seuilAlerteJours: number | null;
  /** Millésime fixé par le pipeline : une édition suivante n'y entrerait pas seule. */
  editionFigee: boolean;
};

/**
 * `editionFigee` : le pipeline vise un millésime écrit en dur (URL,
 * identifiant de publication) et ne peut pas voir le suivant. Propre au
 * site — ce n'est pas un seuil, `fraicheur.conf` ne le porte pas.
 */
type SeuilSource = { unite: UniteAge; retard: number; alerte: number; editionFigee?: true };

/**
 * Seuils de fraîcheur, UN JEU PAR SOURCE.
 *
 * Pourquoi pas une règle générique dérivée de `meta_sources.frequence` :
 * elle produit exactement les deux erreurs que ce tableau corrige. Deux
 * sources déclarées « quotidiennes » n'ont pas le même âge normal — 2 jours
 * pour le Journal officiel, 60 pour les scrutins de l'Assemblée, silencieux
 * toute la trêve estivale sans que rien ne soit cassé ; et une source
 * « annuelle » peut avoir un décalage structurel de 12 à 13 mois entre la
 * clôture de l'exercice et sa publication (subventions aux associations),
 * qu'aucune règle tirée du mot « annuelle » ne peut deviner. Neutraliser
 * ces sources-là (l'ancien état « millésime ») revenait à ne jamais rien
 * signaler sur les seules sources dont l'édition manque réellement.
 *
 * ────────────────────────────────────────────────────────────────────────
 * POINT DE SYNCHRONISATION — à lire avant de toucher à ce tableau
 * ────────────────────────────────────────────────────────────────────────
 * Ces valeurs sont une COPIE du référentiel qui fait autorité côté serveur,
 * `/etc/france-transparence/fraicheur.conf`, lu par la supervision
 * quotidienne `ft-fraicheur`. Duplication assumée faute de mieux :
 *   1. ce fichier n'est pas lisible par l'utilisateur qui construit le site
 *      (`/etc/france-transparence` est en 0750 root:root) ;
 *   2. il n'existe ni dans un dépôt fraîchement cloné ni dans la CI, qui
 *      doivent pourtant produire la même page (`make ingest` puis build).
 * Tant que ces deux points tiennent : toute modification de
 * `fraicheur.conf` doit être reportée ici, et réciproquement.
 * `ft-fraicheur --json` affiche les seuils réellement appliqués côté
 * serveur — c'est la commande qui vérifie que les deux n'ont pas divergé.
 * Deux façons de supprimer cette copie, hors périmètre de ce correctif :
 * rendre `fraicheur.conf` lisible au build et le lire ici, ou porter les
 * seuils dans `meta_sources` (colonnes dédiées) via les pipelines.
 *
 * Ordre et valeurs repris ligne à ligne de `fraicheur.conf`.
 * Dernière synchronisation : 25/08/2026, 44 sources (ajout de S52).
 * ⚠ Divergence voulue depuis le 11/11/2026 : S7-DATAN, S45, S47, S48 et S49
 * ont été recalibrés ici sur le calendrier amont relevé ce jour-là (détail
 * sur chaque ligne) ; `fraicheur.conf` n'est pas accessible depuis le dépôt
 * et doit recevoir les mêmes valeurs à la main (docs/ACTIONS-HUMAINES.md).
 */
const SEUILS_SOURCES: Record<string, SeuilSource> = {
  // Quotidiennes strictes, calendrier ouvré
  S3: { unite: "jo", retard: 3, alerte: 7 },
  S2: { unite: "jo", retard: 3, alerte: 7 },
  S1: { unite: "jo", retard: 7, alerte: 20 },
  S4: { unite: "jo", retard: 6, alerte: 12 },
  S9: { unite: "jo", retard: 10, alerte: 20 },
  // Quotidiennes mais événementielles (le contenu ne bouge qu'à un événement)
  "S5-AMO10": { unite: "jc", retard: 20, alerte: 45 },
  "S6-ODSEN": { unite: "jc", retard: 20, alerte: 45 },
  // Datan publie chaque jour, week-ends compris : dateMaj quotidienne du
  // 22 au 28/10/2026 (journaux CI, 24 et 25/10 inclus), et du jour même le
  // 19/08/2026, en pleine trêve parlementaire. Elle s'est arrêtée au 28/10
  // alors que l'Assemblée a publié 606 scrutins du 29/10 au 10/11 (base du
  // 11/11/2026) : avec 20/45, les scores restaient « à jour ». Ce n'est pas
  // une source événementielle comme AMO10 — l'âge normal est de 0 à 1 jour.
  "S7-DATAN": { unite: "jc", retard: 7, alerte: 14 },
  "S35-reforga-admin-etat": { unite: "jc", retard: 45, alerte: 90 },
  "S11-annuaire-administration": { unite: "jc", retard: 60, alerte: 120 },
  // Calendrier parlementaire (trêve estivale mi-juillet → début octobre)
  "S5-SCRUTINS": { unite: "jc", retard: 60, alerte: 95 },
  // Même trêve estivale que l'AN (session ordinaire 1er octobre → fin juin).
  // date_donnees = date du dernier scrutin Dosleg, jamais Last-Modified du zip.
  "S6-DOSLEG": { unite: "jc", retard: 60, alerte: 95 },
  // DOLE (DILA) : livraisons du soir jusqu'à 5 fois/semaine selon
  // l'actualité parlementaire. date_donnees = max(DATE_DERNIERE_MODIFICATION),
  // jamais last_update data.gouv. Gap max observé 12 j (listing 22/08/2026).
  // 20/35 j couvre une quinzaine creuse sans attendre la trêve des scrutins.
  S43: { unite: "jc", retard: 20, alerte: 35 },
  // Hebdomadaire / mensuelle (lag de clôture comptable pour S13)
  S14: { unite: "jc", retard: 10, alerte: 18 },
  // Même génération hebdomadaire que S14 : les deux fichiers sont publiés à
  // une seconde d'écart par la HATVP, d'où des seuils identiques.
  S15: { unite: "jc", retard: 10, alerte: 18 },
  S13: { unite: "jc", retard: 65, alerte: 80 },
  // Mensuelle stricte : le stock Sirene paraît le 1er de chaque mois, et sa
  // date de donnée est celle du dernier traitement des unités retenues (la
  // veille de la publication). L'âge oscille donc de ~0 à ~32 jours en
  // régime normal ; 55 jours = un millésime entièrement sauté.
  S18: { unite: "jc", retard: 40, alerte: 55 },
  // Trimestrielle
  S17: { unite: "jc", retard: 110, alerte: 150 },
  // Trimestrielle GFS Eurostat t+113 ; date_donnees = fin du trimestre
  // de TIME max, jamais `updated` ; 220 j ≈ Q+1 en retard de ~2 sem. ;
  // 260 j ≈ Q+1 en retard d'~6 sem. (S17 110/150 sonnerait dès la parution).
  S41: { unite: "jc", retard: 220, alerte: 260 },
  // Annuelles « simples »
  // Millésime figé : ingest_budget_structure.py lit « plf-2026-budget-vert »,
  // écrit en dur.
  S20: { unite: "jc", retard: 400, alerte: 440, editionFigee: true },
  // Millésime figé : DECRETS_AIDE_PUBLIQUE (ingest_financement.py) est une
  // liste de décrets consultés, tenue à la main.
  S37: { unite: "jc", retard: 400, alerte: 440, editionFigee: true },
  // Millésime figé : ingest_trainvie.py n'est fait que de constantes
  // relevées à la main dans des publications officielles (Cour des comptes,
  // DGCL, lois de finances) ; un rapport paru n'y entre pas seul.
  S31: { unite: "jc", retard: 450, alerte: 550, editionFigee: true },
  // Annuelle EDP (notification avril N+1). date_donnees = 31/12 du TIME
  // max, jamais `updated`. 400/440 sonnerait dès février, avant la
  // notification d'avril (~477 j après le 31/12). 520/600 = 17/20 mois.
  S42: { unite: "jc", retard: 520, alerte: 600 },
  // Annuelle GFS (juillet N+1). date_donnees = 31/12 du TIME max,
  // jamais `updated`. 400/440 sonnerait dès février, avant la
  // publication de juillet. 520/600 = 17/20 mois, comme S42 EDP.
  S44: { unite: "jc", retard: 520, alerte: 600 },
  // Annuelle GFS détaillée (COFOG). date_donnees = 31/12 du TIME max de
  // TOTAL (2024 → 2024-12-31), jamais `updated` ni
  // OBS_PERIOD_OVERALL_LATEST. Calendrier amont : transmission à t+12 mois
  // (règlement 549/2013), diffusion principale EN FÉVRIER t+2 (métadonnées
  // ESMS gov_10a_exp, relevées le 11/11/2026) — et non « juillet N+1 » :
  // la diffusion du 21/10/2026 listait TIME 2025 sans valeur FR. L'édition
  // précédente a donc ~790 jours quand la suivante paraît (31/12/2024 →
  // fin février 2027). 820 ≈ fin mars t+2, un mois après la diffusion
  // principale ; 900 ≈ mi-juin. 650/750 la disait « à surveiller » chaque
  // année dès la mi-octobre, sans retard amont.
  S49: { unite: "jc", retard: 820, alerte: 900 },
  // Annuelle INSEE comptes des APU (Insee Résultats, mai N+1).
  // date_donnees = 31/12 de l'année max (2025 → 2025-12-31), jamais
  // modified Melodi (2026-06-08) ni la date de parution (29/05/2026).
  // 520/600 comme S44 : millésime 2025 déjà là ; 400/440 sonnerait
  // dès février, avant la parution de mai.
  // Millésime figé : ingest_comptes_apu_insee.py lit la publication Insee
  // Résultats 8988845, écrite en dur.
  S50: { unite: "jc", retard: 520, alerte: 600, editionFigee: true },
  // Même publication Insee Résultats 8988845 que S50 (tableau 3.204,
  // S13112) : millésime = 31/12 de l'année max, jamais modified Melodi.
  // 520/600 comme S50/S44.
  // Millésime figé : même publication 8988845, écrite en dur
  // (ingest_odac_insee.py).
  S51: { unite: "jc", retard: 520, alerte: 600, editionFigee: true },
  // Annuelle CGE : millésime = 31/12 de la pièce de synthèse (xlsx),
  // jamais modified du catalogue. Les balances ligne à ligne peuvent
  // porter N+1 avant que la pièce ne l'ajoute ; 650/750 = 21,5/25 mois
  // couvre un exercice de retard de la pièce sans sonner dès février.
  S22: { unite: "jc", retard: 650, alerte: 750 },
  // Annuelle DREES, comptes de la protection sociale. date_donnees =
  // 31/12 de l'année max (2024 → 2024-12-31), jamais last_update.
  // Calendrier amont relevé le 11/11/2026 : l'année N paraît en décembre
  // N+1 (export 305 du 18/12/2025 pour 2024, fichier « 1959 à 2024 » du
  // 17/12/2025). L'édition précédente a alors ~717 jours : 650/750 la
  // disait « à surveiller » chaque année du 12 octobre à la parution, sans
  // retard amont. 730 = 31/12 N+1, passé la parution habituelle ; 800 ≈
  // mi-mars. Une seule parution observée : à revoir à la suivante.
  S45: { unite: "jc", retard: 730, alerte: 800 },
  // Annuelle IRCOM (DGFiP). date_donnees = 31/12 de l'année des
  // REVENUS (2024 → 2024-12-31), jamais last_update data.gouv.
  // Calendrier amont (created_at des ressources, relevé le 11/11/2026) :
  // revenus 2020 le 21/06/2022, 2021 le 08/06/2023, 2022 le 10/06/2024,
  // 2023 le 09/04/2025, 2024 le 07/04/2026 (les millésimes antérieurs ont
  // tous été re-versés le 27/12/2021 : leur date est perdue). L'édition
  // précédente a alors 828 à 903 jours : 650/750 la disait « à surveiller »
  // dès octobre et « en retard » en janvier, l'amont étant à l'heure. 910
  // couvre la parution la plus tardive observée (21/06, 903 j) ; 970 ≈ fin
  // août N+2.
  S47: { unite: "jc", retard: 910, alerte: 970 },
  // Annuelle REI (DGFiP). date_donnees = 31/12 de l'année
  // d'IMPOSITION (2025 → 2025-12-31), jamais last_update data.gouv ni
  // last-modified du zip. Calendrier amont relevé le 11/11/2026 : REI 2023
  // versé le 29/05/2024, REI 2025 le 12/05/2026 (la date du REI 2024 est
  // perdue : toutes les ressources ont été re-versées le 17/10/2025).
  // L'édition précédente a ~500 jours quand la suivante paraît : 650/750
  // ne signalait un REI manquant qu'en octobre N+2. 560 ≈ mi-juillet N+2,
  // 650 ≈ mi-octobre.
  S48: { unite: "jc", retard: 560, alerte: 650 },
  // Annuelles à décalage structurel documenté
  // Millésime figé : « plf25-depenses-2025-selon-destination », écrit en dur
  // (ingest_budget_structure.py).
  S21: { unite: "jc", retard: 400, alerte: 440, editionFigee: true },
  // Publication open data du PLF 2025 = 11/10/2024 (pas le dépôt AN
  // du 10/10). Aucun équivalent PLF 2026 en données : le seuil annuel
  // simple rend le silence visible, comme S21. Millésime figé :
  // ingest_recettes_plf.py lit le jeu « plf25-… », écrit en dur.
  S46: { unite: "jc", retard: 400, alerte: 440, editionFigee: true },
  // Millésimes figés : jaune « plf25-… » (ingest_budget_structure.py) ;
  // EXERCICES = 2021 → 2024 (ingest_financement.py).
  S23: { unite: "jc", retard: 760, alerte: 850, editionFigee: true },
  S25: { unite: "jc", retard: 850, alerte: 950, editionFigee: true },
  S38: { unite: "jc", retard: 730, alerte: 820 },
  "S27-geo-api": { unite: "jc", retard: 400, alerte: 430 },
  // Millésime figé : SLUG_LEG2024, les législatives de 2024 seules.
  S29: { unite: "jc", retard: 1500, alerte: 1800, editionFigee: true },
  // « Par scrutin » comme S29 : l'âge reste élevé entre deux scrutins par
  // construction, l'alerting est donc quasi désactivé (~36/43 mois).
  S26: { unite: "jc", retard: 1100, alerte: 1300 },
  "S27-insee-populations": { unite: "jc", retard: 1500, alerte: 1650 },
  // Quasi statiques : l'âge n'est plus un signal, seul le volume l'est
  "S27-france-geojson": { unite: "jc", retard: 3650, alerte: 5475 },
  // Cadence composite (comptes locaux + dotations)
  // Millésime figé : EXERCICE_COMPTES (ingest_collectivites.py).
  S16: { unite: "jc", retard: 650, alerte: 750, editionFigee: true },
  // Quotidienne, mais calendrier EUROPÉEN : l'export du registre de
  // transparence de l'Union est régénéré chaque soir par le secrétariat
  // commun Parlement européen / Commission, que le calendrier ouvré français
  // — jours fériés légaux compris — ne gouverne pas. D'où des jours
  // calendaires et non des jours ouvrés, contrairement à S4 (HATVP), avec
  // une marge suffisante pour absorber un week-end sans export.
  S40: { unite: "jc", retard: 6, alerte: 12 },
  // Mensuelle événementielle : le dump ADLC est republishé sans
  // nouvelle amende. date_donnees = date de la dernière décision
  // sanctionnée, jamais last_modified. Gap max observé entre deux
  // décisions : 189 j (2013-06-11 → 2013-12-17). 65/80 (S13) sonnerait
  // dès l'été. 200/280 couvre ce silence ; au-delà, le corpus annuel
  // (4 à 15 décisions/an depuis 2009) a décroché.
  S52: { unite: "jc", retard: 200, alerte: 280 },
};

const JOUR_MS = 86_400_000;

/**
 * Dimanche de Pâques (minuit UTC) par l'algorithme de Meeus/Butcher —
 * même calcul que la supervision serveur, pour que les deux comptent
 * exactement les mêmes jours ouvrés.
 */
function paquesUTC(annee: number): number {
  const a = annee % 19;
  const b = Math.floor(annee / 100);
  const c = annee % 100;
  const d = Math.floor(b / 4);
  const e = b % 4;
  const f = Math.floor((b + 8) / 25);
  const g = Math.floor((b - f + 1) / 3);
  const h = (19 * a + b - d - g + 15) % 30;
  const i = Math.floor(c / 4);
  const k = c % 4;
  const l = (32 + 2 * e + 2 * i - h - k) % 7;
  const m = Math.floor((a + 11 * h + 22 * l) / 451);
  const mois = Math.floor((h + l - 7 * m + 114) / 31);
  const jour = ((h + l - 7 * m + 114) % 31) + 1;
  return Date.UTC(annee, mois - 1, jour);
}

const FERIES = new Map<number, Set<number>>();

/** Les 11 jours fériés légaux français d'une année (minuits UTC). */
function joursFeries(annee: number): Set<number> {
  const connu = FERIES.get(annee);
  if (connu) return connu;
  const p = paquesUTC(annee);
  const feries = new Set<number>([
    Date.UTC(annee, 0, 1), // Jour de l'an
    p + 1 * JOUR_MS, // Lundi de Pâques
    Date.UTC(annee, 4, 1), // Fête du Travail
    Date.UTC(annee, 4, 8), // Victoire 1945
    p + 39 * JOUR_MS, // Ascension
    p + 50 * JOUR_MS, // Lundi de Pentecôte
    Date.UTC(annee, 6, 14), // Fête nationale
    Date.UTC(annee, 7, 15), // Assomption
    Date.UTC(annee, 10, 1), // Toussaint
    Date.UTC(annee, 10, 11), // Armistice
    Date.UTC(annee, 11, 25), // Noël
  ]);
  FERIES.set(annee, feries);
  return feries;
}

/** Jours ouvrés strictement après `debut`, jusqu'à `fin` inclus. */
function ageJoursOuvres(debut: number, fin: number): number {
  let total = 0;
  for (let j = debut + JOUR_MS; j <= fin; j += JOUR_MS) {
    const d = new Date(j);
    const jourSemaine = d.getUTCDay();
    if (jourSemaine === 0 || jourSemaine === 6) continue;
    if (joursFeries(d.getUTCFullYear()).has(j)) continue;
    total += 1;
  }
  return total;
}

/** Le jour civil parisien d'un instant, au format AAAA-MM-JJ. */
const FORMAT_JOUR = new Intl.DateTimeFormat("fr-CA", {
  timeZone: "Europe/Paris",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

/** Minuit UTC du jour AAAA-MM-JJ ; `null` si la date est illisible. */
function jourUTC(iso: string): number | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso.trim());
  if (!m) return null;
  const t = Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  return Number.isNaN(t) ? null : t;
}

/**
 * Fraîcheur d'une source : son âge comparé à SES deux seuils.
 *
 * - `a_jour` sous le seuil de retard — l'âge est celui d'un cycle normal ;
 * - `a_surveiller` entre les deux seuils — l'écart peut encore être un
 *   simple décalage de calendrier ;
 * - `en_retard` au-delà du seuil d'alerte ;
 * - `attente_edition` quand le dépassement excède à son tour la largeur de
 *   la bande de surveillance (seuil d'alerte + [alerte − retard]) : la
 *   source a alors dépassé son seuil d'alerte d'autant que toute la marge
 *   qui le précédait, ce qui ne se rattrape plus par un décalage de
 *   publication de quelques semaines ;
 * - `non_calibre` si la source n'a pas de ligne dans le référentiel — on
 *   affiche alors l'absence de seuil, jamais un état inventé.
 */
export function evalueFraicheur(
  sourceId: string,
  dateDonnees: string,
  maintenant: Date,
): Fraicheur {
  const debut = jourUTC(dateDonnees);
  const fin = jourUTC(FORMAT_JOUR.format(maintenant));
  const ageCalendaire =
    debut !== null && fin !== null ? Math.max(Math.round((fin - debut) / JOUR_MS), 0) : 0;
  const seuil = SEUILS_SOURCES[sourceId];
  if (!seuil || debut === null || fin === null) {
    return {
      niveau: "non_calibre",
      ageJours: ageCalendaire,
      unite: "jc",
      seuilRetardJours: null,
      seuilAlerteJours: null,
      editionFigee: false,
    };
  }
  const ageJours = seuil.unite === "jo" ? ageJoursOuvres(debut, fin) : ageCalendaire;
  const bande = Math.max(seuil.alerte - seuil.retard, 1);
  const niveau: NiveauFraicheur =
    ageJours <= seuil.retard
      ? "a_jour"
      : ageJours <= seuil.alerte
        ? "a_surveiller"
        : ageJours <= seuil.alerte + bande
          ? "en_retard"
          : "attente_edition";
  return {
    niveau,
    ageJours,
    unite: seuil.unite,
    seuilRetardJours: seuil.retard,
    seuilAlerteJours: seuil.alerte,
    editionFigee: seuil.editionFigee === true,
  };
}

/**
 * Le constat affiché pour une source en attente, sans majuscule ni point.
 * Il dit ce que le site sait — l'édition qu'il a INGÉRÉE —, jamais ce que
 * l'amont a publié ou non ; et, pour un millésime figé, que l'ingestion ne
 * la verrait pas seule.
 */
export function constatAttente(f: Pick<Fraicheur, "editionFigee">): string {
  return f.editionFigee
    ? "aucune édition plus récente n’a été ingérée à ce jour — millésime fixé par le pipeline : une édition plus récente n’y entrerait pas sans le modifier"
    : "aucune édition plus récente n’a été ingérée à ce jour";
}

/* ------------------------------------------------------------------ */
/* Phrases — les mêmes au build et à la lecture                        */
/* ------------------------------------------------------------------ */

/** Libellé et jeton de couleur de chaque niveau (la pastille n'est jamais seule). */
export const NIVEAUX: Record<NiveauFraicheur, { jeton: string; libelle: string }> = {
  a_jour: { jeton: "var(--status-good)", libelle: "À jour" },
  a_surveiller: { jeton: "var(--status-warning)", libelle: "À surveiller" },
  en_retard: { jeton: "var(--status-serious)", libelle: "En retard" },
  attente_edition: {
    jeton: "var(--status-critical)",
    libelle: "En attente d’une édition",
  },
  non_calibre: { jeton: "var(--viz-autre)", libelle: "Seuil non calibré" },
};

/** « 678 jours », « 2 jours ouvrés » — l'unité est celle du seuil de la source. */
export function libelleAge(f: Pick<Fraicheur, "ageJours" | "unite">): string {
  const pluriel = f.ageJours >= 2 ? "s" : "";
  const unite = f.unite === "jo" ? `jour${pluriel} ouvré${pluriel}` : `jour${pluriel}`;
  return `${formatNombre(f.ageJours)} ${unite}`;
}

/** Seuil affiché avec son unité (« 850 j », « 20 j ouvrés »). */
function libelleSeuil(f: Fraicheur, jours: number): string {
  return `${formatNombre(jours)} ${f.unite === "jo" ? "j ouvrés" : "j"}`;
}

/**
 * La phrase exacte derrière le badge — factuelle et DATÉE : l'âge est dit
 * « au » jour du calcul, pour que la phrase reste vraie quand elle est lue
 * plus tard qu'elle n'a été écrite (rendu serveur lu sans JavaScript).
 *
 * Pour une source en attente, elle ne dit RIEN de l'amont, de l'avenir ni
 * de l'intention de l'éditeur : seulement qu'aucune édition plus récente
 * n'était INGÉRÉE à ce jour-là (`constatAttente`). C'est le seul fait que le
 * site vérifie.
 */
export function phraseFraicheur(dateDonnees: string, f: Fraicheur, maintenant: Date): string {
  const donneesAu = `Données au ${formatDateFr(dateDonnees)}`;
  const age = `${libelleAge(f)} au ${formatDateFr(maintenant.toISOString())}`;
  if (f.niveau === "non_calibre") {
    return `${donneesAu}, soit ${age}. Aucun seuil n’est calibré pour cette source : son état n’est pas évalué.`;
  }
  const seuils = `seuils calibrés pour cette source : ${libelleSeuil(f, f.seuilRetardJours ?? 0)} (à surveiller) / ${libelleSeuil(f, f.seuilAlerteJours ?? 0)} (alerte)`;
  if (f.niveau === "attente_edition") {
    const constat = constatAttente(f);
    return `${donneesAu}. ${constat.charAt(0).toUpperCase()}${constat.slice(1)} — ${age}, ${seuils}.`;
  }
  return `${donneesAu}, soit ${age} — ${seuils}.`;
}

/** Ce qu'il faut d'une source pour en évaluer la fraîcheur. */
export type SourceDatee = { source_id: string; nom: string; date_donnees: string };

export type SyntheseFraicheur = {
  total: number;
  parNiveau: Record<NiveauFraicheur, number>;
  /** Sources en attente d'une édition, avec leur fraîcheur, dans l'ordre reçu. */
  enAttente: { source: SourceDatee; fraicheur: Fraicheur }[];
};

/** Décompte des niveaux à l'instant `maintenant` (synthèse en tête de /donnees). */
export function syntheseFraicheur(sources: SourceDatee[], maintenant: Date): SyntheseFraicheur {
  const parNiveau: Record<NiveauFraicheur, number> = {
    a_jour: 0,
    a_surveiller: 0,
    en_retard: 0,
    attente_edition: 0,
    non_calibre: 0,
  };
  const enAttente: SyntheseFraicheur["enAttente"] = [];
  for (const s of sources) {
    const f = evalueFraicheur(s.source_id, s.date_donnees, maintenant);
    parNiveau[f.niveau] += 1;
    if (f.niveau === "attente_edition") enAttente.push({ source: s, fraicheur: f });
  }
  return { total: sources.length, parNiveau, enAttente };
}

/**
 * La phrase de synthèse, sans point final : « 33 sources sur 44 sont à
 * jour au regard du seuil calibré pour chacune, 7 à surveiller… ».
 */
export function phraseSynthese(s: SyntheseFraicheur): string {
  const n = s.parNiveau;
  const tete = `${formatNombre(n.a_jour)} source${n.a_jour > 1 ? "s" : ""} sur ${formatNombre(s.total)}`;
  return [
    `${tete} ${n.a_jour > 1 ? "sont à jour" : "est à jour"} au regard du seuil calibré pour chacune`,
    n.a_surveiller > 0 ? `${n.a_surveiller} à surveiller` : null,
    n.en_retard > 0 ? `${n.en_retard} en retard` : null,
    n.non_calibre > 0 ? `${n.non_calibre} sans seuil calibré` : null,
    n.attente_edition > 0 ? `${n.attente_edition} en attente d’une édition plus récente` : null,
  ]
    .filter((x) => x !== null)
    .join(", ");
}

/**
 * Le jour auquel l'état est calculé, dit au lecteur. Au rendu serveur (et
 * donc sans JavaScript), c'est le jour de la construction du site ; dans le
 * navigateur, la date de lecture — et si elles diffèrent, la page le dit.
 */
export function ancrageCalcul(maintenant: number, construitLe: number): string {
  const lu = formatDateFr(new Date(maintenant).toISOString());
  const construit = formatDateFr(new Date(construitLe).toISOString());
  return lu === construit
    ? `État calculé le ${construit}, jour de construction du site`
    : `État recalculé le ${lu}, date de votre lecture (site construit le ${construit})`;
}

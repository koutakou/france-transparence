/**
 * Requêtes SQL du contenu des déclarations d'intérêts HATVP (S15, pipeline
 * P15 `ingest_hatvp_declarations`). Fichier PROPRE aux fiches d'élus
 * (`/elus/[id]`) : aucune autre page ne doit l'importer.
 *
 * Ce que ce module sert, et ce qu'il ne servira jamais :
 *
 * - il sert le CONTENU d'une déclaration d'INTÉRÊTS (DI/DIA), verbatim,
 *   daté, rubrique par rubrique ;
 * - il ne sert AUCUN agrégat, AUCUN classement, AUCUN total. Les libellés
 *   amont ne sont pas normalisés (« Education Nationale » / « Education
 *   nationale » / « ASSEMBLEE NATIONALE » cohabitent, « Isère(38) » et
 *   « Conseillermunicipal » sont des valeurs réelles du fichier) et les
 *   montants sont stockés en TEXTE : il n'existe donc, dans le schéma
 *   lui-même, aucune colonne numérique à sommer. Ce n'est pas une lacune,
 *   c'est la garantie ;
 * - il ne sert rien de PATRIMONIAL. Le pipeline refuse ces blocs deux fois
 *   (par type de déclaration ET par nom de balise) — art. LO 135-2 du code
 *   électoral : la déclaration de situation patrimoniale d'un parlementaire
 *   ne se consulte qu'en préfecture, et sa divulgation est punie de
 *   45 000 € d'amende. Aucune requête d'ici n'y touche, et il n'y a rien à
 *   y toucher.
 *
 * DISTINCTION CARDINALE, portée jusque dans les types : « la personne a
 * déclaré n'avoir rien à déclarer » (`RubriqueDeclaree.neant === 1`, un
 * FAIT publié par la HATVP) n'est PAS « nous n'avons pas la donnée »
 * (`InteretsElu.apparie === false`, une ignorance de notre côté). L'écran
 * doit dire les deux, et jamais l'une à la place de l'autre.
 *
 * Toutes les fonctions renvoient `null` tant que la base n'est pas
 * construite ou que le pipeline n'a pas tourné (tables absentes) : la page
 * affiche alors un message honnête. SQL 100 % paramétré.
 */
import { getDb, type MetaSource } from "@/lib/db";

/* ------------------------------------------------------------------ */
/* Source                                                              */
/* ------------------------------------------------------------------ */

/** Identifiant `meta_sources` de la source (HATVP declarations.xml). */
export const SOURCE_DECLARATIONS = "S15";

/** Fraîcheur de S15, ou `null` (base absente / pipeline jamais lancé). */
export function getSourceDeclarations(): MetaSource | null {
  const db = getDb();
  if (!db || !tablesPresentes()) return null;
  return (
    (db
      .prepare("SELECT * FROM meta_sources WHERE source_id = ?")
      .get(SOURCE_DECLARATIONS) as MetaSource | undefined) ?? null
  );
}

/* ------------------------------------------------------------------ */
/* Garde « pipeline pas encore passé »                                 */
/* ------------------------------------------------------------------ */

const TABLES = [
  "hatvp_decl_interets",
  "hatvp_decl_rubriques",
  "hatvp_decl_lignes",
  "hatvp_decl_montants",
] as const;

let tablesVues: boolean | null = null;

/**
 * Vrai si les quatre tables de P15 existent.
 *
 * POURQUOI ce garde-fou, alors que `getDb()` couvre déjà la base absente :
 * une base construite AVANT ce pipeline existe bel et bien, mais n'a pas ces
 * tables — et une requête sur une table manquante fait échouer le build
 * entier, pas seulement le bloc concerné. Ici l'absence dégrade proprement :
 * la fiche affiche « pas de donnée », ce qui est exactement la vérité.
 */
function tablesPresentes(): boolean {
  if (tablesVues !== null) return tablesVues;
  const db = getDb();
  if (!db) return false;
  const marques = TABLES.map(() => "?").join(", ");
  const nb = (
    db
      .prepare(
        `SELECT COUNT(*) AS n FROM sqlite_master
         WHERE type = 'table' AND name IN (${marques})`,
      )
      .get(...TABLES) as { n: number }
  ).n;
  tablesVues = nb === TABLES.length;
  return tablesVues;
}

/* ------------------------------------------------------------------ */
/* Rubriques                                                           */
/* ------------------------------------------------------------------ */

/**
 * Intitulés des rubriques, dans l'ordre de la déclaration.
 *
 * Ce sont les intitulés du formulaire HATVP, repris tels quels. Ils doublent
 * la table `RUBRIQUES` du pipeline (qui, elle, ne stocke que la clé en base :
 * la répéter 15 841 fois dans SQLite pour économiser six lignes ici n'aurait
 * pas de sens). Une clé inconnue est affichée telle quelle plutôt que
 * masquée — dégradation propre, jamais une erreur.
 */
export const LIBELLES_RUBRIQUES: Record<string, string> = {
  mandat_electif: "Mandats électifs et fonctions électives",
  dirigeant: "Participations aux organes dirigeants d’un organisme",
  participation_financiere:
    "Participations financières directes dans le capital d’une société",
  activite_5ans: "Activités professionnelles des cinq dernières années",
  consultant: "Activités de consultant",
  benevole:
    "Fonctions bénévoles susceptibles de faire naître un conflit d’intérêts",
  observation: "Observations",
};

/** Codes de déclaration servis par ce module (jamais autre chose). */
export const LIBELLES_TYPE_DECLARATION: Record<string, string> = {
  DI: "Déclaration d’intérêts",
  DIA: "Déclaration d’intérêts et d’activités",
};

/* ------------------------------------------------------------------ */
/* Types                                                               */
/* ------------------------------------------------------------------ */

/** Un montant de rémunération ANNUEL et DATÉ, tel qu'il a été déclaré. */
export type MontantDeclare = {
  /** Année déclarée, verbatim (« 2024 »). */
  annee: string;
  /** Montant verbatim (« 70 676 ») — TEXTE : ni sommable, ni classable. */
  montant: string;
  /** « Net » / « Brut » natifs, absent si la source ne l'a pas dit. */
  brut_net?: string;
};

/**
 * Une ligne d'intérêt déclarée. Tout y est verbatim.
 *
 * POURQUOI des champs OPTIONNELS plutôt que `null` : ces objets traversent la
 * frontière serveur→client dans le payload RSC, lui-même inliné dans le HTML
 * statique. Un `"description": null` sérialisé coûte une vingtaine d'octets
 * par champ et par ligne, pour ne rien dire ; sur la fiche la plus chargée
 * (424 lignes) les seuls champs vides pesaient une soixantaine de kilo-octets.
 * L'absence de clé porte exactement la même information — « la source n'a rien
 * mis là » — et ne pèse rien. La règle d'affichage, elle, ne change pas d'un
 * iota : un champ absent s'affiche comme absent, jamais comme un zéro.
 */
export type LigneInteret = {
  id: number;
  /** Société, employeur, structure, mandat — l'entité déclarée. */
  libelle?: string;
  /** Ce qui y est exercé (fonction, activité) ou le texte d'observation. */
  description?: string;
  /** Verbatim (« 11/2019 ») : la source ne donne pas toujours le jour. */
  date_debut?: string;
  date_fin?: string;
  commentaire?: string;
  /** 1 = activité conservée pendant le mandat, 0 = non, absent = non dit. */
  conservee?: number;
  /** Participations financières : valeurs déclarées, verbatim (« 0 » compris). */
  evaluation?: string;
  capital_detenu?: string;
  nombre_parts?: string;
  remuneration_libre?: string;
  activite_conseil?: string;
  organisation_conseil?: string;
  montants?: MontantDeclare[];
};

/** Une rubrique d'une déclaration. */
export type RubriqueDeclaree = {
  /** Clé interne (`mandat_electif`…). */
  rubrique: string;
  /** Intitulé HATVP prêt à afficher. */
  libelle: string;
  /**
   * 1 = la personne a déclaré « néant » pour cette rubrique — un FAIT, qui
   * autorise l'écran à écrire « rien à déclarer » ; 0 = rubrique renseignée ;
   * `null` = la source ne s'est pas prononcée, et alors on ne dit rien.
   */
  neant: number | null;
  lignes: LigneInteret[];
};

/** Une déclaration d'intérêts publiée, avec son contenu. */
export type DeclarationInterets = {
  uuid: string;
  /** 'DI' | 'DIA' — aucun autre type n'entre en base. */
  type_declaration: string;
  type_declaration_libelle: string | null;
  /** Date de dépôt ISO. C'est la date qui doit accompagner tout affichage. */
  date_depot: string | null;
  /** 1 = déclaration modificative (elle ne remplace pas les précédentes). */
  modificative: number;
  qualite_declarant: string | null;
  organe_libelle: string | null;
  type_mandat: string | null;
  nb_lignes: number;
  rubriques: RubriqueDeclaree[];
};

/** Ce que l'on sait — et ce que l'on ne sait pas — des intérêts d'un élu. */
export type InteretsElu = {
  /**
   * FAUX quand aucune déclaration d'intérêts n'a pu être rattachée à cette
   * fiche : l'écran doit alors dire « pas de donnée chez nous », JAMAIS
   * « aucun intérêt déclaré ». Les deux phrases n'ont rien à voir.
   */
  apparie: boolean;
  declarations: DeclarationInterets[];
  /** Total de lignes servies (pour une mention honnête, pas pour un classement). */
  nb_lignes: number;
};

/* ------------------------------------------------------------------ */
/* Requête                                                             */
/* ------------------------------------------------------------------ */

/**
 * Retire les clés valant `null` — l'absence de valeur devient l'absence de
 * clé, ce qui ne change rien au sens et allège d'autant le payload RSC.
 * Voir le commentaire de `LigneInteret` pour la mesure qui a motivé ça.
 */
function sansVide<T extends object>(brut: Record<string, unknown>): T {
  for (const cle of Object.keys(brut)) {
    if (brut[cle] === null || brut[cle] === undefined) delete brut[cle];
  }
  return brut as T;
}

type LigneSql = Omit<LigneInteret, "montants"> & {
  declaration_uuid: string;
  rubrique: string;
  rubrique_ordre: number;
};

/**
 * Contenu des déclarations d'intérêts rattachées à une fiche d'élu.
 *
 * `null` = base absente ou pipeline P15 jamais passé (on ne sait rien, et on
 * ne prétend pas le contraire). Un objet avec `apparie: false` = la base est
 * là, le pipeline a tourné, et cette fiche n'a AUCUNE déclaration rattachée —
 * ce qui reste une absence de donnée chez nous, pas une absence de
 * déclaration : 104 des 1 053 fiches sont dans ce cas, dont 96 dont le nom ne
 * figure tout simplement pas dans le fichier amont.
 *
 * Quatre requêtes à plat plutôt qu'une jointure : les montants multiplieraient
 * les lignes, et l'assemblage se fait ici, une seule fois, en mémoire.
 */
export function getInteretsElu(eluId: string): InteretsElu | null {
  const db = getDb();
  if (!db || !tablesPresentes()) return null;

  const declarations = db
    .prepare(
      `SELECT uuid, type_declaration, type_declaration_libelle, date_depot,
              modificative, qualite_declarant, organe_libelle, type_mandat,
              nb_lignes
       FROM hatvp_decl_interets
       WHERE elu_id = ?
       ORDER BY COALESCE(date_depot, '') DESC, uuid`,
    )
    .all(eluId) as Omit<DeclarationInterets, "rubriques">[];
  if (declarations.length === 0) {
    return { apparie: false, declarations: [], nb_lignes: 0 };
  }

  const lignes = db
    .prepare(
      `SELECT id, declaration_uuid, rubrique, rubrique_ordre, rang, libelle,
              description, date_debut, date_fin, commentaire, conservee,
              evaluation, capital_detenu, nombre_parts, remuneration_libre,
              activite_conseil, organisation_conseil
       FROM hatvp_decl_lignes
       WHERE elu_id = ?
       ORDER BY declaration_uuid, rubrique_ordre, rang`,
    )
    .all(eluId) as LigneSql[];

  const montants = db
    .prepare(
      `SELECT m.ligne_id, m.annee, m.montant, m.brut_net
       FROM hatvp_decl_montants m
       JOIN hatvp_decl_lignes l ON l.id = m.ligne_id
       WHERE l.elu_id = ?
       ORDER BY m.ligne_id, m.annee`,
    )
    .all(eluId) as (MontantDeclare & { ligne_id: number })[];

  const rubriques = db
    .prepare(
      `SELECT r.declaration_uuid, r.rubrique, r.rubrique_ordre, r.neant
       FROM hatvp_decl_rubriques r
       JOIN hatvp_decl_interets d ON d.uuid = r.declaration_uuid
       WHERE d.elu_id = ?
       ORDER BY r.declaration_uuid, r.rubrique_ordre`,
    )
    .all(eluId) as {
    declaration_uuid: string;
    rubrique: string;
    rubrique_ordre: number;
    neant: number | null;
  }[];

  // Assemblage montants → lignes → rubriques → déclarations.
  const montantsParLigne = new Map<number, MontantDeclare[]>();
  for (const m of montants) {
    const liste = montantsParLigne.get(m.ligne_id);
    const valeur = sansVide<MontantDeclare>({
      annee: m.annee,
      montant: m.montant,
      brut_net: m.brut_net,
    });
    if (liste) liste.push(valeur);
    else montantsParLigne.set(m.ligne_id, [valeur]);
  }

  const lignesParCle = new Map<string, LigneInteret[]>();
  for (const l of lignes) {
    const cle = `${l.declaration_uuid}|${l.rubrique}`;
    const montantsLigne = montantsParLigne.get(l.id);
    const ligne = sansVide<LigneInteret>({
      id: l.id,
      libelle: l.libelle,
      description: l.description,
      date_debut: l.date_debut,
      date_fin: l.date_fin,
      commentaire: l.commentaire,
      conservee: l.conservee,
      evaluation: l.evaluation,
      capital_detenu: l.capital_detenu,
      nombre_parts: l.nombre_parts,
      remuneration_libre: l.remuneration_libre,
      activite_conseil: l.activite_conseil,
      organisation_conseil: l.organisation_conseil,
      montants: montantsLigne && montantsLigne.length > 0 ? montantsLigne : null,
    });
    const liste = lignesParCle.get(cle);
    if (liste) liste.push(ligne);
    else lignesParCle.set(cle, [ligne]);
  }

  const rubriquesParDeclaration = new Map<string, RubriqueDeclaree[]>();
  for (const r of rubriques) {
    const rubrique: RubriqueDeclaree = {
      rubrique: r.rubrique,
      libelle: LIBELLES_RUBRIQUES[r.rubrique] ?? r.rubrique,
      neant: r.neant,
      lignes: lignesParCle.get(`${r.declaration_uuid}|${r.rubrique}`) ?? [],
    };
    const liste = rubriquesParDeclaration.get(r.declaration_uuid);
    if (liste) liste.push(rubrique);
    else rubriquesParDeclaration.set(r.declaration_uuid, [rubrique]);
  }

  return {
    apparie: true,
    nb_lignes: lignes.length,
    declarations: declarations.map((d) => ({
      ...d,
      rubriques: rubriquesParDeclaration.get(d.uuid) ?? [],
    })),
  };
}

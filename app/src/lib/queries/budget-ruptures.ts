/**
 * Ruptures de périmètre des cellules de total de `budget_mensuel` (S13).
 *
 * Le pipeline P1 contrôle, à chaque ingestion, quatre identités comptables
 * (recettes nettes = fiscales + non fiscales ; fiscales = cinq impôts ;
 * dépenses nettes = sept titres ; prélèvements sur recettes = collectivités
 * + Union européenne) et écrit dans `budget_mensuel_ruptures` chaque cellule
 * de total qui ne les respecte pas. La valeur amont reste servie telle
 * quelle : elle n'est jamais rectifiée. Ce qui change, c'est qu'AUCUNE
 * variation n'est calculée à travers elle (ni contre N−1, ni sur la courbe
 * des cumuls), puisqu'elle n'a pas la définition des mois auxquels on la
 * comparerait — et la page le dit au contact du chiffre.
 *
 * Mesuré le 11/11/2026 : une seule cellule en rupture sur 165 mois, le total
 * des recettes nettes du 30/09/2026 (voir le pipeline pour le détail).
 */
import { getDb } from "@/lib/db";
import { formatDateFr } from "@/lib/format";

export interface RupturePerimetre {
  ligneId: string;
  dateFinMois: string;
  annee: number;
  mois: number;
  /** Valeur amont, telle quelle (= `budget_mensuel.montant_cumul`). */
  montantPublie: number;
  /** Identité que respectent les autres mois, en clair. */
  identite: string;
  /** Autre combinaison de lignes publiées qui redonne EXACTEMENT la cellule, sinon null. */
  definitionConstatee: string | null;
}

/** Ensemble des ruptures, indexé par `ligneId|annee|mois`. */
export type Ruptures = Map<string, RupturePerimetre>;

const cle = (ligneId: string, annee: number, mois: number) => `${ligneId}|${annee}|${mois}`;

/**
 * Toutes les ruptures constatées. Vide si la table n'existe pas (base
 * antérieure au contrôle) : rien n'est alors supposé, rien n'est masqué.
 */
export function getRupturesBudget(): Ruptures {
  const ruptures: Ruptures = new Map();
  const db = getDb();
  if (!db) return ruptures;
  const presente = db
    .prepare(
      "SELECT count(*) AS n FROM sqlite_master WHERE type = 'table' AND name = 'budget_mensuel_ruptures'",
    )
    .get() as { n: number } | undefined;
  if ((presente?.n ?? 0) === 0) return ruptures;
  const lignes = db
    .prepare(
      `SELECT ligne_id AS ligneId, date_fin_mois AS dateFinMois, annee, mois,
              montant_publie AS montantPublie, identite,
              definition_constatee AS definitionConstatee
         FROM budget_mensuel_ruptures`,
    )
    .all() as RupturePerimetre[];
  for (const r of lignes) ruptures.set(cle(r.ligneId, r.annee, r.mois), r);
  return ruptures;
}

export function ruptureAu(
  ruptures: Ruptures,
  ligneId: string,
  annee: number,
  mois: number,
): RupturePerimetre | null {
  return ruptures.get(cle(ligneId, annee, mois)) ?? null;
}

/** Pourquoi la comparaison d'une cellule avec N−1 n'est pas calculée. */
export interface ComparaisonRompue {
  rupture: RupturePerimetre;
  /** « mois » : la cellule lue est en rupture ; « n1 » : c'est celle de N−1. */
  cote: "mois" | "n1";
}

/** Rupture qui interdit de comparer (annee, mois) à (annee − 1, mois), sinon null. */
export function comparaisonRompue(
  ruptures: Ruptures,
  ligneId: string,
  annee: number,
  mois: number,
): ComparaisonRompue | null {
  const ici = ruptureAu(ruptures, ligneId, annee, mois);
  if (ici) return { rupture: ici, cote: "mois" };
  const avant = ruptureAu(ruptures, ligneId, annee - 1, mois);
  if (avant) return { rupture: avant, cote: "n1" };
  return null;
}

/**
 * Borne à poser AU CONTACT du chiffre quand sa variation n'est pas publiée.
 * Une phrase, qui nomme ce que contient la ligne amont quand c'est établi.
 */
export function bornePerimetreRompu({ rupture, cote }: ComparaisonRompue): string {
  if (cote === "n1") {
    return `la ligne DGFiP du ${formatDateFr(rupture.dateFinMois)} n'a pas le périmètre de celle-ci : variation non calculée`;
  }
  const contenu = rupture.definitionConstatee
    ? `vaut ${rupture.definitionConstatee} (les autres mois : ${rupture.identite})`
    : `ne vaut pas ${rupture.identite}, contrairement aux autres mois`;
  return `ce mois-ci, la ligne DGFiP ${contenu} : variation non calculée`;
}

/** Une valeur retirée d'une série parce qu'elle n'a pas la définition des autres. */
export interface ValeurOmise {
  annee: number;
  mois: number;
  rupture: RupturePerimetre;
}

/**
 * Retire d'une série de cumuls (12 positions par année) les cellules en
 * rupture : tracées ou tabulées à côté des autres, elles se liraient comme
 * comparables. La position devient `null` (trou dit, jamais un zéro) et la
 * valeur retirée est rendue pour que la page la nomme sous le graphique.
 */
export function omettreRuptures<T extends { annee: number; valeurs: (number | null)[] }>(
  series: T[],
  ruptures: Ruptures,
  ligneId: string,
): { series: T[]; omises: ValeurOmise[] } {
  const omises: ValeurOmise[] = [];
  const nettoyees = series.map((s) => ({
    ...s,
    valeurs: s.valeurs.map((v, i) => {
      const r = v === null ? null : ruptureAu(ruptures, ligneId, s.annee, i + 1);
      if (r) {
        omises.push({ annee: s.annee, mois: i + 1, rupture: r });
        return null;
      }
      return v;
    }),
  }));
  return { series: nettoyees, omises };
}

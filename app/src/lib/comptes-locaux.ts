/**
 * Comptes des collectivités (S16, OFGL) : quand peut-on les dire
 * « provisoires » ? Fonctions PURES, sans import.
 *
 * Calendrier de l'OFGL (description du jeu ofgl-base-communes, relue le
 * 11/11/2026) : les comptes N sont chargés en juillet N+1 sur les balances
 * provisoires de la DGFiP, et les balances définitives sont intégrées « fin
 * décembre ». Des comptes LUS avant le 1er décembre N+1 sont donc
 * provisoires ; lus à partir de là, ils peuvent être l'une ou l'autre
 * version, et le site ne dit plus « provisoires » — sans les dire pour
 * autant « définitifs », ce qu'aucune donnée ingérée n'établit.
 *
 * Le jour de lecture est celui de la dernière ingestion
 * (`meta_sources.date_ingestion`), pas celui de la construction : une page
 * servie plusieurs jours après une ingestion parle des comptes lus ce
 * jour-là. Même règle que `comptes_provisoires` de
 * pipelines/ingest_collectivites.py, qui écrit la note S16.
 */

/** Les comptes de l'exercice lus ce jour-là (ISO) sont-ils certainement provisoires ? */
export function comptesProvisoires(exercice: number, dateLecture: string): boolean {
  return dateLecture.slice(0, 10) < `${exercice + 1}-12-01`;
}

/** Textes de /collectivites qui dépendent du statut des comptes lus. */
export type TextesComptesLocaux = {
  /** Jour de lecture, `JJ/MM/AAAA`. */
  luLe: string;
  /** Mention du badge de fraîcheur. */
  mention: string;
  /** Qualificatif accolé à « exercice N » (« (provisoire) » ou rien). */
  qualif: string;
  /** Périmètre des tuiles (KpiTile, borne au contact du chiffre). */
  perimetre: string;
  /** Suite de la phrase d'en-tête, après « budgets principaux, lus le JJ/MM/AAAA ». */
  suiteEntete: string;
};

/**
 * Tous les textes de la page qui disent « provisoire » ou non, tirés d'une
 * seule règle (`comptesProvisoires`) : aucun ne peut la contredire.
 * `formatDate` est `formatDateFr` (lib/format.ts), passé pour garder le
 * module sans import.
 */
export function textesComptesLocaux(
  exercice: number,
  dateLecture: string,
  formatDate: (iso: string) => string,
): TextesComptesLocaux {
  const provisoires = comptesProvisoires(exercice, dateLecture);
  const luLe = formatDate(dateLecture);
  const suite = `${exercice + 1}`;
  return {
    luLe,
    mention: provisoires ? `comptes ${exercice} provisoires` : `comptes ${exercice} lus le ${luLe}`,
    qualif: provisoires ? " (provisoire)" : "",
    perimetre: `budgets principaux${provisoires ? ", comptes provisoires" : ""} — communes ayant rendu leurs comptes, via agrégats départementaux, hors budgets annexes`,
    suiteEntete: provisoires
      ? ` : provisoires jusqu’à l’intégration des balances définitives de la DGFiP, fin décembre ${suite} (calendrier de l’OFGL)`
      : ` ; l’OFGL intègre fin décembre ${suite} les balances définitives de la DGFiP, et ce site ne distingue pas les deux versions`,
  };
}

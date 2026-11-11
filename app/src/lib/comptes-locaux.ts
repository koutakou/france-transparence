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

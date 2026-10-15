/**
 * Libellé de source d'un badge de fraîcheur : un libellé court ne remplace
 * le nom lu dans `meta_sources` que si la ligne décrit bien la source que ce
 * libellé nomme.
 *
 * POURQUOI : en mode secours, `ingest_referentiels` écrit la ligne S35
 * d'après la source RÉELLEMENT utilisée (liste vérifiée des ministères, pas
 * RefOrgaAdminEtat). Un libellé court indexé sur le seul `source_id`
 * continuait d'afficher « DILA · RefOrga État » sous des données qui n'en
 * venaient pas.
 */

/** Début du `nom` S35 quand RefOrgaAdminEtat a servi (pipelines/ingest_referentiels.py). */
export const NOM_S35_REFORGA = "Référentiel de l'organisation administrative de l'État";

/** Sources dont le libellé court suppose une source précise : préfixe attendu du `nom`. */
const NOM_ATTENDU: Record<string, string> = {
  "S35-reforga-admin-etat": NOM_S35_REFORGA,
};

export function libelleBadgeSource(
  source: { source_id: string; nom: string },
  libellesCourts: Record<string, string>,
): string {
  const court = libellesCourts[source.source_id];
  if (court === undefined) return source.nom;
  const attendu = NOM_ATTENDU[source.source_id];
  if (attendu !== undefined && !source.nom.startsWith(attendu)) return source.nom;
  return court;
}

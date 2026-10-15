/**
 * Gravités des alertes, dans l'ordre canonique de la liste. Module PUR,
 * testé par `npm test` (tests/gravites.test.mjs).
 */
export const GRAVITES_ALERTE = ["haute", "moyenne", "info"] as const;

/**
 * Indice de gravité d'une alerte pour le fragment /data/alertes.json.
 * La table `alertes` n'a pas de contrainte CHECK sur `gravite` : une valeur
 * hors liste retombe sur « info », comme dans le rendu HTML
 * (AlertesListe), jamais sur « haute ».
 */
export function indiceGravite(gravite: string | null): number {
  const i = (GRAVITES_ALERTE as readonly string[]).indexOf(gravite ?? "");
  return i >= 0 ? i : GRAVITES_ALERTE.indexOf("info");
}

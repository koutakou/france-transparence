/**
 * Filtres → URL, côté client (pages statiques : le serveur ne voit plus
 * jamais les query strings). À chaque changement de filtre, l'URL est
 * réécrite (replaceState — pas d'entrée d'historique par clic) pour que la
 * vue reste partageable ; la restauration au chargement passe par
 * `useUrlInitiale` (lecture sans effet, compatible hydratation).
 *
 * À n'appeler QUE depuis un gestionnaire d'événement client.
 */

/**
 * Met à jour des paramètres de l'URL courante sans rechargement ni entrée
 * d'historique — `null` ou `""` supprime le paramètre, le reste est posé.
 * Les autres paramètres et le hash sont préservés.
 */
export function majParamsUrl(maj: Record<string, string | null>): void {
  const params = new URLSearchParams(window.location.search);
  for (const [cle, valeur] of Object.entries(maj)) {
    if (valeur === null || valeur === "") params.delete(cle);
    else params.set(cle, valeur);
  }
  const qs = params.toString();
  window.history.replaceState(
    null,
    "",
    `${window.location.pathname}${qs ? `?${qs}` : ""}${window.location.hash}`,
  );
}

"use client";

import { useSyncExternalStore } from "react";

/**
 * Query string de l'URL courante, lisible PENDANT le rendu client sans
 * effet ni setState (pattern `useSyncExternalStore`) :
 * - au rendu serveur / à l'hydratation : `""` (le HTML statique est
 *   identique pour tous — pas de mismatch d'hydratation) ;
 * - juste après l'hydratation, React re-rend avec la vraie valeur — les
 *   filtres d'une URL partagée (`?gravite=…`, `?famille=…`) se restaurent.
 *
 * La valeur n'est PAS réactive aux `history.replaceState` que nous posons
 * nous-mêmes : les composants la traitent comme un état INITIAL, que toute
 * action utilisateur surcharge définitivement.
 */
const abonnementInerte = () => () => {};

export function useUrlInitiale(): string {
  return useSyncExternalStore(
    abonnementInerte,
    () => window.location.search,
    () => "",
  );
}

"use client";

import { useSyncExternalStore } from "react";

/**
 * Heure du visiteur, à la minute, lisible pendant le rendu client sans
 * effet ni setState (pattern `useSyncExternalStore`, comme `useUrlInitiale`) :
 * - au rendu serveur et à l'hydratation : `construitLe`, l'instant de la
 *   construction — le HTML statique est identique pour tous, sans mismatch ;
 * - juste après l'hydratation, puis chaque minute : l'heure du navigateur.
 *
 * La valeur est arrondie à la minute pour que deux lectures successives
 * renvoient le même nombre (exigence de `useSyncExternalStore`).
 */
const MINUTE_MS = 60_000;

function abonner(rappel: () => void): () => void {
  const minuterie = setInterval(rappel, MINUTE_MS);
  return () => clearInterval(minuterie);
}

function minuteCourante(): number {
  return Math.floor(Date.now() / MINUTE_MS) * MINUTE_MS;
}

export function useHorloge(construitLe: number): number {
  return useSyncExternalStore(abonner, minuteCourante, () => construitLe);
}

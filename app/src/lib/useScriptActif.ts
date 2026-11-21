"use client";

import { useSyncExternalStore } from "react";

/** Aucun changement à suivre : seul compte l'écart serveur / navigateur. */
const abonnementInerte = () => () => {};

/**
 * `false` dans le HTML statique (rendu serveur et hydratation), `true` dès
 * que le script a pris la main. Ce que la page dit d'un chargement ou d'un
 * geste à venir doit rester vrai sans JavaScript.
 */
export function useScriptActif(): boolean {
  return useSyncExternalStore(
    abonnementInerte,
    () => true,
    () => false,
  );
}

/**
 * Le cadre de la carte avant son fond : sans script, il ne doit pas
 * annoncer un chargement qui n'aura jamais lieu (ni texte « Chargement »,
 * ni role=status).
 */
export function cadreAttenteCarte(scriptActif: boolean): {
  texte: string;
  role: "status" | undefined;
} {
  return scriptActif
    ? { texte: "Chargement du fond de carte en cours", role: "status" }
    : { texte: "Carte affichée avec JavaScript activé.", role: undefined };
}

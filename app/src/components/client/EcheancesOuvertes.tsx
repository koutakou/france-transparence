"use client";

import type { ReactNode } from "react";
import { echeancesOuvertes } from "@/lib/echeances";
import { useHorloge } from "@/lib/useHorloge";

/**
 * Liste d'échéances re-filtrée À L'HEURE DU VISITEUR.
 *
 * La page (composant serveur) rend chaque élément elle-même et le passe ici
 * avec sa date limite ; cette île n'affiche que les `maxi` premiers dont la
 * date limite n'est pas passée. Au rendu statique et à l'hydratation, l'heure
 * retenue est celle de la construction (`construitLe`) : le HTML servi sans
 * JavaScript est la liste telle qu'arrêtée à la construction, datée par la
 * page.
 */
export function EcheancesOuvertes({
  elements,
  maxi,
  construitLe,
  vide,
}: {
  elements: { dateLimite: string; noeud: ReactNode }[];
  maxi: number;
  construitLe: number;
  /** Affiché quand aucune échéance livrée n'est encore ouverte. */
  vide: ReactNode;
}) {
  const maintenant = useHorloge(construitLe);
  const ouvertes = echeancesOuvertes(elements, (e) => e.dateLimite, maintenant, maxi);
  return ouvertes.length > 0 ? <>{ouvertes.map((e) => e.noeud)}</> : <>{vide}</>;
}

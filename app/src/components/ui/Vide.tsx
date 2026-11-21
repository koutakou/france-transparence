import { VIDE } from "@/lib/format";

/**
 * Cellule ou valeur sans donnée : « n.d. », développé pour les lecteurs
 * d'écran et au survol. À employer partout où une valeur manque en JSX.
 * Dans une chaîne (titre, CSV, infobulle de graphique), employer `VIDE`.
 */
export function Vide() {
  return <abbr title="non disponible">{VIDE}</abbr>;
}

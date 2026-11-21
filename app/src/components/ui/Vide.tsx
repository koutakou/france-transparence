import { SANS_OBJET, VIDE } from "@/lib/format";

/**
 * Cellule ou valeur sans donnée : « n.d. », développé pour les lecteurs
 * d'écran et au survol. À employer partout où une valeur manque en JSX.
 * Dans une chaîne (titre, CSV, infobulle de graphique), employer `VIDE`.
 * `sansObjet` : la valeur n'existe pas par nature (une loi n'a pas de
 * ministère), ce n'est pas une donnée manquante, d'où « s.o. ».
 */
export function Vide({ sansObjet = false }: { sansObjet?: boolean } = {}) {
  return sansObjet ? (
    <abbr title="sans objet">{SANS_OBJET}</abbr>
  ) : (
    <abbr title="non disponible">{VIDE}</abbr>
  );
}

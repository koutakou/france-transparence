/**
 * Libellés des natures de textes DILA (codes bruts en base : ARRETE,
 * DECRET…) — module PUR, partagé entre la page /documents (serveur) et le
 * flux filtrable (client).
 */

export const LIBELLES_NATURE: Record<string, string> = {
  ARRETE: "Arrêté",
  DECRET: "Décret",
  AVIS: "Avis",
  DECISION: "Décision",
  INFORMATIONS_PARLEMENTAIRES: "Informations parlementaires",
  ANNONCES: "Annonces",
  LOI: "Loi",
  DELIBERATION: "Délibération",
  LISTE: "Liste",
  RAPPORT: "Rapport",
  ORDONNANCE: "Ordonnance",
  ARRET: "Arrêt",
  CITATION: "Citation",
  ACCORD: "Accord",
  ACCORD_FONCTION_PUBLIQUE: "Accord (fonction publique)",
  AVENANT: "Avenant",
  EXEQUATUR: "Exequatur",
  RECOMMANDATION: "Recommandation",
  TABLEAU: "Tableau",
};

/** Code DILA → libellé lisible ; nature absente (réel, 4 textes) → « — ». */
export function libelleNature(code: string | null): string {
  if (!code) return "—";
  const connu = LIBELLES_NATURE[code];
  if (connu) return connu;
  const bas = code.toLowerCase().replace(/_/g, " ");
  return bas.charAt(0).toUpperCase() + bas.slice(1);
}

/** Pluriels pour le donut (seules les natures de tête y apparaissent). */
export const PLURIELS_NATURE: Record<string, string> = {
  ARRETE: "Arrêtés",
  DECRET: "Décrets",
  AVIS: "Avis",
  DECISION: "Décisions",
  INFORMATIONS_PARLEMENTAIRES: "Informations parlementaires",
  LOI: "Lois",
};

export function libelleNaturePluriel(code: string | null): string {
  if (!code) return "Nature non renseignée";
  return PLURIELS_NATURE[code] ?? libelleNature(code);
}

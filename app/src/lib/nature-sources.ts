/**
 * Sources qui ne sont pas des « sources publiques officielles sous licence
 * ouverte » au sens strict, étiquetées en clair sur /donnees (décision du
 * propriétaire du 20/11/2026 : la promesse du site dit « sources publiques
 * officielles, plus quelques consolidations reconnues et créditées »). Module
 * pur, testé par tests/textes-ton.test.mjs.
 */
export interface NatureSource {
  etiquette: string;
  detail: string;
}

const NATURES: Record<string, NatureSource> = {
  S1: {
    etiquette: "Consolidation reconnue, non officielle",
    detail:
      "Consolidation des données essentielles des marchés publics (DECP) faite par Colin Maudry (decp-processing), créditée. Les DECP officielles ne sont pas encore ingérées comme contrôle.",
  },
  "S7-DATAN": {
    etiquette: "Consolidation reconnue, non officielle",
    detail:
      "Scores calculés et publiés par l’association Datan à partir des données de l’Assemblée nationale, crédités et affichés à côté du taux calculé ici.",
  },
  S31: {
    etiquette: "Officielle, sans licence ouverte",
    detail:
      "Constantes recopiées à la main de documents officiels (lois, rapports de la Cour des comptes et des assemblées), chacune citée avec son adresse. Ces documents ne sont pas diffusés sous licence ouverte.",
  },
};

export function natureSource(sourceId: string): NatureSource | null {
  return NATURES[sourceId] ?? null;
}

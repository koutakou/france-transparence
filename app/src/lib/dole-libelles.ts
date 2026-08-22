/**
 * Libellés des types de dossiers législatifs DILA (codes bruts en base :
 * LOI_PUBLIEE, PROJET_LOI…) — module PUR, partagé entre /documents et
 * /documents/dossiers.
 *
 * TYPE n'est pas un état « en cours » : un PROJET_LOI d'une législature
 * close reste un projet dans le fichier.
 */

const LIBELLES_TYPE_DOLE: Record<string, string> = {
  LOI_PUBLIEE: "Loi publiée",
  ORDONNANCE_PUBLIEE: "Ordonnance publiée",
  PROJET_LOI: "Projet de loi",
  PROPOSITION_LOI: "Proposition de loi",
  PROJET_ORDONNANCE: "Projet d’ordonnance",
};

/** Code DILA → libellé lisible ; type vide (réel, quelques dossiers) → « Type non renseigné ». */
export function libelleTypeDole(type: string): string {
  if (type === "") return "Type non renseigné";
  return LIBELLES_TYPE_DOLE[type] ?? type;
}

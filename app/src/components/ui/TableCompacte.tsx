import { TableIle, type ColonneSimple } from "@/components/client/TableIle";

/**
 * Même tableau que DataTable, au même HTML, pour une page proche du budget
 * de 500 Ko : rendu serveur, un tableau pèse deux fois (son HTML, et le même
 * arbre d'éléments sérialisé dans le payload RSC — classes de chaque cellule
 * comprises). Ici seul le HTML porte le balisage ; le payload ne porte que
 * les lignes, RÉDUITES AUX CHAMPS AFFICHÉS (colonnes et clé) : une donnée
 * non affichée ne voyage pas. Réservé aux colonnes sans `rendu` (une
 * fonction ne traverse pas la frontière serveur → client).
 */
export function TableCompacte<T extends object>({
  colonnes,
  lignes,
  cleChamp,
  vide,
  hauteurMax,
  libelle,
}: {
  colonnes: ColonneSimple[];
  lignes: T[];
  /** Champ servant de clé React stable (défaut : index). */
  cleChamp?: keyof T & string;
  vide?: string;
  hauteurMax?: string;
  libelle?: string;
}) {
  const champs = new Set(colonnes.map((c) => c.cle));
  if (cleChamp) champs.add(cleChamp);
  const reduites = lignes.map((l) => {
    const r: Record<string, unknown> = {};
    for (const c of champs) r[c] = (l as Record<string, unknown>)[c];
    return r;
  });
  return (
    <TableIle
      colonnes={colonnes}
      lignes={reduites}
      cleChamp={cleChamp}
      vide={vide}
      hauteurMax={hauteurMax}
      libelle={libelle}
    />
  );
}

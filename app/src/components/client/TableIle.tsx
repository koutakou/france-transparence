"use client";

import { DataTable, type Colonne } from "@/components/ui/DataTable";

/** Colonne SÉRIALISABLE : celle de DataTable, sans fonction de rendu. */
export type ColonneSimple = Omit<Colonne<Record<string, unknown>>, "rendu">;

/**
 * DataTable rendu en ÎLE CLIENT pour un tableau sans rendu personnalisé.
 * Ne s'emploie pas directement : passer par `TableCompacte`
 * (components/ui/TableCompacte.tsx), qui réduit les lignes aux colonnes
 * affichées avant qu'elles ne traversent la frontière.
 */
export function TableIle({
  colonnes,
  lignes,
  cleChamp,
  vide,
  hauteurMax,
  libelle,
}: {
  colonnes: ColonneSimple[];
  lignes: Record<string, unknown>[];
  cleChamp?: string;
  vide?: string;
  hauteurMax?: string;
  libelle?: string;
}) {
  return (
    <DataTable
      colonnes={colonnes}
      lignes={lignes}
      cleLigne={cleChamp ? (l, i) => String(l[cleChamp] ?? i) : undefined}
      vide={vide}
      hauteurMax={hauteurMax}
      libelle={libelle}
    />
  );
}

import type { ReactNode } from "react";
import { formatDateFr, formatEuros, formatNombre, formatPct } from "@/lib/format";

/**
 * Tableau dense — specs DATAVIZ §7 :
 * - rangées 36px, padding horizontal 12px ;
 * - en-tête 11px MAJUSCULES letter-spacing 0,04em `--ink-muted` (sticky si
 *   `hauteurMax` est donné) ;
 * - séparateurs horizontaux 1px `--viz-grid`, PAS de filets verticaux ni de
 *   zébrage — le survol `--surface-hover` suit la ligne ;
 * - nombres alignés à DROITE en tabular-nums, texte à gauche ;
 * - l'UNITÉ vit dans l'en-tête de colonne (« Montant (M€) »), jamais répétée
 *   par cellule ; les montants restent en `--ink-primary` (§3.5 — le rouge
 *   n'y marque que dépassements/alertes, via un `rendu` custom).
 *
 * Types de colonne :
 * - `"texte"` (défaut, gauche) ; `"date"` (gauche, JJ/MM/AAAA) ;
 * - `"nombre"` / `"pourcent"` (droite) ;
 * - `"euros"` (droite, symbole € par cellule — pour une colonne isolée) ;
 * - `"montant"` (droite, nombre nu : l'unité est dans l'en-tête) ;
 * - `rendu` custom pour tout le reste (<DeltaPct/>, mini-barres…).
 *
 * @example
 * <DataTable
 *   colonnes={[
 *     { cle: "titulaire", entete: "Titulaire" },
 *     { cle: "montant", entete: "Montant (M€)", type: "montant", decimales: 1 },
 *     { cle: "notification", entete: "Notifié le", type: "date" },
 *   ]}
 *   lignes={lignes}
 *   cleLigne={(l) => l.id}
 * />
 */
export type ColonneType = "texte" | "nombre" | "euros" | "montant" | "pourcent" | "date";

export interface Colonne<T> {
  /** Clé d'accès dans la ligne (`ligne[cle]`) — ignorée si `rendu` est fourni. */
  cle: string;
  /** Libellé d'en-tête — y placer l'unité : « Montant (M€) ». */
  entete: string;
  type?: ColonneType;
  /** Décimales pour nombre/montant/pourcent (défaut 0 ; pourcent 1). */
  decimales?: number;
  /** Rendu custom (prioritaire sur `type`). */
  rendu?: (ligne: T, index: number) => ReactNode;
  /** Largeur CSS optionnelle (« 12rem », « 20% »). */
  largeur?: string;
}

export interface DataTableProps<T extends object> {
  colonnes: Colonne<T>[];
  lignes: T[];
  /** Clé React stable par ligne (défaut : index). */
  cleLigne?: (ligne: T, index: number) => string;
  /** Message d'état vide (défaut « Aucune donnée »). */
  vide?: string;
  /** Si donné : conteneur scrollable (`max-height`) + en-tête sticky. */
  hauteurMax?: string;
  className?: string;
}

function estNumerique(type: ColonneType | undefined): boolean {
  return type === "nombre" || type === "euros" || type === "montant" || type === "pourcent";
}

function formate<T extends object>(colonne: Colonne<T>, ligne: T, index: number): ReactNode {
  if (colonne.rendu) return colonne.rendu(ligne, index);
  const brut = (ligne as Record<string, unknown>)[colonne.cle];
  if (brut === null || brut === undefined) return "—";
  switch (colonne.type) {
    case "nombre":
    case "montant":
      return typeof brut === "number" ? formatNombre(brut, colonne.decimales ?? 0) : String(brut);
    case "euros":
      return typeof brut === "number" ? formatEuros(brut) : String(brut);
    case "pourcent":
      return typeof brut === "number" ? formatPct(brut, colonne.decimales ?? 1) : String(brut);
    case "date":
      return typeof brut === "string" ? formatDateFr(brut) : String(brut);
    default:
      return String(brut);
  }
}

export function DataTable<T extends object>({
  colonnes,
  lignes,
  cleLigne,
  vide = "Aucune donnée",
  hauteurMax,
  className,
}: DataTableProps<T>) {
  // Filet horizontal 1px `--viz-grid` (jamais de filets verticaux, §7) et
  // gabarit de cellule posés UNE FOIS sur le conteneur (variantes [&_td])
  // plutôt que répétés sur chaque cellule : sur un tableau de 100 lignes,
  // ces attributs par cellule pesaient plusieurs dizaines de Ko de HTML.
  return (
    <div
      className={`overflow-x-auto ${hauteurMax ? "overflow-y-auto" : ""} [&_td]:border-b [&_td]:border-[var(--viz-grid)] [&_td]:h-9 [&_td]:px-3 [&_th]:border-b [&_th]:border-[var(--viz-grid)] ${className ?? ""}`}
      style={hauteurMax ? { maxHeight: hauteurMax } : undefined}
    >
      <table className="w-full border-collapse text-[13px]">
        <thead>
          <tr>
            {colonnes.map((c) => (
              <th
                key={c.cle}
                scope="col"
                style={c.largeur ? { width: c.largeur } : undefined}
                className={`px-3 pb-2 pt-1 text-[11px] font-medium uppercase tracking-[0.04em] text-ink-muted ${
                  estNumerique(c.type) ? "text-right" : "text-left"
                } ${hauteurMax ? "sticky top-0 bg-card" : ""}`}
              >
                {c.entete}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {lignes.length === 0 ? (
            <tr>
              <td colSpan={colonnes.length} className="text-center text-ink-muted">
                {vide}
              </td>
            </tr>
          ) : (
            lignes.map((ligne, i) => (
              <tr
                key={cleLigne ? cleLigne(ligne, i) : i}
                className="transition-colors hover:bg-hover"
              >
                {colonnes.map((c) => (
                  <td
                    key={c.cle}
                    className={
                      estNumerique(c.type)
                        ? "text-right text-ink [font-variant-numeric:tabular-nums]"
                        : "text-left text-ink"
                    }
                  >
                    {formate(c, ligne, i)}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

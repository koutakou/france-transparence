import { formatNombre } from "@/lib/format";

/**
 * Barres horizontales (comparaison de magnitudes à noms longs — la forme
 * par défaut pour « dépenses par ministère », DATAVIZ §2).
 *
 * Specs §4 : barre ≤ 24px d'épaisseur, bout de DONNÉE arrondi 4px, carré à
 * la ligne de base ; valeur au bout de la barre. Règle §3.2 : une série de
 * barres NOMINALES = UNE couleur (`--viz-serie-1`) — jamais une rampe de
 * valeur sur des catégories. `couleur` par item ne sert qu'à la dé-emphase
 * (« Autre » en `--viz-autre`) ou à l'emphase inverse (sujet en série 1,
 * contexte en `--viz-autre`).
 *
 * @example
 * <BarList items={[
 *   { libelle: "Enseignement scolaire", valeur: 88_400_000_000 },
 *   { libelle: "Défense", valeur: 62_100_000_000 },
 *   { libelle: "Autres missions", valeur: 51_000_000_000, couleur: "var(--viz-autre)" },
 * ]} formatValeur={(v) => formatEuros(v)} />
 */
export interface BarListItem {
  libelle: string;
  valeur: number;
  /** Override ponctuel (dé-emphase « Autre ») — défaut `var(--viz-serie-1)`. */
  couleur?: string;
}

export interface BarListProps {
  items: BarListItem[];
  /** Format de la valeur affichée (défaut : nombre fr). */
  formatValeur?: (v: number) => string;
  /** Épaisseur de barre en px (défaut 16, plafond 24 — DATAVIZ §4). */
  epaisseur?: number;
  /** Largeur de la colonne libellés (défaut 40%). */
  largeurLibelle?: string;
  className?: string;
}

export function BarList({
  items,
  formatValeur = (v) => formatNombre(v),
  epaisseur = 16,
  largeurLibelle = "40%",
  className,
}: BarListProps) {
  if (items.length === 0) return null;
  const h = Math.min(Math.max(epaisseur, 6), 24);
  const max = Math.max(...items.map((i) => Math.max(i.valeur, 0)), 0) || 1;

  return (
    <ul className={`flex flex-col gap-2 ${className ?? ""}`}>
      {items.map((item, i) => {
        const part = Math.max(item.valeur, 0) / max;
        return (
          <li
            key={`${item.libelle}-${i}`}
            className="flex items-center gap-3"
            title={`${item.libelle} : ${formatValeur(item.valeur)}`}
          >
            <span
              className="shrink-0 truncate text-[13px] text-ink-secondary"
              style={{ width: largeurLibelle }}
            >
              {item.libelle}
            </span>
            <span className="flex min-w-0 flex-1 items-center gap-2">
              <span
                className="block shrink-0 transition-[filter] hover:brightness-[1.18]"
                style={{
                  width: `${(part * 100).toFixed(2)}%`,
                  height: h,
                  background: item.couleur ?? "var(--viz-serie-1)",
                  // bout de donnée arrondi 4px, carré à la base (§4)
                  borderRadius: "0 4px 4px 0",
                  minWidth: item.valeur > 0 ? 2 : 0,
                }}
              />
              <span className="shrink-0 text-[13px] text-ink [font-variant-numeric:tabular-nums]">
                {formatValeur(item.valeur)}
              </span>
            </span>
          </li>
        );
      })}
    </ul>
  );
}

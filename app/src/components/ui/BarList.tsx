import { formatNombre } from "@/lib/format";

/**
 * Barres horizontales (comparaison de magnitudes à noms longs — la forme
 * par défaut pour « dépenses par ministère », DATAVIZ §2).
 *
 * Specs §4 : barre ≤ 24px d'épaisseur, bout de DONNÉE arrondi 4px, carré à
 * la ligne de base ; valeur au bout de la barre — sa place est RÉSERVÉE
 * (largeur de la plus longue valeur formatée) : la barre se raccourcit,
 * la valeur ne se tronque jamais. Règle §3.2 : une série de
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
  const valeurs = items.map((i) => formatValeur(i.valeur));
  // Place réservée à la valeur : largeur de la plus longue valeur formatée
  // (+1ch de marge, « M€ » étant plus large que des chiffres tabulaires).
  // La barre ne dispose que du reste → jamais de valeur tronquée (§4 : une
  // étiquette qui ne tient pas ne se coupe pas), proportions préservées.
  const reserveCh = Math.max(...valeurs.map((v) => v.length)) + 1;

  return (
    <ul className={`flex flex-col gap-2 ${className ?? ""}`}>
      {items.map((item, i) => {
        const part = Math.max(item.valeur, 0) / max;
        return (
          <li
            key={`${item.libelle}-${i}`}
            className="flex items-start gap-3"
            title={`${item.libelle} : ${valeurs[i]}`}
          >
            <span
              className="shrink-0 whitespace-normal text-[13px] leading-snug text-ink-secondary"
              style={{ width: largeurLibelle }}
            >
              {item.libelle}
            </span>
            <span className="flex min-w-0 flex-1 items-center self-center gap-2 text-[13px]">
              <span
                className="block shrink-0 transition-[filter] hover:brightness-[1.18]"
                style={{
                  // part × (100% − place de la valeur − gap-2) : la valeur
                  // au bout de la barre la plus longue reste entière
                  width: `calc((100% - ${reserveCh}ch - 8px) * ${part.toFixed(4)})`,
                  height: h,
                  background: item.couleur ?? "var(--viz-serie-1)",
                  // bout de donnée arrondi 4px, carré à la base (§4)
                  borderRadius: "0 4px 4px 0",
                  minWidth: item.valeur > 0 ? 2 : 0,
                }}
              />
              <span className="shrink-0 whitespace-nowrap text-ink [font-variant-numeric:tabular-nums]">
                {valeurs[i]}
              </span>
            </span>
          </li>
        );
      })}
    </ul>
  );
}

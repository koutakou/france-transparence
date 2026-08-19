import { KpiTile, type KpiTileProps } from "./KpiTile";

/**
 * Bandeau de 3–4 stats (rangée de KPI, DATAVIZ §2) — une seule bande
 * bordée, tuiles séparées par un filet 1px (interstice `gap-px` sur fond
 * `--border-card` : le séparateur reste subtil et suit les retours à la
 * ligne en écran étroit).
 *
 * @example
 * <StatStrip stats={[
 *   { label: "Dépenses payées (juillet)", valeur: <Money valeur={4.2e9} />, montantVedette: true },
 *   { label: "Marchés notifiés (30 j)", valeur: "1 284" },
 *   { label: "Déclarations HATVP publiées", valeur: "912", delta: { valeur: 2.4, vs: "2025", upIsGood: true } },
 * ]} />
 */
export interface StatStripProps {
  stats: Omit<KpiTileProps, "nu">[];
  className?: string;
}

export function StatStrip({ stats, className }: StatStripProps) {
  if (stats.length === 0) return null;
  return (
    <div
      className={`grid gap-px overflow-hidden rounded-xl border border-card-border ${className ?? ""}`}
      style={{
        gridTemplateColumns: `repeat(auto-fit, minmax(200px, 1fr))`,
        background: "var(--border-card)",
      }}
    >
      {stats.map((s, i) => (
        <div key={`${s.label}-${i}`} className="bg-card">
          <KpiTile {...s} nu />
        </div>
      ))}
    </div>
  );
}

import type { ReactNode } from "react";

/**
 * Carte de module — le conteneur standard de chaque bloc du dashboard.
 * Specs DATAVIZ §4 : fond `--surface-card`, bordure 1px `--border-card`,
 * rayon 12px, padding 16–20px. Titre de section en petites capitales
 * espacées (ADN maquette, type « DÉPENSES EN DIRECT »).
 *
 * @example
 * <Card titre="Dépenses en direct" sousTitre="Paiements de l'État, mois courant"
 *       droite={<FreshnessBadge dateDonnees="2026-07-31" source="Chorus" frequence="mensuelle" url="https://…" />}>
 *   …contenu…
 * </Card>
 */
export interface CardProps {
  /** Titre de section — rendu en petites capitales espacées. */
  titre?: string;
  /** Sous-titre 12px `--ink-secondary` (optionnel). */
  sousTitre?: string;
  /** Slot droite de l'en-tête : badge de fraîcheur, toggle « Tableau »… */
  droite?: ReactNode;
  children: ReactNode;
  className?: string;
}

export function Card({ titre, sousTitre, droite, children, className }: CardProps) {
  return (
    <section
      className={`rounded-xl border border-card-border bg-card p-4 sm:p-5 ${className ?? ""}`}
    >
      {(titre || droite) && (
        <header className="mb-4 flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
          <div className="min-w-0">
            {titre && (
              <h2 className="text-[13px] font-semibold uppercase tracking-[0.14em] text-ink">
                {titre}
              </h2>
            )}
            {sousTitre && (
              <p className="mt-1 text-xs text-ink-secondary">{sousTitre}</p>
            )}
          </div>
          {/* min-w-0 + max-w-full (et non shrink-0) : sur écran étroit le badge
              se replie/tronque au lieu de faire déborder le document. */}
          {droite && <div className="min-w-0 max-w-full">{droite}</div>}
        </header>
      )}
      {children}
    </section>
  );
}

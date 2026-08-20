import type { ReactNode } from "react";

/**
 * Alerte — statuts RÉSERVÉS de DATAVIZ §3.4 : TOUJOURS icône + libellé,
 * jamais la couleur seule. L'icône porte le jeton statut (marque ≥ 3:1) ;
 * le LIBELLÉ reste en encre (`--status-critical` à 3,51:1 est sous le
 * minimum 4,5:1 du texte courant, §9 — un statut ne colore pas du texte).
 *
 * `regle` + `baseLegale` vivent dans un dépliable natif (<details>, aucun
 * JS client). La règle de calcul et sa base légale sont aussi documentées
 * sur /donnees (ARCHITECTURE §8).
 *
 * @example
 * <AlertItem gravite="serieux" titre="Marché attribué sans publicité préalable"
 *   detail="Marché de 92 k€ notifié le 12/07/2026 par la commune de X."
 *   regle="Seuil de publicité 40 k€ HT dépassé sans avis préalable repéré au BOAMP."
 *   baseLegale="Art. R2131-12 du code de la commande publique."
 *   source={{ libelle: "DECP consolidées", url: "https://…" }} />
 */
export type Gravite = "bon" | "attention" | "serieux" | "critique";

export interface AlertItemProps {
  gravite: Gravite;
  titre: string;
  /** Détail factuel (une à deux phrases). */
  detail?: string;
  /** Règle de calcul de l'alerte (dépliable). */
  regle?: string;
  /** Base légale de la règle (dépliable, sous la règle). */
  baseLegale?: string;
  /** Source des données ayant déclenché l'alerte. */
  source?: { libelle: string; url?: string };
  /** Libellé de gravité affiché (défauts : Conforme / À surveiller / Sérieux / Critique). */
  graviteLibelle?: string;
  className?: string;
}

const GRAVITES: Record<Gravite, { jeton: string; libelle: string; icone: ReactNode }> = {
  bon: {
    jeton: "var(--status-good)",
    libelle: "Conforme",
    icone: (
      <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
        <circle cx="7" cy="7" r="6" fill="none" stroke="currentColor" strokeWidth="1.6" />
        <path d="M4.2 7.2l2 2 3.6-4" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
  },
  attention: {
    jeton: "var(--status-warning)",
    libelle: "À surveiller",
    icone: (
      <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
        <path d="M7 1.5L13 12H1z" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
        <path d="M7 5.4v3" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        <circle cx="7" cy="10.2" r="0.9" fill="currentColor" />
      </svg>
    ),
  },
  serieux: {
    jeton: "var(--status-serious)",
    libelle: "Sérieux",
    icone: (
      <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
        <circle cx="7" cy="7" r="6" fill="none" stroke="currentColor" strokeWidth="1.6" />
        <path d="M7 3.8v4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        <circle cx="7" cy="10" r="0.9" fill="currentColor" />
      </svg>
    ),
  },
  critique: {
    jeton: "var(--status-critical)",
    libelle: "Critique",
    icone: (
      <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
        <path d="M4.5 1h5L13 4.5v5L9.5 13h-5L1 9.5v-5z" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
        <path d="M7 4v4" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        <circle cx="7" cy="10" r="0.9" fill="currentColor" />
      </svg>
    ),
  },
};

export function AlertItem({
  gravite,
  titre,
  detail,
  regle,
  baseLegale,
  source,
  graviteLibelle,
  className,
}: AlertItemProps) {
  const g = GRAVITES[gravite];
  return (
    <article
      className={`rounded-lg border border-card-border bg-card p-3.5 ${className ?? ""}`}
      style={{ borderLeft: `2px solid ${g.jeton}` }}
    >
      <div className="flex items-start gap-2.5">
        <span className="mt-0.5 shrink-0" style={{ color: g.jeton }}>
          {g.icone}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-baseline gap-x-2">
            <span className="text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-secondary">
              {graviteLibelle ?? g.libelle}
            </span>
            {source && (
              <span className="text-[11px] text-ink-muted">
                ·{" "}
                {source.url ? (
                  <a
                    href={source.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="underline decoration-dotted underline-offset-2 hover:text-ink-secondary"
                  >
                    {source.libelle}
                  </a>
                ) : (
                  source.libelle
                )}
              </span>
            )}
          </div>
          <h3 className="mt-0.5 text-sm font-semibold text-ink">{titre}</h3>
          {detail && <p className="mt-1 text-[13px] leading-snug text-ink-secondary">{detail}</p>}
          {(regle || baseLegale) && (
            <details className="mt-2 group">
              <summary className="cursor-pointer list-none text-xs text-ink-muted transition-colors hover:text-ink-secondary">
                <span aria-hidden="true" className="mr-1 inline-block transition-transform group-open:rotate-90">
                  ›
                </span>
                Règle et base légale
              </summary>
              <div className="mt-1.5 border-l pl-3 text-xs leading-relaxed" style={{ borderColor: "var(--viz-grid)" }}>
                {regle && <p className="text-ink-secondary">{regle}</p>}
                {baseLegale && <p className="mt-1 text-ink-muted">{baseLegale}</p>}
              </div>
            </details>
          )}
        </div>
      </div>
    </article>
  );
}

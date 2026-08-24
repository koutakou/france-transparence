import type { ReactNode } from "react";

/**
 * Toggle « Vue tableau » jumelle d'un graphique (DATAVIZ §7 / §9).
 *
 * `<details>` natif : zéro JS, le clavier passe par le résumé. Un graphique
 * n'a pas un tab stop par point — le tableau (ou ce toggle) est le chemin
 * clavier. `resume` personnalise le libellé (« Vue tableau — 36 mois »).
 */
export function VueTableau({
  children,
  resume = "Vue tableau",
}: {
  children: ReactNode;
  resume?: string;
}) {
  return (
    <details className="group mt-3">
      <summary className="w-fit cursor-pointer list-none select-none text-xs text-ink-muted transition-colors hover:text-ink-secondary">
        <span
          aria-hidden="true"
          className="mr-1 inline-block transition-transform group-open:rotate-90 motion-reduce:transition-none"
        >
          ›
        </span>
        {resume}
      </summary>
      <div className="mt-2">{children}</div>
    </details>
  );
}

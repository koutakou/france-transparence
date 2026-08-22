import type { ReactNode } from "react";
import Link from "next/link";

/**
 * Notice pédagogique d'une page de données — trois questions toujours
 * les mêmes, posées au visiteur avant les tableaux : comment lire, d'où
 * viennent ces données, ce qu'elles ne disent pas.
 *
 * Server Component, zéro JS client. Les titres sont des `h2` : la
 * pédagogie entre dans le plan de la page, elle n'est pas un encadré
 * décoratif sous le contenu.
 *
 * `ancre` sert deux fois : `id` de la notice (lien interne) et fragment
 * de `/comprendre/#…` (développement sur la page de méthode).
 */
export function NoticeLecture({
  ancre,
  commentLire,
  provenance,
  limites,
}: {
  ancre: string;
  commentLire: ReactNode;
  provenance: ReactNode;
  limites: ReactNode;
}) {
  return (
    <aside
      id={ancre}
      className="max-w-3xl scroll-mt-20 rounded-xl border border-card-border bg-raised p-4"
      aria-label="Comment lire ces données"
    >
      <div className="flex flex-col gap-3 text-xs leading-relaxed text-ink-secondary">
        <section>
          <h2 className="mb-1 text-[11px] font-medium uppercase tracking-[0.08em] text-ink-muted">
            Comment lire
          </h2>
          <div>{commentLire}</div>
        </section>
        <section>
          <h2 className="mb-1 text-[11px] font-medium uppercase tracking-[0.08em] text-ink-muted">
            D’où viennent ces données
          </h2>
          <div>{provenance}</div>
        </section>
        <section>
          <h2 className="mb-1 text-[11px] font-medium uppercase tracking-[0.08em] text-ink-muted">
            Ce que ces données ne disent pas
          </h2>
          <div>{limites}</div>
        </section>
        <p className="text-[11px] text-ink-muted">
          Glossaire, fonctionnement et méthode :{" "}
          <Link
            href={`/comprendre/#${ancre}`}
            className="underline decoration-dotted underline-offset-2 hover:text-ink-secondary"
          >
            comprendre ces données
          </Link>
          .
        </p>
      </div>
    </aside>
  );
}

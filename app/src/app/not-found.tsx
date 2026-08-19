import type { Metadata } from "next";
import Link from "next/link";

/**
 * 404 du site — remplace le défaut Next (anglais) constaté dans
 * docs/deploiement/audit-app.md §3. Rendue dans le layout racine
 * (header + footer conservés) pour toute URL sans page.
 */

export const metadata: Metadata = {
  title: "Page introuvable",
};

export default function NotFound() {
  return (
    <section className="mx-auto flex w-full max-w-xl flex-col items-center gap-5 py-16 text-center">
      <p
        aria-hidden="true"
        className="text-6xl font-semibold tracking-tight text-ink-muted"
      >
        404
      </p>
      <div className="flex flex-col gap-2">
        <h1 className="text-lg font-semibold text-ink">Page introuvable</h1>
        <p className="text-sm leading-relaxed text-ink-secondary">
          Cette adresse ne correspond à aucune page du site — elle a pu être
          déplacée, ou la fiche demandée n&apos;existe pas (ou plus) dans les
          données publiées.
        </p>
      </div>
      <nav className="flex flex-wrap items-center justify-center gap-3 text-sm">
        <Link
          href="/"
          className="rounded-lg border border-card-border bg-card px-4 py-2 text-ink transition-colors hover:bg-hover"
        >
          Retour à l&apos;accueil
        </Link>
        <Link
          href="/donnees"
          className="rounded-lg border border-card-border px-4 py-2 text-ink-secondary transition-colors hover:bg-hover hover:text-ink"
        >
          Données &amp; sources
        </Link>
      </nav>
    </section>
  );
}

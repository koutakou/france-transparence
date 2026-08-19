import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "France Transparence",
    template: "%s · France Transparence",
  },
  description:
    "Dashboard de transparence de la vie politique française — données publiques réelles, fraîcheur mesurée et affichée.",
};

const NAV = [
  { href: "/depenses", label: "Dépenses de l'État" },
  { href: "/marches", label: "Commande publique" },
  { href: "/elus", label: "Élus & Institutions" },
  { href: "/lobbying", label: "Lobbying" },
  { href: "/financement", label: "Financement politique" },
  { href: "/frais", label: "Frais & train de vie" },
  { href: "/collectivites", label: "Finances locales" },
  { href: "/documents", label: "Documents / JO" },
  { href: "/donnees", label: "Données" },
] as const;

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="fr" className="h-full antialiased">
      <body className="min-h-full flex flex-col">
        <header className="border-b border-card-border bg-card">
          <div className="mx-auto flex max-w-6xl flex-wrap items-baseline gap-x-8 gap-y-2 px-6 py-4">
            <Link
              href="/"
              className="text-sm font-semibold tracking-[0.18em] text-ink"
            >
              FRANCE&nbsp;TRANSPARENCE
            </Link>
            <nav aria-label="Navigation principale">
              <ul className="flex flex-wrap gap-x-5 gap-y-1 text-[13px] text-ink-secondary">
                {NAV.map((item) => (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      className="transition-colors hover:text-ink"
                    >
                      {item.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </nav>
          </div>
        </header>
        <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-10">
          {children}
        </main>
        <footer className="border-t border-card-border">
          <div className="mx-auto max-w-6xl px-6 py-4 text-xs text-ink-muted">
            Données publiques réelles uniquement — fraîcheur mesurée et
            affichée par source.
          </div>
        </footer>
      </body>
    </html>
  );
}

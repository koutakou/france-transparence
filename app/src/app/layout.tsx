import type { Metadata } from "next";
import Link from "next/link";
import { LogoBouclier } from "@/components/LogoBouclier";
import { MainNav } from "@/components/MainNav";
import { SearchBox } from "@/components/ui/SearchBox";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "France Transparence",
    template: "%s · France Transparence",
  },
  description:
    "Dashboard de transparence de la vie politique française — données publiques réelles, fraîcheur mesurée et affichée.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="fr" className="h-full antialiased">
      <body className="min-h-full flex flex-col">
        <header className="border-b border-card-border bg-card">
          {/* rangée identité + recherche */}
          <div className="mx-auto flex w-full max-w-7xl flex-wrap items-center gap-x-6 gap-y-3 px-5 pb-2 pt-3">
            <Link href="/" className="flex items-center gap-3">
              <LogoBouclier taille={30} />
              <span className="flex flex-col">
                <span className="text-[15px] font-semibold leading-tight tracking-[0.18em] text-ink">
                  FRANCE&nbsp;TRANSPARENCE
                </span>
                {/* fin liseré tricolore sous le titre */}
                <span
                  aria-hidden="true"
                  className="mt-1 block h-[2px] w-full rounded-full opacity-80"
                  style={{
                    background:
                      "linear-gradient(90deg, var(--tricolore-bleu) 0 33.4%, var(--tricolore-blanc) 33.4% 66.7%, var(--tricolore-rouge) 66.7% 100%)",
                  }}
                />
                <span className="mt-1 text-[10px] uppercase tracking-[0.22em] text-ink-muted">
                  La transparence au service des citoyens
                </span>
              </span>
            </Link>
            <div className="ml-auto w-full max-w-md flex-1 basis-64">
              <SearchBox />
            </div>
          </div>
          {/* rangée navigation */}
          <div className="mx-auto w-full max-w-7xl px-5">
            <MainNav />
          </div>
        </header>
        <main className="mx-auto w-full max-w-7xl flex-1 px-5 py-6">{children}</main>
        <footer className="border-t border-card-border">
          <div className="mx-auto w-full max-w-7xl px-5 py-4 text-xs leading-relaxed text-ink-muted">
            Données publiques sous Licence Ouverte / ODbL — sources et fraîcheur
            sur chaque module — page{" "}
            <Link
              href="/donnees"
              className="underline decoration-dotted underline-offset-2 hover:text-ink-secondary"
            >
              Données&nbsp;&amp;&nbsp;API
            </Link>
            .
          </div>
        </footer>
      </body>
    </html>
  );
}

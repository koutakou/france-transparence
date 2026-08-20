import type { Metadata } from "next";
import Link from "next/link";
import { LogoBouclier } from "@/components/LogoBouclier";
import { MainNav } from "@/components/MainNav";
import { SearchBox } from "@/components/ui/SearchBox";
import { REPO_URL, SITE_URL } from "@/lib/site";
import "./globals.css";

const TITRE_DEFAUT =
  "France Transparence — l'argent public et la vie politique, en données ouvertes";
const DESCRIPTION_DEFAUT =
  "Dépenses de l'État, marchés publics, élus, lobbying, financement de la vie politique : données publiques officielles, fraîcheur mesurée et affichée, sources et limites documentées.";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: TITRE_DEFAUT,
    template: "%s — France Transparence",
  },
  description: DESCRIPTION_DEFAUT,
  openGraph: {
    type: "website",
    siteName: "France Transparence",
    locale: "fr_FR",
    // PAS de `title` ni de `description` ici : posés au niveau du layout, ils
    // se figeraient sur TOUTES les pages (chaque fiche d'élu partagée sur un
    // réseau social afficherait la carte de l'accueil). Sans eux, Next
    // retombe sur le title et la description RÉSOLUS de chaque page — le
    // gabarit « %s — France Transparence » compris.
    // URL absolue en dur : avec metadataBase, un chemin « /og.png » perdrait
    // le sous-chemin /france-transparence (basePath GitHub Pages).
    images: [
      {
        url: `${SITE_URL}/og.png`,
        width: 1200,
        height: 630,
        alt: "France Transparence — données publiques officielles",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    images: [`${SITE_URL}/og.png`],
  },
};

/**
 * CSP du site statique, portée par <meta http-equiv> : GitHub Pages ne
 * permet aucun header custom (docs/deploiement/DECISION.md).
 * Limites assumées et documentées :
 * - `script-src 'unsafe-inline'` : l'hydratation Next en export statique
 *   injecte des scripts inline (payload RSC) sans nonce possible sur un
 *   hébergement statique — sans cette valeur, le site ne s'hydrate pas ;
 * - `style-src 'unsafe-inline'` : attributs style= des composants dataviz ;
 * - `frame-ancestors` est IGNORÉ dans une CSP en <meta> (spec CSP3) : ne pas
 *   l'ajouter ici — risque clickjacking résiduel accepté dans DECISION.md.
 * La meta est émise en production seulement : `next dev` (HMR, eval,
 * websockets) est incompatible avec cette politique.
 */
const CSP =
  "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'self'; form-action 'none'";

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="fr" className="h-full antialiased">
      <body className="min-h-full flex flex-col">
        {/* React 19 hisse les <meta> rendues dans l'arbre vers le <head>. */}
        {process.env.NODE_ENV === "production" && (
          <meta httpEquiv="Content-Security-Policy" content={CSP} />
        )}
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
          <div className="mx-auto flex w-full max-w-7xl flex-col gap-1.5 px-5 py-4 text-xs leading-relaxed text-ink-muted">
            {/* Licence exacte : les sources ingérées sont TOUTES en Licence
                Ouverte (aucune ODbL en base — exigences-publiques.md §1.3). */}
            <p>
              Données publiques sous{" "}
              <a
                href="https://www.etalab.gouv.fr/licence-ouverte-open-licence/"
                target="_blank"
                rel="noopener noreferrer"
                className="underline decoration-dotted underline-offset-2 hover:text-ink-secondary"
              >
                Licence&nbsp;Ouverte&nbsp;2.0
              </a>{" "}
              — sources et fraîcheur sur chaque module — page{" "}
              <Link
                href="/donnees"
                className="underline decoration-dotted underline-offset-2 hover:text-ink-secondary"
              >
                Données
              </Link>
              .
            </p>
            <p className="flex flex-wrap items-center gap-x-2 gap-y-1">
              <Link
                href="/mentions-legales"
                className="underline decoration-dotted underline-offset-2 hover:text-ink-secondary"
              >
                Mentions légales
              </Link>
              <span aria-hidden="true">·</span>
              <Link
                href="/donnees-personnelles"
                className="underline decoration-dotted underline-offset-2 hover:text-ink-secondary"
              >
                Données personnelles
              </Link>
              <span aria-hidden="true">·</span>
              <a
                href={REPO_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="underline decoration-dotted underline-offset-2 hover:text-ink-secondary"
              >
                Code source
              </a>
            </p>
          </div>
        </footer>
      </body>
    </html>
  );
}

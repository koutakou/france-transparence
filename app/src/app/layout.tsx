import type { Metadata } from "next";
import Link from "next/link";
import { LogoBouclier } from "@/components/LogoBouclier";
import { MainNav } from "@/components/MainNav";
import { SearchBox } from "@/components/ui/SearchBox";
import { IMAGE_PARTAGE, openGraphPage } from "@/lib/seo";
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
  // Open Graph PAR DÉFAUT — il ne sert qu'aux pages qui n'en déclarent pas
  // (la 404). Toutes les autres passent par `metadonneesPage()`, qui rend le
  // MÊME bloc en y ajoutant leur `og:url` : Next remplace `openGraph` en bloc
  // au lieu de le fusionner champ à champ, il n'y a donc pas d'héritage à
  // espérer ici — d'où la fabrique partagée dans src/lib/seo.ts.
  // Sans `url` : la 404 est servie sous n'importe quelle adresse, elle n'a
  // aucune URL propre à revendiquer.
  openGraph: openGraphPage(),
  // La carte X, elle, est bien HÉRITÉE par toutes les pages : aucune n'en
  // déclare, la clé `twitter` du layout n'est donc jamais remplacée.
  // L'image est donnée en OBJET `{ url, alt }` et non en chaîne nue : une
  // chaîne ne produit que `twitter:image`, et X ne retombe PAS
  // systématiquement sur `og:image:alt` — la carte perdait son texte
  // alternatif, c'est-à-dire toute description pour qui ne voit pas l'image.
  // L'URL et l'alternative viennent de la constante partagée de seo.ts, pour
  // qu'une image de partage changée un jour le soit à un seul endroit.
  twitter: {
    card: "summary_large_image",
    images: [{ url: IMAGE_PARTAGE.url, alt: IMAGE_PARTAGE.alt }],
  },
};

/**
 * CSP du site statique, portée par <meta http-equiv>.
 *
 * La raison d'origine — GitHub Pages n'autorise aucun en-tête personnalisé — a
 * disparu le 20/08/2026 : le site est servi par nginx sur un serveur dédié, qui
 * peut parfaitement émettre l'en-tête `Content-Security-Policy`. Le <meta> est
 * CONSERVÉ malgré tout, et volontairement : il voyage avec l'export. Un miroir,
 * une préproduction ou un fork republiant `app/out/` derrière n'importe quel
 * serveur gardent ainsi la même politique, sans avoir à recopier une
 * configuration. L'en-tête HTTP, lui, reste la voie à privilégier si l'on veut
 * un jour des directives que le <meta> ne sait pas porter (`frame-ancestors`,
 * `report-uri`) — elles seraient alors à poser dans la configuration nginx, pas
 * ici. Voir docs/deploiement/DECISION.md.
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
            {/* Licence : la PLUPART des sources sont en Licence Ouverte, pas
                toutes. Trois relèvent d'un autre régime — publications
                officielles hors open data, texte publié au JORF, décision
                2011/833/UE. Le commentaire précédent affirmait « TOUTES en
                Licence Ouverte » en le déduisant de « aucune ODbL en base » :
                ce sont deux propriétés distinctes, et l'absence de l'une ne
                démontre pas l'autre. meta_sources.licence fait foi ; ne pas
                réintroduire ici un compte qui dérivera à la source suivante. */}
            <p>
              Données publiques, pour la plupart sous{" "}
              <a
                href="https://www.etalab.gouv.fr/licence-ouverte-open-licence/"
                target="_blank"
                rel="noopener noreferrer"
                className="underline decoration-dotted underline-offset-2 hover:text-ink-secondary"
              >
                Licence&nbsp;Ouverte
              </a>{" "}
              — licence exacte et fraîcheur, source par source, page{" "}
              <Link
                href="/donnees"
                className="underline decoration-dotted underline-offset-2 hover:text-ink-secondary"
              >
                Données
              </Link>
              .
            </p>
            {/* `prefetch={false}` sur ces deux liens : ils sont dans le pied de
                page de TOUTES les pages, donc préchargés au viewport dès qu'on
                arrive en bas — ~11 Ko compressés par vue de page pour deux
                pages que quasiment personne n'ouvre. Ici pas de réarmement au
                survol possible (layout = Server Component, aucun handler) : en
                Next 16.3.1, `false` coupe aussi le survol, la navigation vers
                ces deux pages sera donc froide. C'est le bon arbitrage vu leur
                probabilité de clic ; le lien vers /donnees juste au-dessus est
                laissé en préchargement par défaut, la nav le couvre déjà. */}
            <p className="flex flex-wrap items-center gap-x-2 gap-y-1">
              <Link
                href="/mentions-legales"
                prefetch={false}
                className="underline decoration-dotted underline-offset-2 hover:text-ink-secondary"
              >
                Mentions légales
              </Link>
              <span aria-hidden="true">·</span>
              <Link
                href="/donnees-personnelles"
                prefetch={false}
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

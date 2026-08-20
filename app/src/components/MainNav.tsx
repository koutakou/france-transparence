"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useCallback, useRef, type ReactNode } from "react";

/**
 * Navigation principale — horizontale, icônes discrètes, état actif
 * souligné bleu (`--viz-serie-1`). Client : `usePathname` pour l'actif.
 */
interface ItemNav {
  href: string;
  label: string;
  icone: ReactNode;
}

const TRAIT = {
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.6,
  strokeLinecap: "round",
  strokeLinejoin: "round",
} as const;

function Icone({ children }: { children: ReactNode }) {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" aria-hidden="true" {...TRAIT} className="shrink-0 opacity-70">
      {children}
    </svg>
  );
}

/**
 * Libellés volontairement COURTS (« Financement », « Frais », « Données ») :
 * les 10 onglets doivent tenir dans le conteneur max-w-7xl dès 1440px sans
 * couper le dernier. Les intitulés complets restent portés par les pages.
 */
const ITEMS: ItemNav[] = [
  {
    href: "/",
    label: "Accueil",
    icone: (
      <Icone>
        <path d="M3.5 11.5 12 4l8.5 7.5" />
        <path d="M5.5 10v10h13V10" />
      </Icone>
    ),
  },
  {
    href: "/depenses",
    label: "Dépenses",
    icone: (
      <Icone>
        <path d="M17.5 6.2A7 7 0 1 0 17.5 17.8" />
        <path d="M4.5 10.2h9M4.5 13.8h8" />
      </Icone>
    ),
  },
  {
    href: "/marches",
    label: "Marchés publics",
    icone: (
      <Icone>
        <rect x="3.5" y="8" width="17" height="12" rx="2" />
        <path d="M9 8V6.5A1.5 1.5 0 0 1 10.5 5h3A1.5 1.5 0 0 1 15 6.5V8M3.5 13h17" />
      </Icone>
    ),
  },
  {
    href: "/elus",
    label: "Élus & Institutions",
    icone: (
      <Icone>
        <circle cx="9" cy="8.5" r="3" />
        <path d="M3.5 19.5c0-3 2.5-5 5.5-5s5.5 2 5.5 5" />
        <circle cx="17" cy="9.5" r="2.4" />
        <path d="M16.5 14.6c2.4.3 4 2 4 4.4" />
      </Icone>
    ),
  },
  {
    href: "/lobbying",
    label: "Lobbying",
    icone: (
      <Icone>
        <circle cx="6" cy="6" r="2.4" />
        <circle cx="18" cy="8" r="2.4" />
        <circle cx="12" cy="18" r="2.4" />
        <path d="M8.2 7 15.7 8.6M7 8.2l3.8 7.6M16.8 10.2l-3.6 5.8" />
      </Icone>
    ),
  },
  {
    href: "/financement",
    label: "Financement",
    icone: (
      <Icone>
        <path d="M3.5 9.5 12 4l8.5 5.5" />
        <path d="M5.5 10v7M9.8 10v7M14.2 10v7M18.5 10v7M4 19.5h16" />
      </Icone>
    ),
  },
  {
    href: "/frais",
    label: "Frais",
    icone: (
      <Icone>
        <path d="M6 3.5h12V19l-2-1.5-2 1.5-2-1.5-2 1.5-2-1.5-2 1.5Z" />
        <path d="M9 8h6M9 11.5h6" />
      </Icone>
    ),
  },
  {
    href: "/collectivites",
    label: "Finances locales",
    icone: (
      <Icone>
        <path d="M12 21s-6.5-5.5-6.5-10.5a6.5 6.5 0 0 1 13 0C18.5 15.5 12 21 12 21Z" />
        <circle cx="12" cy="10.5" r="2.2" />
      </Icone>
    ),
  },
  {
    href: "/documents",
    label: "Documents",
    icone: (
      <Icone>
        <path d="M6 3.5h8l4 4V20.5H6Z" />
        <path d="M14 3.5V8h4M9 12h6M9 15.5h6" />
      </Icone>
    ),
  },
  {
    href: "/donnees",
    label: "Données",
    icone: (
      <Icone>
        <ellipse cx="12" cy="6" rx="7" ry="2.8" />
        <path d="M5 6v12c0 1.5 3.1 2.8 7 2.8s7-1.3 7-2.8V6" />
        <path d="M5 12c0 1.5 3.1 2.8 7 2.8s7-1.3 7-2.8" />
      </Icone>
    ),
  },
];

/**
 * POURQUOI `prefetch={false}` + réarmement manuel au survol.
 *
 * Cette nav est rendue par le layout RACINE : ses 10 onglets sont donc dans
 * le viewport des 1 067 pages du site, dès le premier rendu. En préchargement
 * par défaut (viewport), CHAQUE vue de page tire les 10 payloads RSC des
 * onglets — ~152 Ko compressés (1,05 Mo bruts) que personne n'a demandés, soit
 * six fois le poids du HTML réellement lu. Sur le trafic réel mesuré, le
 * préchargement représente 26,6 % des octets servis, et le rapport
 * octets préchargés / octets lus va de 8,3× à 46,9× par visiteur.
 *
 * PIÈGE DE VERSION (Next 16.3.1) : contrairement à Next 13/14, `prefetch={false}`
 * désactive le préchargement au viewport ET au survol
 * (`node_modules/next/dist/client/app-dir/link.d.ts` : « `false`: Disable
 * prefetching on both viewport and hover »). Le laisser nu rendrait chaque
 * navigation froide. On réarme donc le survol à la main via
 * `useRouter().prefetch()` sur `onMouseEnter`, `onFocus` (clavier) et
 * `onTouchStart` (le tactile n'a pas de survol) : l'intention de clic devient
 * la condition du téléchargement, au lieu de la simple présence à l'écran.
 */
export function MainNav() {
  const pathname = usePathname();
  const router = useRouter();
  // Un survol émet l'événement plusieurs fois (entrée/sortie) : on ne demande
  // le préchargement qu'une fois par route et par session de page.
  const dejaDemandees = useRef<Set<string>>(new Set());
  const precharger = useCallback(
    (href: string) => {
      if (dejaDemandees.current.has(href)) return;
      dejaDemandees.current.add(href);
      router.prefetch(href);
    },
    [router],
  );
  return (
    <nav aria-label="Navigation principale" className="overflow-x-auto">
      <ul className="flex whitespace-nowrap text-[12.5px]">
        {ITEMS.map((item) => {
          const actif = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
          return (
            <li key={item.href}>
              <Link
                href={item.href}
                aria-current={actif ? "page" : undefined}
                prefetch={false}
                onMouseEnter={() => precharger(item.href)}
                onFocus={() => precharger(item.href)}
                onTouchStart={() => precharger(item.href)}
                className={`flex items-center gap-1.5 border-b-2 px-3 py-2.5 transition-colors ${
                  actif
                    ? "border-accent font-medium text-ink"
                    : "border-transparent text-ink-secondary hover:text-ink"
                }`}
              >
                {item.icone}
                {item.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

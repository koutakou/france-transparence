"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";

/**
 * Navigation principale.
 * POURQUOI deux arbres : les 11 libellés complets ne tiennent pas dans le
 * chrome sous 1280px ; un défilement horizontal cachait Données / Documents
 * sans affordance. Mobile = `<details>` natif (s'ouvre sans JS). Bureau = barre
 * `flex-wrap`, tous les onglets visibles, sans scroll horizontal.
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
 * Libellés complets (« Finances locales », « Élus & Institutions ») : choix
 * éditoriaux. Le fit se joue par le menu mobile et le wrap desktop, pas en
 * raccourcissant.
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
    href: "/recettes",
    label: "Recettes",
    icone: (
      <Icone>
        <path d="M12 3.5v9M8.5 9 12 12.5 15.5 9" />
        <path d="M4.5 14.5v5h15v-5" />
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

function estActif(href: string, pathname: string): boolean {
  return href === "/" ? pathname === "/" : pathname.startsWith(href);
}

/**
 * POURQUOI `prefetch={false}` + réarmement manuel au survol.
 *
 * Cette nav est rendue par le layout RACINE : ses 11 onglets sont donc dans
 * le viewport des 1 067 pages du site, dès le premier rendu. En préchargement
 * par défaut (viewport), CHAQUE vue de page tire les 11 payloads RSC des
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
function LienNav({
  item,
  actif,
  precharger,
  variante,
  onNaviguer,
}: {
  item: ItemNav;
  actif: boolean;
  precharger: (href: string) => void;
  variante: "mobile" | "bureau";
  onNaviguer?: () => void;
}) {
  const classes =
    variante === "mobile"
      ? `flex min-h-11 w-full items-center gap-2 border-l-2 px-3 py-2 text-[13px] ${
          actif
            ? "border-accent bg-hover font-medium text-ink"
            : "border-transparent text-ink-secondary hover:bg-hover hover:text-ink"
        }`
      : `flex items-center gap-1.5 whitespace-nowrap border-b-2 px-2.5 py-2.5 text-[12.5px] transition-colors ${
          actif
            ? "border-accent font-medium text-ink"
            : "border-transparent text-ink-secondary hover:text-ink"
        }`;
  return (
    <Link
      href={item.href}
      aria-current={actif ? "page" : undefined}
      prefetch={false}
      onMouseEnter={() => precharger(item.href)}
      onFocus={() => precharger(item.href)}
      onTouchStart={() => precharger(item.href)}
      onClick={onNaviguer}
      className={classes}
    >
      {item.icone}
      {item.label}
    </Link>
  );
}

export function MainNav() {
  const pathname = usePathname();
  const router = useRouter();
  const detailsRef = useRef<HTMLDetailsElement>(null);
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

  const itemCourant = ITEMS.find((item) => estActif(item.href, pathname));
  // Hauteur de layout du header (offsetHeight), pas le bottom viewport :
  // getBoundingClientRect().bottom reculait au scroll et le panneau
  // `fixed` recouvrait la search. Repli CSS `--chrome-bottom` si pas encore
  // mesuré (no-JS / premier paint).
  const [chromeBas, setChromeBas] = useState<number | null>(null);
  const fermerMenu = useCallback(() => {
    if (detailsRef.current) detailsRef.current.open = false;
  }, []);

  useEffect(() => {
    const el = detailsRef.current;
    if (el) el.open = false;
  }, [pathname]);

  useEffect(() => {
    const el = detailsRef.current;
    if (!el) return;

    const surTouche = (e: KeyboardEvent) => {
      if (e.key !== "Escape" || !el.open) return;
      el.open = false;
      el.querySelector("summary")?.focus();
    };
    const surPointer = (e: PointerEvent) => {
      if (!el.open) return;
      if (el.contains(e.target as Node)) return;
      el.open = false;
    };

    document.addEventListener("keydown", surTouche);
    document.addEventListener("pointerdown", surPointer);
    return () => {
      document.removeEventListener("keydown", surTouche);
      document.removeEventListener("pointerdown", surPointer);
    };
  }, []);

  useEffect(() => {
    const header = detailsRef.current?.closest("header");
    if (!header) return;
    const maj = () => setChromeBas(header.offsetHeight);
    maj();
    const ro = new ResizeObserver(maj);
    ro.observe(header);
    window.addEventListener("resize", maj);
    return () => {
      ro.disconnect();
      window.removeEventListener("resize", maj);
    };
  }, []);

  return (
    <nav aria-label="Navigation principale" className="nav-principale relative flex justify-end xl:static xl:block">
      {/*
        Panneau `fixed` : le nav vit dans une cellule étroite (header-nav) ;
        `absolute left-0 right-0` ne couvrirait que ce coin. Repli CSS
        `--chrome-bottom` (8rem) pour le no-JS ; après hydratation,
        `chromeBas` = header.offsetHeight (le header est sticky : ce n'est
        PAS getBoundingClientRect().bottom, qui recule au scroll).
        max-h + overscroll-contain : 11 × 44px sur un écran court.
      */}
      <details ref={detailsRef} className="shrink-0 xl:hidden">
        <summary className="inline-flex min-h-11 min-w-11 shrink-0 cursor-pointer list-none items-center gap-2 whitespace-nowrap rounded-lg border border-card-border bg-page px-3 text-[13px] text-ink select-none [&::-webkit-details-marker]:hidden">
          <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true" {...TRAIT} className="shrink-0">
            <path d="M4 7h16M4 12h16M4 17h16" />
          </svg>
          Menu
          {itemCourant ? <span className="sr-only">{` · ${itemCourant.label}`}</span> : null}
        </summary>
        <ul
          className="fixed top-[var(--chrome-bottom,8rem)] right-0 left-0 z-40 mx-auto flex max-h-[calc(100dvh-var(--chrome-bottom,8rem))] max-w-7xl flex-col overflow-y-auto overscroll-contain border-b border-card-border bg-card px-5 pt-2 pb-3"
          style={chromeBas != null ? { top: chromeBas, maxHeight: `calc(100dvh - ${chromeBas}px)` } : undefined}
        >
          {ITEMS.map((item) => (
            <li key={item.href}>
              <LienNav
                item={item}
                actif={estActif(item.href, pathname)}
                precharger={precharger}
                variante="mobile"
                onNaviguer={fermerMenu}
              />
            </li>
          ))}
        </ul>
      </details>
      <ul className="hidden text-[12.5px] xl:flex xl:flex-wrap">
        {ITEMS.map((item) => (
          <li key={item.href}>
            <LienNav item={item} actif={estActif(item.href, pathname)} precharger={precharger} variante="bureau" />
          </li>
        ))}
      </ul>
    </nav>
  );
}

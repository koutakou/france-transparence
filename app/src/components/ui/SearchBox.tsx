"use client";

import { useEffect, useId, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

/**
 * Recherche globale (header) — client.
 *
 * Contrat API (route NON implémentée ici) :
 * `GET /api/recherche?q=…` → `{ resultats: [{ type, libelle, sous_libelle?, href }] }`
 *
 * Comportement :
 * - debounce 250 ms, requêtes obsolètes annulées (AbortController) ;
 * - dropdown navigable au clavier (↑ ↓ Entrée Échap) et à la souris ;
 * - API absente / 404 / erreur réseau → état vide SILENCIEUX (aucun
 *   message d'erreur : la route arrive avec l'ingestion) ;
 * - libellés injectés en texte (React), jamais en HTML (DATAVIZ §5 :
 *   noms = données non fiables).
 */
export interface ResultatRecherche {
  /** « élu », « institution », « marché »… (affiché en préfixe discret). */
  type: string;
  libelle: string;
  sous_libelle?: string;
  href: string;
}

export interface SearchBoxProps {
  placeholder?: string;
  className?: string;
}

const DEBOUNCE_MS = 250;
const MIN_CARACTERES = 2;

function estResultat(x: unknown): x is ResultatRecherche {
  if (typeof x !== "object" || x === null) return false;
  const r = x as Record<string, unknown>;
  return (
    typeof r.type === "string" &&
    typeof r.libelle === "string" &&
    typeof r.href === "string" &&
    (r.sous_libelle === undefined || typeof r.sous_libelle === "string")
  );
}

export function SearchBox({
  placeholder = "Rechercher un élu, une institution…",
  className,
}: SearchBoxProps) {
  const [q, setQ] = useState("");
  const [resultats, setResultats] = useState<ResultatRecherche[]>([]);
  const [ouvert, setOuvert] = useState(false);
  const [actif, setActif] = useState(-1);
  const listeId = useId();
  const router = useRouter();
  const racine = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const terme = q.trim();
    // terme trop court : la remise à zéro est faite par le onChange (jamais
    // de setState synchrone dans le corps d'un effet)
    if (terme.length < MIN_CARACTERES) return;
    const controleur = new AbortController();
    const minuteur = setTimeout(async () => {
      try {
        const rep = await fetch(`/api/recherche?q=${encodeURIComponent(terme)}`, {
          signal: controleur.signal,
        });
        if (!rep.ok) {
          // route pas encore implémentée (404) ou erreur : silence
          setResultats([]);
          setOuvert(false);
          return;
        }
        const corps: unknown = await rep.json();
        const bruts = (corps as { resultats?: unknown })?.resultats;
        const propres = Array.isArray(bruts) ? bruts.filter(estResultat) : [];
        setResultats(propres);
        setOuvert(propres.length > 0);
        setActif(propres.length > 0 ? 0 : -1);
      } catch {
        // abort ou réseau : état vide silencieux
        if (!controleur.signal.aborted) {
          setResultats([]);
          setOuvert(false);
        }
      }
    }, DEBOUNCE_MS);
    return () => {
      clearTimeout(minuteur);
      controleur.abort();
    };
  }, [q]);

  const fermer = () => {
    setOuvert(false);
    setActif(-1);
  };

  const surClavier = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!ouvert || resultats.length === 0) {
      if (e.key === "Escape") fermer();
      return;
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActif((a) => (a + 1) % resultats.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActif((a) => (a - 1 + resultats.length) % resultats.length);
    } else if (e.key === "Enter" && actif >= 0) {
      e.preventDefault();
      fermer();
      router.push(resultats[actif].href);
    } else if (e.key === "Escape") {
      fermer();
    }
  };

  return (
    <div
      ref={racine}
      className={`relative ${className ?? ""}`}
      onBlur={(e) => {
        if (!racine.current?.contains(e.relatedTarget as Node | null)) fermer();
      }}
    >
      <svg
        width="14"
        height="14"
        viewBox="0 0 14 14"
        aria-hidden="true"
        className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-muted"
      >
        <circle cx="6" cy="6" r="4.4" fill="none" stroke="currentColor" strokeWidth="1.5" />
        <path d="M9.4 9.4L13 13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
      <input
        type="search"
        role="combobox"
        aria-expanded={ouvert}
        aria-controls={listeId}
        aria-activedescendant={actif >= 0 ? `${listeId}-${actif}` : undefined}
        aria-label="Recherche globale"
        autoComplete="off"
        spellCheck={false}
        value={q}
        placeholder={placeholder}
        onChange={(e) => {
          const v = e.target.value;
          setQ(v);
          if (v.trim().length < MIN_CARACTERES) {
            setResultats([]);
            setOuvert(false);
            setActif(-1);
          }
        }}
        onKeyDown={surClavier}
        onFocus={() => resultats.length > 0 && setOuvert(true)}
        className="w-full rounded-lg border border-card-border bg-page py-1.5 pl-9 pr-3 text-[13px] text-ink placeholder:text-ink-muted focus:border-raised-border"
      />
      {ouvert && (
        <ul
          id={listeId}
          role="listbox"
          aria-label="Résultats de recherche"
          className="absolute left-0 right-0 top-full z-50 mt-1 max-h-80 overflow-y-auto rounded-lg border border-raised-border bg-raised py-1 shadow-[0_8px_24px_rgba(0,0,0,0.45)]"
        >
          {resultats.map((r, i) => (
            <li key={`${r.href}-${i}`} id={`${listeId}-${i}`} role="option" aria-selected={i === actif}>
              <Link
                href={r.href}
                tabIndex={-1}
                onClick={fermer}
                onMouseEnter={() => setActif(i)}
                className={`flex items-baseline gap-2 px-3 py-2 text-[13px] ${
                  i === actif ? "bg-hover" : ""
                }`}
              >
                <span className="w-20 shrink-0 text-[10px] font-medium uppercase tracking-[0.08em] text-ink-muted">
                  {r.type}
                </span>
                <span className="min-w-0">
                  <span className="block truncate text-ink">{r.libelle}</span>
                  {r.sous_libelle && (
                    <span className="block truncate text-xs text-ink-secondary">{r.sous_libelle}</span>
                  )}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

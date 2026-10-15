"use client";

import { useEffect, useId, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { urlSite } from "@/lib/basePath";
import type { IndexRecherche } from "@/lib/recherche-index";
import {
  MIN_CARACTERES,
  preparerIndex,
  rechercher,
  type IndexPret,
  type ResultatRecherche,
} from "@/lib/recherche";

/**
 * Recherche globale (header) — 100 % client, sur index statique.
 *
 * Le site est statique : l'ancienne route de recherche paramétrique n'existe
 * plus. Au premier focus (ou à la première frappe), la SearchBox charge UNE FOIS
 * l'index pré-généré `/data/recherche-index.json` (élus + entités,
 * reconstruit chaque jour avec le site), puis interroge en local
 * (règles de correspondance : `lib/recherche.ts`), 8 élus + 4 entités
 * maximum.
 *
 * CONTRAT FICHES : seuls les élus à mandat depute / senateur / président
 * de conseil départemental ou régional ont une fiche /elus/<id> — les
 * autres résultats mènent à la liste /elus (jamais vers une fiche 404) et
 * l'affichent (« dans les listes /elus »).
 *
 * - dropdown navigable au clavier (↑ ↓ Entrée Échap) et à la souris ;
 * - index indisponible / erreur réseau → silence, panneau fermé (comme avant :
 *   ne pas afficher « erreur » ni « index absent » — fuite d’implémentation) ;
 * - index prêt + 0 hit → panneau non sélectionnable (périmètre réel de l’index :
 *   élus / institutions, jamais un « aucun résultat » nu) ;
 * - une zone `role="status"` TOUJOURS montée (seul son texte change) annonce
 *   le chargement, le nombre de résultats ou leur absence : une zone montée
 *   en même temps que son texte n'est pas annoncée de façon fiable ;
 * - raccourci « / » hors champs éditables ; hint visuel bureau seulement ;
 * - libellés injectés en texte (React), jamais en HTML (DATAVIZ §5 :
 *   noms = données non fiables).
 */
export type { ResultatRecherche } from "@/lib/recherche";

export interface SearchBoxProps {
  placeholder?: string;
  className?: string;
}

const DEBOUNCE_MS = 150;

/** Cycle de vie de l’index — distinct de « 0 hit » (qui n’existe qu’en `pret`). */
type EtatIndex = "absent" | "chargement" | "pret" | "indisponible";

/**
 * « / » ne doit pas voler la frappe déjà engagée dans un champ.
 * (input/textarea/select/contentEditable — pas les boutons ni le reste.)
 */
function estChampEditable(cible: EventTarget | null): boolean {
  if (!(cible instanceof HTMLElement)) return false;
  if (cible.isContentEditable) return true;
  const tag = cible.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT";
}

let indexPromesse: Promise<IndexPret | null> | null = null;

function chargerIndex(): Promise<IndexPret | null> {
  indexPromesse ??= fetch(urlSite("/data/recherche-index.json"))
    .then((rep) => (rep.ok ? (rep.json() as Promise<IndexRecherche | null>) : null))
    .then((brut) => (brut ? preparerIndex(brut) : null))
    .catch(() => null);
  return indexPromesse;
}

export function SearchBox({
  placeholder = "Rechercher un élu, une institution…",
  className,
}: SearchBoxProps) {
  const [q, setQ] = useState("");
  const [resultats, setResultats] = useState<ResultatRecherche[]>([]);
  const [ouvert, setOuvert] = useState(false);
  const [actif, setActif] = useState(-1);
  const [etatIndex, setEtatIndex] = useState<EtatIndex>("absent");
  // Terme pour lequel `rechercher()` a réellement tourné — évite d’annoncer
  // « aucun élu » sur une requête pas encore interrogée (debounce / 1er fetch).
  const [termeRecherche, setTermeRecherche] = useState("");
  const [aLeFocus, setALeFocus] = useState(false);
  const listeId = useId();
  const inputId = useId();
  const router = useRouter();
  const racine = useRef<HTMLDivElement>(null);
  const champ = useRef<HTMLInputElement>(null);
  // Routes de résultats déjà demandées au préchargement (une seule fois chacune).
  const dejaPrechargees = useRef<Set<string>>(new Set());

  /**
   * Préchargement d'un résultat, à l'intention de clic SEULEMENT.
   *
   * Les liens du dropdown portent `prefetch={false}` : ils apparaissent tous
   * dans le viewport dès l'ouverture de la liste, et le préchargement par
   * défaut tirerait donc jusqu'à 12 payloads RSC de fiches à chaque frappe
   * suffisamment sélective — pour un seul clic au bout. En Next 16.3.1,
   * `false` coupe aussi le survol (cf. MainNav), on le réarme ici à la main.
   */
  const precharger = (href: string) => {
    if (dejaPrechargees.current.has(href)) return;
    dejaPrechargees.current.add(href);
    router.prefetch(href);
  };

  /** Premier appel : `absent` → `chargement`. Les suivants réutilisent la promesse mémoïsée. */
  const assurerIndex = () => {
    setEtatIndex((etat) => (etat === "absent" ? "chargement" : etat));
    void chargerIndex().then((index) => {
      setEtatIndex(index ? "pret" : "indisponible");
      if (!index) {
        // Silence : l’index n’est pas là, ce n’est pas « 0 hit ».
        setResultats([]);
        setOuvert(false);
        setActif(-1);
      }
    });
  };

  useEffect(() => {
    const terme = q.trim();
    // terme trop court : la remise à zéro est faite par le onChange (jamais
    // de setState synchrone dans le corps d'un effet)
    if (terme.length < MIN_CARACTERES) return;
    let annule = false;
    const minuteur = setTimeout(async () => {
      const index = await chargerIndex();
      if (annule) return;
      if (!index) {
        // index indisponible : silence (même comportement que l'ancienne API absente)
        setEtatIndex("indisponible");
        setResultats([]);
        setOuvert(false);
        setActif(-1);
        return;
      }
      setEtatIndex("pret");
      const propres = rechercher(index, terme);
      setResultats(propres);
      setTermeRecherche(terme);
      // Index prêt : ouvrir même à 0 hit (status honnête). `actif` reste -1
      // s’il n’y a pas d’option — Entrée ne doit pas naviguer sur le status.
      setOuvert(true);
      setActif(propres.length > 0 ? 0 : -1);
    }, DEBOUNCE_MS);
    return () => {
      annule = true;
      clearTimeout(minuteur);
    };
  }, [q]);

  useEffect(() => {
    const surSlash = (e: KeyboardEvent) => {
      if (e.key !== "/") return;
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      if (estChampEditable(e.target)) return;
      e.preventDefault();
      champ.current?.focus();
    };
    window.addEventListener("keydown", surSlash);
    return () => window.removeEventListener("keydown", surSlash);
  }, []);

  const fermer = () => {
    setOuvert(false);
    setActif(-1);
  };

  /**
   * Safari (et d'autres) posent relatedTarget=null au blur : fermer
   * tout de suite démonterait la liste avant que le click du résultat
   * n'arrive. preventDefault sur mousedown du panneau + délai court.
   */
  const surBlurRacine = (e: React.FocusEvent<HTMLDivElement>) => {
    const suivant = e.relatedTarget as Node | null;
    if (suivant && racine.current?.contains(suivant)) return;
    window.setTimeout(() => {
      if (!racine.current?.contains(document.activeElement)) fermer();
    }, 100);
  };

  const surClavier = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!ouvert || resultats.length === 0) {
      if (e.key === "Escape") fermer();
      return;
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActif((a) => (a + 1) % resultats.length);
      // Même intention de clic qu'un survol : le déplacement au clavier réarme
      // le préchargement, sinon Entrée déclencherait une navigation froide.
      // (L'index est celui du rendu courant : en cas de répétition rapide de
      // touche, on précharge au pire un voisin — l'état, lui, reste exact.)
      precharger(resultats[(actif + 1) % resultats.length].href);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActif((a) => (a - 1 + resultats.length) % resultats.length);
      precharger(resultats[(actif - 1 + resultats.length) % resultats.length].href);
    } else if (e.key === "Enter" && actif >= 0) {
      e.preventDefault();
      fermer();
      router.push(resultats[actif].href);
    } else if (e.key === "Escape") {
      fermer();
    }
  };

  const terme = q.trim();
  const afficherListe = ouvert && resultats.length > 0;
  const afficherChargement = ouvert && etatIndex === "chargement" && terme.length >= MIN_CARACTERES;
  const afficherVide =
    ouvert &&
    etatIndex === "pret" &&
    terme.length >= MIN_CARACTERES &&
    resultats.length === 0 &&
    termeRecherche === terme;
  const panneauOuvert = afficherListe || afficherChargement || afficherVide;
  const messageVide = `Aucun élu ni institution trouvé pour « ${terme} » dans l’index de recherche.`;
  // Texte de la zone d'annonce, toujours montée : seul ce texte change.
  const annonce = afficherListe
    ? `${resultats.length} résultat${resultats.length > 1 ? "s" : ""} pour « ${termeRecherche} ».`
    : afficherChargement
      ? "Chargement de l’index…"
      : afficherVide
        ? messageVide
        : "";

  return (
    <div
      ref={racine}
      className={`relative ${className ?? ""}`}
      onBlur={surBlurRacine}
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
        id={inputId}
        ref={champ}
        type="search"
        role="combobox"
        aria-autocomplete="list"
        aria-haspopup={afficherListe ? "listbox" : undefined}
        aria-keyshortcuts="/"
        aria-expanded={panneauOuvert}
        aria-controls={afficherListe ? listeId : undefined}
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
            return;
          }
          // Fetch encore en cours : ouvrir tout de suite le status « chargement »
          // (le debounce ne sert qu’à `rechercher()`, pas à masquer l’attente).
          if (etatIndex === "absent" || etatIndex === "chargement") {
            assurerIndex();
            setOuvert(true);
            setActif(-1);
          }
        }}
        onKeyDown={surClavier}
        onFocus={() => {
          setALeFocus(true);
          // pré-chargement de l'index au premier focus (une seule requête)
          assurerIndex();
          if (resultats.length > 0) setOuvert(true);
          else if (terme.length >= MIN_CARACTERES && etatIndex !== "indisponible") setOuvert(true);
        }}
        onBlur={() => setALeFocus(false)}
        className="w-full min-h-11 rounded-lg border border-card-border bg-page py-1.5 pl-9 pr-9 text-base text-ink placeholder:text-ink-muted focus:border-raised-border xl:text-[13px]"
      />
      {!q && !aLeFocus && (
        <kbd
          aria-hidden="true"
          className="pointer-events-none absolute right-3 top-1/2 hidden -translate-y-1/2 items-center text-[11px] leading-none text-ink-muted xl:flex"
        >
          /
        </kbd>
      )}
      {afficherListe && (
        <ul
          id={listeId}
          role="listbox"
          aria-label="Résultats de recherche"
          className="absolute left-0 right-0 top-full z-50 mt-1 max-h-80 overflow-y-auto rounded-lg border border-raised-border bg-raised py-1 shadow-[0_8px_24px_rgba(0,0,0,0.45)]"
          onMouseDown={(e) => e.preventDefault()}
        >
          {resultats.map((r, i) => (
            <li key={`${r.href}-${i}`} id={`${listeId}-${i}`} role="option" aria-selected={i === actif}>
              <Link
                href={r.href}
                tabIndex={-1}
                prefetch={false}
                onClick={fermer}
                onMouseEnter={() => {
                  setActif(i);
                  precharger(r.href);
                }}
                onFocus={() => precharger(r.href)}
                onTouchStart={() => precharger(r.href)}
                className={`flex min-h-11 items-baseline gap-2 px-3 py-2 text-[13px] ${
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
      {(afficherChargement || afficherVide) && (
        <div
          aria-hidden="true"
          className="absolute left-0 right-0 top-full z-50 mt-1 rounded-lg border border-raised-border bg-raised px-3 py-2.5 text-[13px] text-ink-secondary shadow-[0_8px_24px_rgba(0,0,0,0.45)]"
          onMouseDown={(e) => e.preventDefault()}
        >
          {afficherChargement ? "Chargement de l’index…" : messageVide}
        </div>
      )}
      <div role="status" className="sr-only">
        {annonce}
      </div>
    </div>
  );
}

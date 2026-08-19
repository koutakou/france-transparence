"use client";

import { useEffect, useId, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { urlSite } from "@/lib/basePath";
import type { IndexRecherche } from "@/lib/recherche-index";

/**
 * Recherche globale (header) — 100 % client, sur index statique.
 *
 * Le site est statique : l'ancienne route de recherche paramétrique n'existe
 * plus. Au premier focus (ou à la première frappe), la SearchBox charge UNE FOIS
 * l'index pré-généré `/data/recherche-index.json` (élus + entités,
 * reconstruit chaque jour avec le site), puis interroge en local :
 * insensible aux accents et à la casse, parlementaires d'abord, 8 élus +
 * 4 entités maximum (mêmes plafonds que l'ancienne API).
 *
 * CONTRAT FICHES : seuls les élus à mandat depute / senateur / président
 * de conseil départemental ou régional ont une fiche /elus/<id> — les
 * autres résultats mènent à la liste /elus (jamais vers une fiche 404) et
 * l'affichent (« dans les listes /elus »).
 *
 * - dropdown navigable au clavier (↑ ↓ Entrée Échap) et à la souris ;
 * - index absent / erreur réseau → état vide SILENCIEUX (comme avant) ;
 * - libellés injectés en texte (React), jamais en HTML (DATAVIZ §5 :
 *   noms = données non fiables).
 */
export interface ResultatRecherche {
  /** « Élu·e », « Ministère »… (affiché en préfixe discret). */
  type: string;
  libelle: string;
  sous_libelle?: string;
  href: string;
}

export interface SearchBoxProps {
  placeholder?: string;
  className?: string;
}

const DEBOUNCE_MS = 150;
const MIN_CARACTERES = 2;
const MAX_ELUS = 8;
const MAX_ENTITES = 4;

/** Minuscules sans diacritiques (recherche insensible accents/casse). */
function plie(s: string): string {
  return s
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
}

/** Index enrichi de ses clés de recherche pré-pliées (calculées une fois). */
type IndexPret = {
  brut: IndexRecherche;
  elusCles: { nom: string; prenom: string; complet: string }[];
  entitesCles: { nom: string; sigle: string }[];
};

let indexPromesse: Promise<IndexPret | null> | null = null;

function chargerIndex(): Promise<IndexPret | null> {
  indexPromesse ??= fetch(urlSite("/data/recherche-index.json"))
    .then((rep) => (rep.ok ? (rep.json() as Promise<IndexRecherche | null>) : null))
    .then((brut) => {
      if (!brut) return null;
      return {
        brut,
        elusCles: brut.elus.map((e) => {
          const nom = plie(e[0]);
          const prenom = plie(e[1]);
          return { nom, prenom, complet: prenom ? `${prenom} ${nom}` : nom };
        }),
        entitesCles: brut.entites.map((e) => ({ nom: plie(e[0]), sigle: plie(e[1]) })),
      };
    })
    .catch(() => null);
  return indexPromesse;
}

/** Recherche locale — mêmes plafonds et priorités que l'ancienne API. */
function rechercher(index: IndexPret, brutQ: string): ResultatRecherche[] {
  const q = plie(brutQ.trim());
  if (q.length < MIN_CARACTERES) return [];
  const { brut, elusCles, entitesCles } = index;

  // Élus : nom, prénom ou « prénom nom » ; parlementaires puis préfixe de
  // nom puis ordre alphabétique (l'index est déjà trié alphabétiquement).
  type Candidat = { i: number; rang: number };
  const candidats: Candidat[] = [];
  for (let i = 0; i < brut.elus.length; i++) {
    const cles = elusCles[i];
    if (!cles.nom.includes(q) && !cles.prenom.includes(q) && !cles.complet.includes(q)) continue;
    const typeIdx = brut.elus[i][2];
    // 0/1 = député/sénateur en exercice, 7/8 = parlementaire du seul RNE.
    const parlementaire = typeIdx === 0 || typeIdx === 1 || typeIdx === 7 || typeIdx === 8;
    const rang = (parlementaire ? 0 : 2) + (cles.nom.startsWith(q) ? 0 : 1);
    candidats.push({ i, rang });
  }
  candidats.sort((a, b) => a.rang - b.rang || a.i - b.i);

  const resultats: ResultatRecherche[] = candidats.slice(0, MAX_ELUS).map(({ i }) => {
    const [nom, prenom, typeIdx, depIdx, id] = brut.elus[i];
    const mandat = brut.typesMandat[typeIdx] ?? "Élu·e";
    const dep = depIdx >= 0 ? brut.departements[depIdx] : undefined;
    const morceaux = [mandat];
    if (dep) morceaux.push(dep);
    if (!id) morceaux.push("dans les listes /elus");
    return {
      type: "Élu·e",
      libelle: `${prenom} ${nom}`.trim(),
      sous_libelle: morceaux.join(" · "),
      href: id ? `/elus/${encodeURIComponent(id)}` : "/elus",
    };
  });

  // Entités (ministères, institutions, collectivités, partis) — l'index
  // est déjà dans l'ordre de priorité de l'ancienne API.
  let nbEntites = 0;
  for (let i = 0; i < brut.entites.length && nbEntites < MAX_ENTITES; i++) {
    const cles = entitesCles[i];
    if (!cles.nom.includes(q) && !cles.sigle.includes(q)) continue;
    const [nom, sigle, typeIdx, hrefIdx] = brut.entites[i];
    resultats.push({
      type: brut.typesEntite[typeIdx] ?? "Institution",
      libelle: nom,
      sous_libelle: sigle || undefined,
      href: brut.hrefs[hrefIdx] ?? "/elus",
    });
    nbEntites++;
  }

  return resultats;
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
    let annule = false;
    const minuteur = setTimeout(async () => {
      const index = await chargerIndex();
      if (annule) return;
      if (!index) {
        // index indisponible : silence (même comportement que l'ancienne API absente)
        setResultats([]);
        setOuvert(false);
        return;
      }
      const propres = rechercher(index, terme);
      setResultats(propres);
      setOuvert(propres.length > 0);
      setActif(propres.length > 0 ? 0 : -1);
    }, DEBOUNCE_MS);
    return () => {
      annule = true;
      clearTimeout(minuteur);
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
        onFocus={() => {
          // pré-chargement de l'index au premier focus (une seule requête)
          void chargerIndex();
          if (resultats.length > 0) setOuvert(true);
        }}
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

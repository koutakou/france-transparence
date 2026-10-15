"use client";

import { useEffect, useState } from "react";
import { Money } from "@/components/ui/Money";
import { urlSite } from "@/lib/basePath";
import { AO_ACCUEIL_AFFICHEES, echeancesOuvertes } from "@/lib/echeances";
import type { AoProcheCloture } from "@/lib/queries/accueil";
import { useHorloge } from "@/lib/useHorloge";

/**
 * Appels d'offres proches de la clôture (accueil), re-filtrés À L'HEURE DU
 * VISITEUR.
 *
 * Le HTML porte les AO_ACCUEIL_AFFICHEES premières échéances ouvertes à la
 * construction : c'est ce que lit un visiteur sans JavaScript, et la page le
 * date. Dès que l'une d'elles est passée à l'heure du navigateur, la réserve
 * /data/accueil/ao-cloture.json (toutes les clôtures des RESERVE_HEURES qui
 * suivent la construction, et quelques-unes au-delà) est chargée une fois,
 * et les premières encore ouvertes s'affichent.
 *
 * Si même la réserve est épuisée (publications en échec plusieurs jours de
 * suite), la liste le dit — sans jamais affirmer qu'aucun appel d'offres
 * n'est ouvert : elle ne sait que ce qu'elle a reçu.
 */
type Reserve = { construitLe: number; lignes: AoProcheCloture[] };

let promesse: Promise<Reserve | null> | null = null;

function chargerReserve(): Promise<Reserve | null> {
  promesse ??= fetch(urlSite("/data/accueil/ao-cloture.json"))
    .then((rep) => (rep.ok ? (rep.json() as Promise<Reserve | null>) : null))
    .catch(() => null);
  return promesse;
}

/** ISO → `JJ/MM HH:MM`, heure de Paris. */
function formatDateHeureFr(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return new Intl.DateTimeFormat("fr-FR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Europe/Paris",
  }).format(d);
}

export function AoProchesCloture({
  initiales,
  construitLe,
  libelleConstruction,
}: {
  initiales: AoProcheCloture[];
  construitLe: number;
  /** Instant de construction déjà formaté par la page (« JJ/MM/AAAA à HHhMM »). */
  libelleConstruction: string;
}) {
  const maintenant = useHorloge(construitLe);
  const [reserve, setReserve] = useState<Reserve | null>(null);
  const [indisponible, setIndisponible] = useState(false);

  const dateLimite = (a: AoProcheCloture) => a.dateLimite;
  // Moins de lignes initiales que d'emplacements : il n'en existait pas
  // d'autres à la construction, la réserve n'apporterait rien.
  const besoinReserve =
    initiales.length >= AO_ACCUEIL_AFFICHEES &&
    echeancesOuvertes(initiales, dateLimite, maintenant, AO_ACCUEIL_AFFICHEES).length <
      AO_ACCUEIL_AFFICHEES;

  useEffect(() => {
    if (!besoinReserve || reserve !== null || indisponible) return;
    let monte = true;
    chargerReserve().then((r) => {
      if (!monte) return;
      if (r === null) setIndisponible(true);
      else setReserve(r);
    });
    return () => {
      monte = false;
    };
  }, [besoinReserve, reserve, indisponible]);

  const lignes = echeancesOuvertes(
    reserve?.lignes ?? initiales,
    dateLimite,
    maintenant,
    AO_ACCUEIL_AFFICHEES,
  );

  if (lignes.length === 0) {
    return (
      <li className="py-2 text-[13px] text-ink-muted">
        Les échéances de la liste arrêtée le {libelleConstruction} sont toutes passées à
        cette heure ; la liste est reconstruite à chaque publication du site.
      </li>
    );
  }

  return (
    <>
      {lignes.map((ao) => (
        <li key={ao.id} className="py-2" style={{ borderBottom: "1px solid var(--viz-grid)" }}>
          <div className="flex items-baseline justify-between gap-3 text-[11px]">
            <span className="shrink-0 font-medium text-ink-secondary [font-variant-numeric:tabular-nums]">
              Clôture le {formatDateHeureFr(ao.dateLimite)}
            </span>
            <span className="min-w-0 break-words text-right text-ink-muted">
              {ao.acheteur?.trim() ? ao.acheteur : "acheteur non renseigné"}
            </span>
          </div>
          <p className="line-clamp-2 break-words text-[13px] text-ink" title={ao.objet ?? undefined}>
            {ao.url ? (
              <a
                href={ao.url}
                target="_blank"
                rel="noopener noreferrer"
                className="underline-offset-2 hover:underline"
              >
                {ao.objet?.trim() ? ao.objet : "objet non publié"}
              </a>
            ) : ao.objet?.trim() ? (
              ao.objet
            ) : (
              "objet non publié"
            )}
          </p>
          <p className="text-[11px] text-ink-muted">
            Montant estimé&nbsp;:{" "}
            {ao.montantEstime !== null ? (
              <Money valeur={ao.montantEstime} className="text-ink-secondary" />
            ) : (
              "non publié"
            )}
          </p>
        </li>
      ))}
    </>
  );
}

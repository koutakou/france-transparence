"use client";

import { Money } from "@/components/ui/Money";
import { AO_ACCUEIL_AFFICHEES, echeancesOuvertes } from "@/lib/echeances";
import type { AoProcheCloture } from "@/lib/queries/accueil";
import { useHorloge } from "@/lib/useHorloge";
import { useTrancheEcheances } from "@/lib/useTrancheEcheances";

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

/**
 * Appels d'offres proches de la clôture (accueil), re-filtrés À L'HEURE DU
 * VISITEUR.
 *
 * Le HTML porte les AO_ACCUEIL_AFFICHEES premières échéances ouvertes à la
 * construction : c'est ce que lit un visiteur sans JavaScript, et la page le
 * date. Dès que l'une d'elles est passée à l'heure du navigateur, la tranche
 * horaire de cette heure (/data/accueil/ao-cloture/<heure>.json : les seules
 * lignes affichables pendant l'heure, lib/echeances.ts) est chargée, et les
 * premières encore ouvertes s'affichent ; une heure plus tard, la suivante.
 *
 * Si même la dernière tranche est épuisée (publications en échec plusieurs
 * jours de suite), la liste le dit — sans jamais affirmer qu'aucun appel
 * d'offres n'est ouvert : elle ne sait que ce qu'elle a reçu.
 */
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

  const dateLimite = (a: AoProcheCloture) => a.dateLimite;
  // Moins de lignes initiales que d'emplacements : il n'en existait pas
  // d'autres à la construction, une tranche n'apporterait rien.
  const besoinTranche =
    initiales.length >= AO_ACCUEIL_AFFICHEES &&
    echeancesOuvertes(initiales, dateLimite, maintenant, AO_ACCUEIL_AFFICHEES).length <
      AO_ACCUEIL_AFFICHEES;
  const tranche = useTrancheEcheances<AoProcheCloture>(
    "/data/accueil/ao-cloture",
    construitLe,
    maintenant,
    besoinTranche,
  );

  const lignes = echeancesOuvertes(
    tranche.lignes ?? initiales,
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

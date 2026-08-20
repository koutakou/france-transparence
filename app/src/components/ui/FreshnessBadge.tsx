import { formatDateFr } from "@/lib/format";

/**
 * Badge de fraîcheur — OBLIGATOIRE sur chaque module (ARCHITECTURE §5) :
 * « Données au JJ/MM/AAAA · <source> · <fréquence> », cliquable vers la
 * source amont. `dateDonnees` = date de la donnée la plus récente réellement
 * en base (`meta_sources.date_donnees`), JAMAIS la date du jour ni la date
 * de modif du dataset amont.
 *
 * `mention` porte les précisions héritées de SOURCES.md quand elles
 * s'imposent : « en cours de consolidation », « provisoire », « PLF »…
 *
 * @example
 * <FreshnessBadge dateDonnees="2026-06-30" source="DECP consolidées"
 *                 frequence="quotidienne" url="https://data.gouv.fr/…"
 *                 mention="en cours de consolidation" />
 */
export interface FreshnessBadgeProps {
  /** ISO (`meta_sources.date_donnees`). */
  dateDonnees: string;
  /** Nom court de la source (« Chorus », « HATVP AGORA »…). */
  source: string;
  /** « quotidienne », « mensuelle »… (`meta_sources.frequence`). */
  frequence: string;
  /** URL de la source amont. */
  url: string;
  /** Mention obligatoire éventuelle (« provisoire », « PLF »…). */
  mention?: string;
  className?: string;
}

export function FreshnessBadge({
  dateDonnees,
  source,
  frequence,
  url,
  mention,
  className,
}: FreshnessBadgeProps) {
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      title={`Ouvrir la source : ${url}`}
      className={`inline-flex max-w-full items-center gap-1.5 rounded-full border border-card-border bg-card px-2.5 py-1 text-[11px] leading-none text-ink-muted transition-colors hover:border-raised-border hover:text-ink-secondary ${className ?? ""}`}
    >
      <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true" className="shrink-0">
        <circle cx="5" cy="5" r="3.5" fill="none" stroke="currentColor" strokeWidth="1.2" />
        <path d="M5 3v2.2l1.5 1" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
      </svg>
      <span className="truncate">
        Données au {formatDateFr(dateDonnees)} · {source} · {frequence}
        {mention ? ` · ${mention}` : ""}
      </span>
    </a>
  );
}

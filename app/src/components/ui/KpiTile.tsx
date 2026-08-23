import type { ReactNode } from "react";
import { DeltaPct } from "./DeltaPct";
import { Sparkline } from "./Sparkline";

/**
 * Stat tile — contrat DATAVIZ §6 :
 * - `label` : 12px `--ink-secondary`, casse de phrase, pas de deux-points ;
 * - `valeur` : 24–32px semibold `--ink-primary`, chiffres PROPORTIONNELS
 *   (jamais tabular-nums sur un grand nombre isolé), déjà formatée par la
 *   page (`<Money/>`, `formatNombre`…) ;
 * - `montantVedette` : peint la valeur en `--montant` (KPI montant vedette) ;
 * - `delta` : flèche + signe + période nommée, couleur = signe × upIsGood
 *   (§3.5 — NEUTRE par défaut : une dépense en hausse n'est pas « mauvaise ») ;
 * - `tendance` : sparkline 12 points, trait `--viz-autre`, fin `--viz-serie-1` ;
 * - `perimetre` : ce que le chiffre COUVRE, quand le libellé ne suffit pas à le
 *   dire — fenêtre glissante, strate, filtre de source, population exclue.
 *
 * POURQUOI cet emplacement existe : une tuile n'offrait que `label` et `valeur`,
 * là où une `Card` offre `sousTitre`, `droite` et une note de bas de carte. Les
 * chiffres bornés affichés en tuile n'avaient donc AUCUN endroit où dire leur
 * borne, et ne la disaient pas — un compte sur 24 mois glissants se lisait comme
 * un total, un dénombrement partiel comme un recensement. Un chiffre borné doit
 * pouvoir dire sa borne à l'endroit où il est lu, pas ailleurs sur la page.
 *
 * @example
 * <KpiTile label="Dépenses payées (juillet)"
 *          valeur={<Money valeur={4.2e9} />} montantVedette
 *          delta={{ valeur: 4.2, vs: "juin" }}
 *          tendance={[3,4,4,5,6,5,7,8,8,9,10,11]} />
 */
export interface KpiTileProps {
  label: string;
  /** Valeur DÉJÀ formatée (string ou <Money/>). */
  valeur: ReactNode;
  /** Peint la valeur en `--montant` (réservé aux montants vedettes, §3.5). */
  montantVedette?: boolean;
  delta?: {
    valeur: number;
    /** Période de comparaison nommée (« 2024 », « juin »…). */
    vs?: string;
    /** Défaut `null` = neutre (cas des montants de dépense). */
    upIsGood?: boolean | null;
  };
  /** 12 points attendus (§6). */
  tendance?: number[];
  /**
   * Périmètre réel du chiffre, en une ligne, quand le libellé ne le dit pas :
   * « notifiés sur 24 mois glissants », « budgets principaux seuls », « hors
   * conseillers municipaux ». Rendu sous la valeur, avant le delta.
   */
  perimetre?: string;
  /** Sans chrome de carte — pour l'usage dans un StatStrip. */
  nu?: boolean;
  className?: string;
}

export function KpiTile({
  label,
  valeur,
  montantVedette = false,
  delta,
  tendance,
  perimetre,
  nu = false,
  className,
}: KpiTileProps) {
  const chrome = nu ? "" : "rounded-xl border border-card-border bg-card ";
  return (
    <div className={`${chrome}flex items-start justify-between gap-3 p-4 ${className ?? ""}`}>
      <div className="min-w-0">
        <div className="text-xs text-ink-secondary">{label}</div>
        <div
          className="mt-1 text-[26px] font-semibold leading-tight text-ink"
          style={montantVedette ? { color: "var(--montant)" } : undefined}
        >
          {valeur}
        </div>
        {perimetre && (
          <div className="mt-1 text-[11px] leading-normal text-ink-muted">{perimetre}</div>
        )}
        {delta && (
          <div className="mt-1">
            <DeltaPct valeur={delta.valeur} vs={delta.vs} upIsGood={delta.upIsGood ?? null} />
          </div>
        )}
      </div>
      {tendance && tendance.length > 0 && (
        <Sparkline valeurs={tendance} emphaseFin largeur={96} hauteur={32} className="mt-5 shrink-0" />
      )}
    </div>
  );
}

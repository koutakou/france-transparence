import { formatNombre, formatPct } from "@/lib/format";
import { cssSurvolColonnes, TooltipGraphique } from "./TooltipGraphique";

/**
 * Donut de répartition (part-du-tout) — SVG maison.
 *
 * Règles DATAVIZ §2 : UNIQUEMENT du part-du-tout en ordre de grandeur,
 * ≤ 6 segments (au-delà, ce composant replie l'excédent en « Autre »,
 * `--viz-autre`), segments dans l'ordre des slots catégoriels, écarts de
 * 2px en `--surface-card`, anneau de 24px d'épaisseur, TOTAL au centre.
 * JAMAIS pour comparer des parts proches (< 5 points d'écart) → BarList.
 *
 * Légende À DROITE obligatoire : pastille + libellé + valeur + % — jamais
 * la couleur seule (§9). Le texte reste en encres, l'identité vient de la
 * pastille (§3.1). `totalMontant` peint le total central en `--montant`
 * (montant vedette, §3.5). La légende garde une largeur minimale lisible :
 * si la place à droite manque, elle passe SOUS le donut (flex-wrap) plutôt
 * que de tronquer les libellés à quelques caractères ; le libellé complet
 * reste accessible au survol (tooltip HTML, pas `title` natif).
 *
 * @example
 * <Donut parts={[
 *   { libelle: "Personnel", valeur: 142e9 },
 *   { libelle: "Fonctionnement", valeur: 61e9 },
 *   { libelle: "Intervention", valeur: 88e9 },
 * ]} formatValeur={(v) => formatEuros(v)} libelleTotal="Total 2026" totalMontant />
 */
export interface DonutPart {
  libelle: string;
  /** Valeur ≥ 0 (les négatives sont ramenées à 0). */
  valeur: number;
  /** Override ponctuel (ex. « Autre » déjà replié en amont → `var(--viz-autre)`). */
  couleur?: string;
}

export interface DonutProps {
  parts: DonutPart[];
  /** Format des valeurs (légende + total) — défaut nombre fr. */
  formatValeur?: (v: number) => string;
  /** Libellé sous le total central (ex. « Total 2026 »). */
  libelleTotal?: string;
  /** Peint le total central en `--montant` (total monétaire vedette). */
  totalMontant?: boolean;
  /** Diamètre du donut en px (défaut 200). */
  taille?: number;
  ariaLabel?: string;
  className?: string;
}

const SLOTS = [
  "var(--viz-serie-1)",
  "var(--viz-serie-2)",
  "var(--viz-serie-3)",
  "var(--viz-serie-4)",
  "var(--viz-serie-5)",
  "var(--viz-serie-6)",
];

/** Secteur d'anneau [a0, a1] (radians depuis 12 h, sens horaire). */
function arcAnneau(cx: number, cy: number, rExt: number, rInt: number, a0: number, a1: number): string {
  const pt = (r: number, a: number) => [cx + r * Math.sin(a), cy - r * Math.cos(a)] as const;
  const [x0e, y0e] = pt(rExt, a0);
  const [x1e, y1e] = pt(rExt, a1);
  const [x1i, y1i] = pt(rInt, a1);
  const [x0i, y0i] = pt(rInt, a0);
  const grand = a1 - a0 > Math.PI ? 1 : 0;
  return [
    `M${x0e.toFixed(3)},${y0e.toFixed(3)}`,
    `A${rExt},${rExt} 0 ${grand} 1 ${x1e.toFixed(3)},${y1e.toFixed(3)}`,
    `L${x1i.toFixed(3)},${y1i.toFixed(3)}`,
    `A${rInt},${rInt} 0 ${grand} 0 ${x0i.toFixed(3)},${y0i.toFixed(3)}`,
    "Z",
  ].join(" ");
}

export function Donut({
  parts,
  formatValeur = (v) => formatNombre(v),
  libelleTotal = "Total",
  totalMontant = false,
  taille = 200,
  ariaLabel,
  className,
}: DonutProps) {
  const propres = parts.map((p) => ({ ...p, valeur: Math.max(p.valeur, 0) }));
  // ≤ 6 segments (§2) : repli de l'excédent en « Autre »
  let affichees = propres;
  if (propres.length > 6) {
    const tete = propres.slice(0, 5);
    const reste = propres.slice(5).reduce((somme, p) => somme + p.valeur, 0);
    affichees = [...tete, { libelle: "Autre", valeur: reste, couleur: "var(--viz-autre)" }];
  }
  const total = affichees.reduce((somme, p) => somme + p.valeur, 0);
  if (total <= 0) return null;

  const cx = taille / 2;
  const cy = taille / 2;
  const rExt = taille / 2 - 2;
  const rInt = rExt - 24; // anneau de 24px (§2)

  // angles cumulés calculés sans mutation (n ≤ 6 : le O(n²) est gratuit)
  const segments = affichees.map((p, i) => {
    const part = p.valeur / total;
    const avant = affichees.slice(0, i).reduce((somme, q) => somme + q.valeur, 0) / total;
    const a0 = avant * 2 * Math.PI;
    const a1 = a0 + part * 2 * Math.PI;
    return { ...p, couleur: p.couleur ?? SLOTS[i], part, a0, a1 };
  });

  const pleins = segments.filter((s) => s.part > 0);
  const segmentUnique = pleins.length === 1;

  const iDernier = Math.max(0, pleins.length - 1);

  return (
    <div
      className={`ft-donut relative flex flex-wrap items-center gap-x-6 gap-y-4 ${className ?? ""}`}
      tabIndex={ariaLabel ? 0 : undefined}
      aria-label={ariaLabel}
    >
      <style>{cssSurvolColonnes(".ft-donut", "ft-donut-seg", pleins.length)}</style>
      <svg
        width={taille}
        height={taille}
        viewBox={`0 0 ${taille} ${taille}`}
        aria-hidden={ariaLabel ? true : undefined}
        className="relative shrink-0"
      >
        <style>{`.ft-donut-seg:hover { filter: brightness(1.18); }
          @media (prefers-reduced-motion: reduce) { .ft-donut-seg:hover { filter: none; } }`}</style>
        {segmentUnique ? (
          <circle
            className="ft-donut-seg"
            data-i={0}
            cx={cx}
            cy={cy}
            r={(rExt + rInt) / 2}
            fill="none"
            stroke={pleins[0].couleur}
            strokeWidth={rExt - rInt}
          />
        ) : (
          pleins.map((s, i) => (
            <path
              key={s.libelle}
              className="ft-donut-seg"
              data-i={i}
              d={arcAnneau(cx, cy, rExt, rInt, s.a0, s.a1)}
              fill={s.couleur}
              // écart de 2px en couleur de carte entre segments (§4)
              stroke="var(--surface-card)"
              strokeWidth={2}
              strokeLinejoin="round"
            />
          ))
        )}
        {/* total au centre — chiffres proportionnels, --montant si vedette */}
        <text
          x={cx}
          y={cy - 2}
          textAnchor="middle"
          fontSize={Math.max(18, Math.min(26, taille * 0.12))}
          fontWeight={600}
          fill={totalMontant ? "var(--montant)" : "var(--ink-primary)"}
        >
          {formatValeur(total)}
        </text>
        <text x={cx} y={cy + 16} textAnchor="middle" fontSize={11} fill="var(--ink-secondary)">
          {libelleTotal}
        </text>
      </svg>
      {pleins.map((s, i) => (
        <TooltipGraphique
          key={`tip-${s.libelle}`}
          data-i={i}
          data-dernier={i === iDernier}
          lignes={[
            {
              nom: s.libelle,
              valeur: `${formatValeur(s.valeur)} (${formatPct(s.part * 100)})`,
              couleur: s.couleur,
            },
          ]}
          style={{
            left: taille / 2,
            top: 8,
            transform: "translate(-50%, 0)",
          }}
        />
      ))}
      {/* légende : pastille + libellé + valeur + % (jamais la couleur seule).
          min-width lisible : plutôt que d'écraser les libellés, la légende
          descend sous le donut quand la place à droite manque (flex-wrap). */}
      <ul className="flex min-w-[min(15rem,100%)] flex-1 flex-col gap-1.5 text-[13px]">
        {segments.map((s) => (
          <li key={s.libelle} className="flex items-baseline gap-2">
            <span
              aria-hidden="true"
              className="inline-block size-3 shrink-0 translate-y-px rounded-[3px]"
              style={{ background: s.couleur }}
            />
            <span className="min-w-0 text-ink-secondary">
              {s.libelle}
            </span>
            <span className="ml-auto shrink-0 font-medium text-ink [font-variant-numeric:tabular-nums]">
              {formatValeur(s.valeur)}
            </span>
            <span className="w-14 shrink-0 text-right text-ink-muted [font-variant-numeric:tabular-nums]">
              {formatPct(s.part * 100)}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

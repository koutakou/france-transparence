import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { BarList } from "@/components/ui/BarList";
import { Card } from "@/components/ui/Card";
import { FreshnessBadge } from "@/components/ui/FreshnessBadge";
import { StatStrip } from "@/components/ui/StatStrip";
import { ESPACE_FINE, formatEuros, formatNombre } from "@/lib/format";
import {
  getArbreMission,
  getSlugsMissions,
  getSourcesBudget,
  LIBELLES_TYPEBUDGET,
  type ActionDestination,
} from "@/lib/queries/depenses";
import { metadonneesPage } from "@/lib/seo";

/**
 * Page statique d'une mission (S21) : programme → action → sous-action en
 * listes dépliables NATIVES (`<details>`, aucun JavaScript, aucun fetch) —
 * tout le contenu est dans le HTML généré au build. Les 46 pages sont
 * pré-rendues (`dynamicParams = false`), comme les fiches élus.
 */
export const dynamicParams = false;

export function generateStaticParams(): { mission: string }[] {
  return getSlugsMissions().map((slug) => ({ mission: slug }));
}

interface Props {
  params: Promise<{ mission: string }>;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { mission } = await params;
  const arbre = getArbreMission(mission);
  return metadonneesPage({
    chemin: `/depenses/destination/${mission}/`,
    ...(arbre && {
      titre: `Mission « ${arbre.libelle} » — budget 2025`,
      description: `Mission « ${arbre.libelle} » du PLF 2025 : programmes, actions et sous-actions, crédits de paiement et autorisations d'engagement, ventilation par titre.`,
    }),
  });
}

/** `68483628839` → `68,48 Md€` (précision maîtrisée pour les KPI). */
function enMd(v: number, decimales = 2): string {
  return `${formatNombre(v / 1e9, decimales)}${ESPACE_FINE}Md€`;
}

/** Montant compact (Md€/M€ selon l'ordre de grandeur) avec valeur exacte. */
function Montant({ valeur }: { valeur: number }) {
  return (
    <span
      className="shrink-0 whitespace-nowrap text-ink [font-variant-numeric:tabular-nums]"
      title={`${formatNombre(valeur)}${ESPACE_FINE}€`}
    >
      {formatEuros(valeur)}
    </span>
  );
}

/**
 * Une action et, si la nomenclature en définit, ses sous-actions. Quand
 * l'action n'est pas subdivisée dans la source, elle s'affiche seule —
 * aucune sous-action n'est inventée.
 */
function LigneAction({ action }: { action: ActionDestination }) {
  const entete = (
    <span className="flex min-w-0 flex-1 items-baseline justify-between gap-3">
      <span className="min-w-0 text-[13px] text-ink-secondary">
        <span className="mr-2 font-mono text-[11px] text-ink-muted">{action.action}</span>
        {action.libelle}
      </span>
      <Montant valeur={action.cp} />
    </span>
  );
  if (action.sousActions.length === 0) {
    return <li className="flex py-1.5 pl-5">{entete}</li>;
  }
  return (
    <li>
      <details>
        <summary className="flex cursor-pointer select-none list-none items-baseline gap-1.5 py-1.5 [&::-webkit-details-marker]:hidden">
          <span aria-hidden="true" className="w-3.5 shrink-0 text-[10px] text-ink-muted transition-transform [details[open]>summary_&]:rotate-90">
            ▸
          </span>
          {entete}
        </summary>
        <ul className="mb-1 ml-5 border-l border-[var(--viz-grid)] pl-4">
          {action.sousActions.map((s) => (
            <li key={s.sousAction} className="flex items-baseline justify-between gap-3 py-1">
              <span className="min-w-0 text-[13px] text-ink-secondary">
                <span className="mr-2 font-mono text-[11px] text-ink-muted">{s.sousAction}</span>
                {s.libelle}
              </span>
              <Montant valeur={s.cp} />
            </li>
          ))}
        </ul>
      </details>
    </li>
  );
}

export default async function PageMission({ params }: Props) {
  const { mission } = await params;
  const arbre = getArbreMission(mission);
  if (!arbre) notFound();
  const sources = getSourcesBudget();

  const badge = sources?.S21 && (
    <FreshnessBadge
      dateDonnees={sources.S21.date_donnees}
      source="PLF 2025 — destination"
      frequence={sources.S21.frequence}
      url={sources.S21.url}
      mention="PLF 2025 — projet"
    />
  );

  const typeBudget = LIBELLES_TYPEBUDGET[arbre.typebudget] ?? arbre.typebudget;
  const nbActions = arbre.programmes.reduce((n, p) => n + p.actions.length, 0);

  return (
    <div className="flex flex-col gap-6">
      {/* En-tête de module */}
      <section className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
        <div className="max-w-2xl">
          <p className="text-xs text-ink-muted">
            <Link
              href="/depenses/destination/"
              className="underline decoration-[var(--viz-grid)] underline-offset-2 transition-colors hover:decoration-current"
            >
              Budget 2025 par destination
            </Link>{" "}
            / mission
          </p>
          <h1 className="mt-1 text-[13px] font-semibold uppercase tracking-[0.14em] text-ink">
            Mission «&nbsp;{arbre.libelle}&nbsp;»
          </h1>
          <p className="mt-2 text-sm text-ink-secondary">
            {typeBudget} ({arbre.typebudget}) — {arbre.etiquette}. Montants
            BRUTS en crédits de paiement (CP) et autorisations
            d&apos;engagement (AE), non comparables aux dépenses nettes de la
            page Dépenses. Ministère{arbre.ministeres.length > 1 ? "s" : ""} de
            rattachement&nbsp;: {arbre.ministeres.join(" · ") || "non renseigné"}.
          </p>
        </div>
        {badge}
      </section>

      {/* KPI de la mission */}
      <StatStrip
        stats={[
          {
            label: "Crédits de paiement 2025 (bruts)",
            valeur: <span title={`${formatNombre(arbre.cp)}${ESPACE_FINE}€`}>{enMd(arbre.cp)}</span>,
            montantVedette: true,
          },
          {
            label: "Autorisations d'engagement 2025 (brutes)",
            valeur: <span title={`${formatNombre(arbre.ae)}${ESPACE_FINE}€`}>{enMd(arbre.ae)}</span>,
          },
          {
            label: "Programmes / actions",
            valeur: `${formatNombre(arbre.programmes.length)}${ESPACE_FINE}/${ESPACE_FINE}${formatNombre(nbActions)}`,
          },
        ]}
      />

      {/* Ventilation par titre de la mission */}
      {arbre.titres.length > 0 && (
        <Card
          titre="Ventilation par titre (nature de la dépense)"
          sousTitre="CP bruts 2025 de la mission, par titre LOLF"
          droite={badge}
        >
          <BarList
            items={arbre.titres.map((t) => ({
              libelle: t.libelle ?? `Titre ${t.titre}`,
              valeur: t.cp,
            }))}
            formatValeur={(v) => formatEuros(v)}
          />
        </Card>
      )}

      {/* Arbre programme → action → sous-action */}
      <Card
        titre="Programmes, actions et sous-actions"
        sousTitre="CP bruts 2025 — déplier un programme, puis une action marquée ▸ quand la nomenclature définit des sous-actions"
        droite={badge}
      >
        <ul className="flex flex-col divide-y divide-[var(--viz-grid)]">
          {arbre.programmes.map((p) => (
            <li key={p.programme}>
              <details open={arbre.programmes.length === 1}>
                <summary className="flex cursor-pointer select-none list-none items-baseline gap-2 py-2.5 [&::-webkit-details-marker]:hidden">
                  <span aria-hidden="true" className="w-3.5 shrink-0 text-[11px] text-ink-muted transition-transform [details[open]>summary_&]:rotate-90">
                    ▸
                  </span>
                  <span className="flex min-w-0 flex-1 items-baseline justify-between gap-3">
                    <span className="min-w-0 text-sm text-ink">
                      <span className="mr-2 font-mono text-[11px] text-ink-muted">
                        {p.programme}
                      </span>
                      {p.libelle}
                    </span>
                    <Montant valeur={p.cp} />
                  </span>
                </summary>
                <ul className="mb-2 ml-5 border-l border-[var(--viz-grid)] pl-4">
                  {p.actions.map((a) => (
                    <LigneAction key={a.action} action={a} />
                  ))}
                </ul>
              </details>
            </li>
          ))}
        </ul>
        <p className="mt-3 text-xs text-ink-muted">
          Les sous-actions ne sont définies que là où la nomenclature du
          PLF 2025 en publie&nbsp;: une action sans marque ▸ n&apos;est pas
          subdivisée dans la source. Les montants affichés sont les CP&nbsp;;
          la valeur exacte en euros apparaît au survol.
        </p>
      </Card>

      {/* Encadré pédagogique obligatoire — CAS Pensions */}
      {arbre.mission === "YD" && (
        <Card titre="Ce que cette mission couvre — et ne couvre pas">
          <div className="flex max-w-3xl flex-col gap-3 text-sm leading-relaxed text-ink-secondary">
            <p>
              La mission «&nbsp;Pensions&nbsp;» est un compte
              d&apos;affectation spéciale (CAS). Elle couvre les pensions dont
              l&apos;État est l&apos;employeur&nbsp;: retraites des
              fonctionnaires civils de l&apos;État, retraites des militaires,
              pensions des ouvriers des établissements industriels de
              l&apos;État, et pensions militaires d&apos;invalidité et des
              victimes de guerre.
            </p>
            <p>
              Les retraites du régime général (CNAV), l&apos;assurance maladie
              et les prestations familiales (CAF) relèvent de la loi de
              financement de la sécurité sociale, hors budget de
              l&apos;État&nbsp;: elles ne figurent pas ici.
            </p>
          </div>
        </Card>
      )}
    </div>
  );
}

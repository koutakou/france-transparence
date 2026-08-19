import { getMetaSources } from "@/lib/db";

// La base locale évolue à chaque ingestion : jamais figer cet état au build.
export const dynamic = "force-dynamic";

/**
 * Accueil — placeholder SOBRE (la vraie home est construite quand les
 * modules s'activent). Aucune donnée fictive : le seul chiffre affiché est
 * l'état réel de la base locale.
 */
export default function Home() {
  const sources = getMetaSources();

  return (
    <section className="flex flex-col gap-6">
      <h1 className="text-[13px] font-semibold uppercase tracking-[0.14em] text-ink">
        Vue d&apos;ensemble
      </h1>
      <p className="max-w-2xl text-sm text-ink-secondary">
        Dépenses publiques, marchés, élus, lobbying, financement politique :
        un tableau de bord construit sur données publiques réelles uniquement,
        avec leur fraîcheur mesurée et affichée.
      </p>
      <div className="max-w-2xl rounded-xl border border-card-border bg-card p-5 text-sm text-ink-muted">
        {sources === null ? (
          <p>
            La base locale n&apos;est pas encore construite — lancer{" "}
            <code className="rounded bg-raised px-1.5 py-0.5">make ingest</code>{" "}
            pour ingérer les sources.
          </p>
        ) : (
          <p>
            {sources.length} source{sources.length > 1 ? "s" : ""} ingérée
            {sources.length > 1 ? "s" : ""} dans la base locale.
          </p>
        )}
      </div>
      <p className="flex items-center gap-2 text-xs text-ink-muted">
        <span
          aria-hidden="true"
          className="inline-block size-1.5 rounded-full"
          style={{ background: "var(--viz-serie-1)" }}
        />
        Ingestion des données en cours — les modules s&apos;activent au fur et
        à mesure.
      </p>
    </section>
  );
}

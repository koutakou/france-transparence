import { getMetaSources } from "@/lib/db";

// La base locale évolue à chaque ingestion : jamais figer cet état au build.
export const dynamic = "force-dynamic";

export default function Home() {
  const sources = getMetaSources();

  return (
    <section className="flex flex-col gap-6">
      <h1 className="text-3xl font-semibold text-ink">France Transparence</h1>
      <p className="max-w-2xl text-ink-secondary">
        Dépenses publiques, marchés, élus, lobbying, financement politique :
        données en cours d&apos;ingestion.
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
    </section>
  );
}

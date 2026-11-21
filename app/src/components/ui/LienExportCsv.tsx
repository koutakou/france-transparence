import { urlSite } from "@/lib/basePath";
import { cheminCsv, cheminProvenance, type DefinitionCsv } from "@/lib/exports-csv";

/**
 * Lien « Télécharger (CSV) » sous un tableau qui a sa version tableur
 * (`lib/exports-csv.ts`), avec à côté le fichier de provenance du CSV
 * (sources amont, licence, date des données, sens des colonnes). Les deux
 * chemins viennent de la définition de l'export : le lien ne peut pas
 * pointer ailleurs que vers la route statique qui publie ce fichier.
 */
export function LienExportCsv({
  definition,
  className,
}: {
  definition: Pick<DefinitionCsv<unknown>, "fichier" | "titre">;
  className?: string;
}) {
  const lien =
    "inline-flex min-h-6 items-center underline decoration-dotted underline-offset-2 hover:text-ink-secondary";
  return (
    <p className={`mt-2 flex flex-wrap items-center gap-x-3 text-xs text-ink-muted ${className ?? ""}`}>
      <a href={urlSite(cheminCsv(definition.fichier))} download className={lien}>
        Télécharger (CSV)
        <span className="sr-only">, {definition.titre}</span>
      </a>
      <a href={urlSite(cheminProvenance(definition.fichier))} className={lien}>
        Provenance du fichier
        <span className="sr-only"> CSV, {definition.titre}</span>
      </a>
    </p>
  );
}

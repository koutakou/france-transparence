import { ESPACE_FINE, formatNombre } from "@/lib/format";
import type { ValeurOmise } from "@/lib/queries/budget-ruptures";

const MOIS = [
  "janvier", "février", "mars", "avril", "mai", "juin",
  "juillet", "août", "septembre", "octobre", "novembre", "décembre",
];

/**
 * Sous un graphique de cumuls S13 : les cellules retirées de la série pour
 * rupture de périmètre amont (`budget_mensuel_ruptures`), avec leur valeur
 * publiée. Elles sont retirées de la courbe et du tableau jumeau, où elles
 * se liraient comme comparables aux autres mois — pas du site : la valeur
 * est dite ici, et sert telle quelle là où elle est le chiffre lu.
 * Rien n'est rendu quand aucune cellule n'est omise.
 */
export function NoteRupturesPerimetre({ omises }: { omises: ValeurOmise[] }) {
  if (omises.length === 0) return null;
  const premiere = omises[0].rupture;
  return (
    <p className="mt-3 text-xs text-ink-muted">
      Ni tracé ni tabulé avec les autres mois&nbsp;:{" "}
      {omises
        .map(
          (o) =>
            `${MOIS[o.mois - 1]} ${o.annee} (${formatNombre(o.rupture.montantPublie / 1e9, 2)}${ESPACE_FINE}Md€ publiés)`,
        )
        .join(", ")}
      .{" "}
      {omises.length > 1
        ? "Les lignes DGFiP de ces mois n’ont pas le périmètre des autres."
        : `La ligne DGFiP de ce mois n’a pas le périmètre des autres${
            premiere.definitionConstatee
              ? ` : elle vaut ${premiere.definitionConstatee}, les autres mois ${premiere.identite}`
              : ""
          }.`}
    </p>
  );
}

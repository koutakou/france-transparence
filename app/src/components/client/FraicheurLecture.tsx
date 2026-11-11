"use client";

import { formatDateFr } from "@/lib/format";
import {
  ancrageCalcul,
  constatAttente,
  evalueFraicheur,
  libelleAge,
  NIVEAUX,
  phraseFraicheur,
  phraseSynthese,
  syntheseFraicheur,
  type SourceDatee,
} from "@/lib/fraicheur";
import { useHorloge } from "@/lib/useHorloge";

/**
 * Fraîcheur de /donnees recalculée À LA DATE DE LECTURE.
 *
 * Au rendu serveur et à l'hydratation, `useHorloge` rend `construitLe` : le
 * HTML statique est l'état du jour de construction, et il le DIT (« état
 * calculé le … », « N jours au … »). Juste après l'hydratation, la même
 * fonction (`evalueFraicheur`, lib/fraicheur.ts) rejoue avec l'heure du
 * navigateur : un site resté figé trois jours ne se dit plus « à jour ».
 * Les seuils n'existent qu'à un endroit ; ces îles n'en portent aucun.
 */

/** Synthèse en tête du tableau : niveaux comptés, puis sources en attente. */
export function SyntheseFraicheurLecture({
  sources,
  construitLe,
}: {
  sources: SourceDatee[];
  construitLe: number;
}) {
  const maintenant = useHorloge(construitLe);
  const synthese = syntheseFraicheur(sources, new Date(maintenant));
  return (
    <>
      <p>
        <span className="text-ink-muted">{ancrageCalcul(maintenant, construitLe)} : </span>
        <strong className="text-ink">{phraseSynthese(synthese)}</strong>.
      </p>
      {synthese.enAttente.length > 0 && (
        <ul className="flex flex-col gap-1.5">
          {synthese.enAttente.map(({ source, fraicheur }) => (
            <li
              key={source.source_id}
              className="border-l pl-3"
              style={{ borderColor: "var(--viz-grid)" }}
            >
              <span className="text-ink">{source.nom}</span>{" "}
              <span className="text-[11px] text-ink-muted">({source.source_id})</span>{" "}
              — données au {formatDateFr(source.date_donnees)} ;{" "}
              {constatAttente(fraicheur)} ({libelleAge(fraicheur)}).
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

/** Badge d'une ligne du tableau (pastille + libellé — jamais la couleur seule). */
export function BadgeFraicheurLecture({
  sourceId,
  dateDonnees,
  construitLe,
}: {
  sourceId: string;
  dateDonnees: string;
  construitLe: number;
}) {
  const maintenant = new Date(useHorloge(construitLe));
  const f = evalueFraicheur(sourceId, dateDonnees, maintenant);
  const n = NIVEAUX[f.niveau];
  const detaille = f.niveau === "en_retard" || f.niveau === "attente_edition";
  // La phrase complète (date, âge, seuils propres à la source) se déplie au
  // clic, au clavier et au doigt : un attribut `title` ne s'ouvre qu'au
  // survol de la souris.
  return (
    <details className="group">
      <summary className="inline-flex cursor-pointer list-none flex-col gap-0.5 [&::-webkit-details-marker]:hidden">
        <span className="inline-flex items-center gap-1.5 whitespace-nowrap">
          <span
            aria-hidden="true"
            className="inline-block size-2 shrink-0 rounded-full"
            style={{ background: n.jeton }}
          />
          <span className="text-ink-secondary underline decoration-dotted underline-offset-2">
            {n.libelle}
          </span>
        </span>
        {detaille && (
          <span className="whitespace-nowrap pl-3.5 text-[11px] text-ink-muted">
            {libelleAge(f)}
          </span>
        )}
      </summary>
      <p className="mt-1 max-w-[16rem] whitespace-normal pl-3.5 text-[11px] leading-snug text-ink-muted">
        {phraseFraicheur(dateDonnees, f, maintenant)}
      </p>
    </details>
  );
}

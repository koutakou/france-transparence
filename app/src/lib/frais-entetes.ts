/**
 * En-têtes des catégories de /frais et dates des sources — module PUR,
 * testé par `npm test` (tests/frais-entetes.test.mjs).
 *
 * Un millésime n'est jamais écrit dans un en-tête : il se lit dans les faits
 * du groupe (`periode`, `date_source`, colonnes de trainvie_faits). Quand les
 * faits n'en partagent pas un seul (le pipeline S31 en met un à jour avant
 * les autres), l'en-tête ne choisit pas : il renvoie à la période que chaque
 * ligne affiche déjà, et la phrase reste complète.
 */
import { formatDateFr } from "@/lib/format";
import type { TrainvieCategorie, TrainvieFait } from "@/lib/queries/frais";

const MOIS_LONGS = [
  "janvier",
  "février",
  "mars",
  "avril",
  "mai",
  "juin",
  "juillet",
  "août",
  "septembre",
  "octobre",
  "novembre",
  "décembre",
];

/** Dates sources à granularité variable : `2025` → `2025` ;
 *  `2026-01` → `janvier 2026` ; `2026-02-17` → `17/02/2026`.
 *  (formatDateFr inventerait un jour précis sur `2026-01`.) */
export function formatDateSourceFr(d: string): string {
  if (/^\d{4}$/.test(d)) return d;
  const m = /^(\d{4})-(\d{2})$/.exec(d);
  if (m) return `${MOIS_LONGS[Number(m[2]) - 1]} ${m[1]}`;
  return formatDateFr(d);
}

/** Période commune à un groupe de faits, ou `null` s'ils n'en partagent pas une seule. */
export function periodeCommune(faits: Pick<TrainvieFait, "periode">[]): string | null {
  const periodes = new Set(faits.map((f) => f.periode));
  return periodes.size === 1 ? [...periodes][0] : null;
}

/** Date de source commune à un groupe de faits, ou `null`. */
export function dateSourceCommune(faits: Pick<TrainvieFait, "date_source">[]): string | null {
  const dates = new Set(faits.map((f) => f.date_source));
  return dates.size === 1 ? [...dates][0] : null;
}

type Faits = Pick<TrainvieFait, "periode" | "date_source">[];

/** Titre et sous-titre d'une catégorie, phrase complète dans tous les cas. */
export function enTeteCategorie(
  cle: TrainvieCategorie,
  faits: Faits,
): { titre: string; sousTitre: string } {
  const p = periodeCommune(faits);
  switch (cle) {
    case "indemnites_parlementaires":
      return {
        titre: "Indemnités parlementaires",
        sousTitre:
          "Barèmes publiés par les assemblées. Bruts et nets y coexistent tels qu’ils sont publiés : chaque montant porte son assiette, ne les comparez pas entre eux.",
      };
    case "frais_mandat":
      return {
        titre: "Frais de mandat — les enveloppes",
        sousTitre:
          "Avances et dotations forfaitaires : les barèmes sont publics, pas le détail des dépenses",
      };
    case "controles":
      return {
        titre: "Contrôles des frais de mandat",
        sousTitre:
          "Agrégats anonymisés publiés par le déontologue de l’Assemblée nationale et le comité de déontologie du Sénat",
      };
    case "elysee":
      return {
        titre: "Élysée",
        sousTitre:
          "Comptes de la présidence de la République audités par la Cour des comptes — un rapport par an",
      };
    case "institutions":
      return p
        ? {
            titre: `Institutions — dotations ${p}`,
            sousTitre: `Mission « Pouvoirs publics » de la loi de finances initiale pour ${p}`,
          }
        : {
            titre: "Institutions — dotations",
            sousTitre:
              "Mission « Pouvoirs publics » des lois de finances initiales — l’exercice de chaque dotation est indiqué sur sa ligne",
          };
    case "cabinets": {
      const d = dateSourceCommune(faits);
      return {
        titre: "Cabinets ministériels",
        sousTitre: d
          ? `Jaune budgétaire « Personnels affectés dans les cabinets ministériels » — situation au ${formatDateSourceFr(d)}`
          : "Jaune budgétaire « Personnels affectés dans les cabinets ministériels » — la date de chaque situation est indiquée sur sa ligne",
      };
    }
    case "elus_locaux":
      return {
        titre: "Élus locaux — barèmes",
        sousTitre: p
          ? `Indemnités maximales publiées par la DGCL, barème ${p} — les montants réellement versés ne sont pas centralisés`
          : "Indemnités maximales publiées par la DGCL — le barème de chaque montant est indiqué sur sa ligne ; les montants réellement versés ne sont pas centralisés",
      };
  }
}

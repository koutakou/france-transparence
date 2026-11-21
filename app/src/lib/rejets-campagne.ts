/**
 * Carte « comptes de campagne rejetés » de /financement : un agrégat SANS NOM.
 *
 * Décision du propriétaire du 21/11/2026 : TOUS les rejets de comptes de
 * campagne passent en agrégats, plus aucun nom. Les seules personnes que la
 * règle précédente nommait étaient des députés en exercice, pour qui le juge
 * de l'élection a vraisemblablement déjà statué : la réserve « décision non
 * définitive » aurait été fausse. Le site publie le nombre de rejets et
 * renvoie aux décisions du Conseil constitutionnel, sans en dire l'issue.
 *
 * Les liens sont FIXES : ils ne viennent plus de la table `alertes`, dont les
 * anciennes lignes de rejet étaient nominatives.
 */
import { formatNombre, formatPct } from "@/lib/format";

/** Jeu de données CNCCFP des comptes de campagne des législatives 2024. */
export const URL_SOURCE_REJETS =
  "https://www.data.gouv.fr/datasets/elections-legislatives-generales-des-30-juin-et-7-juillet-2024/";

/** Décisions du Conseil constitutionnel, juge des élections législatives. */
export const URL_DECISIONS_CONSEIL_CONSTITUTIONNEL =
  "https://www.conseil-constitutionnel.fr/decisions";

/** Ce que le fichier CNCCFP dit, et ne dit pas, d'un rejet. */
export const RESERVE_REJETS =
  "En cas de rejet, la CNCCFP saisit le juge de l'élection, le Conseil constitutionnel pour les législatives (code électoral, art. L. 52-15 et LO 136-1). Ses décisions sont publiées sur conseil-constitutionnel.fr. Ce fichier ne dit pas leur issue.";

export const REGLE_REJETS =
  "Comptes dont la décision CNCCFP est « rejeté » (code R) dans le fichier des comptes de campagne des législatives 2024, comptés sans nom. Le site ne nomme aucun candidat dont le compte a été rejeté.";

export const BASE_LEGALE_REJETS =
  "Code électoral, art. L. 52-15 (contrôle des comptes de campagne par la CNCCFP, qui saisit le juge de l'élection en cas de rejet) et LO 136-1 (le Conseil constitutionnel statue pour tous les candidats aux élections législatives).";

export type FamilleRejete = {
  nb: number;
  depenses_retenues: number;
  remboursement_etat: number;
};

export type CarteRejets = {
  titre: string;
  detail: string;
  regle: string;
  baseLegale: string;
  source: { libelle: string; url: string };
  juge: { libelle: string; url: string };
};

/** Textes et liens de la carte, depuis l'agrégat `v_campagnes_2024_par_decision`. */
export function carteRejets(
  familleRejete: FamilleRejete | null,
  comptesDeposes: number,
  tauxRejetComptesDeposes: number,
): CarteRejets {
  const nb = familleRejete?.nb ?? 0;
  const montants = familleRejete
    ? ` Dépenses retenues de ces comptes : ${formatNombre(familleRejete.depenses_retenues)} €, remboursement de l'État : ${formatNombre(familleRejete.remboursement_etat)} €.`
    : "";
  return {
    titre: `${formatNombre(nb)} comptes de campagne rejetés par la CNCCFP (législatives 2024)`,
    detail: `${formatNombre(nb)} comptes rejetés sur ${formatNombre(comptesDeposes)} comptes déposés (${formatPct(tauxRejetComptesDeposes * 100, 2)}).${montants} ${RESERVE_REJETS}`,
    regle: REGLE_REJETS,
    baseLegale: BASE_LEGALE_REJETS,
    source: { libelle: "CNCCFP, data.gouv.fr", url: URL_SOURCE_REJETS },
    juge: {
      libelle: "Décisions du Conseil constitutionnel (conseil-constitutionnel.fr)",
      url: URL_DECISIONS_CONSEIL_CONSTITUTIONNEL,
    },
  };
}

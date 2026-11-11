"use client";

import { formatDateFr, formatNombre } from "@/lib/format";
import { ageRevolu } from "@/lib/lecture";
import { useHorloge } from "@/lib/useHorloge";

/**
 * « (57 ans au 08/11/2026) » dans le HTML statique, « (58 ans) » chez le
 * lecteur. L'âge révolu change à chaque anniversaire, que la page soit
 * reconstruite ou non : calculé au build sans date, il était faux pour toute
 * fiche dont l'élu avait fêté son anniversaire depuis (mesuré le 11/11/2026
 * sur deux sénatrices nées les 9 et 10 novembre, site figé au 08/11). Au
 * rendu serveur et à l'hydratation, `useHorloge` rend `construitLe` : l'âge
 * est alors DATÉ ; juste après, il est celui du jour de lecture.
 */
export function AgeALaLecture({ naissance, construitLe }: { naissance: string; construitLe: number }) {
  const maintenant = useHorloge(construitLe);
  const age = ageRevolu(naissance, new Date(maintenant));
  if (age === null) return null;
  const ancrage =
    maintenant === construitLe ? ` au ${formatDateFr(new Date(construitLe).toISOString())}` : "";
  return <>{` (${formatNombre(age)} ans${ancrage})`}</>;
}

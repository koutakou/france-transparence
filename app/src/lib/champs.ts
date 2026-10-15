/**
 * Copie des lignes SANS le champ `cle` : avant de passer des lignes à une
 * île client, la page retire ce qu'elle n'affiche pas (une donnée non
 * affichée ne voyage pas dans le payload).
 */
export function sansChamp<T extends object, K extends keyof T>(lignes: T[], cle: K): Omit<T, K>[] {
  return lignes.map((l) => {
    const copie = { ...l };
    delete copie[cle];
    return copie;
  });
}

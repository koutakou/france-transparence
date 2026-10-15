"use client";

import { useEffect, useState } from "react";
import { urlSite } from "@/lib/basePath";
import { nomTranche, trancheAConsulter } from "@/lib/echeances";

/**
 * Tranche horaire d'échéances (lib/echeances.ts) que la visite en cours
 * demande, chargée seulement quand `utile` : quand une échéance du HTML est
 * passée à l'heure du visiteur. Une heure plus tard, la tranche suivante est
 * chargée à son tour ; en attendant, la précédente reste affichée.
 *
 * `dossier` : chemin-site des tranches (`/data/marches/ao-toutes`), chaque
 * fichier s'appelant `<heure UTC>.json`. Rend `lignes: null` tant que rien
 * n'est chargé, `indisponible: true` si le fichier n'a pas pu l'être.
 */
type Tranche<T> = { tranche: string; lignes: T[] } | null;

const promesses = new Map<string, Promise<Tranche<unknown>>>();

function charger<T>(url: string): Promise<Tranche<T>> {
  let p = promesses.get(url);
  if (!p) {
    p = fetch(url)
      .then((rep) => (rep.ok ? (rep.json() as Promise<Tranche<unknown>>) : null))
      .catch(() => null);
    promesses.set(url, p);
  }
  return p as Promise<Tranche<T>>;
}

export function useTrancheEcheances<T>(
  dossier: string,
  construitLe: number,
  maintenant: number,
  utile: boolean,
): { lignes: T[] | null; indisponible: boolean } {
  const tranche = trancheAConsulter(maintenant, construitLe);
  const [chargee, setChargee] = useState<{ tranche: number; lignes: T[] } | null>(null);
  const [enEchec, setEnEchec] = useState<number | null>(null);

  useEffect(() => {
    if (!utile || chargee?.tranche === tranche || enEchec === tranche) return;
    let monte = true;
    charger<T>(urlSite(`${dossier}/${nomTranche(tranche)}.json`)).then((r) => {
      if (!monte) return;
      if (r === null) setEnEchec(tranche);
      else setChargee({ tranche, lignes: r.lignes });
    });
    return () => {
      monte = false;
    };
  }, [dossier, tranche, utile, chargee, enEchec]);

  return { lignes: chargee?.lignes ?? null, indisponible: enEchec === tranche };
}

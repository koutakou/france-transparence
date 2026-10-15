"use client";

import { BarChart, type BarChartProps } from "@/components/ui/BarChart";
import { BarList, type BarListProps } from "@/components/ui/BarList";
import { Donut, type DonutProps } from "@/components/ui/Donut";
import { LineChart, type LineChartProps } from "@/components/ui/LineChart";
import { formateur, type FormatValeur } from "@/lib/formatValeur";

/**
 * Graphiques du kit `ui/` rendus en ÎLES CLIENT, pour les pages proches du
 * budget de 500 Ko de HTML.
 *
 * Rendu serveur, un graphique pèse deux fois : son SVG dans le HTML, et le
 * même arbre d'éléments (cibles de survol, relevés, règles CSS) sérialisé
 * dans le payload RSC. En île, seules les données traversent la frontière :
 * le HTML statique est le MÊME (rendu serveur du composant client, lisible
 * sans JavaScript), le payload ne porte que les points. Même raison d'être
 * que SerieMensuelleMarches et TableTronquee.
 *
 * Une fonction ne traverse pas la frontière serveur → client : le format des
 * valeurs est donc un spec sérialisable (lib/formatValeur.ts).
 */
export function LineChartIle({
  format,
  ...props
}: Omit<LineChartProps, "formatValeur"> & { format?: FormatValeur }) {
  return <LineChart {...props} formatValeur={formateur(format)} />;
}

export function BarChartIle({
  format,
  ...props
}: Omit<BarChartProps, "formatValeur"> & { format?: FormatValeur }) {
  return <BarChart {...props} formatValeur={formateur(format)} />;
}

export function BarListIle({
  format,
  ...props
}: Omit<BarListProps, "formatValeur"> & { format?: FormatValeur }) {
  return <BarList {...props} formatValeur={formateur(format)} />;
}

export function DonutIle({
  format,
  ...props
}: Omit<DonutProps, "formatValeur"> & { format?: FormatValeur }) {
  return <Donut {...props} formatValeur={formateur(format)} />;
}

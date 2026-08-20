import { geoConicConformal } from "d3-geo";
import type { GeoProjection } from "d3-geo";

/**
 * Paramètres UNIQUES de la carte de France des départements — partagés par
 * le générateur du fragment (build) et par `MapFrance` (navigateur).
 *
 * Pourquoi ce module existe : les tracés SVG des 96 départements sont
 * désormais PROJETÉS AU BUILD (route /data/carte-departements.json) et non
 * plus dans le navigateur. Deux endroits calculent donc la même projection à
 * des moments différents ; ils doivent partager la même définition, sinon
 * les points « villes lumineuses » (projetés, eux, à l'affichage) se
 * décaleraient des contours.
 *
 * Projection : conique conforme France métropolitaine (paramètres
 * Lambert-93 : parallèles 44°/49°, méridien 3°E, latitude 46,5°N).
 *
 * Le cadrage (`fitExtent`) se résume à un couple échelle + translation :
 * le fragment les transporte, et `projectionFrance()` les rejoue à
 * l'identique sans avoir besoin du GeoJSON. C'est ce qui permet de ne plus
 * envoyer les 692 Ko de contours au navigateur.
 */

/** Repère de référence des tracés précalculés (viewBox du SVG). */
export const LARGEUR_CARTE = 520;
export const HAUTEUR_CARTE = 500;
/** Marge intérieure du cadrage, en unités du viewBox. */
export const MARGE_CARTE = 8;

/** Un département : son code INSEE, son nom, son tracé SVG déjà projeté. */
export type TraceDepartement = {
  code: string;
  nom: string;
  /** Attribut `d` d'un <path>, exprimé dans le repère LARGEUR × HAUTEUR. */
  d: string;
};

/** Fragment statique /data/carte-departements.json. */
export type CarteFrancePrecalculee = {
  largeur: number;
  hauteur: number;
  /** Échelle et translation issues du `fitExtent` fait au build. */
  echelle: number;
  translation: [number, number];
  /** Métropole + Corse uniquement (voir la note outre-mer de MapFrance). */
  departements: TraceDepartement[];
};

/**
 * Projection prête à l'emploi pour les coordonnées ponctuelles (lon, lat)
 * — les « villes lumineuses » de l'accueil. Rejoue exactement le cadrage
 * calculé au build à partir de l'échelle et de la translation transportées
 * par le fragment.
 */
export function projectionFrance(
  echelle: number,
  translation: [number, number],
): GeoProjection {
  return geoConicConformal()
    .parallels([44, 49])
    .rotate([-3, 0])
    .center([0, 46.5])
    .scale(echelle)
    .translate(translation);
}

/**
 * Même projection, cadrée sur un GeoJSON — utilisée UNIQUEMENT au build par
 * la route qui fabrique le fragment. `fitExtent` ne fait que fixer l'échelle
 * et la translation de la projection ci-dessus.
 */
export function projectionCadree(
  geojson: Parameters<GeoProjection["fitExtent"]>[1],
): GeoProjection {
  return geoConicConformal()
    .parallels([44, 49])
    .rotate([-3, 0])
    .center([0, 46.5])
    .fitExtent(
      [
        [MARGE_CARTE, MARGE_CARTE],
        [LARGEUR_CARTE - MARGE_CARTE, HAUTEUR_CARTE - MARGE_CARTE],
      ],
      geojson,
    );
}

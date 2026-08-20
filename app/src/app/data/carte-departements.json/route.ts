import fs from "node:fs";
import { geoPath, type GeoContext } from "d3-geo";
import {
  HAUTEUR_CARTE,
  LARGEUR_CARTE,
  projectionCadree,
  type CarteFrancePrecalculee,
  type TraceDepartement,
} from "@/components/ui/projection-france";
import {
  GEOJSON_DEPARTEMENTS_PATH,
  type GeojsonDepartements,
} from "@/lib/queries/collectivites";

/**
 * Fond de carte des départements DÉJÀ PROJETÉ, servi en fragment statique.
 *
 * Avant : le navigateur téléchargeait les 692 Ko de contours GeoJSON du
 * référentiel S27, les parsait, puis rejouait pour chaque carte le cadrage
 * `fitExtent` et la génération des tracés sur 21 055 points — un travail
 * strictement identique à chaque visite, pour un résultat qui ne dépend que
 * du fichier source et du repère de rendu, tous deux connus au build.
 *
 * Après : ce calcul est fait UNE FOIS ici, à la construction du site, et le
 * navigateur ne reçoit plus que les 96 attributs `d` du <path>. Le site
 * étant entièrement pré-rendu, c'est la place naturelle de ce calcul.
 *
 * Précision : coordonnées arrondies au dixième d'unité du viewBox (520 ×
 * 500). La carte est affichée au plus sur quelques centaines de pixels de
 * large : un dixième d'unité y vaut moins d'un huitième de pixel, aucun
 * contour n'est déplacé de façon perceptible, et l'arrondi retire à lui seul
 * un quart du poids des tracés.
 *
 * OUTRE-MER : écarté ici comme il l'était au rendu (codes « 97… »), pour la
 * même raison — le cadrage écraserait la métropole. Les valeurs
 * correspondantes restent dans les tableaux des pages.
 *
 * `null` si le référentiel n'est pas ingéré : le composant carte affiche
 * alors le même message honnête qu'avant (tableaux complets).
 */
export const dynamic = "force-static";

/** Décimales conservées sur les coordonnées du viewBox. */
const DECIMALES = 1;

/**
 * Contexte de rendu `d3-geo` qui écrit directement un attribut `d` arrondi.
 * Sans contexte, `geoPath` sort les coordonnées en pleine précision
 * flottante (jusqu'à 15 chiffres par nombre) ; ici chaque point coûte deux
 * nombres à une décimale.
 *
 * `beginPath()` fait partie de l'interface `GeoContext` mais `d3-geo` ne
 * l'appelle jamais sur des polygones : c'est la boucle ci-dessous qui le
 * fait, entre deux départements, pour repartir d'un tracé vide.
 */
class ContexteArrondi implements GeoContext {
  private d = "";
  beginPath() {
    this.d = "";
  }
  moveTo(x: number, y: number) {
    this.d += `M${x.toFixed(DECIMALES)},${y.toFixed(DECIMALES)}`;
  }
  lineTo(x: number, y: number) {
    this.d += `L${x.toFixed(DECIMALES)},${y.toFixed(DECIMALES)}`;
  }
  closePath() {
    this.d += "Z";
  }
  /** Jamais appelé sur des polygones ; exigé par l'interface GeoContext. */
  arc() {}
  /** Tracé de la dernière feature dessinée. */
  trace() {
    return this.d;
  }
}

export async function GET() {
  if (!fs.existsSync(GEOJSON_DEPARTEMENTS_PATH)) {
    return Response.json(null);
  }
  let geojson: GeojsonDepartements;
  try {
    geojson = JSON.parse(
      fs.readFileSync(GEOJSON_DEPARTEMENTS_PATH, "utf-8"),
    ) as GeojsonDepartements;
  } catch {
    return Response.json(null);
  }

  const metropole = {
    type: "FeatureCollection" as const,
    features: geojson.features.filter(
      (f) => !(f.properties?.code ?? "").startsWith("97"),
    ),
  };
  if (metropole.features.length === 0) return Response.json(null);

  const projection = projectionCadree(metropole);
  const contexte = new ContexteArrondi();
  const tracer = geoPath(projection, contexte);

  const departements: TraceDepartement[] = [];
  for (const f of metropole.features) {
    contexte.beginPath();
    tracer(f);
    const d = contexte.trace();
    const code = f.properties?.code ?? "";
    if (!d || !code) continue;
    departements.push({ code, nom: f.properties?.nom ?? code, d });
  }

  const translation = projection.translate();
  const fragment: CarteFrancePrecalculee = {
    largeur: LARGEUR_CARTE,
    hauteur: HAUTEUR_CARTE,
    echelle: projection.scale(),
    translation: [translation[0], translation[1]],
    departements,
  };
  return Response.json(fragment);
}

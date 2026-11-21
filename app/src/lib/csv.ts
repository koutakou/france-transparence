/**
 * Écriture des exports CSV statiques (/api/*.csv) et de leur fichier de
 * provenance (/api/*.provenance.txt). Module pur, testé par
 * tests/csv.test.mjs.
 *
 * Format, choisi pour le tableur français (Excel, LibreOffice en locale fr) :
 * - séparateur `;` : la virgule y est le séparateur décimal ;
 * - UTF-8 avec BOM : sans lui, Excel lit le fichier en Windows-1252 et
 *   casse tous les accents ;
 * - guillemets RFC 4180 : un champ qui contient `;`, `"`, un retour chariot
 *   ou un saut de ligne est entouré de guillemets, ses guillemets doublés ;
 *   lignes terminées par CRLF ;
 * - nombres écrits sans espace insécable ni séparateur de milliers, virgule
 *   décimale (`1234567,5`) : le tableur les reconnaît comme des nombres ;
 * - un texte qui commence par `=`, `+`, `-`, `@`, une tabulation ou un retour
 *   chariot est préfixé d'une apostrophe, pour qu'aucun tableur ne
 *   l'exécute comme une formule (injection de formule). Seuls des textes
 *   sont touchés, jamais un nombre.
 *
 * La provenance (source, licence, date des données, URL amont) n'est PAS
 * écrite en tête du CSV : un tableur ou une bibliothèque d'import lit la
 * première ligne comme les noms de colonnes, et des lignes de commentaire
 * placées avant décaleraient tout l'import. Elle va dans un fichier texte
 * publié à côté, sous le même nom (`elus.csv` et `elus.provenance.txt`).
 */

export const SEPARATEUR_CSV = ";";
export const BOM = "﻿";
const FIN_DE_LIGNE = "\r\n";

export type CelluleCsv = string | number | boolean | null | undefined;

/** Une colonne d'export : clé (nom de colonne), sens, et lecture de la ligne. */
export type ColonneCsv<T> = {
  cle: string;
  description: string;
  valeur: (ligne: T) => CelluleCsv;
};

/** Nombre au format du tableur français : virgule décimale, aucun séparateur de milliers. */
export function nombreCsv(n: number): string {
  if (!Number.isFinite(n)) return "";
  if (Object.is(n, -0)) return "0";
  let s = String(n);
  // Notation exponentielle (très petits nombres) : un tableur ne la relit pas
  // toujours, on l'écrit en clair.
  if (/e/i.test(s)) {
    s = n.toFixed(12).replace(/0+$/, "").replace(/\.$/, "");
  }
  return s.replace(".", ",");
}

const DEBUT_FORMULE = /^[=+\-@\t\r]/;
const A_PROTEGER = /[;"\r\n]/;

/** Une cellule CSV, protégée selon RFC 4180. `null` et `undefined` donnent un champ vide. */
export function celluleCsv(valeur: CelluleCsv): string {
  if (valeur === null || valeur === undefined) return "";
  if (typeof valeur === "number") return nombreCsv(valeur);
  if (typeof valeur === "boolean") return valeur ? "1" : "0";
  let s = valeur;
  if (DEBUT_FORMULE.test(s)) s = `'${s}`;
  if (A_PROTEGER.test(s)) s = `"${s.replace(/"/g, '""')}"`;
  return s;
}

/** Une ligne CSV, sans fin de ligne. */
export function ligneCsv(cellules: CelluleCsv[]): string {
  return cellules.map(celluleCsv).join(SEPARATEUR_CSV);
}

/** Document CSV complet : BOM, ligne des noms de colonnes, puis une ligne par enregistrement. */
export function documentCsv<T>(colonnes: ColonneCsv<T>[], lignes: T[]): string {
  const sortie = [ligneCsv(colonnes.map((c) => c.cle))];
  for (const l of lignes) sortie.push(ligneCsv(colonnes.map((c) => c.valeur(l))));
  return BOM + sortie.join(FIN_DE_LIGNE) + FIN_DE_LIGNE;
}

/** Ce que le fichier de provenance dit d'une source amont (une ligne de `meta_sources`). */
export type SourceProvenance = {
  source_id: string;
  nom: string;
  url: string;
  licence: string;
  date_donnees: string;
  date_ingestion?: string | null;
  /** Étiquette d'une source qui n'est pas une publication officielle ouverte (S1, S31…). */
  nature?: string | null;
};

export type Provenance = {
  /** Nom du fichier CSV décrit, ex. `elus.csv`. */
  fichier: string;
  titre: string;
  description: string;
  /** Mentions à reprendre en cas de réutilisation (crédit, avertissement). */
  mentions?: string[];
  colonnes: { cle: string; description: string }[];
  sources: SourceProvenance[];
  /** Phrase qui remplace la liste des sources quand le fichier n'en a pas en propre. */
  sansSource?: string;
  /** Adresse publique de la page ou de l'export JSON équivalent. */
  voirAussi?: string[];
};

export const LICENCE_AGREGATS = "Licence Ouverte 2.0 (agrégats France Transparence)";

/** Fichier texte de provenance publié à côté de chaque CSV. */
export function documentProvenance(p: Provenance): string {
  const l: string[] = [];
  l.push(`${p.titre}`);
  l.push(`Fichier décrit : ${p.fichier}`);
  l.push("");
  l.push(p.description);
  if (p.mentions && p.mentions.length > 0) {
    l.push("");
    for (const m of p.mentions) l.push(m);
  }
  l.push("");
  l.push("Sources amont");
  if (p.sources.length === 0) {
    l.push(`  ${p.sansSource ?? "Aucune source amont propre à ce fichier."}`);
  }
  for (const s of p.sources) {
    l.push(`  ${s.source_id} : ${s.nom}`);
    if (s.nature) l.push(`    Nature : ${s.nature}`);
    l.push(`    Licence : ${s.licence}`);
    l.push(`    Date des données : ${s.date_donnees}`);
    if (s.date_ingestion) l.push(`    Date d'ingestion : ${s.date_ingestion}`);
    l.push(`    URL amont : ${s.url}`);
  }
  l.push("");
  l.push(`Licence des agrégats : ${LICENCE_AGREGATS}, avec mention de la source amont de chaque donnée.`);
  l.push("");
  l.push("Colonnes");
  for (const c of p.colonnes) l.push(`  ${c.cle} : ${c.description}`);
  l.push("");
  l.push("Format");
  l.push("  Séparateur point-virgule, encodage UTF-8 avec BOM, fin de ligne CRLF.");
  l.push("  Un champ qui contient le séparateur, des guillemets ou un saut de ligne est entouré de guillemets (RFC 4180).");
  l.push("  Nombres sans séparateur de milliers, virgule décimale. Montants en euros. Champ vide = non renseigné.");
  l.push("  Un texte qui commencerait par =, +, - ou @ est précédé d'une apostrophe (aucune formule exécutée par le tableur).");
  if (p.voirAussi && p.voirAussi.length > 0) {
    l.push("");
    l.push("Voir aussi");
    for (const v of p.voirAussi) l.push(`  ${v}`);
  }
  return BOM + l.join(FIN_DE_LIGNE) + FIN_DE_LIGNE;
}

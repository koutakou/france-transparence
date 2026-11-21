// Signes typographiques bannis des textes publiés (décision du propriétaire du
// 21/11/2026) : tiret cadratin, tiret demi-cadratin, point-virgule, points de
// suspension typographiques. Les guillemets français restent.
//
// Deux lectures, partagées par le test des sources et le contrôle de l'export :
// - textesDuSource : chaînes et textes JSX d'un fichier .ts/.tsx, lus par
//   l'analyseur de TypeScript (les commentaires n'en font pas partie) ;
// - textesDuBalisage : texte et valeurs d'attributs d'un document HTML, XML
//   ou SVG, sans le contenu des balises <script> et <style>.
import ts from "typescript";

/** Un signe banni, n'importe où dans la chaîne. */
export const SIGNES_BANNIS = /[—–;…]/u;

const NOMS = { "—": "tiret cadratin", "–": "tiret demi-cadratin", ";": "point-virgule", "…": "points de suspension" };

/** Noms des signes bannis présents dans `texte`. */
export function signesPresents(texte) {
  return [...new Set([...texte].filter((c) => NOMS[c]).map((c) => NOMS[c]))];
}

/**
 * Chaînes d'un fichier source : littéraux, morceaux de gabarits, texte JSX.
 * Rend [{ texte, ligne }]. Les spécificateurs d'import ne sont pas du texte.
 */
export function textesDuSource(code, fichier = "source.tsx") {
  const genre = fichier.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS;
  const sf = ts.createSourceFile(fichier, code, ts.ScriptTarget.Latest, true, genre);
  const textes = [];
  const garder = (noeud, texte) => {
    const ligne = sf.getLineAndCharacterOfPosition(noeud.getStart(sf)).line + 1;
    textes.push({ texte, ligne });
  };
  const visiter = (noeud) => {
    if (ts.isImportDeclaration(noeud) || ts.isExportDeclaration(noeud)) return;
    if (
      ts.isStringLiteral(noeud) ||
      ts.isNoSubstitutionTemplateLiteral(noeud) ||
      ts.isTemplateHead(noeud) ||
      ts.isTemplateMiddle(noeud) ||
      ts.isTemplateTail(noeud)
    ) {
      // Une chaîne d'attribut JSX garde ses entités (&nbsp;) : on les décode.
      garder(noeud, noeud.parent && ts.isJsxAttribute(noeud.parent) ? decoderEntites(noeud.text) : noeud.text);
    } else if (ts.isJsxText(noeud)) {
      garder(noeud, decoderEntites(noeud.text));
    }
    ts.forEachChild(noeud, visiter);
  };
  visiter(sf);
  return textes;
}

const ENTITES = { amp: "&", lt: "<", gt: ">", quot: '"', apos: "'", nbsp: " ", mdash: "—", ndash: "–", hellip: "…" };

/** Décode les entités HTML usuelles et numériques. */
export function decoderEntites(s) {
  return s.replace(/&(#x[0-9a-f]+|#[0-9]+|[a-z]+);/gi, (m, e) => {
    if (e[0] === "#") {
      const n = e[1] === "x" || e[1] === "X" ? parseInt(e.slice(2), 16) : parseInt(e.slice(1), 10);
      return Number.isFinite(n) ? String.fromCodePoint(n) : m;
    }
    return ENTITES[e.toLowerCase()] ?? m;
  });
}

/**
 * Texte lisible d'un document balisé : nœuds de texte et valeurs d'attributs,
 * entités décodées. Le contenu de <script> et <style>, les commentaires et
 * les sections CDATA de script ne comptent pas. Rend une liste de chaînes.
 */
export function textesDuBalisage(doc) {
  const textes = [];
  const sansCode = doc
    .replace(/<!--[\s\S]*?-->/g, "")
    .replace(/<script\b[^>]*>[\s\S]*?<\/script\s*>/gi, "")
    .replace(/<style\b[^>]*>[\s\S]*?<\/style\s*>/gi, "");
  const balise = /<[^>]*>/g;
  let dernier = 0;
  let m;
  while ((m = balise.exec(sansCode))) {
    const avant = sansCode.slice(dernier, m.index);
    if (avant.trim()) textes.push(decoderEntites(avant));
    dernier = m.index + m[0].length;
    const tag = m[0];
    // Attributs d'une balise ouvrante (pas une déclaration <!...> ni <?...?>).
    if (/^<[a-z]/i.test(tag)) {
      for (const a of tag.matchAll(/\s([^\s=/>]+)\s*=\s*("([^"]*)"|'([^']*)')/g)) {
        const nom = a[1].toLowerCase();
        // `style` est du CSS, `d`/`points`/`transform`/`viewBox` de la géométrie.
        if (nom === "style" || nom === "d" || nom === "points" || nom === "transform" || nom === "viewbox") continue;
        const valeur = decoderEntites(a[3] ?? a[4] ?? "");
        if (valeur.trim()) textes.push(valeur);
      }
    }
  }
  const fin = sansCode.slice(dernier);
  if (fin.trim()) textes.push(decoderEntites(fin));
  return textes;
}

/** Chaînes d'une valeur JSON, clés comprises. */
export function textesDuJson(valeur, out = []) {
  if (typeof valeur === "string") out.push(valeur);
  else if (Array.isArray(valeur)) for (const v of valeur) textesDuJson(v, out);
  else if (valeur && typeof valeur === "object")
    for (const [k, v] of Object.entries(valeur)) {
      out.push(k);
      textesDuJson(v, out);
    }
  return out;
}

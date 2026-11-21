// Lecture des chaînes du code pour le test de typographie des textes publiés
// (tests/typographie.test.mjs). Le contrôle de l'export et les signes bannis
// vivent dans scripts/typographie.mjs.
import ts from "typescript";
import { decoderEntites } from "../../scripts/typographie.mjs";

export { SIGNES_BANNIS, signesPresents, decoderEntites, textesDuBalisage, textesDuJson } from "../../scripts/typographie.mjs";

/**
 * Chaînes d'un fichier source : littéraux, morceaux de gabarits, texte JSX.
 * Rend [{ texte, ligne }]. Les commentaires et les spécificateurs d'import
 * ne sont pas du texte.
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
      // Les entités (&nbsp;, &amp;) sont décodées : leur « ; » ne s'affiche pas.
      garder(noeud, decoderEntites(noeud.text));
    } else if (ts.isJsxText(noeud)) {
      garder(noeud, decoderEntites(noeud.text));
    }
    ts.forEachChild(noeud, visiter);
  };
  visiter(sf);
  return textes;
}

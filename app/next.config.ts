import path from "node:path";
import type { NextConfig } from "next";

/**
 * Deux modes de build (docs/deploiement/DECISION.md) :
 * - classique (`npm run build` + `next start`) : serveur Node local, la CI
 *   de test et le dev continuent de fonctionner sans variable ;
 * - export statique (`FT_EXPORT=1 npm run build`) : la CI GitHub Actions
 *   génère app/out/ et le déploie tel quel sur GitHub Pages.
 *
 * `NEXT_PUBLIC_BASE_PATH` (ex. « /france-transparence » pour la project page
 * https://koutakou.github.io/france-transparence/) préfixe routes et assets ;
 * absent en local → site servi à la racine.
 */
const basePath = process.env.NEXT_PUBLIC_BASE_PATH || undefined;

const nextConfig: NextConfig = {
  output: process.env.FT_EXPORT ? "export" : undefined,
  basePath,
  // Cohérent avec basePath : les assets vivent sous le même préfixe.
  assetPrefix: basePath,
  // Émet /page/index.html : indispensable pour un hébergeur statique qui
  // résout les répertoires (GitHub Pages).
  trailingSlash: true,
  // Pas de serveur d'optimisation d'images en statique.
  images: { unoptimized: true },
  // Ne pas exposer « X-Powered-By: Next.js » (audit-app.md § 2).
  poweredByHeader: false,
  // Module natif : ne jamais le bundler côté serveur.
  serverExternalPackages: ["better-sqlite3"],
  // Racine explicite : un package-lock.json parasite existe dans $HOME,
  // sans ceci Turbopack croit que la racine du projet est /Users/<user>.
  turbopack: {
    root: path.join(__dirname),
  },
};

export default nextConfig;

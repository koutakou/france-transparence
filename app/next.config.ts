import path from "node:path";
import type { NextConfig } from "next";

/**
 * Deux modes de build (docs/deploiement/DECISION.md) :
 * - classique (`npm run build` + `next start`) : serveur Node local, la CI
 *   de test et le dev continuent de fonctionner sans variable ;
 * - export statique (`FT_EXPORT=1 npm run build`) : génère app/out/, servi
 *   tel quel par nginx sur le serveur de production. Aucun process Node ne
 *   tourne en production. La CI construit le même export pour le VALIDER,
 *   mais ne le publie pas.
 *
 * Deux variables décrivent l'ADRESSE de déploiement, et rien d'autre — elles
 * évitent d'avoir à réécrire les sources pour changer de domaine :
 * - `NEXT_PUBLIC_SITE_URL` (voir src/lib/site.ts) : URL absolue du site,
 *   d'où sont dérivés canoniques, sitemap et robots.txt ;
 * - `NEXT_PUBLIC_BASE_PATH` : sous-chemin éventuel (ex. « /france-transparence »
 *   pour une « project page » GitHub Pages), qui préfixe routes et assets.
 *   Absent — c'est le cas du déploiement de référence, à la racine de
 *   francetransparence.fr — le site est servi à la racine.
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

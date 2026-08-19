import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Module natif : ne jamais le bundler côté serveur.
  serverExternalPackages: ["better-sqlite3"],
  // Racine explicite : un package-lock.json parasite existe dans $HOME,
  // sans ceci Turbopack croit que la racine du projet est /Users/<user>.
  turbopack: {
    root: path.join(__dirname),
  },
};

export default nextConfig;

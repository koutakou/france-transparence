import type { MetadataRoute } from "next";
import { SITE_URL } from "@/lib/site";

// Exigé par `output: "export"` (route metadata générée au build).
export const dynamic = "force-static";

/**
 * /robots.txt — route de métadonnées Next.js.
 *
 * Remplace l'ancien app/public/robots.txt, qui était un fichier statique
 * portant l'URL du sitemap EN DUR : à chaque changement de domaine, il fallait
 * réécrire ce fichier, et rien ne garantissait qu'il reste d'accord avec
 * SITE_URL (donc avec les canoniques et le sitemap réellement générés). En le
 * générant, l'adresse du sitemap ne peut plus diverger du reste du site : elle
 * en est dérivée.
 *
 * Fonctionne en export statique (`output: "export"`) : Next écrit le fichier
 * dans out/robots.txt au build. Le contrôle de santé de la CI le vérifie.
 */
export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
    },
    sitemap: `${SITE_URL}/sitemap.xml`,
  };
}

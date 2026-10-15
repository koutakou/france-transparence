import { CONTACT_EMAIL, REPO_URL, SITE_URL } from "@/lib/site";

/**
 * /.well-known/security.txt (RFC 9116) — généré au build, versionné ici.
 *
 * POURQUOI ICI. Jusqu'au 15/10/2026, le fichier servi vivait sur le serveur,
 * hors du dépôt, posé à la main le 19/08/2026. Il dirigeait les rapports de
 * vulnérabilité vers les ISSUES PUBLIQUES du dépôt, à l'inverse de
 * SECURITY.md (« En privé, uniquement. … N'ouvrez ni issue… ») : un
 * chercheur qui suivait le fichier standard publiait la faille. Ce qui est
 * publié doit être ce qui est versionné ; le fichier se déduit désormais des
 * mêmes constantes que le reste du site.
 *
 * - `Contact` : d'abord l'adresse privée de SECURITY.md (CONTACT_EMAIL, qui
 *   est aussi celle des pages légales), puis le signalement privé GitHub,
 *   activé sur le dépôt. JAMAIS les issues.
 * - `Expires` : calculé au build (obligatoire, et la RFC le veut à moins
 *   d'un an). Le site étant reconstruit chaque jour, il reste toujours à
 *   environ six mois ; un site qui cesserait d'être reconstruit laisserait
 *   le fichier expirer, ce qui est exactement le signal voulu.
 */
export const dynamic = "force-static";

/** Durée de validité annoncée, comptée depuis le build. */
const VALIDITE_JOURS = 180;

export function GET() {
  const expire = new Date(Date.now() + VALIDITE_JOURS * 24 * 3600 * 1000);
  // Seconde près : un horodatage ISO 8601 sans millisecondes (forme de la RFC).
  const expires = expire.toISOString().replace(/\.\d{3}Z$/, "Z");
  const lignes = [
    `# Signalement de vulnérabilité — ${new URL(SITE_URL).host}`,
    "# En privé uniquement : n'ouvrez pas d'issue publique pour une vulnérabilité.",
    `Contact: mailto:${CONTACT_EMAIL}`,
    `Contact: ${REPO_URL}/security/advisories/new`,
    `Expires: ${expires}`,
    "Preferred-Languages: fr, en",
    `Canonical: ${SITE_URL}/.well-known/security.txt`,
    `Policy: ${REPO_URL}/blob/main/SECURITY.md`,
    "",
  ];
  return new Response(lignes.join("\n"), {
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
}

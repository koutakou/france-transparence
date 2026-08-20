/**
 * Bloc de données structurées schema.org (JSON-LD).
 *
 * Rendu côté serveur uniquement (aucun "use client") : le balisage doit être
 * présent dans le HTML exporté, pas injecté après hydratation — un
 * consommateur qui n'exécute pas le JavaScript (Google Dataset Search,
 * validateurs, aperçus sociaux) ne verrait rien sinon.
 *
 * ÉCHAPPEMENT — les valeurs balisées viennent de la base (noms d'élus,
 * libellés de sources) : ce sont des données NON FIABLES (DATAVIZ §5).
 * `JSON.stringify` ne protège pas d'un « </script> » présent dans une
 * chaîne, qui refermerait l'élément et permettrait une injection. Toute
 * occurrence de « < » est donc réécrite en « < » : échappement JSON
 * standard, transparent pour un analyseur JSON, inoffensif pour l'analyseur
 * HTML.
 *
 * CSP — la politique du site autorise `script-src 'self' 'unsafe-inline'` :
 * ce bloc passe. Il n'est de toute façon pas exécutable (type
 * `application/ld+json`, ignoré par le moteur JavaScript).
 */
export function serialiseJsonLd(donnees: unknown): string {
  return JSON.stringify(donnees).replace(/</g, "\\u003c");
}

export function JsonLd({ donnees }: { donnees: unknown }) {
  return (
    <script
      type="application/ld+json"
      // Sérialisation maîtrisée ci-dessus : « < » est neutralisé, la chaîne
      // ne peut donc pas refermer l'élément <script>.
      dangerouslySetInnerHTML={{ __html: serialiseJsonLd(donnees) }}
    />
  );
}

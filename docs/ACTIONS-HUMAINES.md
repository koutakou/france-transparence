# ACTIONS HUMAINES — ce qui exige physiquement Mickael

La mission de déploiement a été menée sans action humaine (GitHub Pages, 0 €). Les actions ci-dessous sont **optionnelles** : elles améliorent le service mais rien n'est bloqué sans elles.

## 1. Domaine personnalisé (recommandé, ~7-12 €/an)

`koutakou.fr` a **expiré** et est de nouveau libre (vérifié AFNIC 19/08/2026 : NOT FOUND). Options : le reprendre, ou prendre un nom dédié (ex. `france-transparence.fr`, disponibilité à vérifier au moment de l'achat).

1. Acheter chez un registrar (OVH, Gandi, BookMyName…), CB requise.
2. Poser les DNS : `CNAME www → koutakou.github.io.` et à l'apex 4 enregistrements `A → 185.199.108.153 / 185.199.109.153 / 185.199.110.153 / 185.199.111.153` (+ AAAA `2606:50c0:8000..8003::153` si souhaité).
3. Dans le repo GitHub `koutakou/france-transparence` : Settings → Pages → Custom domain → saisir le domaine, cocher « Enforce HTTPS » (certificat automatique en ~1 h).
4. Me le signaler : je poserai le fichier `CNAME`, ajusterai `basePath`/`metadataBase`/sitemap et les mentions légales.

## 2. Adresse e-mail de contact dédiée (recommandé)

Les pages /mentions-legales et /donnees-personnelles offrent aujourd'hui les issues GitHub comme canal d'exercice des droits (RGPD). Une adresse e-mail dédiée est préférable (pas de compte GitHub requis pour écrire) :
- soit un alias du domaine acheté en 1 (ex. `contact@…`),
- soit une boîte gratuite dédiée (ne pas exposer l'adresse personnelle).
Me la communiquer : je l'ajouterai aux deux pages.

## 3. VPS OVH existant : à vérifier au manager (peut-être de l'argent dépensé pour rien)

`~/.ssh/config` référence un VPS OVH `51.83.96.83:24533` (ancien koutakou.fr, reverse `ns3147856.ip-51-83-96.eu`). Au 19/08/2026 : **ping OK mais tous ports fermés** (24533, 22, 80, 443) — serveur pare-feuté, réinstallé ou réattribué. À vérifier sur https://www.ovh.com/manager/ : s'il est encore facturé sans servir, le résilier ; s'il est récupérable, il peut accueillir la version serveur (voir 4).

## 4. Montée en gamme serveur (optionnelle, si le trafic dépasse GitHub Pages)

Si la bande passante Pages (~100 Go/mois, souple) devient limitante ou pour retrouver une recherche server-side :
- **Hetzner Cloud CX33** : 8,49 €/mois HT + ~0,50 € IPv4 (4 vCPU/8 Go/80 Go NVMe, Falkenstein). Création de compte + CB sur https://accounts.hetzner.com/signUp, vérification d'identité possible. Ensuite 100 % scriptable (`hcloud` + cloud-init) — je peux tout provisionner.
- Alternative souveraineté FR : **OVHcloud VPS-2** 7,21 € HT/mois (engagement 12 mois), commande manuelle au panier.
- L'architecture cible (systemd + bascule atomique de db + Caddy) est décrite dans docs/deploiement/plateformes.md §4 ; me signaler le compte créé et je fais le reste.

# freebox-cli (`fbx`)

Surveillance et diagnostic d'une **Freebox** en ligne de commande : état de la
connexion, **étape de démarrage bloquante** (étape 2, 3, 6…), historique des
coupures, journal de connexion de la box, températures, ports, Wi-Fi, et
notifications push émises par la box elle-même.

> **Outil non officiel**, sans lien avec Free ni Iliad. « Freebox » est une
> marque de Free SAS, citée uniquement pour décrire la compatibilité.

*English summary: unofficial CLI to monitor a Freebox (French ISP Free): connection
state, failing boot step, outage history from the box's RRD stats, internal
connection log, temperatures, switch ports, Wi-Fi clients and push
notifications. Output is in French.*

Testé sur Freebox Ultra (API v16). Les autres modèles exposant l'API Freebox OS
(v8+) devraient fonctionner, sans garantie.

## Installation

Arch Linux (AUR) :

```sh
yay -S freebox-cli        # ou paru, ou makepkg -si
```

Ailleurs : Python ≥ 3.10 avec `requests`, `rich` et `websocket-client`, puis
copier `fbx` dans le `PATH`.

## Premier lancement

```sh
fbx auth
```

Une demande d'autorisation s'affiche sur l'écran de la Freebox : il faut la
valider **sur la box**. Le jeton est enregistré dans
`~/.config/fbx/token.json` (droits 600).

Par défaut l'application n'a pas le droit « Modification des réglages ». Il
n'est nécessaire que pour `fbx notify register` : à accorder dans Freebox OS →
Paramètres de la Freebox → Gestion des accès → Applications → « fbx CLI ».

## Commandes

| Commande | Rôle |
|---|---|
| `fbx status` | État complet : système, étape de démarrage, WAN, fibre (puissance optique), diagnostic |
| `fbx logs [--save]` | Journal de connexion interne de la box (effacé à chaque redémarrage de la box) |
| `fbx upnp` | État WAN via UPnP IGD, **sans authentification** |
| `fbx history [-H 24]` | Coupures détectées dans l'historique de débit de la box |
| `fbx report [-H 48] [-o fichier.md]` | Rapport Markdown des coupures (utile pour une réclamation) |
| `fbx temp [-H 24]` | Températures CPU et ventilateur |
| `fbx traffic [-H 24]` | Débits Internet et par port du switch, volume transféré |
| `fbx ports` | Ports Ethernet / SFP : lien, vitesse, erreurs, appareils vus |
| `fbx wifi` | Points d'accès et clients Wi-Fi (signal, débit PHY) |
| `fbx lan [-a]` | Appareils connus du réseau local |
| `fbx watch [--headless] [--notify]` | Tableau de bord temps réel + journal local des changements |
| `fbx events` | Évènements temps réel (WebSocket) : appareils LAN, VM, stockage |
| `fbx notify serve\|register\|unregister\|list` | Notifications push émises par la box |
| `fbx service install\|uninstall\|status` | Services systemd utilisateur (`fbx-watch`, `fbx-notify`) |
| `fbx log [-n 50] [--box] [--kind K]` | Journal local (`~/.local/state/fbx/events.jsonl`) |
| `fbx get <chemin>` | Appel brut à l'API (ex. `fbx get connection/ftth/`) |

### Étape de démarrage

`fbx status` et `fbx watch` déduisent l'étape où la box est bloquée, d'après
[les étapes officielles](https://assistance.free.fr/articles/311) :

| Étape | Situation | Responsable probable |
|---|---|---|
| 2 | Aucune lumière reçue | Fibre, point de mutualisation, NRO |
| 3 | Lumière reçue, enregistrement PON impossible | Équipement fibre Free (OLT) |
| 6 | Lien OK, authentification de la box refusée | Serveurs d'authentification Free |
| 7 | Authentifiée, WAN pas encore monté | Configuration WAN |
| 8 | Opérationnelle | — |

L'API locale reste joignable pendant une coupure Internet : `fbx watch` enregistre
l'heure exacte de chaque changement d'étape.

### Surveillance permanente

```sh
fbx service install           # active fbx-watch et fbx-notify (systemd --user)
loginctl enable-linger $USER  # pour qu'ils tournent sans session ouverte
fbx notify register           # la box envoie ses notifications à fbx-notify
```

`fbx notify serve` écoute sur le port 47800 (`FBX_NOTIF_PORT`) et n'accepte que
les requêtes venant de la box (option `--allow-any` pour désactiver ce filtre).

## Configuration

| Variable | Défaut | Rôle |
|---|---|---|
| `FBX_URL` | `http://mafreebox.freebox.fr` | Adresse de l'API |
| `FBX_UPNP_PORT` | `5678` | Port UPnP de repli (découverte SSDP sinon) |
| `FBX_NOTIF_PORT` | `47800` | Port du récepteur de notifications |

## Endpoints utilisés

En plus de l'[API documentée](http://mafreebox.freebox.fr/doc/index.html),
`fbx` utilise des endpoints non documentés de l'interface Freebox OS
(`connection/logs/`, `connection/full/`, `update/`) : ils peuvent changer sans
préavis lors d'une mise à jour de la box.

## Tests

```sh
python -m pytest tests
```

## Licence

Copyright (C) 2026 Philippe Pignatel

Ce programme est un logiciel libre distribué sous la **GNU General Public
License version 2 uniquement** (GPL-2.0-only) — voir [LICENSE](LICENSE).
Toute version modifiée et redistribuée doit l'être sous la même licence, avec
son code source.

**English** | [Français](README.fr.md)

# freebox-cli (`fbx`)

Command-line monitoring and diagnostics for a **Freebox** (the router of the
French ISP Free): connection state, **failing boot step** (step 2, 3, 6…),
outage history, the box's internal connection log, temperatures, ports, Wi-Fi,
and push notifications sent by the box itself.

> **Unofficial tool**, not affiliated with Free or Iliad. "Freebox" is a
> trademark of Free SAS, used only to describe compatibility.

The program's output is in French.

Tested on Freebox Ultra (API v16). Other models exposing the Freebox OS API
(v8+) should work, without guarantee.

## Installation

Requirements: Python ≥ 3.10 with `requests`, `rich` and `websocket-client`.
`libnotify` (`notify-send`) is optional, for desktop notifications.

### Arch Linux

The `freebox-cli` AUR package is ready but **not published yet**: new account
registration on the AUR is temporarily closed. In the meantime, install
manually:

```sh
sudo pacman -S --needed python-requests python-rich python-websocket-client
git clone https://github.com/XairRrR/freebox-cli.git
cd freebox-cli
sudo install -Dm755 fbx /usr/bin/fbx
sudo install -Dm644 systemd/fbx-watch.service systemd/fbx-notify.service -t /usr/lib/systemd/user/
```

Uninstall:

```sh
sudo rm /usr/bin/fbx /usr/lib/systemd/user/fbx-watch.service /usr/lib/systemd/user/fbx-notify.service
```

### Other distributions

```sh
# Debian / Ubuntu
sudo apt install python3-requests python3-rich python3-websocket
# Fedora
sudo dnf install python3-requests python3-rich python3-websocket-client

git clone https://github.com/XairRrR/freebox-cli.git
install -Dm755 freebox-cli/fbx ~/.local/bin/fbx
```

If the `systemd/` files are not installed, `fbx service install` creates the
services itself in `~/.config/systemd/user/`.

## First run

```sh
fbx auth
```

An authorization request appears on the Freebox front screen: you must accept
it **on the box itself**. The token is stored in `~/.config/fbx/token.json`
(mode 600).

By default the app does not get the "Modification des réglages" (settings)
permission. It is only needed for `fbx notify register`: grant it in Freebox OS
→ Paramètres de la Freebox → Gestion des accès → Applications → "fbx CLI".

## Commands

| Command | Purpose |
|---|---|
| `fbx status` | Full state: system, boot step, WAN, fiber (optical power), diagnosis |
| `fbx logs [--save]` | The box's internal connection log (cleared every time the box reboots) |
| `fbx upnp` | WAN state over UPnP IGD, **no authentication required** |
| `fbx history [-H 24]` | Outages detected in the box's bandwidth history |
| `fbx report [-H 48] [-o file.md]` | Markdown outage report (useful for a complaint to the ISP) |
| `fbx temp [-H 24]` | CPU temperatures and fan speed |
| `fbx traffic [-H 24]` | Internet and per-switch-port throughput, transferred volume |
| `fbx ports` | Ethernet / SFP ports: link, speed, errors, devices seen |
| `fbx wifi` | Wi-Fi access points and clients (signal, PHY rate) |
| `fbx lan [-a]` | Devices known on the local network |
| `fbx watch [--headless] [--notify]` | Live dashboard + local log of state changes |
| `fbx events` | Real-time events (WebSocket): LAN devices, VMs, storage |
| `fbx notify serve\|register\|unregister\|list` | Push notifications sent by the box |
| `fbx service install\|uninstall\|status` | systemd user services (`fbx-watch`, `fbx-notify`) |
| `fbx log [-n 50] [--box] [--kind K]` | Local log (`~/.local/state/fbx/events.jsonl`) |
| `fbx get <path>` | Raw API call (e.g. `fbx get connection/ftth/`) |

### Boot step

`fbx status` and `fbx watch` infer the step at which the box is stuck, based on
[Free's official boot steps](https://assistance.free.fr/articles/311) (French):

| Step | Situation | Likely cause |
|---|---|---|
| 2 | No light received | Fiber, street cabinet (PM), central office (NRO) |
| 3 | Light received, PON registration failing | Free's fiber equipment (OLT) |
| 6 | Link OK, box authentication refused | Free's authentication servers |
| 7 | Authenticated, WAN not up yet | WAN configuration |
| 8 | Operational | — |

The local API stays reachable during an Internet outage: `fbx watch` records
the exact time of every step change.

### Continuous monitoring

```sh
fbx service install           # enables fbx-watch and fbx-notify (systemd --user)
loginctl enable-linger $USER  # keeps them running without an open session
fbx notify register           # the box sends its notifications to fbx-notify
```

`fbx notify serve` listens on port 47800 (`FBX_NOTIF_PORT`) and only accepts
requests coming from the box (use `--allow-any` to disable this filter).

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `FBX_URL` | `http://mafreebox.freebox.fr` | API address |
| `FBX_UPNP_PORT` | `5678` | Fallback UPnP port (SSDP discovery otherwise) |
| `FBX_NOTIF_PORT` | `47800` | Notification receiver port |

## Endpoints used

In addition to the [documented API](http://mafreebox.freebox.fr/doc/index.html)
(reachable from the box's local network only), `fbx` uses undocumented
endpoints of the Freebox OS web interface (`connection/logs/`,
`connection/full/`, `update/`): they may change without notice after a box
firmware update.

## Tests

```sh
python -m pytest tests
```

## License

Copyright (C) 2026 Philippe Pignatel

This program is free software distributed under the **GNU General Public
License version 2 only** (GPL-2.0-only) — see [LICENSE](LICENSE). Any modified
version that is redistributed must be released under the same license, with
its source code.

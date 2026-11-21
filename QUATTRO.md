# Omarchy Quattro essentials for Kasm

> **Historical guide:** this page records the earlier KasmVNC/WayVNC essentials
> implementation. For the current full-desktop Selkies image, start with
> [Getting started](GETTING-STARTED.md). Its current image ID and test results are
> in [FULL-KASM.md](FULL-KASM.md).

## Downstream maintenance policy

Keep upstream Omarchy packages, configuration, and application launchers
authoritative so releases can be synced with minimal reconciliation. Prefer
packaged hooks and native session interfaces over copied defaults or parallel
implementations. Keep Kasm-specific startup, rendering, streaming, and environment
propagation in the container adapter under `scripts/`. Record any unavoidable
upstream patch explicitly; do not make application-specific flags or vendor
launcher edits part of the normal image setup. Application verification must
check usable rendering, not merely that a process or window exists.

**Selkies/Kasm candidate:** [SELKIES-KASM.md](SELKIES-KASM.md) describes the
separate `4.5.0-selkies-kasm-test` image, supported dashboard controls, and tests.

**Direct-streaming experiment:** [NOVNC-EXPERIMENT.md](NOVNC-EXPERIMENT.md)
records the preserved KasmVNC rollback image and the separate noVNC → WayVNC →
Hyprland prototype, including its test endpoint and verification.

## Current release: Omarchy 4.5.0

The current workspace image installs the official signed `omarchy 4.5.0-3` and `omarchy-settings 4.5.0-3` packages. `4.5.0` is the upstream release; `-3` is the Arch packaging revision. The shipping profile is `kasm-omarchy-quattro:4.5.0-essentials`; `4.5.0` and the existing `quattro-dev` workspace tag alias the same image. VS Code is not installed in this base or introduced through a parent layer. Admin/user addons are documented in [ADDONS.md](ADDONS.md).

`packaging/omarchy-expected-apps.packages` declares the baseline: native terminal/editor/prompts, Chromium, Nautilus, image/PDF/media viewers, clipboard/capture/portal utilities, fonts/themes, and package/support tools. Fresh profiles use Omarchy's supported preinstall opt-out; optional office, productivity, AI, and web-app preinstalls are not seeded. Existing profiles retain their preferences.

The image also includes `ttf-liberation`, Neovim, and the official `omarchy-nvim` package. Liberation Sans is required by Omarchy's fontconfig defaults; without it, the inner viewer's startup shortcut hint fell back to an Arabic font and rendered Latin text as boxes. The font fix was verified in a screenshot of a newly started viewer.

Setup → Input and the text-config actions invoke `omarchy-launch-config-editor`, which defaults to Neovim. Previously the missing editor caused the terminal to exit immediately. The image now seeds missing Neovim config and bundled plugin trees from the official package's `/etc/skel` content via `omarchy-configure-editor`, preserving existing user configuration. Input and Hyprland config editor launches were verified against the actual upstream commands, including visually checking `input.lua` in Neovim. First launch can initialize/update editor plugins and language tools.

Verify inside a new session with `omarchy-version` (expected: `4.5.0-3`) or `pacman -Q omarchy omarchy-settings`. Upstream's packaged `version` text file still contains a development placeholder, so use the supported version command/package metadata instead. The source reference for rebuilding is pinned to tag `v4.5.0`, commit `ac2690cd7be4f47e4a255f5e2e78d904d436b068`.

`scripts/install-omarchy-release.sh` replaces the earlier unowned git checkout with the official packages and uses their normal settings/fonts. It rejects unexpected package versions. Only the two EFI/kernel-maintenance package hooks are masked for the container, which has no boot partition or guest kernel; the official dependencies remain installed. Fresh user profiles are initialized from the release defaults. Existing user profiles are not destructively overwritten.

The labeled-container smoke test `tests/verify-essentials.py` passed native terminal/browser cold-start and URL handoff, Nautilus, Setup editor/prompt actions, image/PDF/media default associations, Wayland clipboard, PulseAudio-on-PipeWire userland, the real file chooser, native screenshot saving, native recording to a playable MP4, screensaver start/exit, native titlebars, resizing, and reload. It also checks that Code and its profile are absent. Physical Mac-side F18 verification remains a separate workstation test.

This host's Kasm agent was observed pruning unused local candidate images. A lightweight, read-only, network-disabled `omarchy-audio-image-cache` container runs only `sleep` to retain the published audio-enabled image until a real workspace uses it; it does not start a desktop or consume a GPU. It can be stopped once image-retention policy is configured appropriately.

The direct-container image is `kasm-omarchy-quattro:quattro-dev`. This uses genuine upstream Omarchy Quattro Hyprland configuration, Quickshell, menu, and Tokyo Night theme. It does not boot an ISO or run a virtual machine.

## Upstream-alignment follow-up

The latest image restores more of Omarchy's normal runtime rather than bypassing its launchers:

- `start-hyprland` runs the compositor watchdog. The earlier missing-launcher warning is gone. The session uses `/run/user/1000` and waits for Hyprland's event socket before launching Quickshell.
- The real user `~/.config/hypr/hyprland.lua` is the configuration entrypoint. The wrapper replaces the systemd/hardware autostart module and adds Kasm display synchronization and host-friendly aliases. Essential upstream bindings remain; optional preinstall bindings follow Omarchy's standard opt-out state.
- Omarchy's signed patched Quickshell package is installed from its official repository; package hash and signature are checked. The official package repository is configured for menu-driven package installation.
- `xdg-terminal-exec`, Gum, the upstream Foot desktop entry/terminal preference, and the normal Bash/Starship configuration are present. Omarchy commands are available in the normal executable path, including login shells.
- The default cursor alias resolves to the installed Adwaita cursor theme at Omarchy's 24-pixel size. Cursor images are forwarded through WayVNC and TigerVNC, instead of baking a cursor into captured frames. The outer streaming cursor was captured and verified at 24×24 pixels.
- Quickshell uses NVIDIA/EGL acceleration instead of the forced software backend. The loopback-only VNC hop uses raw encoding, requests up to 60 FPS, and removes the viewer's 17 ms pointer-event throttle. The browser-facing KasmVNC connection retains its normal compression. These remove avoidable processing; end-to-end latency on the user's workstation has not been benchmarked.

Fresh-session verification included opening a terminal through the upstream launcher, launching an actual floating Omarchy presentation window with the proper `org.omarchy.terminal` app ID, entering a Gum prompt and reading its submitted value, resizing the desktop, and reloading the upstream configuration. Screenshots confirmed the native floating prompt and Starship terminal. This verifies terminal-backed prompts, not every hardware/system-management menu: services such as logind, system NetworkManager, power management, and hardware authentication still require a fuller OS environment.

## Architecture

Browser → KasmVNC/Xvnc → fullscreen TigerVNC viewer → loopback WayVNC → GPU-rendered headless Hyprland + Omarchy Quickshell.

The extra loopback VNC hop bridges Kasm's X11 streaming to Quattro's Wayland desktop. Only Kasm's authenticated HTTPS port is published. WayVNC is unauthenticated but bound only to the container's loopback address.

Aquamarine 0.16.0 normally needs a DRM backend or parent compositor to supply an allocator. `scripts/headless-render-node.cpp` is an experimental, version-specific library interposition that supplies the mapped render node and queries EGL's renderable DMA-BUF modifiers. This is essential for the NVIDIA GPU tested here. It does not acquire DRM master or request host input devices. The build rejects a different Aquamarine version; this is not yet a portable production image.

## Build

Run these sequentially from this directory:

```bash
docker build -t kasm-omarchy-quattro:experimental .
docker build -f Dockerfile.runtime -t kasm-omarchy-quattro:runtime .
docker build -f Dockerfile.headless -t kasm-omarchy-quattro:essentials-core .
docker build -f Dockerfile.titlebars -t kasm-omarchy-quattro:essentials-desktop .
docker build -f Dockerfile.audio -t kasm-omarchy-quattro:4.5.0-essentials .
```

The images are already built locally. `Dockerfile.runtime` pins the canonical `https://github.com/omacom/omarchy.git` `v4.5.0` tag, and `Dockerfile.headless` installs the official pinned 4.5.0 runtime/settings packages. The base builds still use rolling Arch dependencies and are not fully reproducible across future package updates.

The deployed build used the known Code-free `kasm-omarchy-quattro:kasm-base-20261119` prototype runtime as `Dockerfile.headless`'s `BASE_IMAGE` override. The recipe then replaces the old source tree with the official 4.5.0 packages, installs the manifest, performs a coherent Arch dependency update, and rejects an unexpected compositor/Aquamarine ABI. It removes obsolete prototype terminals/Weston. The titlebar stage builds unmodified upstream v0.4.0 (commit `929ed753a667dd7d13688e0c8b2d5c930f1babda`) into `omarchy-hyprland-titlebars 0.4.0-1.1`, pinned to `hyprland=0.57.2`. Compiler-stage additions are not copied into the final titlebar layer.

## Browser audio output

`Dockerfile.audio` adds Kasm's pinned WebSocket audio relay and starts it with the
session's existing PipeWire server. The desktop output is **Kasm Audio Output**
(`kasm_output`); its monitor is encoded as MP2/MPEG-TS and streamed over authenticated
TLS WebSocket port 4901. Kasm proxies this port automatically. No host sound device
mapping is needed. The bridge waits for PipeWire readiness and restarts its relay
and encoder if either exits. Set `KASM_SVC_AUDIO=0` to disable streaming.

The earlier image only started PipeWire and exposed its fallback **Dummy Output**;
its Kasm audio startup functions were stubs and the streaming relay was missing.
The audio layer replaces those stubs. It does not add microphone forwarding.

Enable sound in the Kasm client and ensure the client/tab is unmuted. A new image
requires a fresh Kasm session; reconnecting to an old container does not update it.
For direct Docker access outside Kasm, port 4901 must also be reachable by the
client; publishing only 6901 provides the desktop, not the separate audio stream.

Run the audio smoke test inside a running workspace (it plays a brief test tone):

```bash
docker exec -i CONTAINER python - < tests/verify-audio.py
```

The test verifies the default output, rejection of unauthenticated listeners, an
authenticated WebSocket connection, and non-silent decoded audio from a generated
440 Hz tone. It passed on the live Kasm workspace and a fresh network-isolated GPU
container, including after terminating the encoder to exercise automatic recovery.
The live Kasm client was also observed connecting to the audio relay. Audible
playback at the workstation still requires user confirmation.

Logs: `~/.local/state/omarchy/kasm-logs/audio-relay.log`, `audio-encoder.log`, and
`/tmp/kasm-audio.log`.

## Run on this host

Tested with the Quadro P1000, NVIDIA driver 580.178.04, and `/dev/dri/renderD128`, whose host group is 993.

```bash
docker run -d --name omarchy-quattro \
  --gpus all \
  --device /dev/dri/renderD128 \
  --group-add "$(stat -c %g /dev/dri/renderD128)" \
  --shm-size=1g \
  -p 127.0.0.1:16908:6901 \
  -e VNC_PW='choose-a-password' \
  kasm-omarchy-quattro:quattro-dev
```

Open `https://localhost:16908`, username `kasm_user`, using your chosen password. Expect a self-signed certificate. The running local test container uses password `temporary-test-password` and is bound only to localhost.

For remote access to this localhost-only test, forward the port from your workstation:

```bash
ssh -L 16908:127.0.0.1:16908 nburnet1@YOUR_SERVER
```

Then open `https://localhost:16908` on your workstation.

## Verified interactions

- Hyprland renders a headless output using the NVIDIA GPU and follows Kasm's framebuffer dimensions.
- Omarchy's actual Quickshell draws the bar, theme background, and menu.
- Super+Return opens a native Wayland Foot terminal.
- Super+Space opens the Omarchy menu.
- Ctrl+Shift+Return and Ctrl+Shift+Space provide terminal/menu alternatives without Super/Command (useful alongside AeroSpace).
- Keyboard events injected at the outer Xvnc display traverse the viewer/WayVNC bridge and trigger both shortcuts.
- Kasm HTTPS returns 200 with credentials and 401 without credentials.
- Kasm WebSocket endpoint upgrades successfully to the binary streaming protocol (HTTP 101).
- Screenshots of the outer Xvnc display were inspected; this is the framebuffer Kasm streams. A full interactive browser automation session has not been run.

## Resizing and host-friendly shortcuts

### Remote-only Super key (workstation verification in progress)

For a host-side remap such as Right Command → F18, KasmVNC now maps the incoming F18 keysym (`0xffcf`) to Super_L (`0xffeb`) using `keyboard.remap_keys`. This happens before the inner display bridge, preserving normal Omarchy shortcuts. Mapping the final dynamically allocated keycode would be unreliable: initial workstation testing showed the key reaching the Wayland test window as keycode 230 / NoSymbol, with both press and release delivered.

The server's configured `RemapKeys` value was checked in a fresh test container. The full physical-key workflow still needs workstation confirmation after a new Kasm session, because this server setting cannot be changed live. Test the remapped key held with Space, then release both. The alternate Ctrl-based bindings remain available until that verification is complete.

The current image includes an event-driven resize bridge. In the Kasm browser client's display settings, use its remote-resolution/resize-to-client mode rather than only scaling the existing image. When Kasm resizes the outer framebuffer, `omarchy-sync-display.py` updates Hyprland's `KASM` output at scale 1, and WayVNC forwards the new framebuffer to the viewer. The monitor mode is also saved in the session runtime directory so it survives Hyprland configuration/theme reloads. Startup reads the actual Kasm display size instead of assuming 1280×720.

Verified resize sequence: 1920×1080 → 1280×800 → 1024×768 → 1600×1200. Each time, both Xvnc and Hyprland reported identical dimensions. A subsequent Hyprland configuration reload retained 1600×1200. The bridge blocks on X11 display events; it does not poll on a timer.

| Action | Host-friendly shortcut | Original shortcut |
| --- | --- | --- |
| Open terminal | Ctrl+Shift+Return | Super+Return |
| Toggle Omarchy menu | Ctrl+Shift+Space | Super+Space |

### Default editor and Super-free window controls

The base editor is Neovim with the official Omarchy configuration. Ctrl+Alt+E launches the user's default editor through `omarchy-launch-editor`. VS Code is available as an explicit derived-image addon, not a base package; see [ADDONS.md](ADDONS.md).

On macOS use **Control** for Ctrl and **Option** for Alt:

| Action | Shortcut |
| --- | --- |
| Default editor | Ctrl+Alt+E |
| Terminal | Ctrl+Shift+Return |
| Omarchy menu | Ctrl+Shift+Space |
| Focus adjacent window | Ctrl+Alt+Arrow |
| Workspace 1–10 | Ctrl+Alt+1–9 / 0 |
| Move window to workspace | Ctrl+Alt+Shift+1–9 / 0 |
| Fullscreen | Ctrl+Alt+F |
| Floating/tiling | Ctrl+Alt+T |
| Close focused window | Ctrl+Alt+Q |
| Drag/resize window | Ctrl+Alt+left/right mouse drag |

The aliases keep the essential upstream bindings available. The inner viewer's private shortcut prefix requires all four modifiers (Ctrl+Alt+Shift+Super), so it does not consume move-to-workspace shortcuts. Window management and the default terminal/editor use the same upstream dispatchers. Mac/AeroSpace interception still depends on workstation settings.

These alternatives were injected at the outer streaming display and verified to open Foot and the actual Omarchy menu. Their behavior under your specific macOS/AeroSpace bindings still needs your workstation-side confirmation. Click inside the desktop before using them.

After rebuilding the image, delete/end the old Kasm session and launch a new one; merely reconnecting to an old container does not load the new startup code.

## Kasm Workspaces registration

Use Docker image `kasm-omarchy-quattro:quattro-dev`, select the NVIDIA GPU, and map `/dev/dri/renderD128` with supplementary group 993 on this host. Suggested Docker Run Config Override:

```json
{
  "devices": ["/dev/dri/renderD128:/dev/dri/renderD128:rwm"],
  "group_add": ["993"],
  "shm_size": "1g"
}
```

Allow roughly 4 GB RAM and 2 CPU cores as a starting point. Kasm supplies the session password when it launches the container.

### Kasm dashboard verification — 2026-11-19

The existing **Omarchy** workspace was successfully launched through Kasm using `kasm-omarchy-quattro:quattro-dev`. Its session container had an NVIDIA device request, `/dev/dri/card1` and `/dev/dri/renderD128` mappings, and supplementary groups 44 and 993. Hyprland, Quickshell, WayVNC, and the fullscreen viewer were running. A screenshot of the Kasm-launched session confirmed that the Quattro bar and theme background were rendered, and KasmVNC logged successful browser-client authentication.

GPU allocation is necessary for this image. Allocate one NVIDIA GPU in the workspace settings and ensure the device mappings and permissions are present. The inspected session already had these automatically provided by Kasm, so no extra run-config override was needed for that session.

The initial Kasm verification showed centered borders with the old fixed-size image. The newer image includes the resize bridge described above and generates `en_US.UTF-8` for Kasm-supplied locale settings.

## Current limits

- Requires this NVIDIA-capable rendering path; CPU-only and other GPUs are unverified.
- Systemd-based Omarchy autostart is replaced by a container supervisor. A small `uwsm-app` bridge launches applications directly.
- The expected-app baseline is integration-tested; the full optional Omarchy application collection is not installed. Hardware-management, lock/power, and complete OS upgrades are not equivalent to bare metal.
- PipeWire starts internally; browser audio, uploads, microphone, webcam, printing, and Kasm profile-sync integrations are not implemented by this prototype.
- The desktop follows the browser's remote framebuffer size at scale 1. Browser-side image scaling alone does not request a new remote resolution.

Logs: `/home/kasm-user/.local/state/omarchy/kasm-logs/` inside the container. Earlier failed approaches and the ISO-backed image are separate experiments and are not used by this working path.

## Container compatibility and verification

One small, recorded patch (`packaging/omarchy-4.5.0-container.patch`) lets the native browser launcher start a process directly when no systemd user manager exists; normal URL handoff and focusing remain upstream behavior. Chromium uses its supported per-user flags file for the namespace-policy sandbox exception. No container privilege expansion is required. Native recording uses upstream's `wf-recorder` fallback for the headless output rather than pretending it is a physical KMS display. Pulse compatibility is supervised alongside PipeWire/WirePlumber.

Profiles are seeded from the package-generated `/etc/skel` defaults, including branding and editor data, without overwriting existing files. Root-owned `/dockerstartup/profile.d/*.sh` hooks allow an admin-derived image to add application-specific profile initialization.

To run the UI smoke test in a disposable container (it opens apps, changes layouts, and creates fixture files):

```bash
docker run -d --name omarchy-smoke --label org.omarchy.kasm.test=true \
  --gpus all --device /dev/dri/renderD128 \
  --group-add "$(stat -c %g /dev/dri/renderD128)" --shm-size=1g \
  kasm-omarchy-quattro:4.5.0-essentials
python3 tests/verify-essentials.py omarchy-smoke
docker rm -f omarchy-smoke
```

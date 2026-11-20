# Container verification — 2026-11-19

## Essentials shipping profile — 2026-11-20

Built from the Code-free pre-addon runtime, with official Omarchy 4.5.0 packages and the expected-app manifest. The final smoke suite (`tests/verify-essentials.py`, requiring a disposable labeled container) passed:

- Release identity, no Code binary/package/profile, standard optional-preinstall opt-out, retained F18 server mapping.
- Native terminal/browser cold launch, browser URL handoff, Nautilus, real Setup config editor, and presentation prompt input.
- Default image/PDF/media launches, Wayland clipboard, and PulseAudio-on-PipeWire userland.
- Actual file-chooser portal selection/response and native Omasnap screenshot saving.
- Native screen-record start/stop with a playable MP4 through the supported headless CPU fallback.
- Native screensaver start and exit on keyboard input.
- Floating-workspace titlebars loaded from an ABI-matched package built from upstream v0.4.0.
- Resizing and a clean configuration reload.

Screenshots were inspected for native editor/theme/titlebar rendering. The optional VS Code example is not built into this image. Full browser audio transport, host hardware controls, and other GPU vendors remain unverified/unsupported as previously documented.

## Official Omarchy 4.5.0 release

### Font and Setup editor follow-up

Adding `ttf-liberation` changed `fc-match Helvetica` from Noto Naskh Arabic to Liberation Sans; a new viewer's startup hint was captured and inspected as readable text. Installing `neovim` and `omarchy-nvim`, and seeding their missing per-user config/plugin trees, restored the real Setup → Input (`input.lua`) and Setup → Config → Hyprland (`hyprland.lua`) launch paths. A screenshot confirmed the themed editor displaying the input configuration. Existing editor preferences and user configuration are preserved.

The release image installs the official signed `omarchy` and `omarchy-settings` packages, both `4.5.0-3`. `omarchy-version` reports `4.5.0-3`. This supersedes the earlier git-branch snapshot. Tests in a fresh NVIDIA-enabled container passed native Super+Return terminal launch, the native menu (screenshot inspected), floating presentation terminal/Gum input submission, VS Code launch and editor text input (screenshot inspected), 1920×1080 and 1280×800 resizing, and a clean Hyprland reload retaining the current display mode. KasmVNC still reports `RemapKeys=0xffcf->0xffeb`; physical F18 mapping needs workstation confirmation. The two boot-maintenance hooks are masked for the container, and the final package transaction completed without EFI-partition errors.

## Updated result: core Quattro desktop verified in direct container

The later `kasm-omarchy-quattro:quattro-dev` build resolves the allocator failure with a version-specific render-node shim and bridges the rendered Wayland output into Xvnc using WayVNC and a fullscreen viewer. Hyprland, Quickshell, the Tokyo Night background, the menu, and a native Foot terminal have been rendered and inspected in screenshots of the outer streaming framebuffer. Super+Return and Super+Space were tested via keyboard events at the outer Xvnc display. Authenticated HTTPS returns 200, unauthenticated HTTPS returns 401, and the streaming WebSocket returns HTTP 101. A later Kasm-dashboard launch of the existing Omarchy workspace was also verified: NVIDIA allocation and render-node permissions were present, all desktop components were running, and the streamed framebuffer showed Quattro's bar and theme background. Full interactive browser automation remains untested. See [QUATTRO.md](QUATTRO.md).

## Resize/keyboard follow-up

### VS Code / Super-free controls

The existing Kasm session's Code failure was reproduced: Electron aborted because Docker blocks its sandbox namespace setup. Adding the scoped Code launcher flag allowed a visible native Wayland Code window in that session. The new image also includes Code and uses Omarchy's default-keyring provisioning. A fresh test session passed Code launch and text-entry checks, workspace switching, moving the Code window to workspace 3, fullscreen/floating toggles, close-window, and directional focus. Testing found and fixed an inner-viewer shortcut-prefix conflict with Ctrl+Alt+Shift+number. No Hyprland configuration errors remained. Tests were isolated from the user's active apps.

### Later upstream-alignment verification

Image `2d3001b88266` passed fresh-container checks for `start-hyprland` watchdog startup with no missing-launcher warning, no Hyprland config errors, Omarchy's signed patched Quickshell, the upstream terminal launcher, Bash defaults, a floating presentation terminal with the correct application ID, Gum input submission, resizing, and configuration reload. Quickshell mapped NVIDIA EGL libraries; WayVNC reported raw encoding; XFixes cursor capture showed the native 24×24 cursor. Initial event-socket startup warnings were absent after readiness synchronization. End-to-end workstation latency and all hardware/system dialogs remain unverified.

Image `921f3e8b37fc` (`kasm-omarchy-quattro:quattro-dev`) was tested in a fresh GPU-enabled container. Xvnc and Hyprland matched at 1920×1080, 1280×800, 1024×768, and 1600×1200, and a Hyprland reload retained the last mode with no config errors. Ctrl+Shift+Return opened a new Foot window through the streaming-display bridge; Ctrl+Shift+Space opened the Omarchy menu, confirmed by screenshot. The exact client-side macOS/AeroSpace shortcut behavior is not tested from this server. These tests require a new Kasm session to pick up the rebuilt image.

## Earlier failed result (historical)

The ISO download is stopped. These checks use the already-built container and already-cloned upstream source; no ISO is needed for them.

| Check | Result | Evidence |
| --- | --- | --- |
| KasmVNC process and authenticated HTTPS endpoint | PASS | Xvnc runs and authenticated GET returned HTTP 200 |
| Desktop currently running | Openbox only | Process inspection shows Xvnc and openbox, no Hyprland or Quickshell |
| Hyprland startup with nested Wayland | FAIL | Aquamarine: `Cannot open backend: no allocator available` |
| NVIDIA libraries alone fix nested startup | FAIL | NVIDIA EGL context can initialize, but tested wlroots rendering fails with `EGLImage not supported` |
| Upstream Quickshell configuration parses under Weston Wayland | PARTIAL | `Configuration Loaded`, but layer-shell integration fails and Hyprland global shortcuts are unavailable |
| Omarchy session configuration and services | INCOMPLETE | Upstream source is cloned, not fully installed; command PATH, current theme, D-Bus services, and PipeWire are incomplete |

The Weston shell test used a 12-second timeout. Loading its QML under Weston is not proof of a usable Quattro desktop: Weston does not supply the required Hyprland and layer-shell interfaces in this test.

## Next verification gate

Before claiming success, start Hyprland with a functioning allocator, apply the real Omarchy configuration and runtime environment, start Quickshell, and verify the rendered desktop, launcher, terminal launch, and keyboard input through the browser. HTTP 200 alone does not satisfy this gate.

The ISO/QEMU image is an unverified separate experiment. It is not evidence that the direct-container desktop works.

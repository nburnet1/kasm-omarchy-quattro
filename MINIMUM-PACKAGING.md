# Omarchy 4.5.0 minimum/expected-app packaging investigation

## Implementation status

The expected-app profile is now implemented and tested as `kasm-omarchy-quattro:4.5.0-essentials`. VS Code is excluded, including from the selected parent image; it is available only as an explicit user/admin addon. See [ADDONS.md](ADDONS.md). The profile also uses Omarchy's supported preinstall opt-out on fresh homes.

The 71-package audit grew by one small container dependency, `wf-recorder`, which is the recording command's upstream-supported fallback for a headless output. The titlebar blocker was resolved by building unmodified upstream v0.4.0, pinned to commit `929ed753a667dd7d13688e0c8b2d5c930f1babda`, against the exact installed Hyprland 0.57.2 headers. It is registered as an Arch package with that exact dependency, and its actual load/titlebar rendering passed the native floating-workspace test.

Runtime fixes are explicit: the recorded browser-launch patch handles the lack of a systemd user manager; Pulse compatibility is started; package-generated `/etc/skel` profile data is seeded without clobbering user files; and Arch libraries are upgraded coherently rather than partially. The smoke suite passed browser cold-start/URL handoff, terminal, Setup editor/prompt, Nautilus, image/PDF/media associations, clipboard, native file chooser, screenshot saving, playable recording, screensaver input/exit, titlebars, resizing, and reload. Host hardware/system services remain outside the container contract.

The final Docker-reported uncompressed image size is approximately 6.4 GB on this host. This is not a registry download-size estimate. The original audit findings and estimates below are retained as provenance; their listed implementation gaps are resolved as described above unless explicitly noted as hardware/platform limitations.

## Finding

There is no complete official `omarchy-minimal`, `omarchy-core`, or `omarchy-desktop` metapackage in the configured Arch/Omarchy repositories inspected. The official packages provide useful boundaries, but installing `omarchy` alone does not install every application its menus, bindings, and file associations expect.

- `omarchy` supplies runtime scripts, Quickshell, themes, and migrations, and depends on the compositor, shell, Gum, keyring, PipeWire, settings, and other runtime components.
- `omarchy-settings` supplies user defaults, fonts, desktop entries, system configuration, and support helpers. It is not a dependency-complete desktop app bundle.
- `omarchy-nvim` supplies the expected editor configuration and cached plugins; Neovim itself is separately resolved through its dependency/provider relationship.
- `install/omarchy-base.packages` is the full ISO workstation package set, not a minimum. It includes office, media-creation, development, device-management, networking, and other applications.

The audited image contained the official `omarchy 4.5.0-3`, `omarchy-settings 4.5.0-3`, and `omarchy-nvim` packages. The previous editor/font failures exposed the gap between the runtime package dependency closure and a usable default desktop.

## Upstream's own optional-app boundary

The official FAQ documents **Remove → Preinstalls**. The implementation removes web-app/TUI launchers, opts the user out of default mise tool declarations, sets `~/.local/state/omarchy/preinstalls-removed`, and removes these selected optional applications:

`aether`, `cliamp`, `libreoffice-fresh`, `pinta`, `obsidian`, `moonlight-qt`, `omacut`, `monologue`, `omacalc`, `omawrite`, `hype`, and `signed`.

The standard application bindings explicitly keep terminal, browser, file manager, and editor outside the optional-preinstall block. This is the strongest upstream signal for an expected core app set. A minimal shipping profile should use the supported preinstall opt-out state on fresh profiles, rather than maintaining a private replacement keybinding scheme for absent optional apps. Existing users' preferences must be preserved.

## Proposed shipping contract

The proposed manifest is `packaging/omarchy-expected-apps.packages`. It is an audited candidate, not an upstream-certified mathematical minimum or a tested finished image.

| Feature | Expected packages/examples | Reason |
| --- | --- | --- |
| Desktop/runtime | Official `omarchy` and `omarchy-settings` dependency closure | Upstream shell, configuration, themes, and utilities |
| Terminal and config editing | Foot, `xdg-terminal-exec`, Neovim, `omarchy-nvim`, Gum | Menu prompts and Setup config actions must open reliably |
| Shell/tools | Starship, shell completion, Git, search/navigation tools, tmux, lazygit | Native shell and editor integrations should have their expected tools |
| Browser | Chromium | 4.5.0's upstream HTTP/HTTPS default; one browser is enough for the baseline |
| Files | Nautilus and its Python integration | Essential file-manager bindings and directory MIME default |
| File viewing | imv, Evince, mpv/mpv-mpris | Upstream image, PDF, and audio/video associations |
| Desktop operations | GTK/Hyprland portals, share picker, Omasnap, recorder, clipboard, OWE, `ttfx` | File pickers, screenshots, capture, wallpaper/media, and the actual idle screensaver |
| Fonts/appearance | Upstream Nerd Font, Liberation, Noto/emoji, cursor and icon themes | Avoid broken text/icons while keeping upstream appearance |
| Userland audio | PipeWire/WirePlumber, pulse compatibility, pamixer | Expected userland commands; browser audio integration remains separate |
| Install/support | Mise manager, yay, fastfetch, inxi | On-demand tool/package installation and the native diagnostic workflows |

Mise's manager is included without eagerly downloading language runtimes or AI tools. VS Code is excluded from the base and left to explicit user/admin addons. Full CJK fonts and language input-method packs are locale additions; upstream's full ISO includes them, while this baseline is English-first.

## Current image audit and size estimate

The shipping image already has the terminal/editor/prompt/keyring stack and much of the rendering/shell infrastructure. The proposed missing direct additions are:

```text
chromium nautilus imv evince mpv mpv-mpris
xdg-desktop-portal-gtk hyprland-preview-share-picker
owe omasnap ttfx gpu-screen-recorder pamixer
python-gobject nautilus-python qt6-multimedia
gnome-themes-extra yaru-icon-theme woff2-font-awesome
unzip fastfetch inxi lazygit mise-bin yay
```

A read-only pacman dependency-resolution dry run against the current image succeeded for this list: **133 missing packages including dependencies**, approximately **353.4 MiB downloaded** and **1076.3 MiB unpacked installed footprint**. No packages were installed for this investigation. These are incremental estimates from the current repository metadata; OCI image growth varies with caching, compression, and existing layers.

The full office/productivity bundle, extra browsers/editors, games, VM tooling, all language runtimes, AI agents, and host hardware stacks are not added by this proposed profile. Official runtime dependencies already installed (including boot-related assets) remain; their container-specific boot hooks stay masked.

## Compatibility and runtime gaps to resolve before shipping

1. **Titlebar plugin version mismatch:** the available `omarchy-hyprland-titlebars` package requires `hyprland=0.56.2`; our working image uses `0.57.2`. Adding it caused pacman's dry run to fail. Do not bypass dependency checks or downgrade only that component: choose and test a matching compositor/plugin/Aquamarine stack first. The proposed manifest leaves this dependency visibly blocked.
2. **Systemd-backed launchers:** v4.5.0's `omarchy-launch-browser` falls back to `systemd-run --user` when no running Chromium process accepts a handoff. Our container has a direct-launch `uwsm-app` bridge but no systemd user manager. Installing Chromium alone does not prove the native browser shortcut will work. First-launch and URL handoff need explicit integration checks.
3. **Session services and hardware controls:** installing packages does not create a logind session, a system bus, or usable host Bluetooth/network/power controls. Kasm owns the container network and device access. These capabilities need a separate, explicit container contract.
4. **Audio services:** `pipewire-pulse` is installed in the image, but its daemon is not currently supervised alongside PipeWire/WirePlumber. Native PulseAudio-client behavior and browser audio streaming are separate checks.
5. **Profile initialization:** official packages seed `/etc/skel`; Kasm uses its own profile template. New baseline packages need their relevant user defaults seeded without clobbering user modifications. Merely installing more packages repeats the issue fixed for Neovim.
6. **App sandboxes/portals:** browser and capture launches must be tested under the actual Kasm security/device policy. A resolved package transaction is not a successful desktop test.

## Acceptance checks for a future baseline image

- New session: compositor, bar, menu, theme, and cursor work with no fatal startup errors.
- Terminal and real Setup → Input/Hyprland config editors open; a real presentation prompt accepts input.
- Native browser shortcut cold-starts the browser and opens a URL; file manager and its open-terminal action work.
- Images, a PDF, and a media sample open through the intended default associations.
- Screenshot/save, file-picker portal, clipboard, and screensaver start/exit work.
- Fonts/icons and default editor/plugin initialization work in a fresh Kasm profile.
- Resize and remote-Super behavior remain intact.
- Omitted optional apps do not leave misleading preinstall hotkeys in a fresh minimal profile.

The implementation now uses the manifest and the executable integration checks in `tests/verify-essentials.py`. The blocker list above describes the original audit; the implementation status at the top records the resolutions. Existing user sessions/profiles are not rewritten to remove their own applications or preferences.

## Upstream references

- [4.5.0 package layout](https://github.com/omacom/omarchy/blob/v4.5.0/docs/file-layout.md)
- [Full ISO package list](https://github.com/omacom/omarchy/blob/v4.5.0/install/omarchy-base.packages)
- [Optional preinstall removal](https://github.com/omacom/omarchy/blob/v4.5.0/bin/omarchy-remove-preinstalls)
- [Essential versus optional application bindings](https://github.com/omacom/omarchy/blob/v4.5.0/default/hypr/bindings/applications.lua)
- [Default MIME applications](https://github.com/omacom/omarchy/blob/v4.5.0/default/applications/mimeapps.list)
- [FAQ on removing preinstalled extras](https://github.com/omacom/omarchy/blob/v4.5.0/manual/46-faq.md#how-do-i-get-rid-of-all-the-extra-software)

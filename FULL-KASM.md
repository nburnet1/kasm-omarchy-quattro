# Complete desktop packages on ordinary Kasm

For first-launch instructions, see [Getting started](GETTING-STARTED.md).
This page documents the package profile, image identity, and verification.

Release: **4.5.0-1** — Omarchy 4.5.0, Kasm integration revision 1.

Local source-build tag: `kasm-omarchy-quattro:4.5.0-1`. Build it with
`bash scripts/build.sh`; no prebuilt registry image is published.

Earlier verified runtime image ID:
`sha256:f202810bb0bc21c25108ac9678ba8d4522ca4ed88ab84b6c435f617036359e6f`.

This runtime was tested as `kasm-omarchy-quattro:4.5.0-full-kasm-test`.
Local rebuilds can have different image IDs because of dependency and metadata
changes. The full-desktop Dockerfile includes source/version labels directly.

This derivative adds the complete **162-entry** output of the packaged
`omarchy-pkg-defaults x86` command to the verified local-cursor image. It uses
the existing Kasm profile entrypoint and UID 1000 session supervisor, Selkies
2.2.1 / pixelflux 2.2.3, native Kasm audio, and GPU mappings. Launch it by changing
the image on the existing working workspace and starting a fresh session.

## Build

For the complete local build:

```bash
bash scripts/build.sh
```

With `kasm-omarchy-quattro:4.5.0-selkies-local-cursor-test` available locally:

```bash
bash scripts/build.sh --reuse-parent
```

`FULL_KASM_BASE_IMAGE` and `FULL_KASM_IMAGE` override the parent and result tags.
The tested parent ID is
`sha256:28600ff0ac3e2dd6adf2707685e0219da7a46245bc729253e9cde50e880e6319`.
The parent build chain is documented in [REPRODUCING.md](REPRODUCING.md).

The installer uses the parent's synchronized package databases and installs
only unsatisfied defaults. Requesting every package again would select an
incompatible stable titlebar plugin. The build checks that Hyprland 0.57.2,
Aquamarine 0.16.0, Omarchy 4.5.0-3, and the ABI-matched titlebar plugin retain
their exact installed versions. It verifies the complete default list with
`pacman -T` (including providers such as `neovim` for `nvim`) and the package
database with `pacman -Dk`.

When rolling mirrors retire an exact package version, the installer retrieves
that version and its signature from the Arch package archive. Normal package
signature verification remains enabled. Downloads use a BuildKit cache rather
than adding another package archive to the resulting image.

Inventory files inside the image:

- `/usr/local/share/omarchy-kasm/upstream-defaults.packages`
- `/usr/local/share/omarchy-kasm/installed-packages.txt`

## Profile behavior

Fresh full profiles retain upstream optional-app/tool defaults instead of
creating the essentials profile's `preinstalls-removed` marker and mise opt-out.
Existing home-directory preferences are preserved. An existing essentials home
can therefore retain its earlier opt-outs; use a fresh home to verify defaults.
Mise-managed language/tool downloads remain on-demand upstream behavior.

The added packages include wallpaper thumbnail dependencies (`libvips` and
`ffmpegthumbnailer`), office applications, input methods, sharing tools, and the
remaining upstream desktop defaults. The underlying runtime still supervises
its graphical session directly. Installing packages does not start systemd
services such as Docker Engine, NetworkManager, Bluetooth, or a physical login
manager. Host power, storage, and physical-device actions retain the existing
container limitations.

## Verification

Verified in a disposable UID 1000 GPU session with `docker-default`, default
seccomp, and no added capabilities/security options:

| Check | Result |
| --- | --- |
| All 162 upstream defaults and package dependencies | Pass |
| Fresh profile, native mode, Hyprland config | Pass |
| Remote resize, manual resolution, local scaling, config reload | Actual desktop and advancing NVENC video follow the selected mode |
| NVENC H.264 zero-copy streaming through prefix/auth fixture | Pass |
| Session auth, keyboard, clipboard, F18, reconnect, idle timeout | Pass |
| Local pointer motion, focus recovery, arrow/text/resize shapes | Pass |
| Cursor-free captured desktop | Pass |
| Native authenticated Kasm audio | Pass |
| Wallpaper picker | Nine real thumbnail rows for the fresh Tokyo Night theme |
| Desktop/bar double clicks | Open wallpaper picker, apply another wallpaper, and cycle bar background |
| Native terminal, browser, Nautilus, config editor, LibreOffice Writer | Pass |
| Screenshot and screen recording | Saved PNG and playable MP4 |
| GTK image decoding | Pass; `GLYCIN_DISABLE_SANDBOX` unset |
| GTK portal file chooser | Returned the selected PNG URI through the actual stream |
| Container restart | Pass after audio readiness retries and live Hyprland IPC selection |

Restart fixes handle PipeWire answering before sink setup is ready and stale
Hyprland instance directories whose old process IDs have been reused. Startup
now requires responsive compositor IPC before selecting an instance.

The full-desktop check is:

```bash
python3 tests/verify-full-kasm.py DESKTOP_CONTAINER BROWSER_FIXTURE_CONTAINER
```

It requires the labeled disposable desktop, the prefix proxy from
`tests/selkies-proxy.conf`, and the existing Playwright fixture setup described
in [SELKIES-KASM.md](SELKIES-KASM.md). The test launches applications, records
media, and operates a file chooser; use it only in disposable sessions.
Streaming checks use `verify-selkies-browser.py`, `verify-selkies-host.py`,
`verify-cursor-shapes.py`, and `verify-cursor-separation.py`.
Remote desktop resizing is covered by `verify-selkies-resize.py`; it checks
actual Hyprland geometry and advancing decoded video at each size, including
an idle desktop, manual/automatic transitions, and rapid resize bursts. The current
candidate enables remote resizing by default. `OMARCHY_DYNAMIC_RESIZE=0`
restores the earlier launch-resolution lock.

The dynamic-resize session disables Hyprland's `debug:vfr` in its generated
container config. Hyprland applies output-management updates during render
prechecks; on an idle headless output VFR could leave them pending until the
capture client timed out. Keeping the render clock active prevents that stall.
This trades idle render suppression for reliable remote resizing; the desktop
capture remains zero-copy NVENC and the pointer remains locally rendered.

## Double-click timestamp repair

The pinned pixelflux external-compositor input path sends zero-valued Wayland
pointer timestamps. A native Qt probe confirmed that the clicks reached Qt,
but every `wl_pointer.button` event carried time zero, so Qt did not recognize
double clicks. This affected the upstream desktop wallpaper and bar handlers.

`scripts/wayland-input-timestamps.cpp` is linked into the existing headless
compositor interposer. It wraps the standard virtual-pointer request handlers
and replaces **only missing (zero) timestamps** with wrapping monotonic
milliseconds. Existing nonzero times, button states, coordinates, frame
boundaries, original handlers, and resource cleanup are preserved. The same
pointer device and compositor seat remain in use.

`tests/verify-double-click.py DESKTOP_CONTAINER BROWSER_FIXTURE_CONTAINER`
operates both real shell surfaces through the streamed browser: single clicks
and slow pairs leave the bar/picker alone, a double click cycles the bar
background, a desktop double click opens the picker, and selecting another
wallpaper changes the actual background link. Run this check on an otherwise
empty disposable desktop before the application-launch checks.

The default-security disposable fixture is verified. The user launched the
earlier full-package candidate through Kasm; the updated resize/double-click image
still needs a fresh dashboard session and user acceptance pass.

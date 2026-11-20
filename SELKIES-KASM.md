# Selkies adapter for Kasm

## Candidate image

```text
kasm-omarchy-quattro:4.5.0-selkies-repro-test
```

The image runs the existing Omarchy 4.5.0 desktop with Selkies 2.2.1 / pixelflux
2.2.3 attached directly to Hyprland. The browser stream uses NVENC H.264 over
WebSockets. The authenticated native Kasm audio relay remains on port 4901.

**Live-routing recovery:** the first candidate loaded its HTML/assets but Kasm
returned 403 for nested `/api/status` and `/api/websockets` before they reached
the container. The corrected client uses `selkies-status.json` and `websockify`,
with matching authenticated server aliases and revisioned JS filenames so old
Electron/browser caches cannot keep the rejected endpoint paths.

The recovery build uses **fixed native resolution at launch**, matching the
standalone configuration that worked in workstation testing. It reads Kasm's
`VNC_RESOLUTION`, or an explicit `OMARCHY_RESOLUTION` override, and gives
Hyprland and Selkies that same size. Dynamic output resizing is disabled:
follow-up testing found persistent Wayland output-management overrides could
prevent the requested host mode from taking effect and stall capture. Local
fit/scaling is supported; start a new session to change remote dimensions.

```text
Kasm dashboard/proxy → HTTPS 6901 → Selkies → external Hyprland output
                                   NVENC ← DMA-BUF capture
Kasm audio client   → WSS 4901   → native audio relay ← PipeWire monitor
```

Xvnc, Openbox, TigerVNC viewer, and WayVNC are not started. Selkies has its own
internal allocator/control compositor, but applications and the captured desktop
remain on the existing Hyprland session; Hyprland is not nested inside it.

## Launch through Kasm

Clone the working Omarchy workspace and change **Docker Image** to the candidate
tag above. Keep its GPU allocation, render-node mapping, and supplementary groups.
End the old session and launch a fresh one; reconnecting to an old container does
not load the adapter.

The image includes `video` in `NVIDIA_DRIVER_CAPABILITIES`; retain it if the
workspace overrides that environment variable. The tested device is
`/dev/dri/renderD128`, supplementary group 993. Two GiB shared memory is used by
the test container. Example run-config additions if the workspace does not
already supply these mappings:

```json
{
  "devices": ["/dev/dri/renderD128:/dev/dri/renderD128:rwm"],
  "group_add": ["993"],
  "shm_size": "2g"
}
```

Group numbers are host-specific. Kasm supplies the session's `VNC_PW`; the
adapter serves the normal `vnc.html` URL and uses `kasm_user` HTTP Basic auth.
Selkies derives API/WebSocket URLs from the proxied session directory rather
than KasmVNC's legacy `path=.../websockify` query parameter.

## Supported dashboard integration

| Kasm function | Adapter behavior |
| --- | --- |
| Initialization and connection state | Reports initialized/connecting, then connected after the native stream starts |
| Network reconnect | Preserves Selkies' automatic reconnect and reports the new connection state |
| Explicit disconnect/terminate | Releases keys, closes the stream, and navigates to a disconnected page so reconnect timers stop |
| Idle timeout | Honors the URL's timeout in minutes and runtime timeout messages in seconds |
| Text clipboard | Bridges the dashboard clipboard box in both directions; honors URL direction/seamless flags |
| Stream quality | Maps the five Kasm quality levels to Selkies constant-quality indices |
| Frame rate | Applies the quality message's `frameRate` between 8 and 60 FPS |
| Remote sizing | Native dimensions are chosen at session launch from `VNC_RESOLUTION` / `OMARCHY_RESOLUTION`; dynamic resizing is disabled |
| Fixed-resolution dashboard changes | Ignored while the server's native resolution is locked; change launch resolution and start a new session |
| Local scaling / no scaling | Selects local fit or native-size rendering without changing remote pixel dimensions |
| Config reload | The launch output mode remains in the session's runtime monitor config and survives reload |
| HiDPI | Maps to Selkies' CSS/pixel scaling setting |
| Performance stats | Shows native codec/color, hardware encoder, decoder, FPS, timing, and bitrate in an iframe overlay |
| Keyboard controls | Shows Esc, Tab, explicit terminal copy/paste chords, terminal, and menu buttons |
| Panel shortcut | Ctrl+Shift+1 toggles Kasm's panel |
| Remote-only Mac key | Maps F18 to Super on key down, key up, and heartbeat at the server boundary |
| Audio | Keeps the existing native Kasm audio client/relay path |

Quality mapping (larger Kasm value means higher quality; smaller Selkies index
means higher quality):

| Kasm level | 0 | 1 | 2 | 3 | 4 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Selkies constant-quality index | 40 | 30 | 22 | 12 | 5 |

Defaults are 60 FPS, index 5, full-color 4:4:4 requested, and a three-frame
WebSocket backpressure queue. The actual decoder/profile is visible in the stats
overlay; neither the quality setting nor 4:4:4 means pixel-exact lossless.
The external-compositor/NVENC path was checked at runtime in the browser tests.

This candidate deliberately uses the WebSocket path that worked in workstation
testing. KasmVNC-specific codec/WebP/WebRTC controls, relative-pointer/game-mode
controls, multiple displays, viewer/read-only sharing, uploads/downloads,
microphone, webcam, and printer controls are not bridged. KasmVNC DLP
configuration is not automatically translated into Selkies server policy.
Selkies' native IME behavior remains; Kasm's IME switch is not separately mapped.
Only the owning `kasm_user` credentials are accepted; `kasm_viewer` is rejected.

## Implementation

- `Dockerfile.selkies` derives from the current audio-enabled desktop image and
  installs Selkies in its own virtual environment.
- `scripts/start-headless.sh` selects the `selkies` streaming backend and starts
  Selkies plus the native audio relay after the compositor/PipeWire session.
- `scripts/xwayland-env.py` imports the display (and authority, when present)
  from the Xwayland process owned by the current Hyprland instance. The startup
  supervisor passes it to Quickshell and D-Bus-activated applications after
  Hyprland is ready, so X11/Java launchers receive a usable display.
- `scripts/start-selkies.sh` supplies session auth, external-compositor capture,
  NVIDIA GBM/EGL settings, and default encoding policy. It checks NVENC H.264
  availability before starting.
- `scripts/install-selkies-integration.py` copies the packaged client into a
  separate web root, adds the `vnc.html` entrypoint and Kasm-compatible endpoint
  paths, revisions JS filenames, and adds one checked stream-start notification
  to the pinned compiled core.
- `scripts/selkies-kasm.js` translates Kasm parent messages to Selkies' native
  messaging API, and reports state to the authenticated dashboard parent.
- `scripts/run-selkies.py` provides the F18 mapping and authenticated route
  aliases around the pinned server API. The recovery build does not monkeypatch
  dynamic Hyprland sizing; both ends keep their fixed launch dimensions.

No passwords are embedded in the web client. Native pages, control APIs, and
streaming sockets require session authentication. Selkies' native bootstrap and
health endpoints (`/api/status`, `/api/health`) remain public. The Kasm audio
relay authenticates after upgrading and closes unauthorized sockets before
delivering media.

## Build

```bash
docker build --network host -f Dockerfile.selkies \
  -t kasm-omarchy-quattro:4.5.0-selkies-repro-test .
```

The existing shipping aliases, original KasmVNC rollback image, noVNC candidate,
and standalone Selkies measurement container are separate from this image.
`omarchy-selkies-kasm-image-cache` retains the candidate against unused-image
pruning using only a read-only, network-disabled sleep process with no GPU.

## Verification performed

Real Chromium tests used a TLS nginx fixture reproducing Kasm's session-prefix
stripping, forwarded host, WebSocket proxying, and injected Basic credentials.
It was a real server connection, not a mocked video or WebSocket:

- Loaded `vnc.html` and all client/API assets through the prefixed proxy path.
- Received dashboard initialization and actual stream-start notifications.
- Verified NVENC, DMA-BUF/zero-copy, and the WebSocket transport in native telemetry.
- Changed quality/FPS and checked the native stored choice and measured encode rate.
- Verified fixed native dimensions remain stable through sizing controls and reload.
- Typed and pasted commands that created actual files inside native Foot.
- Held F18 across its heartbeat interval and opened a second Foot with Return;
  verified key release by executing another typed command in that terminal.
- Copied text back from Wayland to the dashboard clipboard event.
- Checked clipboard direction flags, controller-message source checks, panel
  shortcut, automatic reconnect, explicit termination, and idle timeout.
- Rejected absent/wrong credentials on client pages, control APIs, and streaming
  sockets; rejected viewer credentials.
- Checked actual Hyprland monitor geometry, preserved it through reload, and
  confirmed absence of the outer VNC/display bridge processes.
- Checked native audio authentication and received media bytes from the
  PipeWire-backed Kasm relay.

Test files: `tests/verify-selkies-browser.py`, `tests/verify-selkies-host.py`, and
`tests/selkies-proxy.conf`. They operate on a fresh disposable container labeled
`org.omarchy.kasm.test=true`, using test-only loopback ports and credentials.

The corrected proxy fixture explicitly returns 403 for nested `/api/*` to
reproduce the live failure. A subsequent real Kasm-launched session was confirmed
working by the user; container logs showed the authenticated proxy connecting
and NVENC/zero-copy H.264 4:4:4 streaming the native 2844×1198 output. The automated
checks do not log into the dashboard themselves. This adapter does not establish
any new maximum-quality performance claim beyond the earlier benchmark and the
workstation comparison.

## Ignition Designer Launcher / X11 applications

**Verification scope:** the earlier automated check proved only that Designer
Launcher could map a window. The later live test below verifies Designer menu
behavior and UI sizing. Neither establishes complete Designer/project rendering
compatibility or independently resolves the earlier white-window report.

The first working Selkies session exposed a separate application-launch issue:
Ignition Designer Launcher 1.3.10 logged `Unable to open DISPLAY`. Hyprland had
Xwayland running, but Quickshell had inherited no `DISPLAY` after the old Xvnc
display was removed. Exporting the actual Xwayland display opened the launcher.

The image now imports that environment before starting Quickshell, including
the D-Bus activation environment. A fresh disposable-image test launched the
**unmodified** vendor launcher using Quickshell's actual environment and checked
that its window mapped through Xwayland inside Hyprland. The test is
`tests/verify-xwayland-launch.py`; the vendor bundle is a temporary fixture,
not part of the image.

For the already-running user session, `scripts/repair-designer-display.py` added
a missing-display fallback to the downloaded launcher, using the same display
discovery helper. It preserved the original as
`designerlauncher.sh.before-xwayland-fix`. The launcher opened successfully
without restarting the working desktop. New sessions receive the environment
from startup and do not need this vendor-script repair.

### Minimal upstream-environment candidate

`kasm-omarchy-quattro:4.5.0-selkies-session-env-test` tests the central environment
correction. It sources the packaged Omarchy session hooks and user environment
overrides, then asks Hyprland to launch a process that records the compositor's
actual graphical environment. Quickshell and D-Bus activation receive that
environment instead of a separately maintained list of toolkit/display flags.
The snapshot stays in the private runtime directory with mode 0600; its contents
are not logged. Only this container's compositor allocator preload/backend are
filtered from application launches; user-selected values are preserved.

This work is contained in the container startup/compatibility scripts. It does
not rewrite Omarchy's packaged defaults, Hyprland user configuration, or the
Designer vendor bundle. This follows the downstream maintenance policy in
`QUATTRO.md` and allows upstream environment changes to flow through directly.

The environment candidate passed the Kasm adapter checks and a comparison of
Quickshell's environment with the compositor-provided snapshot, including
display, GTK/Qt, desktop identity, terminal, and editor settings. The unmodified
Designer Launcher mapped successfully. The actual Designer white-screen report
still requires a live failing session and is **not claimed fixed** by these tests.

Logs: `/home/kasm-user/.local/state/omarchy/kasm-logs/selkies.log`,
`audio-startup.log`, `audio-relay.log`, and `audio-encoder.log`.

### Verified Designer popup-capture fix (live Ignition 8.3.10)

Opening a Designer menu triggered the desktop screen-sharing permission picker.
A live JVM thread dump identified the exact requesting path:

```text
de.javasoft.plaf.synthetica.Popup.createScreenCapture
java.awt.Robot.createScreenCapture
sun.awt.X11.XRobotPeer.getRGBPixels
sun.awt.screencast.ScreencastHelper.getRGBPixelsImpl
```

Designer was blocked in that capture call on its AWT event thread. This explains
the picker without attributing it to a screenshot key or the streaming client.
The vendor documents a supported way to disable this popup capture in Ignition
8.1.48 and later:
[vendor setting](https://forum.inductiveautomation.com/t/ignition-8-1-45-designer-asking-for-monitor-sharing/102767/8),
also linked from the user's
[remote-desktop issue](https://forum.inductiveautomation.com/t/linux-remote-desktop-issue/116604/3).

The live user's `~/.ignition/synthetica-no-popup-capture.xml` contains:

```xml
<synth>
    <defaultsProperty key="Synthetica.popupRobot.enabled" type="boolean" value="false"/>
</synth>
```

With Designer and its launcher closed, the single saved Designer entry's
`jvm.arguments` list in `~/.ignition/clientlauncher-data/designer-launcher.json`
received:

```text
-Dignition.synthetica.customXml=/home/kasm-user/.ignition/synthetica-no-popup-capture.xml
```

The original JSON was backed up beside it as
`designer-launcher.json.before-popup-fix-20261120-155438`, mode 0600. This is a
user/application setting, not an image-wide Java override. If an entry already
uses custom Synthetica XML, merge the property into that file rather than
replacing its setting. To undo, close both applications and remove the added JVM
argument; the backup can restore the entire original launcher configuration if
no subsequent settings need preserving.

The oversized UI had a separate, confirmed environment mismatch: the monitor
configuration had been changed to `GDK_SCALE=1` after Quickshell and the existing
terminal started with `GDK_SCALE=2`. Their Designer child inherited 2 although
the output scale was 1. A fresh Hyprland-child probe returned `GDK_SCALE=1`.
The test reopened the launcher through Hyprland, retaining `GDK_BACKEND=x11`
from the prior Designer run, so it inherited the current scale. Already-running
Quickshell/terminal processes retain their old environment; normal launches from
those processes need a refreshed shell/session to inherit the changed scale.

The user then launched Designer and confirmed **menus work and size is correct**.
Inspection of the new Designer JVM independently confirmed `GDK_SCALE=1` and the
custom XML JVM argument. The fix is applied to this live user's saved entry;
its availability in future containers depends on persistence of that home
directory. Full project rendering and the earlier white-window behavior were
not separately verified by this menu/scaling check.

### Follow-up: persistent launch scale and text rendering

Reopening from the older desktop shell reproduced scale 2 in **both** JavaFX
Launcher and Designer. A trial `-Dsun.java2d.uiScale=1` could not affect the
launcher's separate runtime and was removed. The working correction prefixes
the `Exec` line in these user-owned desktop entries with `env GDK_SCALE=1`:

```text
~/.local/share/applications/Designer Launcher.desktop
~/.local/share/applications/ignition-designer.desktop
~/.local/share/applications/ignition-designer-link.desktop
```

The vendor launcher script is unchanged. Designer's saved entry also uses:

```text
-Dawt.useSystemAAFontSettings=on
-Dswing.aatext=true
```

The user confirmed the resulting size and text were correct. Inspection of the
running Designer confirmed scale 1, both antialiasing settings, and the popup XML
argument. No system font was changed. User settings/backups remain private in
the home directory; none of the gateway configuration is versioned here.

The custom `nburnet1.workspaces` plugin was installed by the user's dotfiles but
was absent from the running registry. `omarchy-shell shell rescanPlugins` followed
by `omarchy-shell shell reloadConfig` restored its visible bar widget; the user
confirmed the 1–5 buttons returned. No widget implementation change was needed.

The repeatable Designer helper and post-stow plugin refresh now live in
[omarchy-dotfiles](https://github.com/nburnet1/omarchy-dotfiles). See
[REPRODUCING.md](REPRODUCING.md) for the combined setup and persistence scope.

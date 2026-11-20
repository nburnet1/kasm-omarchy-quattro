# Direct WayVNC streaming experiment

## Kasm dashboard candidate

Use **`kasm-omarchy-quattro:4.5.0-novnc-kasm-test`** for the dashboard integration
candidate. End the old session and launch a new one after changing the workspace
image. Retain the same GPU allocation, render-node mappings, and supplementary
groups used by the working Omarchy workspace. The shipping aliases and rollback
image are separate from this candidate.

`omarchy-novnc-kasm-image-cache` retains the candidate using only a read-only,
network-disabled sleep process. The disposable verification desktop was stopped
after testing to release its GPU resources.

The original `4.5.0-novnc-test` image was a standalone prototype. Kasm's proxy
logs showed that it connected and transferred desktop data, but upstream noVNC
did not report initialization/connection state to the dashboard. Upstream also
resolved Kasm's origin-relative WebSocket query path against the iframe's
directory, duplicating the session prefix.

The candidate includes `scripts/novnc-kasm.js`, a small dashboard adapter that:

- Reports `noVNC_initialized`, connection states, disconnect, and idle timeout.
- Resolves Kasm's supplied WebSocket path relative to the origin.
- Handles text clipboard, resize/scaling, fixed resolution, JPEG quality,
  keyboard-control visibility, termination, and Ctrl+Shift+1 panel toggling.
- Maps F18 to Super before noVNC sends the event to WayVNC.
- Keeps the standard noVNC control bar hidden in the dashboard by default.

When `KASM_ID` is present, HTTPS pages **and** WebSocket upgrades require HTTP
Basic credentials `kasm_user` and the session's `VNC_PW`, supplied by Kasm's
authenticated proxy. No password is embedded in the client or process arguments.
For an authenticated standalone test, set `OMARCHY_NOVNC_AUTH=1` and `VNC_PW`.

```bash
docker build --network host -f Dockerfile.novnc \
  -t kasm-omarchy-quattro:4.5.0-novnc-kasm-test .
```

The candidate passed real Chromium testing with a Kasm-shaped iframe URL and
parent messages: authenticated rendering, exact WebSocket path, initialization
and connection notifications, remote/fixed resolution changes, quality controls,
keyboard controls, a browser-typed shell command, clipboard paste into Foot,
and dashboard termination. HTTP and WebSocket requests with missing or incorrect
credentials were rejected. Protocol checks also verified nonblank capture,
native input, and absence of the outer Xvnc/viewer processes.

The browser fixture reproduces the observed dashboard contract; it does not
log into the live dashboard. A fresh dashboard launch still needs confirmation.
The browser test is `tests/verify-novnc-browser.py` and requires Playwright plus
Chromium; the protocol check accepts `NOVNC_TEST_PASSWORD` for authenticated
endpoints. Both checks must target a disposable test session.

KasmVNC-only controls such as WebRTC transit, codec selection, performance stats,
game/relative-pointer mode, IME mode switching, and multiple displays are not
implemented by the adapter. Viewer/read-only sharing credentials are rejected;
only the owning `kasm_user` session is supported. This candidate derives from the
preserved pre-audio baseline and does not include the separate audio update.

## Preserved baseline

The exact image backing the working Kasm session on 2026-11-20 is preserved as:

```text
kasm-omarchy-quattro:4.5.0-kasmvnc-rollback-20261120
sha256:ef21ab5e81893a5a2932969256d44fa4f2da750ebcf0559b8c0e10858e94581e
```

This preserves the image, not a snapshot of files in a running session's home
directory. Creating the rollback tag does not alter a running session.
The read-only, network-disabled `omarchy-kasmvnc-rollback-cache` container runs
only `sleep infinity` to retain the rollback image against unused-image pruning.
It has no GPU allocation. Keep this container until the experiment is complete.

For rollback, select the rollback image tag in the Kasm workspace configuration
and launch a new session. The experiment has its own tag and does not retag
`quattro-dev` or the shipping release aliases.

During this work, a separate audio update advanced the shipping aliases to
`sha256:2356c3b75fe08bb2a1c63c6179bd678e03cd00f41edb31cab3405f793dddf667`
(`4.5.0-audio`), retained by `omarchy-audio-image-cache`. The rollback and this
experiment deliberately reference the exact pre-audio image captured above.

## Experimental path

```text
Browser / noVNC 1.6.0
  → HTTPS + WebSocket / websockify 0.13.0
  → loopback WayVNC
  → GPU-rendered headless Hyprland + Omarchy
```

There is no running Xvnc, fullscreen TigerVNC viewer, or Openbox. Websockify
forwards RFB bytes without decoding or recapturing frames. Hyprland may still
start Xwayland for X11 applications; that is not the old streaming bridge.

`Dockerfile.novnc` derives from the preserved baseline and replaces its
entrypoint. It uses the shared startup script's `novnc` backend, while the
default backend remains `kasmvnc`. The initial resolution is 1920×1080 at 60 Hz;
WayVNC requests up to 60 FPS. The direct output is named `HEADLESS-1` because
WayVNC restricts remote resizing to `HEADLESS-*`/`NOOP-*` outputs.

## Build and run

```bash
docker build --network host -f Dockerfile.novnc \
  -t kasm-omarchy-quattro:4.5.0-novnc-test .

docker run -d --name omarchy-novnc-test \
  --label org.omarchy.kasm.test=true \
  --gpus all --device /dev/dri/renderD128 \
  --group-add "$(stat -c %g /dev/dri/renderD128)" --shm-size=1g \
  -p 127.0.0.1:16909:6901 \
  kasm-omarchy-quattro:4.5.0-novnc-test
```

For a remote workstation:

```bash
ssh -N -L 16909:127.0.0.1:16909 nburnet1@YOUR_SERVER
```

Open:

```text
https://localhost:16909/vnc.html?autoconnect=true&resize=remote
```

Accept the test endpoint's self-signed certificate. This experiment has no
browser password/authentication layer: access is restricted by the host-loopback
binding and SSH tunnel. Keep the published port bound to `127.0.0.1`.

For a fixed-resolution A/B comparison, use `resize=scale` in the URL instead of
`resize=remote`. Set `-e OMARCHY_RESOLUTION=2844x1198` when launching to match the
baseline resolution observed during investigation, or compare both at 1080p.

## Verification and comparison

```bash
python3 tests/verify-novnc.py omarchy-novnc-test
```

The protocol smoke check passed:

- noVNC page served over HTTPS; WebSocket upgrade and RFB handshake.
- Nonblank 1920×1080 framebuffer captured through the new path.
- Ctrl+Shift+Return opens a native Foot terminal.
- A command typed through RFB executes in that terminal.
- Pointer movement reaches Hyprland (within one pixel of rounding).
- Remote desktop resize to 1280×800 and restoration.
- No Hyprland config errors and no outer Xvnc/viewer/Openbox processes.

The original standalone verification was protocol-level. The dashboard
candidate adds the browser checks described above. Neither is a physical
input-to-photon latency benchmark. Compare typing, selection, scrolling, and
window dragging from the same workstation/browser at matched resolution.

## Prototype limitations

- The standalone endpoint remains separate from the Kasm dashboard; use the
  candidate above for dashboard integration and session authentication.
- The original standalone image does not carry KasmVNC's F18→Super remapping.
  The dashboard candidate implements it in the client adapter. Ctrl+Shift+Return
  and the existing Super-free Hyprland aliases work in both.
- WayVNC handles remote resizing directly. The old X11 resize synchronizer is
  not started; resized modes are not explicitly saved by this backend for
  compositor configuration reloads.
- noVNC clipboard and keyboard behavior should be checked on the workstation.
- The baseline application's installed packages remain inherited. Audio
  streaming and other Kasm service integration are not added by this prototype.

Logs are in `/home/kasm-user/.local/state/omarchy/kasm-logs/`, including
`wayvnc.log` and `websockify.log`.

Stop the experiment with `docker stop omarchy-novnc-test`. The test container
also retains its image while stopped.

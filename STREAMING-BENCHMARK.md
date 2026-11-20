# Selkies vs WayVNC: measured results, 2026-11-20

## Decision

**The direct Selkies/NVENC path is substantially faster during motion, but the
tested maximum-quality configuration does not meet the native-resolution,
responsive-60-FPS goal. Do not promote it to the shipping Kasm image yet.**

We verified the actual hardware capture/encode path, rather than inferring it
from a synthetic encoder test. The remaining work is not just dashboard glue:
the highest-quality stream still falls short at both encoding and presentation,
and the measured client used software decoding.

## Setup and method

- One disposable container, `omarchy-stream-benchmark`, and **one** Hyprland
  desktop/output shared by both alternatives. Only one streaming client was
  connected at a time. Production workspace definitions/tags were not changed.
- Quadro P1000, NVIDIA driver 580.178.04, render node `/dev/dri/renderD128`.
- Native remote output and client viewport: **2844×1198**; no resolution scaling.
- Real WebGL Aquarium, **1,000 fish**, `fitWindow=true`, locally served assets.
  Fixture commit: `6d56695888ec72b1ef2674498e307f1ab4310226` from
  `https://github.com/WebGLSamples/WebGLSamples.github.io`.
- The application's WebGL renderer was verified as
  `ANGLE (NVIDIA Corporation, Quadro P1000/PCIe/SSE2, OpenGL ES 3.2)`;
  its reported frame rate stayed around 59–60 FPS in the motion tests.
- Source and observing browsers: Chromium **158.0.8127.36**. The observer ran
  headless with `--disable-gpu` and **software decoding**, on the server host.
  This is not the workstation's browser, network, display, or physical input.
  Other host services and the user's separate workspace remained running.
- noVNC 1.6.0 → websockify → WayVNC, Tight, quality **9**, compression **2**.
- Selkies **2.2.1**, pixelflux **2.2.3**, external Hyprland capture, full-frame
  **NVENC H.264 4:4:4 8-bit**, constant-quality mode. Quality values **18**, **10**,
  then **5** were tested. Five is the finest exposed constant-quality index in
  this Selkies version; it is not lossless.
- Main table: 20 synthetic keypress trials per condition, 300 ms between
  completed trials. Clock starts on the observing browser's actual keydown DOM
  event and stops when the input counter appears in decoded stream pixels.
- An independent animated frame counter measures distinct source updates
  observed on the receiving canvas at rAF cadence. Its rate is not a protocol
  frame counter or the source Aquarium's FPS.
- The final highest-quality run added a random generation marker to reject old
  frames from a previous phase. Screensaver/idle was disabled through the
  shell's own IPC on this disposable session.
- The stationary condition freezes the aquarium but keeps the small marker
  animating. It is not a truly unchanged/zero-update desktop.

## Highest-quality comparison

Results below come from `/tmp/opencode/stream-ab-maxquality.json`'s four
completed conditions. A subsequent WebRTC phase in that invocation failed the
fresh-frame check; it is not included in this table.

| Path | Scene | Observed unique FPS | Key → visible median | p95 | Key → application median |
| --- | --- | ---: | ---: | ---: | ---: |
| noVNC/WayVNC, quality 9 | Stationary aquarium + marker | 56.57 | 96.2 ms | 96.9 ms | 2.0 ms |
| noVNC/WayVNC, quality 9 | Aquarium moving | **1.25** | **1,258.5 ms** | **2,128.5 ms** | 6.0 ms |
| Selkies WebSocket, quality index 5, 4:4:4 | Stationary aquarium + marker | 55.77 | 96.4 ms | 107.6 ms | 2.0 ms |
| Selkies WebSocket, quality index 5, 4:4:4 | Aquarium moving | **19.98** | **447.9 ms** | **776.2 ms** | 16.5 ms |

In the motion case, the application received input much sooner than its result
appeared. Streaming feedback latency is a substantial part of the problem.
Selkies improved displayed-update rate by about 16× here, but 20 FPS and roughly
450 ms median feedback are not an acceptable result for the stated goal.

### Server and client evidence

Selkies reported the active stream as:

```text
backend=wayland, capture=dmabuf, zero_copy=true
encoder=NVENC, hardware=true, codec=h264, fullcolor=true
gpu=Quadro P1000, renderer=gl
```

Runtime log:

```text
[HostCapture] capturing host compositor 'wayland-1' (1 outputs).
[Wayland] Encoder: NVENC H264 4:4:4 8-bit on Quadro P1000 ...
[Wayland] Zero-copy capture: ... encoded in place on NVENC.
```

During the highest-quality motion run, the final five reported samples averaged
about **45 encoded FPS**, **17.9 ms encode time**, **23.0 ms capture-to-send time**,
and **300 Mbit/s received video** over the measurement interval. The client
reported software decoding, and presentation was slower than server encoding.
Those timing components are not a complete additive latency budget; queues,
cadence, and receiver buffering also contribute to the measured visible delay.

At quality index 18, earlier repeated motion runs delivered approximately
30–34 observed FPS, 369–401 ms median key-to-visible feedback, and roughly
58–60 server-encoded FPS. That setting has lower measured image fidelity and
is not evidence the maximum-quality target was achieved.

## Quality check

PSNR was measured on a fixed interior crop of the stationary aquarium, comparing
a screenshot of the source page to one of the decoded stream. The crop excludes
client controls, the input/frame marker, and Aquarium's FPS overlay. Higher is
closer to that reference. This is a limited static-image check, not a complete
perceptual or moving-image assessment.

| Setting | Static crop PSNR |
| --- | ---: |
| noVNC/WayVNC quality 9 | 45.89 dB |
| Selkies index 18, 4:4:4 | ~39.31 dB |
| Selkies index 10, 4:4:4 | 42.77 dB |
| Selkies index 5, 4:4:4 | 44.23 dB |

**These are not equal-quality codec settings.** The strongest Selkies setting
tested came closer to noVNC's still-image fidelity but did not equal it, and
raising fidelity reduced motion throughput. There is no basis here to claim
equal or superior maximum image quality at 60 FPS.

## WebRTC findings

- Direct host-to-container UDP ICE connectivity and H.264 4:4:4 negotiation were
  confirmed. It was not necessary to use external STUN/TURN for this local test;
  `/tmp/rtc.json` contained `{"iceServers": []}`.
- A pilot initially requested WebRTC only in the client, but the dashboard
  selected the server's WebSocket mode. **That pilot is excluded as WebRTC
  evidence.** The benchmark now switches the server via `/api/switch` and
  records whether the actual transport matches the request.
- The initial WebRTC constant-quality configuration retained the default
  8-Mbit/s pacing hint while the encoder generated hundreds of Mbit/s. Logs
  showed repeated queue overflow/GOP resets. A later run supplied a
  500-Mbit/s hint without changing constant quality.
- At the highest-quality setting, the receiver still failed to present the
  fresh generation marker within 30 seconds. Logs showed established ICE and
  hardware encoding, but this did not produce a successful comparable run.
  **There is no successful high-quality WebRTC result to recommend yet.**

## What the results justify

1. Selkies' documented external-compositor/NVENC path works with this particular
   headless Hyprland and NVIDIA setup, once the NVIDIA GBM/EGL paths are set.
2. The severe noVNC motion slowdown is reproducible even on a same-host link
   with the aquarium itself running at approximately 60 FPS.
3. Hardware video improves motion throughput substantially, but the tested
   maximum-quality configuration still misses both responsiveness and FPS.
4. Before full Kasm integration, test the actual workstation's decode path and
   investigate the demonstrated frame-age/buffering and WebRTC failures. Do not
   assume hardware encoding alone guarantees a good experience.

## Artifacts and reproduction

- `Dockerfile.selkies-test`: isolated measurement image derived from the
  existing experimental image. It adds a separate Selkies virtual environment.
- `tests/start-selkies-benchmark.sh`: starts external-compositor capture with
  explicit NVIDIA GBM/EGL paths; optional extra CLI arguments override defaults.
- `tests/benchmark-streaming.py`: Playwright workload, pixel-marker timing,
  quality measurement, server/client evidence, and JSON output.
- Initial image tested:
  `sha256:4fd731ba15f43a7344e5e4561ccb527764ecbf2f000bef73e82700448565fd9c`.
- Raw JSON on this host:
  `/tmp/opencode/stream-ab-final.json` (index 18 repeated A/B),
  `/tmp/opencode/stream-crf10.json`,
  `/tmp/opencode/stream-ab-maxquality.json` (index 5, generation-checked).
- Hardware/runtime logs inside the measurement container:
  `/tmp/selkies-benchmark.log`, `/tmp/selkies-benchmark-crf10.log`,
  `/tmp/selkies-benchmark-crf5.log`.

The measurement image leaves the existing noVNC entrypoint intact. Start a
disposable container with the same GPU/render-node mappings as the working
image, 2 GiB shared memory, and **loopback-only** published ports:
16911→6901 (noVNC), 16912→8080 (Selkies), and 19223→9223 (test-only CDP bridge).
Serve the aquarium fixture and its `tdl`, `jquery-ui-1.8.2.custom`, and `khronos`
directories from `/opt/noVNC`, using a container-loopback HTTP server on 8999.
Launch a separate native Chromium with `--kiosk`, Wayland, and
`--remote-debugging-port=9222` at the local aquarium URL, then proxy that CDP
port through container port 9223 using socat. CDP is a test control interface,
not part of the streaming architecture.

Inside the test container, after the compositor is ready:

```bash
XDG_RUNTIME_DIR=/run/user/1000 WAYLAND_DISPLAY=wayland-1 omarchy-shell idle disable
BENCHMARK_CRF=5 bash /tmp/start-selkies-benchmark.sh --video-bitrate=500000-500000
```

The measured observing browser ran in a temporary tooling container using
`--network host`, 1 GiB shared memory, the same image, Playwright, and
`tests/benchmark-streaming.py --trials 20 --order novnc,selkies`. No Kasm reverse
proxy or physical workstation/network delay is included in these measurements.

The standalone measurement endpoints have no additional password; their host
ports are restricted to loopback. They are not a Kasm-ready Selkies image.

## Workstation comparison left running

The measurement desktop is currently left at the moving 1,000-fish aquarium,
native 2844×1198, with Selkies in WebSocket/NVENC/4:4:4 mode at quality index 5.
Both viewers attach to this same desktop. Connect only one at a time so a second
capture/encode/decode session does not change the comparison.

```bash
ssh -N \
  -L 16911:127.0.0.1:16911 \
  -L 16912:127.0.0.1:16912 \
  nburnet1@YOUR_SERVER
```

- noVNC: `https://localhost:16911/vnc.html?autoconnect=1&resize=off&quality=9&compression=2`
- Selkies: `https://localhost:16912/`

Accept the test certificates. Keep the browser, window size, remote resolution,
and fish count the same for both; the Selkies stats panel reports the actual
codec, color format, decode path, and delivered rate. This workstation check is
necessary because the automated observer was a software-decoding Linux browser,
not the user's Mac/Electron client. The test container can be stopped using
`docker stop omarchy-stream-benchmark` after the comparison to release resources.

# High-quality motion streaming architecture investigation

**Measured follow-up:** [STREAMING-BENCHMARK.md](STREAMING-BENCHMARK.md) records
the actual experiment. Selkies/NVENC improved motion performance, but the tested
maximum-quality configuration did not achieve responsive 60 FPS. The proposal
below is an architectural hypothesis, not a validated shipping recommendation.

Investigation: 2026-11-20. Goal: retain the genuine Omarchy/Hyprland desktop,
launch it through Kasm, and sustain high-quality motion with responsive input.
Reducing resolution or JPEG quality is not the proposed solution.

## Recommendation: external-compositor Selkies + NVENC

```text
Kasm: session creation, GPU allocation, authentication, HTTPS proxy, lifecycle

Hyprland headless output
  → Wayland capture by Selkies/pixelflux
  → NVIDIA NVENC H.264
  → WebRTC video → browser decoder/display

Browser input → WebRTC data channel → compositor virtual keyboard/pointer
```

Selkies 2.2.1 documentation describes attachment to an existing compositor using
`SELKIES_WAYLAND_HOST_DISPLAY`, capture via ext-image-copy-capture or
wlr-screencopy, GPU-buffer paths, and virtual keyboard/pointer injection. This
matches the protocols exposed by our running Hyprland. Use this external mode;
starting a second compositor and nesting Hyprland adds another rendering stage.

Selkies also supports hardware video over WebSockets, decoded with WebCodecs.
That is an integration fallback for environments limited to Kasm's HTTPS proxy.
WebRTC is the preferred motion-streaming experiment because video need not wait
for TCP retransmission, and its pacer prioritizes interactive traffic over video
bursts. It needs additional UDP routing or TURN; Kasm's HTTPS reverse proxy does
not supply that media path by itself. Neither transport removes physical
bandwidth or decoder limits.

### Kasm integration is part of the prototype

- Serve the client on the container's HTTPS port 6901 and provide a `vnc.html`
  entrypoint compatible with Kasm's launch URL.
- Map Kasm's HTTP Basic session credentials to Selkies authentication.
- Handle Kasm's proxied session prefixes for HTTP and WebSocket/signaling paths.
- Bridge Selkies client lifecycle events to Kasm's initialized/connection-state
  messages. The noVNC adapter established this contract but cannot be reused
  unchanged against Selkies' different client API.
- Map supported clipboard, resolution, quality, and keyboard controls; advertise
  only capabilities actually implemented.
- Route media to the correct allocated session and stop the media session when
  Kasm ends it. Verify authentication on every externally reachable endpoint.
- Configure UDP mapping/advertisement or authenticated TURN for WebRTC. Do not
  send video through a browser inside another streamed Kasm desktop.

Kasm's documented **Web App Gateway** opens web applications inside a remote
browser and streams that browser. It is not a direct arbitrary-web-app reverse
proxy replacement for the integration above; using it here would recapture and
encode the desktop a second time.

## Hardware findings

Host GPU: Quadro P1000; driver 580.178.04. Tests used disposable containers and
included `NVIDIA_DRIVER_CAPABILITIES=graphics,utility,display,video`.

| Probe | Result |
| --- | --- |
| Current Arch FFmpeg, H.264 NVENC | Failed: requires NVENC API 13.1; driver exposes 13.0 |
| Ubuntu image's older FFmpeg, H.264 4:2:0, 2844×1198, 60 FPS source, 120 frames, QP 18 | Passed; about 3.41× realtime |
| Same older FFmpeg, H.264 High 4:4:4 Predictive, same resolution/rate/frame count/QP | Passed; about 2.42× realtime |

These are short synthetic encode-only probes, not sustained aquarium rendering,
Wayland capture, client decoding, network, or input-to-photon benchmarks. They
establish that the GPU can encode both formats at this resolution with a
compatible encoder build. Selkies/pixelflux has its own encoder implementation;
its compatibility must be tested independently. An FFmpeg failure is not proof
that Selkies fails, and a successful FFmpeg probe is not proof Selkies works.

The new image must include the NVIDIA **video** capability and compatible NVENC
dependencies. Check the actual runtime encoder and fail clearly if hardware
encoding is unavailable rather than silently accepting a software fallback.
AV1 hardware encoding is not an option on the Pascal-generation P1000.

### Reproduce the successful probe

```bash
docker run --rm --gpus all \
  -e NVIDIA_DRIVER_CAPABILITIES=graphics,utility,display,video \
  --entrypoint /usr/bin/ffmpeg kasmweb/ubuntu-noble-nvidia:1.17.0 \
  -hide_banner -f lavfi -i testsrc2=size=2844x1198:rate=60 \
  -vf format=yuv444p -frames:v 120 -c:v h264_nvenc -profile:v high444p \
  -preset p1 -tune ull -rc constqp -qp 18 -bf 0 -f null -
```

## Quality target

Proposed initial target: native 2844×1198 at 60 FPS, no automatic resolution
reduction, a fixed high-quality video setting, bounded queues, and responsive
input while the aquarium runs. QP/CRF values are codec/implementation-specific;
QP 18 was a feasibility probe, not a final setting or a lossless guarantee.

4:4:4 preserves full chroma resolution, which matters for colored text and fine
UI edges. It is not lossless compression. Hardware encoding was verified; the
workstation's browser must also decode the selected 4:4:4 profile fast enough.
A successful browser capability query alone does not establish hardware decode
or realtime throughput. Verify the active profile, decoder, and fallback.

Pixel-exact lossless is a separate target. Uncompressed RGB at the observed
resolution/rate is approximately 4.9 Gbit/s before overhead; lossless compression
can reduce this by a content-dependent amount. No architecture guarantees
pixel-exact full-motion 60 FPS on an arbitrary link. Clarify this distinction
before locking the final quality policy.

## Alternatives considered

| Architecture | Assessment |
| --- | --- |
| Selkies → existing Hyprland + NVENC | Best next browser/Kasm prototype; external Wayland capture, hardware encoding, embeddable client, WebRTC and WebSocket transports |
| Newer KasmVNC video streaming + original viewer bridge | Better native Kasm integration; NVENC H.264/H.265 available, but retains the Xvnc/viewer capture stages and current documented video mode is YUV420 |
| Sunshine + Moonlight | Strong low-latency reference; Sunshine documents wlr capture of Hyprland virtual outputs and NVENC. Native Moonlight is not the Kasm browser client; a browser gateway and its integration need separate work |
| Wolf | Container/game-streaming-oriented, but introduces its own session/display orchestration and primarily targets Moonlight; less direct fit for preserving this Kasm-managed Hyprland session |
| Wayland capture backend added to KasmVNC | Potentially clean long-term architecture; substantial server development, not an existing configuration option |

## Prototype acceptance checks

1. Hardware encode and actual workstation decode at native resolution, including
   4:4:4 if full chroma is required; no unexpected codec/software fallback.
2. Real Kasm dashboard launch, successful session authentication, correct URL
   routing, reconnect, and termination, alongside the preserved rollback image.
3. Sustained aquarium run at fixed fish count, browser size, and quality. Verify
   the aquarium itself renders on NVIDIA, not SwiftShader/llvmpipe.
4. Collect frame/capture/encode/decode times, actual bitrate, queue depth/frame
   age, GPU/CPU utilization, and packet loss. Measure keyboard/mouse visible
   feedback under load, including p95 rather than only average FPS.
5. Check colored text, thin lines, and static-screen fidelity as well as motion.
6. Confirm clipboard, remote sizing, Mac modifier handling, and media-session
   isolation/lifecycle through Kasm.

## Sources

- Selkies settings/backends/transports: https://docs.selkies.io/latest/settings/
- Capture and encoder details: https://docs.selkies.io/latest/components/pixelflux/
- Embeddable client: https://docs.selkies.io/latest/components/web-client/
- Reverse-proxy deployment patterns: https://docs.selkies.io/latest/platforms/
- KasmVNC video mode: https://www.kasmweb.com/kasmvnc/docs/latest/video_streaming_mode
- Sunshine capture/encode configuration: https://docs.lizardbyte.dev/projects/sunshine/latest/md_docs_2configuration.html
- Wolf: https://github.com/games-on-whales/wolf
- Kasm Web App Gateway: https://kasmweb.com/docs/latest/how_to/web_app_gateway.html

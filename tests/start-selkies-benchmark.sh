#!/bin/bash
# Run only inside the disposable measurement container; publish 8080 on host loopback.
set -euo pipefail
export XDG_RUNTIME_DIR=/run/user/$(id -u)
export WAYLAND_DISPLAY=wayland-1
export LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
export GBM_BACKENDS_PATH=/usr/lib/x86_64-linux-gnu/gbm
export __EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/10_nvidia.json
crf=${BENCHMARK_CRF:-18}
exec /opt/selkies-test/bin/selkies \
  --public --port=8080 --enable-https=true \
  --https-cert="$XDG_RUNTIME_DIR/novnc-cert.pem" --https-key="$XDG_RUNTIME_DIR/novnc-key.pem" \
  --enable-basic-auth=false --wayland=true \
  --wayland-host-display=wayland-1 --app-wayland-display=wayland-1 \
  --encoder=h264enc --video-fullcolor=true --rate-control-mode=crf \
  --video-crf="$crf-$crf" \
  --framerate=60-60 --enable-resize=false --manual-width=2844 --manual-height=1198 \
  --audio-enabled=false --second-screen=false --printing-enabled=false \
  --gamepad-enabled=false --file-transfers=none --backpressure-queue-size=3 "$@"

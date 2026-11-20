#!/bin/bash
set -euo pipefail
: "${VNC_PW:?VNC_PW must contain the Kasm session password}"
export PULSE_SERVER="unix:$XDG_RUNTIME_DIR/pulse/native"
export SELKIES_PUBLIC=true SELKIES_PORT=6901 SELKIES_ENABLE_HTTPS=true
export SELKIES_HTTPS_CERT="$HOME/.vnc/self.pem" SELKIES_HTTPS_KEY="$HOME/.vnc/self.pem"
export SELKIES_BASIC_AUTH_USER=kasm_user SELKIES_BASIC_AUTH_PASSWORD="$VNC_PW"
export SELKIES_ENABLE_BASIC_AUTH=true
export SELKIES_WEB_ROOT=/usr/local/share/omarchy-kasm/selkies-web
export SELKIES_WAYLAND=true SELKIES_WAYLAND_HOST_DISPLAY="$WAYLAND_DISPLAY"
export SELKIES_APP_WAYLAND_DISPLAY="$WAYLAND_DISPLAY"
export SELKIES_RENDER_DRI="$AQ_HEADLESS_RENDER_NODE" SELKIES_ENCODE_DRI="$AQ_HEADLESS_RENDER_NODE"
export SELKIES_MODE=websockets SELKIES_ENABLE_DUAL_MODE='false|locked'
export SELKIES_ENABLE_RESIZE='false|locked'
export SELKIES_MANUAL_WIDTH="${OMARCHY_DISPLAY_WIDTH:?}" SELKIES_MANUAL_HEIGHT="${OMARCHY_DISPLAY_HEIGHT:?}"
export SELKIES_ENCODER=h264enc SELKIES_RATE_CONTROL_MODE=crf
export SELKIES_FRAMERATE="${SELKIES_FRAMERATE:-60,8-60}"
export SELKIES_VIDEO_CRF="${SELKIES_VIDEO_CRF:-5,5-50}"
export SELKIES_VIDEO_FULLCOLOR="${SELKIES_VIDEO_FULLCOLOR:-true}"
export SELKIES_BACKPRESSURE_QUEUE_SIZE="${SELKIES_BACKPRESSURE_QUEUE_SIZE:-3}"
export SELKIES_MAC_CMD_AS_CTRL='false|locked' SELKIES_KEYBOARD_SHORTCUTS='false|locked'
# Use Kasm's existing authenticated audio service, not two audio streams.
export SELKIES_AUDIO_ENABLED='false|locked' SELKIES_MICROPHONE_ENABLED='false|locked'
export SELKIES_SECOND_SCREEN='false|locked' SELKIES_GAMEPAD_ENABLED='false|locked'
export SELKIES_PRINTING_ENABLED='false|locked' SELKIES_FILE_TRANSFERS=none

/opt/selkies/bin/python -c 'import pixelflux; assert pixelflux.hardware_encoders().get("h264") == "nvenc", "NVENC H.264 is required for this candidate"'
exec /usr/local/bin/omarchy-run-selkies

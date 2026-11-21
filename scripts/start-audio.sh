#!/bin/bash
# Kasm browser audio: PipeWire sink monitor -> MP2/MPEG-TS -> authenticated WSS.
# PipeWire itself belongs to the desktop session; do not start a second server.
set -euo pipefail
export XDG_RUNTIME_DIR="/run/user/$(id -u)"
export PULSE_SERVER="unix:$XDG_RUNTIME_DIR/pulse/native"
logdir="$HOME/.local/state/omarchy/kasm-logs"
mkdir -p "$logdir"
children=()
cleanup() {
  if ((${#children[@]})); then
    kill "${children[@]}" 2>/dev/null || true
    wait "${children[@]}" 2>/dev/null || true
  fi
}
trap cleanup EXIT
trap 'exit 0' TERM INT

while true; do
  # The custom desktop startup initializes PipeWire asynchronously.
  until pactl info >/dev/null 2>&1; do sleep 0.5; done
  if ! pactl list short sinks | cut -f2 | grep -qx kasm_output; then
    if ! pactl load-module module-null-sink sink_name=kasm_output \
      sink_properties=device.description=Kasm_Audio_Output >/dev/null; then
      # PipeWire can answer info before its Pulse modules/session policy are
      # ready, especially when restoring a profile on container restart.
      sleep 0.5
      continue
    fi
  fi
  if ! pactl set-default-sink kasm_output; then
    sleep 0.5
    continue
  fi
  # Move any applications that started before the virtual sink was ready.
  while read -r input _; do
    pactl move-sink-input "$input" kasm_output || true
  done < <(pactl list short sink-inputs)

  /dockerstartup/jsmpeg/kasm_audio_out-linux kasmaudio 8081 "${AUDIO_PORT:-4901}" \
    "$HOME/.vnc/self.pem" "$HOME/.vnc/self.pem" "kasm_user:${VNC_PW:?}" \
    >> "$logdir/audio-relay.log" 2>&1 &
  relay_pid=$!
  children=($relay_pid)
  for ((attempt=0; attempt<50; attempt++)); do
    kill -0 "$relay_pid" 2>/dev/null || break
    if (exec 3<>/dev/tcp/127.0.0.1/8081) 2>/dev/null; then break; fi
    sleep 0.1
  done
  # Capture the output monitor explicitly, rather than the default microphone.
  no_proxy=127.0.0.1 NO_PROXY=127.0.0.1 ffmpeg -nostdin -hide_banner -loglevel warning \
    -f pulse -fragment_size "${PULSEAUDIO_FRAGMENT_SIZE:-2000}" -ar 44100 \
    -i kasm_output.monitor -f mpegts -correct_ts_overflow 0 \
    -codec:a mp2 -b:a 128k -ac 1 -muxdelay 0.001 \
    http://127.0.0.1:8081/kasmaudio >> "$logdir/audio-encoder.log" 2>&1 &
  children+=($!)
  printf 'Kasm audio output bridge started (WSS port %s).\n' "${AUDIO_PORT:-4901}"
  wait -n "${children[@]}" || true
  cleanup
  children=()
  printf 'Audio bridge exited; retrying in two seconds.\n' >&2
  sleep 2
done

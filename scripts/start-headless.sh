#!/bin/bash
set -euo pipefail
stream_backend=${OMARCHY_STREAM_BACKEND:-kasmvnc}
case "$stream_backend" in
  kasmvnc|novnc|selkies) ;;
  *) printf 'Unknown streaming backend: %s\n' "$stream_backend" >&2; exit 1 ;;
esac
if [[ ${1:-} != --session ]]; then
  exec dbus-run-session -- "$0" --session
fi

export USER="$(whoami)"
export XDG_RUNTIME_DIR=/run/user/$(id -u)
mkdir -p "$XDG_RUNTIME_DIR" "$HOME/.local/state/omarchy" "$HOME/.config"
chmod 700 "$XDG_RUNTIME_DIR"
logdir="$HOME/.local/state/omarchy/kasm-logs"
mkdir -p "$logdir"

if [[ ! -r ${AQ_HEADLESS_RENDER_NODE} || ! -w ${AQ_HEADLESS_RENDER_NODE} ]]; then
  printf 'Render node %s must be mapped into the container and writable by UID %s.\n' "$AQ_HEADLESS_RENDER_NODE" "$(id -u)" >&2
  exit 1
fi

if [[ ! -e "$HOME/.config/omarchy/kasm-profile-initialized" ]]; then
  cp -r --update=none /etc/skel/.config/. "$HOME/.config/"
  if [[ -d /etc/skel/.local/state ]]; then
    mkdir -p "$HOME/.local/state"
    cp -r --update=none /etc/skel/.local/state/. "$HOME/.local/state/"
  fi
  if [[ ${OMARCHY_DESKTOP_PROFILE:-essentials} != full ]]; then
    # Match Omarchy's supported opt-out for the smaller essentials image.
    touch "$HOME/.local/state/omarchy/preinstalls-removed"
    MISE_OFFLINE=true omarchy-mise-default-tools disable
  fi
  OMARCHY_THEME_HEADLESS=1 omarchy-theme-set 'Tokyo Night'
  touch "$HOME/.config/omarchy/kasm-profile-initialized"
fi
# Omarchy's normal terminal preference and interactive Bash environment.
if [[ ! -e "$HOME/.config/omarchy/kasm-shell-initialized" ]]; then
  [[ -e "$HOME/.bashrc" ]] || cp "$OMARCHY_PATH/default/bashrc" "$HOME/.bashrc"
  [[ -e "$HOME/.XCompose" ]] || cp "$OMARCHY_PATH/default/xcompose" "$HOME/.XCompose"
  touch "$HOME/.config/omarchy/kasm-shell-initialized"
fi
export XDG_CURRENT_DESKTOP=Hyprland XDG_SESSION_DESKTOP=Hyprland XDG_SESSION_TYPE=wayland
export XCURSOR_THEME="${XCURSOR_THEME:-default}" XCURSOR_SIZE=24 HYPRCURSOR_SIZE=24
/usr/local/bin/omarchy-configure-user
/usr/local/bin/omarchy-configure-editor
for hook in /dockerstartup/profile.d/*.sh; do
  [[ ! -f $hook ]] || "$hook"
done

# Use Omarchy's packaged session defaults and user environment overrides just
# as its normal session loader does, before starting the compositor.
set +u
for environment_file in "$OMARCHY_PATH"/default/uwsm/env.d/* \
    "${XDG_CONFIG_HOME:-$HOME/.config}"/uwsm/env \
    "${XDG_CONFIG_HOME:-$HOME/.config}"/uwsm/env.d/*; do
  [[ ! -f $environment_file || ! -r $environment_file ]] || source "$environment_file"
done
set -u

# Keep upstream defaults intact. Only replace its systemd/hardware autostart.
if [[ $stream_backend == kasmvnc ]]; then
  output_name=KASM
  read -r OMARCHY_DISPLAY_WIDTH OMARCHY_DISPLAY_HEIGHT < <(DISPLAY=:1 xdotool getdisplaygeometry)
else
  # WayVNC permits remote resizing only for HEADLESS-/NOOP- output names.
  output_name=HEADLESS-1
  size=${OMARCHY_RESOLUTION:-1920x1080}
  if [[ $stream_backend == selkies ]]; then
    size=${OMARCHY_RESOLUTION:-${VNC_RESOLUTION:-1920x1080}}
  fi
  [[ $size =~ ^([0-9]{2,5})x([0-9]{2,5})$ ]] || { printf 'Invalid resolution: %s\n' "$size" >&2; exit 1; }
  OMARCHY_DISPLAY_WIDTH=$((10#${BASH_REMATCH[1]}))
  OMARCHY_DISPLAY_HEIGHT=$((10#${BASH_REMATCH[2]}))
  (( OMARCHY_DISPLAY_WIDTH >= 32 && OMARCHY_DISPLAY_WIDTH <= 16384 &&
     OMARCHY_DISPLAY_HEIGHT >= 32 && OMARCHY_DISPLAY_HEIGHT <= 16384 )) || exit 1
  unset DISPLAY XAUTHORITY
fi
printf 'hl.monitor({output="%s",mode="%sx%s@60",position="0x0",scale=1})\n' \
  "$output_name" "$OMARCHY_DISPLAY_WIDTH" "$OMARCHY_DISPLAY_HEIGHT" > "$XDG_RUNTIME_DIR/kasm-monitor.lua"
config="$XDG_RUNTIME_DIR/hyprland.lua"
cat > "$config" <<'LUA'
-- Upstream's user entrypoint remains authoritative. Only its systemd/hardware
-- autostart module is supplied by this container's process supervisor instead.
package.preload["default.hypr.autostart"] = function() end
dofile(os.getenv("HOME") .. "/.config/hypr/hyprland.lua")
dofile(os.getenv("XDG_RUNTIME_DIR") .. "/kasm-monitor.lua")
dofile("/usr/local/share/omarchy-kasm/bindings.lua")
if os.getenv("OMARCHY_STREAM_BACKEND") == "selkies" and os.getenv("OMARCHY_DYNAMIC_RESIZE") ~= "0" then
  -- Output-management changes are applied during render prechecks. An idle
  -- headless desktop otherwise leaves the request pending until capture times
  -- out. Keep its render clock active even when no application damages pixels.
  hl.config({debug = {vfr = false}})
end
if os.getenv("AQ_HEADLESS_VIRTUAL_CURSOR") == "1" then
  -- The virtual plane uses a render-node GBM buffer, not a DRM dumb cursor BO.
  hl.config({cursor = {no_hardware_cursors = 0, use_cpu_buffer = 0}})
end
LUA

export LD_LIBRARY_PATH="/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export GBM_BACKENDS_PATH=/usr/lib/x86_64-linux-gnu/gbm
export __EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/10_nvidia.json
AQ_BACKEND=headless LD_PRELOAD=/usr/local/lib/omarchy-headless-render-node.so \
  start-hyprland -- --config "$config" > "$logdir/hyprland.log" 2>&1 &
hypr_pid=$!
children=($hypr_pid)
trap 'kill "${children[@]}" 2>/dev/null || true' EXIT
trap 'exit 0' TERM INT

instance=''
for ((attempt=0; attempt<100; attempt++)); do
  kill -0 "$hypr_pid" || { printf 'Hyprland exited. See %s/hyprland.log\n' "$logdir" >&2; exit 1; }
  # A restarted container can retain old instance directories whose PID has
  # been reused. Require responsive IPC instead of trusting the first entry.
  while IFS= read -r candidate; do
    if hyprctl -i "$candidate" -j version >/dev/null 2>&1; then
      instance=$candidate
      break
    fi
  done < <(hyprctl instances -j | jq -r '.[].instance' 2>/dev/null || true)
  [[ -z $instance ]] || break
  sleep 0.2
done
[[ -n $instance ]] || { printf 'Timed out waiting for Hyprland IPC.\n' >&2; exit 1; }
export HYPRLAND_INSTANCE_SIGNATURE=$instance
export WAYLAND_DISPLAY=$(hyprctl instances -j | jq -r --arg instance "$instance" '.[] | select(.instance == $instance) | .wl_socket')
event_socket="$XDG_RUNTIME_DIR/hypr/$instance/.socket2.sock"
for ((attempt=0; attempt<100; attempt++)); do
  [[ ! -S $event_socket ]] || break
  kill -0 "$hypr_pid" || exit 1
  sleep 0.1
done
[[ -S $event_socket ]] || { printf 'Timed out waiting for Hyprland event socket.\n' >&2; exit 1; }
hyprctl output create headless "$output_name"
if [[ ${AQ_HEADLESS_VIRTUAL_CURSOR:-0} == 1 ]]; then
  # Retry the cursor plane after the output/allocator is ready. The first
  # cursor image can be requested while the initial render context is active.
  hyprctl setcursor "$XCURSOR_THEME" "$XCURSOR_SIZE"
fi
if [[ $stream_backend != kasmvnc ]]; then
  # hl.env changes apply to compositor-launched children, not this original
  # supervisor. Import that actual environment before launching Quickshell.
  graphical_environment=$(/usr/local/bin/omarchy-import-session-env)
  eval "$graphical_environment"
  unset graphical_environment
  dbus-update-activation-environment --all
else
  dbus-update-activation-environment WAYLAND_DISPLAY HYPRLAND_INSTANCE_SIGNATURE XDG_RUNTIME_DIR \
    XDG_CURRENT_DESKTOP XDG_SESSION_DESKTOP XDG_SESSION_TYPE OMARCHY_PATH
fi
if [[ $stream_backend == kasmvnc ]]; then
  DISPLAY=:1 python /usr/local/bin/omarchy-sync-display.py > "$logdir/resize.log" 2>&1 &
  children+=($!)
fi

pipewire > "$logdir/pipewire.log" 2>&1 &
children+=($!)
pipewire-pulse > "$logdir/pipewire-pulse.log" 2>&1 &
children+=($!)
wireplumber > "$logdir/wireplumber.log" 2>&1 &
children+=($!)
if [[ $stream_backend == kasmvnc ]]; then
  QT_QPA_PLATFORM=wayland quickshell -n -p "$OMARCHY_PATH/shell" > "$logdir/shell.log" 2>&1 &
else
  quickshell -n -p "$OMARCHY_PATH/shell" > "$logdir/shell.log" 2>&1 &
fi
children+=($!)
if [[ $stream_backend == selkies ]]; then
  export OMARCHY_DISPLAY_WIDTH OMARCHY_DISPLAY_HEIGHT
  mkdir -p "$HOME/.vnc"
  if [[ ! -s $HOME/.vnc/self.pem ]]; then
    (umask 077; openssl req -x509 -newkey rsa:2048 -nodes -days 365 \
      -subj /CN=kasm -keyout "$HOME/.vnc/self.pem" -out "$HOME/.vnc/self.pem") \
      > "$logdir/selkies-tls.log" 2>&1
  fi
  if [[ ${KASM_SVC_AUDIO:-0} == 1 ]]; then
    /dockerstartup/start-audio.sh > "$logdir/audio-startup.log" 2>&1 &
    children+=($!)
  fi
  /usr/local/bin/omarchy-start-selkies > "$logdir/selkies.log" 2>&1 &
  children+=($!)
else
wayvnc -C /etc/omarchy-wayvnc.ini -o "$output_name" -f 60 -v > "$logdir/wayvnc.log" 2>&1 &
wayvnc_pid=$!
children+=($wayvnc_pid)
for ((attempt=0; attempt<100; attempt++)); do
  kill -0 "$wayvnc_pid" || { printf 'WayVNC exited. See %s/wayvnc.log\n' "$logdir" >&2; exit 1; }
  if (exec 3<>/dev/tcp/127.0.0.1/5902) 2>/dev/null; then break; fi
  sleep 0.2
done
if [[ $stream_backend == kasmvnc ]]; then
  # Raw encoding avoids a compress/decompress hop on this loopback-only bridge.
  DISPLAY=:1 vncviewer -FullScreen -Shared -SecurityTypes None -RemoteResize=0 -ShortcutModifiers Ctrl,Alt,Shift,Super \
    -PreferredEncoding Raw -AutoSelect=0 -FullColor -PointerEventInterval 0 \
    127.0.0.1:5902 > "$logdir/viewer.log" 2>&1 &
  children+=($!)
else
  # Websockify forwards RFB bytes; it never decodes or recaptures the desktop.
  auth_args=()
  if [[ -n ${KASM_ID:-} || ${OMARCHY_NOVNC_AUTH:-0} == 1 ]]; then
    [[ -n ${VNC_PW:-} ]] || { printf 'VNC_PW is required for Kasm streaming.\n' >&2; exit 1; }
    auth_args=(--web-auth --auth-plugin omarchy_novnc_auth.SessionAuth)
  fi
  openssl req -x509 -newkey rsa:2048 -nodes -days 30 -subj /CN=localhost \
    -keyout "$XDG_RUNTIME_DIR/novnc-key.pem" -out "$XDG_RUNTIME_DIR/novnc-cert.pem" \
    > "$logdir/novnc-tls.log" 2>&1
  chmod 600 "$XDG_RUNTIME_DIR/novnc-key.pem"
  PYTHONPATH=/usr/local/share/omarchy-kasm /opt/novnc-proxy/bin/websockify --web /opt/noVNC --ssl-only \
    "${auth_args[@]}" \
    --cert "$XDG_RUNTIME_DIR/novnc-cert.pem" --key "$XDG_RUNTIME_DIR/novnc-key.pem" \
    0.0.0.0:6901 127.0.0.1:5902 > "$logdir/websockify.log" 2>&1 &
  children+=($!)
fi
fi
printf 'Omarchy Quattro compositor, shell, and %s streaming started. Logs: %s\n' "$stream_backend" "$logdir"
wait -n "${children[@]}"
printf 'A session component exited; stopping the session. Check %s\n' "$logdir" >&2
exit 1

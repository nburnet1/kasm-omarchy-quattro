#!/bin/bash
set -euo pipefail

# Experimental Omarchy/Quattro session launcher for Kasm (X11/VNC context).
# Omarchy Quattro is Hyprland+Quickshell (Wayland-first); this may not work under KasmVNC.
# We try Hyprland if available, else fall back to a basic shell/terminal.

log() { echo "[omarchy-custom-startup] $*"; }

start_fallback() {
  if command -v foot >/dev/null 2>&1; then
    foot &
  elif command -v xterm >/dev/null 2>&1; then
    xterm &
  elif command -v alacritty >/dev/null 2>&1; then
    alacritty &
  fi
}

wait_for_x() {
  for _ in $(seq 1 30); do
    if DISPLAY=:1 xdpyinfo >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  return 1
}

wait_for_x || log "X display :1 not ready"

# If Hyprland is installed, attempt to start it. Note: requires Wayland-capable environment;
# inside KasmVNC (X11) this is unlikely to produce a usable desktop.
if command -v Hyprland >/dev/null 2>&1; then
  log "Hyprland binary found; attempting launch (experimental)"
  export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/tmp/xdg-runtime-$(id -u)}"
  mkdir -p "$XDG_RUNTIME_DIR"
  chmod 700 "$XDG_RUNTIME_DIR" || true
  # Try nested/headless-friendly env hints; behavior depends on host/container capabilities.
  Hyprland >/tmp/hyprland.log 2>&1 &
  sleep 3
  if ! pgrep -x Hyprland >/dev/null 2>&1; then
    log "Hyprland did not stay running; see /tmp/hyprland.log"
    start_fallback
  fi
else
  log "Hyprland not installed; starting fallback session"
  start_fallback
fi

# Keep script alive briefly so Kasm startup sees it; main session is managed by WM/desktop.
wait

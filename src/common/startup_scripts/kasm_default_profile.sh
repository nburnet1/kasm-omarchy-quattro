#!/usr/bin/env bash
set -e
DEFAULT_PROFILE_HOME=${KASM_DEFAULT_PROFILE_HOME:-/home/kasm-default-profile}

function copy_default_profile_to_home {
    echo "Copying default profile to home directory"
    mkdir -p "$HOME"
    if [ "$DEFAULT_PROFILE_HOME" != "$HOME" ] && [ -d "$DEFAULT_PROFILE_HOME" ]; then
      cp -r "$DEFAULT_PROFILE_HOME/." "$HOME/"
    fi
    ls -la "$HOME" || true
}

function verify_profile_config {
    echo "Verifying Uploads/Downloads Configurations"
    mkdir -p "$HOME/Uploads" "$HOME/Downloads" "$HOME/Desktop" || true

    if [ -e "$HOME/Desktop/Uploads" ] || [ -L "$HOME/Desktop/Uploads" ]; then :; else ln -sf "$HOME/Uploads" "$HOME/Desktop/Uploads" 2>/dev/null || true; fi
    if [ -e "$HOME/Desktop/Downloads" ] || [ -L "$HOME/Desktop/Downloads" ]; then :; else ln -sf "$HOME/Downloads" "$HOME/Desktop/Downloads" 2>/dev/null || true; fi

    if [ -n "${KASM_VNC_PATH:-}" ] && [ -d "$KASM_VNC_PATH/www/Downloads" ]; then
      rm -f "$KASM_VNC_PATH/www/Downloads/Downloads" 2>/dev/null || true
      ln -sf "$HOME/Downloads" "$KASM_VNC_PATH/www/Downloads/Downloads" 2>/dev/null || true
    fi
}

if [ -f "$HOME/.bashrc" ] || [ -d "$HOME/.config" ]; then
    echo "Profile already exists. Will not copy default contents"
else
    copy_default_profile_to_home
fi

verify_profile_config
rm -rf "$HOME/.config/pulse" 2>/dev/null || true
mkdir -p "$HOME/.vnc" || true

echo -e "\n\n------------------ EXECUTE COMMAND ------------------"
echo "Executing command: '$@'"
exec "$@"

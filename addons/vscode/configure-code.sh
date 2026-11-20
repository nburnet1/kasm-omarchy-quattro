#!/bin/bash
set -euo pipefail

config_dir="${XDG_CONFIG_HOME:-$HOME/.config}"
mkdir -p "$config_dir"
# The stock Code launcher reads this file. Docker's default namespace policy
# prevents Electron's internal sandbox from starting. Scope the exception to
# Code, and retain sandboxing on hosts where unprivileged namespaces do work.
if ! unshare --user --map-root-user true 2>/dev/null; then
  flags="$config_dir/code-flags.conf"
  if [[ ! -f $flags ]] || ! grep -Fxq -- '--no-sandbox' "$flags"; then
    printf '\n# Required by the Kasm container namespace policy.\n--no-sandbox\n' >> "$flags"
  fi
fi

# Match the defaults seeded by omarchy-install-editor-vscode without replacing
# any existing user settings or launching a GUI before the compositor is ready.
mkdir -p "$HOME/.vscode" "$config_dir/Code/User"
if [[ ! -e $HOME/.vscode/argv.json ]]; then
  printf '{"password-store":"gnome-libsecret"}\n' > "$HOME/.vscode/argv.json"
fi
if [[ ! -e $config_dir/Code/User/settings.json ]]; then
  printf '{"update.mode":"none"}\n' > "$config_dir/Code/User/settings.json"
fi

# Omarchy seeds its default keyring during user provisioning. Do the same here
# so a fresh container does not block Code behind a keyring-creation dialog.
if command -v gnome-keyring-daemon >/dev/null 2>&1; then
  bash "$OMARCHY_PATH/install/user/default-keyring.sh"
fi

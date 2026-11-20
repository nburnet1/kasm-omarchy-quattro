#!/bin/bash
set -euo pipefail

# Preserve existing profile preferences; only complete a new essentials profile.
mkdir -p "$HOME/.local/share/applications" "$HOME/.config"
# The settings package generates additional defaults (including branding) that
# are not present in the raw source config tree. Never overwrite user edits.
cp -r --update=none /etc/skel/.config/. "$HOME/.config/"
for entry in foot imv mpv omarchy-browser; do
  if [[ ! -e $HOME/.local/share/applications/$entry.desktop ]]; then
    cp "$OMARCHY_PATH/applications/$entry.desktop" "$HOME/.local/share/applications/"
  fi
done
if [[ ! -e $HOME/.config/mimeapps.list ]]; then
  cp "$OMARCHY_PATH/default/applications/mimeapps.list" "$HOME/.config/mimeapps.list"
fi
update-desktop-database "$HOME/.local/share/applications"
bash "$OMARCHY_PATH/install/user/default-keyring.sh"
if [[ ! -e $HOME/.config/user-dirs.dirs ]]; then
  xdg-user-dirs-update
fi

# Chromium's native flags file scopes the namespace workaround to that browser.
if ! unshare --user --map-root-user true 2>/dev/null; then
  flags="$HOME/.config/chromium-flags.conf"
  if [[ ! -f $flags ]] || ! grep -Fxq -- '--no-sandbox' "$flags"; then
    printf '\n# Container namespace policy prevents the Chromium sandbox.\n--no-sandbox\n' >> "$flags"
  fi
fi

#!/bin/bash
set -euo pipefail
mapfile -t packages < <(sed -e 's/[[:space:]]*#.*$//' -e '/^[[:space:]]*$/d' /usr/local/share/omarchy-kasm/expected-apps.packages)
omarchy-pkg-add "${packages[@]}"
patch --batch --forward -p1 -d /usr/bin < /usr/local/share/omarchy-kasm/omarchy-4.5.0-container.patch

# Remove only early prototype applications that the current bridge no longer uses.
for package in alacritty weston xterm; do
  if pacman -Q "$package" >/dev/null 2>&1; then
    omarchy-pkg-drop "$package"
  fi
done
rm -rf /opt/omarchy
if pacman -Q visual-studio-code-bin >/dev/null 2>&1 || pacman -Q code >/dev/null 2>&1 || command -v code >/dev/null 2>&1; then
  echo 'VS Code must not be present in the essentials base.' >&2
  exit 1
fi

#!/bin/bash
set -euo pipefail

# omarchy-nvim normally seeds these through useradd's /etc/skel copy. Kasm
# initializes profiles separately, so seed only missing trees for its user.
for relative in .config/nvim .local/share/nvim; do
  source_dir="/etc/skel/$relative"
  destination="$HOME/$relative"
  if [[ ! -e $destination && -d $source_dir ]]; then
    mkdir -p "${destination%/*}"
    cp -r "$source_dir" "$destination"
  fi
done

#!/usr/bin/env bash
# Extend the tested runtime without replacing its compositor/plugin ABI.
set -euo pipefail
export OMARCHY_ALLOW_DIRECT_PACMAN=1 SYSTEMD_OFFLINE=1
destination=/usr/local/share/omarchy-kasm
mkdir -p "$destination"
omarchy-pkg-defaults x86 > "$destination/upstream-defaults.packages"
mapfile -t packages < "$destination/upstream-defaults.packages"
stack=(hyprland aquamarine omarchy omarchy-hyprland-titlebars)
before=$(pacman -Q "${stack[@]}")
# pacman -T understands providers (nvim is provided by neovim). Its exit code
# 127 means unsatisfied dependencies, not a failure to execute the command.
status=0
missing=$(pacman -T -- "${packages[@]}") || status=$?
[[ $status == 0 || $status == 127 ]] || exit "$status"
if [[ -n $missing ]]; then
  mapfile -t additions <<< "$missing"
  # Use the base's synchronized package databases, not a partial rolling upgrade.
  # Rolling mirrors can retire these exact versions. Recover them from Arch's
  # archive; pacman still verifies package signatures with its trusted keyring.
  if ! pacman --disable-sandbox -Sw --needed --noconfirm -- "${additions[@]}"; then
    while read -r repository name filename; do
      [[ -f /var/cache/pacman/pkg/$filename && -f /var/cache/pacman/pkg/$filename.sig ]] && continue
      case "$repository" in
        core|extra)
          for suffix in '' .sig; do
            curl -fsSL --retry 3 "https://archive.archlinux.org/packages/${name:0:1}/$name/$filename$suffix" \
              -o "/var/cache/pacman/pkg/$filename$suffix.part"
            mv "/var/cache/pacman/pkg/$filename$suffix.part" "/var/cache/pacman/pkg/$filename$suffix"
          done
          ;;
      esac
    done < <(pacman -Sp --needed --print-format '%r %n %f' -- "${additions[@]}")
  fi
  pacman --disable-sandbox -S --needed --noconfirm -- "${additions[@]}"
fi
pacman -T -- "${packages[@]}"
[[ $(pacman -Q "${stack[@]}") == "$before" ]] || {
  printf 'The verified compositor stack changed during package installation.\n' >&2
  exit 1
}
pacman -Dk
pacman -Q > "$destination/installed-packages.txt"
command -v vipsthumbnail
command -v ffmpegthumbnailer

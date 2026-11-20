#!/bin/bash
set -euo pipefail

# Omarchy's patched Quickshell, with the upstream keyring and package signature.
# Bootstrap the keyring from a pinned hash before trusting its signing keys.
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
base=https://pkgs.omarchy.org/stable/x86_64
curl -fsSL "$base/omarchy-keyring-20251027-1-any.pkg.tar.zst" -o "$tmp/keyring.pkg.tar.zst"
curl -fsSL "$base/quickshell-0.3.2.r7.g2b4501a-1-x86_64.pkg.tar.zst" -o "$tmp/quickshell.pkg.tar.zst"
curl -fsSL "$base/quickshell-0.3.2.r7.g2b4501a-1-x86_64.pkg.tar.zst.sig" -o "$tmp/quickshell.pkg.tar.zst.sig"
python - "$tmp" <<'PY'
import hashlib, pathlib, sys
root = pathlib.Path(sys.argv[1])
for name, expected in {
    "keyring.pkg.tar.zst": "f4bc258879f493462736f9a072c4f4c7f753eb559f6b346f5bdf8ed816f75f66",
    "quickshell.pkg.tar.zst": "f9f813213597d1ee25e16860ed326e810857810460c09ee87d06bc3b655c2da1",
}.items():
    actual = hashlib.sha256((root / name).read_bytes()).hexdigest()
    if actual != expected:
        raise SystemExit(f"Hash mismatch for {name}")
PY
pacman-key --init
pacman -U --noconfirm "$tmp/keyring.pkg.tar.zst"
pacman-key --populate omarchy
pacman-key --verify "$tmp/quickshell.pkg.tar.zst.sig" "$tmp/quickshell.pkg.tar.zst"
pacman -U --noconfirm "$tmp/quickshell.pkg.tar.zst"
# Make the upstream menu's package installers able to find Omarchy packages.
python <<'PY'
from pathlib import Path
path = Path('/etc/pacman.conf')
config = path.read_text()
if '\n[omarchy]\n' not in config:
    path.write_text(config + '\n[omarchy]\nServer = https://pkgs.omarchy.org/stable/$arch\n')
PY
pacman -Sy --noconfirm

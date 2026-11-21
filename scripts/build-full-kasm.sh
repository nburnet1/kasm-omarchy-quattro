#!/usr/bin/env bash
set -euo pipefail
root=$(dirname "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")")
base=${FULL_KASM_BASE_IMAGE:-kasm-omarchy-quattro:4.5.0-selkies-local-cursor-test}
image=${FULL_KASM_IMAGE:-kasm-omarchy-quattro:4.5.0-1}
docker image inspect "$base" >/dev/null
docker build --network host -f "$root/Dockerfile.full-kasm" \
  --build-arg "BASE_IMAGE=$base" -t "$image" "$root"
docker image inspect --format '{{.Id}}' "$image"

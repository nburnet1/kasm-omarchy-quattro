#!/usr/bin/env bash
set -euo pipefail
root=$(dirname "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")")
base=${FULL_KASM_BASE_IMAGE:-kasm-omarchy-quattro:4.5.0-selkies-local-cursor-test}
image=${FULL_KASM_IMAGE:-kasm-omarchy-quattro:4.5.0-1}
if ! docker image inspect "$base" >/dev/null 2>&1; then
  printf 'Parent image is not available locally: %s\nRun bash scripts/build.sh to build the complete parent chain.\n' "$base" >&2
  exit 1
fi
docker build --network host -f "$root/Dockerfile.full-kasm" \
  --build-arg "BASE_IMAGE=$base" -t "$image" "$root"
docker image inspect --format '{{.Id}}' "$image"

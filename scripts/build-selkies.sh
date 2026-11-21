#!/usr/bin/env bash
# Rebuild the current adapter, optionally including its complete parent chain.
set -euo pipefail
root=$(dirname "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")")
image=${SELKIES_IMAGE:-kasm-omarchy-quattro:4.5.0-selkies-local-cursor-test}
audio_base=${AUDIO_BASE_IMAGE:-kasm-omarchy-quattro:4.5.0-audio}
case "${1:-}" in
  --from-scratch)
    docker build --network host -f "$root/Dockerfile" -t kasm-omarchy-quattro:experimental "$root"
    docker build --network host -f "$root/Dockerfile.runtime" -t kasm-omarchy-quattro:runtime "$root"
    docker build --network host -f "$root/Dockerfile.headless" -t kasm-omarchy-quattro:essentials-core "$root"
    docker build --network host -f "$root/Dockerfile.titlebars" -t kasm-omarchy-quattro:essentials-desktop "$root"
    docker build --network host -f "$root/Dockerfile.audio" -t "$audio_base" "$root"
    ;;
  '')
    docker image inspect "$audio_base" >/dev/null
    ;;
  *)
    printf 'Usage: bash scripts/build-selkies.sh [--from-scratch]\n' >&2
    exit 2
    ;;
esac
docker build --network host -f "$root/Dockerfile.selkies" \
  --build-arg "BASE_IMAGE=$audio_base" -t "$image" "$root"
docker image inspect --format '{{.Id}}' "$image"

#!/usr/bin/env bash
# Build the complete local Kasm image, including its parent chain by default.
set -euo pipefail
root=$(dirname "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")")
image=${FULL_KASM_IMAGE:-kasm-omarchy-quattro:4.5.0-1}
parent=${FULL_KASM_BASE_IMAGE:-${SELKIES_IMAGE:-kasm-omarchy-quattro:4.5.0-selkies-local-cursor-test}}
reuse_parent=false
dry_run=false

usage() {
  printf '%s\n' \
    'Usage: bash scripts/build.sh [--tag IMAGE:TAG] [--reuse-parent] [--dry-run]' \
    '' \
    'Builds all parent stages and the complete desktop image locally.' \
    '  --tag IMAGE:TAG  Override the final local image name.' \
    '  --reuse-parent   Extend an existing Selkies parent instead of rebuilding it.' \
    '  --dry-run        Print the build commands without contacting Docker.'
}

while (($#)); do
  case "$1" in
    --tag)
      if [[ $# -lt 2 || -z ${2:-} || $2 == -* ]]; then
        printf '%s\n' '--tag requires an image name and tag.' >&2
        exit 2
      fi
      image=$2
      shift 2
      ;;
    --reuse-parent) reuse_parent=true; shift ;;
    --dry-run) dry_run=true; shift ;;
    --help|-h) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
  esac
done

run() {
  if $dry_run; then
    printf '%q ' "$@"
    printf '\n'
  else
    "$@"
  fi
}

if ! $dry_run; then
  [[ $(uname -s) == Linux && $(uname -m) == x86_64 ]] || {
    printf '%s\n' 'This build currently supports Linux x86-64 hosts.' >&2
    exit 1
  }
  command -v docker >/dev/null || {
    printf '%s\n' 'Docker is required to build this image.' >&2
    exit 1
  }
  docker info >/dev/null
  export DOCKER_BUILDKIT=1
fi

if ! $reuse_parent; then
  run env "SELKIES_IMAGE=$parent" bash "$root/scripts/build-selkies.sh" --from-scratch
fi
run env "FULL_KASM_BASE_IMAGE=$parent" "FULL_KASM_IMAGE=$image" bash "$root/scripts/build-full-kasm.sh"
if $dry_run; then
  printf '\n%s\n' "Planned local workspace image: $image"
else
  printf '\n%s\n%s\n' "Built local workspace image: $image" 'Use this tag in the Kasm workspace Docker Image field, then launch a new session.'
fi

# Building and reproducing the current desktop

For your first workspace launch, use [GETTING-STARTED.md](GETTING-STARTED.md).
This guide covers source builds and optional personal configuration. The current
image ID and desktop verification results are in [FULL-KASM.md](FULL-KASM.md).

## What lives where

- **This repository:** Kasm/container startup, GPU adaptation, Selkies streaming,
  cursor/input integration, package-install recipes, and verification tools.
- **[omarchy-dotfiles](https://github.com/nburnet1/omarchy-dotfiles):** optional
  personal Hyprland/shell configuration, workspace widget, and Ignition Designer
  setup helper.
- **The persistent user home:** downloaded Designer Launcher, gateway entries,
  application caches/projects, credentials, and backups. These are not packaged
  in either repository or the desktop image.

## Build from source

Run commands on a Linux x86-64 Docker build host, from the repository root:

```bash
git clone https://github.com/nburnet1/kasm-omarchy-quattro.git
cd kasm-omarchy-quattro
```

The build scripts use Docker BuildKit. Network access is needed for Arch,
Omarchy, Python, and Kasm dependencies. GPU access is needed when running and
verifying the desktop, not for these image-build commands.

### If you already have the verified Selkies parent

```bash
docker image inspect kasm-omarchy-quattro:4.5.0-selkies-local-cursor-test
bash scripts/build-full-kasm.sh
```

This is the path used for the verified full-desktop candidate. It installs
missing upstream default packages and refreshes the startup/render/input
adapter while preserving the tested compositor stack.

### If you have the audio-enabled parent

Build the Selkies layer, then the complete package profile:

```bash
bash scripts/build-selkies.sh
bash scripts/build-full-kasm.sh
```

### On a clean build host

The complete source build chain is:

```bash
bash scripts/build-selkies.sh --from-scratch
bash scripts/build-full-kasm.sh
```

`--from-scratch` builds the base, runtime, headless compositor, titlebar plugin,
audio, and Selkies stages in order. `build-full-kasm.sh` then adds the complete
desktop package set. `docker build .` alone stops at the initial base image.
Required Kasm startup inputs are committed under `src/common/`.

**Reproducibility scope:** the verified image was built from retained local
parent layers; the full clean-host chain has not been reverified end to end.
Arch repositories and Python transitive dependencies are rolling. The recipes
pin Omarchy and check compositor/plugin ABIs, so they deliberately fail when
the installed versions differ. These instructions reproduce the build
procedure, not a promise of a byte-identical image from future repositories.
Use the verified image when you need the already-tested artifact.

### Image names and overrides

| Script | Default output | Relevant overrides |
| --- | --- | --- |
| `scripts/build-selkies.sh` | `kasm-omarchy-quattro:4.5.0-selkies-local-cursor-test` | `SELKIES_IMAGE`, `AUDIO_BASE_IMAGE` |
| `scripts/build-full-kasm.sh` | `kasm-omarchy-quattro:4.5.0-1` | `FULL_KASM_IMAGE`, `FULL_KASM_BASE_IMAGE` |

For example, build a separately tagged full candidate:

```bash
FULL_KASM_IMAGE=local/omarchy-quattro:my-test bash scripts/build-full-kasm.sh
```

When overriding the Selkies output name, pass that same image as
`FULL_KASM_BASE_IMAGE` to the full-desktop helper. For `--from-scratch`,
`AUDIO_BASE_IMAGE` names the audio image that the script will build.

The tested stack is Omarchy 4.5.0-3, Hyprland 0.57.2, Aquamarine 0.16.0,
Selkies 2.2.1, and pixelflux 2.2.3. The complete package profile and dependency
checks are described in [FULL-KASM.md](FULL-KASM.md#build).

## Publish a verified image

Release names use `UPSTREAM_VERSION-KASM_REVISION`, for example `4.5.0-1`.
Increment the Kasm revision for later builds of the same Omarchy version rather
than replacing an existing release tag.

After verifying a runtime image, `Dockerfile.release` adds publication metadata
without rebuilding or modifying its filesystem. For the initial release:

```bash
docker build -f Dockerfile.release \
  --build-arg BASE_IMAGE=kasm-omarchy-quattro:4.5.0-1 \
  --build-arg RELEASE_VERSION=4.5.0-1 \
  --build-arg VCS_REF="$(git rev-parse HEAD)" \
  -t ghcr.io/nburnet1/kasm-omarchy-quattro:4.5.0-1 .
docker push ghcr.io/nburnet1/kasm-omarchy-quattro:4.5.0-1
```

Publishing requires GHCR credentials with `write:packages` and access to the
package. The source label links the image to this repository, and the revision
label identifies the committed source used for publication. The package remains
private; consumers need access and `read:packages` credentials. See
[Getting started](GETTING-STARTED.md#1-make-the-image-available) for pull setup.

## Run and verify

Follow [Kasm workspace setup](GETTING-STARTED.md#2-configure-the-kasm-workspace)
for GPU allocation, render-node mapping, shared memory, and persistent profiles.
Kasm supplies the session credentials. Runtime startup exports
`USER="$(whoami)"` and imports the actual compositor environment for applications.

Image changes take effect only in a **new session**. An existing container can
keep running an older image even after its tag points to a newer build.

The test tools run against a labeled disposable desktop and a localhost
prefix/auth proxy, with Playwright in a separate browser fixture. They launch
applications and change desktop state. See
[Selkies verification](SELKIES-KASM.md#verification-performed) and the full-profile
[verification results](FULL-KASM.md#verification) for requirements and scope.

The Kasm agent on the test host prunes unused images. Keep a required rollback
image referenced by a workspace/container. A lightweight retention container
can keep an image available without starting another desktop:

```bash
docker run -d --name omarchy-image-cache --read-only --network none \
  --entrypoint sleep kasm-omarchy-quattro:4.5.0-1 infinity
```

## Optional personal dotfiles and Designer

Inside your desktop session:

```bash
git clone https://github.com/nburnet1/omarchy-dotfiles.git ~/omarchy-dotfiles
bash ~/omarchy-dotfiles/install.sh
```

These are personal preferences, not a prerequisite for the base desktop.
Review the dotfiles repository's README before applying them to an existing
profile.

For Ignition Designer, install the vendor Designer Launcher and initialize it
by saving a Designer entry. Save your work, close both Designer and Designer
Launcher, then run:

```bash
python3 ~/omarchy-dotfiles/scripts/configure-ignition-designer.py --scale 1
python3 ~/omarchy-dotfiles/scripts/configure-ignition-designer.py --scale 1 --check
```

The dotfiles installer runs this setup automatically when Designer Launcher is
already initialized. Shared defaults and every existing Designer entry are
updated. Launch Designer through its desktop entry so the scale setting applies
to both the launcher and project editor. The helper preserves unrelated
settings and backs up changed files locally; its README covers undo and
existing custom XML.

The user verified the popup-sharing picker fix, text rendering, and application
size. Full project rendering has not been separately certified. The dotfiles
installer also rescans plugins and reloads the shell so its custom workspace
buttons appear without restarting the desktop.

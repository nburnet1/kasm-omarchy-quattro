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

The normal entrypoint builds the entire chain:

```bash
bash scripts/build.sh
```

Options:

```bash
bash scripts/build.sh --tag local/omarchy:my-build
bash scripts/build.sh --reuse-parent
bash scripts/build.sh --dry-run
```

`--reuse-parent` uses an existing Selkies image. `--dry-run` prints the commands
without contacting Docker. The lower-level scripts below are useful when
rebuilding or diagnosing individual stages.

### If you already have the verified Selkies parent

```bash
docker image inspect kasm-omarchy-quattro:4.5.0-selkies-local-cursor-test
bash scripts/build.sh --reuse-parent
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

The complete source build chain can be run with one command:

```bash
bash scripts/build.sh
```

This runs the following lower-level commands in order:

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
Run the desktop verification checks for your local build before relying on it.

### Image names and overrides

| Script | Default output | Relevant overrides |
| --- | --- | --- |
| `scripts/build.sh` | `kasm-omarchy-quattro:4.5.0-1` | `--tag`, `--reuse-parent`, `--dry-run`; parent/image environment overrides below |
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

## Image naming and agent transfer

Release names use `UPSTREAM_VERSION-KASM_REVISION`, for example `4.5.0-1`.
Increment the Kasm revision for later builds of the same Omarchy version.

Images are built locally rather than downloaded from GHCR. If the build host
is separate from your Kasm agent, transfer the image over SSH:

```bash
docker image save kasm-omarchy-quattro:4.5.0-1 \
  | ssh USER@KASM_AGENT 'docker image load'
```

Replace `USER@KASM_AGENT` with your SSH destination. Load the image onto each
eligible agent and set the workspace's Docker Image field to that same local
tag. The full-desktop Dockerfile includes source/version labels; record the Git
commit and Docker image ID alongside your own builds.

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

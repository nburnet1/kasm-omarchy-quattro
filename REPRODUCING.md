# Recreate the verified Kasm/Selkies setup

## What lives where

- This repository: GPU/container startup, Kasm/Selkies integration, build inputs,
  verification tools, and architecture/performance notes.
- [omarchy-dotfiles](https://github.com/nburnet1/omarchy-dotfiles): personal Hyprland
  and shell configuration, workspace widget, and opt-in Designer setup command.
- Persistent user home: downloaded Designer Launcher, gateway entries, Ignition
  caches/projects, credentials, and backups. These are not included in either
  repository.

## Image build

The verified environment uses Omarchy 4.5.0-3, Hyprland 0.57.2, Aquamarine 0.16.0,
Selkies 2.2.1, and pixelflux 2.2.3 on an NVIDIA Quadro P1000. The current source
build (including the runtime username export) produces this local candidate:

```text
kasm-omarchy-quattro:4.5.0-selkies-repro-test
sha256:9dcbfa4bd9634070f4c19f0c25a7f4a28bb9d6f8937f0e10c77e22f14c7f7e4d
```

It was rebuilt from the retained audio parent and started in a disposable GPU
session. The shell inherited `USER=kasm-user` even when Docker supplied an
incorrect username, and Xwayland/Wayland displays were present. The existing
live session remains on `4.5.0-selkies-session-env-test`
(`sha256:76006d57fd6c8133ce50555664ee8610883f10407737bffd099359588e915d42`),
where the full adapter checks and user Designer appearance checks were performed.
The only runtime source change since that image is the username export.

Rebuild the adapter from the existing audio-enabled parent:

```sh
bash scripts/build-selkies.sh
```

On a host without the local parent images, the complete source build chain is:

```sh
bash scripts/build-selkies.sh --from-scratch
```

`SELKIES_IMAGE` overrides the resulting tag; `AUDIO_BASE_IMAGE` overrides the
audio parent tag (or its output tag for a full build). All required Kasm runtime
source inputs are included under `src/common/`. Session startup and the dotfiles
installer export `USER="$(whoami)"` so the runtime identity reaches child apps.

**Reproducibility scope:** this records the setup and build procedure, not a
bit-identical image rebuild. The live candidate was built using the previously
retained Code-free prototype parent described in `QUATTRO.md`. The complete
clean-host chain has not been reverified as part of publishing these repos.
Arch repositories and Python transitive dependencies are rolling; explicit
Omarchy/compositor ABI checks intentionally stop a build if those versions no
longer match. The image digest identifies the tested local image, not a registry
artifact available for pulling. Container images have not been published.

## Kasm workspace

Use the current candidate tag with an NVIDIA GPU allocation. On the tested host:

```json
{
  "devices": ["/dev/dri/renderD128:/dev/dri/renderD128:rwm"],
  "group_add": ["993"],
  "shm_size": "2g"
}
```

The device and supplementary group are host-specific. Kasm provides session
credentials; do not put them in git. Preserve `video` in
`NVIDIA_DRIVER_CAPABILITIES` if overriding it. Start a **new** session after
changing the image. Configure Kasm home/profile persistence before relying on
user-installed apps or projects surviving session deletion.

The native launch resolution comes from `VNC_RESOLUTION` (or
`OMARCHY_RESOLUTION`). The tested output was 2844×1198 at scale 1. Dynamic output
resizing is disabled; local viewer fit/scaling remains available. See
`SELKIES-KASM.md` for controls, proxy routes, audio, and verification details.

The Kasm agent on the test host prunes unused images. Keep an image referenced
by a workspace/container, or use the documented read-only, network-disabled
retention container before relying on its local tag.

## Personal dotfiles and Designer

Inside the user's desktop session:

```sh
git clone https://github.com/nburnet1/omarchy-dotfiles.git ~/omarchy-dotfiles
bash ~/omarchy-dotfiles/install.sh
```

Install the vendor Designer Launcher and save a Designer entry. Save any work,
close both Designer and Designer Launcher, then:

```sh
python3 ~/omarchy-dotfiles/scripts/configure-ignition-designer.py --scale 1
python3 ~/omarchy-dotfiles/scripts/configure-ignition-designer.py --scale 1 --check
```

The dotfiles installer runs this setup automatically once Designer Launcher is
initialized. Shared defaults and every existing Designer entry are updated.
Open Designer through its desktop entry so its scale setting applies to both
the launcher and the project editor. The dotfiles helper preserves unrelated
launcher settings and backs up changed files locally. See its README for undo
and existing-custom-XML handling.

The user confirmed the popup-sharing picker was gone, text and size were
correct, and the custom 1–5 workspace buttons were restored. The dotfiles
installer now rescans plugins and reloads the shell after stowing them. It does
not restart the desktop or change the workspace widget implementation.

## Known follow-up

Duplicate local/remote cursors in the Mac Kasm client remain to be investigated.
Do not interpret this source snapshot as a cursor fix or a complete Designer
project-rendering certification. Existing automated adapter checks and their
scope are documented in `SELKIES-KASM.md`.

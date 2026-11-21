# Omarchy Quattro for Kasm

Run the Omarchy desktop in a Kasm workspace, with a GPU-rendered Hyprland
session streamed to your browser through Selkies and NVIDIA NVENC.

**[Getting started →](GETTING-STARTED.md)** — requirements, image setup, workspace
configuration, first launch, and troubleshooting.

## What you get

- The complete **162-entry upstream Omarchy default package set**.
- Direct Wayland capture and zero-copy NVENC H.264 streaming.
- Fast local cursor movement with native cursor shapes and Mac focus recovery.
- Remote desktop resizing, fixed resolutions, and local viewer scaling.
- Kasm authentication, keyboard controls, clipboard, and browser audio output.
- Working wallpaper selection, bar transparency gestures, screenshots, and
  screen recording.
- **F18 → Super**, plus Ctrl-based shortcuts when your host captures Super/Command.

The tested stack is Omarchy **4.5.0-3**, Hyprland **0.57.2**, Aquamarine
**0.16.0**, Selkies **2.2.1**, and pixelflux **2.2.3**. Host verification used
Kasm **1.19.0-rolling**, an NVIDIA **Quadro P1000**, and driver **580.178.04**.

## Quick start

Release **4.5.0-1** packages Omarchy **4.5.0**, revision **1** of this Kasm
integration. The upstream Arch package revision (`4.5.0-3`) is separate.

```text
ghcr.io/nburnet1/kasm-omarchy-quattro:4.5.0-1
```

Pull the image on your Kasm agent:

```bash
docker pull ghcr.io/nburnet1/kasm-omarchy-quattro:4.5.0-1
```

The package is private; authenticate with a GitHub account that has access.
See [image setup](GETTING-STARTED.md#1-make-the-image-available) for credentials,
source builds, and image transfer.

1. Make the image available on the Kasm agent that will run the workspace.
2. Clone your working NVIDIA-enabled Kasm workspace and set its **Docker Image**
   to the tag above. Keep its GPU allocation and render-node mapping.
3. Launch a **new session** and choose **Remote resizing** in the client.
4. Open a terminal with **Ctrl+Shift+Enter** or **F18+Enter**.

For a new workspace, follow the [step-by-step setup](GETTING-STARTED.md#2-configure-the-kasm-workspace).
Save your work before ending a session; reconnecting to an existing container
does not load an updated image.

## Documentation

| Guide | Use it for |
| --- | --- |
| [Getting started](GETTING-STARTED.md) | First workspace, everyday controls, updates, persistence, troubleshooting |
| [Building and reproducing](REPRODUCING.md) | Source build chain, parent images, optional personal dotfiles and Ignition Designer setup |
| [Full desktop profile](FULL-KASM.md) | Package inventory, tested image ID, verification results, resize and double-click fixes |
| [Selkies/Kasm integration](SELKIES-KASM.md) | Streaming architecture, supported dashboard controls, cursor implementation, regression tests |
| [Application addons](ADDONS.md) | Derived images and user-installed applications |
| [Earlier KasmVNC implementation](QUATTRO.md) | Historical essentials profile and VNC bridge |
| [Earlier noVNC experiment](NOVNC-EXPERIMENT.md) | Historical direct-streaming prototype |

## Scope

This is an experimental **Linux x86-64 / NVIDIA** workspace image. The desktop
uses the normal Kasm container lifecycle and its existing GPU access. It does
not require systemd as PID 1, additional container capabilities, a custom host
AppArmor profile, or a separate desktop password.

The full package set is installed, but host power/storage controls and system
services such as Docker Engine, Bluetooth, and NetworkManager are not equivalent
to running Omarchy on bare metal. Microphone, webcam, printer, and file-transfer
dashboard integrations are not bridged. See the
[integration support table](SELKIES-KASM.md#supported-dashboard-integration)
for the complete list.

Personal dotfiles and Ignition Designer are optional. The image provides a
usable upstream-default desktop without them.

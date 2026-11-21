# Getting started

This guide gets the current full-desktop image running in Kasm. For source-build
details, see [REPRODUCING.md](REPRODUCING.md); for the implementation and test
results, see [FULL-KASM.md](FULL-KASM.md).

## Before you start

You need:

- A **Linux x86-64** Kasm agent with an NVIDIA GPU available to workspace
  containers. The verified setup uses Kasm 1.19.0-rolling and a Quadro P1000.
- A working NVIDIA driver and NVIDIA Container Toolkit on the agent. `nvidia-smi`
  should work on the host, and Kasm should be able to allocate the GPU.
- The GPU's DRM render node, such as `/dev/dri/renderD128`, accessible to the
  workspace user through the existing device mapping and supplementary group.
- Access to create or edit a Kasm workspace and to make an image available on
  its agent.

Start with **2 CPU cores, 4 GB RAM, one GPU, and 2 GB shared memory**. Increase
CPU/RAM for your applications. The current full image occupies approximately
**10.2 GB uncompressed**; source builds also need room for parent layers,
downloads, and build cache.

Already have a working Omarchy/NVIDIA workspace? Clone it and keep its GPU and
device settings. You only need to change the image and launch a fresh session.

## 1. Make the image available

Release **4.5.0-1** means Omarchy 4.5.0 plus revision 1 of this Kasm integration.
The registry image is:

```text
ghcr.io/nburnet1/kasm-omarchy-quattro:4.5.0-1
```

### Pull from GitHub Container Registry

The package is private. Sign in using a GitHub account with access to the
package. At the password prompt, use a personal access token (classic) with
`read:packages`, rather than your GitHub account password:

```bash
docker login ghcr.io --username YOUR_GITHUB_USERNAME
docker pull ghcr.io/nburnet1/kasm-omarchy-quattro:4.5.0-1
```

For multi-agent deployments, configure the private registry credentials in Kasm
so each eligible agent can pull the image. Access to this private source
repository does not automatically configure Docker or Kasm registry credentials.

On the Kasm agent, check whether it is already present:

```bash
docker image inspect --format '{{.Id}}' ghcr.io/nburnet1/kasm-omarchy-quattro:4.5.0-1
```

The verified runtime image ID before publication labels is recorded in
[FULL-KASM.md](FULL-KASM.md). Publication adds source/version labels without
changing its filesystem or runtime settings. A Docker image ID is different
from a registry manifest digest.

### Use a local build instead

The source-build helper produces `kasm-omarchy-quattro:4.5.0-1`. Use that local
tag in the workspace if you built the image yourself.

If the image is on a separate build host, transfer it directly to your agent:

```bash
# Run on the build host; replace USER@KASM_AGENT with your SSH destination.
docker image save kasm-omarchy-quattro:4.5.0-1 \
  | ssh USER@KASM_AGENT 'docker image load'
```

For source builds, clone this repository and follow the
[build instructions](REPRODUCING.md#build-from-source). The full-desktop helper
extends a local Selkies parent image; running `docker build .` alone builds an
older base stage, not the current desktop.

On a multi-agent Kasm deployment, make the image available on each eligible
agent or restrict the workspace to the agent that has it.

## 2. Configure the Kasm workspace

In the Kasm administration UI, clone a working GPU-enabled **Container**
workspace, or create one with these settings:

| Setting | Value |
| --- | --- |
| Name | `Omarchy Quattro` (or your preferred display name) |
| Docker Image | `ghcr.io/nburnet1/kasm-omarchy-quattro:4.5.0-1` (or your local build tag) |
| Architecture | `amd64` / x86-64 |
| CPU cores | `2` to start |
| Memory | `4096 MB` to start |
| GPU allocation | One NVIDIA GPU |
| Connection | Standard Kasm desktop/VNC connection on container port `6901` |
| Audio | Enabled; retain `KASM_SVC_AUDIO=1` if you override environment variables |

Keep the image's default entrypoint and command. Kasm supplies the session's
credentials automatically.

### GPU mapping

Check the render node and its group **on the Kasm agent**:

```bash
ls -l /dev/dri/renderD*
stat -c '%g' /dev/dri/renderD128
```

If your workspace does not already provide the mapping, use the following
**Docker Run Config Override**. Replace the device path and **993** with your
host's actual values:

```json
{
  "devices": ["/dev/dri/renderD128:/dev/dri/renderD128:rwm"],
  "group_add": ["993"],
  "shm_size": "2g"
}
```

GPU allocation and render-node access are both needed: allocating the GPU
provides NVIDIA driver libraries/devices, while the render node is used by the
headless compositor. If the render-node path differs, also set
`AQ_HEADLESS_RENDER_NODE` to that path in the workspace environment.

The image already sets `NVIDIA_DRIVER_CAPABILITIES` to include
`graphics,utility,display,video`. Preserve these if your workspace overrides it;
NVENC streaming uses `video`.

### Save files between sessions

Configure Kasm **persistent profiles** for `/home/kasm-user` if you want user
settings and files to survive session deletion. Without persistence, treat the
session home as disposable.

A persistent home preserves documents, dotfiles, application preferences, and
user-installed tools in that home. It does **not** preserve system packages
installed into a running container. Put shared system-package additions in a
[derived image](ADDONS.md#administrator-derived-images).

## 3. Launch and check the desktop

1. Save any work in the old session, then **end it**.
2. Launch the workspace from the Kasm dashboard. Reconnecting to an old session
   does not update its image or startup code.
3. In Kasm's sizing/display controls, select **Remote resizing** to make the
   desktop follow the viewer dimensions. Local scaling only fits the existing
   desktop image to the viewer.
4. Click inside the desktop, then press **Ctrl+Shift+Enter** to open a terminal.

In that terminal:

```bash
omarchy-version
```

Expected: `4.5.0-3`.

Try a few first-launch checks:

- Open the Omarchy menu with **Ctrl+Shift+Space**.
- Resize the Kasm viewer; the desktop should reflow to the new resolution.
- Double-click an empty desktop area to open the wallpaper picker, then choose
  another background.
- Double-click an **empty area of the top bar** to cycle its background style.
- Enable sound in the Kasm client. Applications should use **Kasm Audio Output**.

The installed package set includes office apps, the file manager, browser,
terminal/editor, capture utilities, input methods, and upstream Omarchy tools.
Some language tools and application data download on first use.

## Everyday controls

| Action | Shortcut or gesture |
| --- | --- |
| Open terminal | Ctrl+Shift+Enter, or Super+Enter |
| Open Omarchy menu | Ctrl+Shift+Space, or Super+Space |
| Remote Super key | **F18**; hold it with another key, then release normally |
| Open the default editor | Ctrl+Alt+E |
| Focus an adjacent window | Ctrl+Alt+Arrow |
| Switch workspace | Ctrl+Alt+1–9 / 0 |
| Move window to workspace | Ctrl+Alt+Shift+1–9 / 0 |
| Toggle fullscreen | Ctrl+Alt+F |
| Toggle floating | Ctrl+Alt+T |
| Close focused window | Ctrl+Alt+Q |
| Move / resize a window | Ctrl+Alt+left / right mouse drag |
| Terminal copy / paste | Ctrl+Shift+C / Ctrl+Shift+V |
| Toggle Kasm side panel | Ctrl+Shift+1 |

On macOS, **Ctrl means Control** and **Alt means Option**. F18 is translated to
Super inside this workspace; mapping a physical Mac key to F18 is a separate
host-side preference. No host remap is needed for the Ctrl-based shortcuts.

## Updating the image

1. Make the updated image available on the Kasm agent.
2. If its tag changed, update the workspace's **Docker Image** field.
3. Save your work and end the old session.
4. Launch a new session and repeat the first-launch checks.

Release tags identify a specific Kasm integration revision; a later revision
will use a new tag such as `4.5.0-2`. For an exact registry artifact, Docker also
supports `ghcr.io/nburnet1/kasm-omarchy-quattro@sha256:MANIFEST_DIGEST`.
Existing persistent homes keep their settings; an earlier essentials profile can retain
its optional-app/tool opt-outs. A fresh profile is the cleanest way to check
upstream defaults.

## Troubleshooting

| Symptom | First checks |
| --- | --- |
| Image pull is denied | Authenticate to GHCR using a token with `read:packages` and confirm the GitHub account has access to the private package. Configure those credentials in Kasm for agent-side pulls. |
| Workspace fails to start or shows a blank desktop | Confirm the image is on the selected agent, the GPU is allocated, the render node is mapped, and its group matches the host. Check `hyprland.log` and `selkies.log`. |
| Resizing only stretches the picture | Select **Remote resizing**, check that `OMARCHY_DYNAMIC_RESIZE` is not `0`, and launch a fresh session on the current image. |
| Wallpaper/bar double-clicks do nothing | Confirm the current image ID and start a fresh session. Use an empty desktop/bar area. The current build repairs the input timestamps needed by Qt double-click detection. |
| Two pointers, or a pointer that lags behind the mouse | Check the image ID and start a fresh session; the current build uses separate local cursor rendering. |
| F18 or a shortcut does nothing | Click inside the stream first. Try Ctrl+Shift+Enter. Verify your host actually sends F18 rather than capturing the key. |
| No audio | Enable sound in Kasm, unmute the browser/tab, retain `KASM_SVC_AUDIO=1`, and select **Kasm Audio Output** in the desktop. |
| Changes disappear after ending a session | Configure a persistent profile for home files; build a derived image for system-package changes. |
| A host power, disk, or Bluetooth action fails | Those actions depend on host hardware/system services and are outside the ordinary-container desktop integration. |

### Logs and build identification

Desktop/session logs are inside the workspace at:

```text
~/.local/state/omarchy/kasm-logs/
```

Useful files include `hyprland.log`, `shell.log`, `selkies.log`,
`audio-startup.log`, `audio-relay.log`, and `audio-encoder.log`.

On the agent, identify the actual image used by a running container:

```bash
docker ps --format '{{.Names}}\t{{.Image}}'
docker inspect --format '{{.Image}}' CONTAINER_NAME
```

When reporting a problem, include the image ID, Kasm version, GPU/driver,
browser/client, whether the session uses a persistent profile, and the relevant
error lines. Share targeted excerpts rather than full environments or session
URLs, which can contain credentials.

## Optional customization

The desktop works with its packaged defaults. Personal dotfiles and Ignition
Designer setup are optional and documented in
[REPRODUCING.md](REPRODUCING.md#optional-personal-dotfiles-and-designer).

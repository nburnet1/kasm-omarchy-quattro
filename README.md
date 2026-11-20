# Omarchy Quattro for Kasm

The current working candidate streams a GPU-rendered Omarchy/Hyprland desktop
directly through **Selkies/NVENC**, integrated with Kasm authentication, controls,
clipboard, and audio. Start with [REPRODUCING.md](REPRODUCING.md) for the image
build, workspace configuration, personal dotfiles, and verified Designer setup.
See [SELKIES-KASM.md](SELKIES-KASM.md) for adapter design and verification.

The following notes document the earlier KasmVNC baseline and initial prototype.

**Current shipping profile:** `kasm-omarchy-quattro:4.5.0-essentials` is the tested expected-app baseline. VS Code is excluded; user/admin extensions are described in [ADDONS.md](ADDONS.md). See [QUATTRO.md](QUATTRO.md) for the current build/run/verification instructions. The notes below describe earlier iterations.

**Current release:** the tested image now contains the official Omarchy **4.5.0** runtime and settings packages (`4.5.0-3`). Use `kasm-omarchy-quattro:4.5.0`, or the existing `quattro-dev` alias used by the Kasm workspace. See [QUATTRO.md](QUATTRO.md) for verification and launch details.

**Update:** The direct-container Quattro prototype now renders Hyprland, Omarchy Quickshell, the menu, and a working terminal using the host NVIDIA GPU. See [QUATTRO.md](QUATTRO.md) for the tested image, launch commands, architecture, and limitations. The notes below describe the earlier attempt, before the headless render-node shim and WayVNC bridge were implemented.

## Can you "point the Omarchy ISO" to Kasm?

Not directly.

- **Omarchy ISO** (`omarchy-*.iso`) is a bootable installer/live image for bare metal or VMs (boots via firmware/bootloader, runs install/provisioning against disks/hardware). Docker/Kasm workspaces run containers from OCI/Docker images, not bootable ISOs.
- **Possible indirect paths (not implemented here):** boot the ISO in QEMU/Proxmox/VMware for a real Omarchy install; or extract the live rootfs (e.g. `arch/x86_64/airootfs.sfs` from the ISO) and `docker import` it as a base, then retrofit Kasm runtime. Even then, Omarchy Quattro is **Hyprland + Quickshell (Wayland-first)** while Kasm streaming is typically **KasmVNC/Xvnc (X11)**, so the full Quattro shell is unlikely to work without major adaptation.
- **Bottom line:** no simple "point ISO to Kasm" switch; a custom image/build is required, and Wayland/Hyprland-in-Kasm is the core technical blocker for true Quattro fidelity.

## What this build tries

- Arch Linux base (`archlinux:base-devel`)
- Installs **KasmVNC** by extracting upstream `.deb` (best-effort; no official Arch/Kasm core)
- Copies Kasm common startup scripts from `kasmtech/workspaces-core-images` into `/dockerstartup`
- Clones `basecamp/omarchy` (`quattro`) into `/opt/omarchy` and default profile
- Attempts to install Hyprland/Quickshell-related packages via pacman
- Uses `custom_startup.sh` to try launching Hyprland (experimental) with fallback to xterm/openbox

## Build

The required Kasm core startup inputs are committed under `src/common/`:

```bash
docker build -t kasm-omarchy-quattro:experimental .
```

Run (manual test):

```bash
docker run --rm -it --shm-size=512m -p 6901:6901 -e VNC_PW=password kasm-omarchy-quattro:experimental
# then open https://localhost:6901 (kasm_user / password)
```

## Known gaps / likely failures

1. **KasmVNC on Arch:** extracted from Ubuntu package; shared lib/perl/dependency mismatches may prevent `vncserver`/`kasmvncpasswd` from running.
2. **Kasm service binaries:** upstream core images include helper binaries (`kasm_upload_server`, audio/gamepad/webcam/printer bridges, jsmpeg, etc.) not present here; `vnc_startup.sh` may error if it assumes them without guards.
3. **Wayland vs KasmVNC:** Quattro’s Quickshell/Hyprland session is not a drop-in X11 WM under Xvnc; expect fallback or no usable desktop.
4. **Omarchy installer assumptions:** full `omarchy-install` targets provisioned systems (systemd, boot, hardware, user creation) and is not run.
5. **Package availability/names:** Arch repo package names/sets may differ from Omarchy ISO mirror expectations.

## Starting-point image inspected

`scopey/kasm-arch-omarchy-minimal:1.0` (Arch 20250810, amd64): has `tigervnc`, `networkmanager`, `dbus`, `pipewire`, `kasm-user`, but **no KasmVNC/Kasm `/dockerstartup`**, **no Omarchy files**, `CMD ["bash"]`, root user — not usable in Kasm and not Quattro.

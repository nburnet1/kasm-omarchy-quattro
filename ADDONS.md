# User and administrator addons

The `4.5.0-essentials` base has no VS Code package, executable, shortcut tied to Code, Code profile defaults, or Code-specific startup helper. Neovim is the default editor. Core desktop app selection is declared in `packaging/omarchy-expected-apps.packages`.

## Administrator: derived images

Build a derived image to make an addon available in every fresh Kasm session:

```dockerfile
FROM kasm-omarchy-quattro:4.5.0-essentials
USER root
RUN omarchy-pkg-add YOUR_PACKAGE
USER 1000
```

Register the derived image/tag as its own Kasm workspace or use it for the desired groups. The normal GPU/device requirements still apply. Use root-owned executable scripts in `/dockerstartup/profile.d/` if an application needs per-user defaults; these run as the Kasm user after the base profile initialization and before compositor startup. Hooks should be idempotent and preserve existing user settings.

## Optional VS Code example

An explicitly opt-in example is provided under `addons/vscode/`:

```bash
docker build -t local/omarchy-vscode:4.5.0 addons/vscode
```

It installs the official `visual-studio-code-bin` package and adds its profile hook. That hook uses the package-supported `~/.config/code-flags.conf` to add `--no-sandbox` only if the container cannot create unprivileged user namespaces. This scopes the Electron compatibility exception to that optional application; it does not loosen the container's policy. Existing settings are preserved. The example is not part of the base build.

## User: on-demand installation

Users with package-management permission can use Omarchy's existing Install menus or native `omarchy-pkg-add`/AUR tools. Packages installed inside a session belong to that container and are lost when it is deleted, unless the administrator captures the change in a derived image. A persistent home directory alone does not preserve system packages.

Applications added this way can still need application-specific container configuration. For VS Code, the opt-in example hook above supplies the required namespace-policy flags; the essentials base intentionally does not initialize VS Code on a user's behalf.

Choose an installed editor using Omarchy's defaults menu. Both the native editor shortcut and Ctrl+Alt+E route through `omarchy-launch-editor`, so they follow the user's choice rather than assuming VS Code.

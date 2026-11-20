# Kasm runtime inputs

The selected files under `common/` originate from
[kasmtech/workspaces-core-images](https://github.com/kasmtech/workspaces-core-images).
Their license is preserved in `LICENSE.md`. The snapshot's original upstream
commit was not recorded during the prototype; the files committed here are the
actual build inputs, including local Arch/container adaptations.

Only the startup scripts, lifecycle hooks, and KasmVNC configuration referenced
by this project's Dockerfiles are vendored. The initial local copy also included
unrelated distributions, wallpapers, and installers; they are not required to
build this image and are excluded from git.

Build from the committed inputs. Do not replace `src/` with an unpinned upstream
checkout: that would discard the local runtime adaptations.

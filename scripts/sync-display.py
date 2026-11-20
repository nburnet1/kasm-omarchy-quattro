#!/usr/bin/python
"""Forward Xvnc root-window resize events to the headless Hyprland output."""
import ctypes as C
import os
from pathlib import Path
import subprocess


def main():
    x11 = C.CDLL("libX11.so.6")
    x11.XOpenDisplay.argtypes = [C.c_char_p]
    x11.XOpenDisplay.restype = C.c_void_p
    x11.XDefaultRootWindow.argtypes = [C.c_void_p]
    x11.XDefaultRootWindow.restype = C.c_ulong
    x11.XSelectInput.argtypes = [C.c_void_p, C.c_ulong, C.c_long]
    x11.XGetGeometry.argtypes = [C.c_void_p, C.c_ulong, C.POINTER(C.c_ulong),
                               C.POINTER(C.c_int), C.POINTER(C.c_int),
                               *([C.POINTER(C.c_uint)] * 4)]
    x11.XNextEvent.argtypes = [C.c_void_p, C.c_void_p]
    x11.XCloseDisplay.argtypes = [C.c_void_p]

    display = x11.XOpenDisplay(os.environ.get("DISPLAY", ":1").encode())
    if not display:
        raise RuntimeError("Cannot connect to the Kasm Xvnc display")
    root = x11.XDefaultRootWindow(display)
    x11.XSelectInput(display, root, 1 << 17)  # StructureNotifyMask
    event = (C.c_long * 24)()  # XEvent union
    previous = None
    try:
        while True:
            geometry_root = C.c_ulong()
            x, y = C.c_int(), C.c_int()
            width, height, border, depth = (C.c_uint() for _ in range(4))
            if not x11.XGetGeometry(display, root, C.byref(geometry_root), C.byref(x),
                                   C.byref(y), C.byref(width), C.byref(height),
                                   C.byref(border), C.byref(depth)):
                raise RuntimeError("Cannot query the Kasm framebuffer geometry")
            size = (width.value, height.value)
            if size != previous:
                if not all(32 <= value <= 16384 for value in size):
                    raise RuntimeError(f"Unsupported framebuffer size: {size}")
                command = ('hl.monitor({output="KASM",mode="%dx%d@60",'
                           'position="0x0",scale=1})') % size
                # Preserve the current mode across theme/config reloads too.
                state = Path(os.environ["XDG_RUNTIME_DIR"]) / "kasm-monitor.lua"
                temporary = state.with_suffix(".tmp")
                temporary.write_text(command + "\n")
                temporary.replace(state)
                result = subprocess.run(["hyprctl", "eval", command],
                                        capture_output=True, text=True, timeout=10)
                if result.returncode or result.stdout.strip() != "ok":
                    raise RuntimeError(f"Hyprland resize failed: {result.stdout} {result.stderr}")
                previous = size
                print(f"Quattro display resized to {size[0]}x{size[1]}", flush=True)
            # Block until Xvnc changes its root window; no periodic polling.
            x11.XNextEvent(display, C.byref(event))
    finally:
        x11.XCloseDisplay(display)


if __name__ == "__main__":
    main()

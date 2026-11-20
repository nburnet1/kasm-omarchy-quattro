#!/usr/bin/env python3
"""Launch an unmodified Designer fixture using Quickshell's actual environment.

Run only in a disposable labeled session; the launcher bundle is not baked into
the image. Args: CONTAINER /absolute/path/to/designerlauncher.sh
"""
import json
import subprocess
import sys
import time

container, launcher = sys.argv[1:]
metadata = json.loads(subprocess.check_output(['docker', 'inspect', container]))[0]
assert metadata['Config'].get('Labels', {}).get('org.omarchy.kasm.test') == 'true'
result = subprocess.check_output(['docker', 'exec', '-i', '-e', 'XDG_RUNTIME_DIR=/run/user/1000',
    container, 'python', '-c', r'''
import os, json, stat, subprocess
from pathlib import Path
import sys
pid = subprocess.check_output(['pgrep', '-x', 'quickshell'], text=True).strip()
env = dict(item.split('=',1) for item in (Path('/proc')/pid/'environ').read_bytes().decode().split(chr(0)) if '=' in item)
assert env.get('DISPLAY'), 'Quickshell has no Xwayland DISPLAY'
assert env.get('WAYLAND_DISPLAY') == 'wayland-1'
snapshot = Path(env['XDG_RUNTIME_DIR'])/'hypr'/env['HYPRLAND_INSTANCE_SIGNATURE']/'kasm-session.env'
assert stat.S_IMODE(snapshot.stat().st_mode) == 0o600
native = dict(item.split('=',1) for item in snapshot.read_text().split(chr(0)) if '=' in item)
required = ('DISPLAY','WAYLAND_DISPLAY','GDK_BACKEND','QT_QPA_PLATFORM',
            'XDG_CURRENT_DESKTOP','XDG_SESSION_TYPE','TERMINAL','EDITOR')
assert all(key in native and env.get(key)==native[key] for key in required), 'Graphical environment differs from upstream compositor context'
assert 'omarchy-headless-render-node' not in env.get('LD_PRELOAD','')
assert 'AQ_BACKEND' not in native
print('Upstream graphical environment matches Quickshell; private snapshot mode is 0600',flush=True)
print(json.dumps({'DISPLAY':env['DISPLAY'],'WAYLAND_DISPLAY':env['WAYLAND_DISPLAY']}),flush=True)
subprocess.Popen([sys.argv[1]], env=env, stdin=subprocess.DEVNULL,
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
''', launcher], text=True)
print('PASS: desktop launcher environment', result.strip())
deadline = time.monotonic() + 30
while time.monotonic() < deadline:
    clients = json.loads(subprocess.check_output(['docker', 'exec', '-e', 'XDG_RUNTIME_DIR=/run/user/1000',
        container, 'hyprctl', '-i', '0', '-j', 'clients']))
    windows = [window for window in clients if 'DesignerLauncherApplication' in window['class']]
    if windows:
        assert all(window['xwayland'] for window in windows)
        print('PASS: unmodified Ignition Designer Launcher mapped inside Hyprland through Xwayland')
        break
    time.sleep(.25)
else:
    raise AssertionError('Designer did not open using the desktop launch environment')

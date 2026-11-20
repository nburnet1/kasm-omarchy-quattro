#!/usr/bin/python
"""Obtain the real graphical application environment from a Hyprland child.

The private NUL-delimited snapshot can contain session credentials. Never log
its content; stdout is shell-quoted assignments for the calling supervisor.
"""
import json
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
import time

runtime = Path(os.environ['XDG_RUNTIME_DIR'])
instance = os.environ['HYPRLAND_INSTANCE_SIGNATURE']
assert re.fullmatch(r'[A-Za-z0-9_-]+', instance)
directory = runtime / 'hypr' / instance
assert directory.is_dir() and directory.stat().st_uid == os.getuid()
snapshot = directory / 'kasm-session.env'
temporary = snapshot.with_suffix('.tmp')
snapshot.unlink(missing_ok=True)
temporary.unlink(missing_ok=True)
# AQ_BACKEND and our LD_PRELOAD are compositor implementation details, not
# ordinary application settings. Leave the supervisor's original values alone.
command = ('umask 077; env -0 > ' + shlex.quote(str(temporary))
           + ' && mv ' + shlex.quote(str(temporary)) + ' ' + shlex.quote(str(snapshot)))
result = subprocess.run(['hyprctl', 'eval', 'hl.exec_cmd(' + json.dumps(command) + ')'],
                        capture_output=True, text=True, timeout=10)
if result.returncode or result.stdout.strip() != 'ok':
    raise RuntimeError('Hyprland could not start the graphical environment probe')
deadline = time.monotonic() + 10
while not snapshot.exists():
    if time.monotonic() >= deadline:
        raise TimeoutError('Hyprland graphical environment probe did not complete')
    time.sleep(.02)
metadata = snapshot.stat()
assert metadata.st_uid == os.getuid() and stat.S_IMODE(metadata.st_mode) == 0o600
values = {}
for entry in snapshot.read_bytes().split(b'\0'):
    if b'=' in entry:
        key, value = entry.decode().split('=', 1)
        if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', key) and key not in ('SHLVL', '_', 'PWD', 'OLDPWD'):
            values[key] = value
assert values.get('HYPRLAND_INSTANCE_SIGNATURE') == instance
assert values.get('WAYLAND_DISPLAY') == os.environ['WAYLAND_DISPLAY']
if values.get('LD_PRELOAD') == '/usr/local/lib/omarchy-headless-render-node.so':
    values.pop('LD_PRELOAD')
    if values.get('AQ_BACKEND') == 'headless':
        values.pop('AQ_BACKEND')
# Keep the private snapshot in application form too. User-defined preload or
# backend values are preserved; only our exact compositor shim is removed.
snapshot.write_bytes(b'\0'.join((key + '=' + value).encode() for key, value in values.items()) + b'\0')
for key, value in values.items():
    print(f'export {key}={shlex.quote(value)}')

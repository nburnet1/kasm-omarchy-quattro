#!/usr/bin/env python3
"""Prove cursor-free pixels in a labeled GPU desktop with a visible cursor.

Run at desktop startup or while a test viewer is connected and hovering over
the stream. A disconnected session may intentionally have no cursor to compare.
"""
import json
import subprocess
import sys

container = sys.argv[1]
metadata = json.loads(subprocess.check_output(['docker', 'inspect', container]))[0]
assert metadata['Config'].get('Labels', {}).get('org.omarchy.kasm.test') == 'true'
subprocess.run(['docker', 'exec', '-i', container, 'python', '-c', r'''
import json
from pathlib import Path
import subprocess
import tempfile
import time

environment = None
deadline = time.monotonic() + 40
while environment is None and time.monotonic() < deadline:
    for process in Path('/proc').glob('[0-9]*'):
        try:
            if (process / 'comm').read_text().strip() == 'quickshell':
                environment = dict(entry.split('=', 1) for entry in (process / 'environ').read_bytes().decode().split(chr(0)) if '=' in entry)
                break
        except OSError:
            continue
    if environment is None:
        time.sleep(.2)
assert environment, 'Desktop did not start'
assert environment.get('AQ_HEADLESS_VIRTUAL_CURSOR') == '1'
monitor = json.loads(subprocess.check_output(['hyprctl', '-j', 'monitors'], env=environment))[0]
position = json.loads(subprocess.check_output(['hyprctl', '-j', 'cursorpos'], env=environment))
assert monitor['scale'] == 1
x = max(0, min(position['x'] - 16, monitor['width'] - 96))
y = max(0, min(position['y'] - 16, monitor['height'] - 96))
geometry = f'{x},{y} 96x96'

def difference(first, second):
    result = subprocess.run(['magick', 'compare', '-metric', 'AE', str(first), str(second), 'null:'], capture_output=True, text=True)
    assert result.returncode in (0, 1), result.stderr
    return float(result.stderr.strip().split()[0])

with tempfile.TemporaryDirectory(prefix='cursor-separation-') as directory:
    root = Path(directory)
    for attempt in range(5):
        for name, options in [('without-a', []), ('with', ['-c']), ('without-b', [])]:
            subprocess.run(['grim', *options, '-g', geometry, str(root / (name + '.png'))], env=environment, check=True)
        if difference(root / 'without-a.png', root / 'without-b.png') == 0:
            changed = difference(root / 'without-a.png', root / 'with.png')
            assert 4 < changed < 4096, f'Expected a separately painted visible cursor, got {changed} changed pixels; keep a test viewer active'
            print(f'PASS: cursor-free captures are stable; explicit cursor painting adds {changed:g} pixels')
            break
        time.sleep(.2)
    else:
        raise AssertionError('Pointer region never became still enough to compare capture modes')
'''], check=True)

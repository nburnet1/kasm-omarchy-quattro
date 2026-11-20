#!/usr/bin/python
"""Print shell-safe X11 environment assignments for this Hyprland's Xwayland."""
import argparse
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time

parser = argparse.ArgumentParser()
parser.add_argument('--timeout', type=float, default=5)
args = parser.parse_args()
deadline = time.monotonic() + args.timeout
signature = os.environ.get('HYPRLAND_INSTANCE_SIGNATURE')

while True:
    result = subprocess.run(['hyprctl', 'instances', '-j'], capture_output=True, text=True, timeout=5)
    instances = json.loads(result.stdout) if result.returncode == 0 else []
    matches = [instance for instance in instances if not signature or instance['instance'] == signature]
    if len(matches) == 1:
        compositor_pid = int(matches[0]['pid'])
        for process in Path('/proc').iterdir():
            if not process.name.isdigit():
                continue
            try:
                if (process / 'comm').read_text().strip() != 'Xwayland':
                    continue
                status = (process / 'status').read_text()
                if int(re.search(r'^PPid:\s+(\d+)', status, re.M)[1]) != compositor_pid:
                    continue
                argv = (process / 'cmdline').read_bytes().decode().rstrip('\0').split('\0')
                display = next(value for value in argv[1:] if re.fullmatch(r':\d+(?:\.\d+)?', value))
                print('export DISPLAY=' + shlex.quote(display))
                if '-auth' in argv:
                    print('export XAUTHORITY=' + shlex.quote(argv[argv.index('-auth') + 1]))
                else:
                    print('unset XAUTHORITY')
                sys.exit(0)
            except (OSError, ValueError, TypeError, IndexError, StopIteration):
                continue
    if time.monotonic() >= deadline:
        sys.exit('No Xwayland process owned by the current Hyprland instance was found')
    time.sleep(.05)

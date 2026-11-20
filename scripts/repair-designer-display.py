#!/usr/bin/python
"""Reversible repair for an already-downloaded Ignition Designer launcher.

Future sessions receive DISPLAY from the desktop supervisor; this only fills a
missing environment in a live session whose Quickshell was already started.
"""
from pathlib import Path
import shutil
import sys

path = Path(sys.argv[1]).resolve()
assert path.name == 'designerlauncher.sh' and path.is_file()
source = path.read_text()
marker = '# Omarchy: complete the Xwayland environment for a pre-existing session.'
if marker in source:
    print('Designer display repair already present')
    sys.exit(0)
assert source.count('# Launch\n') == 1, 'Unrecognized launcher script; no changes made'
backup = path.with_name(path.name + '.before-xwayland-fix')
assert not backup.exists(), 'Backup already exists; inspect it before applying another repair'
shutil.copy2(path, backup)
block = marker + '''
if [[ -z ${DISPLAY:-} ]] && command -v omarchy-xwayland-env >/dev/null 2>&1; then
    if x11_environment=$(omarchy-xwayland-env --timeout=5); then
        eval "$x11_environment"
    fi
fi

'''
path.write_text(source.replace('# Launch\n', block + '# Launch\n'))
print('Repaired missing DISPLAY; original launcher saved as ' + str(backup))

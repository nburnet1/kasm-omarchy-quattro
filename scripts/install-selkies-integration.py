#!/usr/bin/env python3
"""Copy the pinned web client and add small, checked lifecycle hooks for Kasm."""
from importlib.metadata import version
from importlib.resources import files
from pathlib import Path
import hashlib
import json
import shutil
import sys

assert version('selkies') == '2.2.1'
root = Path('/usr/local/share/omarchy-kasm/selkies-web')
if '--replace' in sys.argv:
    # Explicit repair of this adapter's generated files, never a user profile.
    assert (root / 'selkies-kasm.js').is_file() and (root / 'vnc.html').is_file()
    shutil.rmtree(root)
shutil.copytree(files('selkies').joinpath('selkies_web'), root)
shutil.copy('/usr/local/share/omarchy-kasm/selkies-kasm.js', root / 'selkies-kasm.js')
shutil.copy('/usr/local/share/omarchy-kasm/selkies-disconnected.html', root / 'selkies-disconnected.html')


def patch(name, old, new):
    path = root / name
    source = path.read_text()
    assert source.count(old) == 1, f'Unexpected Selkies entrypoint: {name}, {old!r}'
    path.write_text(source.replace(old, new))
    for suffix in ('.gz', '.br'):
        Path(str(path) + suffix).unlink(missing_ok=True)


# The adapter registers before the dashboard/core's module scripts execute.
patch('index.html', '<head>', '<head><script type="module" src="./selkies-kasm.js"></script>')
shutil.copy(root / 'index.html', root / 'vnc.html')
# The wheel bundles/minifies the core. Match its unique stream-start marker,
# not generated variable names, and preserve the expression's return value.
marker = 'console.log(`Stream started (UI elements hidden).`)'
patch('selkies-core.js', marker,
      '(window.dispatchEvent(new CustomEvent("selkies-kasm-state", {detail:"streaming"})), ' + marker + ')')

# Kasm's live session path validator refuses extensionless /api/* requests
# before proxying them. Serve the bootstrap as JSON resources and the stream
# at KasmVNC's accepted WebSocket path; leave Kasm's own API policy intact.
aliases = {
    'api/websockets': 'websockify',
    'api/status': 'selkies-status.json',
    'api/health': 'selkies-health.json',
}
scripts = sorted(root.rglob('*.js'))
counts = {old: 0 for old in aliases}
for path in scripts:
    source = path.read_text()
    for old, new in aliases.items():
        counts[old] += source.count(old)
        source = source.replace(old, new)
    path.write_text(source)
    for suffix in ('.gz', '.br'):
        Path(str(path) + suffix).unlink(missing_ok=True)
assert counts['api/websockets'] and counts['api/status'], counts

# The upstream asset hashes describe upstream content, not our adapted code.
# Give the whole JS graph a revision so an existing Kasm/Electron cache cannot
# pair a new entrypoint with the old API-path code. Keep canonical copies for
# direct diagnostics; the HTML and imports use the revisioned names.
revision = hashlib.sha256(b''.join(path.read_bytes() for path in scripts)).hexdigest()[:12]
renames = {path.name: f'{path.stem}-kasm-{revision}{path.suffix}' for path in scripts
           if path.parent == root / 'assets' or path.name in ('selkies-core.js', 'selkies-kasm.js')}
for path in sorted(root.rglob('*')):
    if path.is_file() and path.suffix in ('.html', '.js', '.css', '.json'):
        source = path.read_text()
        for old, new in renames.items():
            source = source.replace(old, new)
        path.write_text(source)
for path in scripts:
    if path.name in renames:
        shutil.copy(path, path.with_name(renames[path.name]))
(root / 'kasm-adapter.json').write_text(json.dumps({'revision': revision, 'api_aliases': aliases}) + '\n')

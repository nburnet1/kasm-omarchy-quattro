#!/usr/bin/env python3
"""Desktop/package checks in a disposable, labeled ordinary-Kasm GPU session."""
import json
from pathlib import Path
import subprocess
import sys
import time

container, browser_container = sys.argv[1:]
metadata = json.loads(subprocess.check_output(['docker', 'inspect', container]))[0]
assert metadata['Config'].get('Labels', {}).get('org.omarchy.kasm.test') == 'true'
assert metadata['Config']['Labels']['org.omarchy.kasm.profile'] == 'full-packages-standard-runtime'
assert metadata['Config']['User'] == '1000'
assert not metadata['HostConfig']['Privileged']
assert not metadata['HostConfig']['CapAdd']
assert not metadata['HostConfig']['SecurityOpt']
assert metadata['AppArmorProfile'] == 'docker-default'
probe = Path(__file__).with_name('portal-probe.py').read_text()
program = r'''
import json
from pathlib import Path
import subprocess
import sys
import time

env = None
for attempt in range(150):
    for process in Path('/proc').glob('[0-9]*'):
        try:
            if (process/'comm').read_text().strip() == 'quickshell':
                env = dict(x.split('=', 1) for x in (process/'environ').read_bytes().decode().split(chr(0)) if '=' in x)
                break
        except OSError:
            continue
    if env is not None:
        break
    time.sleep(.2)
assert env is not None, 'Desktop did not become ready'

def run(*args):
    return subprocess.check_output(args, env=env, text=True).strip()

def native(command):
    run('hyprctl', 'eval', 'hl.exec_cmd(' + json.dumps(command) + ')')

def wait(predicate, description, seconds=25):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.2)
    raise AssertionError('Timed out: ' + description)

def has_class(name):
    return any(name.lower() in window['class'].lower() for window in json.loads(run('hyprctl', '-j', 'clients')))

root = Path('/tmp/omarchy-essentials-smoke')
failures = []
root.mkdir(exist_ok=True)
(root/'screenshots').mkdir(exist_ok=True)
(root/'recordings').mkdir(exist_ok=True)
for directory in ['screenshots', 'recordings']:
    for artifact in (root/directory).iterdir():
        if artifact.is_file():
            artifact.unlink()
(root/'recording-stopped').unlink(missing_ok=True)
(root/'portal-result.json').unlink(missing_ok=True)
packages = run('omarchy-pkg-defaults', 'x86').splitlines()
run('pacman', '-T', *packages)
run('pacman', '-Dk')
assert not Path('/home/kasm-user/.local/state/omarchy/preinstalls-removed').exists()
assert not run('hyprctl', 'configerrors')
print(f'PASS: all {len(packages)} defaults satisfied; ordinary runtime and fresh full profile', flush=True)

rows = run('omarchy-menu-images', '--print-rows', '/home/kasm-user/.local/state/omarchy/current/theme/backgrounds')
assert rows, 'Wallpaper picker has no displayable entries'
print(f'PASS: wallpaper picker generated {len(rows.splitlines())} thumbnail rows', flush=True)

for command, window in [
    ('omarchy-launch-terminal', 'foot'),
    ('omarchy-launch-browser about:blank', 'chromium'),
    ('uwsm-app -- nautilus --new-window "$HOME"', 'nautilus'),
    ('omarchy-launch-config-editor "$HOME/.config/hypr/input.lua"', 'org.omarchy.nvim'),
    ('libreoffice --writer', 'libreoffice'),
]:
    native(command + ' > '+str(root/(window+'.log'))+' 2>&1')
    try:
        wait(lambda: has_class(window), command)
        print('PASS: native window opened: ' + command, flush=True)
    except AssertionError:
        failures.append(command)
        print('FAIL: native window did not open: ' + command, flush=True)
    # Keep later portal focus tests clear of first-launch application dialogs.
    if window == 'libreoffice':
        for client in json.loads(run('hyprctl', '-j', 'clients')):
            if client['class'] in ['soffice', 'libreoffice-writer']:
                subprocess.run(['kill', '-TERM', str(client['pid'])], env=env, check=False)

native('OMARCHY_SCREENSHOT_DIR='+str(root/'screenshots')+' omarchy-capture-screenshot fullscreen save > '+str(root/'capture.log')+' 2>&1')
wait(lambda: bool(list((root/'screenshots').glob('*.png'))), 'screenshot save')
print('PASS: native screenshot saved PNG', flush=True)

native('OMARCHY_SCREENRECORD_DIR='+str(root/'recordings')+' OMARCHY_SCREENRECORD_DEBUG=true omarchy-capture-screenrecording --fullscreen > '+str(root/'recording.log')+' 2>&1')
wait(lambda: Path('/run/user/1000/omarchy-screenrecord-pid').exists(), 'screen recording start')
time.sleep(3)
native('omarchy-notification-send "Recording verification"')
time.sleep(1)
native('OMARCHY_SCREENRECORD_DIR='+str(root/'recordings')+' omarchy-capture-screenrecording --stop-recording; touch '+str(root/'recording-stopped'))
wait(lambda: (root/'recording-stopped').exists(), 'recording stop')
recording = next((root/'recordings').glob('*.mp4'))
duration = float(run('ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(recording)))
if duration > 1:
    print('PASS: native recording saved playable MP4', flush=True)
else:
    failures.append('screen recording duration: '+str(duration))
    print('FAIL: screen recording duration: '+str(duration), flush=True)

# Exercise image decoding in the actual GTK chooser without a sandbox override.
run('magick', '-size', '320x200', 'xc:steelblue', str(root/'sample.png'))
(root/'portal-probe.py').write_text(sys.argv[1])
native('python '+str(root/'portal-probe.py')+' > '+str(root/'portal.log')+' 2>&1')
try:
    wait(lambda: any('file chooser verification' in w['title'] for w in json.loads(run('hyprctl', '-j', 'clients'))), 'GTK file chooser')
    print('PASS: native GTK file chooser mapped', flush=True)
except AssertionError:
    failures.append('GTK file chooser')
    print('FAIL: native GTK file chooser did not map', flush=True)
texture = subprocess.run(['python', '-c', 'import gi; gi.require_version("Gdk", "4.0"); from gi.repository import Gdk; Gdk.Texture.new_from_filename('+repr(str(root/'sample.png'))+')'], env=env, capture_output=True, text=True)
if texture.returncode:
    # Keep diagnostics scoped; graphical environments may contain credentials.
    for line in texture.stderr.splitlines():
        if any(marker in line for marker in ['bwrap:', 'Sandbox', 'sandbox', 'uid map']):
            print(line, flush=True)
    failures.append('GTK image decoding under normal container policy')
else:
    print('PASS: GTK image decoding under normal container policy', flush=True)
assert not failures, failures
'''
result = subprocess.run(['docker', 'exec', container, 'python', '-u', '-c', program, probe])
if result.returncode:
    raise SystemExit(result.returncode)
windows = json.loads(subprocess.check_output(['docker', 'exec', '-e', 'XDG_RUNTIME_DIR=/run/user/1000',
    container, 'hyprctl', '-i', '0', '-j', 'clients']))
chooser = next(window for window in windows if 'file chooser verification' in window['title'])
subprocess.run(['docker', 'exec', '-e', 'XDG_RUNTIME_DIR=/run/user/1000', container,
    'hyprctl', '-i', '0', 'eval', 'hl.dispatch(hl.dsp.focus({window='+json.dumps('address:'+chooser['address'])+'}))'], check=True, stdout=subprocess.DEVNULL)
point = [chooser['at'][0] + chooser['size'][0]/2, chooser['at'][1] + 30]
driver = r'''
import json
import sys
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='/usr/bin/chromium', args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'])
    context = browser.new_context(ignore_https_errors=True, viewport={'width':1280, 'height':800})
    page = context.new_page()
    page.route('https://127.0.0.1:16915/full-chooser', lambda route: route.fulfill(content_type='text/html', body='<body style="margin:0"><iframe style="width:100vw;height:100vh;border:0" src="/desktop/selkies-browser-test/vnc/vnc.html?autoconnect=1"></iframe>'))
    page.goto('https://127.0.0.1:16915/full-chooser')
    frame = page.frames[1]
    frame.wait_for_function('window.webrtcInput && window.stream_client?.resolution', timeout=45000)
    frame.wait_for_function('window.stream_info?.hardware && document.querySelector("#videoStream")?.readyState >= 2', timeout=30000)
    page.wait_for_timeout(700)
    page.mouse.move(*json.loads(sys.argv[1]))
    frame.locator('#overlayInput').focus()
    page.keyboard.press('Control+l')
    page.wait_for_timeout(400)
    page.keyboard.type('/tmp/omarchy-essentials-smoke/sample.png', delay=5)
    page.keyboard.press('Enter')
    page.wait_for_timeout(600)
    page.keyboard.press('Enter')
    page.wait_for_timeout(600)
    browser.close()
'''
subprocess.run(['docker', 'exec', browser_container, '/tmp/browser-tools/bin/python', '-c', driver, json.dumps(point)], check=True)
for _ in range(30):
    result = subprocess.run(['docker', 'exec', container, 'python', '-c',
        'from pathlib import Path; print(Path("/tmp/omarchy-essentials-smoke/portal-result.json").read_text())'], capture_output=True, text=True)
    if result.returncode == 0:
        break
    time.sleep(.2)
assert result.returncode == 0, 'File chooser did not return a selection'
selection = json.loads(result.stdout)
assert selection == {'response': 0, 'uris': ['file:///tmp/omarchy-essentials-smoke/sample.png']}, selection
print('PASS: real GTK file chooser returned the selected file through the portal')

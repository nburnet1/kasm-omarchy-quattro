#!/usr/bin/env python3
"""Destructive UI smoke checks: run only in a disposable, labeled GPU container.

docker run -d --name omarchy-smoke --label org.omarchy.kasm.test=true ... IMAGE
python3 tests/verify-essentials.py omarchy-smoke
"""
import json
from pathlib import Path
import subprocess
import sys
import time

container = sys.argv[1]
metadata = json.loads(subprocess.check_output(['docker', 'inspect', container], text=True))[0]
if metadata['Config'].get('Labels', {}).get('org.omarchy.kasm.test') != 'true':
    raise SystemExit('Refusing UI checks: container must have org.omarchy.kasm.test=true')

def run(*args, input=None, check=True):
    result = subprocess.run(['docker', 'exec', '-i', '-e', 'DISPLAY=:1', '-e',
                             'XDG_RUNTIME_DIR=/run/user/1000', container, *args],
                            input=input, text=True, capture_output=True, timeout=45)
    if check and result.returncode:
        raise RuntimeError(f'{args}: {result.stdout}\n{result.stderr}')
    return result.stdout.strip()

def wait(predicate, description, seconds=15):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.2)
    raise AssertionError(f'Timed out: {description}')

def native(command):
    run('hyprctl', '-i', '0', 'eval', 'hl.exec_cmd(' + json.dumps(command) + ')')

def clients():
    return json.loads(run('hyprctl', '-i', '0', '-j', 'clients'))

def has_class(name):
    return any(name.lower() in window['class'].lower() for window in clients())

def key(chord):
    run('xdotool', 'key', '--clearmodifiers', chord)
    time.sleep(.3)

def exists(path):
    return run('python', '-c', f'from pathlib import Path; print(Path({path!r}).exists())') == 'True'

root = '/tmp/omarchy-essentials-smoke'
run('mkdir', '-p', root, root + '/screenshots', root + '/recordings')
assert run('omarchy-version') == '4.5.0-3'
assert not run('hyprctl', '-i', '0', 'configerrors')
assert run('bash', '-c', 'command -v code', check=False) == ''
assert not exists('/home/kasm-user/.vscode')
assert exists('/home/kasm-user/.local/state/omarchy/preinstalls-removed')
assert run('kasmvncconfig', '-get', 'RemapKeys') == '0xffcf->0xffeb'
print('PASS: official release, no VS Code/profile, optional preinstall opt-out, remote-Super config')

run('magick', '-size', '320x200', 'xc:steelblue', root + '/sample.png')
run('python', '-c', r'''
from pathlib import Path
root=Path('/tmp/omarchy-essentials-smoke')
(root/'browser.html').write_text('<title>Essentials browser handoff</title><h1>Browser verified</h1>')
stream=b'BT /F1 18 Tf 30 100 Td (PDF viewer verified) Tj ET'
objects=[b'<< /Type /Catalog /Pages 2 0 R >>', b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
 b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 320 200] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
 b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
 b'<< /Length '+str(len(stream)).encode()+b' >>\nstream\n'+stream+b'\nendstream']
pdf=bytearray(b'%PDF-1.4\n'); offsets=[0]
for i,obj in enumerate(objects,1):
 offsets.append(len(pdf));pdf.extend(f'{i} 0 obj\n'.encode()+obj+b'\nendobj\n')
xref=len(pdf);pdf.extend(f'xref\n0 {len(offsets)}\n0000000000 65535 f \n'.encode())
for offset in offsets[1:]:pdf.extend(f'{offset:010d} 00000 n \n'.encode())
pdf.extend(f'trailer\n<< /Root 1 0 R /Size {len(offsets)} >>\nstartxref\n{xref}\n%%EOF\n'.encode())
(root/'sample.pdf').write_bytes(pdf)
''')
run('ffmpeg', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=blue:s=320x200:r=10',
    '-t', '10', '-c:v', 'mpeg4', root + '/sample.mp4')

key('super+Return')
wait(lambda: has_class('foot'), 'terminal')
key('super+shift+b')
wait(lambda: has_class('chromium'), 'browser cold start')
native(f'omarchy-launch-browser file://{root}/browser.html')
wait(lambda: any('Essentials browser handoff' in w['title'] for w in clients()), 'browser URL handoff')
key('super+shift+f')
wait(lambda: has_class('nautilus'), 'file manager')
print('PASS: native terminal, browser cold start, URL handoff, file manager')

native('omarchy-launch-config-editor "$HOME/.config/hypr/input.lua"')
wait(lambda: has_class('org.omarchy.nvim'), 'Setup config editor')
native(f'omarchy-launch-floating-terminal-with-presentation "gum input --placeholder Verification > {root}/prompt.txt"')
wait(lambda: has_class('org.omarchy.terminal'), 'floating prompt')
time.sleep(1)
run('xdotool', 'type', '--clearmodifiers', 'prompt-verified')
key('Return')
wait(lambda: exists(root + '/prompt.txt'), 'prompt result')
assert run('python', '-c', f'print(open({root + "/prompt.txt"!r}).read())') == 'prompt-verified'
key('Return')
print('PASS: actual Setup editor and prompt submission')

for mime, entry in [('image/png', 'imv.desktop'), ('application/pdf', 'org.gnome.Evince.desktop'),
                    ('video/mp4', 'mpv.desktop')]:
    assert run('xdg-mime', 'query', 'default', mime) == entry
for filename, name in [('sample.png', 'imv'), ('sample.pdf', 'evince'), ('sample.mp4', 'mpv')]:
    native(f'xdg-open {root}/{filename}')
    wait(lambda: has_class(name), filename + ' default viewer')
print('PASS: image, PDF, and media MIME launches')

wayland = json.loads(run('hyprctl', 'instances', '-j'))[0]['wl_socket']
run('env', 'WAYLAND_DISPLAY=' + wayland, 'wl-copy', input='clipboard-verified')
assert run('env', 'WAYLAND_DISPLAY=' + wayland, 'wl-paste', '--no-newline') == 'clipboard-verified'
assert 'PipeWire' in run('pactl', 'info')
print('PASS: Wayland clipboard and PulseAudio-on-PipeWire userland')

subprocess.run(['docker', 'cp', str(Path(__file__).with_name('portal-probe.py')),
                container + ':' + root + '/portal-probe.py'], check=True)
native(f'python {root}/portal-probe.py > {root}/portal.log 2>&1')
wait(lambda: any('Essentials file chooser verification' in w['title'] for w in clients()), 'file chooser portal')
chooser = next(w for w in clients() if 'Essentials file chooser verification' in w['title'])
run('hyprctl', '-i', '0', 'eval', 'hl.dispatch(hl.dsp.focus({window=' + json.dumps('address:' + chooser['address']) + '}))')
time.sleep(.5)
key('ctrl+l')
run('xdotool', 'type', '--clearmodifiers', root + '/sample.png')
key('Return')
time.sleep(.5)
if any(w['address'] == chooser['address'] for w in clients()):
    key('Return')
wait(lambda: exists(root + '/portal-result.json'), 'portal response')
result = json.loads(run('python', '-c', f'print(open({root + "/portal-result.json"!r}).read())'))
assert result.get('response') == 0 and result.get('uris') == ['file://' + root + '/sample.png'], result
print('PASS: real file-chooser portal returned selected file')

native(f'OMARCHY_SCREENSHOT_DIR={root}/screenshots omarchy-capture-screenshot fullscreen save > {root}/capture.log 2>&1')
wait(lambda: run('python', '-c', f'from pathlib import Path; print(bool(list(Path({root + "/screenshots"!r}).glob("*.png"))))') == 'True', 'native screenshot save')
print('PASS: native Omasnap fullscreen screenshot saved')

native(f'OMARCHY_SCREENRECORD_DIR={root}/recordings OMARCHY_SCREENRECORD_DEBUG=true omarchy-capture-screenrecording --fullscreen > {root}/recording.log 2>&1')
wait(lambda: exists('/run/user/1000/omarchy-screenrecord-pid'), 'native recording start')
time.sleep(2)
native(f'OMARCHY_SCREENRECORD_DIR={root}/recordings omarchy-capture-screenrecording --stop-recording; touch {root}/recording-stopped')
wait(lambda: exists(root + '/recording-stopped'), 'native recording stop')
recording = run('python', '-c', f'from pathlib import Path; print(next(Path({root + "/recordings"!r}).glob("*.mp4")))')
duration = float(run('ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', recording))
assert duration > 1, duration
print('PASS: native recording command and supported headless fallback produced playable video')

native('omarchy-launch-screensaver force')
wait(lambda: has_class('org.omarchy.screensaver'), 'native screensaver')
wait(lambda: bool(run('pgrep', '-x', 'ttfx', check=False)), 'screensaver renderer')
key('Escape')
wait(lambda: not has_class('org.omarchy.screensaver'), 'screensaver exit on input')
print('PASS: native screensaver starts and exits on keyboard input')

native('omarchy-hyprland-workspace-layout-toggle back')
wait(lambda: any(p['name'] == 'hyprbars' for p in json.loads(run('hyprctl', '-i', '0', 'plugin', 'list', '-j'))), 'native titlebar plugin load')
assert not run('hyprctl', '-i', '0', 'configerrors')
run('magick', 'import', '-window', 'root', root + '/desktop.png')
native('omarchy-hyprland-workspace-layout-toggle')
print('PASS: native floating workspace and ABI-matched titlebar plugin')

for width, height in [(1920, 1080), (1280, 800)]:
    run('xrandr', '-s', f'{width}x{height}')
    wait(lambda: (lambda m: (m['width'],m['height']) == (width,height))(
         json.loads(run('hyprctl','-i','0','-j','monitors'))[0]), 'display resize')
run('hyprctl', '-i', '0', 'reload')
time.sleep(1)
assert not run('hyprctl', '-i', '0', 'configerrors')
assert json.loads(run('hyprctl','-i','0','-j','monitors'))[0]['height'] == 800
print('PASS: resizing and config reload')
print('Artifacts inside container:', root)

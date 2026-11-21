#!/usr/bin/env python3
"""Verify actual Wayland application cursor changes reach the streamed client.

Args: labeled GPU desktop container, Playwright fixture container. The prefix
proxy and /tmp/browser-tools environment match verify-selkies-browser.py.
"""
import json
import subprocess
import sys
import time

container, browser_container = sys.argv[1:]
metadata = json.loads(subprocess.check_output(['docker', 'inspect', container]))[0]
assert metadata['Config'].get('Labels', {}).get('org.omarchy.kasm.test') == 'true'
fixture = r'''
import base64
from pathlib import Path
import subprocess
for p in Path('/proc').glob('[0-9]*'):
    try:
        if (p/'comm').read_text().strip() == 'quickshell':
            environment = dict(x.split('=',1) for x in (p/'environ').read_bytes().decode().split(chr(0)) if '=' in x)
            break
    except OSError:
        continue
html = '<style>body{margin:0;display:flex;height:100vh}div{width:33.333vw;display:grid;place-items:center;background:#ddd;color:#222;font:24px sans-serif}#text{cursor:text;background:#eee}#resize{cursor:ew-resize}</style><div>Arrow</div><div id="text">Text</div><div id="resize">Resize</div>'
url = 'data:text/html;base64,' + base64.b64encode(html.encode()).decode()
process = subprocess.Popen(['chromium','--no-sandbox','--disable-dev-shm-usage','--ozone-platform=wayland',
    '--no-first-run','--user-data-dir=/tmp/omarchy-cursor-shape-fixture','--app='+url],
    env=environment, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
print(process.pid)
'''
pid = int(subprocess.check_output(['docker', 'exec', container, 'python', '-c', fixture], text=True))
deadline = time.monotonic() + 30
window = None
while time.monotonic() < deadline:
    clients = json.loads(subprocess.check_output(['docker', 'exec', '-e', 'XDG_RUNTIME_DIR=/run/user/1000',
        container, 'hyprctl', '-i', '0', '-j', 'clients']))
    window = next((client for client in clients if client['pid'] == pid), None)
    if window:
        break
    time.sleep(.2)
assert window, 'Native Chromium cursor fixture did not map'
points = [[window['at'][0] + window['size'][0] * fraction,
           window['at'][1] + window['size'][1] * .5] for fraction in (1/6, 1/2, 5/6)]
program = r'''
import hashlib
import json
import sys
from playwright.sync_api import sync_playwright
points = json.loads(sys.argv[1])
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='/usr/bin/chromium', args=['--no-sandbox','--disable-dev-shm-usage','--disable-gpu'])
    context = browser.new_context(ignore_https_errors=True, viewport={'width':1280,'height':800})
    page = context.new_page()
    page.route('https://127.0.0.1:16915/cursor-shape-proof', lambda route: route.fulfill(content_type='text/html', body='<html><body style="margin:0"><iframe style="width:100vw;height:100vh;border:0" src="/desktop/selkies-browser-test/vnc/vnc.html?autoconnect=1"></iframe></body></html>'))
    page.goto('https://127.0.0.1:16915/cursor-shape-proof')
    frame = page.frames[1]
    frame.wait_for_function('window.webrtcInput && window.stream_client?.resolution', timeout=45000)
    previous = None
    shapes = []
    for name, point in zip(['arrow','text','resize'], points):
        page.mouse.move(*point)
        frame.wait_for_function('previous => window.webrtcInput._cursorBase64Data && window.webrtcInput._cursorBase64Data !== previous', arg=previous, timeout=10000)
        page.wait_for_timeout(200)
        previous = frame.evaluate('window.webrtcInput._cursorBase64Data')
        assert frame.evaluate("getComputedStyle(window.webrtcInput.cursorDiv).visibility === 'visible'")
        shapes.append(hashlib.sha256(previous.encode()).hexdigest())
        print('PASS: received '+name+' cursor image', flush=True)
    assert len(set(shapes)) == 3, 'Actual application cursor shapes were not distinct'
    browser.close()
'''
try:
    subprocess.run(['docker', 'exec', browser_container, '/tmp/browser-tools/bin/python', '-c', program,
                    json.dumps(points)], check=True)
finally:
    subprocess.run(['docker', 'exec', container, 'kill', '-TERM', str(pid)], check=False)

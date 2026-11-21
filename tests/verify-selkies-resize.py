#!/usr/bin/env python3
"""Verify viewer/manual resizing against real Hyprland geometry and NVENC video."""
import json
import ssl
import subprocess
import sys
import time
import urllib.request

container, browser_container = sys.argv[1:]
metadata = json.loads(subprocess.check_output(['docker', 'inspect', container]))[0]
assert metadata['Config'].get('Labels', {}).get('org.omarchy.kasm.test') == 'true'
deadline = time.monotonic() + 90
while True:
    try:
        with urllib.request.urlopen('https://127.0.0.1:16915/desktop/selkies-browser-test/vnc/vnc.html',
                                    context=ssl._create_unverified_context(), timeout=3) as response:
            if response.status == 200:
                break
    except OSError:
        pass
    assert time.monotonic() < deadline, 'Disposable stream endpoint did not become ready'
    time.sleep(.5)

def host(*args):
    return subprocess.check_output(['docker', 'exec', '-e', 'XDG_RUNTIME_DIR=/run/user/1000', container, *args], text=True).strip()

driver = r'''
import json
import sys
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='/usr/bin/chromium', args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'])
    context = browser.new_context(ignore_https_errors=True, viewport={'width':1280,'height':800})
    page = context.new_page()
    page.route('https://127.0.0.1:16915/resize-proof', lambda route: route.fulfill(content_type='text/html', body='<body style="margin:0;overflow:hidden"><iframe style="width:100vw;height:100vh;border:0" src="/desktop/selkies-browser-test/vnc/vnc.html?autoconnect=1&resize=remote"></iframe>'))
    page.goto('https://127.0.0.1:16915/resize-proof')
    frame = page.frames[1]
    frame.wait_for_function('window.stream_info?.hardware', timeout=60000)
    def realized(width, height):
        frame.wait_for_function('s=>window.stream_client?.resolution===s', arg=f'{width}x{height}', timeout=30000)
        frame.wait_for_function('s=>{const v=document.querySelector("#videoStream"); return v?.readyState>=2 && `${v.videoWidth}x${v.videoHeight}`===s}', arg=f'{width}x{height}', timeout=30000)
        assert frame.evaluate('window.stream_info.encoder === "NVENC" && window.stream_info.zero_copy')
        before = frame.evaluate('document.querySelector("#videoStream").getVideoPlaybackQuality().totalVideoFrames')
        frame.wait_for_function('n=>document.querySelector("#videoStream").getVideoPlaybackQuality().totalVideoFrames > n+2', arg=before, timeout=10000)
    realized(1280,800)
    print('READY', flush=True)
    for line in sys.stdin:
        command = json.loads(line)
        if command['type'] == 'quit':
            break
        if command['type'] == 'viewport':
            page.set_viewport_size({'width':command['width'], 'height':command['height']})
        elif command['type'] == 'burst':
            for width, height in [(1500,900),(1000,700),(1700,1000),(1200,760),(1600,900)]:
                page.set_viewport_size({'width':width,'height':height})
                page.wait_for_timeout(40)
            page.set_viewport_size({'width':command['width'],'height':command['height']})
        elif command['type'] == 'manual':
            page.evaluate('m=>document.querySelector("iframe").contentWindow.postMessage(m,location.origin)', {'action':'set_resolution','value_x':command['width'],'value_y':command['height']})
        elif command['type'] == 'remote':
            page.evaluate('()=>document.querySelector("iframe").contentWindow.postMessage({action:"resize",value:"remote"},location.origin)')
        realized(command.get('expected_width',command['width']),command.get('expected_height',command['height']))
        print('OK', flush=True)
    browser.close()
'''
process = subprocess.Popen(['docker', 'exec', '-i', browser_container, '/tmp/browser-tools/bin/python', '-u', '-c', driver], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
try:
    assert process.stdout.readline().strip() == 'READY', 'Stream did not start at launch size'
    for index, (kind, width, height, expected_width, expected_height) in enumerate([
        ('viewport',1600,900,1600,900), ('viewport',1024,768,1024,768),
        ('viewport',1920,1080,1920,1080), ('viewport',1366,768,1366,768),
        ('manual',1100,700,1100,700), ('viewport',1536,864,1100,700),
        ('remote',1536,864,1536,864), ('viewport',1280,800,1280,800)]):
        if index == 2:
            # First grow/shrink the idle desktop, then add continuous visible
            # damage to verify both idle and active capture paths.
            host('hyprctl', '-i', '0', 'eval', 'hl.exec_cmd('+json.dumps("foot --app-id=omarchy-resize-fixture -e bash -c 'while true; do date +%s.%N; sleep .1; done'")+')')
        process.stdin.write(json.dumps({'type':kind,'width':width,'height':height,'expected_width':expected_width,'expected_height':expected_height})+'\n')
        process.stdin.flush()
        assert process.stdout.readline().strip() == 'OK', (kind,width,height)
        monitor = next(m for m in json.loads(host('hyprctl','-i','0','-j','monitors')) if m['name']=='HEADLESS-1')
        assert (monitor['width'],monitor['height']) == (expected_width,expected_height), monitor
        assert monitor['refreshRate'] > 0, monitor
        print(f'PASS: {kind} realizes {expected_width}x{expected_height} in Hyprland and advancing zero-copy NVENC video', flush=True)
    host('hyprctl','-i','0','reload')
    assert not host('hyprctl','-i','0','configerrors')
    process.stdin.write(json.dumps({'type':'viewport','width':1440,'height':900})+'\n')
    process.stdin.flush()
    assert process.stdout.readline().strip() == 'OK', 'Resize after config reload failed'
    print('PASS: resizing still works after compositor config reload', flush=True)
    process.stdin.write(json.dumps({'type':'burst','width':1280,'height':800})+'\n')
    process.stdin.flush()
    assert process.stdout.readline().strip() == 'OK'
    monitor = next(m for m in json.loads(host('hyprctl','-i','0','-j','monitors')) if m['name']=='HEADLESS-1')
    assert (monitor['width'],monitor['height']) == (1280,800), monitor
    print('PASS: rapid viewer resizes settle on the final desktop/video size', flush=True)
finally:
    if process.poll() is None:
        process.communicate(json.dumps({'type':'quit'})+'\n', timeout=20)
    for client in json.loads(host('hyprctl','-i','0','-j','clients')):
        if client['class'] == 'omarchy-resize-fixture':
            host('kill','-TERM',str(client['pid']))
assert process.returncode == 0

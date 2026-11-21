#!/usr/bin/env python3
"""Operate the real Omarchy bar and wallpaper picker through the stream.

Requires the disposable 1280x800 desktop and prefix/browser fixture. Changes
wallpaper/bar preferences only inside that labeled disposable desktop.
"""
import json
import subprocess
import sys
import time

container, browser_container = sys.argv[1:]
metadata = json.loads(subprocess.check_output(['docker','inspect',container]))[0]
assert metadata['Config'].get('Labels', {}).get('org.omarchy.kasm.test') == 'true'

def host(*args):
    return subprocess.check_output(['docker','exec','-e','XDG_RUNTIME_DIR=/run/user/1000',container,*args],text=True).strip()

assert not json.loads(host('hyprctl','-i','0','-j','clients')), 'Run in an otherwise empty disposable desktop'

def background():
    return host('python','-c','from pathlib import Path; print((Path.home()/".local/state/omarchy/current/background").resolve())')

def bar():
    return json.loads(host('python','-c','from pathlib import Path; print((Path.home()/".config/omarchy/shell.json").read_text())'))['bar']['background']

def picker():
    layers = json.loads(host('hyprctl','-i','0','-j','layers'))
    return any(layer['namespace']=='omarchy-image-selector' for output in layers.values()
               for level in output['levels'].values() for layer in level)

def wait(predicate, description):
    deadline=time.monotonic()+20
    while time.monotonic()<deadline:
        if predicate(): return
        time.sleep(.1)
    raise AssertionError(description)

driver = r'''
import json,sys
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--no-sandbox','--disable-dev-shm-usage','--disable-gpu'])
    context=browser.new_context(ignore_https_errors=True,viewport={'width':1280,'height':800})
    page=context.new_page()
    page.route('https://127.0.0.1:16915/double-click-proof',lambda route:route.fulfill(content_type='text/html',body='<body style="margin:0;overflow:hidden"><iframe style="width:100vw;height:100vh;border:0" src="/desktop/selkies-browser-test/vnc/vnc.html?autoconnect=1&resize=remote"></iframe>'))
    page.goto('https://127.0.0.1:16915/double-click-proof')
    frame=page.frames[1]
    frame.wait_for_function('window.stream_info?.hardware && document.querySelector("#videoStream")?.readyState>=2',timeout=45000)
    page.wait_for_timeout(500)
    page.mouse.move(300,300)
    print('READY',flush=True)
    for line in sys.stdin:
        command=json.loads(line)
        if command['action']=='quit': break
        if command['action']=='key':
            frame.locator('#overlayInput').focus()
            page.keyboard.press(command['key'])
        elif command['action']=='double':
            page.mouse.dblclick(command['x'],command['y'],delay=65)
        elif command['action']=='single':
            page.mouse.click(command['x'],command['y'])
        elif command['action']=='slow-pair':
            page.mouse.click(command['x'],command['y'])
            page.wait_for_timeout(650)
            page.mouse.click(command['x'],command['y'])
        page.wait_for_timeout(650)
        print('OK',flush=True)
    browser.close()
'''
process=subprocess.Popen(['docker','exec','-i',browser_container,'/tmp/browser-tools/bin/python','-u','-c',driver],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)

def send(action, **values):
    process.stdin.write(json.dumps({'action':action,**values})+'\n')
    process.stdin.flush()
    assert process.stdout.readline().strip()=='OK', (action,values)

try:
    assert process.stdout.readline().strip()=='READY'
    send('key',key='Escape')
    wait(lambda:not picker(),'Old wallpaper picker did not close')
    before=bar()
    send('single',x=300,y=12)
    assert bar()==before, 'Single click changed the bar background'
    send('slow-pair',x=300,y=12)
    assert bar()==before, 'Slow independent clicks were treated as a double click'
    send('double',x=300,y=12)
    wait(lambda:bar()!=before,'Double click did not cycle the bar background')
    print('PASS: bar double click changes its background; single and slow clicks do not',flush=True)

    send('single',x=500,y=400)
    assert not picker(), 'Single desktop click opened the wallpaper picker'
    send('slow-pair',x=500,y=400)
    assert not picker(), 'Slow desktop clicks opened the wallpaper picker'
    before=background()
    send('double',x=500,y=400)
    wait(picker,'Desktop double click did not open the wallpaper picker')
    print('PASS: desktop double click opens the real wallpaper picker',flush=True)
    send('key',key='ArrowRight')
    send('double',x=640,y=400)
    wait(lambda:not picker(),'Wallpaper selection did not close the picker')
    wait(lambda:background()!=before,'Selecting a different wallpaper did not update its link')
    print('PASS: selecting a different wallpaper updates the background and closes the picker',flush=True)
finally:
    if process.poll() is None:
        process.communicate(json.dumps({'action':'quit'})+'\n',timeout=20)
assert process.returncode==0

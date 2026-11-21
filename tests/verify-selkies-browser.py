#!/usr/bin/env python3
"""Exercise the adapter through the loopback prefix/auth proxy in selkies-proxy.conf.

Requires Playwright/Chromium; run only against the disposable labeled test setup.
The host companion must verify the marker files and final compositor geometry.
"""
from playwright.sync_api import sync_playwright

URL = 'https://127.0.0.1:16915'
PREFIX = '/desktop/selkies-browser-test/vnc/'
QUERY = 'autoconnect=1&path=desktop/selkies-browser-test/vnc/websockify&resize=remote&video_quality=4&clipboard_up=true&clipboard_down=true&clipboard_seamless=true'


def parent_page(context, query=QUERY):
    page = context.new_page()
    errors = []
    sockets = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('websocket', lambda socket: sockets.append(socket.url))
    html = '''<!doctype html><html><body style="margin:0;overflow:hidden">
    <script>window.events=[];addEventListener('message',e=>{
      if(e.source===document.querySelector('iframe')?.contentWindow)events.push(e.data);
    });</script><iframe id="iframe-id" style="width:100vw;height:100vh;border:0" src="''' + PREFIX + 'vnc.html?' + query + '''"></iframe></body></html>'''
    page.route(URL + '/kasm-parent-test', lambda route: route.fulfill(content_type='text/html', body=html))
    page.goto(URL + '/kasm-parent-test')
    page.wait_for_function("events.some(e=>e.action==='noVNC_initialized')", timeout=30000)
    page.wait_for_function("events.some(e=>e.action==='connection_state'&&e.value==='connected')", timeout=30000)
    frame = page.frames[1]
    frame.wait_for_function("window.stream_info?.hardware && window.stream_info.encoder==='NVENC'", timeout=30000)
    assert frame.evaluate('window.stream_info.zero_copy')
    assert frame.evaluate('window.stream_client.transport') == 'websockets'
    assert frame.evaluate('window.video_crf') == 5
    return page, frame, errors, sockets


def message(page, action, **values):
    page.evaluate("m=>document.querySelector('iframe').contentWindow.postMessage(m,location.origin)",
                  {'action': action, **values})


def resize(page, frame, action, expected, **values):
    message(page, action, **values)
    frame.wait_for_function('expected=>window.stream_client?.resolution===expected', arg=expected, timeout=20000)
    frame.wait_for_function("""expected=>{
        const video=document.querySelector('#videoStream');
        return video?.readyState>=2 && `${video.videoWidth}x${video.videoHeight}`===expected;
    }""", arg=expected, timeout=15000)


with sync_playwright() as playwright:
    browser = playwright.chromium.launch(executable_path='/usr/bin/chromium',
        args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'])
    context = browser.new_context(ignore_https_errors=True, viewport={'width': 1280, 'height': 800},
                                  permissions=['clipboard-read', 'clipboard-write'])
    page, frame, errors, sockets = parent_page(context)
    assert context.request.get(URL + PREFIX + 'api/status').status == 403
    assert frame.url.startswith(URL + PREFIX + 'vnc.html?')
    assert any(url.startswith(URL.replace('https:', 'wss:') + PREFIX + 'websockify') for url in sockets), sockets
    print('PASS: proxy session URL, injected HTTP auth, lifecycle notifications, NVENC/zero-copy video', flush=True)

    page.mouse.move(200, 120)
    frame.wait_for_function("""() => {
        const input = window.webrtcInput;
        return input && !input.use_browser_cursors && input._cursorImageBitmap
            && getComputedStyle(input.element).cursor.startsWith('url("data:image/png;base64,')
            && input.cursorDiv.classList.contains('kasm-selkies-video-cursor')
            && getComputedStyle(input.cursorDiv).visibility === 'hidden';
    }""", timeout=15000)
    assert page.locator('#iframe-id').evaluate("e => getComputedStyle(e).cursor.startsWith('url(\"data:image/png;base64,')")
    # Exercise focus/entry recovery and a native context's cursor reset without
    # using the parent control panel as the workaround.
    frame.evaluate("""() => {
        window.dispatchEvent(new Event('blur'));
        window.webrtcInput.element.style.cursor = 'auto';
        window.frameElement.style.cursor = 'auto';
        window.dispatchEvent(new Event('focus'));
    }""")
    assert frame.evaluate("getComputedStyle(window.webrtcInput.element).cursor.startsWith('url(\"data:image/png;base64,')")
    assert page.locator('#iframe-id').evaluate("e => getComputedStyle(e).cursor.startsWith('url(\"data:image/png;base64,')")
    frame.evaluate("window.webrtcInput.element.style.cursor = 'none'")
    frame.wait_for_function("getComputedStyle(window.webrtcInput.element).cursor.startsWith('url(\"data:image/png;base64,')")
    print('PASS: stream hides both browser and canvas pointers for the video-only cursor', flush=True)

    message(page, 'show_keyboard_controls')
    frame.locator('#kasm-selkies-keys').wait_for(state='visible')
    assert frame.locator('#kasm-selkies-keys button').first.evaluate("e => getComputedStyle(e).cursor") != 'none'
    message(page, 'hide_keyboard_controls')
    frame.locator('#kasm-selkies-keys').wait_for(state='hidden')
    message(page, 'set_perf_stats', value=True)
    frame.locator('#kasm-selkies-stats').wait_for(state='visible')
    frame.wait_for_function("document.querySelector('#kasm-selkies-stats').textContent.includes('NVENC')")
    message(page, 'control_displays')
    page.wait_for_function("events.some(e=>e.action==='can_control_displays'&&e.value===false)")
    message(page, 'setvideoquality', value=2, frameRate=30)
    frame.wait_for_function("""() => {
        const ns=(location.origin+location.pathname).replace(/[^a-zA-Z0-9._-]/g,'_');
        return localStorage.getItem(ns+'_video_crf')==='22' && localStorage.getItem(ns+'_framerate')==='30';
    }""")
    frame.wait_for_function('window.stream_stats?.latest?.encoded_fps>=20 && window.stream_stats.latest.encoded_fps<=35', timeout=15000)
    message(page, 'set_resolution', value_x=1024, value_y=768)
    message(page, 'resize', value='scale')
    page.wait_for_timeout(300)
    assert frame.evaluate('window.stream_client.resolution') == '1280x800'
    message(page, 'resize', value='off')
    message(page, 'resize', value='remote')
    print('PASS: keyboard controls, stats, quality/FPS, fixed native resolution and local scaling', flush=True)

    frame.locator('#overlayInput').click(position={'x': 300, 'y': 200})
    page.keyboard.press('Control+Shift+Enter')
    page.wait_for_timeout(1500)
    page.keyboard.type('touch /tmp/selkies-browser-keyboard', delay=10)
    page.keyboard.press('Enter')
    message(page, 'clipboardsnd', value='touch /tmp/selkies-browser-clipboard')
    page.wait_for_timeout(400)
    page.keyboard.press('Control+Shift+v')
    page.keyboard.press('Enter')
    page.wait_for_timeout(400)
    cdp = context.new_cdp_session(page)
    cdp.send('Input.dispatchKeyEvent', {'type':'keyDown','key':'F18','code':'F18','windowsVirtualKeyCode':129,'nativeVirtualKeyCode':129})
    page.wait_for_timeout(600)  # Exercise the modifier heartbeat too.
    page.keyboard.press('Enter')
    cdp.send('Input.dispatchKeyEvent', {'type':'keyUp','key':'F18','code':'F18','windowsVirtualKeyCode':129,'nativeVirtualKeyCode':129})
    page.wait_for_timeout(1500)
    page.keyboard.type('touch /tmp/selkies-browser-f18-release', delay=10)
    page.keyboard.press('Enter')
    message(page, 'clipboardsnd', value='printf selkies-clipboard-out | wl-copy')
    page.wait_for_timeout(400)
    page.keyboard.press('Control+Shift+v')
    page.keyboard.press('Enter')
    page.wait_for_function("events.some(e=>e.action==='clipboardrx'&&e.value==='selkies-clipboard-out')", timeout=15000)
    page.keyboard.press('Control+Shift+1')
    page.wait_for_function("events.some(e=>e.action==='togglenav')")
    print('PASS: browser keyboard, clipboard both directions, F18 chord/release, panel hotkey (host markers checked separately)', flush=True)

    # A self/sibling frame cannot impersonate Kasm's parent controller.
    frame.evaluate("window.postMessage({action:'terminate'},location.origin)")
    page.wait_for_timeout(300)
    assert 'selkies-disconnected' not in frame.url
    before = page.evaluate("events.filter(e=>e.action==='connection_state'&&e.value==='connected').length")
    frame.evaluate('window.selkiesTransport.close()')
    page.wait_for_function("n=>events.filter(e=>e.action==='connection_state'&&e.value==='connected').length>n", arg=before, timeout=30000)
    message(page, 'terminate')
    frame.wait_for_url('**/selkies-disconnected.html')
    page.wait_for_timeout(1500)
    assert page.frames[1].url.endswith('/selkies-disconnected.html')
    assert not errors, errors
    print('PASS: controller-source check, automatic reconnect, explicit termination without reconnect', flush=True)
    context.close()

    restricted = browser.new_context(ignore_https_errors=True, viewport={'width': 1280, 'height': 800})
    page, frame, errors, sockets = parent_page(restricted, QUERY.replace('clipboard_up=true','clipboard_up=false').replace('clipboard_down=true','clipboard_down=false'))
    assert frame.evaluate("localStorage.getItem((location.origin+location.pathname).replace(/[^a-zA-Z0-9._-]/g,'_')+'_clipboard_in_enabled')") == 'false'
    assert frame.evaluate("localStorage.getItem((location.origin+location.pathname).replace(/[^a-zA-Z0-9._-]/g,'_')+'_clipboard_out_enabled')") == 'false'
    message(page, 'clipboardsnd', value='touch /tmp/selkies-browser-forbidden')
    page.wait_for_timeout(400)
    assert not page.evaluate("events.some(e=>e.action==='clipboardrx')")
    message(page, 'set_resolution', value_x=1024, value_y=768)
    page.wait_for_timeout(300)
    assert frame.evaluate('window.stream_client.resolution') == '1280x800'
    message(page, 'set_idle_timeout', value=1)
    page.wait_for_function("events.some(e=>e.action==='idle_session_timeout')", timeout=10000)
    frame.wait_for_url('**/selkies-disconnected.html')
    assert not errors, errors
    print('PASS: URL clipboard policy and idle timeout', flush=True)
    restricted.close()
    browser.close()

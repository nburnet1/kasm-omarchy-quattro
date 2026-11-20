#!/usr/bin/env python3
"""Browser check of the Kasm iframe contract against a disposable test endpoint.

Requires Playwright and Chromium. NOVNC_TEST_PASSWORD enables HTTP Basic auth.
This reproduces Kasm's iframe URLs/messages; it does not log into the dashboard.
"""
import os
import sys
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright


url = sys.argv[1] if len(sys.argv) > 1 else 'https://127.0.0.1:16910'
assert urlsplit(url).hostname in ('127.0.0.1', 'localhost'), 'Use a disposable loopback endpoint'
prefix = '/desktop/novnc-browser-test/vnc/'
password = os.environ.get('NOVNC_TEST_PASSWORD')
parent_html = '''<!doctype html><html><body style="margin:0">
<script>window.events=[]; addEventListener('message', e => {
  if (e.source === document.querySelector('iframe')?.contentWindow) events.push(e.data);
});</script>
<iframe id="iframe-id" style="width:100vw;height:100vh;border:0" src="''' + prefix + '''vnc.html?autoconnect=1&path=desktop/novnc-browser-test/vnc/websockify&resize=remote&video_quality=4&clipboard_up=true&clipboard_down=true"></iframe>
</body></html>'''

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(executable_path='/usr/bin/chromium',
        args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'])
    options = {'ignore_https_errors': True, 'viewport': {'width': 1280, 'height': 800}}
    if password:
        options['http_credentials'] = {'username': 'kasm_user', 'password': password}
    context = browser.new_context(**options)
    page = context.new_page()
    errors = []
    sockets = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('websocket', lambda ws: sockets.append(ws.url))
    page.route(url + '/kasm-parent-test', lambda route: route.fulfill(content_type='text/html', body=parent_html))
    # Reproduce Kasm's prefix-stripping reverse proxy for HTTP module/assets.
    page.route(url + prefix + '**', lambda route: route.continue_(
        url=route.request.url.replace(url + prefix, url + '/', 1)))
    page.goto(url + '/kasm-parent-test')
    page.wait_for_function("events.some(e => e.action === 'noVNC_initialized')", timeout=30000)
    page.wait_for_function("events.some(e => e.action === 'connection_state' && e.value === 'connected')", timeout=30000)
    assert sockets == [url.replace('https:', 'wss:') + prefix + 'websockify'], sockets
    frame = page.frame_locator('#iframe-id')
    canvas = frame.locator('canvas')
    canvas.wait_for()
    iframe = page.frames[1]
    iframe.wait_for_function("""() => {
        const canvas = document.querySelector('canvas');
        if (!canvas || !canvas.width || !canvas.height) return false;
        const pixels = canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data;
        return new Set(pixels).size > 20;
    }""")
    print('PASS: real Chromium/noVNC render, authenticated WebSocket, correct Kasm session URL and lifecycle messages')

    def message(action, **values):
        page.evaluate("message => document.querySelector('iframe').contentWindow.postMessage(message, location.origin)",
                      {'action': action, **values})

    message('control_displays')
    page.wait_for_function("events.some(e => e.action === 'can_control_displays' && e.value === false)")
    message('show_keyboard_controls')
    frame.locator('#noVNC_modifiers').wait_for(state='visible')
    message('hide_keyboard_controls')
    frame.locator('#noVNC_modifiers').wait_for(state='hidden')
    message('setvideoquality', value=2)
    message('resize', value='scale')
    iframe.wait_for_function("async () => { const {default: UI} = await import('./app/ui.js'); return UI.rfb.scaleViewport && !UI.rfb.resizeSession && UI.rfb.qualityLevel === 6; }")
    message('resize', value='remote')
    iframe.wait_for_function("async () => { const {default: UI} = await import('./app/ui.js'); return UI.rfb.resizeSession; }")
    message('set_resolution', value_x=1024, value_y=768)
    iframe.wait_for_function("async () => { const {default: UI} = await import('./app/ui.js'); return UI.rfb._fbWidth === 1024 && UI.rfb._fbHeight === 768; }")
    message('resize', value='remote')
    message('clipboardsnd', value='novnc-browser-clipboard')

    canvas.click(position={'x': 300, 'y': 200})
    page.keyboard.press('Control+Shift+Enter')
    page.wait_for_timeout(1500)  # Native terminal cold-start, outside the DOM.
    page.keyboard.type('touch /tmp/novnc-browser-verified', delay=10)
    page.keyboard.press('Enter')
    page.wait_for_timeout(500)
    message('clipboardsnd', value='touch /tmp/novnc-browser-clipboard')
    page.wait_for_timeout(300)
    page.keyboard.press('Control+Shift+v')
    page.keyboard.press('Enter')
    page.wait_for_timeout(500)
    if os.environ.get('NOVNC_TEST_SCREENSHOT'):
        page.screenshot(path=os.environ['NOVNC_TEST_SCREENSHOT'])
    assert not errors, errors
    print('PASS: dashboard keyboard controls, quality and resize messages; browser mouse/keyboard events sent')
    message('terminate')
    page.wait_for_function("events.some(e => e.action === 'connection_state' && e.value === 'disconnected')")
    print('PASS: dashboard termination reports disconnected; no browser JavaScript errors')
    context.close()
    browser.close()

// Kasm dashboard adapter for the pinned Selkies 2.2.1 WebSocket client.
// Video remains the native Selkies/NVENC stream; this module only bridges UI.
const embedded = window.parent !== window && /\/desktop\/[^/]+\/vnc\//.test(location.pathname);
if (embedded) {
    const query = new URLSearchParams(location.search);
    const parentOrigin = new URL(document.referrer || location.href).origin;
    const notify = (action, value = null) => window.parent.postMessage({action, value}, parentOrigin);
    const native = message => window.postMessage(message, location.origin);
    const allowed = name => !['false', '0'].includes(query.get(name));
    const quality = value => [40, 30, 22, 12, 5][Number(value)] ?? 5;
    const clipIn = allowed('clipboard_up'), clipOut = allowed('clipboard_down');
    const namespace = (location.origin + location.pathname).replace(/[^a-zA-Z0-9._-]/g, '_');
    let configured = false, connected = false, terminating = false;
    let resizeMode = ['remote', 'scale', 'off'].includes(query.get('resize')) ? query.get('resize') : 'remote';
    let fixedSize = null, perf = query.get('enable_perf_stats') === 'true';
    let serverFixedResolution = false;
    let idleSeconds = Math.max(0, Number(query.get('idle_disconnect')) || 0) * 60;
    let lastActive = Date.now();
    let crf = query.has('video_quality') ? quality(query.get('video_quality')) : 5;
    let framerate = 60;
    // Selkies publishes these integration handles before initializing the core
    // and its socket. Wrap them without patching minified function names.
    let initialize, transport;
    Object.defineProperty(window, 'selkiesCoreInitialize', {
        configurable: true,
        get: () => initialize,
        set: fn => {
            initialize = function (...args) {
                const result = fn.apply(this, args);
                window.dispatchEvent(new Event('selkies-kasm-initialized'));
                return result;
            };
        },
    });
    Object.defineProperty(window, 'selkiesTransport', {
        configurable: true,
        get: () => transport,
        set: value => {
            transport = value;
            if (!value) return;
            for (const [event, state] of [['open', 'connecting'], ['close', 'disconnected'], ['error', 'error']]) {
                value.addEventListener(event, () => {
                    if (transport === value) window.dispatchEvent(new CustomEvent('selkies-kasm-state', {detail: state}));
                });
            }
        },
    });
    const preferences = {
        video_crf: crf, rate_control_mode: 'crf', keyboard_shortcuts: false,
        mac_cmd_as_ctrl: false, clipboard_in_enabled: clipIn, clipboard_out_enabled: clipOut,
        clipboard_seamless: allowed('clipboard_seamless'),
        use_css_scaling: !['true', '1'].includes(query.get('enable_hidpi')),
        // Hide the browser pointer. The captured-video cursor is the sole
        // pointer; suppress Selkies' separate canvas sprite below as well.
        use_browser_cursors: false,
    };
    // Apply the dashboard's clipboard policy before the native clipboard sync starts.
    for (const [name, value] of Object.entries(preferences)) {
        try { localStorage.setItem(`${namespace}_${name}`, String(value)); } catch (_) { /* storage disabled */ }
    }

    // A real transparent cursor avoids Electron/macOS losing cursor:none's
    // hidden state when switching windows, while the video supplies the sprite.
    const invisibleCursor = 'url("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAAGklEQVR4nO3BAQEAAACCIP+vbkhAAQAAAO8GECAAARlDNO4AAAAASUVORK5CYII=") 0 0, none';
    const style = document.createElement('style');
    style.textContent = `
        #root, #touch-gamepad-host { display:none !important; }
        html.kasm-selkies-streaming, html.kasm-selkies-streaming body { cursor:${invisibleCursor} !important; }
        .kasm-selkies-video-cursor { visibility:hidden !important; }
        #kasm-selkies-stats, #kasm-selkies-keys {
            position:fixed;z-index:2147483647;background:#171923e8;color:#eee;
            font:12px/1.5 monospace;padding:9px;border:1px solid #666;border-radius:6px;
        }
        #kasm-selkies-stats { top:8px;right:8px;white-space:pre;pointer-events:none; }
        #kasm-selkies-keys { bottom:8px;left:50%;transform:translateX(-50%);display:flex;gap:5px;cursor:auto; }
        #kasm-selkies-keys[hidden], #kasm-selkies-stats[hidden] { display:none !important; }
        #kasm-selkies-keys button { background:#303448;color:white;padding:6px 10px;border:1px solid #777;border-radius:4px; }
    `;
    document.head.append(style);
    let statsPanel, keyPanel;

    function chord(keys) {
        const input = window.webrtcInput;
        if (!connected || !input) return;
        for (const [keysym, code] of keys) input._sendKeyEvent(keysym, code, true);
        for (const [keysym, code] of [...keys].reverse()) input._sendKeyEvent(keysym, code, false);
        input.element.focus();
    }

    function buildPanels() {
        if (statsPanel) return;
        statsPanel = document.createElement('div');
        statsPanel.id = 'kasm-selkies-stats'; statsPanel.hidden = true;
        keyPanel = document.createElement('div');
        keyPanel.id = 'kasm-selkies-keys'; keyPanel.hidden = true;
        const ctrl = [0xffe3, 'ControlLeft'], shift = [0xffe1, 'ShiftLeft'], superKey = [0xffeb, 'MetaLeft'];
        const buttons = [
            ['Esc', [[0xff1b, 'Escape']]], ['Tab', [[0xff09, 'Tab']]],
            ['Ctrl+Shift+C', [ctrl, shift, [0x63, 'KeyC']]], ['Ctrl+Shift+V', [ctrl, shift, [0x76, 'KeyV']]],
            ['Terminal', [superKey, [0xff0d, 'Enter']]], ['Menu', [superKey, [0x20, 'Space']]],
        ];
        for (const [label, keys] of buttons) {
            const button = document.createElement('button'); button.textContent = label;
            button.addEventListener('pointerdown', event => event.preventDefault());
            button.addEventListener('click', () => chord(keys));
            keyPanel.append(button);
        }
        document.body.append(statsPanel, keyPanel);
    }

    function renderStats() {
        if (!perf || !statsPanel) return;
        const info = window.stream_info || {}, client = window.stream_client || {};
        const stats = window.stream_stats?.latest || {};
        const value = (name, unit) => stats[name] == null ? '—' : `${stats[name]}${unit}`;
        statsPanel.textContent = [
            `Selkies · ${info.encoder || 'starting'} ${info.codec || 'H.264'} · ${info.fullcolor ? '4:4:4' : '4:2:0'}`,
            `${client.resolution || ''} · ${value('fps', ' FPS')} · quality ${crf}`,
            `Encode ${value('encode_ms', ' ms')} · Decode ${value('decode_ms', ' ms')}`,
            `${value('mbps', ' Mbit/s')} · decoder ${client.decoder || 'unknown'}`,
        ].join('\n');
    }

    function showStats(value) {
        perf = !!value; buildPanels(); statsPanel.hidden = !perf;
        native({type: 'statsOpen', open: perf}); renderStats();
    }

    function resolution() {
        const match = /^(\d+)x(\d+)$/.exec(window.stream_client?.resolution || '');
        if (match) return {width: Number(match[1]), height: Number(match[2])};
        const canvas = document.getElementById('videoCanvas');
        return {width: canvas?.width || 1920, height: canvas?.height || 1080};
    }

    function applyResize() {
        if (!connected) return;
        if (serverFixedResolution) {
            native({type: 'setScaleLocally', value: resizeMode !== 'off'});
            return;
        }
        if (resizeMode === 'remote' && !fixedSize) {
            native({type: 'resetResolutionToWindow'});
        } else {
            native({type: 'setManualResolution', ...(fixedSize || resolution())});
            native({type: 'setScaleLocally', value: resizeMode === 'scale'});
        }
    }

    function settings() {
        native({type: 'settings', settings: {...preferences, video_crf: crf, framerate}});
    }

    const hostFrame = window.frameElement;
    const hostCursor = hostFrame && {
        value: hostFrame.style.getPropertyValue('cursor'),
        priority: hostFrame.style.getPropertyPriority('cursor'),
    };
    let cursorTarget = null, cursorObserver = null;

    function hideLocalCursor() {
        if (connected && cursorTarget && cursorTarget.style.getPropertyValue('cursor') !== invisibleCursor) {
            cursorTarget.style.setProperty('cursor', invisibleCursor, 'important');
        }
    }

    function syncCursorBoundary() {
        document.documentElement.classList.toggle('kasm-selkies-streaming', connected);
        if (hostFrame) {
            if (connected) hostFrame.style.setProperty('cursor', invisibleCursor, 'important');
            else if (hostCursor.value) hostFrame.style.setProperty('cursor', hostCursor.value, hostCursor.priority);
            else hostFrame.style.removeProperty('cursor');
        }
        const target = connected ? window.webrtcInput?.element : null;
        if (target !== cursorTarget) {
            cursorObserver?.disconnect();
            cursorTarget = target;
            if (target) {
                // Native input handlers reset the inline cursor during hover
                // and cursor-shape updates. Keep our transparent image in force.
                cursorObserver = new MutationObserver(hideLocalCursor);
                cursorObserver.observe(target, {attributes: true, attributeFilter: ['style']});
            }
        }
        hideLocalCursor();
    }

    // Electron can fall back to the parent iframe's cursor while focus/hit
    // testing crosses the viewer boundary. Keep that boundary hidden too,
    // without changing the Kasm control panel or taking keyboard focus.
    for (const type of ['focus', 'pageshow', 'pointerover']) {
        window.addEventListener(type, syncCursorBoundary);
    }
    document.addEventListener('visibilitychange', () => {
        if (!document.hidden) syncCursorBoundary();
    });

    function useVideoCursor() {
        const input = window.webrtcInput;
        if (!connected || !input) return;
        syncCursorBoundary();
        input.cursorDiv.classList.add('kasm-selkies-video-cursor');
        input.send('SET_NATIVE_CURSOR_RENDERING,1');
    }

    document.addEventListener('pointerlockchange', () => {
        // The native handler turns video cursor painting off on unlock. Apply
        // this adapter's single-video-cursor policy after that handler finishes.
        if (!document.pointerLockElement) queueMicrotask(useVideoCursor);
    });

    function stop(reason = 'Disconnected') {
        if (terminating) return;
        terminating = true; connected = false;
        syncCursorBoundary();
        window.webrtcInput?.resetKeyboard();
        notify('connection_state', 'disconnected'); notify('disconnectrx', reason);
        window.selkiesTransport?.close();
        // Navigation ends the native client's automatic reconnect timers too.
        location.replace(new URL('./selkies-disconnected.html', location.href));
    }

    window.addEventListener('selkies-kasm-initialized', () => {
        buildPanels(); notify('noVNC_initialized'); notify('connection_state', 'connecting');
    });
    window.addEventListener('selkies-kasm-state', event => {
        if (terminating) return;
        if (event.detail === 'streaming') {
            connected = true; notify('connection_state', 'connected');
            if (!configured) {
                configured = true; settings(); applyResize(); showStats(perf);
            }
            useVideoCursor();
        } else if (['disconnected', 'error'].includes(event.detail)) {
            connected = false; notify('connection_state', 'disconnected');
        } else if (event.detail === 'connecting') {
            connected = false; notify('connection_state', 'connecting');
        }
        syncCursorBoundary();
    });
    window.addEventListener('selkies-stream-stats', renderStats);
    window.addEventListener('message', event => {
        if (event.source === window && event.origin === location.origin) {
            if (event.data?.type === 'serverSettings') {
                const manual = event.data.payload?.manual_resolution;
                serverFixedResolution = !!(manual?.locked && manual.value);
            }
            if (event.data?.type === 'clipboardContentUpdate' && clipOut && typeof event.data.text === 'string') {
                notify('clipboardrx', event.data.text);
            } else if (event.data?.type === 'toggleDashboard') notify('togglenav');
            return;
        }
        if (event.source !== window.parent || event.origin !== parentOrigin || terminating) return;
        const message = event.data;
        if (!message || typeof message !== 'object') return;
        switch (message.action) {
            case 'clipboardsnd':
                if (clipIn && typeof message.value === 'string') native({type: 'clipboardUpdateFromUI', text: message.value});
                break;
            case 'setvideoquality': {
                crf = quality(message.qualityLevel ?? message.value);
                const fps = Number(message.frameRate);
                if (Number.isFinite(fps) && fps >= 8 && fps <= 60) framerate = Math.round(fps);
                if (connected) settings();
                break;
            }
            case 'resize':
                if (['remote', 'scale', 'off'].includes(message.value)) {
                    resizeMode = message.value; fixedSize = null; applyResize();
                }
                break;
            case 'set_resolution': {
                if (serverFixedResolution) break;
                const width = Number(message.value_x), height = Number(message.value_y);
                if ([width, height].every(n => Number.isInteger(n) && n >= 32 && n <= 8192)) {
                    fixedSize = {width: width - width % 2, height: height - height % 2};
                    if (resizeMode === 'remote') resizeMode = 'scale';
                    applyResize();
                }
                break;
            }
            case 'enable_hidpi':
                preferences.use_css_scaling = !message.value;
                native({type: 'setUseCssScaling', value: preferences.use_css_scaling});
                break;
            case 'set_perf_stats': showStats(message.value); break;
            case 'show_keyboard_controls': buildPanels(); keyPanel.hidden = false; break;
            case 'hide_keyboard_controls': buildPanels(); keyPanel.hidden = true; break;
            case 'control_displays': notify('can_control_displays', false); break;
            case 'set_idle_timeout': idleSeconds = Math.max(0, Number(message.value) || 0); break;
            case 'terminate': stop(); break;
        }
    });

    for (const type of ['keydown', 'pointerdown', 'pointermove', 'wheel', 'touchstart']) {
        window.addEventListener(type, () => { lastActive = Date.now(); }, {capture: true, passive: true});
    }
    window.addEventListener('keyup', event => {
        if (event.ctrlKey && event.shiftKey && event.code === 'Digit1') notify('togglenav');
    }, true);
    const idleTimer = setInterval(() => {
        if (!terminating && connected && idleSeconds > 0 && Date.now() - lastActive >= idleSeconds * 1000) {
            notify('idle_session_timeout', 'Idle session timeout exceeded'); stop('Idle timeout');
        }
    }, 1000);
    window.addEventListener('unload', () => {
        clearInterval(idleTimer);
        connected = false; syncCursorBoundary();
    });
}

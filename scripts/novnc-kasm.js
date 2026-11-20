// Kasm dashboard adapter for upstream noVNC. No frame decoding or proxying here.
export function installKasmIntegration(UI) {
    const embedded = window.parent !== window && /\/desktop\/[^/]+\/vnc\//.test(location.pathname);
    if (!embedded) return;

    const query = new URLSearchParams(location.search);
    const parentOrigin = new URL(document.referrer || location.href).origin;
    const enabled = name => !['false', '0'].includes(query.get(name));
    const notify = (action, value = null) => window.parent.postMessage({action, value}, parentOrigin);
    let lastActive = Date.now();
    let idleSeconds = Number(query.get('idle_disconnect') || 0) * 60;
    const clipboardUp = enabled('clipboard_up');
    const clipboardDown = enabled('clipboard_down');
    const hideControlbar = () => document.getElementById('noVNC_control_bar_anchor').style.setProperty('display', 'none', 'important');

    const initSettings = UI.initSettings;
    UI.initSettings = function (...args) {
        initSettings.apply(UI, args);
        // Kasm supplies a path relative to the origin, not the iframe directory.
        const path = query.get('path');
        if (path) UI.forceSetting('path', '/' + path.replace(/^\/+/, ''));
        UI.forceSetting('resize', query.get('resize') || 'remote');
    };

    const updateVisualState = UI.updateVisualState;
    UI.updateVisualState = function (state) {
        updateVisualState.call(UI, state);
        notify('connection_state', state);
    };

    const connect = UI.connect;
    UI.connect = function (...args) {
        const result = connect.apply(UI, args);
        if (!UI.rfb) return result;
        // Reproduce the baseline's remote-only Mac key mapping without Xvnc.
        const sendKey = UI.rfb.sendKey.bind(UI.rfb);
        UI.rfb.sendKey = (keysym, code, down) => keysym === 0xffcf
            ? sendKey(0xffeb, 'MetaLeft', down) : sendKey(keysym, code, down);
        UI.rfb.qualityLevel = [2, 4, 6, 8, 9][Number(query.get('video_quality'))] ?? 8;
        UI.rfb.addEventListener('disconnect', event => notify('disconnectrx', event.detail.reason || 'Disconnected'));
        return result;
    };

    const clipboardReceive = UI.clipboardReceive;
    UI.clipboardReceive = function (event) {
        if (!clipboardDown) return;
        clipboardReceive.call(UI, event);
        notify('clipboardrx', event.detail.text);
    };

    window.addEventListener('message', event => {
        if (event.source !== window.parent || event.origin !== parentOrigin) return;
        const message = event.data;
        if (!message || typeof message !== 'object') return;
        switch (message.action) {
            case 'clipboardsnd':
                if (clipboardUp && typeof message.value === 'string') UI.rfb?.clipboardPasteFrom(message.value);
                break;
            case 'resize':
                if (['off', 'scale', 'remote'].includes(message.value)) {
                    UI.forceSetting('resize', message.value);
                    UI.applyResizeMode();
                }
                break;
            case 'setvideoquality':
                if (UI.rfb) UI.rfb.qualityLevel = [2, 4, 6, 8, 9][Number(message.qualityLevel ?? message.value)] ?? 8;
                break;
            case 'set_resolution': {
                const width = Number(message.value_x), height = Number(message.value_y);
                if (UI.rfb?._supportsSetDesktopSize && [width, height].every(n => Number.isInteger(n) && n >= 32 && n <= 16384)) {
                    UI.forceSetting('resize', 'scale');
                    UI.applyResizeMode();
                    // The noVNC version is pinned; its public resizeSession
                    // property only supports matching the browser viewport.
                    UI.rfb.constructor.messages.setDesktopSize(UI.rfb._sock, width, height,
                        UI.rfb._screenID, UI.rfb._screenFlags);
                }
                break;
            }
            case 'set_idle_timeout':
                idleSeconds = Math.max(0, Number(message.value) || 0);
                break;
            case 'control_displays':
                notify('can_control_displays', false);
                break;
            case 'show_keyboard_controls':
                document.getElementById('noVNC_control_bar_anchor').style.removeProperty('display');
                UI.openControlbar();
                UI.openExtraKeys();
                break;
            case 'hide_keyboard_controls':
                UI.closeExtraKeys();
                if (!query.has('show_control_bar') || !enabled('show_control_bar')) {
                    hideControlbar();
                }
                break;
            case 'terminate':
                UI.disconnect();
                break;
        }
    });

    for (const type of ['keydown', 'pointerdown', 'pointermove', 'wheel', 'touchstart']) {
        document.addEventListener(type, () => { lastActive = Date.now(); }, {capture: true, passive: true});
    }
    document.addEventListener('pointerdown', () => notify('enable_audio'), {passive: true});
    document.addEventListener('keyup', event => {
        if (event.ctrlKey && event.shiftKey && event.code === 'Digit1') notify('togglenav');
    }, true);
    const idleTimer = setInterval(() => {
        if (UI.connected && idleSeconds > 0 && Date.now() - lastActive > idleSeconds * 1000) {
            notify('idle_session_timeout', 'Idle session timeout exceeded');
            UI.disconnect();
        }
    }, 1000);
    window.addEventListener('unload', () => clearInterval(idleTimer));

    const start = UI.start;
    UI.start = async function (...args) {
        const result = await start.apply(UI, args);
        if (!enabled('show_control_bar') || !query.has('show_control_bar')) {
            hideControlbar();
        }
        notify('noVNC_initialized');
        return result;
    };
}

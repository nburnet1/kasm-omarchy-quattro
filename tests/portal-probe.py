"""Exercise the real file-chooser portal from inside an isolated test session."""
import json
from pathlib import Path
from gi.repository import Gio, GLib

root = Path('/tmp/omarchy-essentials-smoke')
bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
loop = GLib.MainLoop()

def response(connection, sender, path, interface, signal, parameters):
    print('Portal response:', path, parameters.unpack(), flush=True)
    if 'essentials_probe' not in path:
        return
    code, values = parameters.unpack()
    (root / 'portal-result.json').write_text(json.dumps({'response': code, 'uris': values.get('uris', [])}))
    loop.quit()

bus.signal_subscribe(None, 'org.freedesktop.portal.Request', 'Response', None, None,
                     Gio.DBusSignalFlags.NONE, response)
bus.call_sync('org.freedesktop.portal.Desktop', '/org/freedesktop/portal/desktop',
              'org.freedesktop.portal.FileChooser', 'OpenFile',
              GLib.Variant('(ssa{sv})', ('', 'Essentials file chooser verification', {
                  'handle_token': GLib.Variant('s', 'essentials_probe'),
              })), None, Gio.DBusCallFlags.NONE, 15000, None)

def timeout():
    (root / 'portal-result.json').write_text(json.dumps({'error': 'timeout'}))
    loop.quit()
    return False

GLib.timeout_add_seconds(30, timeout)
loop.run()

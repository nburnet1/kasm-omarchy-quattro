"""Feed the external headless cursor plane into pinned Selkies cursor delivery."""
import asyncio
import io
import os
from pathlib import Path
import stat
import struct
import threading

from PIL import Image
from selkies.display_utils import format_pixelflux_cursor


class CursorSnapshot:
    def __init__(self, path):
        self.path = Path(path)
        self.revision = None
        self.payload = None
        self.lock = threading.Lock()

    def current(self):
        with self.lock:
            try:
                metadata = self.path.stat()
                revision = (metadata.st_ino, metadata.st_mtime_ns, metadata.st_size)
                if revision == self.revision:
                    return self.payload
                if (metadata.st_uid != os.getuid() or not stat.S_ISREG(metadata.st_mode)
                        or stat.S_IMODE(metadata.st_mode) != 0o600
                        or not 24 <= metadata.st_size <= 24 + 512 * 512 * 4):
                    return self.payload
                data = self.path.read_bytes()
                magic, width, height, hotx, hoty, visible = struct.unpack('<4sIIiiI', data[:24])
                if magic != b'OCUR':
                    return self.payload
                if visible == 0 and width == height == 0 and len(data) == 24:
                    payload = format_pixelflux_cursor('hide', None, 0, 0, 0)
                elif (visible == 1 and 0 < width <= 512 and 0 < height <= 512
                        and len(data) == 24 + width * height * 4):
                    image = Image.frombytes('RGBA', (width, height), data[24:])
                    output = io.BytesIO()
                    image.save(output, format='PNG', compress_level=1)
                    payload = format_pixelflux_cursor('png', output.getvalue(), hotx, hoty, width)
                else:
                    return self.payload
                self.revision = revision
                self.payload = payload
            except (OSError, ValueError, struct.error):
                pass
            return self.payload


def install_cursor_bridge(server_class, app_class):
    """Replace the internal-compositor sprite, preserving native auth/transport."""
    reader = CursorSnapshot(Path(os.environ['XDG_RUNTIME_DIR']) / 'omarchy-headless-cursor.bin')
    send_cursor = app_class.send_ws_cursor_data
    refresh_cache = server_class.refresh_cursor_cache
    run = server_class.run

    def external_cursor(self, data):
        payload = reader.current()
        return send_cursor(self, payload if payload is not None else data)

    def external_cache(self):
        payload = reader.current()
        if payload is not None and self.app is not None:
            self.app.last_cursor_sent = payload
            return payload
        return refresh_cache(self)

    async def watch_cursor(server):
        previous = None
        while True:
            payload = reader.current()
            if payload is not None and server.app is not None:
                key = (payload['handle'], payload['hotx'], payload['hoty'])
                if key != previous:
                    server.app.last_cursor_sent = payload
                    if server.clients:
                        send_cursor(server.app, payload)
                    previous = key
            # Only shapes cross the server. Pointer motion remains local.
            await asyncio.sleep(.02)

    async def run_with_cursor(self, *args, **kwargs):
        watcher = asyncio.create_task(watch_cursor(self), name='omarchy-headless-cursor')
        try:
            return await run(self, *args, **kwargs)
        finally:
            watcher.cancel()
            await asyncio.gather(watcher, return_exceptions=True)

    app_class.send_ws_cursor_data = external_cursor
    server_class.refresh_cursor_cache = external_cache
    server_class.run = run_with_cursor

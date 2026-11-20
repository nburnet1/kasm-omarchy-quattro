#!/usr/bin/env python3
"""Exercise TLS/WebSocket/RFB, capture, and input in a disposable container.

The browser companion checks resizing with a full client that handles desktop
layout updates and framebuffer requests throughout the resize negotiation.
"""
import base64
import hashlib
import json
import os
import socket
import ssl
import struct
import subprocess
import sys
import threading
import time
import urllib.request
import urllib.error


container = sys.argv[1]
port = int(sys.argv[2]) if len(sys.argv) > 2 else 16909
metadata = json.loads(subprocess.check_output(['docker', 'inspect', container]))[0]
assert metadata['Config'].get('Labels', {}).get('org.omarchy.kasm.test') == 'true'


def run(*args):
    return subprocess.check_output(['docker', 'exec', '-e', 'XDG_RUNTIME_DIR=/run/user/1000',
                                    container, *args], text=True).strip()


def wait(predicate, description):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.1)
    raise AssertionError('Timed out: ' + description)


context = ssl._create_unverified_context()  # Disposable endpoint's self-signed certificate.
password = os.environ.get('NOVNC_TEST_PASSWORD')
authorization = ''
if password:
    authorization = 'Basic ' + base64.b64encode(('kasm_user:' + password).encode()).decode()
    for bad_auth in ('', 'Basic ' + base64.b64encode(b'kasm_user:wrong-password').decode()):
        try:
            urllib.request.urlopen(urllib.request.Request(f'https://127.0.0.1:{port}/vnc.html',
                headers={'Authorization': bad_auth}), context=context)
        except urllib.error.HTTPError as error:
            assert error.code == 401
        else:
            raise AssertionError('Unauthenticated or incorrect credentials accepted')
    print('PASS: unauthenticated and wrong-password HTTP requests rejected')
request = urllib.request.Request(f'https://127.0.0.1:{port}/vnc.html', headers={'Authorization': authorization})
with urllib.request.urlopen(request, context=context) as response:
    assert response.status == 200 and b'noVNC' in response.read()
sock = context.wrap_socket(socket.create_connection(('127.0.0.1', port)), server_hostname='localhost')
sock.settimeout(15)


def exact(n):
    result = bytearray()
    while len(result) < n:
        chunk = sock.recv(n - len(result))
        if not chunk:
            raise EOFError('WebSocket closed')
        result.extend(chunk)
    return bytes(result)


key = base64.b64encode(os.urandom(16)).decode()
if password:
    for bad_auth in ('', 'Basic ' + base64.b64encode(b'kasm_user:wrong-password').decode()):
        with context.wrap_socket(socket.create_connection(('127.0.0.1', port)), server_hostname='localhost') as probe:
            probe.settimeout(10)
            probe.sendall((f'GET /websockify HTTP/1.1\r\nHost: localhost:{port}\r\n'
                'Upgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Version: 13\r\n'
                f'Sec-WebSocket-Key: {key}\r\nAuthorization: {bad_auth}\r\n\r\n').encode())
            assert b' 401 ' in probe.recv(4096).split(b'\r\n', 1)[0]
    print('PASS: unauthenticated and wrong-password WebSocket upgrades rejected')
sock.sendall((f'GET /websockify HTTP/1.1\r\nHost: localhost:{port}\r\n'
              f'Authorization: {authorization}\r\n'
              'Upgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Version: 13\r\n'
              f'Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Protocol: binary\r\n\r\n').encode())
headers = bytearray()
while not headers.endswith(b'\r\n\r\n'):
    headers.extend(exact(1))
assert b'101 Switching Protocols' in headers
accept = base64.b64encode(hashlib.sha1((key + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest())
assert accept in headers


send_lock = threading.Lock()


def send(payload, opcode=2):
    mask = os.urandom(4)
    n = len(payload)
    header = bytes([0x80 | opcode, 0x80 | n]) if n < 126 else bytes([0x80 | opcode, 0xfe]) + struct.pack('!H', n)
    with send_lock:
        sock.sendall(header + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))


buffer = bytearray()


def read(n):
    while len(buffer) < n:
        flags, size = exact(2)
        length = size & 127
        if length == 126:
            length = struct.unpack('!H', exact(2))[0]
        elif length == 127:
            length = struct.unpack('!Q', exact(8))[0]
        assert not size & 128
        payload = exact(length)
        opcode = flags & 15
        if opcode == 9:
            send(payload, 10)
        elif opcode in (0, 2):
            buffer.extend(payload)
        else:
            raise AssertionError(f'Unexpected WebSocket opcode {opcode}')
    result = bytes(buffer[:n])
    del buffer[:n]
    return result


assert read(12) == b'RFB 003.008\n'
send(b'RFB 003.008\n')
assert 1 in read(read(1)[0])
send(b'\x01')
assert read(4) == b'\0' * 4
send(b'\x01')
width, height = struct.unpack('!HH', read(4))
pixel_format = read(16)
assert pixel_format[0] == 32
name = read(struct.unpack('!I', read(4))[0]).decode()
send(struct.pack('!BBHiii', 2, 0, 3, 0, -223, -308))
send(struct.pack('!BBHHHH', 3, 0, 0, 0, width, height))
raw = bytearray()
screen_id = 0
while not raw:
    assert read(1) == b'\0'  # FramebufferUpdate
    _, count = struct.unpack('!BH', read(3))
    for _ in range(count):
        x, y, w, h, encoding = struct.unpack('!HHHHi', read(12))
        if encoding == 0:
            raw.extend(read(w * h * 4))
        elif encoding == -308:
            screens = read(4)[0]
            for _ in range(screens):
                screen_id = struct.unpack('!I', read(4))[0]
                read(12)
        elif encoding != -223:
            raise AssertionError(f'Unexpected encoding {encoding}')
assert len(set(raw)) > 20, 'Captured framebuffer appears blank'
print(f'PASS: noVNC page, TLS/WebSocket/RFB handshake, nonblank {width}x{height} capture ({name})')


def drain_updates():
    # Keep consuming resize responses and frames while exercising input. A real
    # browser always reads the stream; otherwise socket backpressure skews checks.
    try:
        while sock.recv(65536):
            pass
    except (OSError, ssl.SSLError):
        pass


threading.Thread(target=drain_updates, daemon=True).start()
stop_updates = threading.Event()


def request_updates():
    # Standard RFB clients keep requesting incremental frames, including while
    # a resize is in flight. Keep capture buffers flowing as the browser does.
    try:
        while not stop_updates.wait(.1):
            send(struct.pack('!BBHHHH', 3, 1, 0, 0, width, height))
    except OSError:
        pass


threading.Thread(target=request_updates, daemon=True).start()


def key_event(keysym, down):
    send(struct.pack('!BBHI', 4, down, 0, keysym))


def foot_count():
    return sum(w['class'] == 'foot' for w in json.loads(run('hyprctl', '-i', '0', '-j', 'clients')))


previous_foot_count = foot_count()
for keysym in (0xffe3, 0xffe1, 0xff0d):  # Ctrl+Shift+Return
    key_event(keysym, 1)
for keysym in (0xff0d, 0xffe1, 0xffe3):
    key_event(keysym, 0)
wait(lambda: foot_count() > previous_foot_count, 'terminal shortcut')
time.sleep(1)
marker = f'/tmp/omarchy-novnc-input-{time.time_ns()}'
for char in f'printf direct-wayvnc-verified > {marker}\n':
    keysym = 0xff0d if char == '\n' else ord(char)
    key_event(keysym, 1)
    key_event(keysym, 0)
wait(lambda: run('sh', '-c', f'test -f {marker} && cat {marker} || true') == 'direct-wayvnc-verified', 'typed command')
send(struct.pack('!BBHH', 5, 0, 300, 200))
wait(lambda: all(abs(a - b) <= 1 for a, b in zip(
    map(int, run('hyprctl', '-i', '0', 'cursorpos').split(',')), (300, 200))), 'pointer motion')
print('PASS: shortcut and typed command reach native Foot; pointer motion reaches Hyprland')

assert not run('hyprctl', '-i', '0', 'configerrors')
processes = run('ps', '-eo', 'comm').splitlines()
assert not any(p.strip() in ('Xvnc', 'Xkasmvnc', 'vncviewer', 'openbox') for p in processes)
print('PASS: no compositor config errors or outer display/viewer processes')
stop_updates.set()
send(b'', 8)
sock.close()

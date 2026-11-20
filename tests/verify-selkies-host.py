#!/usr/bin/env python3
"""Host-side checks after verify-selkies-browser.py, in a disposable GPU session."""
import base64
import http.client
import json
import os
import socket
import ssl
import struct
import subprocess
import sys
import time

container = sys.argv[1]
metadata = json.loads(subprocess.check_output(['docker', 'inspect', container]))[0]
assert metadata['Config'].get('Labels', {}).get('org.omarchy.kasm.test') == 'true'
environment = dict(value.split('=', 1) for value in metadata['Config']['Env'] if '=' in value)
password = environment['VNC_PW']
context = ssl._create_unverified_context()


def run(*args):
    return subprocess.check_output(['docker', 'exec', '-e', 'XDG_RUNTIME_DIR=/run/user/1000',
                                    container, *args], text=True).strip()


def port(number):
    binding = metadata['HostConfig']['PortBindings'][f'{number}/tcp'][0]
    assert binding['HostIp'] == '127.0.0.1'
    return int(binding['HostPort'])


def auth(value=password, user='kasm_user'):
    return 'Basic ' + base64.b64encode((user + ':' + value).encode()).decode()


for path in ('/vnc.html', '/selkies-core.js', '/api/sessions', '/selkies-status.json'):
    for header in ('', auth('incorrect-password'), auth(user='kasm_viewer')):
        connection = http.client.HTTPSConnection('127.0.0.1', port(6901), context=context, timeout=5)
        connection.request('GET', path, headers={'Authorization': header})
        response = connection.getresponse()
        assert response.status == 401, (path, response.status)
        response.read(); connection.close()
    connection = http.client.HTTPSConnection('127.0.0.1', port(6901), context=context, timeout=5)
    connection.request('GET', path, headers={'Authorization': auth()})
    response = connection.getresponse()
    assert response.status == 200, (path, response.status)
    body = response.read()
    connection.close()
print('PASS: pages, client code and API require the owning session credentials')
connection = http.client.HTTPSConnection('127.0.0.1', port(6901), context=context, timeout=5)
connection.request('GET', '/api/status')  # Native bootstrap/health endpoints are public.
status = json.loads(connection.getresponse().read())
assert status['current_mode'] == 'websockets' and status['enable_dual_mode'] is False
connection.close()


def websocket(number, path, authorization):
    sock = context.wrap_socket(socket.create_connection(('127.0.0.1', port(number)), timeout=5), server_hostname='localhost')
    sock.settimeout(5)
    key = base64.b64encode(os.urandom(16)).decode()
    sock.sendall((f'GET {path} HTTP/1.1\r\nHost: localhost:{port(number)}\r\n'
        'Upgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Version: 13\r\n'
        f'Sec-WebSocket-Key: {key}\r\nAuthorization: {authorization}\r\n\r\n').encode())
    headers = bytearray()
    while not headers.endswith(b'\r\n\r\n'):
        value = sock.recv(1)
        if not value:
            break
        headers.extend(value)
        assert len(headers) < 16384
    return sock, bytes(headers)


for header in ('', auth('incorrect-password')):
    sock, headers = websocket(6901, '/websockify', header)
    assert b' 401 ' in headers.split(b'\r\n')[0], headers
    sock.close()
sock, headers = websocket(6901, '/websockify', auth())
assert b' 101 ' in headers.split(b'\r\n')[0], headers
sock.close()
print('PASS: streaming WebSocket rejects absent/wrong credentials and accepts session auth')


markers = ('selkies-browser-keyboard', 'selkies-browser-clipboard', 'selkies-browser-f18-release')
for marker in markers:
    assert run('python', '-c', f'from pathlib import Path; print(Path("/tmp/{marker}").exists())') == 'True', marker
assert run('python', '-c', 'from pathlib import Path; print(Path("/tmp/selkies-browser-forbidden").exists())') == 'False'
clients = json.loads(run('hyprctl', '-i', '0', '-j', 'clients'))
assert sum(window['class'] == 'foot' for window in clients) == 2, clients
print('PASS: typed/pasted commands executed; F18 opened the second terminal and released; blocked paste absent')


def size():
    monitors = json.loads(run('hyprctl', '-i', '0', '-j', 'monitors'))
    return [(monitor['width'], monitor['height']) for monitor in monitors if monitor['name'] == 'HEADLESS-1']


assert size() == [(1280, 800)], size()
assert not run('hyprctl', '-i', '0', 'configerrors')
run('hyprctl', '-i', '0', 'reload')
time.sleep(.5)
assert size() == [(1280, 800)], size()
processes = run('ps', '-eo', 'comm').splitlines()
assert not any(name.strip() in ('Xvnc', 'Xkasmvnc', 'vncviewer', 'wayvnc', 'openbox') for name in processes)
print('PASS: native Hyprland resolution preserved through controls/reload; no VNC/display bridge processes')

for header in ('', auth('incorrect-password')):
    sock, headers = websocket(4901, '/', header)
    # The native Kasm relay upgrades first, then closes unauthorized sockets.
    if b' 101 ' in headers.split(b'\r\n')[0]:
        head = sock.recv(2)
        assert not head or head[0] & 15 == 8, (headers, head)
    else:
        assert b' 401 ' in headers.split(b'\r\n')[0], headers
    sock.close()
sock, headers = websocket(4901, '/', auth())
assert b' 101 ' in headers.split(b'\r\n')[0], headers


def exact(n):
    data = bytearray()
    while len(data) < n:
        value = sock.recv(n - len(data))
        if not value:
            raise EOFError('Audio socket closed')
        data.extend(value)
    return bytes(data)


binary = False
for _ in range(10):
    flags, length = exact(2)
    length &= 127
    if length == 126:
        length = struct.unpack('!H', exact(2))[0]
    elif length == 127:
        length = struct.unpack('!Q', exact(8))[0]
    payload = exact(length)
    if flags & 15 == 2 and len(payload) > 188:
        binary = True
        break
assert binary
sock.close()
assert run('sh', '-c', 'PULSE_SERVER=unix:/run/user/1000/pulse/native pactl get-default-sink') == 'kasm_output'
print('PASS: native Kasm authenticated audio WebSocket delivers media from the PipeWire sink')

#!/usr/bin/env python3
"""Run inside a workspace as kasm-user. Plays a brief tone through browser audio.

Example: docker exec -i CONTAINER python - < tests/verify-audio.py
Uses the container's VNC_PW without printing it. Requires Python stdlib + ffmpeg.
"""
import array
import base64
import math
import os
import socket
import ssl
import struct
import subprocess
import time

os.environ["XDG_RUNTIME_DIR"] = f"/run/user/{os.getuid()}"
os.environ["PULSE_SERVER"] = f"unix:{os.environ['XDG_RUNTIME_DIR']}/pulse/native"
port = int(os.environ.get("AUDIO_PORT", "4901"))


def connect(auth=None):
    context = ssl._create_unverified_context()  # Local Kasm self-signed cert.
    sock = context.wrap_socket(socket.create_connection(("127.0.0.1", port), 5),
                               server_hostname="localhost")
    key = base64.b64encode(os.urandom(16)).decode()
    request = (f"GET / HTTP/1.1\r\nHost: localhost:{port}\r\n"
               "Upgrade: websocket\r\nConnection: Upgrade\r\n"
               f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n")
    if auth:
        request += f"Authorization: Basic {auth}\r\n"
    sock.sendall((request + "\r\n").encode())
    header = bytearray()
    while not header.endswith(b"\r\n\r\n"):
        byte = sock.recv(1)
        if not byte:
            raise RuntimeError("Audio relay closed during HTTP handshake")
        header.extend(byte)
        if len(header) > 16384:
            raise RuntimeError("Oversized HTTP handshake")
    return sock, bytes(header).split(b"\r\n", 1)[0]


def receive(sock, length):
    data = bytearray()
    while len(data) < length:
        chunk = sock.recv(length - len(data))
        if not chunk:
            raise RuntimeError("Audio websocket closed unexpectedly")
        data.extend(chunk)
    return bytes(data)


sink = subprocess.check_output(["pactl", "get-default-sink"], text=True).strip()
assert sink == "kasm_output", f"Unexpected default sink: {sink}"
sock, status = connect()
if b"101" in status:
    # Kasm's relay authenticates after upgrading, then closes unauthorized peers.
    assert receive(sock, 2) == b"\x88\x00", "Unauthenticated peer received audio"
else:
    assert b"401" in status, f"Unauthenticated audio was not rejected: {status!r}"
sock.close()
auth = base64.b64encode(f"kasm_user:{os.environ['VNC_PW']}".encode()).decode()
sock, status = connect(auth)
assert b"101" in status, f"Websocket upgrade failed: {status!r}"
tone = subprocess.Popen([
    "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-re",
    "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=3",
    "-af", "volume=0.2", "-f", "pulse", "default",
])
stream = bytearray()
try:
    deadline = time.monotonic() + 4
    while time.monotonic() < deadline:
        first, second = receive(sock, 2)
        opcode = first & 15
        length = second & 127
        if length == 126:
            length = struct.unpack("!H", receive(sock, 2))[0]
        elif length == 127:
            length = struct.unpack("!Q", receive(sock, 8))[0]
        assert not second & 128, "Server must not mask websocket frames"
        assert length < 1024 * 1024, "Oversized websocket frame"
        payload = receive(sock, length)
        if opcode in (0, 2):
            stream.extend(payload)
        elif opcode == 8:
            raise RuntimeError("Audio relay sent a close frame")
finally:
    sock.close()
    if tone.poll() is None:
        tone.terminate()
    tone.wait(timeout=5)

decoded = subprocess.run([
    "ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "mpegts", "-i", "pipe:0",
    "-f", "s16le", "-ac", "1", "-ar", "44100", "pipe:1",
], input=stream, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
samples = array.array("h", decoded.stdout)
assert len(samples) > 44100, "Less than one second of decoded audio"
rms = math.sqrt(sum(sample * sample for sample in samples) / len(samples))
assert rms > 100, f"Stream contains silence or insufficient signal: RMS={rms:.1f}"
print(f"PASS: Kasm output, unauthenticated rejection, authenticated WSS, "
      f"{len(stream)} MPEG-TS bytes, {len(samples)/44100:.2f}s decoded audio, "
      f"non-silent test tone (RMS={rms:.1f}).")

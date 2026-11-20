"""Use Kasm's per-session HTTP Basic credentials for pages and WebSockets."""
import base64
import binascii
import hmac
import os

from websockify.auth_plugins import AuthenticationError


class SessionAuth:
    def __init__(self, src=None):
        self.password = os.environ.get('VNC_PW', '')
        if not self.password:
            raise ValueError('VNC_PW is required for authenticated streaming')

    def authenticate(self, headers, target_host, target_port):
        try:
            scheme, encoded = headers.get('Authorization', '').split(' ', 1)
            if scheme.lower() != 'basic':
                raise ValueError('Not Basic authentication')
            credentials = base64.b64decode(encoded, validate=True)
            expected = ('kasm_user:' + self.password).encode()
            if hmac.compare_digest(credentials, expected):
                return
        except (ValueError, binascii.Error):
            pass
        raise AuthenticationError(response_code=401,
                                  response_headers={'WWW-Authenticate': 'Basic realm="Omarchy"'})

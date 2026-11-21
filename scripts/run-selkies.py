#!/opt/selkies/bin/python
"""Pinned Selkies server integration: Kasm-compatible routes and F18 mapping."""
from importlib.metadata import version
import os

assert version('selkies') == '2.2.1'
from selkies.input_handler import WebRTCInput
from selkies.websockets_mode import DataStreamingServer, SelkiesStreamingApp
import selkies.stream_server as stream_server

dispatch = WebRTCInput._dispatch_message


async def kasm_dispatch(self, message, display_id='primary', conn_id=None):
    fields = message.split(',')
    if fields[0] in ('kd', 'ku', 'kh'):
        fields[1:] = ['65515' if value == '65487' else value for value in fields[1:]]
        message = ','.join(fields)
    return await dispatch(self, message, display_id, conn_id)


WebRTCInput._dispatch_message = kasm_dispatch

# Preserve native authentication/origin checks on Kasm-compatible aliases.
stream_server.WEBSOCKET_ROUTES = (*stream_server.WEBSOCKET_ROUTES, '/websockify')
register_routes = DataStreamingServer.register_routes


def kasm_register_routes(self, api_prefix, router):
    register_routes(self, api_prefix, router)
    router.add_get(f'{api_prefix}/websockify{{slash:/?}}', self.data_ws_handler)
    router.add_get(f'{api_prefix}/selkies-status.json', self.supervisor.handle_status)
    router.add_get(f'{api_prefix}/selkies-health.json', self.supervisor.handle_health)


DataStreamingServer.register_routes = kasm_register_routes

if os.environ.get('AQ_HEADLESS_VIRTUAL_CURSOR') == '1':
    from headless_cursor import install_cursor_bridge
    install_cursor_bridge(DataStreamingServer, SelkiesStreamingApp)

from selkies.__main__ import main

main()

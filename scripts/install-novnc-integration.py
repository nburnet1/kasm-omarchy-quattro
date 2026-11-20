#!/usr/bin/env python3
"""Install the adapter before the pinned upstream client's UI starts."""
from pathlib import Path

page = Path('/opt/noVNC/vnc.html')
source = page.read_text()
anchor = '        import UI from "./app/ui.js";'
assert source.count(anchor) == 1, 'Unexpected noVNC entrypoint; review the adapter'
page.write_text(source.replace(anchor, anchor + '\n'
    '        import { installKasmIntegration } from "./app/novnc-kasm.js";\n'
    '        installKasmIntegration(UI);'))

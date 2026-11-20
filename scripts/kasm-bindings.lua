-- Extra shortcuts for browser sessions where the host owns Super/Command.
-- Keep Omarchy's existing bindings, including Super+Space.
o.rebind("CTRL + SHIFT + RETURN", "Terminal (Kasm)", o.launch_terminal())
o.rebind("CTRL + SHIFT + SPACE", "Omarchy menu (Kasm)", { panel = "omarchy.menu" })

-- Super-free aliases for the core desktop controls. On macOS, Alt is Option.
o.rebind("CTRL + ALT + E", "Default editor (Kasm)", "omarchy-launch-editor")
o.rebind("CTRL + ALT + Q", "Close window (Kasm)", hl.dsp.window.close())
o.rebind("CTRL + ALT + F", "Fullscreen (Kasm)", hl.dsp.window.fullscreen({ mode = "fullscreen" }))
o.rebind("CTRL + ALT + T", "Toggle floating (Kasm)", hl.dsp.window.float({ action = "toggle" }))
for _, direction in ipairs({{"LEFT", "l"}, {"RIGHT", "r"}, {"UP", "u"}, {"DOWN", "d"}}) do
  o.rebind("CTRL + ALT + " .. direction[1], "Focus window (Kasm)", hl.dsp.focus({ direction = direction[2] }))
end
for workspace = 1, 10 do
  local key = "code:" .. tostring(workspace + 9)
  o.rebind("CTRL + ALT + " .. key, "Workspace " .. workspace .. " (Kasm)", o.workspaces.focus(workspace))
  o.rebind("CTRL + ALT + SHIFT + " .. key, "Move to workspace " .. workspace .. " (Kasm)", o.workspaces.move_window(workspace))
end
o.rebind("CTRL + ALT + mouse:272", "Move window (Kasm)", hl.dsp.window.drag(), { mouse = true })
o.rebind("CTRL + ALT + mouse:273", "Resize window (Kasm)", hl.dsp.window.resize(), { mouse = true })

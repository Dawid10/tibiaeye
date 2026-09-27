"""
Global hotkeys: fire even when Tibia (not the GUI) is focused.

macOS requires the terminal/IDE running the bot to be allowed under
System Settings -> Privacy & Security -> Input Monitoring.
"""
from pynput import keyboard


def start_global_hotkeys(root, callbacks):
    """callbacks: {key_char: fn}. Each fn runs on the Tk main thread."""
    def on_press(key):
        callback = callbacks.get(getattr(key, 'char', None))
        if callback:
            root.after(0, callback)

    listener = keyboard.Listener(on_press=on_press)
    listener.daemon = True
    listener.start()
    return listener

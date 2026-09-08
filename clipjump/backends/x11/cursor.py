from Xlib import display

_display = None


def cursor_pos():
    global _display
    if _display is None:
        _display = display.Display()
    pointer = _display.screen().root.query_pointer()
    return pointer.root_x, pointer.root_y

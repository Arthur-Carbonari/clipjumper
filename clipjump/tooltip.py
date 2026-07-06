import queue
import threading
import tkinter as tk

from Xlib import display as xdisplay

MAX_PREVIEW_CHARS = 300


def _preview(text):
    text = text.replace("\r\n", "\n")
    if len(text) > MAX_PREVIEW_CHARS:
        text = text[:MAX_PREVIEW_CHARS] + "…"
    return text


class Tooltip:
    """Borderless always-on-top window near the cursor.

    show()/hide()/quit() are thread-safe (backed by a queue) and may be
    called from any thread. run() itself must be called on the process's
    real main thread and blocks forever (it owns the Tk mainloop) -- Tcl's
    signal/async-handler integration is only safe when Tk is created and
    torn down on the same thread that will eventually finalize the
    interpreter, which for CPython is the main thread. start() (spawning
    run() on a background thread) is fine for quick throwaway scripts that
    never call quit(), but will hit a Tcl_AsyncDelete abort on teardown --
    it exists only for the __main__ test below.
    """

    def __init__(self):
        self._queue = queue.Queue()
        self._ready = threading.Event()
        self._thread = None
        self._x_display = xdisplay.Display()

    def start(self):
        self._thread = threading.Thread(target=self.run, daemon=True)
        self._thread.start()
        self._ready.wait()

    def show(self, text, index, total, status=None):
        self._queue.put(("show", text, index, total, status))

    def hide(self):
        self._queue.put(("hide",))

    def quit(self):
        self._queue.put(("quit",))

    def _cursor_pos(self):
        pointer = self._x_display.screen().root.query_pointer()
        return pointer.root_x, pointer.root_y

    def run(self):
        root = tk.Tk()
        root.withdraw()
        root.overrideredirect(True)
        root.attributes("-topmost", True)

        label = tk.Label(
            root,
            text="",
            justify="left",
            anchor="w",
            bg="#1e1e1e",
            fg="#e0e0e0",
            font=("monospace", 10),
            padx=8,
            pady=6,
            wraplength=420,
        )
        label.pack()

        counter = tk.Label(
            root,
            text="",
            justify="left",
            anchor="w",
            bg="#1e1e1e",
            fg="#888888",
            font=("monospace", 8),
            padx=8,
        )
        counter.pack(anchor="w")

        status_label = tk.Label(
            root,
            text="",
            justify="left",
            anchor="w",
            bg="#1e1e1e",
            fg="#e0a030",
            font=("monospace", 8, "bold"),
            padx=8,
        )
        status_label.pack(anchor="w")

        self._ready.set()

        def poll():
            try:
                while True:
                    msg = self._queue.get_nowait()
                    if msg[0] == "show":
                        _, text, index, total, status = msg
                        label.config(text=_preview(text))
                        counter.config(text=f"clip {index + 1} / {total}")
                        if status:
                            status_label.config(text=status)
                            status_label.pack(anchor="w")
                        else:
                            status_label.pack_forget()
                        x, y = self._cursor_pos()
                        root.deiconify()
                        root.geometry(f"+{x + 16}+{y + 16}")
                        root.lift()
                        root.update_idletasks()
                        root.update()
                    elif msg[0] == "hide":
                        root.withdraw()
                    elif msg[0] == "quit":
                        root.destroy()
                        return
            except queue.Empty:
                pass
            root.after(20, poll)

        root.after(20, poll)
        root.mainloop()


if __name__ == "__main__":
    import time

    tt = Tooltip()
    tt.start()
    samples = ["first clip content here", "second clip\nwith a newline", "third clip " * 20]
    for i, s in enumerate(samples):
        tt.show(s, i, len(samples))
        time.sleep(1.5)
    tt.hide()
    time.sleep(1)
    tt.quit()
    tt._thread.join(timeout=2)
    print("tooltip test done")

"""
Single entry point for the packaged app (PyInstaller targets this file).

Boots the Flask server on a free port in a background thread, then opens the UI:
  - if pywebview is available → a native desktop window
  - otherwise → the user's default web browser

Designed so a double-clicked .exe "just works": no console interaction, picks an
open port, and fails with a visible message rather than silently.
"""
import os
import sys
import socket
import threading
import time
import webbrowser


def _resource_base() -> str:
    """Directory to import the app from — handles the PyInstaller one-file bundle,
    where modules are unpacked to sys._MEIPASS at runtime."""
    return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))


# Make both the gui/ dir and the repo root importable (frozen and source modes).
_BASE = _resource_base()
sys.path.insert(0, _BASE)
sys.path.insert(0, os.path.dirname(_BASE))

import app as flask_module  # noqa: E402


def find_free_port(start=5000):
    for p in (start, 5001, 5050, 8000, 8080, 8765, 8910):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", p))
                return p
            except OSError:
                continue
    return start


def start_flask(port):
    import logging
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    flask_module.app.run(host="127.0.0.1", port=port, debug=False,
                         use_reloader=False, threaded=True)


def wait_for_server(port, timeout=12.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.1)
    return False


def main():
    port = find_free_port()
    threading.Thread(target=start_flask, args=(port,), daemon=True).start()
    url = f"http://127.0.0.1:{port}"
    if not wait_for_server(port):
        sys.stderr.write(f"Lead Engine failed to start on {url}\n")
        try:
            input("Press Enter to close…")
        except Exception:
            pass
        return

    # Prefer a native window; fall back to the default browser.
    try:
        import webview
        webview.create_window("Lead Engine", url, width=1180, height=900,
                              min_size=(860, 640), resizable=True)
        webview.start()
    except Exception:
        webbrowser.open(url)
        print(f"Lead Engine is running at {url}\nClose this window to quit.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()

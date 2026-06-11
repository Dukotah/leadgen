"""
Native-window launcher for the Lead Engine GUI (pywebview wrapping the Flask app).

Run:  python gui/desktop_app.py
Falls back to a clear message if pywebview/native rendering isn't available;
in that case just run `python gui/app.py` and open the printed URL in a browser.
"""
import socket
import threading
import time

import app as flask_module


def find_free_port(start=5000):
    for p in (start, 5001, 5050, 8000, 8080, 8765):
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


def wait_for_server(port, timeout=8.0):
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
    if not wait_for_server(port):
        print(f"Server did not start on port {port}.")
        return
    try:
        import webview
    except ImportError:
        print(f"pywebview not installed — open http://127.0.0.1:{port} in your browser,"
              f"\nor: pip install pywebview")
        # keep the Flask thread alive so the browser URL works
        while True:
            time.sleep(1)
    webview.create_window("Lead Engine", f"http://127.0.0.1:{port}",
                          width=1140, height=860, min_size=(840, 620), resizable=True)
    webview.start()


if __name__ == "__main__":
    main()

"""Desktop app entry point: run the local server + open a native window.

    python -m poker_engine.desktop.app

Starts the FastAPI server (see ``server.py``) on a background thread and
opens it in a native OS web view via ``pywebview`` (WebView2 on Windows,
WKWebView on macOS) -- a companion window next to the poker client, not an
overlay on top of it (see architecture notes on why).
"""

from __future__ import annotations

import threading

import uvicorn

from .server import create_app

HOST = "127.0.0.1"
PORT = 8765
WINDOW_WIDTH = 400
WINDOW_HEIGHT = 520


def _run_server() -> None:
    uvicorn.run(create_app(), host=HOST, port=PORT, log_level="warning")


def main() -> None:
    import webview

    server_thread = threading.Thread(target=_run_server, daemon=True)
    server_thread.start()

    webview.create_window(
        "PokerSense",
        url=f"http://{HOST}:{PORT}/",
        width=WINDOW_WIDTH,
        height=WINDOW_HEIGHT,
        resizable=True,
        on_top=False,
    )
    webview.start()


if __name__ == "__main__":
    main()

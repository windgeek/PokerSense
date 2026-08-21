"""Desktop app entry point: run the local server + open a native window.

    python -m poker_engine.desktop.app

Starts the FastAPI server (see ``server.py``) on a background thread and
opens it in a native OS web view via ``pywebview`` (WebView2 on Windows,
WKWebView on macOS) -- a companion window next to the poker client, not an
overlay on top of it (see architecture notes on why).
"""

from __future__ import annotations

import argparse
import sys
import threading
import time

import uvicorn

from .live import DEFAULT_WINDOW_TITLE, live_analysis_stream
from .server import create_app

HOST = "127.0.0.1"
PORT = 8765
WINDOW_WIDTH = 400
WINDOW_HEIGHT = 520
SERVER_STARTUP_TIMEOUT_SECONDS = 10.0


def _request_capture_permission_if_needed() -> None:
    """Ask at app launch, on macOS' main thread, before capture begins."""
    if sys.platform != "darwin":
        return
    from poker_engine.perceptual.capture.quartz_backend import (
        request_screen_capture_permission,
    )

    request_screen_capture_permission()


def _create_server(
    window_title: str, window_index: int | None
) -> uvicorn.Server:
    def stream():
        return live_analysis_stream(window_title, window_index)

    config = uvicorn.Config(
        create_app(stream), host=HOST, port=PORT, log_level="warning"
    )
    return uvicorn.Server(config)


def _wait_for_server(
    server: uvicorn.Server,
    server_thread: threading.Thread,
    timeout_seconds: float = SERVER_STARTUP_TIMEOUT_SECONDS,
) -> None:
    """Wait until uvicorn is listening before navigating the native webview."""
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if server.started:
            return
        if not server_thread.is_alive():
            raise RuntimeError("PokerSense local server stopped during startup")
        time.sleep(0.02)
    raise RuntimeError("PokerSense local server did not start within 10 seconds")


def main(
    window_title: str = DEFAULT_WINDOW_TITLE, window_index: int | None = None
) -> None:
    import webview

    _request_capture_permission_if_needed()
    server = _create_server(window_title, window_index)
    server_thread = threading.Thread(
        target=server.run, daemon=True
    )
    server_thread.start()
    _wait_for_server(server, server_thread)

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
    parser = argparse.ArgumentParser(description="Open the PokerSense companion app")
    parser.add_argument(
        "--window-index",
        type=int,
        help="visible same-title window index from tools/list_windows.py",
    )
    parser.add_argument("--window-title", default=DEFAULT_WINDOW_TITLE)
    args = parser.parse_args()
    main(window_title=args.window_title, window_index=args.window_index)

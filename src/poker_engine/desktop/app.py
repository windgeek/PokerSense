"""Desktop app entry point: run the local server + open a native window.

    python -m poker_engine.desktop.app

Starts the FastAPI server (see ``server.py``) on a background thread and
opens it in a native OS web view via ``pywebview`` (WebView2 on Windows,
WKWebView on macOS) -- a companion window next to the poker client, not an
overlay on top of it (see architecture notes on why).
"""

from __future__ import annotations

import argparse
import threading

import uvicorn

from .live import DEFAULT_WINDOW_TITLE, live_analysis_stream
from .server import create_app

HOST = "127.0.0.1"
PORT = 8765
WINDOW_WIDTH = 400
WINDOW_HEIGHT = 520


def _run_server(window_title: str, window_index: int | None) -> None:
    def stream():
        return live_analysis_stream(window_title, window_index)

    uvicorn.run(create_app(stream), host=HOST, port=PORT, log_level="warning")


def main(
    window_title: str = DEFAULT_WINDOW_TITLE, window_index: int | None = None
) -> None:
    import webview

    server_thread = threading.Thread(
        target=_run_server, args=(window_title, window_index), daemon=True
    )
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
    parser = argparse.ArgumentParser(description="Open the PokerSense companion app")
    parser.add_argument(
        "--window-index",
        type=int,
        help="visible same-title window index from tools/list_windows.py",
    )
    parser.add_argument("--window-title", default=DEFAULT_WINDOW_TITLE)
    args = parser.parse_args()
    main(window_title=args.window_title, window_index=args.window_index)

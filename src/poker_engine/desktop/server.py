"""Local FastAPI server: serves the UI and streams live analysis over WebSocket.

Runs entirely on localhost — a companion process for the desktop shell, not
a network service. ``/ws`` streams :class:`RealtimeAnalysis` produced from a
real capture of the poker window (see ``live.py``).

A capture problem (window not open, screen-recording permission not granted,
window resized past the layout's tolerance) is a normal condition, not a
crash: it is sent to the UI as a ``{"error": ...}`` frame so the user is told
what to fix, and the stream keeps retrying.
"""

from __future__ import annotations

import asyncio
import argparse
import sys
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Callable

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response

from poker_engine.realtime.analysis import RealtimeAnalysis

from .live import DEFAULT_WINDOW_TITLE, LiveCaptureError, live_analysis_stream
from .serialize import analysis_to_dict
from .settings import load_settings, save_language


def _resolve_ui_dir() -> Path:
    """Find ``ui/`` in a dev checkout or inside a PyInstaller bundle.

    PyInstaller extracts bundled data files under ``sys._MEIPASS`` at
    runtime (a temp dir, not the source tree) -- see ``pyinstaller.spec``'s
    ``datas`` entry, which bundles ``ui/`` as ``ui/`` relative to that root.
    """
    frozen_base = getattr(sys, "_MEIPASS", None)
    if frozen_base is not None:
        return Path(frozen_base) / "ui"
    return Path(__file__).resolve().parents[3] / "ui"


_UI_DIR = _resolve_ui_dir()

AnalysisStreamFactory = Callable[[], AsyncIterator[RealtimeAnalysis]]


class _SettingsPayload(BaseModel):
    language: str


class _NoCacheStaticFiles(StaticFiles):
    """Serve the UI without caching.

    The UI ships inside the app bundle, so a cached copy has no upside: it
    is never fetched over a network, and a stale one means an updated build
    silently keeps rendering the previous version's interface.
    """

    def file_response(self, *args, **kwargs) -> Response:
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-store, must-revalidate"
        return response


# How long to wait before re-attempting capture after a recoverable failure.
_RETRY_SECONDS = 3.0


def _default_stream() -> AsyncIterator[RealtimeAnalysis]:
    return live_analysis_stream(DEFAULT_WINDOW_TITLE)


def create_app(stream_factory: AnalysisStreamFactory = _default_stream) -> FastAPI:
    app = FastAPI()

    @app.get("/settings")
    def get_settings() -> dict[str, str]:
        return load_settings()

    @app.put("/settings")
    def put_settings(payload: _SettingsPayload) -> dict[str, str]:
        try:
            return save_language(payload.language)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.websocket("/ws")
    async def ws_endpoint(websocket: WebSocket) -> None:
        await websocket.accept()
        try:
            while True:
                try:
                    async for analysis in stream_factory():
                        await websocket.send_json(analysis_to_dict(analysis))
                except LiveCaptureError as exc:
                    await websocket.send_json({"error": str(exc)})
                    await asyncio.sleep(_RETRY_SECONDS)
        except WebSocketDisconnect:
            pass

    if _UI_DIR.is_dir():
        app.mount(
            "/",
            _NoCacheStaticFiles(directory=str(_UI_DIR), html=True),
            name="ui",
        )

    return app


def run(
    host: str = "127.0.0.1",
    port: int = 8765,
    window_title: str = DEFAULT_WINDOW_TITLE,
    window_index: int | None = None,
) -> None:
    def stream() -> AsyncIterator[RealtimeAnalysis]:
        return live_analysis_stream(window_title, window_index)

    import uvicorn

    uvicorn.run(create_app(stream), host=host, port=port, log_level="warning")


__all__ = ["create_app", "run"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the PokerSense local server")
    parser.add_argument("--window-title", default=DEFAULT_WINDOW_TITLE)
    parser.add_argument(
        "--window-index",
        type=int,
        help="visible same-title window index from tools/list_windows.py",
    )
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    run(port=args.port, window_title=args.window_title, window_index=args.window_index)

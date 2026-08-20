"""Local FastAPI server: serves the UI and streams analysis over WebSocket.

Runs entirely on localhost -- this is a companion process for the desktop
shell, not a network service. The ``/ws`` endpoint currently streams the
scripted demo sequence (see ``demo.py``); swapping in a real, calibrated
``RealtimePipeline`` later only means passing a different
``AsyncIterator[RealtimeAnalysis]`` into :func:`create_app` -- the wire
contract (``serialize.analysis_to_dict``) and the frontend do not change.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from typing import Callable

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

from poker_engine.realtime.analysis import RealtimeAnalysis

from .demo import demo_analysis_stream
from .serialize import analysis_to_dict

# ui/ lives at the repo root, not inside the installed package -- fine for
# running from a checkout; a packaged (PyInstaller) build must bundle it as
# a data directory and adjust this path. See project roadmap Phase 3.
_UI_DIR = Path(__file__).resolve().parents[3] / "ui"

AnalysisStreamFactory = Callable[[], AsyncIterator[RealtimeAnalysis]]


def create_app(stream_factory: AnalysisStreamFactory = demo_analysis_stream) -> FastAPI:
    app = FastAPI()

    @app.websocket("/ws")
    async def ws_endpoint(websocket: WebSocket) -> None:
        await websocket.accept()
        try:
            async for analysis in stream_factory():
                await websocket.send_json(analysis_to_dict(analysis))
        except WebSocketDisconnect:
            pass

    if _UI_DIR.is_dir():
        app.mount("/", StaticFiles(directory=str(_UI_DIR), html=True), name="ui")

    return app


def run(host: str = "127.0.0.1", port: int = 8765) -> None:
    import uvicorn

    uvicorn.run(create_app(), host=host, port=port, log_level="warning")


__all__ = ["create_app", "run"]


if __name__ == "__main__":
    run()

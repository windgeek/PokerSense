"""FrameSource abstraction for the realtime pipeline.

The realtime layer consumes a *stream* of frames without knowing where they
come from. Two implementations:
  - :class:`SyntheticFrameSource` — replays a pre-built sequence of frames
    (tests / CI / benchmark). Deterministic.
  - :class:`MSSFrameSource` — wraps the existing MSS capture backend for real
    screen capture. Present only as an interface stub; the realtime pipeline
    does NOT enable it by default (auto-capturing real platforms is out of
    scope).

Only the frame *lifecycle* is owned here: the frame's pixel data remains the
immutable ``Frame`` from the capture layer.
"""

from __future__ import annotations

from typing import Protocol

from poker_engine.perceptual.capture.base import Frame


class FrameSource(Protocol):
    """An ordered, pull-based source of frames."""

    def next_frame(self) -> Frame | None:
        """Return the next frame, or None when the stream is exhausted."""
        ...


class SyntheticFrameSource:
    """Replay a fixed sequence of frames (deterministic, test-friendly)."""

    def __init__(self, frames: tuple[Frame, ...]) -> None:
        if not isinstance(frames, tuple):
            raise TypeError("frames must be a tuple of Frame")
        for f in frames:
            if not isinstance(f, Frame):
                raise TypeError("each frame must be a Frame")
        self._frames = frames
        self._idx = 0

    def next_frame(self) -> Frame | None:
        if self._idx >= len(self._frames):
            return None
        frame = self._frames[self._idx]
        self._idx += 1
        return frame


class MSSFrameSource:
    """Real-screen frame source (interface stub; NOT enabled by default).

    Auto-capturing real poker platforms (GGPoker/WePoker/...) is out of scope
    and must not be wired into the pipeline. This stub exists only so the
    realtime layer exposes a uniform FrameSource shape for a future, explicitly
    approved capture source.
    """

    def __init__(self) -> None:
        raise NotImplementedError(
            "MSSFrameSource is a stub; real screen capture is out of scope"
        )


__all__ = ["FrameSource", "SyntheticFrameSource", "MSSFrameSource"]

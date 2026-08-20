"""Tests for Frame immutability (bytes-backed) and FakeBackend."""

from __future__ import annotations

import sys
from datetime import datetime, timezone

import numpy as np
import pytest

from poker_engine.perceptual import (
    CaptureError,
    CaptureTarget,
    FakeBackend,
    Frame,
    WindowRect,
)

UTC = timezone.utc


def _mk(image):
    return Frame(
        frame_seq=0,
        timestamp=datetime(2026, 8, 19, 1, 0, tzinfo=UTC),
        window_id="t",
        window_rect=WindowRect(left=0, top=0, width=4, height=3),
        image=image,
        width=4,
        height=3,
    )


def test_mutating_source_does_not_affect_frame():
    source = np.zeros((3, 4, 3), dtype=np.uint8)
    frame = _mk(source)
    source[:] = 255  # mutate the caller-owned ndarray
    assert frame.image[0, 0, 0] == 0
    assert frame.image.max() == 0


def test_frame_image_write_fails():
    source = np.zeros((3, 4, 3), dtype=np.uint8)
    frame = _mk(source)
    with pytest.raises(ValueError):
        frame.image[0, 0, 0] = 123
    with pytest.raises(ValueError):
        frame.image[...] = 123


def test_frame_image_cannot_regain_writability():
    source = np.zeros((3, 4, 3), dtype=np.uint8)
    frame = _mk(source)
    # bytes-backed read-only view: setflags(write=True) must also fail.
    with pytest.raises(ValueError):
        frame.image.setflags(write=True)


def test_frame_naive_timestamp_rejected():
    with pytest.raises(TypeError):
        Frame(
            frame_seq=0,
            timestamp=datetime(2026, 8, 19, 1, 0),  # naive
            window_id="t",
            window_rect=WindowRect(0, 0, 4, 3),
            image=np.zeros((3, 4, 3), dtype=np.uint8),
            width=4,
            height=3,
        )


def test_frame_negative_frame_seq_rejected():
    with pytest.raises(ValueError):
        Frame(
            frame_seq=-1,
            timestamp=datetime(2026, 8, 19, 1, 0, tzinfo=UTC),
            window_id="t",
            window_rect=WindowRect(0, 0, 4, 3),
            image=np.zeros((3, 4, 3), dtype=np.uint8),
            width=4,
            height=3,
        )


def test_frame_bool_frame_seq_rejected():
    with pytest.raises(TypeError):
        Frame(
            frame_seq=True,
            timestamp=datetime(2026, 8, 19, 1, 0, tzinfo=UTC),
            window_id="t",
            window_rect=WindowRect(0, 0, 4, 3),
            image=np.zeros((3, 4, 3), dtype=np.uint8),
            width=4,
            height=3,
        )


def test_fake_backend_monotonic_seq():
    be = FakeBackend(window_id="fake")
    target = CaptureTarget(window_id="fake")
    f1 = be.capture(target)
    f2 = be.capture(target)
    assert f1.frame_seq == 0
    assert f2.frame_seq == 1


def test_fake_backend_uses_custom_image():
    img = np.full((10, 10, 3), 7, dtype=np.uint8)
    be = FakeBackend(image=img)
    f = be.capture(CaptureTarget(window_id="x"))
    assert f.image.shape == (10, 10, 3)
    assert f.image[0, 0, 0] == 7


def test_capture_target_window_id_nonempty():
    with pytest.raises(ValueError):
        CaptureTarget(window_id="")
    with pytest.raises(ValueError):
        CaptureTarget(window_id="   ")


# --- DPI awareness fail-fast contract (mocked) ---

def test_mss_backend_fails_fast_when_dpi_none(monkeypatch):
    import poker_engine.perceptual.capture.mss_backend as mb

    monkeypatch.setattr(mb, "_try_set_dpi_awareness", lambda: "none")
    monkeypatch.setattr(mb, "_HAS_WIN32", True)
    monkeypatch.setattr(mb, "mss", object)  # non-None sentinel

    with pytest.raises(RuntimeError):
        mb.MssBackend()


class _FakeUser32Ctypes:
    """A ctypes-like object whose SetProcessDpiAwarenessContext is patchable
    as a standalone function (so ``fn.argtypes = ...`` works)."""

    def __init__(self):
        self.SetProcessDpiAwarenessContext = None
        self.GetThreadDpiAwarenessContext = None
        self.GetAwarenessFromDpiAwarenessContext = None


def _setup_dpi_mocks(monkeypatch, mb, access_denied, is_per_monitor):
    import ctypes

    monkeypatch.setattr(mb, "_HAS_WIN32", True)

    def fake_set_ctx(ctx):
        if access_denied:
            ctypes.set_last_error(5)
        else:
            ctypes.set_last_error(0)
        return False  # FALSE -> error path

    fake = _FakeUser32Ctypes()
    fake.SetProcessDpiAwarenessContext = fake_set_ctx
    monkeypatch.setattr(mb, "_user32", fake)
    monkeypatch.setattr(
        mb, "_is_current_context_per_monitor", lambda: is_per_monitor
    )

    # Patch shcore WinDLL to a sentinel whose SetProcessDpiAwareness returns
    # a non-S_OK HRESULT so legacy path does NOT rescue us.
    class _FakeShcore:
        def SetProcessDpiAwareness(self, *a):
            return 0x80004005  # E_FAIL -> neither S_OK nor E_ACCESSDENIED

    monkeypatch.setattr(mb.ctypes, "WinDLL", lambda *a, **k: _FakeShcore())


@pytest.mark.skipif(
    sys.platform != "win32",
    reason="patches ctypes.WinDLL, which only exists on Windows",
)
def test_dpi_access_denied_with_per_monitor_accepted(monkeypatch):
    import poker_engine.perceptual.capture.mss_backend as mb

    _setup_dpi_mocks(monkeypatch, mb, access_denied=True, is_per_monitor=True)
    assert mb._try_set_dpi_awareness() == "already_set_per_monitor"


@pytest.mark.skipif(
    sys.platform != "win32",
    reason="patches ctypes.WinDLL, which only exists on Windows",
)
def test_dpi_access_denied_with_system_aware_rejected(monkeypatch):
    import poker_engine.perceptual.capture.mss_backend as mb

    _setup_dpi_mocks(monkeypatch, mb, access_denied=True, is_per_monitor=False)
    assert mb._try_set_dpi_awareness() == "none"


def test_dpi_access_denied_then_backend_runtime_error(monkeypatch):
    import poker_engine.perceptual.capture.mss_backend as mb

    monkeypatch.setattr(mb, "_HAS_WIN32", True)
    monkeypatch.setattr(mb, "mss", object)
    # SYSTEM_AWARE -> not safe, so try_set returns "none" -> backend must fail.
    monkeypatch.setattr(mb, "_try_set_dpi_awareness", lambda: "none")
    with pytest.raises(RuntimeError):
        mb.MssBackend()


# --- IsIconic -> CaptureError (mocked) ---

def test_minimized_window_raises_capture_error(monkeypatch):
    import poker_engine.perceptual.capture.mss_backend as mb

    class _FakeUser32Min:
        def IsWindow(self, hwnd):
            return True

        def IsWindowVisible(self, hwnd):
            return True

        def IsIconic(self, hwnd):
            return True  # minimized

    monkeypatch.setattr(mb, "_find_hwnd_matches", lambda title: [123])
    monkeypatch.setattr(mb, "_user32", _FakeUser32Min())
    be = object.__new__(mb.MssBackend)  # bypass __init__ (no real mss/DPI)
    with pytest.raises(CaptureError):
        be._resolve_window_rect("some-title")


def test_fake_backend_derives_dims_from_image():
    img = np.full((10, 10, 3), 7, dtype=np.uint8)
    be = FakeBackend(image=img)
    f = be.capture(CaptureTarget(window_id="x"))
    assert f.width == 10
    assert f.height == 10


def test_frame_dimension_mismatch_fails():
    img = np.zeros((10, 10, 3), dtype=np.uint8)
    with pytest.raises(ValueError):
        Frame(
            frame_seq=0,
            timestamp=datetime(2026, 8, 19, 1, 0, tzinfo=UTC),
            window_id="t",
            window_rect=WindowRect(0, 0, 99, 10),  # width mismatch
            image=img,
            width=99,
            height=10,
        )


# --- package import tests (blocker 2) ---

def test_import_perceptual_package():
    import poker_engine.perceptual as p

    assert hasattr(p, "Frame")
    assert hasattr(p, "TableMap")


def test_import_capture_subpackage():
    import poker_engine.perceptual.capture as c

    assert hasattr(c, "Frame")
    assert hasattr(c, "FakeBackend")
    assert hasattr(c, "MssBackend")


def test_import_vision_subpackage():
    import poker_engine.perceptual.vision as v

    assert hasattr(v, "TableMap")
    assert hasattr(v, "ROIKind")
    assert hasattr(v, "extract_all")

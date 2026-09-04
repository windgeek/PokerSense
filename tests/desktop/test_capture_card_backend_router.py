"""Tests for live.py capture-backend routing (ADB vs capture-card).

These test only the *selection* logic — which backend class gets instantiated
for a given ``source``. They monkeypatch the backend constructors to avoid any
real ADB device / UVC capture card, and assert that an unknown source fails
closed.
"""

from __future__ import annotations

import pytest

from poker_engine.desktop import live


def _defuse_adb_backend(monkeypatch, captured):
    """Stub AdbBackend so construction needs no ADB binary."""
    import poker_engine.perceptual.capture.adb_backend as mod

    def fake_init(self):
        captured["adb"] = True

    monkeypatch.setattr(mod, "AdbBackend", type("FakeAdb", (), {"__init__": fake_init}))


def _defuse_capture_card(monkeypatch, captured):
    """Stub CaptureCardBackend so construction needs no UVC device."""
    import poker_engine.perceptual.capture.capture_card_backend as mod

    def fake_init(self, **kwargs):
        captured["card"] = kwargs

    monkeypatch.setattr(
        mod, "CaptureCardBackend", type("FakeCard", (), {"__init__": fake_init})
    )


def test_unknown_source_fails_closed():
    with pytest.raises(live.LiveCaptureError, match="unknown capture source"):
        live.build_capture_backend("bogus")


def test_adb_soure_returns_adb_backend(monkeypatch):
    captured = {}
    _defuse_adb_backend(monkeypatch, captured)
    backend = live.build_capture_backend("adb")
    assert captured["adb"] is True
    assert backend is not None


def test_capture_card_source_passes_options_through(monkeypatch):
    captured = {}
    _defuse_capture_card(monkeypatch, captured)
    backend = live.build_capture_backend(
        "capture-card",
        device_index=3,
        api="MSMF",
        normalization="norm-config",
    )
    assert captured["card"]["device_index"] == 3
    assert captured["card"]["api"] == "MSMF"
    assert captured["card"]["normalization"] == "norm-config"
    assert backend is not None


def test_normalization_ignored_for_adb(monkeypatch):
    # The ADB path ignores the normalization kwarg entirely.
    captured = {}
    _defuse_adb_backend(monkeypatch, captured)
    backend = live.build_capture_backend("adb", normalization="should-be-ignored")
    assert captured["adb"] is True
    assert backend is not None


def test_capture_card_pipeline_selects_independent_profile(monkeypatch):
    selected = {}

    def reject_uncalibrated(platform, layout):
        selected["profile"] = (platform, layout)
        raise live.LiveCaptureError("uncalibrated")

    monkeypatch.setattr(live, "load_calibration", reject_uncalibrated)

    with pytest.raises(live.LiveCaptureError, match="uncalibrated"):
        live.build_pipeline(source="capture-card", normalization="measured")

    assert selected["profile"] == (
        live.CAPTURE_CARD_PLATFORM,
        live.CAPTURE_CARD_LAYOUT,
    )


def test_capture_card_pipeline_rejects_foreign_profile():
    with pytest.raises(live.LiveCaptureError, match="independent"):
        live.build_pipeline(
            source="capture-card",
            platform="wepoker",
            layout="some-h5-layout",
        )


def test_capture_card_pipeline_requires_measured_normalization():
    with pytest.raises(live.LiveCaptureError, match="NormalizationConfig"):
        live.build_pipeline(source="capture-card")


def test_adb_pipeline_rejects_capture_card_profile():
    with pytest.raises(live.LiveCaptureError, match="ADB source"):
        live.build_pipeline(
            source="adb",
            platform=live.CAPTURE_CARD_PLATFORM,
            layout=live.CAPTURE_CARD_LAYOUT,
        )


def test_explicitly_uncalibrated_profile_fails_closed(tmp_path, monkeypatch):
    platform = "test_uncalibrated"
    layout = "test_layout"
    platform_dir = tmp_path / "configs" / "platform"
    vision_dir = tmp_path / "configs" / "vision" / platform
    platform_dir.mkdir(parents=True)
    vision_dir.mkdir(parents=True)
    source_map = (
        live._REPO_ROOT / "configs" / "platform"
        / f"{live.CAPTURE_CARD_PLATFORM}__{live.CAPTURE_CARD_LAYOUT}.json"
    )
    platform_map = source_map.read_text(encoding="utf-8")
    platform_map = platform_map.replace(live.CAPTURE_CARD_PLATFORM, platform)
    platform_map = platform_map.replace(live.CAPTURE_CARD_LAYOUT, layout)
    (platform_dir / f"{platform}__{layout}.json").write_text(
        platform_map,
        encoding="utf-8",
    )
    (vision_dir / "calibration.json").write_text(
        '{"status":"uncalibrated"}',
        encoding="utf-8",
    )
    monkeypatch.setattr(live, "_REPO_ROOT", tmp_path)

    with pytest.raises(live.LiveCaptureError, match="explicitly uncalibrated"):
        live.load_calibration(platform, layout)


def test_capture_card_profile_rejects_invalid_fused_model(monkeypatch):
    def reject_model(*args, **kwargs):
        raise ValueError("bad model")

    monkeypatch.setattr(live, "load_card_heads", reject_model)
    with pytest.raises(live.LiveCaptureError, match="integrity validation"):
        live.load_calibration(
            live.CAPTURE_CARD_PLATFORM,
            live.CAPTURE_CARD_LAYOUT,
        )


def test_capture_card_profile_loads_verified_fused_recognizer():
    from poker_engine.perceptual.vision.fused_card_adapter import (
        FusedCardRecognizerAdapter,
    )

    table_map, vision = live.load_calibration(
        live.CAPTURE_CARD_PLATFORM,
        live.CAPTURE_CARD_LAYOUT,
    )
    assert table_map.platform_id == live.CAPTURE_CARD_PLATFORM
    assert isinstance(vision._card, FusedCardRecognizerAdapter)

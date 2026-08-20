from __future__ import annotations

import pytest

from poker_engine.desktop.demo import DEMO_SEQUENCE
from poker_engine.desktop.serialize import analysis_to_dict


def test_analysis_to_dict_matches_wire_contract():
    d = analysis_to_dict(DEMO_SEQUENCE[1])  # flop step
    assert d["frame_seq"] == 2
    assert d["state"]["street"] == "flop"
    assert d["state"]["hero_cards"] == ["Ah", "Kh"]
    assert d["state"]["board_cards"] == ["Qh", "9h", "2c"]
    assert d["state"]["pot"] == "6"
    assert d["equity"] == {"win_rate": 0.71, "tie_rate": 0.01}
    assert d["confidence"]["overall_confidence"] == 0.95
    assert ["bet_size", "low_confidence"] in d["confidence"]["field_status"]


def test_analysis_to_dict_is_json_serializable():
    import json

    for analysis in DEMO_SEQUENCE:
        json.dumps(analysis_to_dict(analysis))  # must not raise


def test_analysis_to_dict_rejects_wrong_type():
    with pytest.raises(TypeError):
        analysis_to_dict({"not": "an analysis"})


def test_create_app_mounts_ui_and_ws():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from poker_engine.desktop.server import create_app

    app = create_app()
    client = TestClient(app)
    with client.websocket_connect("/ws") as ws:
        payload = ws.receive_json()
        assert payload["frame_seq"] == 1
        assert payload["state"]["street"] == "preflop"

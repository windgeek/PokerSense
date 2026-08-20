"""Dev entry point: run the desktop server without an editable install.

    ./.venv/bin/python tools/run_desktop_server.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from poker_engine.desktop.server import run  # noqa: E402

if __name__ == "__main__":
    run()

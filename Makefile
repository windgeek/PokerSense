PYTHON ?= python

.PHONY: install test lint clean run-desktop run-desktop-server

install:
	$(PYTHON) -m pip install -e ".[dev]"

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m flake8 src tests 2>/dev/null || echo "flake8 not installed (dev dep); run 'make install'"

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache build dist *.egg-info

# Desktop shell (needs the `desktop` extra: pip install -e ".[dev,desktop]").
# Currently streams the scripted demo sequence, not a real capture pipeline.
run-desktop:
	$(PYTHON) -m poker_engine.desktop.app

# Server only (no native window) -- useful for previewing ui/ in a browser.
run-desktop-server:
	$(PYTHON) -m poker_engine.desktop.server

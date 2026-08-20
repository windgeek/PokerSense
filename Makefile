PYTHON ?= python

.PHONY: install test lint clean

install:
	$(PYTHON) -m pip install -e ".[dev]"

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m flake8 src tests 2>/dev/null || echo "flake8 not installed (dev dep); run 'make install'"

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache build dist *.egg-info

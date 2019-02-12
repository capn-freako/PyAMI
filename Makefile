# Replace the individual build scripts with one Makefile to provide the same functionality.

.PHONY: tox clean test lint

tox:
	tox

lint:
	tox -e pylint,flake8

test:
	tox -e py36,py37

clean:
	rm -rf .tox docs/build/ __pycache__/ tests/__pycache__ .pytest_cache/ *.egg-info

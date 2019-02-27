# Replace the individual build scripts with one Makefile to provide the same functionality.
.PHONY: tox clean test lint

# If you don't want to use pipenv, replace it with pip or conda.  Tox must be installed first.
tox:
	pipenv run tox

lint:
	pipenv run tox -e pylint,flake8

test:
	pipenv run tox -e py37

clean:
	rm -rf .tox docs/build/ __pycache__/ tests/__pycache__ .pytest_cache/ *.egg-info \
		Pipfile Pipfile.lock .venv

docker-build:
	docker build -t pyami .

# Update ~/git/PyAMI to match your local path.
docker-shell:
	docker run -v ~/git/PyAMI:/data/PyAMI:rw -it pyami /bin/bash

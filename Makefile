# Makefile for PyIBIS-AMI project.
#
# Original author: David Banas <capn.freako@gmail.com>
# Original date:   February 11, 2019
#
# Copyright (c) 2019 David Banas; all rights reserved World wide.

.PHONY: dflt help check tox format lint flake8 type-check docs upload test clean distclean

PROJ_NAME := pyibis_ami
PROJ_FILE := pyproject.toml
PROJ_INFO := src/${PROJ_NAME}.egg-info/PKG-INFO
VER_FILE := proj_ver
VER_GETTER := ./get_proj_ver.py
PYTHON_EXEC := python -I
TOX_EXEC := tox
TOX_SKIP_ENV := format
PYVERS := 310 311 312
PLATFORMS := lin mac win

# Put it first so that "make" without arguments is like "make help".
dflt: help

# Prevent implicit rule searching for makefiles.
$(MAKEFILE_LIST): ;

check:
	${TOX_EXEC} run -e check

# Auto-versioning should now be complete, even for docs generation.
${VER_FILE}: ${PROJ_INFO}
	${PYTHON_EXEC} ${VER_GETTER} ${PROJ_NAME} $@

${PROJ_INFO}: ${PROJ_FILE}
	${PYTHON_EXEC} -m build
	${PYTHON_EXEC} -m pip install -e .

# For the most part, this makefile is just a switching junction for Tox.
tox:
	TOX_SKIP_ENV="${TOX_SKIP_ENV}" ${TOX_EXEC} -m test

format:
	${TOX_EXEC} run -e format

lint:
	${TOX_EXEC} run -e lint

flake8:
	${TOX_EXEC} run -e flake8

type-check:
	${TOX_EXEC} run -e type-check

docs: ${VER_FILE}
	. ./$< && ${TOX_EXEC} run -e docs

upload: ${VER_FILE}
	. ./$< && ${TOX_EXEC} run -e upload

test:
	@for V in ${PYVERS}; do \
		for P in ${PLATFORMS}; do \
			${TOX_EXEC} run -e "py$$V-$$P"; \
		done; \
	done

clean:
	rm -rf .tox build/ docs/build/ .mypy_cache .pytest_cache .venv src/*.egg-info

distclean: clean
	rm -rf dist/

help:
	@echo "Available targets:"
	@echo ""
	@echo "\tPip Targets"
	@echo "\t==========="
	@echo "\ttox: Run all Tox environments."
	@echo "\tcheck: Validate the 'pyproject.toml' file."
	@echo "\tformat: Run Tox 'format' environment."
	@echo "\t\tThis will run EXTREME reformatting on the code. Use with caution!"
	@echo "\tlint: Run Tox 'lint' environment. (Runs 'pylint' on the source code.)"
	@echo "\tflake8: Run Tox 'flake8' environment. (Runs 'flake8' on the source code.)"
	@echo "\ttype-check: Run Tox 'type-check' environment. (Runs 'mypy' on the source code.)"
	@echo "\tdocs: Run Tox 'docs' environment. (Runs 'sphinx' on the source code.)"
	@echo "\t\tTo view the resultant API documentation, open 'docs/build/index.html' in a browser."
	@echo "\tupload: Run Tox 'upload' environment."
	@echo "\t\tUploads source tarball and wheel to PyPi."
	@echo "\t\t(Only David Banas can do this.)"
	@echo "\ttest: Run Tox testing for all supported Python versions."
	@echo "\tclean: Remove all previous build results, virtual environments, and cache contents."
	@echo "\tdistclean: Runs a 'make clean' and removes 'dist/'."
	@echo ""
	@echo "\tMisc. Targets"
	@echo "\t============="
	@echo "\tcheck: Test the project TOML file integrity."

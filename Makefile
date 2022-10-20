.PHONY: tox format lint check test tests clean

tox:
	tox -p all

format:
	tox -e format

lint:
	tox -e lint

check:
	tox -e type-check

tests:
	tox -e py310

test:
	tox -e py310

clean:
	rm -rf .tox .pytest_cache htmlcov *.egg-info .coverage

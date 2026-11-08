.PHONY: install test smoke bench

install:
	pip install -e ".[test]"

test:
	pytest -q

smoke:
	repromut bench --smoke --out results/smoke

bench:
	repromut bench --out results/full

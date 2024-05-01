.PHONY: clean build test

clean:
	rm -rf dist/
	rm -rf src/*.egg-info/
	rm -rf src/alfred/__pycache__/

build:
	python -m build

test:
	python test.py

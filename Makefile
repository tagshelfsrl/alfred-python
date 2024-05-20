.PHONY: clean build test

clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf alfred/__pycache__/

build:
	python -m build

test:
	python test.py

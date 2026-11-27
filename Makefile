
.PHONY: lint format-check check fix mypy test ci docker-build docker-run dist dist-clean

IMAGE ?= cobalt-sequence-lab
VERSION := $(shell sed -n 's/^version = "\(.*\)"/\1/p' pyproject.toml)


# ruff call, if it is installed (environment.yml has it)
lint: 
	ruff check src tests scripts

format-check:
	ruff format --check src tests scripts

mypy:
	mypy src scripts

test:
	pytest --cov=cobalt

check: lint format-check

ci: check mypy test

format_fix: 
	ruff check --fix src tests scripts
	ruff format src tests scripts

# Container image for `cobalt-server` (see "Running in Docker" in README.md)
docker-build:
	docker build --build-arg VERSION=$(VERSION) -t $(IMAGE):$(VERSION) -t $(IMAGE):latest .

# Needs COBALT_API_KEYS in the environment: COBALT_API_KEYS=my-key make docker-run
docker-run:
	docker run --rm -p 8000:8000 -e COBALT_API_KEYS $(IMAGE):latest

# Distribution zip: dist/cobalt-sequence-lab-<version>.zip with the wheel, sdist, docs and
# INSTALL.txt. Needs the `build` package (in the dev extra: pip install -e ".[dev]")
dist:
	python scripts/make_dist.py

dist-clean:
	rm -rf dist build

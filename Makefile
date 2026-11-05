
.PHONY: lint format-check check fix mypy test ci docker-build docker-run

IMAGE ?= cobalt-sequence-lab
VERSION := $(shell sed -n 's/^version = "\(.*\)"/\1/p' pyproject.toml)


# ruff call, if it is installed (environment.yml has it)
lint: 
	ruff check src tests

format-check:
	ruff format --check src tests	

mypy:
	mypy src

test:
	pytest --cov=cobalt

check: lint format-check

ci: check mypy test

format_fix: 
	ruff check --fix src tests
	ruff format src tests

# Container image for `cobalt serve` (see "Running in Docker" in README.md)
docker-build:
	docker build --build-arg VERSION=$(VERSION) -t $(IMAGE):$(VERSION) -t $(IMAGE):latest .

# Needs COBALT_API_KEYS in the environment: COBALT_API_KEYS=my-key make docker-run
docker-run:
	docker run --rm -p 8000:8000 -e COBALT_API_KEYS $(IMAGE):latest

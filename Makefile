
.PHONY: lint format-check check fix mypy test ci


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
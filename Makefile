
# ruff call, if it is installed (environment.yml has it)
lint: 
	ruff check src
	ruff check tests

lint_fix: 
	ruff format src
	ruff format tests

mypy:
	mypy src

test:
	pytest

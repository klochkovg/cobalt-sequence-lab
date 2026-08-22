
# ruff call, if it is installed (environment.yml has it)
lint: 
	ruff check src

lint_fix: 
	ruff format src

mypy:
	mypy src

test:
	pytest

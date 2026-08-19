
# ruff call, if it is installed (environment.yml has it)
lint: 
	ruff check .

mypy:
	mypy src
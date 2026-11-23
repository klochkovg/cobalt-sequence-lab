# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project

Cobalt Sequence Lab: a Python CLI (`cobalt`) and optional FastAPI server for experimenting with
Biopython on sequence data (FASTA, GenBank). See `README.md` for goals, roadmap and command examples.

- Source: `src/cobalt/` (src layout, package `cobalt`), a shared core and two front-ends
  - `core/`: shared by both front-ends; imports neither of them
    - `analysis/`: processing logic behind the commands
    - `io/`: readers, writers, format sniffing
    - `model/`: data model (records, stats, QC)
    - `pipeline/`: pipeline definitions, loader, rendering, run model
  - `cli/`: the `cobalt` command, one module per subcommand (`inspect`, `stats`, `validate`,
    `normalize`, `run`, `runs`, `help`, ...), dispatched from `cli/main.py`; client mode talks to
    the server over HTTP only (`cli/client.py`)
  - `server/`: the `cobalt-server` command (`server/main.py`): FastAPI app (`app.py`), upload
    handling, middleware, auth, config file, run registry
  - `logging_config.py`: logging setup, shared by both commands
- `cli` and `server` must never import each other, and `core` imports neither. Ruff rule TID251
  enforces it (`[tool.ruff.lint]` in `pyproject.toml` plus `src/cobalt/{cli,server}/ruff.toml`).
  Tests may import across.
- Tests: `tests/cobalt/...` mirrors `src/cobalt/...`; sample inputs in `tests/test_data/`

## Environment

- Python 3.12, conda env `biolab-dev` (`environment.yml`); package installed with `pip install -e ".[dev]"`
- Server dependencies (fastapi, uvicorn, pydantic) are the optional `server` extra;
  `server/main.py` imports them lazily so a missing extra gives a clear error

## Commands

```bash
make lint          # ruff check src tests
make format-check  # ruff format --check src tests
make mypy          # mypy src
make test          # pytest --cov=cobalt
make ci            # everything CI runs
make format_fix    # auto-fix lint and formatting
```

Run `make ci` before declaring a change done; it matches `.github/workflows/ci.yml`.

## Conventions

- Ruff, line length 100, target py312; code must pass mypy
- Type hints on all functions; `from __future__ import annotations` at the top of modules
- Results go to stdout or the output file; diagnostics go to stderr via
  `log = logging.getLogger(__name__)`. Never use `print` for diagnostics.
- New behavior gets tests in the matching `tests/cobalt/...` directory
- Keep changes small and focused; match the style of the surrounding code

## Git: hands off

**Do not run any git or GitHub CLI command** (`git`, `gh`, including read-only ones like
`git status`/`git diff`) and do not modify anything inside `.git/`. The user does all version
control: staging, commits, branches, pushes, PRs. When a change is ready, say so and summarize it;
the user will commit it.

This is enforced by a PreToolUse hook (`.claude/hooks/block_git.py`, wired in `.claude/settings.json`)
and by permission deny rules. If a command is blocked, don't try to get around the hook.
Ask the user instead.

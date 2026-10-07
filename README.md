# Cobalt Sequence Lab

The main goal of this project, is experimenting with biopython and some
tooling necessary for bioinformatics tasks.

# Plans for future

Cover most of biopython functionality as part of the task. Tests and adequate build infrastructure.
Provide easy integration with one of common bioinformatics pipelines. Easy integration into cloud platforms.

# Short term plans

Integration of pytest + ruff + mypy config. Inspect command fully functional. Until 18.08.2026 for FASTA and GenBank.

# Definition of DONE (preliminary stage)

- Installable Python package
- CLI with inpsect, stats, validate, normalize
- support for FASTA and GenBank
- tests for both formats
- one example dataset folder
- README with before and after examples
- Build with github actions, including tests and lint
- outputs:
  - cleaned FASTA
  - JSON QC report
  - CSV/Parquet stats table

# Some preliminaries

Conda environment was used. It can be created with the following command:

```bash
conda create -n biolab-dev -c conda-forge \
  python=3.12 \
  biopython \
  pandas \
  pyarrow \
  numpy \
  typer \
  rich \
  pydantic \
  pytest \
  pytest-cov \
  ruff \
  mypy \
  jupyterlab \
  ipykernel
```

# Supposed capabilities (stage 1)

1. Inspect command (DONE)
   - number of records
   - guessed molecule types
   - min/max/mean length
   - formats detected
   - warning couts
2. Stats command, emit a table with one row per record
   - ID
   - description
   - length
   - alphabet class
   - GC fraction if nucleotide
   - ambiguity fraction
   - invalid char count
   - source format
   - selected annotations if present (Do I need it?)
3. Validate commands, emit structured QC
   - fatal errors
   - warnings
   - normalization notes
4. Normalize command, produce
   - cleaned IDs
   - uppercase standardized sequences
   - consistent description handling
   - filtered output formats
5. Record report
   - sequence preview
   - metadata
   - annotations
   - features summary
   - stats
   - QC notes
6. REST API
   - implementation of stats command through REST API
   - implementation of inspect command through REST API
   - implementation of validate command through REST API
   - implementation of normalize command through REST API

# Example of commands

```bash
cobalt inspect input.gb
cobalt stats input.fasta --out stats.csv
cobalt normalize input.gb --fasta cleaned.fasta
cobalt validate input.fasta --report qc.json
cobalt serve
cobalt serve --cors                         # allow any origin (UI development)
cobalt serve --cors http://localhost:5173   # allow specific origin(s)
```

# Logging

Cobalt separates **results** from **diagnostics**:

- results (stats tables, reports, sequences, `inspect` summary) go to stdout or to the file given
  with `--out` / `--report` / `--fasta`, so they can be piped safely;
- diagnostics (errors, warnings, debug details) are logged to **stderr** using Python's standard
  `logging` module, rendered by [rich](https://rich.readthedocs.io/) when stderr is a terminal.

Inside the code, modules just use `log = logging.getLogger(__name__)`. The handler is installed
once, in `cobalt.cli.main`, by `cobalt.logging_config.configure_logging`.

## Controls

| Control | Effect |
|---|---|
| `-v` / `-vv` | info / debug level |
| `-q` | errors only |
| `COBALT_LOG_LEVEL=DEBUG\|INFO\|WARNING\|ERROR` | level when no `-v`/`-q` is given |
| `COBALT_LOG_FORMAT=auto\|rich\|plain` | `auto` (default): rich on a terminal, plain text otherwise |

Global flags go **before** the command: `cobalt -v stats input.fasta`, not `cobalt stats input.fasta -v`.

Precedence for the level: `-v`/`-q` → `COBALT_LOG_LEVEL` → default (WARNING standalone, INFO for `serve`).

## Standalone (CLI, scripts, pipelines)

Default level is WARNING, so normal runs print nothing except problems:

```bash
cobalt stats missing.fasta
# ERROR    file not found: missing.fasta          (rich, interactive terminal)
# ERROR: file not found: missing.fasta            (plain, when stderr is redirected)

cobalt -q validate input.fasta --report qc.json   # errors only
cobalt -vv inspect input.gb                       # everything, for debugging
cobalt stats input.fasta > stats.csv 2> cobalt.log   # results and diagnostics in separate files
```

In workflow managers (Nextflow, Snakemake, CI) stderr is not a terminal, so `auto` already
switches to plain one-line messages, which are friendly to log collectors and `grep`.

## Server (`cobalt serve`)

The default level is INFO and every line carries a timestamp and logger name. Uvicorn's own
startup and access logs go through the same handler (uvicorn is started with `log_config=None`),
so there is a single, uniform log stream on stderr:

```text
2026-10-07 22:16:56,284 INFO uvicorn.error: Uvicorn running on http://127.0.0.1:8000
2026-10-07 22:16:57,326 INFO uvicorn.access: 127.0.0.1:33796 - "GET / HTTP/1.1" 200
```

Typical setups:

```bash
cobalt serve                                   # local development: rich, coloured output
COBALT_LOG_FORMAT=plain cobalt serve > /dev/null 2>> server.log   # local log file
cobalt -q serve                                # hide access logs, keep errors
```

In a container or under systemd, leave the output on stderr and let the platform collect it
(`docker logs`, `journalctl`, cloud logging agents). Set `COBALT_LOG_FORMAT=plain` explicitly if
the platform allocates a TTY (e.g. `docker run -t`), because rich output wraps long lines at the
terminal width, which breaks one-event-per-line log parsing.

# some use (I'm not a seasoned Python programmer, so some strange things are possible)

```bash
conda env create -f environment.yml
pip install -e .
```

Local installation

```bash
pip install -e .
```

# Some known problems

- lack of tests
- lack of precommit hooks for linter and tests
- lack of API implementation, though some infrastructure is already created

# Some future plans

- Definition of Done fulfilled
- Use of main common data sources
- Rework of data model, extensive use of dicitonaries is ugly
- Introduction of some forms of job/task model
- Introduction of some kind of pipelining model to run batches of data
- Integration with Nextflow

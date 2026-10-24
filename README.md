# Cobalt Sequence Lab

The main goal of this project is experimenting with biopython and some
tooling necessary for bioinformatics tasks.

# Plans for future

Cover most of biopython functionality as part of the task. Tests and adequate build infrastructure.
Provide easy integration with one of common bioinformatics pipelines. Easy integration into cloud platforms.

# Short term plans

Integration of pytest + ruff + mypy config. Inspect command fully functional. Until 18.08.2026 for FASTA and GenBank.

# Definition of DONE (preliminary stage)

- Installable Python package
- CLI with inspect, stats, validate, normalize
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
   - warning counts
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
cobalt stats input.fasta --sort gc_fraction --desc   # also: id, length, ambiguity_fraction, invalid_char_count
cobalt stats a.fasta b.gb.gz --out stats.csv   # several files, one table; source_file column says which
cobalt stats input.gb --out stats.parquet   # format from extension: .csv, .json, .parquet/.pq
cobalt stats input.gb --format json --out stats.txt   # --format overrides the extension
# parquet needs: pip install "cobalt-sequence-lab[parquet]"
cobalt normalize input.gb --fasta cleaned.fasta
cobalt validate input.fasta --report qc.json
cobalt serve
cobalt serve --cors                         # allow any origin (UI development)
cobalt serve --cors http://localhost:5173   # allow specific origin(s)
COBALT_API_KEYS=key1,key2 cobalt serve --host 0.0.0.0 --auth api-key   # require X-API-Key
cobalt serve --host 0.0.0.0 --allow-no-auth   # no auth: a gateway or service mesh handles it
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

| Control                                        | Effect                                                     |
| ---------------------------------------------- | ---------------------------------------------------------- |
| `-v` / `-vv`                                   | info / debug level                                         |
| `-q`                                           | errors only                                                |
| `COBALT_LOG_LEVEL=DEBUG\|INFO\|WARNING\|ERROR` | level when no `-v`/`-q` is given                           |
| `COBALT_LOG_FORMAT=auto\|rich\|plain`          | `auto` (default): rich on a terminal, plain text otherwise |

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

- lack of precommit hooks for linter and tests
- further integration with pipelines (or implementation of pipeline logic)

# Some future plans

- Use of main common data sources
- Introduction of some forms of job/task model
- Introduction of pipeline and job models
- Introduction of some kind of pipelining model to run batches of data
- Integration with Nextflow
- Wider range of input formats (see below)
- Less dependence on Biopython in the long term (see below)

## Input formats

Today the input formats are FASTA and GenBank, plain or gzip/bzip2 compressed. Formats are
detected from the content (`cobalt.io.sniff`), so each new format needs a detection rule as well
as a reader. Planned additions, mostly as input, in rough order of priority:

1. FASTQ (`@` first): raw sequencing reads and the main input of Nextflow pipelines.
2. EMBL (`ID   ... BP.`): the same content as GenBank in different syntax
3. Multiple sequence alignments: Clustal (`CLUSTAL`), Stockholm (`# STOCKHOLM 1.0`), PHYLIP
4. UniProt/SwissProt flat files (`ID   ... AA.`): protein records with annotations.
5. ABI/AB1 Sanger traces (binary, `ABIF` magic) and SnapGene `.dna` (binary)
6. PDB/mmCIF: extract chain sequences from structure files (`pdb-seqres`, `cif-seqres` in
   Biopython). Structure analysis itself stays out of scope for now, but not for the future.
7. VCF
8. Lower priority: GFF3 annotations (often with embedded FASTA), 2bit genomes

## Less dependence on Biopython

Biopython is the reason for the project and stays the reference implementation, but in the long

## Authentication for `serve` (microservice deployment)

The goal is to run `cobalt serve` as one service in a microservice system, so authentication is
pluggable and selected with `--auth`. Each mode is a FastAPI dependency attached to the router
with the processing endpoints (`/stats`, `/inspect`, `/validate`, `/normalize`); `GET /` stays
public for version info and liveness probes. Secrets come only from environment variables, never
from command-line arguments (those are visible in `ps`).

Modes:

- `none` (default): for local development. Refused on a non-loopback `--host` unless
  `--allow-no-auth` is given, for deployments where a gateway or service mesh authenticates.
- `api-key` (implemented): callers send an `X-API-Key` header; valid keys are read from
  `COBALT_API_KEYS` (comma-separated, so keys can be rotated by running with old and new keys).
  Fine for an early stage and a few internal callers, but there is no caller identity or
  per-endpoint permission.
- `jwt` (planned): OAuth2/OIDC bearer tokens from an identity provider (Keycloak, Auth0, Entra ID,
  Cognito), checked locally against the provider's JWKS with `COBALT_JWT_ISSUER`,
  `COBALT_JWT_AUDIENCE` and `COBALT_JWKS_URL`. Per-endpoint scopes such as `cobalt:stats`;
  other services get tokens with the client-credentials flow, user requests pass the user's
  token along.

Deployment path: `api-key` now → `jwt` once an identity provider exists → a service mesh
(Istio, Linkerd) providing mTLS between services, with the JWT saying who is calling and what
they may do.

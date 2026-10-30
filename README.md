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
cobalt stats reads.fastq.gz --sort mean_quality   # FASTQ adds mean_quality, min_quality, q30_fraction
cobalt normalize input.gb --fasta cleaned.fasta
cobalt normalize reads.fastq --fastq cleaned.fastq   # qualities kept
cobalt validate input.fasta --report qc.json
cobalt foldrna input.fasta                  # RNAfold-style: >id, sequence, dot-bracket (MFE)
cobalt foldrna --input GGGAAAUCC --adapter viennarna   # viennarna is the default (and only) adapter
# foldrna needs: pip install "cobalt-sequence-lab[rna]"
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

RNA folding (`cobalt foldrna`) uses ViennaRNA: `pip install -e ".[rna]"` (included in `.[dev]`).

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

Today the input formats are FASTA, GenBank, FASTQ, PDB and mmCIF, plain or gzip/bzip2
compressed. Formats
are detected from the content (`cobalt.io.sniff`), so each new format needs a detection rule as
well as a reader.

FASTQ (`@` first, `+` on the third line) is read as Sanger/Illumina 1.8+ (Phred+33). Per-read
`mean_quality`, `min_quality` and `q30_fraction` (share of bases with Phred >= 30) appear in
`stats` and `inspect`; `normalize --fastq` writes reads with their qualities. Wrapped
(multi-line) FASTQ isn't detected, and the whole file is loaded into memory, so very large read
sets are memory-bound until reading is streamed.

PDB (first line is a record name such as `HEADER`, `REMARK`, `MODEL` or `ATOM`) and mmCIF
(`data_` first) structure files are read as one protein sequence per chain, built from the
ATOM records (Biopython `pdb-atom`/`cif-atom`). Files from structure prediction tools, which
usually have no SEQRES records, give sequences too. Record ids are `<PDB id>:<chain>`, e.g.
`1A8O:A`. Coordinates and other structure data aren't kept yet.

Planned additions, mostly as input, in rough order of priority:

1. EMBL (`ID   ... BP.`): the same content as GenBank in different syntax
2. Multiple sequence alignments: Clustal (`CLUSTAL`), Stockholm (`# STOCKHOLM 1.0`), PHYLIP
3. UniProt/SwissProt flat files (`ID   ... AA.`): protein records with annotations.
4. ABI/AB1 Sanger traces (binary, `ABIF` magic) and SnapGene `.dna` (binary)
5. PDB/mmCIF: chain sequences are read (see above). Next is a structure model (chains,
   residues, atoms, B-factors) with structure output, then adapters for structure prediction
   tools.
6. VCF
7. Lower priority: GFF3 annotations (often with embedded FASTA), 2bit genomes

## Less dependence on Biopython

Biopython is the reason for the project and stays the reference implementation, but in the long

## Local and client-server modes (planned)

Cobalt runs in one of two modes:

- **local** (default): the command does the work in the current process, as it does today. No
  network connections are made.
- **client-server**: one instance runs as the server (`cobalt serve`). Other instances run as
  clients: they send the work to the server and print or write the result as a local run would.

Local mode is used unless a server URL is given, with the global `--server` flag or the
`COBALT_SERVER` environment variable:

```bash
cobalt serve --host 0.0.0.0 --auth api-key                    # machine A: the server

cobalt stats input.fasta                                      # local, as today
cobalt --server http://lab-a:8000 stats input.fasta           # client: processed on lab-a
export COBALT_SERVER=http://lab-a:8000                        # client for the whole session
cobalt stats input.fasta --out stats.csv                      # stats.csv is written locally
cobalt --local stats input.fasta                              # local, even with COBALT_SERVER set
```

| Control                       | Effect                                                        |
| ----------------------------- | ------------------------------------------------------------- |
| `--server URL`                | client mode, send the work to the cobalt server at `URL`      |
| `--local`                     | local mode, overrides `COBALT_SERVER`                         |
| `COBALT_SERVER=URL`           | client mode when neither `--server` nor `--local` is given    |
| `COBALT_API_KEY=key`          | key sent as `X-API-Key` to a server running `--auth api-key`  |

Precedence: `--server` / `--local` → `COBALT_SERVER` → local. Like `-v`, the flags go before
the command.

Why these names: `--cobalt-url` repeats the program name (`cobalt --cobalt-url ...`), and
`COBALT-URL` can't be set from a shell because a variable name can't contain `-`. `--server`
matches `serve` on the other end, and `COBALT_SERVER` follows `COBALT_LOG_LEVEL` and
`COBALT_API_KEYS`.

Rules:

- The output is the same in both modes. Input files are read and uploaded by the client, and
  results are written by the client (`--out`, `--report`, `--fasta`), so paths always refer to
  the client's machine.
- No silent fallback. If the server can't be reached, rejects the key or doesn't support the
  command, the client logs an error and exits with status 1; it doesn't run the command locally
  instead.
- The API key comes only from `COBALT_API_KEY`, never from a flag (flags are visible in `ps`).
  It's sent only to the configured server. The client should warn when a key is sent over plain
  `http://` to a host that isn't loopback.
- In client mode, the client checks the server version (`GET /`) first, so a mismatch gives a
  clear error.
- `serve` and `help` always run locally and ignore `--server` and `COBALT_SERVER`.
- `pipeline check` and `pipeline graph` only read the YAML, so they run locally in both modes.
- Client mode starts with the commands the server already exposes (`stats`, `inspect`,
  `validate`, `normalize`). `foldrna`, then `run` and `runs` once pipelines execute, need server
  endpoints first; until then they fail in client mode instead of running locally.

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

## Pipelining (partially implemented)

We introduce concept of pipeline and task.

- `task` - reusable definition for cobalt execution, inspect, validate etc.
- `pipeline` - A DAG (Directed Acyclic Graph) of tasks with wiring between them, defined in YAML
- `job` - concrete execution of the task
- `run` - execution of the whole pipeline

```bash
cobalt pipeline check pipeline.yaml     # schema + DAG validation, prints the structure
cobalt pipeline graph pipeline.yaml     # prints the DAG, one `upstream -> downstream` per line
cobalt run pipeline.yaml --backend local --param input=x.fasta --resume   # stub
cobalt runs list                        # stub: past runs from manifests
cobalt runs show <run_id>               # stub: provenance for one run
```

`pipeline check` and `pipeline graph` work; `run` and `runs` parse their arguments but only report
"not implemented yet" (exit status 1). The code lives in `src/cobalt/pipeline/` (model, loader,
text rendering).

### Pipeline file, schema version 1

Example: [`tests/test_data/pipeline_test_v1.yaml`](tests/test_data/pipeline_test_v1.yaml).

```yaml
schema_version: 1
pipeline: {name: fold-rna-from-fasta, version: 0.1.0, description: ...}
params:                      # pipeline-level knobs: type + default
  min_length: {type: int, default: 20}
inputs:                      # named, typed entry points supplied at run time
  sequences: {type: fasta}
tasks:
  validate:
    type: validate
    inputs: {file: "${inputs.sequences}"}
    params: {min_length: "${params.min_length}"}
  normalize:
    type: normalize
    inputs:
      file: "${inputs.sequences}"
      qc: "${tasks.validate.outputs.report}"   # this reference creates the edge
outputs:
  report: "${tasks.validate.outputs.report}"
```

- Top-level keys: `schema_version` (must be `1`), `pipeline` (`name` and `version` required),
  `params`, `inputs`, `tasks` (at least one), `outputs`.
- Task keys: `type` (required), `inputs`, `params`, `adapter`, `container`, `resources`, `scatter`.
- References: `${inputs.<name>}`, `${params.<name>}`, `${tasks.<task>.outputs.<key>}`. Edges of
  the DAG come from the `${tasks...}` references.
- Quote references inside inline `{...}` mappings (`{file: "${inputs.sequences}"}`): unquoted,
  `{` and `}` break the YAML.

`pipeline check` rejects unknown keys (catches typos like `adaptor`), references to undefined
inputs, params or tasks, and dependency cycles. The error names the file and the key:

```text
ERROR: pipeline.yaml: tasks.fold: unknown key 'adaptor'
ERROR: pipeline.yaml: tasks.normalize.inputs.qc: unresolved reference ${tasks.validte.outputs.report}
```

Output for the example file:

```text
$ cobalt pipeline graph tests/test_data/pipeline_test_v1.yaml
validate -> normalize
normalize -> fold
inspect
```

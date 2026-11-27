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
cobalt inspect input.gb --json --output-seq-number 5   # same summary as JSON (the REST API format)
cobalt stats input.fasta --out stats.csv
cobalt stats input.fasta --sort gc_fraction --desc   # also: id, length, ambiguity_fraction, invalid_char_count
cobalt stats a.fasta b.gb.gz --out stats.csv   # several files, one table; source_file column says which
cobalt stats input.gb --out stats.parquet   # format from extension: .csv, .json, .parquet/.pq
cobalt stats input.gb --format json --out stats.txt   # --format overrides the extension
# parquet needs: pip install "cobalt-sequence-lab[parquet]"
cobalt stats reads.fastq.gz --sort mean_quality   # FASTQ adds mean_quality, min_quality, q30_fraction
cobalt normalize input.gb --fasta cleaned.fasta
cobalt normalize reads.fastq --fastq cleaned.fastq   # qualities kept
cobalt validate input.fasta --report qc.json   # JSON QC report: passed, warning counts, warnings
cobalt validate input.fasta --json             # the same report on stdout (the REST API format)
cobalt foldrna input.fasta                  # RNAfold-style: >id, sequence, dot-bracket (MFE)
cobalt foldrna --input GGGAAAUCC --adapter viennarna   # viennarna is the default (and only) adapter
# foldrna needs: pip install "cobalt-sequence-lab[rna]"

# REST API server: a separate command; needs pip install "cobalt-sequence-lab[server]"
cobalt-server
cobalt-server --cors                         # allow any origin (UI development)
cobalt-server --cors http://localhost:5173   # allow specific origin(s)
cobalt-admin users add ada                   # add a user (asks a password); prints its API key once
cobalt-server --host 0.0.0.0 --auth api-key  # require X-API-Key: users' keys
COBALT_API_KEYS=key1,key2 cobalt-server --host 0.0.0.0 --auth api-key   # ... or shared keys
cobalt-server --host 0.0.0.0 --allow-no-auth   # no auth: a gateway or service mesh handles it
cobalt-server --api-prefix ""                # pre-0.2.0 paths, without the /api prefix
cobalt-server --max-upload-mb 500            # request body limit (default 100, 0 for none)
cobalt-server --ui-dist ../cobalt-sequence-lab-ui/dist   # also serve the built UI at /
cobalt-server --config /etc/cobalt/server.yaml   # another config file (see Server configuration)
cobalt-server --storage-dir /srv/cobalt          # server file storage
COBALT_SERVER_HOME=/srv/cobalt cobalt-server     # server home: config and storage (see below)
```

Every endpoint is served under `/api` (`--api-prefix` changes it; `""` removes it): `GET /api/`
returns the title and version, `GET /api/health` returns `{"status": "ok"}` (both public, also with
`--auth api-key`), and the OpenAPI schema and Swagger UI are at `/api/openapi.json` and `/api/docs`.
Errors are JSON `{"detail": ...}`, including unexpected ones (500). A request body over
`--max-upload-mb` MiB, or a compressed upload expanding to more than 10 times that, gives 413.
With `--ui-dist`, the UI's static files are served at `/`, and other HTML requests outside the API
prefix get its `index.html` (client-side routes).

`POST /api/inspect` takes the file as a multipart upload (any format and compression
`cobalt inspect` reads) with optional form fields `overview_only` and `output_seq_number`, and
returns what `cobalt inspect --json` prints. For paging, `offset` skips records before the listing
(`records_offset` in the response), `include_sequence=false` leaves out sequences, and
`max_warnings` caps the `warnings` list (`warnings_truncated` says whether it was cut; counts and
statistics always describe the whole file). An unreadable or unrecognized file gives 422 with the
CLI's error message:

```bash
curl -F file=@input.gb.gz -F output_seq_number=5 http://127.0.0.1:8000/api/inspect
curl -F file=@input.fasta -F overview_only=true http://127.0.0.1:8000/api/inspect
```

`POST /api/validate` takes the same `file` upload (and optional `max_warnings`) and returns the
QC report `cobalt validate --json` prints. An `invalid_characters` warning has `details`: the
distinct characters, their count and the 1-based positions of the first 10 (`null` for other kinds):

```bash
curl -F file=@input.fasta http://127.0.0.1:8000/api/validate
```

`POST /api/stats` takes one or more `file` uploads, or a `sequence` form field instead (like
`--input`; whitespace inside it is removed), with optional form fields `sort` and `desc`, and
returns what `cobalt stats --json` prints. Sending both or neither gives a field-level 422. Any
unreadable upload fails the whole request with 422:

```bash
curl -F file=@reads.fastq.gz -F file=@input.gb -F sort=length -F desc=true http://127.0.0.1:8000/api/stats
curl -F sequence=AGCGCA http://127.0.0.1:8000/api/stats
```

`POST /api/normalize` takes the same `file` upload and an optional `format` form field (`fasta`,
the default, `genbank` or `fastq`) and returns the normalized file as text, as `cobalt normalize`
would write it with `--fasta`, `--genbank` or `--fastq`. The `Content-Disposition` header suggests
a file name, and `X-Records-Read`, `X-Records-Written` and `X-Records-Skipped` count the records
(with `--cors` they are exposed to the browser):

```bash
curl -F file=@input.gb -F format=fasta http://127.0.0.1:8000/api/normalize > cleaned.fasta
```

## Server configuration

`cobalt-server` reads its settings from `cobalt-config.yaml` in the **server home** directory.
The home is set in one place, so the server and the admin commands (`cobalt-admin`) always find
the same files, whatever the working directory:

| Precedence | Source                      | Config file                          |
| ---------- | --------------------------- | ------------------------------------ |
| 1          | `--config PATH`             | `PATH` (must exist)                  |
| 2          | `--home DIR`                | `DIR/cobalt-config.yaml`             |
| 3          | `COBALT_SERVER_HOME=DIR`    | `DIR/cobalt-config.yaml`             |
| 4          | default                     | `./.cobalt-server/cobalt-config.yaml` |

Set `COBALT_SERVER_HOME` at installation (systemd unit, `/etc/environment`, the admin's shell
profile) or in the container image. A missing config file in the home is created with the
default values. The server's file storage (`storage_dir`: user store, runs) defaults to the
config file's directory and is created at startup; `cobalt-admin paths` shows every location.

```yaml
config_version: 1
host: 127.0.0.1
port: 8000
api_prefix: /api
max_upload_mb: 100
cors: null            # null: disabled; []: any origin; or a list of origins
auth: none            # none or api-key (keys: users store or $COBALT_API_KEYS, never this file)
allow_no_auth: false
ui_dist: null
storage_dir: .        # relative paths are relative to this file's directory
```

- Precedence: defaults → config file → command-line flags. `cobalt-server --port 8080` overrides
  `port: 9000` from the file.
- Files from other cobalt versions load: missing keys get their defaults, and unknown keys are
  ignored with a warning (as is a newer `config_version`). The file is never rewritten.
- Invalid values (`port: abc`, `auth: jwt`) stop the server with an error naming the key.
- Secrets are never stored in the file.

### Administration (`cobalt-admin`)

`cobalt-admin` is the service command for the server's admin, run on the server host (over ssh,
or `docker exec`). It works on the server's files directly, also while the server runs, and
needs no `server` extra. It finds the files like `cobalt-server` (`--home`, `--config`,
`--storage-dir` before the command, or `COBALT_SERVER_HOME`).

The server keeps its users, passwords and API keys in a SQLite file,
`<storage_dir>/users.sqlite3` (created at startup or by the first `cobalt-admin users` command):

```bash
cobalt-admin paths                       # config file, storage, user store, runs directory
cobalt-admin users add ada               # asks for a password; prints the new API key, only once
cobalt-admin users add bot --no-password # API key only
cobalt-admin users passwd ada            # change the password (asked twice); --clear removes it
cobalt-admin users rotate-key ada        # revoke ada's keys and print a new one, only once
cobalt-admin users list                  # names, the start of each key, password set, created
cobalt-admin users rename ada "Ada Lovelace"
cobalt-admin users remove "Ada Lovelace" # also deletes its keys

# Scripts and containers: the password comes from stdin, never from a flag (flags show in ps)
printf '%s\n' "$PW" | ssh lab-a cobalt-admin users passwd ada --password-stdin
```

- Keys are stored as SHA-256 hashes only; a lost key can't be recovered (`users rotate-key`).
- Passwords (at least 8 characters) are stored as salted scrypt hashes. They are not used by the
  API yet (it authenticates with API keys); they are ready for a UI login.
- With `--auth api-key`, a user's key authenticates as that user, and `GET /api/me` returns its
  name. Shared keys from `$COBALT_API_KEYS` keep working without an account.
- A default user, `lab user`, stands for callers without an account: everyone with `--auth none`,
  and shared-key callers. It can be renamed (`users rename "lab user" NAME`), not removed.
- `--auth api-key` needs at least one user key or shared key to start.

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

Precedence for the level: `-v`/`-q` → `COBALT_LOG_LEVEL` → default (WARNING standalone, INFO for
`cobalt-server`). `cobalt-server` takes the same `-v`/`-q` flags; as it already logs at INFO, `-v`
gives debug.

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

## Server (`cobalt-server`)

The default level is INFO and every line carries a timestamp and logger name. Uvicorn's own
startup and access logs go through the same handler (uvicorn is started with `log_config=None`),
so there is a single, uniform log stream on stderr:

```text
2026-10-07 22:16:56,284 INFO uvicorn.error: Uvicorn running on http://127.0.0.1:8000
2026-10-07 22:16:57,326 INFO uvicorn.access: 127.0.0.1:33796 - "GET / HTTP/1.1" 200
```

Typical setups:

```bash
cobalt-server                                   # local development: rich, coloured output
COBALT_LOG_FORMAT=plain cobalt-server > /dev/null 2>> server.log   # local log file
cobalt-server -q                               # hide access logs, keep errors
```

In a container or under systemd, leave the output on stderr and let the platform collect it
(`docker logs`, `journalctl`, cloud logging agents). Set `COBALT_LOG_FORMAT=plain` explicitly if
the platform allocates a TTY (e.g. `docker run -t`), because rich output wraps long lines at the
terminal width, which breaks one-event-per-line log parsing. The Docker image already sets
`COBALT_LOG_FORMAT=plain` (see [Running in Docker](#running-in-docker)).

# some use (I'm not a seasoned Python programmer, so some strange things are possible)

```bash
conda env create -f environment.yml
pip install -e .
```

RNA folding (`cobalt foldrna`) uses ViennaRNA: `pip install -e ".[rna]"` (included in `.[dev]`).
The REST API server (`cobalt-server`) needs `pip install -e ".[server]"` (also in `.[dev]`).

## Code layout

The package has a shared core and two front-ends, which never import each other (a ruff rule,
TID251, enforces it):

- `src/cobalt/core/`: sequence I/O, analysis, data model and pipeline definitions
- `src/cobalt/cli/`: the `cobalt` command; in client mode it talks to the server over HTTP only
- `src/cobalt/server/`: the `cobalt-server` command and its FastAPI app; `server/admin/` is the
  `cobalt-admin` service command (users, passwords, API keys, paths)

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

## Local and client-server modes (partially implemented)

Status: `--server`, `--local` and `COBALT_SERVER` are parsed, and the entry point
(`cobalt.cli.main`) decides between local and client mode (`cobalt.cli.remote`). Of the remote
calls, only `runs list` and `runs show` are implemented (`cobalt.cli.client`, standard library
HTTP). The other commands log a warning in client mode and still run locally.
Everything below about the server side describes the target behavior.

Cobalt runs in one of two modes:

- **local** (default): the command does the work in the current process, as it does today. No
  network connections are made. Functionality of pipelines is limited or purely synchronous.
- **client-server**: one instance runs as the server (`cobalt-server`). Other instances run as
  clients: they send the work to the server and print or write the result as a local run would.

Local mode is used unless a server URL is given, with the global `--server` flag or the
`COBALT_SERVER` environment variable:

```bash
cobalt-server --host 0.0.0.0 --auth api-key                    # machine A: the server

cobalt stats input.fasta                                      # local, as today
cobalt --server http://lab-a:8000 stats input.fasta           # client: processed on lab-a
export COBALT_SERVER=http://lab-a:8000                        # client for the whole session
cobalt stats input.fasta --out stats.csv                      # stats.csv is written locally
cobalt --local stats input.fasta                              # local, even with COBALT_SERVER set
```

| Control              | Effect                                                       |
| -------------------- | ------------------------------------------------------------ |
| `--server URL`       | client mode, send the work to the cobalt-serverr at `URL`     |
| `--local`            | local mode, overrides `COBALT_SERVER`                        |
| `COBALT_SERVER=URL`  | client mode when neither `--server` nor `--local` is given   |
| `COBALT_API_KEY=key` | key sent as `X-API-Key` to a server running `--auth api-key` |

Precedence: `--server` / `--local` → `COBALT_SERVER` → local. Like `-v`, the flags go before
the command.

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
- In client mode, the client checks the server version (`GET /api/`) first, so a mismatch gives a
  clear error.
- `help` and `pipeline` always run locally and ignore `--server` and `COBALT_SERVER`.
- `run` and `runs` are server-only: in local mode they fail with "not supported in CLI mode".
- `pipeline check` and `pipeline graph` only read the YAML, so they run locally in both modes.
- Client mode starts with the commands the server already exposes (`stats`, `inspect`,
  `validate`, `normalize`).

  `foldrna` and `run` are not implemented yet and have stub endpoints (`POST /api/foldrna`,
  `POST /api/run`) that answer 501 Not Implemented. `GET /api/runs` and `GET /api/runs/{run_id}`
  answer from the server's run registry (see [Runs](#runs)), and `cobalt runs` calls them.

## Authentication for `cobalt-server` (microservice deployment)

The goal is to run `cobalt-server` as one service in a microservice system, so authentication is
pluggable and selected with `--auth`. Each mode is a FastAPI dependency attached to the router
with the processing endpoints (`/api/stats`, `/api/inspect`, `/api/validate`, `/api/normalize`,
the `/api/foldrna` and `/api/run` stubs, and `/api/runs`); `GET /api/` (version info) and
`GET /api/health` (liveness probes) stay public. Secrets come only from environment variables, never
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

## Building a distribution zip

`make dist` (script: `scripts/make_dist.py`; needs the `build` package from `.[dev]`) builds the
wheel and sdist and packs them into `dist/cobalt-sequence-lab-<version>.zip`:

```
cobalt-sequence-lab-<version>/
    cobalt_sequence_lab-<version>-py3-none-any.whl
    cobalt_sequence_lab-<version>.tar.gz
    README.md  LICENSE  THIRD_PARTY_NOTICE.md
    INSTALL.txt                      # install steps for this version
```

Dependencies are not bundled; pip downloads them from PyPI. To install from the zip:

```bash
unzip cobalt-sequence-lab-<version>.zip && cd cobalt-sequence-lab-<version>
python3 -m venv .venv && . .venv/bin/activate
pip install "cobalt_sequence_lab-<version>-py3-none-any.whl[server]"
```

`make dist-clean` removes `dist/` and `build/`.

## Running in Docker

The `Dockerfile` at the repository root builds one image with the package and its `server`
dependencies (installed with pip from `pyproject.toml`; the conda environment is for development
only). It has the commands `cobalt`, `cobalt-server` and `cobalt-admin`, and by default runs
`cobalt-server --host 0.0.0.0 --port 8000 --auth api-key`.

```bash
make docker-build                              # tags cobalt-sequence-lab:<version> and :latest

# Server: API keys come from the environment at runtime and are never baked into the image
COBALT_API_KEYS=my-key make docker-run
docker run --rm -p 8000:8000 -e COBALT_API_KEYS=key1,key2 cobalt-sequence-lab
curl -H "X-API-Key: key1" -F file=@seqs.fasta http://127.0.0.1:8000/api/stats

# Behind a gateway or service mesh that authenticates: override the command
docker run --rm -p 8000:8000 cobalt-sequence-lab cobalt-server --host 0.0.0.0 --allow-no-auth

# Admin: run cobalt-admin in the running container (COBALT_SERVER_HOME is set in the image)
docker exec -it CONTAINER cobalt-admin users add ada
printf '%s\n' "$PW" | docker exec -i CONTAINER cobalt-admin users passwd ada --password-stdin

# CLI: run `cobalt` instead; mount the input files to /data (the working directory)
docker run --rm -v "$PWD:/data" cobalt-sequence-lab cobalt stats seqs.fasta
```

Notes:

- Without `COBALT_API_KEYS` the default command exits with an error instead of serving
  unauthenticated.
- Logs are plain text on stderr; read them with `docker logs` or the platform's log collector.
- `HEALTHCHECK` polls `GET /api/health`, which is public, so liveness probes need no API key.
- The server keeps its config and storage in `/data/.cobalt-server` (created on first start):
  the image sets `COBALT_SERVER_HOME=/data/.cobalt-server`, so `cobalt-admin` finds it from any
  working directory. Mount a volume at `/data` to keep them across containers; override the
  variable (`-e COBALT_SERVER_HOME=...`) to move them.
- The server runs as the unprivileged user `cobalt` (uid 10001). Uploads are written to a
  temporary directory under `/tmp`, so with `--read-only` also mount `--tmpfs /tmp`.
- RNA folding (ViennaRNA, the `rna` extra) is not in the image yet; it will be added when
  `/foldrna` is implemented.
- CI (`docker` job in `.github/workflows/ci.yml`) builds the image and smoke-tests the server, the
  API-key check and CLI mode.

## Pipelining (partially implemented)

We introduce concept of pipeline and task.

- `task` - reusable definition for cobalt execution, inspect, validate etc.
- `pipeline` - A DAG (Directed Acyclic Graph) of tasks with wiring between them, defined in YAML
- `job` - concrete execution of the task
- `run` - execution of the whole pipeline

```bash
cobalt pipeline check pipeline.yaml     # schema + DAG validation, prints the structure
cobalt pipeline graph pipeline.yaml     # prints the DAG, one `upstream -> downstream` per line
cobalt --server http://lab-a:8000 run pipeline.yaml --param input=x.fasta --resume   # stub
cobalt --server http://lab-a:8000 runs list            # the server's runs, newest first
cobalt --server http://lab-a:8000 runs show <run_id>   # one run: params, status of each task
cobalt --server http://lab-a:8000 runs list --json     # the server's JSON answer instead of text
```

`pipeline check` and `pipeline graph` work. `run` and `runs` are server-only commands: in local
(CLI) mode they report "not supported in CLI mode" (exit status 1).

- `runs list` and `runs show` work in client mode (`--server URL` or `COBALT_SERVER`). They call
  `GET /api/runs` and `GET /api/runs/{run_id}` on the server; the server's API prefix must be
  the default `/api`. If the server runs `--auth api-key`, set `COBALT_API_KEY`. A server error
  (unknown run, wrong key, server unreachable) is logged and gives exit status 1.
- `run` in client mode still reports "not implemented yet" (exit status 1).

The
code lives in `src/cobalt/core/pipeline/`: the definition model (`Pipeline`, `Task`), the loader,
text rendering and the run model (`PipelineRun`, `TaskRun`). The run registry (`RunRegistry`) is
server-side, in `src/cobalt/server/registry.py`.

### Runs

`cobalt-server` keeps one run registry for its whole lifetime. It holds every pipeline run with its
status (`pending`, `running`, `succeeded`, `failed`, `cancelled`) and the status of each task.
Each run is stored in `<storage_dir>/runs/<run_id>/`: `manifest.json` (the run and its tasks) and
`pipeline.yaml` (a copy of the definition, for provenance). The server reloads the manifests at
startup. An invalid manifest is skipped with a warning, and a run that was still pending or
running when the server stopped is marked `failed` ("interrupted: server stopped").

- `GET /api/runs`: all runs, newest first, each with task counts per status.
- `GET /api/runs/{run_id}`: one run with its parameters and tasks, or 404.

Nothing executes runs yet (`POST /api/run` answers 501), so the registry only lists the runs
already stored.

### Pipeline file, schema version 1

Example: [`tests/test_data/pipeline_test_v1.yaml`](tests/test_data/pipeline_test_v1.yaml).

```yaml
schema_version: 1
pipeline: { name: fold-rna-from-fasta, version: 0.1.0, description: ... }
params: # pipeline-level knobs: type + default
  min_length: { type: int, default: 20 }
inputs: # named, typed entry points supplied at run time
  sequences: { type: fasta }
tasks:
  validate:
    type: validate
    inputs: { file: "${inputs.sequences}" }
    params: { min_length: "${params.min_length}" }
  normalize:
    type: normalize
    inputs:
      file: "${inputs.sequences}"
      qc: "${tasks.validate.outputs.report}" # this reference creates the edge
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

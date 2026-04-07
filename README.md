# Cobalt Sequence Lab

The main goal of this project, is experimenting with biopython and some
tooling necessary for bioinformatics tasks.

# Definition of DONE (according to chatbot)

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

I used conda environment created with the following command:

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

# Supposed capabilities

1. Inspect command
   - number of records
   - guessed molecule types
   - min/max/mean length
   - formats detected
   - warning couts
2. State command, emit a table with one row per crecord
   - ID
   - description
   - length
   - alphabet class
   - GC fraction if nucleotide
   - ambiguity fraction
   - invalid char count
   - source format
   - selected annotations if present
3. Validate commands, emit structured QC
   - fatal errors
   - warnings
   - normalization notes
4. Normalize command, produce
   - cleaned IDs
   - uppercase standardized sequences
   - consistent desciption handling
   - filtered output formats
5. Record report
   - sequene preview
   - metadata
   - annotations
   - features summary
   - stats
   - QC notes

# Example of commands

```bash
cobalt inspect input.gb
cobalt stats input.fasta --out stats.csv
cobalt normalize input.gb --fasta cleaned.fasta
cobalt validate input.fasta --report qc.json
```

# some use (I'm not a seasoned Python programmer, so some strange things are possible)

```bash
conda env create -f environment.yml
pip install -e .
```

"""Build a distribution zip: wheel, sdist, docs and install notes.

Usage: python scripts/make_dist.py [--root DIR] [--outdir DIR]   (or: make dist)

Writes <outdir>/cobalt-sequence-lab-<version>.zip with everything under a
cobalt-sequence-lab-<version>/ folder. Needs the `build` package (in the `dev` extra).
"""

from __future__ import annotations

import argparse
import importlib.util
import logging
import subprocess
import sys
import tempfile
import tomllib
import zipfile
from collections.abc import Sequence
from pathlib import Path

log = logging.getLogger(__name__)

DIST_NAME = "cobalt-sequence-lab"
DOC_FILES = ("README.md", "LICENSE", "THIRD_PARTY_NOTICE.md")
DEFAULT_ROOT = Path(__file__).resolve().parent.parent


def build_available() -> bool:
    """True if the `build` package (python -m build) is importable."""
    return importlib.util.find_spec("build") is not None


def read_version(pyproject: Path) -> str:
    """Return `[project].version` from a pyproject.toml."""
    with pyproject.open("rb") as fh:
        data = tomllib.load(fh)
    return str(data["project"]["version"])


def build_packages(root: Path, outdir: Path) -> tuple[Path, Path]:
    """Build the wheel and sdist of `root` into `outdir`; return their paths."""
    log.info("building wheel and sdist from %s", root)
    subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--sdist", "--outdir", str(outdir), str(root)],
        check=True,
    )
    wheels = sorted(outdir.glob("*.whl"))
    sdists = sorted(outdir.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        raise RuntimeError(f"expected one wheel and one sdist in {outdir}, got {wheels + sdists}")
    return wheels[0], sdists[0]


def render_install_txt(version: str, wheel_name: str) -> str:
    """Return the INSTALL.txt text for this release."""
    return f"""\
Cobalt Sequence Lab {version}
{"=" * (20 + len(version))}

Requirements: Python 3.12 or newer. Dependencies (biopython, rich, pyyaml and, for the
server, fastapi/uvicorn/pydantic) are downloaded from PyPI during installation.

Install into a virtual environment (from this folder):

    python3 -m venv .venv
    . .venv/bin/activate              # Windows: .venv\\Scripts\\activate
    pip install "{wheel_name}[server]"

This installs three commands:

    cobalt          the sequence processing CLI     (cobalt --help)
    cobalt-server   the REST API server             (cobalt-server --help)
    cobalt-admin    server administration           (cobalt-admin --help)

Optional extras, combined in the brackets, e.g. "{wheel_name}[server,parquet]":

    parquet   Parquet output (pyarrow)
    rna       RNA folding (ViennaRNA)

The sdist (cobalt_sequence_lab-{version}.tar.gz) holds the source. See README.md for the
commands, server configuration and examples.
"""


def write_zip(zip_path: Path, prefix: str, files: dict[str, Path], extra: dict[str, str]) -> None:
    """Write `files` (archive name -> source) and `extra` (archive name -> text) under `prefix/`."""
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, source in files.items():
            zf.write(source, f"{prefix}/{name}")
        for name, text in extra.items():
            zf.writestr(f"{prefix}/{name}", text)


def make_dist(root: Path, outdir: Path) -> Path:
    """Build the packages and write the distribution zip; return its path."""
    version = read_version(root / "pyproject.toml")
    prefix = f"{DIST_NAME}-{version}"
    with tempfile.TemporaryDirectory() as tmp:
        wheel, sdist = build_packages(root, Path(tmp))
        files = {wheel.name: wheel, sdist.name: sdist}
        files.update({name: root / name for name in DOC_FILES})
        zip_path = outdir / f"{prefix}.zip"
        write_zip(zip_path, prefix, files, {"INSTALL.txt": render_install_txt(version, wheel.name)})
    log.info("wrote %s", zip_path)
    return zip_path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the cobalt-sequence-lab dist zip.")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="project root")
    parser.add_argument("--outdir", type=Path, help="output directory (default: <root>/dist)")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if not build_available():
        log.error("the 'build' package is missing: pip install build (or pip install -e '.[dev]')")
        return 1
    root: Path = args.root.resolve()
    outdir: Path = args.outdir if args.outdir is not None else root / "dist"
    try:
        zip_path = make_dist(root, outdir)
    except (subprocess.CalledProcessError, RuntimeError, OSError) as exc:
        log.error("dist build failed: %s", exc)
        return 1
    print(zip_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())

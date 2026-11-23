"""File helpers shared by the server's persistent state (config, run manifests)."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

DEFAULT_FILE_MODE = 0o644


def write_text_atomic(path: Path, text: str, mode: int = DEFAULT_FILE_MODE) -> None:
    """Write `text` to `path` atomically, creating parent directories.

    The text goes to a temporary file in the same directory, which then replaces `path`, so a
    reader never sees a half-written file. Raises OSError.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as tmp:
            tmp.write(text)
        # mkstemp creates the file 0600
        os.chmod(tmp_name, mode)
        os.replace(tmp_name, path)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise

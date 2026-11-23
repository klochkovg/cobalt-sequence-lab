"""Server configuration of `cobalt-server`: a versioned YAML file and its reader and writer.

The file lives at `./.cobalt-server/cobalt-config.yaml` by default. A file written by another
cobalt version still loads: parameters it lacks get their defaults and parameters this version
doesn't know are ignored (with a warning). Invalid values are errors. Secrets (API keys) are never
stored here; they come from the environment.

This module must not import the optional `server` dependencies (fastapi, uvicorn).
"""

from __future__ import annotations

import dataclasses
import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from cobalt.core.io.files import write_text_atomic

log = logging.getLogger(__name__)

CONFIG_VERSION = 1
SERVER_DIR = ".cobalt-server"
CONFIG_FILENAME = "cobalt-config.yaml"
CONFIG_FILE_MODE = 0o644

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
DEFAULT_API_PREFIX = "/api"
DEFAULT_MAX_UPLOAD_MB = 100
AUTH_MODES = ("none", "api-key")

CONFIG_HEADER = (
    "# Cobalt Sequence Lab server configuration (cobalt-server).\n"
    "# Command-line flags override these values. Relative paths are relative to this file's\n"
    "# directory. Never put secrets here: API keys come from $COBALT_API_KEYS.\n"
)


class ServerConfigError(Exception):
    """A config file that can't be read or holds an invalid value; the message is ready to log."""


def default_config_path(cwd: Path | None = None) -> Path:
    """Return the default config file path under `cwd` (the current directory by default)."""
    return (cwd if cwd is not None else Path.cwd()) / SERVER_DIR / CONFIG_FILENAME


@dataclass(slots=True)
class ServerConfig:
    """Parameters of `cobalt-server`; each default matches the flag's default."""

    config_version: int = CONFIG_VERSION
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    api_prefix: str = DEFAULT_API_PREFIX
    max_upload_mb: int = DEFAULT_MAX_UPLOAD_MB
    # None disables CORS; an empty list allows any origin
    cors: list[str] | None = None
    auth: str = "none"
    allow_no_auth: bool = False
    ui_dist: Path | None = None
    # Server file storage; "." is the config file's directory (.cobalt-server)
    storage_dir: Path = field(default_factory=lambda: Path("."))

    def with_overrides(self, **values: Any) -> ServerConfig:
        """Return a copy with the given values replaced; None values are ignored."""
        return dataclasses.replace(self, **{k: v for k, v in values.items() if v is not None})

    def resolve_paths(self, config_dir: Path) -> ServerConfig:
        """Return a copy whose relative paths are made relative to `config_dir`."""
        return dataclasses.replace(
            self,
            storage_dir=config_dir / self.storage_dir,
            ui_dist=None if self.ui_dist is None else config_dir / self.ui_dist,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return the config as plain YAML-ready values, paths as strings."""
        data = dataclasses.asdict(self)
        for key, value in data.items():
            if isinstance(value, Path):
                data[key] = str(value)
        return data


def _int_in_range(low: int, high: int | None) -> Callable[[object], int]:
    expected = (
        f"expected an integer {low}-{high}" if high is not None else f"expected an integer >= {low}"
    )

    def parse(value: object) -> int:
        # bool is an int subclass: `port: true` must not become port 1
        if (
            isinstance(value, int)
            and not isinstance(value, bool)
            and value >= low
            and (high is None or value <= high)
        ):
            return value
        raise ValueError(expected)

    return parse


def _string(value: object) -> str:
    if isinstance(value, str):
        return value
    raise ValueError("expected a string")


def _non_empty_string(value: object) -> str:
    if isinstance(value, str) and value.strip():
        return value
    raise ValueError("expected a non-empty string")


def _bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    raise ValueError("expected true or false")


def _auth_mode(value: object) -> str:
    if value in AUTH_MODES:
        return str(value)
    raise ValueError(f"expected one of {', '.join(AUTH_MODES)}")


def _origins(value: object) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return list(value)
    raise ValueError("expected a list of origins, [] for any origin, or null to disable CORS")


def _path(value: object) -> Path:
    return Path(_non_empty_string(value))


def _optional_path(value: object) -> Path | None:
    return None if value is None else _path(value)


# Parser of each field (except config_version): returns the value or raises ValueError
FIELD_PARSERS: dict[str, Callable[[object], object]] = {
    "host": _non_empty_string,
    "port": _int_in_range(1, 65535),
    "api_prefix": _string,
    "max_upload_mb": _int_in_range(0, None),
    "cors": _origins,
    "auth": _auth_mode,
    "allow_no_auth": _bool,
    "ui_dist": _optional_path,
    "storage_dir": _path,
}


def load_server_config(path: Path) -> ServerConfig:
    """Read the config file `path`.

    Missing keys get their defaults and unknown keys are ignored with a warning, so files of
    older and newer config versions load. The result always has the current CONFIG_VERSION; the
    file itself is never rewritten. Raises ServerConfigError if the file can't be read or a value
    is invalid.
    """
    try:
        with open(path) as f:
            data = yaml.safe_load(f)
    except FileNotFoundError:
        raise ServerConfigError(f"config file not found: {path}") from None
    except IsADirectoryError:
        raise ServerConfigError(f"config file is a directory: {path}") from None
    except OSError as exc:
        raise ServerConfigError(f"could not read {path}: {exc}") from None
    except yaml.YAMLError as exc:
        raise ServerConfigError(f"{path}: invalid YAML: {exc}") from None
    try:
        return parse_server_config({} if data is None else data, str(path))
    except ServerConfigError as exc:
        raise ServerConfigError(f"{path}: {exc}") from None


def parse_server_config(data: object, source: str = "config") -> ServerConfig:
    """Build a ServerConfig from already parsed YAML (see `load_server_config`).

    `source` names the file in log messages. Raises ServerConfigError for an invalid value.
    """
    if not isinstance(data, Mapping):
        raise ServerConfigError(f"expected a mapping, got {type(data).__name__}")
    _check_version(data.get("config_version"), source)

    values: dict[str, object] = {}
    for name, parse in FIELD_PARSERS.items():
        if name not in data:
            continue
        try:
            values[name] = parse(data[name])
        except ValueError as exc:
            raise ServerConfigError(f"{name}: {exc}, got {data[name]!r}") from None

    defaulted = [name for name in FIELD_PARSERS if name not in data]
    if defaulted:
        log.debug("%s: defaults used for %s", source, ", ".join(defaulted))
    unknown = [str(key) for key in data if key != "config_version" and key not in FIELD_PARSERS]
    if unknown:
        log.warning("%s: ignoring unknown key(s): %s", source, ", ".join(unknown))
    return ServerConfig(**values)  # type: ignore[arg-type]


def _check_version(version: object, source: str) -> None:
    """Validate `config_version` and log how a version mismatch is handled."""
    if version is None:
        log.warning("%s: no config_version, read as version %d", source, CONFIG_VERSION)
        return
    if not isinstance(version, int) or isinstance(version, bool):
        raise ServerConfigError(f"config_version: expected an integer, got {version!r}")
    if version < CONFIG_VERSION:
        log.info(
            "%s: config version %d is older than %d: missing keys get defaults",
            source,
            version,
            CONFIG_VERSION,
        )
    elif version > CONFIG_VERSION:
        log.warning(
            "%s: config version %d is newer than %d (written by a newer cobalt): "
            "unknown keys are ignored",
            source,
            version,
            CONFIG_VERSION,
        )


def save_server_config(config: ServerConfig, path: Path) -> None:
    """Write `config` to `path` with the current CONFIG_VERSION, creating parent directories.

    The file is replaced atomically, so a reader never sees a half-written config.
    """
    data = dataclasses.replace(config, config_version=CONFIG_VERSION).to_dict()
    # The config holds no secrets, so it is readable by others
    text = CONFIG_HEADER + yaml.safe_dump(data, sort_keys=False)
    write_text_atomic(path, text, CONFIG_FILE_MODE)


def normalize_api_prefix(prefix: str) -> str:
    """Return `prefix` with one leading slash and no trailing slash; "" stays "" (no prefix)."""
    stripped = prefix.strip().strip("/")
    return f"/{stripped}" if stripped else ""

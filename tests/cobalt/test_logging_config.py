import logging

import pytest
from rich.logging import RichHandler

from cobalt.logging_config import configure_logging, resolve_level


@pytest.mark.parametrize(
    ("verbose", "quiet", "expected"),
    [
        (0, False, logging.WARNING),
        (1, False, logging.INFO),
        (2, False, logging.DEBUG),
        (0, True, logging.ERROR),
    ],
)
def test_resolve_level_flags(monkeypatch, verbose, quiet, expected):
    monkeypatch.delenv("COBALT_LOG_LEVEL", raising=False)
    assert resolve_level(verbose, quiet, logging.WARNING) == expected


def test_resolve_level_env(monkeypatch):
    monkeypatch.setenv("COBALT_LOG_LEVEL", "debug")
    assert resolve_level(0, False, logging.WARNING) == logging.DEBUG
    # flags win over the environment
    assert resolve_level(0, True, logging.WARNING) == logging.ERROR


def test_resolve_level_bad_env_falls_back(monkeypatch):
    monkeypatch.setenv("COBALT_LOG_LEVEL", "loud")
    assert resolve_level(0, False, logging.INFO) == logging.INFO


def cobalt_handlers():
    return [h for h in logging.getLogger().handlers if h.get_name() == "cobalt"]


def test_configure_replaces_handler(monkeypatch):
    monkeypatch.setenv("COBALT_LOG_FORMAT", "plain")
    configure_logging()
    configure_logging()
    assert len(cobalt_handlers()) == 1


def test_configure_rich_format(monkeypatch):
    monkeypatch.setenv("COBALT_LOG_FORMAT", "rich")
    configure_logging()
    assert isinstance(cobalt_handlers()[0], RichHandler)


def test_server_defaults_to_info(monkeypatch):
    monkeypatch.delenv("COBALT_LOG_LEVEL", raising=False)
    configure_logging(server=True)
    assert logging.getLogger().level == logging.INFO

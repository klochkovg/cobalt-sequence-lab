import logging

import pytest


@pytest.fixture(autouse=True)
def restore_root_logger():
    """cobalt's main() installs a handler on the root logger; undo it after each test."""
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    yield
    root.handlers[:] = handlers
    root.setLevel(level)

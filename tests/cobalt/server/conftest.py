import pytest

from cobalt.server.config import HOME_ENV


@pytest.fixture(autouse=True)
def no_server_home(monkeypatch):
    """Tests choose the server home themselves: ignore one set in the environment."""
    monkeypatch.delenv(HOME_ENV, raising=False)


@pytest.fixture
def ui_dist(tmp_path):
    """A minimal built UI."""
    (tmp_path / "index.html").write_text("<html>cobalt ui</html>")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.js").write_text("console.log('ui')")
    return tmp_path

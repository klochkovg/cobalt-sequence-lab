import pytest


@pytest.fixture
def ui_dist(tmp_path):
    """A minimal built UI."""
    (tmp_path / "index.html").write_text("<html>cobalt ui</html>")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.js").write_text("console.log('ui')")
    return tmp_path

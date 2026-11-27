from __future__ import annotations

import importlib.util
import sys
import zipfile
from pathlib import Path
from types import ModuleType

import pytest

import cobalt

ROOT = Path(__file__).resolve().parents[2]


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("make_dist", ROOT / "scripts" / "make_dist.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["make_dist"] = module
    spec.loader.exec_module(module)
    return module


make_dist = _load_script()


def _fake_project(root: Path, version: str = "9.9.9") -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "pyproject.toml").write_text(f'[project]\nname = "x"\nversion = "{version}"\n')
    for name in make_dist.DOC_FILES:
        (root / name).write_text(f"{name} text\n")


def _fake_build(root: Path, outdir: Path) -> tuple[Path, Path]:
    version = make_dist.read_version(root / "pyproject.toml")
    wheel = outdir / f"cobalt_sequence_lab-{version}-py3-none-any.whl"
    sdist = outdir / f"cobalt_sequence_lab-{version}.tar.gz"
    wheel.write_bytes(b"wheel")
    sdist.write_bytes(b"sdist")
    return wheel, sdist


def test_read_version_matches_package() -> None:
    assert make_dist.read_version(ROOT / "pyproject.toml") == cobalt.__version__


def test_install_txt_names_wheel_and_server_extra() -> None:
    text = make_dist.render_install_txt("1.2.3", "pkg-1.2.3-py3-none-any.whl")
    assert 'pip install "pkg-1.2.3-py3-none-any.whl[server]"' in text
    assert "Cobalt Sequence Lab 1.2.3" in text


def test_make_dist_layout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "proj"
    _fake_project(root)
    monkeypatch.setattr(make_dist, "build_packages", _fake_build)

    zip_path = make_dist.make_dist(root, tmp_path / "dist")

    assert zip_path == tmp_path / "dist" / "cobalt-sequence-lab-9.9.9.zip"
    prefix = "cobalt-sequence-lab-9.9.9/"
    with zipfile.ZipFile(zip_path) as zf:
        names = set(zf.namelist())
        install = zf.read(prefix + "INSTALL.txt").decode()
        assert zf.read(prefix + "README.md") == b"README.md text\n"
    assert names == {
        prefix + "cobalt_sequence_lab-9.9.9-py3-none-any.whl",
        prefix + "cobalt_sequence_lab-9.9.9.tar.gz",
        prefix + "README.md",
        prefix + "LICENSE",
        prefix + "THIRD_PARTY_NOTICE.md",
        prefix + "INSTALL.txt",
    }
    assert "cobalt_sequence_lab-9.9.9-py3-none-any.whl[server]" in install


def test_make_dist_overwrites_existing_zip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "proj"
    _fake_project(root)
    monkeypatch.setattr(make_dist, "build_packages", _fake_build)
    outdir = tmp_path / "dist"

    make_dist.make_dist(root, outdir)
    (root / "README.md").write_text("changed\n")
    zip_path = make_dist.make_dist(root, outdir)

    with zipfile.ZipFile(zip_path) as zf:
        assert zf.read("cobalt-sequence-lab-9.9.9/README.md") == b"changed\n"
        assert len(zf.namelist()) == 6


def test_main_prints_zip_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "proj"
    _fake_project(root)
    monkeypatch.setattr(make_dist, "build_packages", _fake_build)
    monkeypatch.setattr(make_dist, "build_available", lambda: True)

    code = make_dist.main(["--root", str(root), "--outdir", str(tmp_path / "out")])

    assert code == 0
    assert capsys.readouterr().out.strip() == str(
        tmp_path / "out" / "cobalt-sequence-lab-9.9.9.zip"
    )


def test_main_fails_without_build(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _fake_project(tmp_path)
    monkeypatch.setattr(make_dist, "build_available", lambda: False)

    assert make_dist.main(["--root", str(tmp_path)]) == 1
    assert not (tmp_path / "dist").exists()

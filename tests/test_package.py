from importlib.metadata import version

import dhara


def test_version_matches_the_package_metadata() -> None:
    assert version("dhara") == dhara.__version__


def test_paths_point_into_the_repository() -> None:
    assert (dhara.REPO / "pyproject.toml").is_file()
    assert dhara.DATA.parent == dhara.REPO
    assert dhara.RUNS.parent == dhara.REPO

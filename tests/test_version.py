import re


def test_version_semver():
    from codex import __version__

    assert re.match(r"^\d+\.\d+\.\d+(?:[.-][A-Za-z0-9.]+)?$", __version__), __version__

"""
Test the common module.

Requires --log-format="%(levelname)s:%(name)s:%(message)s"

"""
from pathlib import Path
from unittest.mock import Mock

import pytest

import common


@pytest.fixture()
def mock_config(tmp_path, monkeypatch):
    monkeypatch.setattr(
        common, "Path", Mock(wraps=Path, cwd=Mock(return_value=tmp_path))
    )
    file = tmp_path / "config.toml"
    file.write_text(
        '[reader]\nunique_key="value"\n[writer]\nunique_key="ignore this"\n'
    )
    return file


def test_get_config_found(mock_config):
    config = common.get_config(reader={"hgtg": 42})
    assert config["reader"]["unique_key"] == "value"
    assert config["reader"]["hgtg"] == 42


def test_get_config_notfound(mock_no_config):
    config = common.get_config(reader={"hgtg": 42})
    assert "unique_key" not in config
    assert config["reader"] == common.DEFAULT_READER_CONFIG | {"hgtg": 42}
    assert config["reader"]["hgtg"] == 42

"""
Test the common module.

Requires --log-format="%(levelname)s:%(name)s:%(message)s"

"""
from pathlib import Path
import os
import tomllib
from unittest.mock import Mock, call

import pytest

import common


@pytest.fixture()
def mock_config(tmp_path, monkeypatch):
    mock_path_class = Mock(
        wraps=Path,
        cwd=Mock(return_value=tmp_path / "cwd"),
        home=Mock(return_value=tmp_path / "home"),
    )
    monkeypatch.setattr(common, "Path", mock_path_class)

    (tmp_path / "cwd").mkdir()
    (tmp_path / "home").mkdir()
    (tmp_path / "alt").mkdir()

    config = tmp_path / "cwd" / "config.toml"
    config.write_text(
        '[reader]\nunique_key="value"\n[writer]\nunique_key="ignore this"\n'
    )
    creds = tmp_path / "home" / "fdrdr_config.toml"
    creds.write_text(
        '[notifier.smtp]\nhost="home"\nport=1\n'
    )
    alt_creds = tmp_path / "alt" / "fdrdr_config.toml"
    alt_creds.write_text(
        '[notifier.smtp]\nhost="alt"\nport=2\n'
    )
    return mock_path_class


def test_get_config_found(mock_config):
    config = common.get_config(reader={"hgtg": 42})
    assert mock_config.mock_calls == [call.home(), call.cwd()]
    assert config["reader"]["unique_key"] == "value"
    assert config["reader"]["hgtg"] == 42
    assert config["notifier"]["smtp"]['host'] == "home"

def test_get_config_alt_found(mock_config, monkeypatch, tmp_path):
    alt = tmp_path / "alt"
    monkeypatch.setenv("FDRDR_CREDENTIALS", str(alt))
    config = common.get_config(reader={"hgtg": 42})
    assert mock_config.mock_calls == [
        call(str(alt)),
        call.cwd()]
    assert config["reader"]["unique_key"] == "value"
    assert config["reader"]["hgtg"] == 42
    assert config["notifier"]["smtp"]['host'] == "alt"


def test_get_config_notfound(mock_no_config):
    config = common.get_config(reader={"hgtg": 42})
    assert "unique_key" not in config
    assert config["reader"] == common.DEFAULT_READER_CONFIG | {"hgtg": 42}
    assert config["reader"]["hgtg"] == 42


def test_sample_file():
    """Be sure the sample file matches the actual defaults."""
    config = tomllib.loads(Path("config.toml").read_text())
    assert config == common.DEFAULTS

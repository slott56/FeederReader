"""
Common functions and classes used throughout Feeder Reader.
"""
from pathlib import Path
import tomllib
from typing import Any

DEFAULT_CLEANER_CONFIG = {"days_ago": 90}

DEFAULT_READER_CONFIG = {
    "base_directory": "data",
    "feeds": [
        "https://ecf.dcd.uscourts.gov/cgi-bin/rss_outside.pl",
        "https://ecf.nyed.uscourts.gov/cgi-bin/readyDockets.pl",
        ## "https://ecf.cacd.uscourts.gov/cgi-bin/rss_outside.pl",
        ## "https://ecf.nysd.uscourts.gov/cgi-bin/rss_outside.pl",
    ],
}

DEFAULT_FILTER_CONFIG = {"dockets": ["2:23-cv-04570-HG"]}

DEFAULT_WRITER_CONFIG = {
    "format": "html",  # Or md or csv
    "page_size": 20,
    "base_directory": "output",
}

DEFAULT_MONITOR_CONFIG = {
    "every": ["07:00", "20:00"]
}


DEFAULTS = {
    "cleaner": DEFAULT_CLEANER_CONFIG,
    "reader": DEFAULT_READER_CONFIG,
    "filter": DEFAULT_FILTER_CONFIG,
    "writer": DEFAULT_WRITER_CONFIG,
    "monitor": DEFAULT_MONITOR_CONFIG,
}


def get_config(**section: dict[str, Any]) -> dict[str, Any]:
    """Read THE `config.toml` config file, if present.

    Update the DEFAULTS with config file updated with any section-level dictionaries.

    Use a call like this::

        common.get_config(writer = {'format': 'csv'})

    to override the config file with command-line options.
    """

    config_path = Path.cwd() / "config.toml"
    try:
        config_file = tomllib.loads(config_path.read_text())
    except FileNotFoundError:
        config_file = {}
    config = {
        s: DEFAULTS[s] | config_file.get(s, {}) | section.get(s, {}) for s in DEFAULTS
    }
    return config

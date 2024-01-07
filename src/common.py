"""
Common functions and classes used throughout Feeder Reader.
"""
import os
from pathlib import Path
import tomllib
from typing import Any

DEFAULT_CLEANER_CONFIG: dict[str, Any] = {"days_ago": 90}

DEFAULT_READER_CONFIG: dict[str, Any] = {
    "base_directory": "data",
    "feeds": [
        "https://ecf.dcd.uscourts.gov/cgi-bin/rss_outside.pl",
        "https://ecf.nyed.uscourts.gov/cgi-bin/readyDockets.pl",
        ## "https://ecf.cacd.uscourts.gov/cgi-bin/rss_outside.pl",
        ## "https://ecf.nysd.uscourts.gov/cgi-bin/rss_outside.pl",
    ],
}

DEFAULT_FILTER_CONFIG: dict[str, Any] = {"dockets": ["2:23-cv-04570-HG"]}

DEFAULT_NOTIFIER_CONFIG: dict[str, Any] = {
    "smtp": {
        # "host": "smtp.your host",
        # "port": 587,
        # "admin": "admin@domain.smtp.your host",
        # "password": "admin password",
        # "send_to": "slott56@gmail.com",
    }
}

DEFAULT_WRITER_CONFIG: dict[str, Any] = {
    "format": "html",  # Or md or csv
    "page_size": 20,
    "base_directory": "output",
}

DEFAULT_MONITOR_CONFIG: dict[str, Any] = {
    "every": ["07:00", "20:00"]
}

DEFAULTS = {
    "cleaner": DEFAULT_CLEANER_CONFIG,
    "reader": DEFAULT_READER_CONFIG,
    "filter": DEFAULT_FILTER_CONFIG,
    "notifier": DEFAULT_NOTIFIER_CONFIG,
    "writer": DEFAULT_WRITER_CONFIG,
    "monitor": DEFAULT_MONITOR_CONFIG,
}


def get_config(**section: dict[str, Any]) -> dict[str, Any]:
    """Read a `config.toml` config file, if present
    in the local directory.

    FDRDR

    Here are the tiers of overrides.
    - Any overrides from the ``section`` parameter are seen first. These should come from the command line.
    - The ``~/fdrdr_config.toml``. This usually has a ``[[notifier.smtp]]`` table with user credentials.
    - The ``config.toml`` from the current working directory.
    - The ``DEFAULTS`` in this module.

    Use a call like this to provide overrides from the command line::

        common.get_config(writer = {'format': 'csv'})

    to override the config file with command-line options.
    """
    if 'FDRDR_CREDENTIALS' in os.environ:
        personal_config_path = Path(os.environ['FDRDR_CREDENTIALS']) / "fdrdr_config.toml"
    else:
        personal_config_path = Path.home() / "fdrdr_config.toml"
    try:
        personal_config_file = tomllib.loads(personal_config_path.read_text())
    except FileNotFoundError:
        personal_config_file = {}

    config_path = Path.cwd() / "config.toml"
    try:
        config_file = tomllib.loads(config_path.read_text())
    except FileNotFoundError:
        config_file = {}

    config = {
        s: DEFAULTS[s] |
           config_file.get(s, {}) |
           personal_config_file.get(s, {}) |
           section.get(s, {})
        for s in DEFAULTS
    }
    return config

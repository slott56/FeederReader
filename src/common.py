"""
Common functions and classes used throughout Feeder Reader.

There are three functions in this module to get configuration
information from a variety of places.

..  plantuml::

    @startuml

    class get_class << (F, orchid) Function >>
    class env_table << (F, orchid) Function >>
    class get_config << (F, orchid) Function >>
    object DEFAULTS

    get_config --> env_table
    get_class --> env_table
    get_config --> DEFAULTS

    hide empty members

    @enduml

There's a hierarchy to the configuration data:

-   Environment variables.

    -   All of the ``AWS_`` environment variables

    -   All of the ``LAMBDA_`` environment variables

    -   All of the ``FDRDR_`` environment variables

-   The user's private ``~fdrdr_config.toml``.

-   The local ``config.toml``.

-   The built-in defaults in this module.

See https://docs.aws.amazon.com/lambda/latest/dg/configuration-envvars.html#configuration-envvars-runtime
for standard AWS environment variable names.
"""
from functools import cache
import os
from pathlib import Path
import tomllib
from typing import Any

import notification
import storage

CONFIG: dict[str, dict[type, type]] = {
    "local": {
        notification.Notification: notification.LogNote,
        storage.Storage: storage.LocalFileStorage,
    },
    "AWS": {
        notification.Notification: notification.SESEmail,
        storage.Storage: storage.S3Storage,
    },
}


@cache
def get_class(cls: type) -> type:
    """
    Map a generic class to a specific implementation class, if there are choices.
    This generally applies to :py:class:`storage.Storage` and :py:class:`notification.Notification`.

    The ``CONFIG`` mapping dictinary has environments and class mappings.

    :param cls: An abstract super class with an environment-specific implementation.
    :return: an implementation class, based on the environment.
    """
    aws_config = env_table().get("AWS", {})
    if "LAMBDA_FUNCTION_NAME" in aws_config:
        # At least one AWS label is present: this is a lambda.
        environment = "AWS"
    else:
        # Not a lambda function, could be an EC2 or running locally.
        environment = "local"
    return CONFIG[environment].get(cls, cls)


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
        # Set in ~/fdrdr_config.toml.
        # "host": "smtp.your host",
        # "port": 587,
        # "admin": "admin@domain.smtp.your host",
        # "password": "admin password",
        # "send_to": "slott56@gmail.com",
    },
    "ses": {
        "admin": "admin@domain.smtp.your_host",
        "send_to": "slott56@gmail.com",
    }
}

DEFAULT_WRITER_CONFIG: dict[str, Any] = {
    "format": "html",  # Or md or csv
    "page_size": 20,
    "base_directory": "output",
}

DEFAULT_MONITOR_CONFIG: dict[str, Any] = {"every": ["07:00", "20:00"]}

DEFAULTS = {
    "cleaner": DEFAULT_CLEANER_CONFIG,
    "reader": DEFAULT_READER_CONFIG,
    "filter": DEFAULT_FILTER_CONFIG,
    "notifier": DEFAULT_NOTIFIER_CONFIG,
    "writer": DEFAULT_WRITER_CONFIG,
    "monitor": DEFAULT_MONITOR_CONFIG,
}


@cache
def env_table() -> dict[str, Any]:
    """
    Get environment variables and create TOML-like tables.

    ``AWS_REGION = "us-east-1"`` is treated like the following TOML

    ..  code-block:: toml

        [AWS]
            REGION = "us-east-1"

    The envvar name is decomposed into a table and a name within the table.

    This looks for variable names that begin with ``"AWS_"``, ``"LAMBDA_"``. or ``"FDRDR_"``.
    """
    settings: dict[str, Any] = {}
    for envvar, value in os.environ.items():
        if any(envvar.startswith(s) for s in ("AWS_", "LAMBDA_", "FDRDR_")):
            table, _, name = envvar.partition("_")
            settings.setdefault(table, {})[name] = value
    return settings


def get_config(**section: dict[str, Any]) -> dict[str, Any]:
    """Read the config files, if present and merge in the reults of the :py:func:`env_table` function.

    Here are the tiers of overrides:

    - Any overrides from the ``section`` parameter are seen first. These should come from the command line.

    - The ``~/fdrdr_config.toml``. This usually has a ``[[notifier.smtp]]`` table with user credentials.

    - The ``config.toml`` from the current working directory.

    - The ``DEFAULTS`` in this module.

    Use a call like this to provide overrides from the command line::

        common.get_config(writer = {'format': 'csv'})

    to override the config file with command-line options.

    :param section: A specific table within the TOML file to inject overrides.
    :returns: The complete configuration.
    """

    @cache
    def load(path: Path) -> dict[str, Any]:
        try:
            config = tomllib.loads(path.read_text())
        except FileNotFoundError:
            config = {}
        return config

    if "FDRDR_CREDENTIALS" in os.environ:
        personal_config_path = (
            # if Path(os.environ["FDRDR_CREDENTIALS"]).is_directory()...
            Path(os.environ["FDRDR_CREDENTIALS"]) / "fdrdr_config.toml"
        )
    else:
        personal_config_path = Path.home() / "fdrdr_config.toml"
    personal_config_file = load(personal_config_path)

    config_path = Path.cwd() / "config.toml"
    config_file = load(config_path)

    config = {
        s: DEFAULTS[s]
        | config_file.get(s, {})
        | personal_config_file.get(s, {})
        | section.get(s, {})
        for s in DEFAULTS
    }
    config |= env_table()
    return config

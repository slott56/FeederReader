#######
Operate
#######


There are four separate parts:

-   Cleaning,
-   Reading,
-   Filtering, and
-   Writing.

The cleaner removes cache files older the 90 days.

The reader scans the RSS feeds and updates the cache files with new items.

The filter scans the cache files for specific dockets, and updates a cache of items with those docket numbers.
The filter may invoke notification to send an email.

The writer creates a static HTML web site with indices organized by court, docket, and date.

Configuration
=============

There are two configuration files:

-   The current working directory has a ``config.toml`` with most of the configuration details.

-   The user's home directory has a ``~/fdrdr_config.toml`` with sensitive credential information.

A ``config.toml`` file can look like this:

..  code-block:: toml

    [cleaner]
        days_ago = 90

    [reader]
        base_directory = "data"
        feeds = [
            "https://ecf.dcd.uscourts.gov/cgi-bin/rss_outside.pl",
            "https://ecf.nyed.uscourts.gov/cgi-bin/readyDockets.pl",
            ## "https://ecf.cacd.uscourts.gov/cgi-bin/rss_outside.pl",
            ## "https://ecf.nysd.uscourts.gov/cgi-bin/rss_outside.pl",
        ]

    [filter]
        dockets = ["2:23-cv-04570-HG"]

    [writer]
        format = "html"  # Or md or csv
        page_size = 20
        base_directory = "output"

    [notifier.smtp]
        # details here.

    [monitor]
        every = ["07:00", "20:00"]

The ``data`` and ``output`` directories named in the config
*must* exist before running any of the programs.
The app does *not* create these two top-level directories.

The ``~/fdrdr_config.toml`` file can look like this:

..  code-block:: toml

    [notifier.smtp]
        host = "smtp.your host"
        port = 587
        admin = "admin@domain.smtp.your host"
        password = "admin password"
        send_to = "slott56@gmail.com"

This file has credentials and is -- therefore -- kept away from everything else.

..  important::

    Don't put ``~/fdrdr_config.toml`` file into Git.

It helps to change the mode to make the file only accessible by the owner.

..  code-block:: bash

    chmod 400 ~/fdrdr_config.toml

This reduces the possibility of compromise.

General Monitoring
==================

First, create the required two configuration files.

Open a terminal window to use the command line interface (CLI).

Run the whole show with scheduled times of day to perform the processing steps:

..  code-block:: bash

    % python src/monitor.py

Once this starts, the terminal window can be safely ignored. Don't close it. Just leave it be.

To stop it, use **Control-C** in the terminal window.

Individual Steps
================

Cleaning and Reading is all in one place:

..  code-block:: bash

    % python src/reader.py


Filtering:

..  code-block:: bash

    % python src/filter.py


Writing:

..  code-block:: bash

    % python src/writer.py

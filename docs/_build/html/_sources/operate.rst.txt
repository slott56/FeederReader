#######
Operate
#######

There are four separate parts:

-   **Cleaner**. Removes cache files older the 90 days.
-   **Reader**. Parses the RSS feeds and updates the cache files with new items.
-   **Filter**. Reads the cache files looking for specific dockets, and updates a cache of items with those docket numbers. The filter will also invoke notification to send an email.
-   **Writer**. Creates a static HTML web site with indices organized by court, docket, and date

Currently, this is bundled with all four steps being done together.

It makes sense to decompose this into two kinds of operations:

-   Once Daily: Cleaner-Reader-Filter-Writer.

-   One additional time during the day: Reader.

The RSS feed holds precisely 24 hours of docket items.
Running once each day means that a tiny scheduling offset between AOUSC and FeeaderReader could
miss something. Running the reader step only prevents missing something in the very likely
event of scheduling offsets between the data producer and this consumer.

There are two operating modes: Local and Cloud.

Local Operations
================

There are two parts:

-   `Local Configuration`_

-   `Local Monitor`_

First, create the required two configuration files.

Then, with a terminal window, run the monitor.

Local Configuration
-------------------

Local operations uses two separate configuration files:

-   The current working directory has a ``config.toml`` with most of the configuration details.

-   The user's home directory has a ``~/fdrdr_config.toml`` with sensitive credential information.

A ``config.toml`` file can look like this:


..  include:: ../config.toml
    :code: toml

The ``[reader]`` and ``[writer]`` tables have ``base_directory`` values.
These are file system paths. In the example, it uses
The ``data`` and ``output`` local directories.
These *must* exist before running any of the programs.
The app does *not* create the top-level directories.

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

Local Monitor
-------------

Open a terminal window to use the command line interface (CLI).

Run the whole show with scheduled times of day to perform the processing steps:

..  code-block:: bash

    % python src/monitor.py

Once this starts, the terminal window can be safely ignored. Don't close it. Just leave it be.

To stop it, use **Control-C** in the terminal window.

Cloud Operation
===============

This section is **TBD**.

To run this in AWS, the cloud resources need to be allocated.

-   Create the S3 Bucket used for storage. (Elastic FileSystem is another possibility here.)

    See https://docs.aws.amazon.com/AmazonS3/latest/userguide/create-bucket-overview.html

    See https://docs.aws.amazon.com/AmazonS3/latest/userguide/security.html

-   Make sure an Email address has been verified for sending email by SES.

    See https://docs.aws.amazon.com/ses/latest/dg/send-email.html

-   Create the Lambda, providing the necessary ARN's as configuration parameters as environment variables.

    See https://docs.aws.amazon.com/lambda/latest/dg/lambda-deploy-functions.html

    See https://docs.aws.amazon.com/lambda/latest/dg/lambda-python.html

-   Create the Lambda schedule using EventBridge.

    See https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-run-lambda-schedule.html

Monitoring
----------

See https://docs.aws.amazon.com/lambda/latest/dg/lambda-monitoring.html

See https://docs.aws.amazon.com/AmazonS3/latest/userguide/monitoring-overview.html

See https://docs.aws.amazon.com/ses/latest/dg/monitor-sending-activity.html

Some additional considerations:

-   Lambda execution produces a log. The logs are available in CloudWatch.

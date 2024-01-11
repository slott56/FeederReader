###########
Components
###########

We have the following software architecture.

..  plantuml::

    @startuml

    package feederreader {
        component model.py
        component common.py
        component storage.py
        component notification.py
        component reader.py
        component filter.py
        component writer.py
        component monitor.py
        component handler.py
    }

    handler.py --> reader.py
    handler.py --> filter.py
    handler.py --> writer.py

    monitor.py --> reader.py
    monitor.py --> filter.py
    monitor.py --> writer.py

    filter.py --> notification.py

    reader.py --> model.py
    filter.py --> model.py
    writer.py --> model.py

    reader.py --> storage.py
    filter.py --> storage.py
    writer.py --> storage.py

    notification.py --> common.py
    storage.py --> common.py
    reader.py --> common.py
    filter.py --> common.py
    writer.py --> common.py

    @enduml

Note the four tiers:

-   **Control**. At the top are monitor (to run locally) and handler (to run as an AWS lambda.)

-   **Application**. The top-tier relies on the applications: reader, writer, filter.
    The application modules are also stand-alone applications and can be executed
    individually from the command line.

-   **Storage and Notification**. The application modules rely on storage and notification: model, storage, notification.

-   **Infrastructure**. All of the commonments rely on the common module which provides configuration details.

These rest on a number of dependencies, listed in the ``requirements.in``.

-  pydantic. Used to define the model class in :py:mod:`model`.

-  requests. Used to capture RSS feed in :py:mod:`reader`.

-  jinja2. Used to create HTML documents in :py:mod:`writer` and :py:mod:`notification`.

-  schedule. Used by the :py:mod:`monitor` to control a recurring task.

-  boto3 and botocore. Used to manage AWS resources in :py:mod:`storage` and :py:mod:`notification`.

We'll look at each componment in a little more detail.

Monitor
=======

The monitor executes the feeder reader using its own internal scheduler.
This is used when running locally.

..  plantuml::

    @startuml

    start

    :read config
    build schedule;

    repeat :at scheduled time;

        partition Feeder_Reader {
            :cleaner;
            :reader;
            :filter;
            :writer;
        }

    repeatwhile (forever)

    @enduml

To change the schedule, use **control-c** to crash the application.
It consumes very few resources, and can be left running in a terminal window.
It can be started or stopped as needed.

Handler
=======

The handler is used to execute the feeder reader when it's deployed as as AWS lambda.
The AWS lambda is triggered by a lambda scheduler to periodically perform the various
tasks.

This is used when running locally.

..  plantuml::

    @startuml

    start

    repeat :at scheduled time;

        partition Feeder_Reader {
            :cleaner;
            :reader;
            :filter;
            :writer;
        }

    repeatwhile (forever)

    @enduml

To change the schedule, an AWS console is used.
A Cloud Formation Template (CLT) can define the resources and the schedule.

Reader
======

The reader consumes data from USCourts RSS feeds and captures it locally.


..  plantuml::

    @startuml

    component reader
    component storage

    cloud AOUSC {
        file RSS
        file r2 as "RSS"
    }

    database data {
        folder YYYYMMDD {
            folder HH {
                file items.json
            }
        }
    }

    AOUSC <--- reader : "query"
    reader --> storage
    storage --> items.json : "capture"

    @enduml

The ``storage`` module will either use an AWS S3 bucket or it will
use local file storage.

Here's a more detailed view of the processing.

..  plantuml::

    @startuml

    start

    partition cleaner {
    :read config;

    :clean old files;
    }

    partition reader {

    :read config;

    repeat :for each feed;

        :consume the XML source;

        repeat :for each item;

            :build USCourtItemDetail object;

            if (unique) then (unique)
                :Append to history file;
            endif

        repeat while (more items)

    repeat while (more feeds)
    }

    stop

    @enduml

The resulting files have the following structure:

..  plantuml::

    @startuml

    folder data {
        folder YYYYMMDD {
            folder HH {
                file items.json
            }
            folder hh2 as "HH" {
                file i2 as "items.json"
            }
            folder hh3 as "HH" {
                file i3 as "items.json"
            }
        }

        folder yyyymmdd2 as "YYYYMMDD"
        folder yyyymmdd3 as "YYYYMMDD"

        file filter.json
    }

    @enduml

The files are decomposed by day to make it easy to clean up old files.
Within a day, they're decomposed by hour to make the files small and fast to process.

Within a JSON file (either an ``items.json`` or ``filter.json``) the structure saved
is a sequence of ``USCourtItemDetail`` instances. See `Model`_ for more on this data structure.

Filter
======

The filter examines the captured JSON files, examining all of the  ``USCourtItemDetail``
instances. The that match the docket information are written to a
separate file, ``filter.json``.

..  plantuml::

    @startuml

    component filter
    component storage

    database data {
        folder YYYYMMDD {
            folder HH {
                file items.json
            }
        }
        file filter.json
    }

    filter <-- storage
    storage <-- items.json : "read"
    filter --> storage
    storage --> filter.json : "write"

    @enduml

Any changes to the filter file are important.
A notification strategy is provided in the :py:mod:`notification` module.

Within these JSON files (either ``history.json`` or ``filter.json``) the structure saved
is a sequence of ``USCourtItemDetail`` instances. See `Model`_ for more on this data structure.

Writer
======

The writer builds a web site from the captured files.


..  plantuml::

    @startuml

    component writer
    component storage

    database data {
        folder YYYYMMDD {
            folder HH {
                file items.json
            }
        }
    }

    database output {
        folder court {
            file ci as "index.html"
        }
        folder docket {
            file di as "index.html"
        }
        folder date {
            file dti as "index.html"
        }
        folder filter {
            file fi as "index.html"
        }
        file index.html
    }

    items.json ---> storage  : "read"
    storage --> writer
    writer --> storage
    storage --> output : "write"

    @enduml

The source JSON files (either ``history.json`` or ``filter.json``) the structure saved
is a sequence of ``USCourtItemDetail`` instances. See `Model`_ for more on this data structure.

The output files are created with Jinja templates. See `Jinja Templates`_ for more information.

Notification
============

Choices involve

    -   SMTP on a local computer.

    -   SES when deployed in an AWS lambda.

    -   A fancy Text User Interface (TUI) application to show status and notifications.

Other choices include a simple log file or using AWS SNS for notifications.

..  plantuml::

    @startuml

    component notification
    component common

    notification --> common  : "get configuration"

    cloud {
        component SES
    }

    () smtp

    notification --> SES : "Lambda"
    notification --> smtp : "Local"
    SES --> smtp

    @enduml

The decision of which notification to use is a feature of the ``common`` module.

The output files are created with Jinja templates. See `Jinja Templates`_ for more information.

Model
=====

The model classes are built using **Pydantic**. This does data validation,
and also handles serialization to and from JSON format.

The ``USCourtItemDetail`` class is defined as follows:

..  note:

    Check the source directory to be sure the line numbers are correct.

..  include:: ../src/model.py
    :start-line: 4
    :end-line: 55

Common
======

The common module gathers configuration data.

..  plantuml::

    @startuml

    component common

    file config.toml

    file fdrdr_config.toml
    note bottom of fdrdr_config.toml
        Kept outside Git repository.
        Usually the user's home directory.
    end note

    node host {
        rectangle "environment variables" as envvar
    }
    note bottom of envvar
        Kept outside Git repository.
        Usually part of Cloud Formation Template.
    end note

    common --> envvar
    common --> config.toml
    common --> fdrdr_config.toml

    @enduml

Generally, a lambda deployment relies on environment variables that are part of the lambda configuration.

When running locally, the configuration file is split to keep private information
in a separate file that's not easily put into a Git repository.

Jinja Templates
===============

Jinja templates are fairly complex pieces of functionality used in two places.

HTML pages have a fair amount of boilerplate. Jinja faciltates this by permitting
a sophisticated inheritance hierarchy among pages.

..  plantuml::

    @startuml

    package jinja {
        class Environment
        class DictLoader
        Environment *-- DictLoader
    }

    package notification as "notification.py" {
        class HTML_BASE <<Template>>  {
            head: block
            title: block
            content: block
            render(index_name, items)
        }

        class HTML_MESSAGE <<Template>> {
        }
        HTML_BASE <|-- HTML_MESSAGE
    }

    DictLoader *-- HTML_MESSAGE
    DictLoader *-- HTML_BASE

    notification --> Environment

    hide <<Template>> circle

    @enduml

The diagram for the relationships in :py:mod:`writer` is similar to
the one shown above for :py:mod:`notification`.
It involves more than a single ``HTML_MESSAGE`` extension to ``HTML_BASE``.

..  plantuml::

    @startuml

    package writer as "writer.py" {
        class HTML_BASE <<Template>>  {
            head: block
            title: block
            content: block
            render(index_name, items)
        }

        class HTML_INDEX <<Template>>
        HTML_BASE <|-- HTML_INDEX

        class HTML_SUBJECT_INDEX <<Template>>
        HTML_BASE <|-- HTML_SUBJECT_INDEX

        class HTML_SUBJECT_PAGE <<Template>>
        HTML_BASE <|-- HTML_SUBJECT_PAGE

        HTML_INDEX *-- HTML_SUBJECT_INDEX
        HTML_SUBJECT_INDEX *-- HTML_SUBJECT_PAGE
    }

    hide <<Template>> circle

    @enduml

The overall ``index.html`` page is generated by the ``HTML_INDEX`` template.
This template includes links to the other subject index pages.
Each of the subject areas -- court, docket, date, filtered -- has a
directory with an index page and a number of subject pages.
The ``court/index.html`` has the list of index pages, created by the ``HTML_SUBJECT_INDEX`` template.
Each of the ``court/index_xx.html`` pages is created by the ``HTML_SUBJECT_PAGE`` template,
and contains one page of items.

Template expansion works by "evaluating" a page template.
Each page template extends the base template, which provides a consistent set of content.
The base template includes blocks that are replaced by content
defined in the extension templates.

The template language includes ``for`` commands, allowing
template and content to be repeated for each item in a collection.
Additionally, "macro" definitions allow for pieces of template content
to be injected consistently in multiple places within a page.

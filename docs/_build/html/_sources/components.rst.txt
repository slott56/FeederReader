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
    }

    monitor.py --> reader.py
    monitor.py --> filter.py
    monitor.py --> writer.py

    filter.py --> notification.py

    reader.py --> model.py
    filter.py --> model.py
    writer.py --> model.py

    reader.py --> common.py
    filter.py --> common.py
    writer.py --> common.py

    reader.py --> storage.py
    filter.py --> storage.py
    writer.py --> storage.py

    @enduml

Some of these modules are stand-alone applications.

-   Monitor

-   Reader

-   Filter

-   Writer

We'll look at each in a little more detail.

Monitor
=======

The monitor executes the feeder reader using its own internal scheduler.

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

Reader
======

The reader consumes data from USCourts RSS feeds and captures it locally.


..  plantuml::

    @startuml

    component reader

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

    AOUSC ---> reader : "query"
    reader --> items.json : "capture"

    @enduml

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

Within a JSON file (either an ``items.json`` or ``filter.json``) the structure is
as follows

..  plantuml::

    @startuml

    class USCourtItemDetail {
        item: USCourtItem
        channel: Channel
    }

    class Item {
        title: str
        link: URL
        description: str
        pub_date: datetime

        {static} from_tag(xml)
    }

    class USCourtItem {
        docket: str
        parties: str

        {static} from_tag(xml)
    }

    Item <|-- USCourtItem

    class Channel {
        title: str
        link: URL

        {static} from_tag(xml)
    }

    USCourtItemDetail::item --> USCourtItem

    USCourtItemDetail::channel --> Channel

    @enduml

Filter
======

The filter examines the captured JSON files, examining all of the  ``USCourtItemDetail``
instances. The that match the docket information are written to a
separate file, ``filter.json``.

..  plantuml::

    @startuml

    component filter

    database data {
        folder YYYYMMDD {
            folder HH {
                file items.json
            }
        }
        file filter.json
    }

    filter <-- items.json : "read"
    filter --> filter.json : "write"

    @enduml

Any changes to the filter file are important.
A notification strategy is provided in the :py:mod:`notification` module.

Writer
======

The writer builds a web site from the captured files.


..  plantuml::

    @startuml

    component writer

    database data {
        folder YYYYMMDD {
            folder HH {
                file items.json
            }
        }
        file filter.json
    }

    folder output {
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

    items.json ---> writer : "read"
    writer --> output : "write"

    @enduml

Notification
============

Choices involve

    -   SMTP from a local computer

    -   SNS when deployed in an AWS lambda

    -   A fancy Text User Interface (TUI) application to show status and notifications

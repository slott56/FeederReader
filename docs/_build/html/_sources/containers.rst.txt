##########
Containers
##########

There are two implementation options.

1. On a local host, i.e., a PC.

2. On a cloud computer as a serverless lambda.

Local Host
==========

On a local host, i.e, a PC, the configuration looks like this:

..  plantuml::

    @startuml

    node local {
        component python
        component feederreader
        python --> feederreader
        database history
        folder "web pages" as html
        component browser
    }
    node AOUSC {
        file RSS
    }
    () email

    feederreader <-- RSS
    feederreader <--> history
    feederreader --> email
    feederreader --> html

    actor Journalist

    Journalist <-- email
    browser <-- html
    Journalist -- browser

    @enduml

This requires either manually running the application periodically,
or configuring a scheduler to run the app periodically.

If the computer is on and connected, this
can work out nicely.

The https://schedule.readthedocs.io/en/stable/index.html
package provides a high-level scheduler
that can be started and left running.


Cloud
=====

When using a cloud implementation, the configuration looks like this:


..  plantuml::

    @startuml

    node PC {
        component browser
    }

    node lambda {
        component python
        component feederreader
        python --> feederreader
    }

    node S3 {
        database history
        folder "web pages" as html
    }

    node AOUSC {
        file RSS
    }

    node SNS {
        () email
    }

    feederreader <-- RSS
    feederreader <--> history
    feederreader --> email
    feederreader --> html

    actor Journalist

    Journalist <-- email
    browser <-- html
    Journalist -- browser

    @enduml

This requires a Cloud Formation Template to build
the Lambda and SNS, and bind the SNS to an email output.

Summary
=======

Note that the components are the same.
The host processing each component is distinct.

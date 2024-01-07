#######
Context
#######

There are several asynchronous parts to the processing.

..  plantuml::

    @startuml
    left to right direction

    actor Journalist
    actor AOUSC
    actor FeederReader as fr

    cloud Pacer {
        (RSS upload) as upload
        (RSS reader-filter-writer) as rfw
        (Notification) as note
        (HTML Pages) as web
    }

    AOUSC --> upload
    fr --> rfw
    fr --> note
    Journalist --> note
    Journalist --> web
    @enduml

AOUSC is the Admin Office of the US Courts. They provide the RSS feed.

The sequence has the following outline.

1.  AOUSC posts the RSS feed periodically. This has (exactly) the prior 24 hours of activity.

2.  The FeederReader has several applications to do the following:

    -   Read and save the RSS,
    -   Filter the saved RSS looking for dockets of interest,
    -   Write several index pages with the details.

3.  The Journalist can be notified of an interesting case, and browse the index to see
    the cases organized by Docket.

This lets a Journalist avoid the need to examine the RSS feed daily for dockets of interest.

####
Code
####


Infrastructure
==============

The overall configuration and infrastructure is implemented by the `Common` module.

Common
-------

..  automodule:: common
   :members:
   :undoc-members:


Storage and Notification
=========================

The structure of RSS entries is defined by the `Model`_ module.

Storage has a number of implementations in the `Storage`_ module.

Messaging, also, has a number of implementations in the `Notification`_ module.

Model
-------

..  automodule:: model
   :members:
   :undoc-members:

Storage
--------

..  automodule:: storage
    :members:
    :undoc-members:

Notification
------------

..  automodule:: notification
    :members:
    :undoc-members:

Applications
============

There are three top-level applications.

The `Reader`_ application parses the RSS feed and saves history.
This application includes a Cleaner function to erase old objects from history.

The `Filter`_ application examines the history for any of the interesting dockets.
These are used for notification.

The `Writer`_ application converts the history into HTML pages.
When an S3 bucket is used, these can be read with a browser.


Reader
------

..  automodule:: reader
   :members:
   :undoc-members:

Filter
------

..  automodule:: filter
   :members:
   :undoc-members:

Writer
------

..  automodule:: writer
   :members:
   :undoc-members:

Control
========

There are two overall control implementations.

-   Local running is implemented via the :py:mod:`monitor` module.

-   Lambda execution remains TBD. A :py:mod:`handler` module is planned.

Monitor
-------

..  automodule:: monitor
   :members:
   :undoc-members:

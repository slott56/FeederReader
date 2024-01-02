###########
Components
###########

We have the following software architecture.

..  plantuml::

    @startuml

    package feederreader {
        component model.py
        component reader.py
        component filter.py
        component writer.py
        component monitor.py
        component common.py
    }

    monitor.py --> reader.py
    monitor.py --> filter.py
    monitor.py --> writer.py

    reader.py --> model.py
    filter.py --> model.py
    writer.py --> model.py

    reader.py --> common.py
    filter.py --> common.py
    writer.py --> common.py

    @enduml

Some of these modules are stand-alone applications.


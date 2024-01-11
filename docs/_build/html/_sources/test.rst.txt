####################
Test and Development
####################

For testing and development, additional installations are required.
Testing needs this:

..  code-block:: bash

    python -m pip install -r requirements-test.txt

Development needs even more:

..  code-block:: bash

    python -m pip install -r requirements-dev.txt

Development includes producing documentation, which relies
on PlantUML.

See https://plantuml.com/starting

Testing
=======

Testing uses **tox**. Here's the command

..  code-block:: bash

    tox

That's it. It will build it's own virtual environment
based on ``requirements.txt`` and then execute the test commands.

Documentation
=============

Documentation is built by **Sphinx**. Here are the commands:

..  code-block:: bash

    cd docs
    make html

It's often helpful to run this **without** making a change to the
command-line environment.

..  code-block:: bash

    (cd docs; make html)


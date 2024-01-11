#######
Install
#######

This is not in PyPI and **cannot** be installed with PIP.

The installation requires **git**. For building a Python environment, we suggest **conda**.

Download and install GIT: https://git-scm.com/book/en/v2/Getting-Started-Installing-Git

Download and install mini-conda: https://docs.conda.io/projects/miniconda/en/latest/miniconda-install.html

1.  Use **git** to clone the repository.

    ..  code-block:: bash

        git clone https://github.com/slott56/FeederReader.git

2.  Use **conda** to install Python 3.12. (There are many other ways to install Python. This seems simplest.)

    ..  code-block:: bash

        conda --create=fdrdr python=3.12 --channel=conda-forge
        conda activate fdrdr

3.  Use **PIP** to install the dependencies.

    ..  code-block:: bash

        python -m pip install -r requirements.txt

At this point, the Feeder Reader is ready for operating locally, installing in the cloud,
or doing testing and development.

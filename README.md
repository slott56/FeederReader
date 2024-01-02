
# RSS Feeder/Reader

This monitors and filters RSS feeds.

The focus is on AOUSC -- it specifically parses the title attribute of each `<item>` to extract a Docket Number.

# Installation

Python >= 3.11 is required. 

Creating a virtual environment is strongly suggested.

Install Miniconda as one way to handle the install and environment management.
Tools like hatch and poetry also work well.

```bash
conda create --name feederreader python==3.11 
conda activate feederreader
python -m pip install -r requirements.txt
```

# Test

Testing uses ``tox``

```bash
tox
```

# Operation

There are four separate parts:

-   Cleaning,
-   Reading,
-   Filtering, and
-   Writing.

The cleaner removes cache files older the 90 days.

The reader scans the RSS feeds and updates the cache files with new items.

The filter scans the cache files for specific dockets, and updates a cache of items with those docket numbers.

The writer creates a static HTML web site with indices organized by court, docket, and date.

A `config.toml` file has the congiguation

```toml
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
    dockets = ["16-cv-07161", "16-cv-01557", "18-cv-00979", "17-cv-06331-ARR-CLP"]

[writer]
    format = "html"  # Or md or csv
    page_size = 20
    base_directory = "output"
```

The `data` and `output` directories *must* exist before running any of the programs.
The app does *not* create these two top-level directories.

Cleaning and Reading is all in one place:

```bash
python src/reader.py
```

Filtering:

```bash
python src/filter.py
```

Writing:

```bash
python src/filter.py
```

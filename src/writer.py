"""Writer application of the Feeder Reader.

..  plantuml::

    @startuml
    class load_indices << (F, orchid) Function >>
    class write_csv << (F, orchid) Function >>
    class paginate_keys << (F, orchid) Function >>
    class write_template << (F, orchid) Function >>
    class writer << (F, orchid) Function >>

    component storage {
        class Storage
    }
    component common {
        class get_config << (F, orchid) Function >>
    }
    component jinja {
        class Environment
        class Template
    }

    load_indices --> Storage : "reads"


    @enduml



The :py:func:`writer` uses :py:mod:`common` to get the target output format.

This reads *all* the unique items from the data cache, organizes them, and then
emits all of them using the selected template.

It also looks for a ``filter.json`` with the dockets considered interesting by the filter.
"""
from collections import defaultdict
import csv
import logging
from pathlib import Path
import sys
from typing import TypeAlias, Any, cast

from jinja2 import Environment, DictLoader

import common
from model import USCourtItemDetail
from storage import Storage

MD_COURT_INDEX = """\
# Court
{% for pg in range(1, page_limit+1) %}
Page [{{ pg }}](court/index_{{ pg }}.md)
{% endfor %}
"""

MD_COURT_PAGE = """\
# Court   page {{ page }}
{% for ct in items | sort %}
{{ ct }} {{ items[c] | length }}
{% endfor %}
"""

MD_DOCKET_INDEX = """\
# Docket
{% for pg in range(1, page_limit+1) %}
Page [{{ pg }}](docket/index_{{ pg }}.md)
{% endfor %}
"""

MD_DOCKET_PAGE = """\
# Docket   page {{ page }}
{% for d in items | sort %}
{{d}}
{% for item in items[d] %}
-  {{item.item.title}}: {{item.item.pub_date.ctime()}} [link]({{item.item.link}}) {{item.item.description}}
{% endfor %}
{% endfor %}
"""

MD_DATE_INDEX = """\
# Date
{% for pg in range(1, page_limit+1) %}
Page [{{ pg }}](date/index_{{ pg }}.md)
{% endfor %}
"""

MD_DATE_PAGE = """\
# Date   page {{ page }}
{% for dt in items | sort %}
{{ dt }} {{ items[dt] | length }}
{% endfor %}
"""

HTML_BASE = """\
{% macro detail(item) -%}
{{item.item.title}}: {{item.item.pub_date.ctime()}} <a href="{{item.item.link}}">link</a> {{item.item.description}}
{%- endmacro %}
{% macro nav(prev_pg, next_pg) -%}
<p>{% if prev_pg %}<a class="button" href="index_{{prev_pg}}.html">Page {{prev_pg}}</a> {% endif %}<a class="button" href="index.html">Index</a>{% if next_pg %} <a class="button" href="index_{{next_pg}}.html">Page {{next_pg}}</a> {% endif %}</p>
{%- endmacro %}
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="https://cdn.simplecss.org/simple.min.css">
    {% block head -%}
    <title>{% block title %}{% endblock %}</title>
    {# CSS #}
    {%- endblock %}
</head>
<body>
    <header>
    {% block heading %}<h1>{{ self.title() }}</h1>{% endblock %}
    </header>
    <main>
    {% block content %}
    {% endblock %}
    </main>
</body>
</html>
"""

HTML_INDEX = """\
{% extends "base.html" %}
{% block title %}US Courts RSS Index{% endblock %}
{% block content %}
<p>
<a href="court/index.html">Court</a>
</p>
<p>
<a href="docket/index.html">Docket</a>
</p>
<p>
<a href="date/index.html">Date</a>
</p>
<p>
<a href="filtered/index.html">Filtered by Docket</a>
</p>
{% endblock %}
"""

HTML_SUBJECT_INDEX = """\
{% extends "base.html" %}
{% block title %}{{ index_name | title }} Index{% endblock %}
{% block content %}
<p><a class="button" href="..">Main Index</a></p>
<ul>
{% for pg in range(1, page_limit+1) %}
<li><p>{{ index_name | title }} <a href="index_{{ pg }}.html">Page {{ pg }}</a></p>
{% endfor %}
</ul>
<p><a class="button" href="..">Main Index</a></p>
{% endblock %}
"""

HTML_SUBJECT_PAGE = """\
{% extends "base.html" %}
{% block title %}{{ index_name | title }} Page {{page}}{% endblock %}
{% block content %}
{{ nav(prev_pg, next_pg) }}
{% for ct in items | sort %}
<section>
<h2>{{ ct }} ({{ items[ct] | length }} items)</h2>
<ul>
{% for item in items[ct] %}
<li>{{ detail(item) }}</li>
{% endfor %}
</ul>
</section>
{% endfor %}
{{ nav(prev_pg, next_pg) }}
{% endblock %}
"""


DetailMap: TypeAlias = dict[str, list[USCourtItemDetail]]


def load_indices(storage: Storage) -> dict[str, DetailMap]:
    """
    Reads all of the data files to organize items by court, docket, date, as well
    those found by the :py:mod:`filter` application.

Here's the transformation done by the :py:func:`load_indices` function.

    ..  plantuml::

        @startuml

        object YYYYMMDD
        object HH
        object "items.json" as data

        YYYYMMDD *-- HH
        HH *-- data
        data *-- USCourtItemDetail

        class USCourtItemDetail {
            court
            docket
            pub_date
        }

        object court
        court o-- USCourtItemDetail : list

        object docket
        docket o-- USCourtItemDetail : list

        object date
        date o-- USCourtItemDetail : list

        object filtered
        filtered o-- USCourtItemDetail : list

        map "**indices**" as indices {
        court *--> court
        docket *---> docket
        date *----> date
        filtered *-----> filtered
        }

        data =[thickness=4]=> indices : "transformed by load_indices()"

        @enduml

    :param storage: Storage for all items.
    :return: a dictionary with a collection of mappings used to organize the presentation.
    """
    court: defaultdict[str, list[USCourtItemDetail]] = defaultdict(list)
    docket: defaultdict[str, list[USCourtItemDetail]] = defaultdict(list)
    date: defaultdict[str, list[USCourtItemDetail]] = defaultdict(list)
    filtered: defaultdict[str, list[USCourtItemDetail]] = defaultdict(list)

    for path in storage.listdir(("*", "*", "items.json")):
        for item in cast(
            list[USCourtItemDetail], storage.read_json(path, USCourtItemDetail)
        ):
            court[item.channel.title].append(item)
            docket[item.item.docket or "Unknown"].append(item)
            date[item.item.pub_date.date().strftime("%Y-%b-%d")].append(item)

    if storage.exists("filter.json"):
        for item in cast(
            list[USCourtItemDetail], storage.read_json("filter.json", USCourtItemDetail)
        ):
            filtered[item.item.docket or "Unknown"].append(item)

    return {
        "court": court,
        "docket": docket,
        "date": date,
        "filtered": filtered,
    }


def write_csv(indices: dict[str, DetailMap]) -> None:
    """
    Writes a CSV-formatted extract of the "court" index.
    This is written to standard output.

    :param indices: Indices mapping created by :py:func:`load_indices`
    """
    court = indices["court"]
    rows = (
        [
            item.channel.title,
            item.item.docket,
            item.item.pub_date.ctime(),
            item.item.title,
            item.item.link,
            item.item.description,
        ]
        for ct in court
        for item in sorted(court[ct], key=lambda i: i.item.pub_date)
    )
    writer = csv.writer(sys.stdout)
    writer.writerow(["title", "docket", "pub_date", "title", "link", "description"])
    writer.writerows(rows)


def paginate_keys(keys: list[Any], page_size: int) -> list[tuple[int, tuple[int, int]]]:
    """
    Decomposes the keys in an index into pages. Returns list of page number and start-end values.
    This can be used to group keys into pages.

    :param keys: Keys to an index created by  :py:func:`load_indices`
    :param page_size: Page size.  A value of zero stops pagination and returns a [(1, (0, len))] list
        of page numbers and start values.
    :return: List of tuple[page number, tuple[start, end]] values.
    """
    if page_size != 0:
        start_stop = [
            (start, start + page_size) for start in range(0, len(keys), page_size)
        ]
        return list(enumerate(start_stop, start=1))
    else:
        return [(1, (0, len(keys)))]


def write_template(
    logger: logging.Logger,
    output: Storage,
    format: str,
    page_size: int,
    indices: dict[str, DetailMap],
) -> None:
    """
    Writes the ``index.html``, and ``index_page.html`` files for the expected four keys
    in the output from the :py:func:`load_indices` function.

    :param logger: A place to log interesting info.
    :param output: The Storage to which the files will be written.
    :param format: The format, "html" or "md"
    :param page_size: The page size
    :param indices: The output from the :py:func:`load_indices` function
    :return:
    """
    env = Environment(
        loader=DictLoader(
            {
                "court/index.md": MD_COURT_INDEX,
                "court/index_.md": MD_COURT_PAGE,
                "docket/index.md": MD_DOCKET_INDEX,
                "docket/index_.md": MD_DOCKET_PAGE,
                "date/index.md": MD_DATE_INDEX,
                "date/index_.md": MD_DATE_PAGE,
                "base.html": HTML_BASE,
                "index.html": HTML_INDEX,
                "court/index.html": HTML_SUBJECT_INDEX,
                "court/index_.html": HTML_SUBJECT_PAGE,
                "docket/index.html": HTML_SUBJECT_INDEX,
                "docket/index_.html": HTML_SUBJECT_PAGE,
                "date/index.html": HTML_SUBJECT_INDEX,
                "date/index_.html": HTML_SUBJECT_PAGE,
                "filtered/index.html": HTML_SUBJECT_INDEX,
                "filtered/index_.html": HTML_SUBJECT_PAGE,
            },
        )
    )

    for page_type in ("court", "docket", "date", "filtered"):
        index_template = env.get_template(f"{page_type}/index.{format}")
        page_template = env.get_template(f"{page_type}/index_.{format}")

        output.make((page_type,), exist_ok=True)

        index_data = indices.get(page_type, {})
        keys = sorted(index_data.keys())

        page_start_end = paginate_keys(keys, page_size)

        text = index_template.render(
            index_name=page_type.title(), page_limit=len(page_start_end)
        )
        logger.info("writing %s", f"{page_type}/index.{format}")
        output.write_text((page_type, f"index.{format}"), text)

        for pg, (start, stop) in page_start_end:
            content = {k: index_data[k] for k in keys[start:stop]}
            prev = None if pg == 1 else pg - 1
            next = None if pg == len(page_start_end) else pg + 1
            text = page_template.render(
                items=content,
                page=pg,
                prev_pg=prev,
                next_pg=next,
                start=start,
                stop=stop,
                index_name=page_type.title(),
            )
            logger.info("writing %s", f"{page_type}/index_{pg}.{format}")
            output.write_text((page_type, f"index_{pg}.{format}"), text)

    main_index_template = env.get_template(f"index.{format}")
    logger.info("writing %s", f"index.{format}")
    text = main_index_template.render()
    output.write_text((f"index.{format}"), text)


def writer() -> None:
    """
    Captures the RSS state as HTML or MD files.
    Uses :py:func:`common.get_config` to get the format, page size, and the Storage class.
    Uses :py:func:`load_indices` to gather the items.
    Uses :py:func:`write_template` to write HTML or MD output.
    Uses :py:func:`write_csv` to write CSV output.
    """
    logger = logging.getLogger("writer")

    config = common.get_config()
    rdr_config = config["reader"]
    wtr_config = config["writer"]

    logger.info("Reading captured items")
    rdr_base = Path.cwd() / rdr_config["base_directory"]
    storage_cls = common.get_class(Storage)
    storage = storage_cls(rdr_base)
    indices = load_indices(storage)
    for k in indices:
        logger.info("%-10s  %5d", k, len(indices[k]))

    logger.info("Writing %s", wtr_config["format"])
    if wtr_config["format"] == "csv":
        write_csv(indices)

    elif wtr_config["format"] in {"html", "md"}:
        wtr_base = Path.cwd() / wtr_config["base_directory"]
        output = storage_cls(wtr_base)

        format = wtr_config["format"]
        page_size = wtr_config["page_size"]
        write_template(logger, output, format, page_size, indices)

    logger.info("Done")


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    writer()

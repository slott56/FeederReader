"""Writer portion of Feeder Reader.

From the ``config.toml``, get a desired output format.

This reads *all* the unique items from the data cache, organizes them, and then
emits all of them using the selected template.

It also looks for a `filter.json` with the dockets considered interesting by the filter.
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
from storage import Storage, LocalFileStorage

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
    logger = logging.getLogger("writer")

    config = common.get_config()
    rdr_config = config["reader"]
    wtr_config = config["writer"]

    logger.info("Reading captured items")
    rdr_base = Path.cwd() / rdr_config["base_directory"]
    storage = LocalFileStorage(rdr_base)
    indices = load_indices(storage)
    for k in indices:
        logger.info("%-10s  %5d", k, len(indices[k]))

    logger.info("Writing %s", wtr_config["format"])
    if wtr_config["format"] == "csv":
        write_csv(indices)

    elif wtr_config["format"] in {"html", "md"}:
        wtr_base = Path.cwd() / wtr_config["base_directory"]
        output = LocalFileStorage(wtr_base)

        format = wtr_config["format"]
        page_size = wtr_config["page_size"]
        write_template(logger, output, format, page_size, indices)

    logger.info("Done")


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    writer()

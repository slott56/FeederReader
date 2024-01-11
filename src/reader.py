"""Reader application of the Feeder Reader.

..  plantuml::

    @startuml
    class feed_iter << (F, orchid) Function >>
    class capture << (F, orchid) Function >>
    class reader << (F, orchid) Function >>
    class cleaner << (F, orchid) Function >>

    component storage {
        class Storage
    }

    reader --> feed_iter : "for each RSS feed"
    reader --> capture

    class XML

    component model {
        class USCourtItemDetail
        class USCourtItem
        class Channel

        Channel *-- "1,m" USCourtItem
        USCourtItem <-- USCourtItemDetail /' --> USCourtItem '/
        Channel <-- USCourtItemDetail     /' --> Channel '/
    }

    XML *-- Channel
    XML *-- USCourtItem
    feed_iter --> XML : "reads"
    feed_iter o--> Channel : "yields"
    feed_iter o--> USCourtItem : "yields"

    capture --> feed_iter : "consumes"
    capture o--> USCourtItemDetail : "creates"
    capture --> Storage : "reads and writes"
    Storage *--> USCourtItemDetail : "contains"

    cleaner --> Storage

    component common {
        class get_config << (F, orchid) Function >>
    }

    reader --> get_config
    cleaner --> get_config

    hide empty members

    @enduml

The :py:func:`reader` uses :py:mod:`common` to get parameters with the list of RSS feeds.
For each feed, it gets the current RSS document, and parses this to extract
the :py:class:`USCourtItemDetail` details.

.. important::

    Feeds have only the previous 24 hours of content.

    This should be run at least once each day, twice to be sure nothing is missed.

..  todo:: This needs to be more cautious about reading from storage.

    We can't reread stored history for every individual item.
"""
from collections import Counter
import datetime
import logging
from pathlib import Path
from typing import cast
from xml.etree import ElementTree

import requests

import common
from model import Channel, USCourtItem, USCourtItemDetail, Feed
from storage import Storage


def feed_iter(document: ElementTree.Element) -> Feed:
    """
    Iterates through the ``<channel><item>...</item></channel>`` structure of the ``<rss>`` tag describing a feed.

    This emits a sequence of :py:class:`model.Channel` and :py:class:`model.USCourtItem` objects from the XML.
    No effort is made to combine the :py:class:`Channel` and :py:class:`USCourtItem` items;
    the data is emitted as a denormalized sequence.

    :param document: the XML source.
    :returns: an iterable of :py:class:`Channel` and :py:class:`USCourtItem`
    """
    for channel in document.iter("channel"):
        yield Channel.from_tag(channel)
        for item in channel.iter("item"):
            yield USCourtItem.from_tag(item)


def capture(storage: Storage, feed: Feed) -> None:
    """
    Save this feed into JSON file in storage ``{item.date}/{item.time.hour}/items.json``.

    This transforms the publication date into ``YYYYMMDD/HH`` path to a file.
    If the file exists, this is added to the content.

    If the file doesn't exist, it's created.

    :param storage: Where to stash history.
    """
    logger = logging.getLogger("reader.capture")
    counts: Counter[str] = Counter()

    for channel_item in feed:
        match channel_item:
            case Channel() as channel:
                pass
            case USCourtItem() as item:
                detail = USCourtItemDetail(item=item, channel=channel)
                path = (
                    f"{detail.item.pub_date.year}{detail.item.pub_date.month:02d}{detail.item.pub_date.day:02d}",
                    f"{detail.item.pub_date.hour:02d}",
                )
                logger.debug(detail.model_dump_json())
                if not storage.exists(path):
                    logger.info("Make %s", path)
                    storage.make(path)
                item_name = path + ("items.json",)
                # TODO: This should be part of local cache, NOT reloaded each time.
                existing_items: list[USCourtItemDetail]
                if storage.exists(item_name):
                    existing_items = cast(
                        list[USCourtItemDetail],
                        storage.read_json(item_name, USCourtItemDetail),
                    )
                else:
                    existing_items = []
                existing_item_set = set(existing_items)
                # add to set of JSON docs to YYYYMMDD/HH/items.nlj if unique
                # TODO: Consider replacing set with a bisect-based algorithm to avoid the sort.
                if detail not in existing_item_set:
                    new_items = sorted(
                        existing_item_set | {detail}, key=lambda d: d.item.pub_date
                    )
                    storage.write_json(item_name, new_items)
                    counts["new"] += 1
                else:
                    counts["duplicate"] += 1
            case _:  # pragma: no cover
                raise ValueError(f"unexected {channel_item!r} in feed")

    logger.info(counts)


def reader() -> None:
    """
    Reads all RSS feeds and saves the items.
    Uses :py:func:`common.get_config` to get the list of feeds and the storage class.
    Uses :py:func:`feed_iter` to parse XML.
    Uses :py:func:`capture` to preserve the :py:class:`model.USCourtItemDetail` items.
    """
    logger = logging.getLogger("reader")

    config = common.get_config()
    rdr_config = config["reader"]

    base = Path.cwd() / rdr_config["base_directory"]
    storage_cls = common.get_class(Storage)
    writer = storage_cls(base)

    for url in rdr_config["feeds"]:
        logger.info("Downloading %s", url)
        response = requests.get(url)
        logger.info("HTTP response %s", response.status_code)
        if response.status_code == 200:
            document = ElementTree.fromstring(response.content)
            capture(writer, feed_iter(document))
    logger.info("Done")


def cleaner() -> None:
    """
    Removes all old files. The configuration file provides the window size.

    Uses :py:func:`common.get_config` to get the list of feeds and the storage class.
    """
    logger = logging.getLogger("cleaner")

    config = common.get_config()
    rdr_config = config["reader"]
    cln_config = config["cleaner"]

    today = datetime.datetime.now(tz=datetime.timezone.utc).date()
    before = today - datetime.timedelta(days=cln_config["days_ago"])

    base = Path.cwd() / rdr_config["base_directory"]
    storage_cls = common.get_class(Storage)
    writer = storage_cls(base)

    logger.info("Removing files from prior to %s", before)

    for date_dir in writer.listdir(("*")):
        logger.debug(date_dir)
        try:
            date = datetime.datetime.strptime(date_dir[-1], "%Y%m%d").date()
            if date < before:
                logger.info("Removing %s", date_dir)
                writer.rmdir(date_dir)
        except ValueError:  # pragma: no cover
            logger.info("Skipping %s", date_dir)
    logger.info("Done")


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    cleaner()
    reader()

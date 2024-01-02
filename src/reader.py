"""Reader portion of the Feeder Reader.

From the ``config.toml``, get a list of feeds.

Get the current RSS document, and parse to extract Channel and Item details.

Note that feeds are updated to have only the previous 24 hours of content.
This should be run at least once each day, twice to be sure nothing is missed.
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
from storage import Storage, LocalFileStorage


def feed_iter(document: ElementTree.Element) -> Feed:
    """Iterate through the <channel><item>...</item></channel> structure of an <rss>.
    This emits a sequence of Channel and USCourtItem objects from the XML.
    """
    for channel in document.iter("channel"):
        yield Channel.from_tag(channel)
        for item in channel.iter("item"):
            yield USCourtItem.from_tag(item)


def capture(writer: Storage, feed: Feed) -> None:
    """
    Save this feed JSON files ``{item.date}/{item.time.hour}/items.json``.

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
                if not writer.exists(path):
                    logger.info("Make %s", path)
                    writer.make(path)
                item_name = path + ("items.json",)
                existing_items: list[USCourtItemDetail]
                if writer.exists(item_name):
                    existing_items = cast(
                        list[USCourtItemDetail],
                        writer.read_json(item_name, USCourtItemDetail),
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
                    writer.write_json(item_name, new_items)
                    counts["new"] += 1
                else:
                    counts["duplicate"] += 1
            case _:  # pragma: no cover
                raise ValueError(f"unexected {channel_item!r} in feed")

    logger.info(counts)


def reader() -> None:
    logger = logging.getLogger("reader")

    config = common.get_config()
    rdr_config = config["reader"]

    base = Path.cwd() / rdr_config["base_directory"]
    writer = LocalFileStorage(base)

    for url in rdr_config["feeds"]:
        logger.info("Downloading %s", url)
        response = requests.get(url)
        logger.info("HTTP response %s", response.status_code)
        if response.status_code == 200:
            document = ElementTree.fromstring(response.content)
            capture(writer, feed_iter(document))
    logger.info("Done")


def cleaner() -> None:
    logger = logging.getLogger("cleaner")

    config = common.get_config()
    rdr_config = config["reader"]
    cln_config = config["cleaner"]

    today = datetime.datetime.now(tz=datetime.timezone.utc).date()
    before = today - datetime.timedelta(days=cln_config["days_ago"])

    base = Path.cwd() / rdr_config["base_directory"]
    writer = LocalFileStorage(base)

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

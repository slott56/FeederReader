"""Filter application of the Feeder Reader.

..  plantuml::

    @startuml
    class match_items << (F, orchid) Function >>
    class filter << (F, orchid) Function >>

    component storage {
        class Storage
    }
    component notification {
        class Notification
    }
    component common {
        class get_config << (F, orchid) Function >>
    }

    match_items --> Storage : "reads"

    filter --> match_items : "consumes"
    filter --> Notification : "notify"
    filter --> Storage : "writes"
    filter --> get_config

    hide empty members

    @enduml


The :py:func:`filter` uses :py:mod:`common` to get the list of interesting docket numbers.

It scans the entire downloaded collection of items looking
for "interesting" docket.
It compares those with the history cache to see if
there have been changes.
When changes are found the cache is updated and notifications are sent.
"""
from collections import Counter
from collections.abc import Iterator
import logging
from pathlib import Path
from typing import cast

import common
from model import USCourtItemDetail
from storage import Storage
from notification import Notification


def match_items(
    storage: Storage,
    path: tuple[str, ...],
    targets: list[str],
    history: set[USCourtItemDetail],
    counts: Counter[str],
) -> Iterator[USCourtItemDetail]:
    """
    Examine all the items in storage, looking for interesting dockets.

    The implementation is a sequence of filters...

    Sadly, we've pre-empted the name ``filter()`` in this module.
    Here's the alternative design.

    ::

        source = cast(list[USCourtItemDetail], storage.read_json(path, USCourtItemDetail))
        has_docket = filter(lambda item: item.item.docket, source)
        has_target = filter(lambda item: any(d in item.item.docket.lower() for d in targets), has_docket)
        novel = filter(lambda item: item not in history, has_target)

    :param storage: The persistent storage from which we can read data.
    :param path: The path in storage to find :py:class:`model.USCourtItemDetail` instances.
    :param targets: The various dockets that are interesting.
    :param history: The previous state of the history, to see if this is new.
    :param coutns: A counter to update when something new is found.
    """
    for item in cast(
        list[USCourtItemDetail], storage.read_json(path, USCourtItemDetail)
    ):
        counts["item"] += 1
        if item.item.docket:
            if any(d in item.item.docket.lower() for d in targets):
                if item not in history:
                    yield item
                    counts["new"] += 1
        else:
            counts["no docket"] += 1


def filter() -> None:
    """
    Reads the RSS data.
    Uses :py:func:`common.get_config` to get the list of dockers, and the storage class,
    and the notifier class.
    Uses :py:func:`match_items` to get items on the interesting dockets.
    Uses the give notifier to notify of changes.
    """
    logger = logging.getLogger("filter")

    config = common.get_config()
    rdr_config = config["reader"]
    ftr_config = config["filter"]
    nfr_config = config["notifier"]

    rdr_base = Path.cwd() / rdr_config["base_directory"]
    storage_cls = common.get_class(Storage)
    storage = storage_cls(rdr_base)

    targets = list(d.lower() for d in ftr_config["dockets"])
    logger.info("Dockets %s", targets)

    counts = Counter({"targets": len(targets)})
    history: set[USCourtItemDetail] = set()
    if storage.exists("filter.json"):
        history = set(
            cast(
                list[USCourtItemDetail],
                storage.read_json("filter.json", USCourtItemDetail),
            )
        )
    start = len(history)
    logger.info("History start %5d", len(history))
    counts["history:start"] = start

    note_class = common.get_class(Notification)
    with note_class(storage, nfr_config) as notifier:
        logger.info("Scanning downloaded items")
        for path in storage.listdir(("*", "*", "items.json")):
            for new_item in match_items(storage, path, targets, history, counts):
                history.add(new_item)
                notifier.notify(new_item)

        logger.info("Saving filter.json")
        history_items = sorted(history, key=lambda d: d.item.pub_date)
        storage.write_json("filter.json", history_items)

    logger.info("History end   %5d", len(history_items))
    counts["history:end"] = len(history)

    logger.info(counts)


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    filter()

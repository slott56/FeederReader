"""Filter portion of Feeder Reader.

From the ``config.toml``, get a list of interesting docket numbers.

This keeps an cache of items that are interesting.

It scanes the entire downloaded collection of items looking
for "interesting" items. It compares those with the cache to see if
there have been changes.

Changes trigger notification -- SMTP email or an SNS.
"""
from collections import Counter
from collections.abc import Iterator
import logging
from pathlib import Path
from typing import cast

import common
from model import USCourtItemDetail
from storage import Storage, LocalFileStorage
from notification import LogNote


def match_items(
    storage: Storage,
    path: tuple[str, ...],
    targets: list[str],
    history: set[USCourtItemDetail],
    counts: Counter[str],
) -> Iterator[USCourtItemDetail]:
    """
    A sequence of filters...

    Sadly, we've pre-empted the name filter() in this module.

    ::

        source = cast(list[USCourtItemDetail], storage.read_json(path, USCourtItemDetail))
        has_docket = filter(lambda item: item.item.docket, source)
        has_target = filter(lambda item: any(d in item.item.docket.lower() for d in targets), has_docket)
        novel = filter(lambda item: item not in history, has_target)
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
    logger = logging.getLogger("filter")

    config = common.get_config()
    rdr_config = config["reader"]
    ftr_config = config["filter"]
    nfr_config = config["notifier"]

    rdr_base = Path.cwd() / rdr_config["base_directory"]
    storage = LocalFileStorage(rdr_base)

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

    with LogNote(storage, nfr_config) as notifier:

        logger.info("Scanning downloaded items")
        for path in storage.listdir(("*", "*", "items.json")):
            for new_item in match_items(storage, path, targets, history, counts):
                history.add(new_item)
                notifier.notify(str(new_item))

        logger.info("Saving filter.json")
        history_items = sorted(history, key=lambda d: d.item.pub_date)
        storage.write_json("filter.json", history_items)

    logger.info("History end   %5d", len(history_items))
    counts["history:end"] = len(history)

    logger.info(counts)


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    filter()

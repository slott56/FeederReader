"""
The top-level Feeder Reader contoller
when run in local model.

This will define and execute a periodic schedule of FeederReader work.

It leverages :py:mod:`reader`, :py:mod:`filter`, and :py:mod:`writer`
to actually do the work.
"""
import logging
import sys
import time
from typing import Any

import schedule
from schedule import ScheduleValueError

import common
import reader
import filter
import writer


def feeder_reader() -> None:
    """
    The FeederReader Processing.

    1. :py:func:`reader.cleaner`

    2. :py:func:`reader.reader`

    3. :py:func:`reader.filter`

    4. :py:func:`writer.writer`
    """
    reader.cleaner()
    reader.reader()
    filter.filter()
    writer.writer()


def sched_builder(logger: logging.Logger, options: dict[str, Any]) -> None:
    """
    Builds the schedule from the configuration options.

    :param logger: A logger to write info
    :param options: The options for the monitor.
    """
    times = options["every"]
    error_count = 0
    for t in times:
        try:
            schedule.every().day.at(t).do(feeder_reader)
        except ScheduleValueError as ex:
            logger.error("invalid %r in %r", t, options)
            logger.error(ex)
            error_count += 1
    if error_count:
        sys.exit("invalid schedule configuration")


def sched_runner() -> None:
    """Run the schedule."""
    try:
        feeder_reader()
        while True:
            time.sleep(60)  #  Every minute, same as cron
            schedule.run_pending()
    except KeyboardInterrupt:
        pass


def main() -> None:
    """
    Main program for the monitor.

    Get the configuration. Build the schedule. Run the schedule.
    """
    logger = logging.getLogger("monitor")

    options = common.get_config()
    sched_builder(logger, options["monitor"])
    logger.info("Schedule: %r", schedule.get_jobs())

    sched_runner()
    logger.info("Schedule stopped.")


if __name__ == "__main__":  # pragma: no cover
    # TODO: Configure logger(s)
    logging.basicConfig(level=logging.INFO)
    main()

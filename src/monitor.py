"""
Define and execute a periodic schedule of FeederReader work.
"""
import logging
import sys
import time

import schedule

import common
import reader
import filter
import writer


def feeder_reader() -> None:
    """The FeederReader Processing."""
    reader.cleaner()
    reader.reader()
    filter.filter()
    writer.writer()


def main() -> None:
    logger = logging.getLogger("monitor")

    options = common.get_config()
    times = options['monitor']['every']
    error_count = 0
    for t in times:
        try:
            schedule.every().day.at(t).do(feeder_reader)
        except schedule.ScheduleValueError as ex:
            logger.error('invalid %r in %r', t, options['monitor'])
            logger.error(ex)
            error_count += 1
    if error_count:
        sys.exit("invalid schedule configuration")
    logger.info("Schedule: %r", schedule.get_jobs())

    try:
        feeder_reader()
        while True:
            time.sleep(60)  #  Every minute, same as cron
            schedule.run_pending()
    except KeyboardInterrupt:
        logger.info("Schedule stopped.")

if __name__ == "__main__":  # pragma: no cover
    # TODO: Configure logger(s)
    logging.basicConfig(level=logging.INFO)
    main()

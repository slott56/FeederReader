"""
Test the monitor module.

Requires --log-format="%(levelname)s:%(name)s:%(message)s"

"""
import logging
from unittest.mock import Mock, call

import pytest
import schedule

import monitor


def test_job_function(monkeypatch):
    mock_reader = Mock()
    mock_filter = Mock()
    mock_writer = Mock()
    monkeypatch.setattr(monitor, "reader", mock_reader)
    monkeypatch.setattr(monitor, "filter", mock_filter)
    monkeypatch.setattr(monitor, "writer", mock_writer)
    monitor.feeder_reader()
    assert mock_reader.cleaner.mock_calls == [call()]
    assert mock_reader.reader.mock_calls == [call()]
    assert mock_filter.filter.mock_calls == [call()]
    assert mock_writer.writer.mock_calls == [call()]


def test_sched_builder(monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    logger = logging.getLogger("monitor")
    mock_schedule = Mock()
    monkeypatch.setattr(monitor, "schedule", mock_schedule)
    monitor.sched_builder(logger, {"every": ["10:00", "22:00"]})
    assert mock_schedule.mock_calls == [
        call.every(),
        call.every().day.at("10:00"),
        call.every().day.at().do(monitor.feeder_reader),
        call.every(),
        call.every().day.at("22:00"),
        call.every().day.at().do(monitor.feeder_reader),
    ]


def test_bad_sched_builder(monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    logger = logging.getLogger("monitor")
    mock_schedule = Mock(wraps=schedule)
    monkeypatch.setattr(monitor, "schedule", mock_schedule)
    with pytest.raises(SystemExit):
        monitor.sched_builder(logger, {"every": ["7:00"]})
    assert mock_schedule.mock_calls == [call.every()]
    assert caplog.text.splitlines() == [
        "ERROR:monitor:invalid '7:00' in {'every': ['7:00']}",
        "ERROR:monitor:Invalid time format for a daily job (valid format is HH:MM(:SS)?)",
    ]


def test_sched_runner(monkeypatch):
    mock_app = Mock(name="feeder_reader")
    mock_time = Mock(name="time")
    monkeypatch.setattr(
        monitor.schedule, "run_pending", Mock(side_effect=KeyboardInterrupt())
    )
    monkeypatch.setattr(monitor, "feeder_reader", mock_app)
    monkeypatch.setattr(monitor, "time", mock_time)
    monitor.sched_runner()
    assert mock_app.mock_calls == [call()]
    assert mock_time.sleep.mock_calls == [call(60)]


def test_monitor_main(monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    mock_builder = Mock()
    mock_runner = Mock()
    monkeypatch.setattr(monitor, "sched_builder", mock_builder)
    monkeypatch.setattr(monitor, "sched_runner", mock_runner)
    monitor.main()
    logger = logging.getLogger("monitor")
    assert mock_builder.mock_calls == [call(logger, {"every": ["07:00", "20:00"]})]
    assert mock_runner.mock_calls == [call()]
    assert caplog.text.splitlines() == [
        "INFO:monitor:Schedule: []",
        "INFO:monitor:Schedule stopped.",
    ]

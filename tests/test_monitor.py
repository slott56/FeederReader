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
    monkeypatch.setattr(monitor, 'reader', mock_reader)
    monkeypatch.setattr(monitor, 'filter', mock_filter)
    monkeypatch.setattr(monitor, 'writer', mock_writer)
    monitor.feeder_reader()
    assert mock_reader.cleaner.mock_calls == [call()]
    assert mock_reader.reader.mock_calls == [call()]
    assert mock_filter.filter.mock_calls == [call()]
    assert mock_writer.writer.mock_calls == [call()]

def test_schedule_runner(monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    mock_app =  Mock(name='feeder_reader')
    mock_sleep = Mock(name='sleep')
    monkeypatch.setattr(monitor, 'common', Mock(get_config=Mock(return_value={'monitor':{'every': ['10:00']}})))
    monkeypatch.setattr(monitor, 'time', Mock(sleep=mock_sleep))
    monkeypatch.setattr(schedule, 'run_pending', Mock(side_effect=KeyboardInterrupt))
    monkeypatch.setattr(monitor, 'feeder_reader', mock_app)
    monitor.main()
    assert mock_app.mock_calls == [call()]
    assert mock_sleep.mock_calls == [call(60)]
    assert caplog.text.splitlines() == [
        f'INFO:monitor:Schedule: [Every 1 day at 10:00:00 do functools.partial({mock_app!r})() (last run: [never], next run: 2024-01-03 10:00:00)]',
        'INFO:monitor:Schedule stopped.',
    ]


def test_bad_schedule_config(monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    mock_app =  Mock(name='feeder_reader')
    mock_sleep = Mock(name='sleep')
    monkeypatch.setattr(monitor, 'common', Mock(get_config=Mock(return_value={'monitor':{'every': ['7:00']}})))
    monkeypatch.setattr(monitor, 'time', Mock(sleep=mock_sleep))
    monkeypatch.setattr(schedule, 'run_pending', Mock(side_effect=KeyboardInterrupt))
    monkeypatch.setattr(monitor, 'feeder_reader', mock_app)
    with pytest.raises(SystemExit):
        monitor.main()
    assert mock_app.mock_calls == []
    assert mock_sleep.mock_calls == []
    assert caplog.text.splitlines() == [
        "ERROR:monitor:invalid '7:00' in {'every': ['7:00']}",
        'ERROR:monitor:Invalid time format for a daily job (valid format is HH:MM(:SS)?)',
    ]

"""
Test the reader module.

Requires --log-format="%(levelname)s:%(name)s:%(message)s"

"""
import datetime
import logging
from pathlib import Path
from textwrap import dedent
from unittest.mock import Mock, call, sentinel
from xml.etree import ElementTree

from pydantic.networks import Url
import pytest

import reader


def test_feed_iter(xml_doc):
    rss = ElementTree.fromstring(xml_doc)
    content = list(reader.feed_iter(rss))
    assert content == [
        reader.Channel(
            title="Eastern District of New York Filings Entries on cases",
            link=Url("https://ecf.nyed.uscourts.gov/"),
            description="Public Filings in the last 24 Hours",
            last_build=datetime.datetime(2023, 12, 28, 21, 20, 1),
        ),
        reader.USCourtItem(
            title="2:23-cv-09491-PKC-ST Sookra v. Berkeley Carroll School et al",
            link=Url("https://ecf.nyed.uscourts.gov/cgi-bin/DktRpt.pl?508001"),
            description="[Quality Control Check - Summons] Sookra v. Berkeley Carroll School et al",
            text_pub_date="Thu, 28 Dec 2023 21:18:55 GMT",
            docket="2:23-cv-09491-PKC-ST",
            parties="Sookra v. Berkeley Carroll School et al",
        ),
        reader.USCourtItem(
            title="2:23-cv-08293-NJC-ST Miller v. Sanofi US Services Inc. et al",
            link=Url("https://ecf.nyed.uscourts.gov/cgi-bin/DktRpt.pl?505703"),
            description="[Order to Show Cause] Miller v. Sanofi US Services Inc. et al",
            text_pub_date="Thu, 28 Dec 2023 21:18:41 GMT",
            docket="2:23-cv-08293-NJC-ST",
            parties="Miller v. Sanofi US Services Inc. et al",
        ),
    ]


@pytest.fixture()
def mock_storage_noprev():
    return Mock(
        exists=Mock(return_value=False),
    )


@pytest.fixture()
def mock_storage_prev():
    return Mock(exists=Mock(return_value=True), read_json=Mock(return_value=[]))


@pytest.fixture()
def mock_storage_prev_dup(mock_item_detail):
    return Mock(
        exists=Mock(return_value=True), read_json=Mock(return_value=[mock_item_detail])
    )


@pytest.fixture()
def mock_url():
    return Mock(host="host", path="path")


def test_capture_new(
    mock_storage_noprev, mock_url, mock_channel, mock_item, mock_item_detail
):
    feed = [mock_channel, mock_item]
    reader.capture(mock_storage_noprev, feed)
    assert mock_storage_noprev.mock_calls == [
        call.exists(("20231229", "21")),
        call.make(("20231229", "21")),
        call.exists(("20231229", "21", "items.json")),
        call.write_json(("20231229", "21", "items.json"), [mock_item_detail]),
    ]


def test_capture_more(
    mock_storage_prev, mock_url, mock_channel, mock_item, mock_item_detail
):
    feed = [mock_channel, mock_item]
    reader.capture(mock_storage_prev, feed)
    assert mock_storage_prev.mock_calls == [
        call.exists(("20231229", "21")),
        call.exists(("20231229", "21", "items.json")),
        call.read_json(("20231229", "21", "items.json"), reader.USCourtItemDetail),
        call.write_json(("20231229", "21", "items.json"), [mock_item_detail]),
    ]


def test_capture_dup(
    mock_storage_prev_dup, mock_url, mock_channel, mock_item, mock_item_detail
):
    feed = [mock_channel, mock_item]
    reader.capture(mock_storage_prev_dup, feed)
    assert mock_storage_prev_dup.mock_calls == [
        call.exists(("20231229", "21")),
        call.exists(("20231229", "21", "items.json")),
        call.read_json(("20231229", "21", "items.json"), reader.USCourtItemDetail),
    ]


@pytest.fixture()
def mock_requests(monkeypatch):
    requests = Mock(
        get=Mock(
            return_value=Mock(
                status_code=200, content='<?xml version="1.0"?><rss></rss>'
            )
        )
    )
    monkeypatch.setattr(reader, "requests", requests)
    return requests


def test_reader(
    monkeypatch, caplog, mock_no_config, mock_storage_noprev, mock_requests
):
    caplog.set_level(logging.INFO)
    monkeypatch.setattr(
        reader, "LocalFileStorage", Mock(return_value=mock_storage_noprev)
    )
    mock_feed_iter = Mock(return_value=sentinel.FEED)
    monkeypatch.setattr(reader, "feed_iter", mock_feed_iter)
    mock_capture = Mock()
    monkeypatch.setattr(reader, "capture", mock_capture)
    reader.reader()
    assert caplog.text.splitlines() == [
        "INFO:reader:Downloading https://ecf.dcd.uscourts.gov/cgi-bin/rss_outside.pl",
        "INFO:reader:HTTP response 200",
        "INFO:reader:Downloading https://ecf.nyed.uscourts.gov/cgi-bin/readyDockets.pl",
        "INFO:reader:HTTP response 200",
        "INFO:reader:Done",
    ]
    assert mock_requests.get.mock_calls == [
        call("https://ecf.dcd.uscourts.gov/cgi-bin/rss_outside.pl"),
        call("https://ecf.nyed.uscourts.gov/cgi-bin/readyDockets.pl"),
    ]
    assert mock_capture.mock_calls == [
        call(mock_storage_noprev, sentinel.FEED),
        call(mock_storage_noprev, sentinel.FEED),
    ]


@pytest.fixture()
def mock_datetime():
    return Mock(
        datetime=Mock(
            now=Mock(return_value=datetime.datetime(2024, 1, 18)),
            strptime=Mock(
                side_effect=[
                    datetime.datetime(2023, 10, 19),
                    datetime.datetime(2024, 1, 18),
                ]
            ),
        ),
        timedelta=Mock(wraps=datetime.timedelta),
    )


@pytest.fixture()
def mock_storage_content():
    return Mock(
        listdir=Mock(return_value=[("old"), ("new")]),
    )


def test_cleaner(
    monkeypatch, caplog, tmp_path, mock_no_config, mock_storage_content, mock_datetime
):
    caplog.set_level(logging.INFO)
    monkeypatch.setattr(reader, "datetime", mock_datetime)
    monkeypatch.setattr(
        reader, "LocalFileStorage", Mock(return_value=mock_storage_content)
    )
    reader.cleaner()
    assert caplog.text.splitlines() == [
        "INFO:cleaner:Removing files from prior to 2023-10-20",
        "INFO:cleaner:Removing old",
        "INFO:cleaner:Done",
    ]
    assert mock_storage_content.mock_calls == [call.listdir("*"), call.rmdir("old")]

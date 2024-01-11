"""
Test the filter module.

Requires --log-format="%(levelname)s:%(name)s:%(message)s"

"""
from collections import Counter
import datetime
import logging
from pathlib import Path
from unittest.mock import Mock, MagicMock, call

from pydantic.networks import Url

import pytest

import filter
import model
import common
import storage
import notification


@pytest.fixture()
def mock_no_config(tmp_path, monkeypatch):
    monkeypatch.setattr(
        filter, "Path", Mock(wraps=Path, cwd=Mock(return_value=tmp_path))
    )
    monkeypatch.setitem(common.DEFAULT_FILTER_CONFIG, "dockets", ["example"])


def test_match_items():
    counts = Counter()
    mock_item_1 = Mock(item=Mock(docket="nope"))
    mock_item_2 = Mock(item=Mock(docket=None))
    mock_item_3 = Mock(item=Mock(docket="contains example"))
    mock_item_4 = Mock(item=Mock(docket="also contains example"))
    mock_storage = Mock(
        read_json=Mock(
            return_value=[mock_item_1, mock_item_2, mock_item_3, mock_item_4]
        )
    )
    history = {mock_item_4}
    new = list(
        filter.match_items(
            mock_storage, ("yyyymmdd", "hh", "items.json"), ["example"], history, counts
        )
    )
    assert new == [mock_item_3]
    assert counts["item"] == 4
    assert counts["new"] == 1


@pytest.fixture()
def mock_history():
    history = [Mock(item=Mock(docket="contains example", pub_date=1))]
    return history


@pytest.fixture
def mock_item():
    item = model.USCourtItem(
        title="2:23-cv-08293-NJC-ST Miller v. Sanofi US Services Inc. et al",
        link=Url("https://ecf.nyed.uscourts.gov/cgi-bin/DktRpt.pl?505703"),
        description="[Order to Show Cause] Miller v. Sanofi US Services Inc. et al",
        text_pub_date="Fri, 29 Dec 2023 21:23:33 GMT",
        docket="2:23-cv-08293-NJC-ST",
        parties="Miller v. Sanofi US Services Inc. et al",
    )
    return item


@pytest.fixture
def mock_item_detail(mock_channel, mock_item):
    return model.USCourtItemDetail(item=mock_item, channel=mock_channel)


@pytest.fixture()
def mock_storage(mock_history, mock_item_detail):
    items = [mock_item_detail]
    return Mock(
        exists=Mock(return_value=True),
        listdir=Mock(return_value=[("date", "hr", "items.json")]),
        read_json=Mock(side_effect=[mock_history, items]),
    )


@pytest.fixture()
def mock_config(tmp_path, monkeypatch):
    monkeypatch.setattr(
        common, "Path", Mock(wraps=Path, cwd=Mock(return_value=tmp_path))
    )
    file = tmp_path / "config.toml"
    file.write_text('[filter]\ndockets=["example"]\n')
    return file


def test_filter(caplog, monkeypatch, mock_config, mock_storage, mock_history):
    mock_notification = MagicMock()
    mock_notification_class = Mock(return_value=mock_notification)

    def mock_get_class(cls):
        match cls:
            case storage.Storage:
                return Mock(return_value=mock_storage)
            case notification.Notification:
                return mock_notification_class

    caplog.set_level(logging.INFO)
    monkeypatch.setattr(common, "get_class", Mock(side_effect=mock_get_class))
    mock_new = Mock(item=Mock(docket="example", pub_date=3))
    mock_match_items = Mock(return_value=[mock_new])
    monkeypatch.setattr(filter, "match_items", mock_match_items)

    filter.filter()

    assert caplog.text.splitlines() == [
        "INFO:filter:Dockets ['example']",
        "INFO:filter:History start     1",
        "INFO:filter:Scanning downloaded items",
        "INFO:filter:Saving filter.json",
        # "INFO:LogNote:Writing 1 items to ('notification', '2024-Jan-07.md')",
        "INFO:filter:History end       2",
        "INFO:filter:Counter({'history:end': 2, 'targets': 1, 'history:start': 1})",
    ]
    assert mock_storage.write_json.mock_calls == [
        call("filter.json", mock_history + [mock_new])
    ]
    assert mock_notification_class.mock_calls == [call(mock_storage, {"smtp": {}, 'ses': {'admin': 'admin@domain.smtp.your_host', 'send_to': 'slott56@gmail.com'}})]
    assert mock_notification.mock_calls == [
        call.__enter__(),
        call.__enter__().notify(mock_new),
        call.__exit__(None, None, None),
    ]

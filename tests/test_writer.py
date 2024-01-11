"""
Test the writer module.

Requires --log-format="%(levelname)s:%(name)s:%(message)s"

"""
from collections import defaultdict
import datetime
import logging
from pathlib import Path
from unittest.mock import Mock, call

from pydantic.networks import Url
import pytest

import common
import model
import writer


@pytest.fixture
def mock_channel():
    c = model.Channel(
        title="Eastern District of New York Filings Entries on cases",
        link=Url("https://ecf.nyed.uscourts.gov/"),
        description="Public Filings in the last 24 Hours",
        last_build=datetime.datetime(2023, 12, 28, 21, 20, 1),
    )
    return c


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
def mock_storage(mock_item_detail):
    return Mock(
        exists=Mock(return_value=True),
        listdir=Mock(return_value=[("date", "hr", "items.json")]),
        read_json=Mock(return_value=[mock_item_detail]),
    )


def test_load_indices(mock_storage, mock_item_detail):
    inx = writer.load_indices(mock_storage)
    assert inx == {
        "court": defaultdict(
            list,
            {
                "Eastern District of New York Filings Entries on cases": [
                    mock_item_detail
                ]
            },
        ),
        "date": defaultdict(list, {"2023-Dec-29": [mock_item_detail]}),
        "docket": defaultdict(list, {"2:23-cv-08293-NJC-ST": [mock_item_detail]}),
        "filtered": defaultdict(list, {"2:23-cv-08293-NJC-ST": [mock_item_detail]}),
    }


def test_write_csv(capsys, mock_item_detail):
    writer.write_csv({"court": {"test": [mock_item_detail]}})
    out, err = capsys.readouterr()
    assert out.splitlines() == [
        "title,docket,pub_date,title,link,description",
        "Eastern District of New York Filings Entries on cases,2:23-cv-08293-NJC-ST,Fri Dec 29 21:23:33 2023,2:23-cv-08293-NJC-ST Miller v. Sanofi US Services Inc. et al,https://ecf.nyed.uscourts.gov/cgi-bin/DktRpt.pl?505703,[Order to Show Cause] Miller v. Sanofi US Services Inc. et al",
    ]


def test_paginate():
    keys = list(range(20))
    assert writer.paginate_keys(keys, 7) == [
        (1, (0, 7)),
        (2, (7, 14)),
        (3, (14, 21)),
    ]
    assert writer.paginate_keys(keys, 0) == [(1, (0, 20))]


@pytest.fixture()
def mock_load_indices(mock_item_detail):
    indices = {
        "court": {"court": [mock_item_detail]},
        "docket": {"docket": [mock_item_detail]},
        "date": {"date": [mock_item_detail]},
    }
    return indices


def test_write_html(caplog, mock_load_indices):
    caplog.set_level(logging.INFO)
    logger = logging.getLogger("writer")
    storage = Mock()
    writer.write_template(logger, storage, "html", 20, mock_load_indices)
    assert caplog.text.splitlines() == [
        "INFO:writer:writing court/index.html",
        "INFO:writer:writing court/index_1.html",
        "INFO:writer:writing docket/index.html",
        "INFO:writer:writing docket/index_1.html",
        "INFO:writer:writing date/index.html",
        "INFO:writer:writing date/index_1.html",
        "INFO:writer:writing filtered/index.html",
        "INFO:writer:writing index.html",
    ]
    assert storage.make.mock_calls == [
        call(("court",), exist_ok=True),
        call(("docket",), exist_ok=True),
        call(("date",), exist_ok=True),
        call(("filtered",), exist_ok=True),
    ]
    assert len(storage.write_text.mock_calls) == 8


@pytest.fixture()
def mock_no_config(tmp_path, monkeypatch):
    monkeypatch.setattr(
        writer, "Path", Mock(wraps=Path, cwd=Mock(return_value=tmp_path))
    )


def test_html_writer(caplog, mock_no_config, monkeypatch, mock_load_indices):
    caplog.set_level(logging.INFO)
    mock_reader_storage = Mock()
    mock_writer_storage = Mock()
    mock_write_template = Mock()
    mock_storage_class = Mock(side_effect=[mock_reader_storage, mock_writer_storage])
    monkeypatch.setattr(common, "get_class", Mock(return_value=mock_storage_class))
    monkeypatch.setattr(writer, "load_indices", Mock(return_value=mock_load_indices))
    monkeypatch.setattr(writer, "write_template", mock_write_template)
    writer.writer()
    assert caplog.text.splitlines() == [
        "INFO:writer:Reading captured items",
        "INFO:writer:court           1",
        "INFO:writer:docket          1",
        "INFO:writer:date            1",
        "INFO:writer:Writing html",
        "INFO:writer:Done",
    ]
    logger = logging.getLogger("writer")
    assert mock_write_template.mock_calls == [
        call(logger, mock_writer_storage, "html", 20, mock_load_indices)
    ]


@pytest.fixture()
def mock_config(tmp_path, monkeypatch):
    monkeypatch.setattr(
        common, "Path", Mock(wraps=Path, cwd=Mock(return_value=tmp_path))
    )
    file = tmp_path / "config.toml"
    file.write_text('[writer]\nformat="csv"\n')
    return file


def test_csv_writer(caplog, mock_config, monkeypatch, mock_load_indices):
    caplog.set_level(logging.INFO)
    mock_reader_storage = Mock()
    mock_writer_storage = Mock()
    mock_write_csv = Mock()
    mock_storage_class = Mock(side_effect=[mock_reader_storage, mock_writer_storage])
    monkeypatch.setattr(
        common, "get_class", Mock(return_value=Mock(return_value=mock_storage_class))
    )
    monkeypatch.setattr(writer, "load_indices", Mock(return_value=mock_load_indices))
    monkeypatch.setattr(writer, "write_csv", mock_write_csv)
    writer.writer()
    assert caplog.text.splitlines() == [
        "INFO:writer:Reading captured items",
        "INFO:writer:court           1",
        "INFO:writer:docket          1",
        "INFO:writer:date            1",
        "INFO:writer:Writing csv",
        "INFO:writer:Done",
    ]
    logger = logging.getLogger("writer")
    assert mock_write_csv.mock_calls == [call(mock_load_indices)]

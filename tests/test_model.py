"""
Test the reader module.

Requires --log-format="%(levelname)s:%(name)s:%(message)s"

"""
import datetime
from textwrap import dedent
from xml.etree import ElementTree

from pydantic.networks import Url
import pytest

import model


def test_channel_class(xml_doc):
    rss = ElementTree.fromstring(xml_doc)
    channel_tag = rss.find("channel")
    channel = model.Channel.from_tag(channel_tag)
    assert channel == model.Channel(
        title="Eastern District of New York Filings Entries on cases",
        link=Url("https://ecf.nyed.uscourts.gov/"),
        description="Public Filings in the last 24 Hours",
        last_build=datetime.datetime(2023, 12, 28, 21, 20, 1),
    )


def test_item_class(xml_doc):
    rss = ElementTree.fromstring(xml_doc)
    channel_tag = rss.find("channel")
    item_tag = channel_tag.find("item")
    item = model.Item.from_tag(item_tag)
    assert item == model.Item(
        title="2:23-cv-09491-PKC-ST Sookra v. Berkeley Carroll School et al",
        link=Url("https://ecf.nyed.uscourts.gov/cgi-bin/DktRpt.pl?508001"),
        description="[Quality Control Check - Summons] Sookra v. Berkeley Carroll School et al",
        text_pub_date="Thu, 28 Dec 2023 21:18:55 GMT",
    )


def test_uscourt_item_class(xml_doc):
    rss = ElementTree.fromstring(xml_doc)
    channel_tag = rss.find("channel")
    item_tag = channel_tag.find("item")
    item = model.USCourtItem.from_tag(item_tag)
    assert item == model.USCourtItem(
        title="2:23-cv-09491-PKC-ST Sookra v. Berkeley Carroll School et al",
        link=Url("https://ecf.nyed.uscourts.gov/cgi-bin/DktRpt.pl?508001"),
        description="[Quality Control Check - Summons] Sookra v. Berkeley Carroll School et al",
        text_pub_date="Thu, 28 Dec 2023 21:18:55 GMT",
        docket="2:23-cv-09491-PKC-ST",
        parties="Sookra v. Berkeley Carroll School et al",
    )

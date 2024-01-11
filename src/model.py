"""
Data Model for the Feeder Reader.


..  plantuml::

    @startuml

    component pydantic {
        class BaseModel
    }

    component model {

    class Item {
        title: str
        link: URL
        description: str
        pub_date: datetime

        {static} from_tag(xml)
    }
    BaseModel <|-- Item

    class Channel {
        title: str
        link: URL

        {static} from_tag(xml)
    }
    BaseModel <|-- Channel

    Channel *-- "1,m" Item

    class USCourtItem {
        docket: str
        parties: str

        {static} from_tag(xml)
    }
    BaseModel <|-- USCourtItem

    Item <|-- USCourtItem

    class USCourtItemDetail {
        item: USCourtItem
        channel: Channel
    }
    BaseModel <|-- USCourtItemDetail

    USCourtItem <-- USCourtItemDetail /' --> USCourtItem '/
    Channel <-- USCourtItemDetail     /' --> Channel '/
    }

    hide empty members

    @enduml


..  references:
    components.rst expects lines 4 to 47 have the diagram. Note zero-based numbering.
    In the IDE editor it looks like lines 5 to 48.

..  note::

    A docket number may be composed of a number or letter indicating the court,
    a two-digit number to identify the year,
    the case type (either CV/cv for civil cases or CR/cr for criminal cases),
    a four- or five-digit case number, and the judge’s initials.

    For example, 1:21-cv-5678-MW is the docket number for the 5,678th civil case filed in the year 2021 and assigned to court number 1 and the Honorable Martha Washington.
"""
from collections.abc import Iterator
import datetime
import re
from xml.etree import ElementTree
from typing import Any, TypeAlias

from pydantic import BaseModel
from pydantic.networks import AnyUrl


class Channel(BaseModel, frozen=True):
    """The channel definition from the RSS source.

    For example,

    ..  code-block:: xml

        <rss version="2.0">
        <channel>
        <title>Eastern District of New York Filings Entries on cases</title>
        <link>https://ecf.nyed.uscourts.gov</link>
        <description>Public Filings in the last 24 Hours</description>
        <lastBuildDate>Thu, 28 Dec 2023 21:20:01 GMT</lastBuildDate>
        ...
        </channel>
        </rss>

    The :py:meth:`from_tag` method only preserves the title and link
    information.
    """

    title: str  #: RSS feed title
    link: AnyUrl  #: RSS feed link
    # description: str
    # last_build: datetime.datetime

    @classmethod
    def from_tag(cls, tag: ElementTree.Element) -> "Channel":
        """
        Extracts the individual field values from the XML tag.

        :param tag: The XML tag for a channel.
        :return: New :py:class:`Channel` instance.
        """
        title = (tag.findtext("title") or "").strip()
        link = (tag.findtext("link") or "").strip()
        # description = (tag.findtext("description") or "").strip()
        # last_build_text = (tag.findtext("lastBuildDate") or "").strip()
        # last_build_date = datetime.datetime.strptime(
        #     last_build_text, "%a, %d %b %Y %H:%M:%S %Z"
        # )
        return Channel(
            title=title,
            link=AnyUrl(link),
            # description=description,  # Always "Public Filings in the last 24 Hours"
            # last_build=last_build_date,  # Changes with each release
        )


class Item(BaseModel, frozen=True):
    """One item from within a channel extracted from the RSS source.

    For example,

    ..  code-block:: xml

        <item>
        <title>
        <![CDATA[ 2:23-cv-09491-PKC-ST Sookra v. Berkeley Carroll School et al ]]>
        </title>
        <pubDate>Thu, 28 Dec 2023 21:18:55 GMT</pubDate>
        <author/>
        <guid isPermaLink="true">https://ecf.nyed.uscourts.gov/cgi-bin/DktRpt.pl?508001</guid>
        <description>
        <![CDATA[ [Quality Control Check - Summons] Sookra v. Berkeley Carroll School et al ]]>
        </description>
        <link>https://ecf.nyed.uscourts.gov/cgi-bin/DktRpt.pl?508001</link>
        </item>

    """

    title: str  #: RSS feed title
    link: AnyUrl  #: RSS feed link
    description: str  #: RSS feed description
    text_pub_date: str  #: RSS feed publication date

    @property
    def pub_date(self) -> datetime.datetime:
        """Parse the publication date."""
        return datetime.datetime.strptime(
            self.text_pub_date, "%a, %d %b %Y %H:%M:%S %Z"
        )

    @classmethod
    def parse(cls, tag: ElementTree.Element) -> dict[str, Any]:
        """
        Parse the individual fields to create an interim mapping.

        :param tag: the XML tag
        :returns: a dictionary with fields and values.
        """
        return dict(
            title=(tag.findtext("title") or "").strip(),
            link=(tag.findtext("link") or "").strip(),
            description=(tag.findtext("description") or "").strip(),
            text_pub_date=(tag.findtext("pubDate") or "").strip(),
        )

    @classmethod
    def from_tag(cls, tag: ElementTree.Element) -> "Item":
        """
        Extracts the individual field values from the XML tag.

        :param tag: The XML tag for an item.
        :return: New :py:class:`Item` instance.
        """
        parsed = cls.parse(tag)
        return Item(
            title=parsed["title"],
            link=AnyUrl(parsed["link"]),
            description=parsed["description"],
            text_pub_date=parsed["text_pub_date"],
        )


class USCourtItem(Item, frozen=True):
    """
    Decompose an Item tag content to get Docket and Parties from the Title.

    Generally the title has a docket string followed by the parties.

    ::

        2:23-cv-09491-PKC-ST Sookra v. Berkeley Carroll School et al

    The ``2:23-cv-09491-PKC-ST`` is the docket.
    The remaining portion name the parties.
    """

    docket: str | None  #: Docket extracted from the title
    parties: str | None  #: Parties extracted from the title.

    @classmethod
    def from_tag(cls, tag: ElementTree.Element) -> "USCourtItem":
        """
        Extracts the individual field values from the XML tag.

        :param tag: The XML tag for an item.
        :return: New :py:class:`USCourtItem` instance.
        """
        parsed = cls.parse(tag)
        docket_pattern = re.compile(
            r"^(?P<docket>.+:\d+-\w+-\d+.*?)\s+(?P<parties>.*)$"
        )
        docket: str | None = None
        parties: str | None = None
        if match := docket_pattern.match(parsed["title"]):
            docket = match.group("docket")
            parties = match.group("parties").strip()
        return USCourtItem(
            title=parsed["title"],
            link=AnyUrl(parsed["link"]),
            description=parsed["description"],
            text_pub_date=parsed["text_pub_date"],
            docket=docket,
            parties=parties,
        )


Feed: TypeAlias = Iterator[USCourtItem | Channel]


class USCourtItemDetail(BaseModel, frozen=True):
    """
    An item and the channel for this item.
    The two are bound together to make sure the overall court information is kept with each item.
    """
    item: USCourtItem  #: The item from the RSS feed.
    channel: Channel  #: The channel to which the item belongs.

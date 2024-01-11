"""
Test the notification module.

Requires --log-format="%(levelname)s:%(name)s:%(message)s"

"""
import os
import re
from unittest.mock import Mock, call, ANY, sentinel

import boto3
from pydantic.networks import Url
import pytest
from moto import mock_sns, mock_sesv2, mock_ses


import common
import model
import notification


@pytest.fixture(scope="function")
def aws_credentials():
    """Mocked AWS Credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"


@pytest.fixture()
def mock_storage():
    return Mock(name="Storage")


@pytest.fixture()
def mock_datetime(monkeypatch):
    mock_datetime_datetime = Mock(
        name="datetime.datetime", now=Mock(return_value=datetime.datetime(2024, 1, 18))
    )
    mock_package = Mock(name="datetime", datetime=mock_datetime_datetime)
    monkeypatch.setattr(filter, "datetime", mock_package)
    return mock_package


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


def test_lognote_messages(mock_storage, mock_item_detail):
    ln = notification.LogNote(mock_storage)
    with ln:
        ln.notify(mock_item_detail)

    assert ln.created is not None
    assert mock_storage.write_text.mock_calls == [
        call(("notification", ln.finish_time.strftime("%Y-%b-%d.html")), ANY)
    ]
    path, content = mock_storage.write_text.mock_calls[0].args
    assert re.search(r"\<!DOCTYPE html\>", content, re.MULTILINE | re.DOTALL)
    assert re.search(
        r"\<title\>Rss Feederreader Notification .*\</title\>",
        content,
        re.MULTILINE | re.DOTALL,
    )
    assert re.search(
        r"\<li\>2:23-cv-08293-NJC-ST.*\</li\>", content, re.MULTILINE | re.DOTALL
    )


def test_lognote_no_messages(mock_storage):
    ln = notification.LogNote(mock_storage)
    with ln:
        pass

    assert ln.created is None
    assert mock_storage.write_text.mock_calls == []


@pytest.fixture()
def mock_smtplib(monkeypatch):
    mock_client = Mock(
        name="SMTP",
    )
    mock_smtplib = Mock(name="smtplib", SMTP=Mock(return_value=mock_client))
    monkeypatch.setattr(notification, "smtplib", mock_smtplib)
    return mock_smtplib


@pytest.fixture()
def mock_smtp_config(monkeypatch):
    config = {
        "host": sentinel.HOST,
        "port": sentinel.PORT,
        "admin": "admin@smtp.host",
        "password": "password",
        "send_to": "target@emailhost",
    }
    monkeypatch.setattr(
        common, "get_config", Mock(return_value={"notifier": {"smtp": config}})
    )


def test_smtpnote(mock_smtplib, mock_smtp_config, mock_item_detail):
    mock_smtp_client = mock_smtplib.SMTP()
    ln = notification.SMTPNote(
        None,
    )
    with ln:
        ln.notify(mock_item_detail)

    assert ln.created is not None
    assert mock_smtplib.mock_calls == [
        call.SMTP(),  # This test function.
        call.SMTP(sentinel.HOST, sentinel.PORT),
    ]
    assert mock_smtp_client.mock_calls == [
        call.login("admin@smtp.host", "password"),
        call.sendmail("admin@smtp.host", "slott56@gmail.com", ANY),
        call.quit(),
    ]
    from_addr, to_addr, content = mock_smtp_client.sendmail.mock_calls[0].args
    assert re.search(
        r"Rss Feederreader Notification .*", content, re.MULTILINE | re.DOTALL
    )
    assert re.search(r"2:23-cv-08293-NJC-ST", content, re.MULTILINE | re.DOTALL)


@mock_sns
def test_snsnote(mock_item_detail, aws_credentials, monkeypatch):
    conn = boto3.client("sns", region_name="us-east-1")
    topic = conn.create_topic(
        Name="topic_name",
    )
    # print(topic)
    monkeypatch.setattr(
        common,
        "get_config",
        Mock(
            return_value={
                "FDRDR": {"SNS_TOPIC": topic["TopicArn"]},
                "AWS": {"REGION": "us-east-1"},
            }
        ),
    )

    ln = notification.SNSNote(
        None,
    )
    with ln:
        ln.notify(mock_item_detail)

    assert ln.created is not None

    from moto.core import DEFAULT_ACCOUNT_ID
    from moto.sns import sns_backends

    sns_backend = sns_backends[DEFAULT_ACCOUNT_ID]["us-east-1"]
    all_sent_notifications = sns_backend.topics[topic["TopicArn"]].sent_notifications
    assert "2:23-cv-08293-NJC-ST" in all_sent_notifications[0][1]


@pytest.fixture()
def mock_ses_config(monkeypatch):
    config = {
        "admin": "admin@smtp.host",
        "send_to": "target@emailhost",
    }
    monkeypatch.setattr(
        common,
        "get_config",
        Mock(
            return_value={
                "notifier": {"ses": config},
                "AWS": {"REGION": "us-east-1"},
                "FDRDR": {"IDENTITY_ARN": "arn:aws:ses:us-east-1:123456789012:identity/smtp.host"},
            }
        ),
    )


@pytest.fixture(scope="function")
def ses_v1():
    """Use this for API calls which exist in v1 but not in v2"""
    with mock_ses():
        yield boto3.client("ses", region_name="us-east-1")


@mock_sesv2
def test_sesnote(ses_v1, mock_ses_config, mock_item_detail, aws_credentials):
    # Create "admin@smtp.host" as verified Email identity to permit sending messages.
    reply = ses_v1.verify_domain_identity(Domain="smtp.host")

    ln = notification.SESEmail(
        None,
    )
    with ln:
        ln.notify(mock_item_detail)

    assert ln.created is not None

    from moto.core import DEFAULT_ACCOUNT_ID
    from moto.ses import ses_backends

    ses_backend = ses_backends[DEFAULT_ACCOUNT_ID]["us-east-1"]
    print(dir(ses_backend.sent_messages[0]))
    assert ses_backend.sent_messages[0].source == "admin@smtp.host"
    assert ses_backend.sent_messages[0].destinations == {
        "ToAddresses": ["target@emailhost"]
    }
    assert ses_backend.sent_messages[0].subject.startswith(
        "RSS FeederReader notification"
    )
    assert "<!DOCTYPE html>" in ses_backend.sent_messages[0].body
    assert "2:23-cv-08293-NJC-ST" in ses_backend.sent_messages[0].body

"""
Test the notification module.

Requires --log-format="%(levelname)s:%(name)s:%(message)s"

"""
from unittest.mock import Mock, call, ANY, sentinel

import pytest

import notification

@pytest.fixture()
def mock_storage():
    return Mock(name="Storage")

def test_lognote_messages(mock_storage):
    ln = notification.LogNote(mock_storage, {})
    with ln:
        ln.notify("message 1")

    assert ln.created is not None
    assert mock_storage.write_text.mock_calls == [
        call(('notification', ln.finish_time.strftime("%Y-%b-%d.md")), ANY)
    ]

def test_lognote_no_messages(mock_storage):
    ln = notification.LogNote(mock_storage, {})
    with ln:
        pass

    assert ln.created is None
    assert mock_storage.write_text.mock_calls == []

@pytest.fixture()
def mock_smtplib(monkeypatch):
    mock_client = Mock(
        name="SMTP",
    )
    mock_smtplib = Mock(
        name="smtplib",
        SMTP=Mock(return_value=mock_client)
    )
    monkeypatch.setattr(notification, 'smtplib', mock_smtplib)
    return mock_smtplib

def test_smtpnote(mock_smtplib):
    mock_smtp_client = mock_smtplib.SMTP()
    ln = notification.SMTPNote( None, {
        "host": sentinel.HOST,
        "port": sentinel.PORT,
        "admin": "admin@smtp.host",
        "password": "password",
        "send_to": "target@emailhost",
    })
    with ln:
        ln.notify("message 1")

    assert ln.created is not None
    assert mock_smtplib.mock_calls == [
        call.SMTP(),  # This test function.
        call.SMTP(sentinel.HOST, sentinel.PORT)
    ]
    assert mock_smtp_client.mock_calls == [
        call.login('admin@smtp.host', 'password'),
        call.sendmail('admin@smtp.host', 'slott56@gmail.com', ANY),
        call.quit()
    ]

def test_smtpnote_no_messages(mock_smtplib):
    mock_smtp_client = mock_smtplib.SMTP()
    ln = notification.SMTPNote( None, {
        "host": sentinel.HOST,
        "port": sentinel.PORT,
        "admin": "admin@smtp.host",
        "password": "password",
        "send_to": "target@emailhost",
    })
    with ln:
        pass

    assert ln.created is None
    assert mock_smtplib.mock_calls == [
        call.SMTP(),  # This test function.
    ]
    assert mock_smtp_client.mock_calls == []

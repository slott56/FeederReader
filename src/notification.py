"""Notification for the Feeder Reader.

The idea is to provide a common abstract class with several concrete implementations:

 -  Stored log files.

 -  AWS SNS.

 -  Local SMTP.

 -  AWS SES -- better than local SMTP.

The notifiers use Jinja to format documents.
This module has the document templates.

 ..  plantuml::

    @startuml

    component notification {
        abstract class Notification {
            messages: list[USCourtItemDetail]
            + notify(USCourtItemDetail)
            - start()
            - {abstract} finish()
        }

        class LogNote {
        - finish()
        }
        Notification <|-- LogNote

        class SMTPNote {
        - finish()
        }
        Notification <|-- SMTPNote

        class SNSNote {
        - finish()
        }
        Notification <|-- SNSNote

        class SESEmail {
        - finish()
        }
        Notification <|-- SESEmail
    }

    component model {
        class USCourtItemDetail
    }

    component smtplib {
        class SMTP
    }

    component storage {
        class Storage
    }

    component common {
        class get_config << (F, orchid) Function >>
    }

    component jinja {
        class Environment
        class Template
    }

    cloud AWS {
        circle SES
        circle SNS
    }

    notification ..> Template
    Notification ..> model
    SNSNote ..> SNS
    SESEmail ..> SES
    LogNote ..> Storage
    SMTPNote ..> SMTP
    Notification ..> get_config

    @enduml

 A notifier is a context manager.
 The idea is that it is going to accumulate details
 and send them at exit time.
 If there are no details, it does nothing.

 ::

    note_class = common.get_class(Notification)
    with note_class(storage, nfr_config) as notifier:
        # process items
        notifier.notify(item)

At the end of the ``with`` statement, the context manager will
make sure all items are handled.
"""
import abc
import datetime
from email.message import EmailMessage
import logging
import smtplib
from types import TracebackType
from typing import Literal

import boto3  # type: ignore [import-untyped]
from jinja2 import Environment, DictLoader

import model
import common
import storage

HTML_BASE = """\
{% macro detail(item) -%}
{{item.item.title}}: {{item.item.pub_date.ctime()}} <a href="{{item.item.link}}">link</a> {{item.item.description}}
{%- endmacro %}
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="https://cdn.simplecss.org/simple.min.css">
    {% block head -%}
    <title>{% block title %}{% endblock %}</title>
    {# CSS #}
    {%- endblock %}
</head>
<body>
    <header>
    {% block heading %}<h1>{{ self.title() }}</h1>{% endblock %}
    </header>
    <main>
    {% block content %}
    {% endblock %}
    </main>
</body>
</html>
"""

HTML_MESSAGE = """\
{% extends "base.html" %}
{% block title %}{{ index_name | title }}{% endblock %}
{% block content %}
<ul>
{% for item in items %}
<li>{{ detail(item) }}</li>
{% endfor %}
</ul>
{% endblock %}
"""

TEXT_MESSAGE = """\
{% for item in items %}
- {{item.item.title}}: {{item.item.pub_date.ctime()}} {{item.item.link}} {{item.item.description}}

{% endfor %}
"""


class Notification:
    """
    Abstract class with operations to notify of changes.
    """
    def __init__(self, storage: storage.Storage | None = None) -> None:
        """
        Prepare to send notifications.

        :param storage: A :py:class:`storage.Storage` object. Only used for the :py:class:`LogNote` subclass.
            For all other subclasses, this should be `None`.
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.config = common.get_config()
        self.env = Environment(
            loader=DictLoader(
                {
                    "base.html": HTML_BASE,
                    "message.html": HTML_MESSAGE,
                    "message.txt": TEXT_MESSAGE,
                },
            )
        )
        self.messages: list[model.USCourtItem] = []

    def __enter__(self) -> "Notification":
        """
        Context manager entrance.

        Delegate work to the more visible :py:meth:`start` method.

        :return: Notification
        """
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[Exception] | None,
        exc: Exception | None,
        exc_tb: TracebackType,
    ) -> Literal[None]:
        """
        Context manager exit.

        Set the ``subject`` and ``finish_time`` attributes.
        Delegate work to the more visible :py:meth:`finish` method.
        Propagate any exceptions.

        :return: Notification
        """
        if not self.messages:
            self.logger.info("Nothing new")
            return
        self.finish_time = datetime.datetime.now()
        self.logger.info("Writing %d items", len(self.messages))
        self.subject = f"RSS FeederReader notification {self.finish_time.ctime()}"
        self.finish()

    def start(self) -> None:  # pragma: no cover
        """Start accumulating  notifications."""
        pass

    def notify(self, message: model.USCourtItem) -> None:
        """
        Accumulate an item for notification.

        :param message: An item to include in the notification.
        """
        self.messages.append(message)

    @abc.abstractmethod
    def finish(self) -> None:  # pragma: no cover
        """End accumulating  notifications; finalize and send."""
        ...


class LogNote(Notification):
    """
    Accumulates an HTML file with notifications.

    The ``storage`` parameter is required.
    """

    def __init__(self, storage: storage.Storage) -> None:
        """
        Prepare to write notifications to the given storage instance.
        Prepares to write a ``notification/yyyy-mmm-dd.html`` file.

        :param storage: A :py:class:`storage.Storage` object. This is required.
        """
        super().__init__()
        self.storage = storage
        self.note_base = ("notification",)
        self.created: tuple[str, ...] | None = None

    def finish(self) -> None:
        note_path = self.note_base + (self.finish_time.strftime("%Y-%b-%d.html"),)
        message_template = self.env.get_template("message.html")
        text = message_template.render(index_name=self.subject, items=self.messages)
        self.storage.write_text(note_path, text)
        self.created = note_path


class SMTPNote(Notification):
    """
    Sends an email message using Python smtplib.

    The ``storage`` parameter must be ``None``, which is the default.

    The configuration file must provide the parameters for
    accessing the SMTP server. See :py:func:`common.get_config`.
    """

    def __init__(self, storage: storage.Storage | None = None) -> None:
        """
        Prepare to send notifications to the SMTP server.
        """
        assert storage is None
        super().__init__()
        self.created: tuple[str, ...] | None = None
        smtp_config = self.config["notifier"]["smtp"]
        self.host = smtp_config["host"]
        self.port = smtp_config["port"]
        self.admin = smtp_config["admin"]
        self.password = smtp_config["password"]
        self.send_to = smtp_config["send_to"]

    def finish(self) -> None:
        text_template = self.env.get_template("message.txt")
        text = text_template.render(index_name=self.subject, items=self.messages)
        html_template = self.env.get_template("message.html")
        html = html_template.render(index_name=self.subject, items=self.messages)

        msg = EmailMessage()
        msg["Subject"] = self.subject
        msg["From"] = self.admin
        msg["To"] = "slott56@gmail.com"
        msg.set_content(text)
        msg.add_alternative(html, subtype="html")

        s = smtplib.SMTP(self.host, self.port)
        s.login(self.admin, self.password)
        s.sendmail(msg["From"], msg["To"], msg.as_string())
        s.quit()
        self.created = (
            "email",
            self.finish_time.strftime("%Y-%b-%d.md"),
        )


class SNSNote(Notification):
    """
    Sends a message using AWS SNS; presumably with an email subscription configured.

    The topic's ARN is provided as an environment variable :envvar:`FDRDR_SNS_TOPIC`.

    The ``storage`` parameter must be ``None``, which is the default.
    """

    def __init__(self, storage: storage.Storage | None = None) -> None:
        assert storage is None
        super().__init__()
        self.storage = storage
        fdrdr_config = self.config["FDRDR"]
        aws_config = self.config["AWS"]

        self.arn = fdrdr_config["SNS_TOPIC"]
        self.sns = boto3.resource("sns", region_name=aws_config["REGION"])
        self.topic = self.sns.Topic(self.arn)

    def finish(self) -> None:
        message_template = self.env.get_template("message.txt")
        text = message_template.render(index_name=self.subject, items=self.messages)
        response = self.topic.publish(
            TopicArn=self.arn,
            Subject=self.subject,
            Message=text,
        )
        self.logger.info("SNS %s", response)
        self.created = (
            "sns",
            self.finish_time.strftime("%Y-%b-%d.md"),
        )


class SESEmail(Notification):
    """Sends an email message using AWS SES.

    The sending email address must have been verified with AWS.

    https://docs.aws.amazon.com/ses/latest/dg/creating-identities.html

    The Identity ARN is provided as an environment variable :envvar:`FDRDR_IDENTITY_ARN`.
    The configuration file must provide the parameters for
    accessing the SES Email. See :py:func:`common.get_config`.

    The ``storage`` parameter must be ``None``, which is the default.
    """

    def __init__(self, storage: storage.Storage | None = None) -> None:
        assert storage is None
        super().__init__()
        self.storage = storage
        aws_config = self.config["AWS"]
        fdrdr_config = self.config["FDRDR"]
        ses_config = self.config["notifier"]["ses"]

        self.admin = ses_config["admin"]
        self.send_to = ses_config["send_to"]
        self.identity_arn = fdrdr_config.get("IDENTITY_ARN")
        self.client = boto3.client("sesv2", region_name=aws_config["REGION"])

    def finish(self) -> None:
        text_template = self.env.get_template("message.txt")
        text = text_template.render(index_name=self.subject, items=self.messages)
        html_template = self.env.get_template("message.html")
        html = html_template.render(index_name=self.subject, items=self.messages)

        response = self.client.send_email(
            FromEmailAddress=self.admin,
            FromEmailAddressIdentityArn=self.identity_arn,
            Destination={
                "ToAddresses": [self.send_to],
            },
            Content={
                "Simple": {
                    "Subject": {"Data": self.subject},
                    "Body": {
                        "Html": {"Data": html},
                        "Text": {"Data": text},
                    },
                }
            },
        )
        self.logger.info("SES %s", response)
        self.created = (
            "email",
            self.finish_time.strftime("%Y-%b-%d.md"),
        )

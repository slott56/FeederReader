"""Notification for the Feeder Reader.

The idea is to provide a common wrapper with several implementations:

 -  Stored log files

 -  Local SMTP

 -  AWS SNS

 A notifier is a context manager.
 The idea is that it is going to accumulate details
 and send them at exit time.

 If there are no details, it does nothing.
"""
import abc
from contextlib import redirect_stdout
import datetime
from email.mime.text import MIMEText
import io
import logging
import smtplib
from types import TracebackType
from typing import Literal, Any

import common
import storage

class Notification:
    def __init__(self) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self.config = common.get_config()

    def __enter__(self) -> "Notification":
        self.start()
        return self

    def __exit__(self, exc_type: type[Exception] | None, exc: Exception | None, exc_tb: TracebackType) -> Literal[None]:
        self.finish()

    def start(self) -> None:  # pragma: no cover
        pass

    @abc.abstractmethod
    def notify(self, message: str) -> None:  # pragma: no cover
        ...

    def finish(self) -> None:  # pragma: no cover
        pass


class LogNote(Notification):
    """Accumulates a Markdown format files with notifications."""
    def __init__(self, storage: storage.Storage, config: dict[str, Any]) -> None:
        super().__init__()
        self.messages: list[str] = []
        self.storage = storage
        self.note_base = ("notification",)
        self.created: tuple[str, ...] | None = None

    def notify(self, message: str) -> None:
        self.messages.append(message)

    def finish(self) -> None:
        if not self.messages:
            return
        self.finish_time = datetime.datetime.now()
        note_path = self.note_base + (self.finish_time.strftime("%Y-%b-%d.md"),)
        self.logger.info("Writing %d items to %s", len(self.messages), str(note_path))

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            print(f"# Notifications as of {self.finish_time.ctime()}")
            for m in self.messages:
                print(m)
                print()
        self.storage.write_text(note_path, buffer.getvalue())
        self.created = note_path


class SMTPNote(Notification):
    def __init__(self, storage: storage.Storage | None, config: dict[str, Any]) -> None:
        super().__init__()
        self.messages: list[str] = []
        self.created: tuple[str, ...] | None = None
        self.host = config['host']
        self.port = config['port']
        self.admin = config['admin']
        self.password = config['password']
        self.send_to = config['send_to']

    def notify(self, message: str) -> None:
        self.messages.append(message)

    def finish(self) -> None:
        if not self.messages:
            return
        self.finish_time = datetime.datetime.now()
        self.logger.info("Emailing %d items", len(self.messages))

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            print(f"# Notifications as of {self.finish_time.ctime()}")
            for m in self.messages:
                print(m)
                print()

        msg = MIMEText(buffer.getvalue())
        msg['Subject'] = f"RSS FeederReader notification {self.finish_time.ctime()}"
        msg['From'] = self.admin
        msg['To'] = "slott56@gmail.com"

        s = smtplib.SMTP(self.host, self.port)
        s.login(self.admin, self.password)
        s.sendmail(msg['From'], msg['To'], msg.as_string())
        s.quit()
        self.created = ('email', self.finish_time.strftime("%Y-%b-%d.md"),)

"""Storage for the Feeder Reader.

The idea is to provide a common wrapper with two implementations:

 -  Local File system

 -  AWS S3
"""
import abc
from collections import deque
from collections.abc import Iterator, Iterable
from pathlib import Path
from typing import TypeAlias, TextIO

from pydantic import BaseModel, Json
from pydantic_core import to_json, from_json


Writable: TypeAlias = str | BaseModel | Json[str] | Iterable[BaseModel]


class Storage:
    def __init__(self, base: Path) -> None:
        self.base = base
        self.nlj_file: TextIO | None = None

    def pathify(self, local_path: str | tuple[str, ...]) -> Path:
        p = self.base
        match local_path:
            case str() as txt:
                return p / txt
            case tuple() as seq:
                for c in seq:
                    p = p / c
                return p
            case _:  # pragma: no cover
                raise ValueError(f"unexpected {local_path!r}")

    def textify(self, content: Writable) -> str:
        match content:
            case str() as tx:
                return tx
            case BaseModel() as pd:
                return pd.model_dump_json()
            case list() | dict() | int() | str() | float() | bool() | None as other:
                return to_json(other).decode("ascii")
            case _:  # pragma: no cover
                raise ValueError(f"unexpected {type(content)} type")

    @abc.abstractmethod
    def exists(self, local_path: str | tuple[str, ...]) -> bool:
        ...  # pragma: no cover

    @abc.abstractmethod
    def make(self, local_path: str | tuple[str, ...], exist_ok: bool = False) -> None:
        ...  # pragma: no cover

    @abc.abstractmethod
    def write_json(self, local_path: str | tuple[str, ...], content: Writable) -> None:
        ...  # pragma: no cover

    @abc.abstractmethod
    def read_json(
        self, local_path: str | tuple[str, ...], target: type[BaseModel]
    ) -> list[BaseModel]:
        ...  # pragma: no cover

    @abc.abstractmethod
    def write_text(self, local_path: str | tuple[str, ...], content: str) -> None:
        ...  # pragma: no cover

    @abc.abstractmethod
    def open_nljson(self, local_path: str | tuple[str, ...]) -> None:
        ...  # pragma: no cover

    @abc.abstractmethod
    def write_nljson(self, content: Writable) -> None:
        ...  # pragma: no cover

    @abc.abstractmethod
    def close_nljson(self) -> None:
        ...  # pragma: no cover

    @abc.abstractmethod
    def listdir(self, local_path: str | tuple[str, ...]) -> Iterator[tuple[str, ...]]:
        ...  # pragma: no cover

    @abc.abstractmethod
    def rmdir(self, local_path: str | tuple[str, ...]) -> None:
        ...  # pragma: no cover


class LocalFileStorage(Storage):
    def exists(self, local_path: str | tuple[str, ...]) -> bool:
        return self.pathify(local_path).exists()

    def make(self, local_path: str | tuple[str, ...], exist_ok: bool = False) -> None:
        self.pathify(local_path).mkdir(parents=True, exist_ok=exist_ok)

    def write_json(self, local_path: str | tuple[str, ...], content: Writable) -> None:
        target = self.pathify(local_path)
        target.write_text(self.textify(content))

    def read_json(
        self, local_path: str | tuple[str, ...], cls: type[BaseModel]
    ) -> list[BaseModel]:
        target = self.pathify(local_path)
        document = from_json(target.read_text())
        match document:
            case dict() as singleton:
                return [cls.model_validate(singleton)]
            case list() as collection:
                return [cls.model_validate(item) for item in collection]
            case _:  # pragma: no cover
                raise IOError(f"unexpected {document}")

    def write_text(self, local_path: str | tuple[str, ...], content: str) -> None:
        target = self.pathify(local_path)
        target.write_text(content)

    def open_nljson(self, local_path: str | tuple[str, ...]) -> None:
        if self.nlj_file:
            raise RuntimeError("previous nlj stream not closed")
        self.nlj_file = self.pathify(local_path).open("a")

    def write_nljson(self, content: Writable) -> None:
        if self.nlj_file:
            one_line = "".join(self.textify(content).splitlines())
            self.nlj_file.write(self.textify(one_line))
            self.nlj_file.write("\n")

    def close_nljson(self) -> None:
        if not self.nlj_file:
            return
        self.nlj_file.close()
        self.nlj_file = None

    def listdir(self, local_path: str | tuple[str, ...]) -> Iterator[tuple[str, ...]]:
        match local_path:
            case str() as tx:
                pattern = tx
            case tuple() as seq:
                pattern = "/".join(seq)
            case _:  # pragma: no cover
                raise ValueError

        for name in sorted(self.base.glob(pattern)):
            yield name.relative_to(self.base).parts

    def rmdir(self, local_path: str | tuple[str, ...]) -> None:
        target = self.pathify(local_path)
        cleanup: deque[Path] = deque()
        for hr_data in target.glob("**/*"):
            if hr_data.is_file():
                hr_data.unlink()
            elif hr_data.is_dir():
                cleanup.append(hr_data)
        while cleanup:
            subdir = cleanup.popleft()
            try:
                subdir.rmdir()
            except OSError:  # pragma: no cover
                # Not empty, try again later
                cleanup.append(subdir)
        target.rmdir()

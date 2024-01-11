"""
Storage for the Feeder Reader.

The idea is to provide a common abstract class with two concrete implementations:

 -  Local File system

 -  AWS S3

 ..  plantuml::

    @startuml

    component storage {
        abstract class Storage {
            exists(path) : Bool
            make(path)
            write_json(path, object)
            read_json(path, class): object
            write_text(path, object)
            listdir(path) : List[path]
            rmdir(path)
        }

        class LocalFileStorage
        Storage <|-- LocalFileStorage

        class S3Storage
        Storage <|-- S3Storage
    }

    component model {
        class USCourtItemDetail
    }

    cloud AWS {
        class S3Bucket
        class S3Object

        S3Bucket *-- S3Object
    }

    S3Storage --> S3Bucket

    storage ..> model

    @enduml


"""
import abc
from collections import deque
from collections.abc import Iterator, Iterable
import io
from pathlib import Path
from typing import TypeAlias, TextIO, Any

from pydantic import BaseModel, Json
from pydantic_core import to_json, from_json
import boto3  # type: ignore [import-untyped]


Writable: TypeAlias = str | BaseModel | Json[str] | Iterable[BaseModel]


class Storage:
    """
    Abstract class with operations to persist data.

    Note that a path is represented as a ``tuple[str, ...]``, not as a "/"-delimited string.
    """
    def __init__(self, base: Path) -> None:
        """Prepares the Storage. This may make a request to assert the S3 Bucket exists.
        It may check to be sure the Path is a valid local file.

        :param base: A :py:class:`Path` instance that can be used for local storage or can be used to create the name of an S3 bucket."""
        self.base = base

    def textify(self, content: Writable) -> str:
        """
        Transforms a ``Writeable`` into JSON-formatted representation.

        -   str objects are left intact, no changes. Presumably, these were already in JSON format.

        -   Any :py:class:`pydanticBaseModel` instance is serialized using it's :meth:`model_dump_json` method.

        -   Any other class is provided to the :py:class:`pydantic.to_json` function.

        :param content: Something to persist
        :returns: String, ready to write.
        """
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
        """
        Does the path exist?

        :param local_path: nodes along the path.
        """
        ...  # pragma: no cover

    @abc.abstractmethod
    def make(self, local_path: str | tuple[str, ...], exist_ok: bool = False) -> None:
        """
        Make a new directory.

        :param local_path: nodes along the path.
        """
        ...  # pragma: no cover

    @abc.abstractmethod
    def write_json(self, local_path: str | tuple[str, ...], content: Writable) -> None:
        """
        Serialize an object or list of objects in JSON. Most collections should be lists.

        :param local_path: nodes along the path.
        :param content: An object to be converted to JSON and persisted. Usually a list.
        """
        ...  # pragma: no cover

    @abc.abstractmethod
    def read_json(
        self, local_path: str | tuple[str, ...], target: type[BaseModel]
    ) -> list[BaseModel]:
        """
        Deserialize a list of objects from JSON to Python. Most collections are lists.

        :param local_path: nodes along the path.
        :param target: Sublass of :py:class:`pydantic.BaseModel`.
        """
        ...  # pragma: no cover

    @abc.abstractmethod
    def write_text(self, local_path: str | tuple[str, ...], content: str) -> None:
        """
        Write text. Often HTML. Possible Markdown or CSV.

        :param local_path: nodes along the path.
        :param content: An string to write.
        """
        ...  # pragma: no cover

    @abc.abstractmethod
    def open_nljson(self, local_path: str | tuple[str, ...]) -> None:
        """
        Open a path to append objects in Newline Delimited JSON format.
        The path must exist. Use :py:meth:`exists` and :py:meth:`make` as needed.

        :param local_path: nodes along the path.
        """
        ...  # pragma: no cover

    @abc.abstractmethod
    def write_nljson(self, content: Writable) -> None:
        """
        Append on object in Newline Delimited JSON format to the currenly open NLJSON.

        :param content: An object to be converted to JSON and persisted.
        """
        ...  # pragma: no cover

    @abc.abstractmethod
    def close_nljson(self) -> None:
        """
        Close path after appending objects in Newline Delimited JSON format.
        """
        ...  # pragma: no cover

    @abc.abstractmethod
    def listdir(self, local_path: str | tuple[str, ...]) -> Iterator[tuple[str, ...]]:
        """
        List the contents of a path.

        :param local_path: nodes along the path.
        """
        ...  # pragma: no cover

    @abc.abstractmethod
    def rmdir(self, local_path: str | tuple[str, ...]) -> None:
        """
        Remove all objects with a given path.

        :param local_path: nodes along the path.
        """
        ...  # pragma: no cover

    def validate(
        self, document: dict[str, Any], cls: type[BaseModel]
    ) -> list[BaseModel]:
        """
        Uses ``pydantic`` model validation to validate JSON to create an object.
        Since most collections have lists, this builds a list of instances,
        even when given a dictionary built from a JSON source.

        :param document: a dictionary recovered from parsing JSON text.
        :param cls: A subclass of :py:class:`pydantic.BaseModel`.
        :returns: an instance of the given class
        :raises: Validation errors of the document cannot be validated.
        """
        match document:
            case dict() as singleton:
                return [cls.model_validate(singleton)]
            case list() as collection:
                return [cls.model_validate(item) for item in collection]
            case _:  # pragma: no cover
                raise IOError(f"unexpected {document}")


class LocalFileStorage(Storage):
    """
    Concrete class with operations to persist data in the local filesystem.

    Note that a path is represented as a ``tuple[str, ...]``, not as a "/"-delimited string.
    """
    def __init__(self, base: Path) -> None:
        """Prepares the Storage; check to be sure the Path is a valid local directory.

        :param base: A :py:class:`Path` instance that can be used for local storage. This must be a directory.
        """
        if not base.exists() or not base.is_dir():  # pragma: no cover
            raise ValueError(f"path {base} must be an existing directory")
        super().__init__(base)
        self.nlj_file: TextIO | None = None

    def pathify(self, local_path: str | tuple[str, ...]) -> Path:
        """
        Builds a local :py:class:`Path` from a tuple of strings.

        :param local_path: nodes along the path.
        :return: :py:class:`Path` instance.
        """
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
        return self.validate(document, cls)

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
        dir = self.base
        match local_path:
            case str() as tx:
                dir /= tx
            case tuple() as seq:
                for dir_name in seq:
                    dir /= dir_name
            case _:  # pragma: no cover
                raise ValueError

        for name in sorted(dir.glob("**/*")):
            if name.is_file():
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


class S3Storage(Storage):
    """
    Concrete class with operations to persist data in an S3 bucket.

    Note that a path is represented as a ``tuple[str, ...]``, not as a "/"-delimited string.

    Within an S3 bucket, there aren't proper directories;
    the "path" IS merely a long key to identify an object in the bucket.
    This means that the :py:meth:`make` method doesn't really need to do anything.
    """

    def __init__(self, base: Path) -> None:
        """Prepares the Storage. This may make a request to assert the S3 Bucket exists.

        :param base: A :py:class:`Path` instance is used to create the name of an S3 bucket.
        """
        self.base = base
        self.nlj_key: str | None = None
        self.nlj_body: list[str] | None = None
        self.s3 = boto3.resource("s3")
        self.bucket = self.s3.Bucket(str(base))
        self.bucket.objects.all()

    def pathify(self, local_path: str | tuple[str, ...]) -> str:
        match local_path:
            case str() as txt:
                return txt
            case tuple() as seq:
                return "/".join(seq)
            case _:  # pragma: no cover
                raise ValueError(f"unexpected {local_path!r}")

    def exists(self, local_path: str | tuple[str, ...]) -> bool:
        target = self.pathify(local_path)
        directory = [obj_summ.key for obj_summ in self.bucket.objects.all()]
        return target in directory

    def make(self, local_path: str | tuple[str, ...], exist_ok: bool = False) -> None:
        pass

    def write_json(self, local_path: str | tuple[str, ...], content: Writable) -> None:
        target = self.pathify(local_path)
        object = self.bucket.Object(target)
        status = object.put(Body=self.textify(content))
        # print("write_json", status)
        if status["ResponseMetadata"]["HTTPStatusCode"] != 200:
            raise IOError(status)  # pragma: no cover

    def read_json(
        self, local_path: str | tuple[str, ...], cls: type[BaseModel]
    ) -> list[BaseModel]:
        target_path = self.pathify(local_path)
        object = self.bucket.Object(target_path)
        buffer = io.BytesIO()
        object.download_fileobj(buffer)
        document = from_json(buffer.getvalue())
        return self.validate(document, cls)

    def write_text(self, local_path: str | tuple[str, ...], content: str) -> None:
        target = self.pathify(local_path)
        object = self.bucket.Object(target)
        object.put(Body=content)

    def open_nljson(self, local_path: str | tuple[str, ...]) -> None:
        if self.nlj_body is not None:
            raise RuntimeError("previous nlj stream not closed")
        self.nlj_key = self.pathify(local_path)
        object = self.bucket.Object(self.nlj_key)
        try:
            self.nlj_body = object.get().splitlines()
        except self.s3.meta.client.exceptions.NoSuchKey:
            self.nlj_body = []

    def write_nljson(self, content: Writable) -> None:
        if self.nlj_body is not None:
            line = self.textify(content)
            self.nlj_body.append(line)

    def close_nljson(self) -> None:
        if self.nlj_body is None:
            return
        object = self.bucket.Object(self.nlj_key)
        object.put(Body="\n".join(self.nlj_body) + "\n")
        self.nlj_key = None
        self.nlj_body = None

    def listdir(self, local_path: str | tuple[str, ...]) -> Iterator[tuple[str, ...]]:
        target = self.pathify(local_path)
        directory = (
            tuple(obj_summ.key.split("/"))
            for obj_summ in self.bucket.objects.filter(Prefix=target)
        )
        return directory

    def rmdir(self, local_path: str | tuple[str, ...]) -> None:
        target = self.pathify(local_path)
        remove_me = list(
            obj_summ.key for obj_summ in self.bucket.objects.filter(Prefix=target)
        )
        for name in remove_me:
            object = self.bucket.Object(name)
            object.delete()

"""
Test the storage module.

Requires --log-format="%(levelname)s:%(name)s:%(message)s"

"""
import io
import boto3

import pytest
from moto import mock_s3

import storage
import model


def test_local_file_storage(tmp_path, mock_channel, mock_item):
    lfs = storage.LocalFileStorage(tmp_path)
    assert not lfs.exists("dir")
    assert not lfs.exists(("tuple", "of", "str"))
    lfs.make("dir")
    assert lfs.exists("dir")
    with pytest.raises(FileExistsError):
        lfs.make("dir")
    lfs.write_json("text", "text")
    assert (tmp_path / "text").read_text() == "text"
    lfs.write_json("dict", {"some": "dict"})
    assert (tmp_path / "dict").read_text() == '{"some":"dict"}'
    lfs.write_json("chan", mock_channel)
    ch = model.Channel.model_validate_json((tmp_path / "chan").read_text())
    assert mock_channel == ch

    lfs.write_json("list", [mock_item])
    saved = lfs.read_json("list", model.USCourtItem)
    assert len(saved) == 1
    assert saved == [mock_item]

    lfs.write_json("item", mock_item)
    saved = lfs.read_json("item", model.USCourtItem)
    assert saved == [mock_item]

    # listdir and cleanup
    lfs.make(("dir", "data"))
    lfs.write_json(("dir", "data", "file"), "some data")
    assert lfs.exists(("dir", "data", "file"))
    assert list(lfs.listdir("dir")) == [("dir", "data", "file")]
    assert list(lfs.listdir(("dir", "data"))) == [("dir", "data", "file")]
    lfs.rmdir("dir")
    assert not lfs.exists(("dir", "data"))
    assert not lfs.exists("dir")

    # Text
    lfs.write_text("something.html", "<!DOCTYPE html>")
    assert (tmp_path / "something.html").exists()


def test_local_file_nlj_file(tmp_path, mock_channel, mock_item):
    lfs = storage.LocalFileStorage(tmp_path)

    # NLJson stream
    lfs.open_nljson("nlj")
    with pytest.raises(RuntimeError):
        lfs.open_nljson("nlj")
    lfs.write_nljson("one")
    lfs.write_nljson("two")
    lfs.close_nljson()
    lfs.close_nljson()
    assert (tmp_path / "nlj").read_text() == "one\ntwo\n"


@mock_s3
def test_s3_file_storage(mock_channel, mock_item):
    conn = boto3.resource("s3", region_name="us-east-1")
    conn.create_bucket(Bucket="some-bucket")

    s3fs = storage.S3Storage("some-bucket")
    assert not s3fs.exists("dir")
    assert not s3fs.exists(("tuple", "of", "str"))
    s3fs.make("dir")

    # Not true until we write something; semantics slightly different from file system.
    # assert s3fs.exists("dir")
    # with pytest.raises(FileExistsError):
    #    s3fs.make("dir")

    s3fs.write_json("text", "text")
    assert s3fs.exists("text")

    buffer = io.BytesIO()
    conn.Bucket("some-bucket").Object("text").download_fileobj(buffer)
    assert buffer.getvalue().decode("utf-8") == "text"

    s3fs.write_json("dict", {"some": "dict"})

    buffer = io.BytesIO()
    conn.Bucket("some-bucket").Object("dict").download_fileobj(buffer)
    assert buffer.getvalue().decode("utf-8") == '{"some":"dict"}'

    s3fs.write_json("chan", mock_channel)

    buffer = io.BytesIO()
    conn.Bucket("some-bucket").Object("chan").download_fileobj(buffer)
    assert model.Channel.model_validate_json(buffer.getvalue()) == mock_channel

    s3fs.write_json("list", [mock_item])
    saved = s3fs.read_json("list", model.USCourtItem)
    assert len(saved) == 1
    assert saved == [mock_item]

    s3fs.write_json("item", mock_item)
    saved = s3fs.read_json("item", model.USCourtItem)
    assert saved == [mock_item]

    # listdir and cleanup
    s3fs.make(("dir", "data"))
    s3fs.write_json(("dir", "data", "file"), "some data")
    assert s3fs.exists(("dir", "data", "file"))
    assert list(s3fs.listdir("dir")) == [("dir", "data", "file")]
    assert list(s3fs.listdir(("dir", "data"))) == [("dir", "data", "file")]
    s3fs.rmdir("dir")
    assert not s3fs.exists(("dir", "data"))
    assert not s3fs.exists("dir")

    # Text
    s3fs.write_text("something.html", "<!DOCTYPE html>")
    assert s3fs.exists("something.html")
    buffer = io.BytesIO()
    conn.Bucket("some-bucket").Object("something.html").download_fileobj(buffer)
    assert buffer.getvalue().decode("utf-8") == "<!DOCTYPE html>"


@mock_s3
def test_s3_nlj_file(tmp_path, mock_channel, mock_item):
    conn = boto3.resource("s3", region_name="us-east-1")
    conn.create_bucket(Bucket="some-bucket")

    s3fs = storage.S3Storage("some-bucket")

    # NLJson stream
    s3fs.open_nljson("nlj")
    with pytest.raises(RuntimeError):
        s3fs.open_nljson("nlj")
    s3fs.write_nljson("one")
    s3fs.write_nljson("two")
    s3fs.close_nljson()
    s3fs.close_nljson()

    # assert (tmp_path / "nlj").read_text() == "one\ntwo\n"
    buffer = io.BytesIO()
    conn.Bucket("some-bucket").Object("nlj").download_fileobj(buffer)
    assert buffer.getvalue().decode("utf-8") == "one\ntwo\n"

"""
Test the storage module.

Requires --log-format="%(levelname)s:%(name)s:%(message)s"

"""
import pytest

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

    # NLJson stream
    lfs.open_nljson("nlj")
    with pytest.raises(RuntimeError):
        lfs.open_nljson("nlj")
    lfs.write_nljson("one")
    lfs.write_nljson("two")
    lfs.close_nljson()
    lfs.close_nljson()
    assert (tmp_path / "nlj").read_text() == "one\ntwo\n"

    # listdir and cleanup
    lfs.make(("dir", "data"))
    lfs.write_json(("dir", "data", "file"), "some data")
    assert (tmp_path / "dir" / "data").exists()
    assert list(lfs.listdir("dir")) == [("dir",)]
    assert list(lfs.listdir(("dir", "data"))) == [("dir", "data")]
    lfs.rmdir("dir")
    assert not (tmp_path / "dir" / "data").exists()
    assert not (tmp_path / "dir").exists()

    lfs.write_text("something.html", "<!DOCTYPE html>")
    assert (tmp_path / "something.html").exists()

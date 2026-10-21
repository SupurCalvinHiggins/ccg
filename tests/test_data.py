import pytest

from qualgraph.data import load_data, parse_data


def test_load_data(tmp_path):
    path = tmp_path / "quotes.csv"
    path.write_text("participant,codes\nP01,trust|communication\nP01,cost\nP02,trust|cost|delay\n")
    assert load_data(path) == [
        ("P01", ["trust", "communication"]),
        ("P01", ["cost"]),
        ("P02", ["trust", "cost", "delay"]),
    ]


def test_parse_data():
    assert parse_data("participant,codes\r\nP01,a|b\r\nP02,c\r\n") == [("P01", ["a", "b"]), ("P02", ["c"])]


def test_parse_data_rejects_bad_header():
    with pytest.raises(ValueError, match="codes"):
        parse_data("participant,tags\nP01,a\n")

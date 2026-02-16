import pytest
from pypm.resolver import is_stdlib

def test_is_stdlib_true():
    assert is_stdlib("os") is True
    assert is_stdlib("sys") is True
    assert is_stdlib("json") is True
    assert is_stdlib("math") is True

def test_is_stdlib_false():
    assert is_stdlib("requests") is False
    assert is_stdlib("pypm") is False
    assert is_stdlib("black") is False
    assert is_stdlib("numpy") is False

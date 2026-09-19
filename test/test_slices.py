import logging

import pytest
from pytest import fixture

from atom_tools.lib.slices import AtomSlice, import_slice


@fixture
def java_usages_1():
    return AtomSlice("test/data/java-piggymetrics-usages.json", "java")


@fixture
def java_usages_2():
    return AtomSlice("test/data/java-sec-code-usages.json", "java")


@fixture
def js_usages_1():
    return AtomSlice("test/data/js-juiceshop-usages.json", "js")


@fixture
def js_usages_2():
    return AtomSlice("test/data/js-nodegoat-usages.json", "js")


@fixture
def py_usages_1():
    return AtomSlice("test/data/py-depscan-usages.json", "js")


@fixture
def py_usages_2():
    return AtomSlice("test/data/py-tornado-usages.json", "js")


def test_usages_class(
    java_usages_1,
    java_usages_2,
):
    usages = AtomSlice("test/data/java-piggymetrics-usages.json", "java")
    assert usages.content is not None

    usages = AtomSlice("test/data/java-sec-code-usages.json", "java")
    assert usages.content is not None


def test_import_slice_names_the_file_and_position_on_bad_json(caplog):
    """A malformed slice reports its own path and parse position, and exits
    non-zero, instead of naming a character offset into an unnamed file."""
    with caplog.at_level(logging.WARNING):
        with pytest.raises(SystemExit) as exc:
            import_slice("test/data/invalid.json")
    assert exc.value.code == 1
    assert (
        "Failed to load usages slice: test/data/invalid.json:"
        " Expecting value: line 5 column 1 (char 41)" in caplog.text
    )

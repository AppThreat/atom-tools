from pytest import fixture
from atom_tools.lib.slices import AtomSlice


@fixture
def java_usages_1():
    return AtomSlice('test/data/java-piggymetrics-usages.json')


@fixture
def java_usages_2():
    return AtomSlice('test/data/java-sec-code-usages.json')


@fixture
def js_usages_1():
    return AtomSlice('test/data/js-juiceshop-usages.json')


@fixture
def js_usages_2():
    return AtomSlice('test/data/js-nodegoat-usages.json')


@fixture
def py_usages_1():
    return AtomSlice('test/data/py-depscan-usages.json')


@fixture
def py_usages_2():
    return AtomSlice('test/data/py-tornado-usages.json')


def test_usages_class(
        java_usages_1,
        java_usages_2,
):
    usages = AtomSlice('test/data/java-piggymetrics-usages.json')
    assert usages.content is not None

    usages = AtomSlice('test/data/java-sec-code-usages.json')
    assert usages.content is not None


def test_import_slices(js_usages_1):
    # Test nonexistent file
    assert AtomSlice('test/data/js-tornado-usages.json').content == {}

    # Test invalid JSON file
    assert AtomSlice('test/data/invalid.json').content == {}

    # Valid JSON but reachables not usages
    assert AtomSlice('test/data/js-juiceshop-reachables.json').content == {}

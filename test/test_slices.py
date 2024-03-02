from pytest import fixture
from atom_tools.lib.slices import AtomSlice


@fixture
def java_usages_1():
    return AtomSlice('test/data/java-piggymetrics-usages.json', 'java')


@fixture
def java_usages_2():
    return AtomSlice('test/data/java-sec-code-usages.json', 'java')


@fixture
def js_usages_1():
    return AtomSlice('test/data/js-juiceshop-usages.json', 'js')


@fixture
def js_usages_2():
    return AtomSlice('test/data/js-nodegoat-usages.json', 'js')


@fixture
def py_usages_1():
    return AtomSlice('test/data/py-depscan-usages.json', 'js')


@fixture
def py_usages_2():
    return AtomSlice('test/data/py-tornado-usages.json', 'js')


def test_usages_class(
        java_usages_1,
        java_usages_2,
):
    usages = AtomSlice('test/data/java-piggymetrics-usages.json', 'java')
    assert usages.content is not None

    usages = AtomSlice('test/data/java-sec-code-usages.json', 'java')
    assert usages.content is not None


def test_import_slices(js_usages_1):
    # Test nonexistent file
    assert AtomSlice('test/data/js-tornado-usages.json', 'js').content == {}

    # Test invalid JSON file
    assert AtomSlice('test/data/invalid.json', 'js').content == {}

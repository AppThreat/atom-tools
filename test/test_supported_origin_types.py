"""Tests for the shared supported origin-type set and the commands using it.

`convert` and `query-endpoints` must accept exactly the same --type values,
taken from the single SUPPORTED_ORIGIN_TYPES constant in
atom_tools.lib.converter (which is derived from the converter's own dispatch),
so the two commands can never drift apart again.

Unblocking those types surfaced a second defect, since fixed: the go, rust
and ruby converters attach x-atom-usages to each *operation* while the
JVM-style converter attaches it to the *path item*, and output_endpoints read
only the path item -- so those languages converted correctly but printed an
empty console listing. See test_console_listing_is_not_empty.
"""

import pytest
from cleo.testers.command_tester import CommandTester

from atom_tools.cli.application import Application
from atom_tools.cli.commands.convert import ConvertCommand
from atom_tools.cli.commands.query_endpoints import QueryEndpointsCommand
from atom_tools.lib.converter import SUPPORTED_ORIGIN_TYPES, OpenAPI

# Pins the constant to exactly the aliases the converter dispatches on.
EXPECTED_TYPES = {
    "java",
    "jar",
    "python",
    "py",
    "javascript",
    "js",
    "typescript",
    "ts",
    "ruby",
    "rb",
    "scala",
    "sbt",
    "rs",
    "rust",
    "go",
    "golang",
}

# A real slice file per alias, used for end-to-end acceptance of every type.
# Scala has no usages fixture in this repository; the java usages file is used
# there purely to exercise acceptance (scala_convert returns no paths without
# a semantics slice, and no fixture is invented for it).
LANGUAGE_FIXTURES = {
    "java": "test/data/java-piggymetrics-usages.json",
    "jar": "test/data/java-piggymetrics-usages.json",
    "javascript": "test/data/js-juiceshop-usages.json",
    "js": "test/data/js-juiceshop-usages.json",
    "typescript": "test/data/ts-custom-router-usages.json",
    "ts": "test/data/ts-custom-router-usages.json",
    "python": "test/data/py-breakable-flask-usages.json",
    "py": "test/data/py-breakable-flask-usages.json",
    "ruby": "test/data/rb-railsgoat-usages.json",
    "rb": "test/data/rb-railsgoat-usages.json",
    "scala": "test/data/java-piggymetrics-usages.json",
    "sbt": "test/data/java-piggymetrics-usages.json",
    "rs": "test/data/rust-axum-sample-rusi.json",
    "rust": "test/data/rust-axum-sample-rusi.json",
    "go": "test/data/go-gin-sample-golem.json",
    "golang": "test/data/go-gin-sample-golem.json",
}

PATH_COUNTS = [
    ("rb", "test/data/rb-railsgoat-usages.json", 58),
    ("rs", "test/data/rust-axum-sample-rusi.json", 8),
    ("go", "test/data/go-gin-sample-golem.json", 6),
    ("go", "test/data/ecosystem/go-ipsw-golem.json", 50),
]


def test_supported_types_match_the_converter_dispatch():
    assert SUPPORTED_ORIGIN_TYPES == EXPECTED_TYPES


def test_commands_use_the_shared_constant():
    from atom_tools.cli.commands import convert, query_endpoints

    assert convert.SUPPORTED_ORIGIN_TYPES is SUPPORTED_ORIGIN_TYPES
    assert query_endpoints.SUPPORTED_ORIGIN_TYPES is SUPPORTED_ORIGIN_TYPES


@pytest.mark.parametrize(("origin_type", "fixture", "expected_paths"), PATH_COUNTS)
def test_query_endpoints_conversion_produces_real_paths(origin_type, fixture, expected_paths):
    """query-endpoints converts the previously blocked languages.

    Asserts the exact path count produced by the same OpenAPI call the
    command makes, not merely that no exception was raised.
    """
    converter = OpenAPI("openapi3.1.0", origin_type, fixture)
    result = converter.endpoints_to_openapi("")
    assert result["paths"]
    assert len(result["paths"]) == expected_paths


@pytest.mark.parametrize("origin_type", sorted(SUPPORTED_ORIGIN_TYPES))
def test_query_endpoints_accepts_every_supported_type(origin_type):
    app = Application()
    tester = CommandTester(app.find("query-endpoints"))
    tester.execute(f"-t {origin_type} -i {LANGUAGE_FIXTURES[origin_type]}")
    assert tester.status_code == 0


@pytest.mark.parametrize("origin_type", sorted(SUPPORTED_ORIGIN_TYPES))
def test_convert_accepts_the_same_types(origin_type, tmp_path):
    app = Application()
    tester = CommandTester(app.find("convert"))
    tester.execute(
        f"-f openapi3.1.0 -t {origin_type} -i {LANGUAGE_FIXTURES[origin_type]} "
        f"-o {tmp_path / 'openapi.json'}"
    )
    assert tester.status_code == 0
    assert (tmp_path / "openapi.json").exists()


def test_fixture_coverage_tracks_the_constant():
    """A new alias cannot silently pass acceptance without a fixture decision."""
    assert set(LANGUAGE_FIXTURES) == set(SUPPORTED_ORIGIN_TYPES)


@pytest.mark.parametrize("command_name", ["convert", "query-endpoints"])
@pytest.mark.parametrize("unknown_type", ["kt", "swift"])
def test_unknown_type_lists_supported_values(command_name, unknown_type):
    app = Application()
    tester = CommandTester(app.find(command_name))
    with pytest.raises(ValueError) as excinfo:
        tester.execute(f"-t {unknown_type} -i test/data/java-piggymetrics-usages.json")
    message = str(excinfo.value)
    assert message.startswith(f"Unknown origin type: {unknown_type}")
    assert "Supported:" in message
    for alias in ("go", "java", "ruby"):
        assert alias in message


@pytest.mark.parametrize("command_cls", [ConvertCommand, QueryEndpointsCommand])
def test_type_option_help_lists_supported_values(command_cls):
    description = next(o for o in command_cls.options if o.name == "type").description
    assert "Origin type" in description
    for alias in sorted(SUPPORTED_ORIGIN_TYPES):
        assert alias in description


@pytest.mark.parametrize(
    ("origin_type", "fixture", "expected_lines"),
    [
        ("go", "test/data/go-gin-sample-golem.json", 6),
        ("rs", "test/data/rust-axum-sample-rusi.json", 8),
        ("rb", "test/data/rb-railsgoat-usages.json", 31),
        ("java", "test/data/java-piggymetrics-usages.json", 18),
    ],
)
def test_console_listing_is_not_empty(origin_type, fixture, expected_lines, capsys):
    """
    query-endpoints must print endpoints, not just convert them.

    go/rs/rb regressed to an empty listing the moment they became reachable,
    because their x-atom-usages lives one level deeper than the JVM-style
    converter's. java is included to pin that the fallback changed nothing
    for the path-item nesting.
    """
    app = Application()
    tester = CommandTester(app.find("query-endpoints"))
    tester.execute(f"-t {origin_type} -i {fixture}")
    assert tester.status_code == 0
    # The command writes the listing with print(), not through cleo's io.
    printed = [line for line in capsys.readouterr().out.splitlines() if line.strip()]
    assert len(printed) == expected_lines

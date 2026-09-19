"""Tests that every registered CLI command module loads cleanly.

The command loader imports command modules lazily, so a syntax or import
error in any single command would otherwise only surface when that command
is invoked. This suite loads them all.
"""

import pytest

from atom_tools.cli.application import COMMANDS, load_command


@pytest.mark.parametrize("name", COMMANDS)
def test_command_module_loads(name):
    factory = load_command(name)
    command = factory()
    assert command.name == name
    assert command.description
    assert command.options is not None
    assert command.help


def test_registered_commands_are_the_expected_set():
    assert set(COMMANDS) == {
        "analyze",
        "apk-analysis",
        "attack-surface",
        "check-reachable",
        "convert",
        "crypto-reach",
        "drift",
        "explain",
        "filter",
        "graph",
        "ingest",
        "merge-slices",
        "query-endpoints",
        "stats",
        "validate-lines",
        "visualize",
    }

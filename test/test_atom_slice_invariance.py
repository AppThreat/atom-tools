"""The atom-slice invariance baseline.

Every phase of the ecosystem work (dosai/golem/rusi support, the six new
commands) has promised that the original commands behave byte-identically on
atom slices. That promise is pinned here and in the table in
test/data/ecosystem/PROVENANCE.md: the md5 of each command's exact bytes —
the output file for convert, stdout for stats and query-endpoints.

A moving digest means either atom-slice behaviour changed (a regression for
every existing user of the tool) or the change is deliberate, in which case
re-derive the digest, update PROVENANCE.md, and say so in the changelog.
"""

import hashlib
from pathlib import Path

import pytest
from cleo.testers.command_tester import CommandTester

from atom_tools.cli.application import Application

# The inputs are repo-relative POSIX strings, as PROVENANCE.md records the
# commands: an absolute spelling differs per checkout, and str(Path(...))
# differs per OS. Each test chdirs to the repo root so they resolve from any
# cwd -- pytest does not guarantee one.
REPO = Path(__file__).resolve().parent.parent

PIGGYMETRICS = "test/data/java-piggymetrics-usages.json"
JUICESHOP = "test/data/js-juiceshop-usages.json"

# Verified on 3886b19 (start of phase 8) and re-derived unchanged at its
# close; OUT is any output path — the convert document does not embed it.
PINNED = [
    (
        "convert",
        f"-i {PIGGYMETRICS} -o {{out}} -t java",
        "cbdd4c26b11d04efefd6d8db2f2f7942",
    ),
    (
        "convert",
        f"-i {JUICESHOP} -o {{out}} -t js",
        "c3006109418f023b5755e8ca2ae15429",
    ),
    (
        "stats",
        f"-i {PIGGYMETRICS}",
        "a52a5e8a2f7d0a3e957e379b1b46d079",
    ),
    (
        "query-endpoints",
        f"-i {PIGGYMETRICS}",
        "a72277a26c0224b89b687f6f90a10c82",
    ),
]


@pytest.mark.parametrize(("command", "args", "expected"), PINNED)
def test_atom_slice_bytes_are_pinned(command, args, expected, tmp_path, capsys, monkeypatch):
    """The original commands' exact bytes on atom slices must not move."""
    monkeypatch.chdir(REPO)
    app = Application()
    tester = CommandTester(app.find(command))
    if "{out}" in args:
        out = tmp_path / "out.json"
        tester.execute(args.format(out=out))
        digest = hashlib.md5(out.read_bytes()).hexdigest()
    else:
        tester.execute(args)
        # stats writes through cleo's io, query-endpoints through print();
        # each command uses exactly one of the two channels.
        stdout = tester.io.fetch_output() + capsys.readouterr().out
        digest = hashlib.md5(stdout.encode()).hexdigest()
    assert digest == expected, (
        f"{command}'s atom-slice output changed: md5 {digest} != {expected}."
        " Either a regression, or re-derive the digest and update the table"
        " in test/data/ecosystem/PROVENANCE.md."
    )

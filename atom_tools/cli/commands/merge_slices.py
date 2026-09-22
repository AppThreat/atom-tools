"""Merge Slices Command for the atom-tools CLI."""

import logging

from cleo.helpers import option

from atom_tools.cli.commands.command import Command
from atom_tools.lib.reachables import load_reachables
from atom_tools.lib.utils import export_json


logger = logging.getLogger(__name__)


class MergeSlicesCommand(Command):
    """
    This command merges reachable slice files into a single document.

    atom writes reachable slices in chunks (reachables.json, reachables_1.json,
    ...) and monorepos frequently produce one slice per language or project.
    This command folds any number of them into one de-duplicated document that
    the other atom-tools commands accept.

    Attributes:
        name (str): The name of the command.
        description (str): The description of the command.
        options (list): The list of options for the command.
        help (str): The help message for the command.

    Methods:
        handle: Executes the command and performs the merge.
    """

    name = "merge-slices"
    description = (
        "Merge reachable slice files (including atom's chunked output) into a"
        " single de-duplicated slice."
    )
    options = [
        option(
            "input-slice",
            "i",
            "Slice file, glob pattern, or comma separated list. Sibling chunks"
            " such as reachables_1.json are picked up automatically.",
            flag=False,
            value_required=True,
        ),
        option(
            "output-file",
            "o",
            "Output file",
            flag=False,
            default="merged.reachables.slices.json",
            value_required=True,
        ),
        option(
            "no-dedupe",
            None,
            "Keep duplicate flow groups instead of dropping them.",
        ),
    ]
    # The literal JSON example must double its braces: cleo runs help text
    # through str.format, and a bare {"reachables": ...} raises KeyError.
    help = """Merges reachable slice files into a single document.

atom chunks reachable slices at 1000 flow groups per file and writes them as
bare JSON arrays. This command loads every matching file plus its sibling
chunks, de-duplicates identical flow groups, and writes a single
{{"reachables": [...]}} document usable by filter, convert, check-reachable and
the other commands."""

    loggers = [
        "atom_tools.lib.reachables",
        "atom_tools.lib.utils",
    ]

    def handle(self):
        """
        Executes the merge command.
        """
        merged = load_reachables(self.option("input-slice"), dedupe=not self.option("no-dedupe"))
        count = len(merged.get("reachables", []))
        if not count:
            logger.warning("No reachable entries found. Nothing to merge.")
            return 1
        export_json(merged, self.option("output-file"))
        logger.debug(
            "Merged %d reachable flow group(s) into %s.",
            count,
            self.option("output-file"),
        )
        self.line(f"Merged {count} reachable flow group(s) into {self.option('output-file')}.")
        return 0

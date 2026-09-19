"""Stats Command for the atom-tools CLI."""

import logging

from cleo.helpers import option

from atom_tools.cli.commands.command import Command
from atom_tools.lib.slices import AtomSlice
from atom_tools.lib.stats import SliceStats
from atom_tools.lib.utils import export_json

logger = logging.getLogger(__name__)


class StatsCommand(Command):
    """
    This command summarises an atom slice: counts, files, packages and tags.

    Attributes:
        name (str): The name of the command.
        description (str): The description of the command.
        options (list): The list of options for the command.
        help (str): The help message for the command.

    Methods:
        handle: Executes the command and prints the summary.
    """

    name = "stats"
    description = "Summarise an atom slice: counts, source files, packages (purls) and tags."
    options = [
        option(
            "input-slice",
            "i",
            "Slice file. Usages, reachables, data-flow, parsedeps and semantics"
            " slices are supported.",
            flag=False,
            value_required=True,
        ),
        option(
            "json",
            None,
            "Write the summary as a JSON document instead of printing text.",
        ),
        option(
            "output-file",
            "o",
            "Output file used together with --json.",
            flag=False,
            default="slice-stats.json",
            value_required=True,
        ),
    ]
    help = """Summarise an atom slice for quick triage and CI usage.

Reports flow group, node and file counts, the reachable package purls, the
most common chen tags (sources, sinks, pii, tracker, ...) and per-type detail
for usages, data-flow and parsedeps slices. Use --json for a machine readable
summary."""

    loggers = [
        "atom_tools.lib.reachables",
        "atom_tools.lib.slices",
        "atom_tools.lib.utils",
    ]

    def handle(self):
        """
        Executes the stats command.
        """
        atom_slice = AtomSlice(self.option("input-slice"))
        stats = SliceStats(
            atom_slice.content, atom_slice.slice_type, self.option("input-slice")
        ).to_dict()
        if self.option("json"):
            export_json(stats, self.option("output-file"), 4)
            self.line(f"<info>Stats written to {self.option('output-file')}.</info>")
        else:
            self._render(stats)
        return 0

    def _render(self, stats):
        """Print the summary as readable sections."""
        self.line(f"<info>Slice type</info>: {stats['slice_type']}")
        for section, value in stats.items():
            if section == "slice_type":
                continue
            if isinstance(value, dict):
                self.line(f"<comment>{section}</comment>:")
                for k, v in value.items():
                    self.line(f"  {k}: {v}")
            else:
                self.line(f"<comment>{section}</comment>: {value}")

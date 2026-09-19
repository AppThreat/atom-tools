"""Drift Command for the atom-tools CLI."""

import logging

from cleo.helpers import option

from atom_tools.cli.commands.command import Command
from atom_tools.lib.reachables import load_json_report

logger = logging.getLogger(__name__)

FORMATS = ("json", "console", "markdown")


class DriftCommand(Command):
    """
    This command compares two runs of the same engine and reports what changed:
    flows added, removed or merely moved, newly reachable packages, new entry
    points, and whether the new run actually covered as much code as the old
    one.
    """

    name = "drift"
    description = (
        "Compare two reachability reports from the same engine and report the"
        " risk delta between them (added, removed and moved flows)."
    )
    options = [
        option(
            "old",
            None,
            "Baseline report: dosai dataflows, golem analyze, rusi or kosi analyze or"
            " atom reachables.",
            flag=False,
            value_required=True,
        ),
        option(
            "new",
            None,
            "Current report, from the same engine as --old.",
            flag=False,
            value_required=True,
        ),
        option(
            "output-file",
            "o",
            "Output file for the drift document (json format only).",
            flag=False,
            default="drift.json",
            value_required=True,
        ),
        option(
            "format",
            "f",
            f"Output format: {', '.join(FORMATS)}.",
            flag=False,
            default="console",
            value_required=True,
        ),
        option(
            "fail-on",
            None,
            "Comma separated gate keys; exit code 2 when any trips. Known:"
            " new-high, new-medium, new-anonymous-endpoint, new-package,"
            " new-sink-category, new-entrypoint. A coverage regression trips"
            " the gate regardless of this option.",
            flag=False,
            value_required=True,
        ),
        option(
            "engine",
            None,
            "Force the producing engine for both inputs instead of detecting"
            " it from the report envelope.",
            flag=False,
            value_required=True,
        ),
    ]
    help = """Report the reachability delta between two runs.

A repository with thousands of flows is never triaged; the handful that
appeared since the last run is. drift is a pure function over two reports --
it never invokes an engine, so it runs in seconds in CI.

Flow identity is built from analysis facts (source and sink category, sink
symbol, root-relative file, purls) and deliberately excludes line numbers,
column numbers and engine node ids, all of which move on every edit. A flow
whose location changed but whose identity did not is reported as moved, not as
added plus removed.

Coverage is reported alongside the delta and gates independently: if the new
run analysed materially fewer files, or the engine itself reported the run as
truncated, the gate trips whatever --fail-on says. A half-broken build must not
render as a green diff."""
    loggers = [
        "atom_tools.lib.adapters",
        "atom_tools.lib.drift",
        "atom_tools.lib.unified",
        "atom_tools.lib.utils",
    ]

    def handle(self):
        """Executes the drift command."""

        from atom_tools.lib.adapters import parse_report
        from atom_tools.lib.drift import (
            GATE_EXIT_CODE,
            compute_drift,
            evaluate_gates,
            render_console,
            render_markdown,
        )
        from atom_tools.lib.utils import export_json

        output_format = self.option("format")
        if output_format not in FORMATS:
            raise ValueError(f"Unknown format: {output_format}. Known: {', '.join(FORMATS)}")
        engine = self.option("engine")
        reports = []
        for path, what in (
            (self.option("old"), "baseline report"),
            (self.option("new"), "current report"),
        ):
            if not path:
                raise ValueError("Both --old and --new are required.")
            reports.append(
                parse_report(load_json_report(path, what), source_file=path, engine=engine)
            )

        drift = compute_drift(reports[0], reports[1])
        for message in drift["diagnostics"]:
            logger.warning(message)

        if output_format == "json":
            export_json(drift, self.option("output-file"), 4)
            self.line(f"<info>Drift document written to {self.option('output-file')}.</info>")
        elif output_format == "markdown":
            self.line(render_markdown(drift))
        else:
            for line in render_console(drift):
                self.line(line)

        tripped, reasons = evaluate_gates(drift, self.option("fail-on"))
        if tripped:
            for reason in reasons:
                self.line(f"<error>gate tripped — {reason}</error>")
            return GATE_EXIT_CODE
        return 0

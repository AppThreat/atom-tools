"""Analyze Command for the atom-tools CLI."""

import logging
import os

from cleo.helpers import option

from atom_tools.cli.commands.command import Command
from atom_tools.lib.analysis_pipeline import analyze_source

logger = logging.getLogger(__name__)


class AnalyzeCommand(Command):
    """
    This command drives the atom CLI for any supported language and then
    post-processes the artefacts with atom-tools: merges chunked reachables,
    computes slice stats, extracts OpenAPI endpoints and exports SARIF.

    Attributes:
        name (str): The name of the command.
        description (str): The description of the command.
        options (list): The list of options for the command.
        help (str): The help message for the command.

    Methods:
        handle: Executes the command and performs the analysis.
    """

    name = "analyze"
    description = (
        "Analyse a source tree with atom and post-process the slices "
        "(merge, stats, OpenAPI, SARIF)."
    )
    options = [
        option(
            "language",
            "l",
            "atom language code: java, python, jssrc, jssrc/ts, c, ruby, php, "
            "jar, apk, scala, ...",
            flag=False,
            value_required=True,
        ),
        option(
            "input",
            "i",
            "Path to the source file or directory to analyse.",
            flag=False,
            default=".",
            value_required=True,
        ),
        option(
            "output",
            "o",
            "Directory to write reports to.",
            flag=False,
            default="reports",
        ),
        option(
            "atom-cmd",
            None,
            "Path to the atom command; resolved from PATH when omitted.",
            flag=False,
        ),
        option(
            "extract-endpoints",
            None,
            "Extract an OpenAPI document from the usages slice.",
            flag=True,
        ),
        option(
            "sarif",
            None,
            "Export the reachable slices to a SARIF document.",
            flag=True,
        ),
        option(
            "no-usages",
            None,
            "Skip the usages slice; only reachables are generated.",
            flag=True,
        ),
    ]
    help = """Analyse a source tree from end to end.

Runs `atom reachables` and `atom usages` (the reachables pass runs first so the
usages pass can reuse its atom), merges any chunked reachables files, computes
slice statistics, and - on request - extracts an OpenAPI document and writes a
SARIF report. Use this command to drive atom for any language the same way
apk-analysis does for Android."""

    loggers = ["atom_tools.lib.analysis_pipeline", "atom_tools.lib.apk_pipeline"]

    def handle(self):
        """
        Executes the analyze command.
        """
        language = self.option("language")
        if not language:
            self.line_error("<error>A language (-l) is required.</error>")
            return 1
        input_path = self.option("input")
        if not os.path.exists(input_path):
            self.line_error(f"<error>Input path not found: {input_path}</error>")
            return 1
        result = analyze_source(
            input_path,
            language,
            self.option("output"),
            atom_cmd=self.option("atom-cmd") or None,
            extract_endpoints=self.option("extract-endpoints"),
            generate_sarif=self.option("sarif"),
            skip_usages=self.option("no-usages"),
        )
        for artifact in (
            result.reachables_file,
            result.usages_file,
            result.openapi_file,
            result.sarif_file,
            result.stats_file,
        ):
            if artifact:
                self.line(f"<info>{artifact}</info>")
        if result.stats:
            reachables = result.stats.get("flow_groups")
            purls = result.stats.get("purls", {}).get("count")
            self.line(
                f"Analysed {input_path}: {reachables} reachable flow group(s), "
                f"{purls} reachable package(s)."
            )
        for error in result.errors:
            self.line_error(f"<error>{error}</error>")
        return 1 if result.errors else 0

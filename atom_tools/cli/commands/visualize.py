"""Visualize Command for the atom-tools CLI."""

import logging

from cleo.helpers import option

from atom_tools.cli.commands.command import Command
from atom_tools.lib.reachables import load_reachables
from atom_tools.lib.visualizer import (
    DEFAULT_LABEL_WRAP,
    VisualizationModel,
    load_bom,
    render_console,
    render_html,
    render_mermaid,
)

logger = logging.getLogger(__name__)


class VisualizeCommand(Command):
    """
    This command renders a reachable slice as a rich console report and as a
    mermaid.js flowchart, optionally enriched with a CycloneDX SBOM from
    cdxgen.

    Attributes:
        name (str): The name of the command.
        description (str): The description of the command.
        options (list): The list of options for the command.
        help (str): The help message for the command.

    Methods:
        handle: Executes the command and performs the rendering.
    """

    name = "visualize"
    description = (
        "Visualise reachable slices: rich console report plus a mermaid.js "
        "flowchart and an HTML page."
    )
    options = [
        option(
            "input-slice",
            "i",
            "Reachable slice file, glob pattern, or comma separated list. "
            "Sibling chunks such as reachables_1.json are picked up automatically.",
            flag=False,
            value_required=True,
        ),
        option(
            "output",
            "o",
            "Base path for the .mmd and .html outputs.",
            flag=False,
            default="reachables-viz",
        ),
        option(
            "bom",
            "b",
            "Optional CycloneDX SBOM (e.g. from cdxgen) used to enrich "
            "package nodes with licenses and report reachability coverage.",
            flag=False,
        ),
        option(
            "format",
            "f",
            "Renderers to run: all, console, mermaid or html.",
            flag=False,
            default="all",
        ),
        option(
            "max-flows",
            None,
            "Maximum number of flows drawn in the mermaid diagram. The most "
            "interesting flows (high risk sinks first) are kept.",
            flag=False,
            default="60",
        ),
        option(
            "label-wrap",
            None,
            "Soft width at which long diagram labels (relative paths, purls, "
            "sink expressions) are wrapped across lines. Labels are never "
            "truncated; pass 0 to keep each on a single line.",
            flag=False,
            default=str(DEFAULT_LABEL_WRAP),
        ),
        option(
            "mermaid-source",
            None,
            "Path to a local mermaid.min.js to embed in the HTML page so it "
            "renders offline (default: load mermaid.js from the CDN, which "
            "requires internet access).",
            flag=False,
        ),
    ]
    help = """Visualise reachable data flows.

Prints a rich console report (overview panel, per-file flow tree, reachable
package table) and writes a mermaid.js flowchart (``<output>.mmd``) plus a
single-file HTML page (``<output>.html``) that renders it. Sources are green,
high risk sinks (sql, ssrf, code-execution, ...) are red, other tagged sinks
orange, and the reached packages are purple hexagons carrying their license
when a SBOM is passed with -b.

The HTML page loads mermaid.js from the CDN by default, so viewing it needs
internet access; pass --mermaid-source with a local mermaid.min.js to embed
the renderer for offline use.

With a CycloneDX SBOM from cdxgen the report also shows how many SBOM
components the analysis proved reachable, so the diagram doubles as an SBOM
reachability review. Chunked reachable slices (reachables.json,
reachables_1.json, ...) are merged automatically."""

    loggers = [
        "atom_tools.lib.reachables",
        "atom_tools.lib.visualizer",
    ]

    def handle(self):
        """
        Executes the visualize command.
        """
        output_format = self.option("format")
        if output_format not in {"all", "console", "mermaid", "html"}:
            self.line_error(f"<error>Unknown format: {output_format}</error>")
            return 1
        try:
            max_flows = max(1, int(self.option("max-flows")))
        except ValueError:
            self.line_error(f"<error>Invalid --max-flows: {self.option('max-flows')}</error>")
            return 1
        try:
            label_wrap = max(0, int(self.option("label-wrap")))
        except ValueError:
            self.line_error(f"<error>Invalid --label-wrap: {self.option('label-wrap')}</error>")
            return 1

        entries = load_reachables(self.option("input-slice")).get("reachables", [])
        if not entries:
            self.line_error(
                "<error>No reachable entries found. Nothing to visualise.</error>"
            )
            return 1
        bom = None
        if self.option("bom"):
            bom = load_bom(self.option("bom"))
            if bom is None:
                self.line_error(
                    f"<error>Unable to read CycloneDX SBOM: {self.option('bom')}</error>"
                )
                return 1
        model = VisualizationModel.build(entries, bom)

        if output_format in {"all", "console"}:
            render_console(model)
            if model.bom_components:
                reachable = model.reachable_components
                total = len(model.bom_components)
                percent = (100 * reachable // total) if total else 0
                self.line(
                    f"<info>{reachable} of {total} SBOM components "
                    f"({percent}%) are proven reachable.</info>"
                )

        if output_format in {"all", "mermaid", "html"}:
            diagram = render_mermaid(model, max_flows, label_wrap)
            written = []
            if output_format in {"all", "mermaid"}:
                mmd_file = f"{self.option('output')}.mmd"
                with open(mmd_file, "w", encoding="utf-8") as f:
                    f.write(diagram)
                written.append(mmd_file)
            if output_format in {"all", "html"}:
                html_file = f"{self.option('output')}.html"
                mermaid_js = None
                if self.option("mermaid-source"):
                    try:
                        with open(self.option("mermaid-source"), "r", encoding="utf-8") as f:
                            mermaid_js = f.read()
                    except OSError as e:
                        self.line_error(
                            f"<error>Unable to read mermaid.min.js: {e}</error>"
                        )
                        return 1
                document = render_html(
                    model, diagram, self.option("input-slice"), mermaid_js=mermaid_js
                )
                with open(html_file, "w", encoding="utf-8") as f:
                    f.write(document)
                written.append(html_file)
            for path in written:
                self.line(f"<info>Written to {path}</info>")
        return 0

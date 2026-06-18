"""
APK Analysis Command for the atom-tools CLI.

Orchestrates blint and atom to analyse Android application files and presents
the results using rich.
"""

import logging
import os

from cleo.helpers import option

from atom_tools.cli.commands.command import Command
from atom_tools.lib.apk_pipeline import (
    analyze_app,
    build_cyclonedx_services,
    categorize_tags,
    check_prerequisites,
    collect_attribution,
    collect_behaviours,
    enrich_bom_with_services,
    find_apps,
    is_dangerous_permission,
    load_json,
    summarize_bom,
)
from atom_tools.lib.utils import export_json

logger = logging.getLogger(__name__)


def _direction(info: dict) -> str:
    """Describe a service's observed data-flow direction for presentation."""
    if info.get("local"):
        return "on-device"
    if info.get("egress") and info.get("ingress"):
        return "bi-directional"
    if info.get("ingress"):
        return "ingress"
    if info.get("egress"):
        return "egress"
    return "unknown"


def _attribution_to_json(attribution: dict) -> dict:
    """Convert a service/tracker attribution mapping into a JSON-serializable dict."""
    result = {}
    for name, info in sorted(attribution.items()):
        entry = {"categories": sorted(info["categories"]), "flows": info["flows"]}
        if "egress" in info:
            entry["direction"] = _direction(info)
        result[name] = entry
    return result


class ApkAnalysisCommand(Command):
    """
    Analyse Android application files using blint and atom.

    Attributes:
        name (str): The name of the command.
        description (str): The description of the command.
        options (list): The list of options for the command.
        help (str): The help message for the command.

    Methods:
        handle: Executes the command and performs the analysis.
    """

    name = "apk-analysis"
    description = "Analyse Android apps (apk/apkm/aab) using blint and atom."
    options = [
        option(
            "input",
            "i",
            "Path to an apk/apkm/aab file or a directory containing them.",
            flag=False,
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
            "no-deep",
            None,
            "Disable blint deep mode (deep parsing of dex classes is on by default).",
            flag=True,
        ),
        option("skip-atom", None, "Skip atom usage and reachable slicing.", flag=True),
        option(
            "blint-venv",
            None,
            "Path to a blint virtual environment, its bin directory, or the blint executable.",
            flag=False,
            value_required=True,
        ),
        option(
            "format",
            "f",
            "Presentation format: table or json.",
            flag=False,
            default="table",
        ),
    ]
    help = """The apk-analysis command analyses Android application files.

It invokes blint to generate a CycloneDX SBOM and atom to generate usage and
reachable slices, then presents a consolidated report. blint runs in deep mode by
default so dex classes are parsed for service / tracker detection; pass --no-deep
to skip that. Use --skip-atom to only generate the SBOM, and --blint-venv to point
at a blint installed in its own virtual environment."""
    loggers = ["atom_tools.lib.apk_pipeline"]

    def handle(self):
        """
        Executes the apk-analysis command.
        """
        input_path = self.option("input")
        if not input_path or not os.path.exists(input_path):
            self.line_error(f"<error>Input path not found: {input_path}</error>")
            return 1
        reports_dir = self.option("output")
        skip_atom = self.option("skip-atom")
        # Deep mode is on by default: blint only parses dex classes (the signal used
        # for service / tracker detection) in deep mode.
        deep = not self.option("no-deep")

        tools = check_prerequisites(skip_atom, self.option("blint-venv"))
        if not self._verify_tools(tools, skip_atom):
            return 1

        apps = find_apps(input_path)
        if not apps:
            self.line_error(f"<error>No apk/apkm/aab files found at {input_path}</error>")
            return 1
        os.makedirs(reports_dir, exist_ok=True)

        output_format = self.option("format")
        for app in apps:
            self.line(f"<info>Analysing {os.path.basename(app)}</info>")
            analysis = analyze_app(app, reports_dir, tools, deep, skip_atom)
            reachables = load_json(analysis.reachables_file)
            bom_doc = load_json(analysis.bom_file)
            services, trackers = collect_attribution(reachables)
            # Promote the detected services into the SBOM so the BOM records the
            # remote services the app actually reaches, and persist the enriched BOM.
            cdx_services = build_cyclonedx_services(services)
            if bom_doc is not None and cdx_services and analysis.bom_file:
                enrich_bom_with_services(bom_doc, cdx_services)
                export_json(bom_doc, analysis.bom_file, 4)
            bom = summarize_bom(bom_doc)
            behaviours = collect_behaviours(bom_doc)
            tags = categorize_tags(reachables)
            if output_format == "json":
                self._write_json(analysis, bom, tags, services, trackers, behaviours, reports_dir)
            else:
                self._render(analysis, bom, tags, services, trackers, behaviours)
        return 0

    def _verify_tools(self, tools, skip_atom):
        """Verify required external tools are available and report otherwise."""
        if not tools.get("blint"):
            self.line_error(
                "<error>blint command not found.</error> Install it with "
                "<comment>pip install blint</comment> or use the atom-tools container image."
            )
            return False
        if not skip_atom and not tools.get("atom"):
            self.line_error(
                "<error>atom command not found.</error> Install it with "
                "<comment>npm install -g @appthreat/atom</comment> (requires a JVM and "
                "ANDROID_HOME), use --skip-atom, or use the atom-tools container image."
            )
            return False
        return True

    def _write_json(self, analysis, bom, tags, services, trackers, behaviours, reports_dir):
        """Write a consolidated analysis document to disk."""
        out_file = os.path.join(
            reports_dir, f"{os.path.basename(analysis.app_file)}.analysis.json"
        )
        export_json(
            {
                "app": analysis.app_file,
                "reports": {
                    "bom": analysis.bom_file,
                    "usages": analysis.usages_file,
                    "reachables": analysis.reachables_file,
                    "callgraph": analysis.callgraph_file,
                },
                "summary": bom,
                "findings": tags,
                "services": _attribution_to_json(services),
                "trackers": _attribution_to_json(trackers),
                "behaviours": behaviours,
                "errors": analysis.errors,
            },
            out_file,
            4,
        )
        self.line(f"<info>Analysis written to {out_file}</info>")

    def _render(self, analysis, bom, tags, services, trackers, behaviours):
        """Render the analysis to the console using rich."""
        from rich.console import Console
        from rich.panel import Panel
        from rich.table import Table

        console = Console()
        meta = bom["properties"]
        summary_lines = [
            f"[bold]Package[/bold]: {bom['name']} {bom['version']}",
            f"[bold]Min SDK[/bold]: {meta.get('internal:minSdkVersion', '?')}  "
            f"[bold]Target SDK[/bold]: {meta.get('internal:targetSdkVersion', '?')}",
            f"[bold]Components[/bold]: {len(bom['components'])}  "
            f"[bold]Permissions[/bold]: {len(bom['permissions'])}",
        ]
        if meta.get("internal:architectures"):
            summary_lines.append(f"[bold]Architectures[/bold]: {meta['internal:architectures']}")
        console.print(Panel("\n".join(summary_lines), title=os.path.basename(analysis.app_file)))

        if bom["permissions"]:
            perm_table = Table(title="Permissions", show_lines=False)
            perm_table.add_column("Permission")
            perm_table.add_column("Risk")
            for perm in bom["permissions"]:
                dangerous = is_dangerous_permission(perm)
                perm_table.add_row(
                    perm,
                    "[red]dangerous[/red]" if dangerous else "normal",
                )
            console.print(perm_table)

        if tags:
            findings = Table(title="Reachable findings", show_lines=False)
            findings.add_column("Category")
            findings.add_column("Tag")
            findings.add_column("Flows", justify="right")
            for category, matches in tags.items():
                for tag, count in matches.items():
                    findings.add_row(category, tag, str(count))
            console.print(findings)
        elif analysis.reachables_file:
            console.print("[dim]No android-specific tags found in reachable slices.[/dim]")

        if services:
            svc_table = Table(title="Reachable services (data egress / ingress)")
            svc_table.add_column("Service")
            svc_table.add_column("Category")
            svc_table.add_column("Direction")
            svc_table.add_column("Flows", justify="right")
            for name in sorted(services):
                info = services[name]
                svc_table.add_row(
                    name,
                    ", ".join(sorted(info["categories"])) or "-",
                    _direction(info),
                    str(info["flows"]),
                )
            console.print(svc_table)

        if trackers:
            trk_table = Table(title="Reachable trackers / SDKs")
            trk_table.add_column("Tracker")
            trk_table.add_column("Category")
            trk_table.add_column("Flows", justify="right")
            for name in sorted(trackers):
                info = trackers[name]
                trk_table.add_row(
                    name,
                    ", ".join(sorted(info["categories"])) or "-",
                    str(info["flows"]),
                )
            console.print(trk_table)

        if behaviours:
            sev_colour = {
                "critical": "bold red",
                "high": "red",
                "medium": "yellow",
                "low": "cyan",
                "info": "dim",
            }
            beh_table = Table(title="Static behaviours (blint dex review)")
            beh_table.add_column("Behaviour")
            beh_table.add_column("Severity")
            beh_table.add_column("Sites", justify="right")
            beh_table.add_column("Example")
            for behaviour in behaviours:
                severity = behaviour["severity"]
                colour = sev_colour.get(severity, "white")
                beh_table.add_row(
                    behaviour["id"],
                    f"[{colour}]{severity}[/{colour}]",
                    str(behaviour["count"]),
                    (behaviour.get("evidence") or "")[:60],
                )
            console.print(beh_table)

        if analysis.callgraph_file:
            console.print(f"[dim]Dalvik callgraph written to {analysis.callgraph_file}[/dim]")

        for error in analysis.errors:
            console.print(f"[yellow]Warning:[/yellow] {error}")

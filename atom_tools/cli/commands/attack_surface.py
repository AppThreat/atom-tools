"""Attack Surface Command for the atom-tools CLI."""

import logging

from cleo.helpers import option

from atom_tools.cli.commands.command import Command

logger = logging.getLogger(__name__)

FORMATS = ("json", "console", "html")


class AttackSurfaceCommand(Command):
    """
    This command groups a report's entry points by exposure tier and reports
    what each one reaches, in the shape of dosai's own ``AttackSurface[]``
    view — for dosai, golem, rusi, kosi and atom alike.
    """

    name = "attack-surface"
    description = (
        "Group entry points by exposure tier and report what each reaches"
        " (dosai's AttackSurface view, for every engine)."
    )
    options = [
        option(
            "input-slice",
            "i",
            "Report file(s): dosai dataflows/methods, golem analyze, rusi"
            " analyze, atom reachables or atom usages slices. Comma separated"
            " lists and globs are supported, and engines can be mixed freely.",
            flag=False,
            value_required=True,
        ),
        option(
            "output-file",
            "o",
            "Output path: the json document with -f json, or the base path for"
            " the .mmd and .html files with -f html.",
            flag=False,
            default="attack-surface",
            value_required=True,
        ),
        option(
            "format",
            "f",
            f"Output format(s), comma separated: {', '.join(FORMATS)}.",
            flag=False,
            default="console",
            value_required=True,
        ),
        option(
            "min-exposure",
            None,
            "Only report tiers at least this exposed. One of the documented"
            " tier names (anonymous-http is the most exposed). Tiers whose"
            " authentication is unknown never match the filter and are counted"
            " in a note instead.",
            flag=False,
            value_required=True,
        ),
        option(
            "max-entries",
            None,
            "Maximum number of entry points listed in the console and diagram"
            " renderings. The json output always carries every entry point.",
            flag=False,
            default="200",
            value_required=True,
        ),
    ]
    help = """Report an application's attack surface: which entry points exist,
how they are exposed, and what each one reaches.

Only dosai classifies authentication (its own AttackSurface array is used
verbatim, never re-derived); every other engine's entry points land in the
unknown-auth tier, which is rendered as a gap rather than as a verdict. For
golem, rusi and kosi, reach is computed by anchoring each endpoint's handler in the
engine's call graph and attaching the flows whose source function falls inside
its transitive closure. Endpoints that cannot be anchored report
seed-not-found; endpoints with no call graph report reach as not computed.
"Reaches nothing" and "not computed" are opposite findings and always render
differently."""
    loggers = [
        "atom_tools.lib.adapters",
        "atom_tools.lib.attack_surface",
        "atom_tools.lib.unified",
        "atom_tools.lib.utils",
        "atom_tools.lib.visualizer",
    ]

    def handle(self):
        """Executes the attack-surface command."""

        from atom_tools.lib.adapters import parse_report
        from atom_tools.lib.attack_surface import (
            SurfaceInput,
            compute_attack_surface,
            is_usages_slice,
            render_console,
            render_html,
            render_mermaid,
        )
        from atom_tools.lib.reachables import expand_inputs, load_json_report
        from atom_tools.lib.utils import export_json

        # The spec's invocation is --format console,html; several renderings
        # from one computation are the point, so a list is accepted everywhere.
        formats = [f.strip() for f in str(self.option("format")).split(",") if f.strip()]
        unknown = [f for f in formats if f not in FORMATS]
        if unknown:
            raise ValueError(f"Unknown format: {unknown[0]}. Known: {', '.join(FORMATS)}")
        try:
            max_entries = max(1, int(self.option("max-entries")))
        except ValueError:
            raise ValueError(f"Invalid --max-entries: {self.option('max-entries')}") from None

        files = expand_inputs(self.option("input-slice"))
        if not files:
            # expand_inputs has already warned about every unmatched part.
            return 1

        inputs = []
        for path in files:
            content = load_json_report(path)
            if is_usages_slice(content):
                # Usages slices are not flow reports; the converter in the
                # library turns them into endpoints.
                inputs.append(SurfaceInput(report=None, raw=content, path=path))
                continue
            report = parse_report(content, source_file=path)
            inputs.append(SurfaceInput(report=report, raw=content, path=path))

        document = compute_attack_surface(
            inputs, min_exposure=self.option("min-exposure") or ""
        )
        # The console rendering prints these itself, next to the numbers they
        # qualify; only the file formats need the log copy.
        if formats != ["console"]:
            for message in document["diagnostics"]:
                logger.warning(message)

        for output_format in formats:
            if output_format == "json":
                export_json(document, self.option("output-file"), 4)
                self.line(
                    f"<info>Attack surface with {document['summary']['entryPoints']}"
                    f" entry point(s) written to {self.option('output-file')}.</info>"
                )
            elif output_format == "html":
                diagram = render_mermaid(document)
                mmd_file = f"{self.option('output-file')}.mmd"
                with open(mmd_file, "w", encoding="utf-8") as f:
                    f.write(diagram)
                html_file = f"{self.option('output-file')}.html"
                with open(html_file, "w", encoding="utf-8") as f:
                    f.write(render_html(document, diagram, self.option("input-slice")))
                self.line(f"<info>Written to {mmd_file}</info>")
                self.line(f"<info>Written to {html_file}</info>")
            else:
                for line in render_console(document, max_entries):
                    self.line(line)
        return 0

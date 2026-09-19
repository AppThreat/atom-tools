"""Ingest Command for the atom-tools CLI."""

import logging

from cleo.helpers import option

from atom_tools.cli.commands.command import Command
from atom_tools.lib.adapters import detect_engine, parse_report
from atom_tools.lib.reachables import expand_inputs, load_json_report
from atom_tools.lib.unified import merge_reports, to_reachables_document
from atom_tools.lib.utils import export_json

logger = logging.getLogger(__name__)

KNOWN_ENGINES = ("atom", "dosai", "golem", "rusi")


class IngestCommand(Command):
    """
    This command normalises flow reports from any AppThreat ecosystem engine
    (atom, dosai, golem, rusi) into one unified flow model — or, with
    ``--emit reachables``, into an atom-compatible document every existing
    atom-tools command already understands.
    """

    name = "ingest"
    description = (
        "Normalise dosai, golem, rusi or atom flow reports into the unified"
        " flow model (or an atom-compatible reachables document)."
    )
    options = [
        option(
            "input-slice",
            "i",
            "Report file(s): dosai dataflows/methods, golem analyze, rusi analyze"
            " or atom reachables. Comma separated lists and globs are supported,"
            " and engines can be mixed freely.",
            flag=False,
            value_required=True,
        ),
        option(
            "output-file",
            "o",
            "Output file for the unified (or reachables) document.",
            flag=False,
            default="unified-flows.json",
            value_required=True,
        ),
        option(
            "emit",
            None,
            "Output form: 'unified' (the model document, default) or"
            " 'reachables' (an atom-compatible document that stats, visualize,"
            " convert, check-reachable and filter already consume).",
            flag=False,
            default="unified",
            value_required=True,
        ),
        option(
            "engine",
            None,
            "Force the producing engine (atom, dosai, golem, rusi) instead of"
            " detecting it from the report envelope.",
            flag=False,
            value_required=True,
        ),
    ]
    help = """Normalise engine reports into one flow model.

The producing engine is detected from the report envelope (Dosai's
Metadata.Tool, golem/rusi's tool.name). Every flow is hydrated — engine node
id references are joined against the report's node table, with unresolvable
ids dropped and diagnosed, never silently — and carries severity provenance
(the engine's own severity where it emits one, taxonomy-derived otherwise),
truncated-witness flags and the raw engine record as an escape hatch.

With --emit reachables the output loads through the existing atom slice
loader, so stats, visualize, convert -f sarif, check-reachable and filter all
work on dosai, golem and rusi reports unchanged."""
    loggers = [
        "atom_tools.lib.adapters",
        "atom_tools.lib.reachables",
        "atom_tools.lib.unified",
        "atom_tools.lib.utils",
    ]

    def handle(self):
        """Executes the ingest command."""
        emit = self.option("emit")
        if emit not in ("unified", "reachables"):
            raise ValueError(f"Unknown emit format: {emit}")
        engine = self.option("engine")
        if engine and engine not in KNOWN_ENGINES:
            raise ValueError(f"Unknown engine: {engine}. Known: {', '.join(KNOWN_ENGINES)}")
        files = expand_inputs(self.option("input-slice"))
        if not files:
            # expand_inputs has already warned about every unmatched part.
            return 1

        reports, compat_entries, endpoint_sections = [], [], {}
        for path in files:
            content = load_json_report(path)
            detected = engine or detect_engine(content)
            if detected is None and (
                isinstance(content, list) or isinstance(content, dict) and "reachables" in content
            ):
                detected = "atom"
            if detected is None:
                raise ValueError(
                    f"Could not detect the producing engine for {path};"
                    " re-run with --engine atom|dosai|golem|rusi."
                )
            report = parse_report(content, source_file=path, engine=detected)
            reports.append(report)
            document = to_reachables_document(report, original=content)
            compat_entries.extend(document["reachables"])
            for key in ("apiEndpoints", "api_endpoints"):
                if key in document:
                    endpoint_sections.setdefault(key, []).extend(document[key])

        if emit == "reachables":
            export_json(
                {"reachables": compat_entries, **endpoint_sections}, self.option("output-file"), 4
            )
            self.line(
                f"<info>Reachables document with {len(compat_entries)} flow group(s)"
                f" written to {self.option('output-file')}.</info>"
            )
            return 0
        merged = merge_reports(reports)
        export_json(merged.to_dict(), self.option("output-file"), 4)
        self.line(
            f"<info>Unified report with {len(merged.flows)} flow(s) from"
            f" {len(files)} file(s) written to {self.option('output-file')}.</info>"
        )
        return 0

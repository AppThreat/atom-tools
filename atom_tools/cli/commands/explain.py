"""Explain Command for the atom-tools CLI."""

import logging

from cleo.helpers import option

from atom_tools.cli.commands.command import Command

logger = logging.getLogger(__name__)

FORMATS = ("text", "markdown", "agent")


class ExplainCommand(Command):
    """
    This command renders a report's flows as deterministic, citable sentences
    — for a reviewer or for an agent. No model call: every clause maps to a
    field in the unified flow model, and where a field is empty the clause is
    omitted or hedged, never filled with a plausible default.
    """

    name = "explain"
    description = (
        "Explain flows in words: deterministic, template-driven narratives over"
        " any engine report or unified document (text, markdown or agent JSON)."
    )
    options = [
        option(
            "input-slice",
            "i",
            "Report file(s): dosai dataflows/methods, golem analyze, rusi"
            " analyze, atom reachables or a unified document from ingest."
            " Comma separated lists and globs are supported.",
            flag=False,
            value_required=True,
        ),
        option(
            "output-file",
            "o",
            "Write the rendering here instead of the console (the natural home"
            " for -f agent and -f markdown).",
            flag=False,
            default="",
            value_required=True,
        ),
        option(
            "format",
            "f",
            f"Output format: {', '.join(FORMATS)}. 'agent' is compact,"
            " token-budgeted JSON over the whole report; 'markdown' is"
            " PR-attachable.",
            flag=False,
            default="text",
            value_required=True,
        ),
        option(
            "flow",
            None,
            "Explain one flow by its exact id (text and markdown formats).",
            flag=False,
            value_required=True,
        ),
        option(
            "package",
            None,
            "Explain the flows whose purls contain this string"
            " (case-insensitive substring; text and markdown formats).",
            flag=False,
            value_required=True,
        ),
        option(
            "file",
            None,
            "Explain the flows with any node in this file (suffix match on"
            " normalised path separators; text and markdown formats).",
            flag=False,
            value_required=True,
        ),
        option(
            "query",
            None,
            "dosai's compact query grammar over the model:"
            " 'flows[sink_category=sql && severity=error]', with 'sort by prop"
            " [desc]' and 'count' postfixes. Collections are flows, endpoints,"
            " packages; a flow also exposes dotted source./sink. paths (an"
            " atom-tools addition). Overlaps 'filter' on atom slices; filter is"
            " kept as-is for compatibility.",
            flag=False,
            value_required=True,
        ),
        option(
            "max-flows",
            None,
            "Maximum flow narratives listed in text and markdown renderings"
            " (the remainder is counted in a 'truncated: N more' marker).",
            flag=False,
            default="10",
            value_required=True,
        ),
        option(
            "max-tokens",
            None,
            "Token budget for -f agent, counted as characters/4 of the"
            " serialized JSON — an estimate, not a real tokeniser.",
            flag=False,
            default="4000",
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
        option(
            "old",
            None,
            "With --mcp only: baseline report for the atom.drift tool, loaded"
            " at startup (tools never touch the filesystem).",
            flag=False,
            value_required=True,
        ),
        option("mcp", None, "Run a read-only stdio MCP server over the loaded report.", flag=True),
    ]
    help = """Explain flows in words, deterministically.

The narrative is assembled from facts already in the model — nothing is
generated, so the output is reproducible, citable and safe in CI:

  Flow seam-slice|sha256:… — http-input → http-response
    Reachability: `pkg:golang/...` is reached from `GET /dsc/webkit`
    (routes.go:230); golem does not classify authentication, so the route's
    exposure is unknown.
    Path: source `Query` (dsc.go:489) tagged `http-input` which reaches `JSON`
    (context.go:232) in 8 step(s), classified `http-response`.
    Evidence: golem 3.2.0, all mode. Severity `warning` (engine-reported).
    Sanitizer: No sanitizer reported on this path by golem's sanitizer
    analysis; this run found none to report.

Honesty rules, measured on the committed fixtures: only dosai classifies
authentication (every other engine's entry points are unknown-auth, and the
sentence says so); the endpoint→flow join is partial (31 of 57 golem
endpoints anchor; dosai flows carry no entry-point reference at all) and an
unjoined flow says so instead of dropping the clause; atom slices carry no
version, so none is printed; the sanitizer sentence appears only for engines
whose slice schema carries a sanitizer field (dosai, golem), phrased as
reported absence — for rusi and atom it is omitted entirely.

--format agent emits dosai agent-context-shaped JSON (summary, entry points,
high-risk flows, reachable packages, relevant files, suggested next
commands) for the whole report, under --max-tokens, trimmed with an
unmissable 'truncated: N more' marker so a consuming agent knows it is not
seeing everything. Selectors (--flow/--package/--file/--query) apply to the
text and markdown formats only.

--mcp starts a read-only, file-scoped stdio MCP server (requires the mcp
extra: pip install 'atom-tools[mcp]') exposing atom.explain_flow,
atom.attack_surface, atom.drift, atom.graph_hotspots and atom.query. It
never invokes an engine, shells out, or reads a file other than the report
(and optional --old baseline) given at startup.

The query grammar is dosai's, operator for operator — ~= != >= <= = > < in
that match order, ~= a case-insensitive contains, && AND of conjuncts, ||
OR within one, 'sort by prop [desc]' and 'count' postfixes — over the
unified model's collections (flows, endpoints, packages) instead of dosai's
report paths, and with source./sink. paths on flows as a deliberate
addition."""
    loggers = [
        "atom_tools.lib.adapters",
        "atom_tools.lib.attack_surface",
        "atom_tools.lib.explain",
        "atom_tools.lib.query",
        "atom_tools.lib.unified",
        "atom_tools.lib.utils",
    ]

    def handle(self):
        """Executes the explain command."""
        import json

        from atom_tools.lib.adapters import parse_report
        from atom_tools.lib.attack_surface import SurfaceInput, is_usages_slice
        from atom_tools.lib.explain import (
            build_agent_document,
            build_context,
            find_flow,
            flows_for_file,
            flows_for_package,
            run_query_text,
        )
        from atom_tools.lib.reachables import expand_inputs, load_json_report

        output_format = self.option("format")
        if output_format not in FORMATS:
            raise ValueError(f"Unknown format: {output_format}. Known: {', '.join(FORMATS)}")
        selectors = {
            name: self.option(name)
            for name in ("flow", "package", "file", "query")
            if self.option(name)
        }
        if len(selectors) > 1:
            raise ValueError(
                "Pick at most one of --flow, --package, --file and --query"
                f" (got: {', '.join(sorted(selectors))})."
            )

        files = expand_inputs(self.option("input-slice"))
        if not files:
            # expand_inputs has already warned about every unmatched part.
            return 1
        inputs = []
        for path in files:
            content = load_json_report(path)
            if is_usages_slice(content):
                inputs.append(SurfaceInput(report=None, raw=content, path=path))
                continue
            inputs.append(
                SurfaceInput(
                    report=parse_report(content, source_file=path, engine=self.option("engine")),
                    raw=content,
                    path=path,
                )
            )
        ctx = build_context(inputs)

        if self.option("mcp"):
            if selectors:
                raise ValueError("--mcp ignores --flow/--package/--file/--query.")
            return self._run_mcp(ctx)

        try:
            max_flows = max(0, int(self.option("max-flows")))
            max_tokens = max(1, int(self.option("max-tokens")))
        except ValueError:
            raise ValueError("--max-flows and --max-tokens must be integers.") from None

        if output_format == "agent":
            if selectors:
                raise ValueError(
                    "--format agent renders the whole report; --flow/--package/"
                    "--file/--query apply to text and markdown."
                )
            text = json.dumps(build_agent_document(ctx, max_tokens), indent=2, sort_keys=True) + "\n"
        elif "flow" in selectors:
            text = self._render_flow(ctx, find_flow(ctx.report, selectors["flow"]), output_format)
        elif "query" in selectors:
            result_line, flows = run_query_text(ctx, selectors["query"])
            text = result_line + "\n" if flows is None else self._render_listing(
                ctx, flows, result_line, output_format, max_flows
            )
        else:
            if "package" in selectors:
                flows = flows_for_package(ctx.report, selectors["package"])
                heading = (
                    f"{len(flows)} flow(s) reach package(s) matching"
                    f" '{selectors['package']}':"
                )
            elif "file" in selectors:
                flows = flows_for_file(ctx.report, selectors["file"])
                heading = f"{len(flows)} flow(s) touch file '{selectors['file']}':"
            else:
                flows, heading = None, ""
            text = self._render_listing(ctx, flows, heading, output_format, max_flows)

        if self.option("output-file"):
            with open(self.option("output-file"), "w", encoding="utf-8") as f:
                f.write(text)
            self.line(f"<info>Explanation written to {self.option('output-file')}.</info>")
        else:
            self.line(text.rstrip("\n"))
        return 0

    def _render_flow(self, ctx, flow, output_format) -> str:
        from atom_tools.lib.explain import explain_flow_lines, render_flow_markdown

        if output_format == "markdown":
            return render_flow_markdown(flow, ctx)
        return "\n".join(explain_flow_lines(flow, ctx)) + "\n"

    def _render_listing(self, ctx, flows, heading, output_format, max_flows) -> str:
        if output_format == "markdown":
            from atom_tools.lib.explain import render_markdown

            return render_markdown(ctx, flows, max_flows, heading)
        from atom_tools.lib.explain import render_text

        return render_text(ctx, flows, max_flows, heading)

    def _run_mcp(self, ctx) -> int:

        from atom_tools.lib.adapters import parse_report
        from atom_tools.lib.explain import build_mcp_server
        from atom_tools.lib.reachables import load_json_report

        baseline = None
        if self.option("old"):
            baseline = parse_report(
                load_json_report(self.option("old"), "baseline report"),
                source_file=self.option("old"),
            )
        try:
            server = build_mcp_server(ctx, baseline)
        except ModuleNotFoundError as error:
            self.line(
                "<error>--mcp needs the mcp package (v1 API): pip install"
                f" 'atom-tools[mcp]'. ({error})</error>"
            )
            return 1
        # Nothing may touch stdout from here: the stdio transport speaks
        # JSON-RPC on it, and a friendly banner would corrupt the protocol.
        logger.info("Starting read-only MCP server (5 atom.* tools).")
        server.run(transport="stdio")
        return 0

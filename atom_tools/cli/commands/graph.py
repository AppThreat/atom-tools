"""Graph Command for the atom-tools CLI."""

import logging

from cleo.helpers import option

from atom_tools.cli.commands.command import Command

logger = logging.getLogger(__name__)

FORMATS = ("json", "console", "mermaid")
EXPORTS = ("graphml", "gexf")
METRICS = (
    "chokepoints",
    "centrality",
    "blast-radius",
    "entry-depth",
    "dead-code",
    "cycles",
)
CONFIDENCE = ("exact", "external", "candidate", "unknown")


class GraphCommand(Command):
    """
    This command reads the call graph four engines emit — golem callGraph,
    rusi call_graph, dosai CallGraph+Reachability, atom export --format
    graphml — and computes one metric over it: chokepoints (betweenness over
    flow source→sink paths), centrality, blast radius, entry depth,
    dead-code (the engine's verdict, never derived), or recursion clusters.
    """

    name = "graph"
    description = (
        "Compute a call-graph metric — chokepoints, centrality, blast radius,"
        " entry depth, dead-code or cycles — over engine call graphs."
    )
    options = [
        option(
            "input-slice",
            "i",
            "Report file(s) carrying a call graph: golem analyze, rusi"
            " analyze, dosai methods, or atom export --format graphml. Comma"
            " separated lists and globs are supported, and engines can be"
            " mixed freely.",
            flag=False,
            value_required=True,
        ),
        option(
            "metric",
            None,
            f"One of: {', '.join(METRICS)}. Default: chokepoints.",
            flag=False,
            value_required=True,
        ),
        option(
            "blast-radius",
            None,
            "Node to measure the blast radius of (a call-graph node id or a"
            " unique function name); selects the blast-radius metric.",
            flag=False,
            value_required=True,
        ),
        option(
            "min-confidence",
            None,
            f"Keep only edges at or above this confidence tier: {', '.join(CONFIDENCE)}."
            " Tiers are mapped from each engine's own vocabulary (rusi call"
            " types, dosai DispatchConfidence/EvidenceKind, atom dispatch"
            " types); a filter that cannot reduce a graph (golem is 100%"
            " static) says so instead of passing silently.",
            flag=False,
            value_required=True,
        ),
        option(
            "include-external",
            None,
            "Include external (out-of-workspace) nodes in rankings. Off by"
            " default: most engines' graphs are dominated by third-party"
            " leaf calls, which a ranking should not be.",
        ),
        option(
            "algorithms",
            None,
            "atom 'algorithms' JSON output(s) (centrality and/or scc) to join"
            " verbatim; only meaningful for atom graphml inputs, which their"
            " method names are keyed by.",
            flag=False,
            value_required=True,
        ),
        option(
            "top",
            None,
            "Ranked entries shown in the console and diagram renderings."
            " The json output always carries every entry.",
            flag=False,
            default="15",
            value_required=True,
        ),
        option(
            "max-chokepoint-sources",
            None,
            "Cap on the source nodes whose paths the chokepoint metric"
            " enumerates. When the cap binds the output says so and the"
            " scores are a lower bound.",
            flag=False,
            default="64",
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
            "output-file",
            "o",
            "Output path: the json document with -f json, the .mmd diagram"
            " with -f mermaid, or the base path for --export graphml/gexf"
            " (the extension is appended unless the path already ends with"
            " it).",
            flag=False,
            default="call-graph",
            value_required=True,
        ),
        option(
            "export",
            None,
            f"Export the unified graph(s) as: {', '.join(EXPORTS)}. Key"
            " vocabulary matches dosai's own exporters so artefacts"
            " interoperate with yEd, Gephi and NetworkX.",
            flag=False,
            value_required=True,
        ),
    ]
    help = """Read a call graph and rank what matters about it.

golem tells you which flows exist; the call graph tells you which single
function sits on most of the paths between them — which is where a fix is
cheapest. Where an engine already computes a metric (dosai's fanIn/fanOut
and DepthFromEntryPoint, golem's reachableFromRoots, dosai's
RecursionClusters), the engine's value is used verbatim and provenance
labeled; recomputed values say so (severitySource made the same distinction
for flows).

Engine metrics arrive joined from separate sections (dosai's Reachability[]
is a top-level array keyed by NodeId, not a CallGraph.Nodes property), and
they describe the engine's full run even when the committed call graph is a
slice of it — so a recomputation over the slice's own edges disagrees by
design, and that disagreement is reported rather than reconciled.

Dead-code is never derived: on a sliced call graph, "no reachable entry
point" describes the slice, not the program, and announcing deletable
functions from it would be this command's most damaging wrong answer. The
engine's own dead-code data (dosai DeadCode[], golem reachability from
roots) is reported with its definition attached, and nothing else."""
    loggers = [
        "atom_tools.lib.adapters",
        "atom_tools.lib.callgraph",
        "atom_tools.lib.unified",
        "atom_tools.lib.utils",
        "atom_tools.lib.visualizer",
    ]

    def handle(self):
        """Executes the graph command."""

        from atom_tools.lib.adapters import parse_report
        from atom_tools.lib.callgraph import (
            CONFIDENCE_TIERS,
            METRICS as LIB_METRICS,
            compute_graph_document,
            flow_functions,
            load_call_graph,
            render_console,
            render_mermaid,
        )
        from atom_tools.lib.reachables import expand_inputs, load_json_report
        from atom_tools.lib.utils import export_json

        formats = [f.strip() for f in str(self.option("format")).split(",") if f.strip()]
        unknown = [f for f in formats if f not in FORMATS]
        if unknown:
            raise ValueError(f"Unknown format: {unknown[0]}. Known: {', '.join(FORMATS)}")
        exports = [e.strip() for e in str(self.option("export") or "").split(",") if e.strip()]
        bad_exports = [e for e in exports if e not in EXPORTS]
        if bad_exports:
            raise ValueError(
                f"Unknown export format: {bad_exports[0]}. Known: {', '.join(EXPORTS)}"
            )
        metric = self.option("metric") or ""
        blast_node = self.option("blast-radius") or ""
        if blast_node:
            if metric and metric != "blast-radius":
                raise ValueError(
                    "--blast-radius selects the blast-radius metric;"
                    f" --metric {metric} contradicts it."
                )
            metric = "blast-radius"
        metric = metric or "chokepoints"
        if metric not in LIB_METRICS:
            raise ValueError(f"Unknown metric: {metric}. Known: {', '.join(LIB_METRICS)}")
        min_confidence = self.option("min-confidence") or ""
        if min_confidence and min_confidence not in CONFIDENCE_TIERS:
            raise ValueError(
                f"Unknown confidence: {min_confidence}. Known: {', '.join(CONFIDENCE_TIERS)}"
            )
        try:
            top = max(1, int(self.option("top")))
        except ValueError:
            raise ValueError(f"Invalid --top: {self.option('top')}") from None
        try:
            max_sources = max(1, int(self.option("max-chokepoint-sources")))
        except ValueError:
            raise ValueError(
                f"Invalid --max-chokepoint-sources: {self.option('max-chokepoint-sources')}"
            ) from None

        files = expand_inputs(self.option("input-slice"))
        if not files:
            # expand_inputs has already warned about every unmatched part.
            return 1

        graphs = []
        flow_sources, flow_sinks = set(), set()
        endpoints_by_source = {}
        for path in files:
            if str(path).endswith((".graphml", ".graph-ml")):
                graphs.append(load_call_graph(path))
                continue
            content = load_json_report(path)
            graphs.append(load_call_graph(path, content))
            report = parse_report(content, source_file=path)
            sources, sinks = flow_functions(report)
            flow_sources |= sources
            flow_sinks |= sinks
            endpoints_by_source[path] = report.endpoints

        algorithms = {}
        if self.option("algorithms"):
            non_atom = [g.engine for g in graphs if g.engine != "atom"]
            if non_atom:
                raise ValueError(
                    "--algorithms joins atom's own method names, which only an"
                    " atom graphml input carries; got engine(s):"
                    f" {', '.join(sorted(set(non_atom)))}."
                )
            for algo_file in expand_inputs(self.option("algorithms")):
                algo_doc = load_json_report(algo_file, "algorithms document")
                if "ranking" in algo_doc:
                    algorithms["centrality"] = algo_doc
                elif "componentCount" in algo_doc:
                    algorithms["scc"] = algo_doc
                else:
                    raise ValueError(
                        f"{algo_file} is not a recognisable atom algorithms"
                        " output (expected a 'ranking' or 'componentCount' key)."
                    )

        document = compute_graph_document(
            graphs,
            metric,
            flow_sources=flow_sources,
            flow_sinks=flow_sinks,
            endpoints_by_source=endpoints_by_source,
            min_confidence=min_confidence,
            include_external=bool(self.option("include-external")),
            blast_radius_node=blast_node,
            max_chokepoint_sources=max_sources,
            algorithms=algorithms,
        )
        if formats != ["console"]:
            for message in document["diagnostics"]:
                logger.warning(message)

        base = self.option("output-file")
        for output_format in formats:
            if output_format == "json":
                export_json(document, base, 4)
                self.line(
                    f"<info>Graph metric '{metric}' over {len(graphs)} graph(s)"
                    f" written to {base}.</info>"
                )
            elif output_format == "mermaid":
                mmd_file = f"{base}.mmd"
                with open(mmd_file, "w", encoding="utf-8") as f:
                    f.write(render_mermaid(document, graphs, top=min(top, 12)))
                self.line(f"<info>Written to {mmd_file}</info>")
            else:
                for line in render_console(document, top=top):
                    self.line(line)
        for export_format in exports:
            self._export(document, graphs, export_format, base)
        return 0

    def _export(self, document, graphs, export_format, base):
        from atom_tools.lib.callgraph import export_gexf, export_graphml

        writer, extension = (
            (export_graphml, ".graphml") if export_format == "graphml" else (export_gexf, ".gexf")
        )
        path = base if base.endswith(extension) else f"{base}{extension}"
        with open(path, "w", encoding="utf-8") as f:
            f.write(writer(graphs))
        self.line(
            f"<info>Exported {len(graphs)} call graph(s) ({document['metric']}"
            f" input(s)) to {path}.</info>"
        )

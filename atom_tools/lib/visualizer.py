"""
Visualisation of atom reachable slices.

Two renderers are provided:

* a rich console report - a summary panel, a per-file tree of source-to-sink
  flows and a reachable package table;
* mermaid.js diagrams - a styled flowchart of the interesting flows (green
  sources, red high-risk sinks, package nodes for the purls involved) written
  as a ``.mmd`` file and as a single-file HTML page that renders it with
  mermaid.js (from the CDN by default, or embedded from a local copy for
  offline use).

Both renderers accept an optional CycloneDX SBOM (as produced by cdxgen) to
enrich package nodes with licenses and to report how many SBOM components the
analysis actually proved reachable.
"""

import html
import json
import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from atom_tools.lib.sarif import HIGH_RISK_SINKS, node_tags

if TYPE_CHECKING:
    from rich.console import Console

logger = logging.getLogger(__name__)

# Soft width a mermaid node label is wrapped at. Labels are never truncated;
# long paths and purls are broken across lines instead.
DEFAULT_LABEL_WRAP = 48

# Number of flows kept per file and files shown in the console tree.
TREE_FILES_LIMIT = 10
TREE_FLOWS_PER_FILE = 5

SINK_STYLES = {
    "high": "bold red",
    "warning": "yellow",
    "note": "cyan",
}

# Score used to pick the most interesting flows for the mermaid diagram.
# Bookkeeping tags that carry no visual meaning.
NOISY_TAGS = {"framework", "flow-summary"}


def _clean_tags(node: Dict) -> List[str]:
    """Tags of a slice node without purls and bookkeeping noise."""
    return [t for t in node_tags(node) if t not in NOISY_TAGS]


def mm_escape(label: str, limit: int = 0) -> str:
    """
    Escape a string for use inside a quoted mermaid node label.

    Quoted labels tolerate most characters, but quotes, braces, brackets,
    pipes and backslashes break the diagram grammar; they are replaced with
    look-alike punctuation.

    Labels are *not* truncated by default: java package names, relative source
    paths and purls are long, and an ellipsis in the middle of one makes the
    diagram unreadable. Pass a positive ``limit`` to truncate explicitly.
    """
    label = (label or "").strip().splitlines()[0] if label else ""
    replacements = {
        '"': "'",
        "[": "(",
        "]": ")",
        "{": "(",
        "}": ")",
        "|": "/",
        "\\": "/",
        "`": "'",
        "<": "&lt;",
        ">": "&gt;",
        "#": "&#35;",
        ";": ",",
    }
    for old, new in replacements.items():
        label = label.replace(old, new)
    if limit > 0 and len(label) > limit:
        label = label[: limit - 1] + "…"
    return label


# Long labels are kept whole and soft-wrapped instead. Breaks are allowed after
# a path or purl separator, after whitespace, and after a dot that does not
# start a version segment - so "spring-web@7.0.8" never splits mid-version.
WRAP_POINTS = re.compile(r"(?<=[/@])|(?<=\s)|(?<=\.)(?!\d)")


def mm_label(text: str, wrap: int = DEFAULT_LABEL_WRAP) -> str:
    """
    Escape a label and soft-wrap it across mermaid ``<br/>`` lines.

    Nothing is dropped: the full relative path, package name or purl stays in
    the diagram, just spread over as many lines as it needs.

    Args:
        text: The raw label.
        wrap: Soft target width per line; 0 disables wrapping.

    Returns:
        The escaped, wrapped mermaid label.
    """
    escaped = mm_escape(text)
    if wrap <= 0 or len(escaped) <= wrap:
        return escaped
    lines: List[str] = []
    current = ""
    for token in WRAP_POINTS.split(escaped):
        if current and len(current) + len(token) > wrap:
            lines.append(current)
            current = token
        else:
            current += token
    if current:
        lines.append(current)
    return "<br/>".join(lines)


@dataclass
class FlowInfo:
    """A single reachable flow group in render-friendly form."""

    source_name: str
    source_file: str
    source_line: Optional[int]
    sink_name: str
    sink_file: str
    sink_line: Optional[int]
    sink_code: str
    tags: List[str]
    purls: List[str]
    steps: int

    @property
    def primary_tag(self) -> str:
        for tag in self.tags:
            if tag in HIGH_RISK_SINKS:
                return tag
        return self.tags[0] if self.tags else "flow"

    @property
    def risk(self) -> str:
        if any(t in HIGH_RISK_SINKS for t in self.tags):
            return "high"
        return "warning" if self.tags else "note"
    def source_label(self) -> str:
        line = f":{self.source_line}" if self.source_line else ""
        return f"{self.source_name}{line}"

    def sink_label(self) -> str:
        code = mm_escape(self.sink_code or self.sink_name)
        line = f":{self.sink_line}" if self.sink_line else ""
        return f"{code}{line}"


@dataclass
class VisualizationModel:
    """Aggregated view of a reachable slice plus optional SBOM context."""

    entries: List[Dict] = field(default_factory=list)
    flows: List[FlowInfo] = field(default_factory=list)
    files: Counter = field(default_factory=Counter)
    tags: Counter = field(default_factory=Counter)
    purl_counts: Counter = field(default_factory=Counter)
    sources: int = 0
    sinks: int = 0
    tagged_flows: int = 0
    bom: Optional[Dict] = None
    bom_components: Dict[str, Dict] = field(default_factory=dict)
    # Qualifier-stripped purl -> canonical purl, for ecosystem tolerant matching
    # (atom maven purls carry ?type=jar; other frontends may not).
    bom_by_base_purl: Dict[str, str] = field(default_factory=dict)

    def bom_component_for(self, purl: str) -> Optional[Dict]:
        """Look up an SBOM component for a purl, ignoring qualifiers."""
        if purl in self.bom_components:
            return self.bom_components[purl]
        canonical = self.bom_by_base_purl.get(purl.split("?", 1)[0])
        return self.bom_components.get(canonical) if canonical else None

    @property
    def reachable_components(self) -> int:
        return sum(1 for p in self.purl_counts if self.bom_component_for(p) is not None)

    @classmethod
    def build(
        cls, entries: List[Dict], bom: Optional[Dict] = None
    ) -> "VisualizationModel":
        """
        Build the model from reachables entries and an optional parsed SBOM.

        Args:
            entries: The ``reachables`` list of a reachable slice.
            bom: A parsed CycloneDX document (dict), or None.

        Returns:
            The populated model.
        """
        model = cls(entries=entries, bom=bom)
        if bom:
            for component in bom.get("components", []) or []:
                purl = component.get("purl")
                if not purl:
                    continue
                model.bom_components[purl] = component
                model.bom_by_base_purl.setdefault(purl.split("?", 1)[0], purl)
        for entry in entries:
            flows = entry.get("flows") or []
            purls = sorted(p for p in entry.get("purls") or [] if isinstance(p, str))
            for purl in purls:
                model.purl_counts[purl] += 1
            if not flows:
                continue
            source, sink = flows[0], flows[-1]
            # Tags from both ends of the flow tell the story: sources carry
            # framework-input/pii style tags, sinks carry sql/ssrf style tags.
            flow_tags = list(dict.fromkeys(_clean_tags(source) + _clean_tags(sink)))
            for tag in flow_tags:
                model.tags[tag] += 1
            if _clean_tags(sink):
                model.sinks += 1
            if _clean_tags(source):
                model.sources += 1
            if flow_tags:
                model.tagged_flows += 1
            model.files[sink.get("parentFileName", "?")] += 1
            model.flows.append(
                FlowInfo(
                    source_name=source.get("name") or source.get("code") or "?",
                    source_file=source.get("parentFileName", "?"),
                    source_line=source.get("lineNumber"),
                    sink_name=sink.get("name") or sink.get("code") or "?",
                    sink_file=sink.get("parentFileName", "?"),
                    sink_line=sink.get("lineNumber"),
                    sink_code=sink.get("code") or sink.get("name") or "",
                    tags=flow_tags,
                    purls=purls,
                    steps=len(flows),
                )
            )
        return model

    def interesting_flows(self, limit: int) -> List[FlowInfo]:
        """Return the most interesting flows, capped for diagram readability."""
        file_rank = {f: i for i, (f, _) in enumerate(self.files.most_common())}
        ranked = sorted(
            enumerate(self.flows),
            key=lambda pair: (
                -_flow_score_from_info(pair[1])[0],
                file_rank.get(pair[1].sink_file, 1 << 30),
                pair[0],
            ),
        )
        return [flow for _, flow in ranked[:limit]]


def _flow_score_from_info(flow: FlowInfo) -> Tuple[int, int]:
    if any(t in HIGH_RISK_SINKS for t in flow.tags):
        return (3, flow.steps)
    return (2 if flow.tags else 1, flow.steps)


def load_bom(path: str) -> Optional[Dict]:
    """
    Load a CycloneDX SBOM document.

    Args:
        path: Path to the SBOM json file.

    Returns:
        The parsed document, or None when it cannot be read.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            bom = json.load(f)
        if isinstance(bom, dict) and "components" in bom:
            return bom
        logger.warning("Not a CycloneDX SBOM: %s", path)
        return None
    except (OSError, ValueError) as e:
        logger.warning("Unable to read SBOM %s: %s", path, e)
        return None


def component_licenses(component: Dict) -> str:
    """Extract a short license string from a CycloneDX component."""
    licenses = component.get("licenses") or []
    parts = []
    for entry in licenses:
        if isinstance(entry, dict):
            license_obj = entry.get("license") or {}
            name = license_obj.get("id") or license_obj.get("name")
            if name:
                parts.append(name)
            elif entry.get("expression"):
                parts.append(entry["expression"])
    return ", ".join(dict.fromkeys(parts)) or "-"


# ---------------------------------------------------------------------------
# rich console rendering
# ---------------------------------------------------------------------------


def render_console(model: VisualizationModel) -> "Console":
    """
    Render the model to a rich Console (returned for testing).

    Args:
        model: The visualization model.

    Returns:
        A Console containing the rendered report.
    """
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.tree import Tree

    console = Console(record=True)
    summary = [
        f"[bold]Flow groups[/bold]: {len(model.flows)}   "
        f"[bold]Files[/bold]: {len(model.files)}   "
        f"[bold]Sources[/bold]: {model.sources}   [bold]Tagged flows[/bold]: {model.tagged_flows}",
        f"[bold]Reachable packages[/bold]: {len(model.purl_counts)}",
    ]
    if model.bom_components:
        total = len(model.bom_components)
        reachable = model.reachable_components
        percent = (100 * reachable // total) if total else 0
        summary.append(
            f"[bold]SBOM components[/bold]: {total}   "
            f"[bold]Proven reachable[/bold]: [green]{reachable}[/green] ({percent}%)"
        )
    console.print(Panel("\n".join(summary), title="Reachables overview"))

    tree = Tree("[bold]Data flows by file[/bold]", guide_style="dim")
    for filename, count in model.files.most_common(TREE_FILES_LIMIT):
        branch = tree.add(f"[bold magenta]{filename}[/bold magenta] [dim]({count})[/dim]")
        shown = 0
        for flow in model.flows:
            if flow.sink_file != filename or shown >= TREE_FLOWS_PER_FILE:
                continue
            shown += 1
            style = SINK_STYLES.get(flow.risk, "cyan")
            # Keep the namespace so packages sharing a name stay distinguishable;
            # only the purl qualifiers (?type=jar) are dropped here.
            via = ", ".join(p.split("?", 1)[0] for p in flow.purls[:2])
            purls = f" [dim]via {via}[/dim]" if flow.purls else ""
            branch.add(
                f"[blue]{flow.source_label()}[/blue] →"
                f" [{style}]{flow.sink_label()}[/{style}]"
                f" [dim]\\[{flow.primary_tag}, {flow.steps} steps][/dim]{purls}"
            )
    console.print(tree)

    if model.purl_counts:
        table = Table(title="Reachable packages", show_lines=False)
        table.add_column("Package")
        table.add_column("Flows", justify="right")
        table.add_column("License")
        table.add_column("In SBOM")
        for purl, count in model.purl_counts.most_common(15):
            component = model.bom_component_for(purl)
            in_sbom = "[green]yes[/green]" if component else "[dim]no[/dim]"
            license_str = component_licenses(component) if component else "-"
            # Full purl: the group id distinguishes packages that share a name.
            table.add_row(purl, str(count), license_str, in_sbom)
        console.print(table)
    return console


# ---------------------------------------------------------------------------
# mermaid rendering
# ---------------------------------------------------------------------------


def render_mermaid(
    model: VisualizationModel,
    max_flows: int = 60,
    label_wrap: int = DEFAULT_LABEL_WRAP,
) -> str:
    """
    Render the most interesting flows as a mermaid flowchart.

    Sources are green stadium nodes, high risk sinks red, other tagged sinks
    orange, and package purls purple hexagons linked to the sinks they serve.
    Flows are grouped into subgraphs by sink file.

    Labels carry the full relative path, the full sink expression and the full
    purl; long ones are soft-wrapped rather than cut with an ellipsis.

    Args:
        model: The visualization model.
        max_flows: Maximum number of flows to draw.
        label_wrap: Soft width to wrap long labels at; 0 keeps them on one line.

    Returns:
        The mermaid diagram source.
    """
    lines = ["flowchart LR"]
    lines.append("    classDef source fill:#1a7f37,stroke:#116329,color:#fff")
    lines.append("    classDef sinkHigh fill:#cf222e,stroke:#a40e26,color:#fff")
    lines.append("    classDef sinkWarn fill:#d29922,stroke:#9a6700,color:#fff")
    lines.append("    classDef pkg fill:#8250df,stroke:#5c33b8,color:#fff")
    node_ids: Dict[Tuple[str, str], str] = {}
    pkg_ids: Dict[str, str] = {}
    counter = 0

    def node_id(key: Tuple[str, str]) -> str:
        nonlocal counter
        if key not in node_ids:
            counter += 1
            node_ids[key] = f"n{counter}"
        return node_ids[key]

    def declare(key: Tuple[str, str], label: str, kind: str) -> str:
        """Register a node and emit its declaration exactly once."""
        fresh = key not in node_ids
        ident = node_id(key)
        if not fresh:
            return ident
        text = mm_label(label, label_wrap)
        if kind == "source":
            lines.append(f'        {ident}("{text}"):::source')
        elif kind == "sinkHigh":
            lines.append(f'        {ident}[["{text}"]]:::sinkHigh')
        elif kind == "sinkWarn":
            lines.append(f'        {ident}["{text}"]:::sinkWarn')
        else:
            lines.append(f'        {ident}("{text}")')
        return ident

    by_file: Dict[str, List[FlowInfo]] = {}
    for flow in model.interesting_flows(max_flows):
        by_file.setdefault(flow.sink_file, []).append(flow)

    for file_index, (filename, flows) in enumerate(
        sorted(by_file.items(), key=lambda kv: -model.files[kv[0]])
    ):
        lines.append(f'    subgraph sg{file_index}["{mm_label(filename, label_wrap)}"]')
        for flow in flows:
            src = declare((flow.source_file, flow.source_label()), flow.source_label(), "source")
            kind = {"high": "sinkHigh", "warning": "sinkWarn"}.get(flow.risk, "note")
            dst = declare((flow.sink_file, flow.sink_label()), flow.sink_label(), kind)
            lines.append(
                f'        {src} -->|"{mm_escape(flow.primary_tag, 20)}"| {dst}'
            )
        lines.append("    end")
        pkg_edges = set()
        for flow in flows:
            dst = node_id((flow.sink_file, flow.sink_label()))
            for purl in flow.purls[:2]:
                if purl not in pkg_ids:
                    counter += 1
                    pkg_ids[purl] = f"p{counter}"
                    component = model.bom_component_for(purl)
                    license_str = component_licenses(component) if component else ""
                    # The whole purl, so the group id and version stay visible.
                    label = mm_label(purl, label_wrap)
                    if license_str and license_str != "-":
                        label += f"<br/>{mm_escape(license_str)}"
                    lines.append(f'        {pkg_ids[purl]}{{"{label}"}}:::pkg')
                if (dst, purl) not in pkg_edges:
                    pkg_edges.add((dst, purl))
                    lines.append(f"        {dst} -.-> {pkg_ids[purl]}")
    return "\n".join(lines) + "\n"


MERMAID_CDN = "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"

HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>atom-tools reachables</title>
<script src="{mermaid_src}"></script>
<style>
 body {{ background: #0d1117; color: #c9d1d9; font-family: -apple-system, sans-serif;
        margin: 0; padding: 2rem; }}
 h1 {{ color: #58a6ff; font-size: 1.4rem; }}
 .summary {{ display: flex; gap: 1.5rem; flex-wrap: wrap; margin-bottom: 1.5rem; }}
 .card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px;
         padding: .8rem 1.2rem; }}
 .card b {{ display: block; font-size: 1.4rem; color: #58a6ff; }}
 .diagram {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px;
            padding: 1rem; overflow: auto; }}
 footer {{ color: #8b949e; margin-top: 1rem; font-size: .8rem; }}
</style>
</head>
<body>
<h1>Reachable data flows</h1>
<div class="summary">{summary}</div>
<div class="diagram"><pre class="mermaid">{diagram}</pre></div>
<footer>Generated by atom-tools visualize from {source}. Red nodes are high risk
sinks (sql, ssrf, code-execution, ...), green nodes are sources, purple hexagons
are the packages reached by the flow.</footer>
<script>mermaid.initialize({{ startOnLoad: true, theme: "dark" }});</script>
</body>
</html>
"""


def render_html(
    model: VisualizationModel,
    diagram: str,
    source: str,
    mermaid_js: Optional[str] = None,
) -> str:
    """
    Render a single-file HTML page embedding the mermaid diagram.

    By default mermaid.js loads from the CDN, so viewing needs internet
    access. Pass the contents of a local ``mermaid.min.js`` via ``mermaid_js``
    to embed the renderer inline for offline use.

    Args:
        model: The visualization model (for the summary cards).
        diagram: The mermaid diagram source from ``render_mermaid``.
        source: The input slice name, shown in the footer.
        mermaid_js: Optional mermaid.min.js contents to embed instead of the
            CDN script tag.

    Returns:
        The HTML document.
    """
    cards = [
        ("Flow groups", len(model.flows)),
        ("Files", len(model.files)),
        ("Sources", model.sources),
        ("Tagged flows", model.tagged_flows),
        ("Reachable packages", len(model.purl_counts)),
    ]
    if model.bom_components:
        cards.append(("SBOM components reachable", model.reachable_components))
    summary = "".join(
        f'<div class="card"><b>{value}</b>{html.escape(label)}</div>'
        for label, value in cards
    )
    if mermaid_js:
        # "</script" inside the payload would terminate the script element
        # early; "\/" is a valid JS escape for "/" so this is a no-op for JS.
        safe_js = mermaid_js.replace("</script", "<\\/script")
        head = f"<script>{safe_js}</script>"
    else:
        head = f'<script src="{MERMAID_CDN}"></script>'
    template = HTML_TEMPLATE.replace('<script src="{mermaid_src}"></script>', "{mermaid_head}")
    return template.format(
        mermaid_head=head,
        summary=summary,
        diagram=html.escape(diagram),
        source=html.escape(Path(source).name),
    )


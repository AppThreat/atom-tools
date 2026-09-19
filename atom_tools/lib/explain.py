"""Deterministic narrative rendering over the unified flow model.

Every artefact in the ecosystem is JSON aimed at a program; ``explain`` is
the one surface that states, in words a reviewer or an agent can act on,
*why a flow exists* — and states nothing the model cannot back. There is no
model call anywhere: the value is that the output is reproducible, citable
and safe in CI.

The showcase sentence in the phase spec made four claims the model cannot
support; the renderers here implement the honest version of each (measured
against the committed fixtures in ``test/data/ecosystem/``):

- *"reachable from an anonymous HTTP route"* — only dosai classifies
  authentication. Every golem, rusi and atom entry point sits in
  ``unknown-auth`` on purpose (Phase 2), so for those engines the sentence
  says the route's exposure is unknown, never "anonymous".
- *"``GET /owners/{ownerId}`` (OwnerController.java:78)"* — the endpoint→flow
  join is partial (31 of 57 golem endpoints anchor; 14 of 14 rusi; 0 for
  dosai, whose flows carry no entry-point reference). The join is reused from
  :mod:`atom_tools.lib.attack_surface` — never re-implemented here — and a
  flow with no anchored entry point says so, with the reason, instead of
  dropping the clause silently.
- *"Evidence: atom 49360b5"* — atom slices carry no version (``engine_version``
  is ``''``); a bare reachables list has no envelope at all. What exists is
  printed; nothing is invented.
- *"No sanitizer observed on this path"* — ``sanitized`` is False on every
  flow of every committed fixture (0/5 rusi, 0/397 golem, 0/60 dosai, 0/163
  atom), so the spec's sentence would print on every flow, always, and read
  as "this path is unsanitised". It is emitted only for the two engines whose
  slice schema carries a sanitizer field the adapter actually reads (dosai's
  ``SanitizedFlows``, golem's ``sanitizerNodeIds``), phrased as what it is:
  reported absence, not a finding. For rusi and atom the clause is omitted
  entirely — those engines emit no sanitizer signal, and "none observed" from
  an engine that never looked would be an absence-of-evidence claim dressed
  as one.

The rule underneath all four: every clause maps to a field. Where a field is
empty the clause is omitted or hedged — never filled with a plausible
default.

Determinism: every collection whose order reaches the output is sorted
(hash-seed independence is asserted by ``test/test_determinism.py``, which
runs these renderers in subprocesses under several ``PYTHONHASHSEED``
values).
"""

import os
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional, Tuple

from atom_tools.lib.attack_surface import TIER_ORDER, SurfaceInput, compute_attack_surface
from atom_tools.lib.query import run_query
from atom_tools.lib.unified import UnifiedFlow, UnifiedReport

EXPLAIN_VERSION = 1
SEVERITY_RANK = {"error": 0, "warning": 1, "note": 2}
UNRANKED_TIER = len(TIER_ORDER)

# Engines whose slice schema carries a sanitizer field the adapter reads
# (dosai's SanitizedFlows section, golem's sanitizerNodeIds). rusi and atom
# emit no sanitizer signal at all, so for them the sanitizer clause is omitted
# entirely rather than hedged: "no sanitizer observed" from an engine that
# never looked would read as a finding.
SANITIZER_CAPABLE_ENGINES = ("dosai", "golem")

AGENT_SCHEMA = "atom-tools/explain-agent-context@1"
AGENT_TOKEN_METHOD = "characters/4 of the serialized JSON — an estimate, not a real tokeniser"


# -- context --------------------------------------------------------------------


@dataclass
class ExplainContext:
    """Everything a renderer needs: the model, the inputs, and the one join."""

    report: UnifiedReport
    inputs: List[SurfaceInput]
    surface: Dict
    #: flow id → the surface's entry-point dicts anchored to it (the join).
    flow_entry_points: Dict[str, List[Dict]] = field(default_factory=dict)
    #: engine names whose input file was a unified document (no call graph
    #: inside, so the golem/rusi anchor join could not run).
    unified_engines: List[str] = field(default_factory=list)

    @property
    def source_names(self) -> List[str]:
        return [os.path.basename(i.path) for i in self.inputs]

    def rank_flows(self, flows: Optional[List[UnifiedFlow]] = None) -> List[UnifiedFlow]:
        """Severity first, then the best anchored entry-point tier, then id."""
        flows = flows if flows is not None else self.report.flows

        def key(flow: UnifiedFlow) -> Tuple:
            tiers = [
                TIER_ORDER.index(entry.get("Exposure"))
                for entry in self.flow_entry_points.get(flow.id, [])
                if entry.get("Exposure") in TIER_ORDER
            ]
            return (
                SEVERITY_RANK.get(flow.severity, 3),
                min(tiers) if tiers else UNRANKED_TIER,
                flow.id,
            )

        return sorted(flows, key=key)

    def collections(self) -> Dict[str, List[Dict]]:
        """The query grammar's collections over the model.

        A flow's dict form gains ``source``/``sink`` (first/last node) and
        ``steps`` (node count) as resolvable paths — the deliberate
        atom-tools addition to dosai's grammar.
        """
        flows = []
        for flow in self.report.flows:
            item = asdict(flow)
            item["steps"] = len(item["nodes"])
            if item["nodes"]:
                item["source"] = item["nodes"][0]
                item["sink"] = item["nodes"][-1]
            flows.append(item)
        return {"flows": flows, "endpoints": self.report.endpoints, "packages": self.report.packages}


def build_context(inputs: List[SurfaceInput]) -> ExplainContext:
    """Load the model, run the (single, shared) endpoint join, index it."""
    from atom_tools.lib import unified as unified_lib

    reports = [i.report for i in inputs if i.report is not None]
    merged = _merge(reports, inputs)
    surface = compute_attack_surface(inputs)
    flow_entry_points: Dict[str, List[Dict]] = {}
    for tier in surface["tiers"]:
        for entry in tier["EntryPoints"]:
            for flow_id in (entry.get("Reach") or {}).get("flowIds") or []:
                flow_entry_points.setdefault(flow_id, []).append(entry)
    unified_engines = sorted({i.engine for i in inputs if unified_lib.detect(i.raw)})
    return ExplainContext(
        report=merged,
        inputs=inputs,
        surface=surface,
        flow_entry_points=flow_entry_points,
        unified_engines=unified_engines,
    )


def _merge(reports: List[UnifiedReport], inputs: List[SurfaceInput]) -> UnifiedReport:
    """One model document from the parsed inputs (usages-only inputs have none)."""
    if not reports:
        return UnifiedReport(
            engine="+".join(sorted({i.engine for i in inputs})) or "atom",
            analysis_mode="+".join(sorted({i.engine for i in inputs})),
            source_file=",".join(i.path for i in inputs),
        )
    if len(reports) == 1:
        return reports[0]
    from atom_tools.lib.unified import merge_reports

    return merge_reports(reports)


# -- selection ------------------------------------------------------------------


def flows_for_package(report: UnifiedReport, package: str) -> List[UnifiedFlow]:
    """Flows whose purls (or nodes' purls) contain ``package`` (case-insensitive)."""
    lowered = package.lower()

    def hit(flow: UnifiedFlow) -> bool:
        purls = list(flow.purls) + [n.purl for n in flow.nodes if n.purl]
        return any(lowered in p.lower() for p in purls if p)

    return [f for f in report.flows if hit(f)]


def flows_for_file(report: UnifiedReport, path: str) -> List[UnifiedFlow]:
    """Flows with any node in ``path`` (suffix match on normalised separators)."""

    def norm(value: str) -> str:
        value = value.replace("\\", "/")
        while value.startswith("./"):
            value = value[2:]
        return value

    wanted = norm(path)

    def hit(flow: UnifiedFlow) -> bool:
        for node in flow.nodes:
            if node.file and (norm(node.file) == wanted or norm(node.file).endswith("/" + wanted)):
                return True
        return False

    return [f for f in report.flows if hit(f)]


def find_flow(report: UnifiedReport, flow_id: str) -> UnifiedFlow:
    """Exact flow-id lookup with a deterministic "did you mean" on failure."""
    for flow in report.flows:
        if flow.id == flow_id:
            return flow
    import difflib

    near = difflib.get_close_matches(flow_id, [f.id for f in report.flows], n=3, cutoff=0.6)
    hint = f" Did you mean: {', '.join(near)}?" if near else ""
    raise ValueError(
        f"Unknown flow id: {flow_id}. The report carries {len(report.flows)} flow(s).{hint}"
    )


# -- the narrative --------------------------------------------------------------


def _location(file: str, line: Optional[int]) -> str:
    if not file:
        return ""
    return f" ({file}:{line})" if isinstance(line, int) else f" ({file})"


def _entry_label(entry: Dict) -> str:
    route = entry.get("Route")
    if route:
        return f"`{entry.get('HttpMethod') or 'ANY'} {route}`"
    return f"`{entry.get('Handler') or entry.get('EntryPointId') or 'entry point'}`"


def _entry_where(entry: Dict) -> str:
    file, line = entry.get("File") or "", entry.get("LineNumber")
    return _location(file, line) if file else ""


def _no_join_reason(flow: UnifiedFlow, ctx: ExplainContext) -> str:
    engine = flow.engine
    if engine == "dosai":
        return "dosai links weaknesses — not flows — to entry points, so no route is named here"
    if engine in ("golem", "rusi"):
        coverage = ctx.surface["coverage"].get(engine, {})
        if not coverage.get("callGraphs"):
            if engine in ctx.unified_engines:
                return (
                    "the input is a unified document, which carries no call graph,"
                    " so endpoints could not be anchored (pass the engine's own"
                    " report to compute the join)"
                )
            return "the report carries no call graph, so handlers could not be anchored"
        return (
            "its source function sits inside no anchored handler's closure"
            f" ({coverage.get('endpointsAnchored', 0)} of {coverage.get('endpoints', 0)}"
            " endpoints anchored in this report's call graph)"
        )
    if engine == "atom":
        return "no route-tagged node (framework-route/service-ingress) sits on its path"
    return f"{engine or 'the engine'} emits no entry-point link this command can read"


def _reach_clause(flow: UnifiedFlow, ctx: ExplainContext) -> str:
    """Clause 1: what is reached, from where — hedged exactly as far as the join goes."""
    purls = sorted(flow.purls)
    sink = flow.sink
    if len(purls) == 1:
        subject = f"`{purls[0]}`"
    elif purls:
        subject = f"`{purls[0]}` (and {len(purls) - 1} more package(s))"
    elif sink is not None:
        subject = f"sink `{sink.name}`{_location(sink.file, sink.line)}"
    else:
        subject = f"flow `{flow.id}`"

    entries = sorted(
        ctx.flow_entry_points.get(flow.id, []), key=lambda e: (_entry_label(e), e.get("EntryPointId") or "")
    )
    if not entries:
        return f"{subject} is reached by this flow; {_no_join_reason(flow, ctx)}."
    first = entries[0]
    described = f"{_entry_label(first)}{_entry_where(first)}"
    if len(entries) > 1:
        described += f", and {len(entries) - 1} more entry point(s)"
    if first.get("Exposure") in TIER_ORDER and first.get("Exposure") != "unknown-auth":
        article = "an" if first["Exposure"][0] in "aeiou" else "a"
        return (
            f"{subject} is reachable from {article} `{first['Exposure']}` entry point"
            f" {described}."
        )
    return (
        f"{subject} is reached from {described};"
        f" {flow.engine or 'this engine'} does not classify authentication, so the"
        " route's exposure is unknown."
    )


def _path_clause(flow: UnifiedFlow) -> str:
    """Clause 2: the source→sink walk. The tag modifier is omitted when the
    engine recorded none (fewer than half of atom's flows carry source tags)."""
    source, sink = flow.source, flow.sink
    parts = []
    if source is not None:
        tagged = ""
        if source.tags:
            tagged = f" tagged `{'`, `'.join(sorted(source.tags))}`"
        parts.append(f"source `{source.name}`{_location(source.file, source.line)}{tagged}")
    if sink is not None:
        parts.append(f"reaches `{sink.name}`{_location(sink.file, sink.line)}")
    sentence = " which ".join(parts) if len(parts) == 2 else "; ".join(parts) or "no nodes recorded"
    steps = f" in {len(flow.nodes)} step(s)"
    classified = (
        f", classified `{flow.sink_category}`"
        if flow.sink_category
        else ", with no sink category recorded in this slice"
    )
    truncated = (
        "; the witness path is a representative excerpt, not every step (path_truncated)"
        if flow.path_truncated
        else ""
    )
    return f"{sentence}{steps}{classified}{truncated}."


def _evidence_clause(flow: UnifiedFlow) -> str:
    """Clause 3: who produced this, and where the severity came from."""
    engine = flow.engine or "unknown engine"
    version = f" {flow.engine_version}" if flow.engine_version else " (no version recorded in the slice)"
    mode = f", {flow.analysis_mode} mode" if flow.analysis_mode else ""
    provenance = (
        "engine-reported"
        if flow.severity_source == "engine"
        else "derived from the shared taxonomy, not engine-reported"
    )
    confidence = f" Confidence `{flow.confidence}`." if flow.confidence else ""
    return (
        f"{engine}{version}{mode}. Severity `{flow.severity}` ({provenance})."
        f"{confidence}"
    )


def _sanitizer_clause(flow: UnifiedFlow) -> Optional[str]:
    """Clause 4: reported absence, never a finding — None means "say nothing"."""
    if flow.engine not in SANITIZER_CAPABLE_ENGINES:
        return None
    if flow.sanitized:
        return f"{flow.engine} reported this flow as sanitized (a sanitizer suppressed it)."
    return (
        f"No sanitizer reported on this path by {flow.engine}'s sanitizer analysis;"
        " this run found none to report."
    )


def explain_flow_lines(flow: UnifiedFlow, ctx: ExplainContext) -> List[str]:
    """The full four-clause narrative for one flow (plain lines, no markup)."""
    categories = (
        f"{flow.source_category or 'uncategorised'} → {flow.sink_category or 'uncategorised'}"
    )
    lines = [f"Flow {flow.id} — {categories}"]
    lines.append(f"  Reachability: {_reach_clause(flow, ctx)}")
    lines.append(f"  Path: {_path_clause(flow)}")
    lines.append(f"  Evidence: {_evidence_clause(flow)}")
    sanitizer = _sanitizer_clause(flow)
    if sanitizer is not None:
        lines.append(f"  Sanitizer: {sanitizer}")
    return lines


def render_flow_markdown(flow: UnifiedFlow, ctx: ExplainContext) -> str:
    """One flow's narrative as a standalone markdown block (--flow -f markdown)."""
    lines = explain_flow_lines(flow, ctx)
    out = [f"### `{flow.id}` — {flow.severity} ({flow.severity_source})", ""]
    for line in lines[1:]:
        label, _, body = line.strip().partition(": ")
        out.append(f"- **{label}:** {body}")
    return "\n".join(out) + "\n"


# -- the overview ---------------------------------------------------------------


def _engine_summary(ctx: ExplainContext) -> str:
    engines: Dict[str, Dict[str, set]] = {}
    for flow in ctx.report.flows:
        facts = engines.setdefault(flow.engine or "unknown", {})
        facts.setdefault("versions", set()).add(flow.engine_version)
        facts.setdefault("modes", set()).add(flow.analysis_mode)
    if not engines:
        engines["atom"] = {"versions": set(), "modes": set()}
    parts = []
    for engine in sorted(engines):
        versions = sorted(v for v in engines[engine]["versions"] if v)
        modes = sorted(m for m in engines[engine]["modes"] if m)
        qualifiers = [f"{'/'.join(modes)} mode"] if modes else []
        if not versions:
            qualifiers.append("no version recorded")
        described = engine + (f" {'/'.join(versions)}" if versions else "")
        if qualifiers:
            described += f" ({'; '.join(qualifiers)})"
        parts.append(described)
    return ", ".join(parts)


def _severity_line(report: UnifiedReport) -> str:
    counts = {"error": 0, "warning": 0, "note": 0}
    engine_reported = sum(1 for f in report.flows if f.severity_source == "engine")
    for flow in report.flows:
        counts[flow.severity] = counts.get(flow.severity, 0) + 1
    return (
        f"severity: {counts['error']} error / {counts['warning']} warning /"
        f" {counts['note']} note; {engine_reported} engine-reported,"
        f" {len(report.flows) - engine_reported} derived"
    )


def _join_lines(ctx: ExplainContext) -> List[str]:
    coverage = ctx.surface["coverage"]
    joined = len(ctx.flow_entry_points)
    total = len(ctx.report.flows)
    bits = []
    for engine in sorted(coverage):
        cov = coverage[engine]
        if engine == "dosai":
            if cov.get("endpoints"):
                bits.append(
                    "dosai: engine-tiered entry points taken verbatim from the"
                    " report's own AttackSurface array; dosai links weaknesses —"
                    " not flows — to entry points"
                )
            else:
                bits.append(
                    "dosai: no entry points — the engine's AttackSurface/EntryPoints"
                    " arrays are not in this document (the unified model does not"
                    " carry them)"
                )
        elif engine in ("golem", "rusi"):
            anchored = cov.get("endpointsAnchored", 0)
            endpoints = cov.get("endpoints", 0)
            if cov.get("callGraphs"):
                bits.append(
                    f"{engine}: {anchored} of {endpoints} endpoint(s) anchored in the"
                    f" call graph, {cov.get('flowsAttached', 0)} flow attachment(s)"
                )
            else:
                reason = (
                    " (the unified document does not carry one)"
                    if engine in ctx.unified_engines
                    else ""
                )
                bits.append(
                    f"{engine}: {endpoints} endpoint(s) known but no call graph to"
                    f" anchor them in{reason}"
                )
        elif engine == "atom":
            bits.append(
                f"atom: {cov.get('endpoints', 0)} entry point(s) from route tags or"
                " usages conversion (atom emits no call graph)"
            )
    head = f"entry-point join: {joined} of {total} flow(s) sit behind an anchored entry point"
    lines = [head + ("; " + "; ".join(bits) if bits else "") + "."]
    diagnostics = list(ctx.surface.get("diagnostics") or [])
    for diagnostic in diagnostics[:5]:
        lines.append(f"note: {diagnostic}")
    if len(diagnostics) > 5:
        lines.append(f"note: … and {len(diagnostics) - 5} more diagnostic(s) (see -f json)")
    return lines


def _tag_coverage_line(report: UnifiedReport) -> str:
    tagged = sum(1 for f in report.flows if f.source is not None and f.source.tags)
    return f"source tags: {tagged} of {len(report.flows)} flow(s) carry tags on the source node"


def overview_lines(ctx: ExplainContext) -> List[str]:
    report = ctx.report
    # Endpoint counts live in the join line, qualified per engine by how they
    # were anchored — a raw model count here would read as a verdict.
    lines = [
        f"Flow report: {_engine_summary(ctx)} — {len(report.flows)} flow(s),"
        f" {len(report.packages)} package record(s) from {len(ctx.inputs)}"
        f" input file(s) ({', '.join(ctx.source_names)})."
    ]
    lines.append(_severity_line(report))
    lines.append(_tag_coverage_line(report))
    lines.extend(_join_lines(ctx))
    return lines


TRUNCATION_HINT = (
    "the listing is ranked by severity then entry-point tier; select with"
    " --flow/--package/--file/--query or raise --max-flows"
)


def _truncation_line(omitted: int) -> str:
    return f"truncated: {omitted} more flow(s) not shown — {TRUNCATION_HINT}."


# -- renderers ------------------------------------------------------------------


def _listing_blocks(ctx: ExplainContext, flows: List[UnifiedFlow], max_flows: int) -> List[str]:
    """Narrative blocks for the ranked ``flows``, plus the marker when capped."""
    shown, omitted = flows[:max_flows], max(0, len(flows) - max_flows)
    blocks = []
    for position, flow in enumerate(shown, start=1):
        narrative = explain_flow_lines(flow, ctx)
        blocks.append(f"{position}. {narrative[0]}")
        blocks.extend(narrative[1:])
        blocks.append("")
    if omitted:
        blocks.append(_truncation_line(omitted))
    return blocks


def render_text(
    ctx: ExplainContext,
    flows: Optional[List[UnifiedFlow]] = None,
    max_flows: int = 10,
    heading: str = "",
) -> str:
    """Console/markdown-safe plain text: overview (or selector heading) + blocks."""
    lines = [heading] if heading else overview_lines(ctx)
    lines.append("")
    selected = ctx.rank_flows(flows) if flows is not None else ctx.rank_flows()
    lines.extend(_listing_blocks(ctx, selected, max_flows))
    return "\n".join(lines).rstrip("\n") + "\n"


def render_markdown(
    ctx: ExplainContext,
    flows: Optional[List[UnifiedFlow]] = None,
    max_flows: int = 10,
    heading: str = "",
) -> str:
    """PR-attachable review document; same facts as text, markdown dressing."""
    out: List[str] = [f"# Flow explanation — {_engine_summary(ctx)}", ""]
    out.append(
        "> Generated by `atom-tools explain`; deterministic template rendering over"
        " the unified flow model — no model call. Every clause maps to a field;"
        " hedged clauses say what the report does not know."
    )
    out.append("")
    if heading:
        out.append(f"## {heading}")
    else:
        out.append("## Summary")
        out.extend(f"- {line}" for line in overview_lines(ctx)[1:])
    out.append("")
    selected = ctx.rank_flows(flows) if flows is not None else ctx.rank_flows()
    out.append(
        f"## Flows ({len(selected)} matching, ranked by severity then entry-point tier)"
    )
    out.append("")
    shown, omitted = selected[:max_flows], max(0, len(selected) - max_flows)
    for position, flow in enumerate(shown, start=1):
        narrative = explain_flow_lines(flow, ctx)
        out.append(f"### {position}. `{flow.id}` — {flow.severity} ({flow.severity_source})")
        for line in narrative[1:]:
            label, _, body = line.strip().partition(": ")
            out.append(f"- **{label}:** {body}")
        out.append("")
    if omitted:
        out.append(_truncation_line(omitted))
    return "\n".join(out).rstrip("\n") + "\n"


# -- the agent document ---------------------------------------------------------


def _flow_facts(flow: UnifiedFlow, ctx: ExplainContext) -> Dict:
    """The compact per-flow record the agent format carries."""
    entries = sorted(
        ctx.flow_entry_points.get(flow.id, []),
        key=lambda e: (_entry_label(e), e.get("EntryPointId") or ""),
    )
    source, sink = flow.source, flow.sink
    return {
        "id": flow.id,
        "severity": flow.severity,
        "severitySource": flow.severity_source,
        "confidence": flow.confidence,
        "sourceCategory": flow.source_category or None,
        "sinkCategory": flow.sink_category or None,
        "source": (
            {
                "name": source.name,
                "file": source.file or None,
                "line": source.line,
                "tags": sorted(source.tags),
            }
            if source is not None
            else None
        ),
        "sink": (
            {"name": sink.name, "file": sink.file or None, "line": sink.line}
            if sink is not None
            else None
        ),
        "steps": len(flow.nodes),
        "pathTruncated": flow.path_truncated or None,
        "purls": sorted(flow.purls),
        "entryPoints": [
            {
                "label": _entry_label(entry).strip("`"),
                "exposure": entry.get("Exposure"),
                "location": (f"{entry.get('File')}:{entry.get('LineNumber')}" if entry.get("File") else None),
            }
            for entry in entries
        ],
        "sanitizerReported": True if flow.sanitized else (False if flow.engine in SANITIZER_CAPABLE_ENGINES else None),
    }


def _agent_summary(ctx: ExplainContext) -> Dict:
    report = ctx.report
    engines: Dict[str, Dict[str, set]] = {}
    for flow in report.flows:
        facts = engines.setdefault(flow.engine or "unknown", {})
        facts.setdefault("versions", set()).add(flow.engine_version)
    joined = len(ctx.flow_entry_points)
    return {
        "engines": sorted(engines) or ["atom"],
        "engineVersions": {e: sorted(v for v in engines[e]["versions"] if v) or None for e in sorted(engines)} or None,
        "flows": len(report.flows),
        "severity": {
            "error": sum(1 for f in report.flows if f.severity == "error"),
            "warning": sum(1 for f in report.flows if f.severity == "warning"),
            "note": sum(1 for f in report.flows if f.severity == "note"),
        },
        "severitySource": {
            "engine": sum(1 for f in report.flows if f.severity_source == "engine"),
            "derived": sum(1 for f in report.flows if f.severity_source != "engine"),
        },
        "endpoints": len(report.endpoints),
        "packageRecords": len(report.packages),
        "flowsWithSourceTags": sum(1 for f in report.flows if f.source is not None and f.source.tags),
        "flowsBehindAnEntryPoint": joined,
        "sources": ctx.source_names,
    }


def _suggested_commands(ctx: ExplainContext) -> List[str]:
    source = ",".join(ctx.source_names)
    commands = []
    for flow in ctx.rank_flows()[:3]:
        commands.append(f"atom-tools explain -i {source} --flow {flow.id}")
    commands.append(f"atom-tools explain -i {source} --query 'flows[severity=error] count'")
    commands.append(f"atom-tools attack-surface -i {source} -f json -o attack-surface.json")
    graphy = any(
        i.engine in ("golem", "rusi") and i.raw and not isinstance(i.raw, list) and (
            (i.raw.get("callGraph") or {}).get("nodes") or (i.raw.get("call_graph") or {}).get("nodes")
        )
        for i in ctx.inputs
    )
    if graphy:
        commands.append(f"atom-tools graph -i {source} --metric chokepoints")
    return commands


def build_agent_document(ctx: ExplainContext, max_tokens: int = 4000) -> Dict:
    """dosai agent-context shape over the unified model, under a token budget.

    Budget counting is ``len(serialized json) // 4`` — stated in the document
    itself, because implying a real tokeniser would be one more claim the
    output cannot support. Lowest-value lists are trimmed from the tail until
    the estimate fits; flows are trimmed last because they are the payload.
    """
    ranked = ctx.rank_flows()
    packages: Dict[str, int] = {}
    for flow in ctx.report.flows:
        for purl in flow.purls:
            packages[purl] = packages.get(purl, 0) + 1
    files: Dict[str, int] = {}
    for flow in ctx.report.flows:
        for node in flow.nodes:
            if node.file:
                files[node.file] = files.get(node.file, 0) + 1
    entries = [
        {
            "label": _entry_label(entry).strip("`"),
            "method": entry.get("HttpMethod"),
            "route": entry.get("Route"),
            "exposure": entry.get("Exposure"),
            "authClassifiedByEngine": entry.get("Exposure") in TIER_ORDER
            and entry.get("Exposure") != "unknown-auth",
            "location": (f"{entry.get('File')}:{entry.get('LineNumber')}" if entry.get("File") else None),
            "reachFlows": (entry.get("Reach") or {}).get("flows", 0),
            "reachSinkCategories": sorted((entry.get("Reach") or {}).get("sinkCategories") or []),
        }
        for tier in ctx.surface["tiers"]
        for entry in tier["EntryPoints"]
    ]
    document = {
        "schema": AGENT_SCHEMA,
        "explainVersion": EXPLAIN_VERSION,
        "summary": _agent_summary(ctx),
        "entryPoints": entries,
        "highRiskFlows": [_flow_facts(f, ctx) for f in ranked],
        "reachablePackages": [
            {"purl": purl, "flows": count} for purl, count in sorted(packages.items(), key=lambda kv: (-kv[1], kv[0]))
        ],
        "relevantFiles": [
            {"file": name, "flows": count} for name, count in sorted(files.items(), key=lambda kv: (-kv[1], kv[0]))
        ],
        "suggestedNextCommands": _suggested_commands(ctx),
    }
    return _apply_token_budget(document, max_tokens)


def _estimate_tokens(document: Dict) -> int:
    """The document's own size under :data:`AGENT_TOKEN_METHOD`."""
    import json

    return len(json.dumps(document, indent=2, sort_keys=True)) // 4


def _apply_token_budget(document: Dict, max_tokens: int) -> Dict:
    """Trim tail-first until the estimate fits; say exactly what was cut.

    The ``truncation`` and ``tokenBudget`` blocks are written into the document
    *before* it is measured, and kept in sync while it is trimmed. Appending
    them afterwards made the document describe a size it no longer had: on the
    golem fixture at ``--max-tokens 4000`` it reported ``estimatedTokens 3894,
    respected true`` for bytes that actually came to 3944. A consumer packing a
    real context window off that field would have been told the budget held
    when it did not.
    """
    lists = ("relevantFiles", "reachablePackages", "entryPoints", "highRiskFlows")
    omitted = {name: 0 for name in lists}

    def trimmable() -> List[str]:
        return [name for name in lists if len(document.get(name) or []) > 0]

    def sync() -> int:
        """Refresh the self-describing blocks, then measure the whole document.

        ``estimatedTokens`` is part of what it counts, so writing it can change
        it (by a digit). Iterating to a fixed point costs at most a couple of
        passes and makes the number exact rather than nearly right.
        """
        if sum(omitted.values()):
            detail = ", ".join(f"{v} {k}" for k, v in omitted.items() if v)
            document["truncation"] = {
                "marker": f"truncated: {sum(omitted.values())} more item(s) not shown ({detail})",
                "omitted": {k: v for k, v in omitted.items() if v},
                "reason": (
                    "the token budget (--max-tokens, counting "
                    f"{AGENT_TOKEN_METHOD}) was reached; what is listed is ranked,"
                    " not exhaustive"
                ),
            }
        budget = document.setdefault(
            "tokenBudget",
            {
                "maxTokens": max_tokens,
                "estimatedTokens": 0,
                "countingMethod": AGENT_TOKEN_METHOD,
                "respected": True,
            },
        )
        for _ in range(4):
            total = _estimate_tokens(document)
            if budget["estimatedTokens"] == total:
                break
            budget["estimatedTokens"] = total
        budget["maxTokens"] = max_tokens
        budget["respected"] = budget["estimatedTokens"] <= max_tokens
        return budget["estimatedTokens"]

    while sync() > max_tokens and trimmable():
        name = trimmable()[0]
        omitted[name] += 1
        document[name] = document[name][:-1]
    sync()
    return document


# -- query rendering ------------------------------------------------------------


SINGULAR = {"flows": "flow", "endpoints": "endpoint", "packages": "package"}


def run_query_text(ctx: ExplainContext, expression: str) -> Tuple[str, Optional[List[UnifiedFlow]]]:
    """Run one query; returns (result text, matched flows when the collection is flows)."""
    result = run_query(ctx.collections(), expression)
    singular = SINGULAR.get(result["collection"], result["collection"])
    if result["countMode"]:
        return f"{result['count']} {singular}(s) match `{expression}`.", None
    items = result["items"]
    if result["collection"] == "flows":
        ids = [item.get("id") for item in items]
        by_id = {f.id: f for f in ctx.report.flows}
        flows = [by_id[i] for i in ids if i in by_id]
        return f"{len(items)} flow(s) match `{expression}`.", flows
    labels = []
    for item in items[:20]:
        if result["collection"] == "endpoints":
            labels.append(
                f"  {item.get('method') or 'ANY'} {item.get('path') or item.get('kind') or ''}"
                f" — {item.get('file') or ''}"
            )
        else:
            labels.append(f"  {item.get('purl') or item}")
    more = (
        f"\ntruncated: {len(items) - 20} more {result['collection']}(s) not shown"
        if len(items) > 20
        else ""
    )
    body = ("\n".join(labels) + more) if labels else "  (no matches)"
    return f"{len(items)} {result['collection']}(s) match `{expression}`:\n{body}", None


# -- the MCP server -------------------------------------------------------------


def build_mcp_server(ctx: ExplainContext, baseline: Optional[UnifiedReport] = None):
    """Read-only, file-scoped stdio MCP server over the loaded report.

    Every tool closes over data parsed at startup — no tool touches the
    filesystem, invokes an engine or shells out. ``atom.drift`` needs a second
    report, so the baseline is loaded at startup too (``--old``), never on
    call.
    """
    # Imported here and only here: the mcp extra must stay optional so every
    # other command (and --help) works without it.
    from mcp.server.fastmcp import FastMCP

    server = FastMCP(
        "atom-tools",
        instructions=(
            "Read-only tools over an already-loaded flow report (atom, dosai,"
            " golem, rusi, kosi or unified). No engine invocation, no shell, no"
            " filesystem access beyond the loaded report."
        ),
    )

    def explain_flow(flow_id: str) -> str:
        """Explain one source→sink flow in words; every clause maps to a field."""
        flow = find_flow(ctx.report, flow_id)
        return "\n".join(explain_flow_lines(flow, ctx))

    def attack_surface() -> Dict:
        """Entry points grouped by exposure tier with what each reaches."""
        return ctx.surface

    def drift() -> Dict:
        """Reachability delta against the baseline this server was started with."""
        if baseline is None:
            raise ValueError(
                "atom.drift needs a baseline report; start the server with"
                " --old <baseline report>."
            )
        from atom_tools.lib.drift import compute_drift

        return compute_drift(baseline, ctx.report)

    def graph_hotspots() -> Dict:
        """Call-graph chokepoints over the loaded report's own call graph."""
        from atom_tools.lib.callgraph import (
            compute_graph_document,
            flow_functions,
            load_call_graph,
        )

        graphs, notes = [], []
        for inp in ctx.inputs:
            if not isinstance(inp.raw, dict):
                continue
            try:
                graphs.append(load_call_graph(inp.path, inp.raw))
            except ValueError:
                notes.append(f"{os.path.basename(inp.path)} carries no call graph")
        if not graphs:
            raise ValueError(
                "no input carries a call graph (golem/rusi analyze or dosai"
                f" methods do; {'; '.join(notes) or 'the loaded report has none'})."
            )
        sources, sinks = flow_functions(ctx.report)
        return compute_graph_document(
            graphs,
            "chokepoints",
            flow_sources=sources,
            flow_sinks=sinks,
            endpoints_by_source={inp.path: (inp.report.endpoints if inp.report else []) for inp in ctx.inputs},
        )

    def query(expression: str) -> Dict:
        """Filter the report with dosai's compact grammar, e.g. flows[severity=error]."""
        result = run_query(ctx.collections(), expression)
        items = result["items"]
        cap = 50
        result["items"] = items[:cap]
        if len(items) > cap:
            result["truncated"] = {
                "marker": f"truncated: {len(items) - cap} more item(s) not shown",
                "total": len(items),
            }
        return result

    server.add_tool(
        explain_flow,
        name="atom.explain_flow",
        description="Explain one source→sink flow in words (deterministic, template-driven).",
    )
    server.add_tool(
        attack_surface,
        name="atom.attack_surface",
        description="Entry points grouped by exposure tier, with what each reaches.",
    )
    server.add_tool(
        drift,
        name="atom.drift",
        description="Reachability delta against the baseline the server was started with.",
    )
    server.add_tool(
        graph_hotspots,
        name="atom.graph_hotspots",
        description="Call-graph chokepoints: nodes on the most source→sink paths.",
    )
    server.add_tool(
        query,
        name="atom.query",
        description="Filter with dosai's compact grammar: flows[sink_category=sql && severity=error].",
    )
    return server

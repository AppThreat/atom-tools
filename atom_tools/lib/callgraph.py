"""The call graph of a report: chokepoints, centrality, blast radius.

``query-endpoints`` lists routes, ``attack-surface`` says what each entry
point reaches, and ``drift`` says what changed. None of them answers the
question a fixer actually asks — *which single function sits on the most
paths?* That is a call-graph question, and four engines emit a call graph
that nothing here read: golem ``callGraph``, rusi ``call_graph``, dosai
``CallGraph`` + ``Reachability``, and atom's ``export --format graphml`` /
``algorithms`` outputs. This module turns all four into one model and
computes metrics over it, as pure functions over parsed inputs.

Facts measured against the real fixtures (``test/data/ecosystem/``, see
PROVENANCE.md) that shape the design:

**Engine metrics are carried verbatim, never recomputed.** dosai's
``FanIn``/``FanOut`` live in a separate top-level ``Reachability[]`` array
joined by ``NodeId`` — not on ``CallGraph.Nodes`` — and were computed over
the whole 21,570-node run, while the fixture keeps a contiguous 300-edge
slice. A recomputation over the slice's own edges therefore *disagrees* by
design (266 of 315 nodes match on FanIn, 311 of 315 on FanOut; the engine's
FanIn sums to 448 against 300 edges). Overwriting the engine's numbers, or
"fixing" a test to tolerate the disagreement, would both hide that the
fixture is a slice. The disagreement itself is pinned by a test.

**Dispatch confidence is thin where you would look for it and rich where
you would not.** golem's graph is single-valued — 3,325 of 3,325 edges
``static`` — so ``--min-confidence`` cannot reduce it (said plainly in the
output, not silently passed through). dosai populates ``DispatchConfidence``
on 4 of 300 edges (all ``cha-candidate``; the same 4 carry
``EvidenceKind=SourceRoslynVirtualCandidate``; the rest is Roslyn-direct
evidence and is treated as exact). rusi is the real test bed: seven call
types (``external`` 1,570, ``static`` 306, ``static-overapprox`` 168,
``higher-order`` 71, ``receiver-typed`` 30, ``trait-overapprox`` 9,
``trait-impl`` 2) plus ``candidate_count`` on 181 edges (2–37 candidates),
and the confidence tiers here are defined over that vocabulary.

**1,570 of rusi's 2,156 edges leave the workspace.** No rusi edge ever
originates from an external node (external calls are pure leaves), so a
centrality or chokepoint ranking that includes external nodes is dominated
by third-party leaf functions. Rankings therefore exclude external nodes
unless ``--include-external`` is passed, and both totals are printed either
way.

**Dead-code is the engine's verdict or nothing.** Only 20 of 315 dosai
``Reachability`` entries name a reachable entry point, so a naive
"no reachable entry point ⇒ deletable" metric would announce 295 deletable
functions on a 300-edge slice — while dosai's own ``DeadCode`` array in the
same file is empty and its own diagnostics say the dead-code list is capped
at 500. This module never derives dead-code; it reports the engine's own
list (dosai ``DeadCode[]``, golem ``reachability.nodes.reachableFromRoots``)
and explains what those verdicts do and do not mean.
"""

import logging
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

logger = logging.getLogger(__name__)

GRAPH_VERSION = 1

# Confidence tiers, most trusted first. The vocabulary is ours; the mapping
# from each engine's own fields is documented per adapter below. ``external``
# sits between exact and candidate: the call itself is resolved (it leaves
# the workspace to a known third-party function), but the target carries no
# local body and no dispatch decision.
CONFIDENCE_TIERS = ("exact", "external", "candidate", "unknown")

# rusi's call_type vocabulary -> tier. ``static-overapprox``,
# ``higher-order``, ``receiver-typed`` and ``trait-overapprox`` all mean "one
# edge emitted for each of several candidate targets" (candidate_count >= 2).
RUSI_CONFIDENCE = {
    "static": "exact",
    "trait-impl": "exact",
    "external": "external",
    "static-overapprox": "candidate",
    "higher-order": "candidate",
    "receiver-typed": "candidate",
    "trait-overapprox": "candidate",
}

# Betweenness enumerates one shortest-path DAG per source node; the cap
# bounds that enumeration. When it binds, the scores are a lower bound and
# the output says so — never silently.
DEFAULT_MAX_CHOKEPOINT_SOURCES = 64
MERMAID_NODE_CAP = 40


@dataclass
class CallNode:
    """One call-graph function in the unified shape.

    ``fan_in``/``fan_out``/``min_depth_from_entry``/``in_cycle`` are the
    engine's own values where it computes them (``depth_source="engine"``,
    ``cycle_source="engine"``) and ours only where it does not
    (``depth_source="derived"``) — the same distinction ``severity_source``
    makes for flows.
    """

    id: str
    name: str
    label: str = ""
    file: str = ""
    line: Optional[int] = None
    package: str = ""
    purl: str = ""
    external: bool = False
    kind: str = ""
    # The engine's short spelling (golem "Debug", rusi "alter_table", atom
    # "main"); ``name`` is the qualified one. Anchoring uses both.
    short_name: str = ""
    fan_in: Optional[int] = None
    fan_out: Optional[int] = None
    min_depth_from_entry: Optional[int] = None
    depth_source: str = ""
    in_cycle: Optional[bool] = None
    cycle_source: str = ""
    # Engine verdicts, carried verbatim where they exist.
    reachable_from_roots: Optional[bool] = None  # golem reachability.nodes
    reachable_entry_points: Optional[List[str]] = None  # dosai Reachability
    scc_id: Optional[Any] = None  # dosai SccId

    @property
    def where(self) -> str:
        if self.file and self.line:
            return f"{self.file}:{self.line}"
        return self.file


@dataclass
class CallEdge:
    """One caller→callee edge. ``call_type`` keeps the engine's vocabulary."""

    caller: str
    callee: str
    call_type: str = ""
    confidence: str = "unknown"  # our tier, mapped from the engine's fields
    dispatch_confidence: Optional[str] = None  # dosai DispatchConfidence verbatim
    location: str = ""  # file:line:column when the engine gives one
    candidate_count: Optional[int] = None  # rusi: candidates the edge came from
    call_site_count: Optional[int] = None  # dosai CallSiteCount / atom aggregated
    source_purl: str = ""  # dosai SourcePurl / golem sourcePurl
    target_purl: str = ""  # dosai TargetPurl / golem sinkPurl


@dataclass
class UnifiedCallGraph:
    """One engine's call graph, with whatever verdicts that engine emitted.

    ``nodes`` are shared, never copied, by confidence-filtered views of the
    same graph — engine verdicts ride on nodes and survive an edge filter
    unchanged.
    """

    engine: str
    source_file: str
    nodes: List[CallNode]
    edges: List[CallEdge]
    # The engine's own root/entry set (golem roots[], dosai EntryPoints
    # MethodIds). Not filtered to the node set — how many roots the graph
    # actually contains is itself a fact the output must be able to state.
    engine_roots: List[str] = field(default_factory=list)
    engine_root_reasons: Dict[str, int] = field(default_factory=dict)  # golem
    # In-file evidence that the graph is a subgraph of the engine's run
    # (golem callGraph.stats). False means "no such evidence", not "full".
    trimmed: bool = False
    full_nodes: Optional[int] = None
    full_edges: Optional[int] = None
    engine_dead_code: List[str] = field(default_factory=list)  # dosai DeadCode
    engine_diagnostics: List[str] = field(default_factory=list)
    # Engine cycle verdicts (dosai RecursionClusters), verbatim.
    engine_cycles: List[Dict] = field(default_factory=list)
    # golem reachability.paths: shortest witness paths, emitted only when the
    # run was given --reachable-symbols. Carried verbatim, never recomputed.
    engine_witness_paths: List[Dict] = field(default_factory=list)

    def __post_init__(self):
        self._index()

    def _index(self):
        self.by_id: Dict[str, CallNode] = {n.id: n for n in self.nodes}
        # Every name spelling a node carries -> ids, for anchoring flow
        # functions and CLI-supplied node names. Mirrors attack_surface.
        self.by_name: Dict[str, List[str]] = defaultdict(list)
        self.by_name_pkg: Dict[Tuple[str, str], List[str]] = defaultdict(list)
        for node in self.nodes:
            for spelling in {node.name, node.label, node.id}:
                if spelling:
                    self.by_name[spelling].append(node.id)
            for spelling in {node.short_name, node.name}:
                if spelling:
                    self.by_name_pkg[(spelling, node.package)].append(node.id)
        self.adj: Dict[str, List[str]] = defaultdict(list)
        self.in_edges: Dict[str, List[str]] = defaultdict(list)
        for edge in self.edges:
            if edge.caller in self.by_id and edge.callee in self.by_id:
                self.adj[edge.caller].append(edge.callee)
                self.in_edges[edge.callee].append(edge.caller)

    def view_with_edges(self, edges: List[CallEdge]) -> "UnifiedCallGraph":
        """A filtered view sharing this graph's nodes and engine verdicts."""
        return UnifiedCallGraph(
            engine=self.engine,
            source_file=self.source_file,
            nodes=self.nodes,
            edges=edges,
            engine_roots=self.engine_roots,
            engine_root_reasons=self.engine_root_reasons,
            trimmed=self.trimmed,
            full_nodes=self.full_nodes,
            full_edges=self.full_edges,
            engine_dead_code=self.engine_dead_code,
            engine_diagnostics=self.engine_diagnostics,
            engine_cycles=self.engine_cycles,
            engine_witness_paths=self.engine_witness_paths,
        )

    def anchor(self, name: str) -> List[str]:
        """Node ids for a function spelling: exact id, then unique name."""
        if name in self.by_id:
            return [name]
        same = self.by_name.get(name, [])
        return list(same) if len(same) == 1 else []

    @property
    def internal_ids(self) -> List[str]:
        return [n.id for n in self.nodes if not n.external]

    @property
    def external_ids(self) -> List[str]:
        return [n.id for n in self.nodes if n.external]

    def call_type_mix(self) -> Dict[str, int]:
        return dict(sorted(Counter(e.call_type for e in self.edges).items()))

    def confidence_mix(self) -> Dict[str, int]:
        return dict(sorted(Counter(e.confidence for e in self.edges).items()))

    def to_dict(self) -> Dict:
        return {
            "engine": self.engine,
            "sourceFile": self.source_file,
            "nodes": len(self.nodes),
            "edges": len(self.edges),
            "internalNodes": len(self.internal_ids),
            "externalNodes": len(self.external_ids),
            "engineRoots": len(self.engine_roots),
            "engineRootsInGraph": sum(1 for r in self.engine_roots if r in self.by_id),
            "engineRootReasons": dict(self.engine_root_reasons),
            "trimmed": self.trimmed,
            **({"fullNodes": self.full_nodes} if self.full_nodes else {}),
            **({"fullEdges": self.full_edges} if self.full_edges else {}),
            "callTypeMix": self.call_type_mix(),
            "confidenceMix": self.confidence_mix(),
            "engineDiagnostics": list(self.engine_diagnostics),
        }


# -- engine adapters ---------------------------------------------------------


def _diagnostic_text(diagnostic) -> str:
    """
    A diagnostic's message, not a Python dict repr of it.

    golem emits diagnostics as objects (``kind``/``message``/``position``);
    str() on one produces ``"{'position': {}, 'message': ...}"``, which is what
    the reader then sees in the output.
    """
    if isinstance(diagnostic, dict):
        message = diagnostic.get("message") or diagnostic.get("Message") or ""
        kind = diagnostic.get("kind") or diagnostic.get("Kind") or ""
        if message:
            return f"{kind}: {message}" if kind else str(message)
    return str(diagnostic)


def load_golem(content: Dict, path: str) -> UnifiedCallGraph:
    """
    golem ``callGraph``: nodes/edges/roots plus the engine's own reachability.

    ``reachability.nodes[]`` carries ``minDepth`` and ``rootIds`` alongside
    ``reachableFromRoots``, and ``reachability.paths[]`` carries shortest
    witness paths (``symbol``/``nodeIds``/``edgeIds``/``depth``). All three are
    ``omitempty``: the depth and roots appear only on nodes that are actually
    reachable, and the whole ``paths`` section only when the run was given
    ``--reachable-symbols``. Absent is therefore *not* evidence that golem
    cannot produce them — every fixture here was simply generated without the
    flag — so they are read when present rather than assumed away.
    """
    graph = content.get("callGraph") or {}
    if not graph.get("nodes") and not graph.get("edges"):
        raise ValueError(f"{path} carries no callGraph section.")
    reachability = graph.get("reachability") or {}
    reach = {
        r.get("nodeId"): r.get("reachableFromRoots")
        for r in reachability.get("nodes") or []
    }
    depths = {
        r.get("nodeId"): r.get("minDepth")
        for r in reachability.get("nodes") or []
        if isinstance(r.get("minDepth"), int)
    }
    root_ids = {
        r.get("nodeId"): list(r.get("rootIds") or [])
        for r in reachability.get("nodes") or []
        if r.get("rootIds")
    }
    witness_paths = [p for p in reachability.get("paths") or [] if isinstance(p, dict)]
    nodes = [
        CallNode(
            id=n.get("id") or "",
            name=n.get("label") or n.get("name") or n.get("id") or "",
            label=n.get("label") or "",
            file=(n.get("position") or {}).get("filename") or "",
            line=(n.get("position") or {}).get("line"),
            package=n.get("packagePath") or "",
            purl=n.get("purl") or "",
            external=bool(n.get("external")),
            kind=n.get("kind") or "",
            short_name=n.get("name") or "",
            reachable_from_roots=reach.get(n.get("id")),
            min_depth_from_entry=depths.get(n.get("id")),
            depth_source="engine" if n.get("id") in depths else "",
            reachable_entry_points=root_ids.get(n.get("id")) or [],
        )
        for n in graph.get("nodes") or []
    ]
    edges = [
        CallEdge(
            caller=e.get("sourceId") or "",
            callee=e.get("targetId") or "",
            call_type=e.get("callType") or "",
            confidence="exact" if (e.get("callType") or "static") == "static" else "candidate",
            location=_loc(e.get("position")),
            source_purl=e.get("sourcePurl") or "",
            target_purl=e.get("sinkPurl") or "",
        )
        for e in graph.get("edges") or []
    ]
    stats = graph.get("stats") or {}
    full_nodes, full_edges = stats.get("nodeCount"), stats.get("edgeCount")
    trimmed = bool(
        (full_nodes and full_nodes > len(nodes)) or (full_edges and full_edges > len(edges))
    )
    roots = graph.get("roots") or []
    return UnifiedCallGraph(
        engine="golem",
        source_file=str(path),
        nodes=nodes,
        edges=edges,
        engine_roots=[r.get("id") for r in roots if r.get("id")],
        engine_root_reasons=dict(Counter(r.get("rootReason") or "unspecified" for r in roots)),
        trimmed=trimmed,
        full_nodes=full_nodes,
        full_edges=full_edges,
        engine_diagnostics=[_diagnostic_text(d) for d in graph.get("diagnostics") or []],
        engine_witness_paths=witness_paths,
    )


def load_rusi(content: Dict, path: str) -> UnifiedCallGraph:
    """rusi ``call_graph``: the confidence-rich vocabulary (seven call types,
    ``candidate_count`` on over-approximated edges)."""
    graph = content.get("call_graph") or {}
    if not graph.get("nodes") and not graph.get("edges"):
        raise ValueError(f"{path} carries no call_graph section.")
    nodes_raw = graph.get("nodes") or []
    file_of = {}
    for n in nodes_raw:
        pos = n.get("position") or {}
        file_of[n.get("id")] = pos.get("filename") or n.get("file_path") or ""
    nodes = [
        CallNode(
            id=n.get("id") or "",
            name=n.get("qualified_name") or n.get("name") or n.get("id") or "",
            label=n.get("canonical_name") or "",
            file=file_of.get(n.get("id"), ""),
            line=(n.get("position") or {}).get("line"),
            package=n.get("package_path") or "",
            purl=n.get("purl") or "",
            external=bool(n.get("external")),
            kind=n.get("kind") or "",
            short_name=n.get("name") or "",
        )
        for n in nodes_raw
    ]
    edges = []
    for e in graph.get("edges") or []:
        call_type = e.get("call_type") or ""
        location = ""
        if e.get("line") is not None:
            location = f"{file_of.get(e.get('source_id'), '')}:{e.get('line')}"
            if e.get("column") is not None:
                location += f":{e.get('column')}"
        edges.append(
            CallEdge(
                caller=e.get("source_id") or "",
                callee=e.get("target_id") or "",
                call_type=call_type,
                confidence=RUSI_CONFIDENCE.get(call_type, "unknown"),
                location=location,
                candidate_count=e.get("candidate_count"),
            )
        )
    return UnifiedCallGraph(
        engine="rusi",
        source_file=str(path),
        nodes=nodes,
        edges=edges,
        engine_diagnostics=[
            d.get("message") or str(d)
            for d in graph.get("diagnostics") or []
            if isinstance(d, dict)
        ],
    )


def load_dosai(content: Dict, path: str) -> UnifiedCallGraph:
    """dosai ``CallGraph`` joined to the top-level ``Reachability[]`` by
    ``NodeId`` — the fan-in/fan-out table is a separate section, exactly as
    the flow adapters join ``Slices`` to ``Nodes``.

    FanIn/FanOut/InRecursiveCycle/DepthFromEntryPoint/ReachableEntryPoints
    are the engine's values over its whole run, even when the committed
    call graph is a slice of it (see PROVENANCE.md); they are carried
    verbatim and never recomputed.
    """
    if not (content.get("CallGraph") or {}).get("Nodes"):
        raise ValueError(
            "dosai dataflows/crypto reports carry no call graph; the call"
            " graph lives in the methods report (dosai methods --path ...)."
        )
    call_graph = content["CallGraph"]
    reach = {r.get("NodeId"): r for r in content.get("Reachability") or []}
    nodes = []
    for n in call_graph.get("Nodes") or []:
        facts = reach.get(n.get("Id")) or {}
        nodes.append(
            CallNode(
                id=n.get("Id") or "",
                name=n.get("Name") or n.get("Id") or "",
                label=n.get("Label") or "",
                file=n.get("FileName") or "",
                line=n.get("LineNumber"),
                package=n.get("Namespace") or "",
                purl=n.get("Purl") or "",
                external=bool(n.get("IsExternal")),
                kind=n.get("Kind") or "",
                short_name=n.get("Name") or "",
                fan_in=facts.get("FanIn"),
                fan_out=facts.get("FanOut"),
                min_depth_from_entry=facts.get("DepthFromEntryPoint"),
                depth_source=("engine" if facts.get("DepthFromEntryPoint") is not None else ""),
                in_cycle=facts.get("InRecursiveCycle"),
                cycle_source="engine" if facts.get("InRecursiveCycle") is not None else "",
                reachable_entry_points=facts.get("ReachableEntryPoints") or [],
                scc_id=facts.get("SccId"),
            )
        )
    edges = [
        CallEdge(
            caller=e.get("SourceId") or "",
            callee=e.get("TargetId") or "",
            call_type=e.get("CallType") or "",
            # DispatchConfidence is set only for virtual-dispatch candidates
            # (the same edges the engine marks SourceRoslynVirtualCandidate);
            # everything else is Roslyn-direct evidence.
            confidence=_dosai_confidence(e),
            dispatch_confidence=e.get("DispatchConfidence"),
            location=_dosai_loc(e),
            call_site_count=e.get("CallSiteCount"),
            source_purl=e.get("SourcePurl") or "",
            target_purl=e.get("TargetPurl") or "",
        )
        for e in call_graph.get("Edges") or []
    ]
    return UnifiedCallGraph(
        engine="dosai",
        source_file=str(path),
        nodes=nodes,
        edges=edges,
        engine_roots=[
            ep.get("MethodId") for ep in content.get("EntryPoints") or [] if ep.get("MethodId")
        ],
        engine_dead_code=[m.get("Id") for m in content.get("DeadCode") or [] if m.get("Id")],
        engine_diagnostics=[str(d) for d in content.get("Diagnostics") or []],
        engine_cycles=list(content.get("RecursionClusters") or []),
    )


def _dosai_confidence(edge: Dict) -> str:
    if edge.get("DispatchConfidence"):
        tier = {
            "exact": "exact",
            "rta-candidate": "candidate",
            "cha-candidate": "candidate",
        }.get(str(edge["DispatchConfidence"]).lower())
        return tier or "unknown"
    if edge.get("EvidenceKind") == "SourceRoslynVirtualCandidate":
        return "candidate"
    # SourceRoslynDirect / SourceRoslynDelegateTarget: Roslyn resolved it.
    return "exact"


GRAPHML_NS = "{http://graphml.graphdrawing.org/xmlns}"


def load_atom_graphml(path: str) -> UnifiedCallGraph:
    """atom's ``export --format graphml`` (the whole CPG): METHOD nodes and
    CALL edges, with each call site attributed to its caller by walking the
    AST parent chain.

    The CPG models a call site as a ``CALL`` node whose outgoing ``CALL``
    edge points at the callee ``METHOD``; the caller is the nearest ``METHOD``
    ancestor over ``AST`` edges. Multiple call sites for one (caller, callee)
    pair are aggregated into one edge carrying ``call_site_count`` — the same
    shape dosai's edges have. ``DISPATCH_TYPE`` maps STATIC_DISPATCH→exact,
    DYNAMIC_DISPATCH→candidate (one edge per virtual site; the runtime target
    set may be larger).
    """
    tree = ET.parse(path)
    graph = tree.getroot().find(f"{GRAPHML_NS}graph")
    if graph is None:
        raise ValueError(f"No <graph> element in {path}.")
    labels: Dict[str, str] = {}
    props: Dict[str, Dict[str, str]] = {}
    parents: Dict[str, str] = {}
    call_edges_raw: List[Tuple[str, str]] = []
    for el in graph:
        data = {d.get("key"): d.text for d in el.findall(f"{GRAPHML_NS}data")}
        if el.tag == f"{GRAPHML_NS}node":
            node_id = el.get("id") or ""
            labels[node_id] = data.get("labelV") or ""
            props[node_id] = data
        elif el.tag == f"{GRAPHML_NS}edge":
            label = data.get("labelE")
            if label == "CALL":
                call_edges_raw.append((el.get("source") or "", el.get("target") or ""))
            elif label == "AST":
                # AST edges run parent -> child.
                parents[el.get("target") or ""] = el.get("source") or ""

    def method_ancestor(node_id: str) -> Optional[str]:
        current = node_id
        seen = set()
        while current and current not in seen:
            seen.add(current)
            if labels.get(current) == "METHOD":
                return current
            current = parents.get(current)
        return None

    nodes = []
    for node_id, label in labels.items():
        if label != "METHOD":
            continue
        data = props[node_id]
        line = data.get("node__METHOD__LINE_NUMBER")
        nodes.append(
            CallNode(
                id=data.get("node__METHOD__FULL_NAME") or node_id,
                name=data.get("node__METHOD__FULL_NAME") or node_id,
                label=data.get("node__METHOD__NAME") or "",
                file=data.get("node__METHOD__FILENAME") or "",
                line=int(line) if line and line.isdigit() else None,
                # "<empty>" is atom's spelling of null here.
                package=(
                    parent
                    if (parent := data.get("node__METHOD__AST_PARENT_FULL_NAME"))
                    not in (None, "", "<empty>")
                    else ""
                ),
                external=data.get("node__METHOD__IS_EXTERNAL") == "true",
                kind="method",
                short_name=data.get("node__METHOD__NAME") or "",
            )
        )
    id_to_full = {
        node_id: props[node_id].get("node__METHOD__FULL_NAME") or node_id
        for node_id, lab in labels.items()
        if lab == "METHOD"
    }
    file_of = {n.id: n.file for n in nodes}
    aggregated: Dict[Tuple[str, str, str], Dict] = {}
    for source, target in call_edges_raw:
        if labels.get(target) != "METHOD":
            continue
        caller = method_ancestor(source)
        if not caller:
            continue
        dispatch = props.get(source, {}).get("node__CALL__DISPATCH_TYPE") or ""
        key = (id_to_full[caller], id_to_full[target], dispatch)
        entry = aggregated.setdefault(key, {"count": 0, "line": None})
        entry["count"] += 1
        line = props.get(source, {}).get("node__CALL__LINE_NUMBER")
        if entry["line"] is None and line and line.isdigit():
            entry["line"] = line
    edges = []
    for (caller, callee, dispatch), entry in sorted(aggregated.items()):
        location = (
            f"{file_of.get(caller, '')}:{entry['line']}"
            if entry["line"] is not None and file_of.get(caller)
            else file_of.get(caller, "")
        )
        edges.append(
            CallEdge(
                caller=caller,
                callee=callee,
                call_type=dispatch,
                confidence="exact" if dispatch == "STATIC_DISPATCH" else "candidate",
                location=location,
                call_site_count=entry["count"],
            )
        )
    return UnifiedCallGraph(engine="atom", source_file=str(path), nodes=nodes, edges=edges)


def _loc(position: Optional[Dict]) -> str:
    if not position:
        return ""
    parts = [position.get("filename") or ""]
    if position.get("line") is not None:
        parts.append(str(position.get("line")))
        if position.get("column") is not None:
            parts.append(str(position.get("column")))
    return ":".join(p for p in parts if p)


def _dosai_loc(edge: Dict) -> str:
    location = edge.get("CallLocation") or {}
    base = edge.get("Path") or location.get("FileName") or ""
    if location.get("LineNumber") is None:
        return base
    column = f":{location['ColumnNumber']}" if location.get("ColumnNumber") is not None else ""
    return f"{base}:{location['LineNumber']}{column}"


def load_call_graph(path: str, content: Optional[Any] = None) -> UnifiedCallGraph:
    """Load one input file into a :class:`UnifiedCallGraph`.

    ``content`` is the already-parsed document for JSON inputs; graphml
    inputs are parsed from the path.
    """
    from atom_tools.lib.adapters import detect_engine

    if str(path).endswith((".graphml", ".graph-ml")):
        return load_atom_graphml(str(path))
    if not isinstance(content, dict):
        raise ValueError(f"Could not read a call graph from {path}.")
    engine = detect_engine(content)
    if engine == "golem":
        return load_golem(content, str(path))
    if engine == "rusi":
        return load_rusi(content, str(path))
    if engine == "dosai":
        return load_dosai(content, str(path))
    raise ValueError(
        f"{path} carries no call graph this command can read (detected engine:"
        f" {engine or 'none'}). Known sources: golem analyze, rusi analyze,"
        " dosai methods, atom export --format graphml."
    )


# -- seeds: where paths start ------------------------------------------------


def flow_functions(report) -> Tuple[Set[str], Set[str]]:
    """The flow model's own source and sink function spellings.

    golem slices carry ``sourceFunction``/``sinkFunction``; rusi slices
    ``source_function``/``sink_function``. dosai methods reports carry no
    flows at all (flows live in the dataflows report, which has no call
    graph) — the empty sets say so.
    """
    sources, sinks = set(), set()
    for flow in report.flows:
        raw = flow.raw or {}
        if flow.engine == "golem":
            if raw.get("sourceFunction"):
                sources.add(raw["sourceFunction"])
            if raw.get("sinkFunction"):
                sinks.add(raw["sinkFunction"])
        elif flow.engine == "rusi":
            if raw.get("source_function"):
                sources.add(raw["source_function"])
            if raw.get("sink_function"):
                sinks.add(raw["sink_function"])
    return sources, sinks


def anchor_all(graph: UnifiedCallGraph, names: Iterable[str]) -> List[str]:
    anchored = []
    for name in sorted(names):
        anchored.extend(graph.anchor(name))
    return sorted(set(anchored))


def endpoint_seeds(graph: UnifiedCallGraph, endpoints: Sequence[Dict]) -> List[str]:
    """Anchor endpoint handlers in the graph: id, handler name scoped by the
    endpoint's package, unique name, then the endpoint's file range (gin
    reports most handlers as the literal string "func literal", so the range
    is the only usable anchor for those)."""
    seeds = set()
    by_file: Dict[str, List[Tuple[Optional[int], str]]] = defaultdict(list)
    for node in graph.nodes:
        if node.file:
            by_file[node.file].append((node.line, node.id))
    for ep in endpoints:
        raw = ep.get("raw") or ep
        handler = ep.get("handler")
        anchored = graph.anchor(handler) if handler else []
        if not anchored and handler:
            by_pkg = graph.by_name_pkg.get((handler, ep.get("package") or ""))
            if by_pkg:
                anchored = list(by_pkg)
        if not anchored:
            rng = raw.get("range") or {}
            start, end = rng.get("start") or {}, rng.get("end") or {}
            filename = start.get("filename") or ep.get("file") or ""
            first = start.get("line")
            if filename and first is not None:
                last = end.get("line") if end.get("line") is not None else first
                anchored = [
                    node_id
                    for line, node_id in by_file.get(filename, [])
                    if line is None or first <= line <= last
                ]
        seeds.update(anchored)
    return sorted(seeds)


def entry_seeds(graph: UnifiedCallGraph, endpoints: Sequence[Dict]) -> Tuple[List[str], Dict]:
    """Where entry-depth BFS starts, in decreasing order of engine authority.

    1. the engine's own root/entry set, when those nodes are in the graph
       (golem ``roots``; dosai ``EntryPoints`` — 0 of 32 MethodIds are nodes
       of the committed slice, so this legitimately misses there);
    2. endpoint handlers anchored in the graph (golem/rusi endpoints);
    3. zero-in-degree internal nodes — ours, labeled ``derived``.

    The policy used is returned alongside the seeds so the output can say
    which rung of the ladder produced the numbers.
    """
    roots_in = [r for r in graph.engine_roots if r in graph.by_id]
    if roots_in:
        return sorted(set(roots_in)), {"policy": "engine-roots", "source": "engine"}
    if endpoints:
        seeds = endpoint_seeds(graph, endpoints)
        if seeds:
            return seeds, {"policy": "endpoints", "source": "engine"}
    seeds = [node_id for node_id in graph.internal_ids if not graph.in_edges.get(node_id)]
    return sorted(seeds), {"policy": "zero-indegree", "source": "derived"}


# -- confidence filter --------------------------------------------------------


def filter_by_confidence(
    graphs: Sequence[UnifiedCallGraph], min_confidence: str
) -> Tuple[List[UnifiedCallGraph], List[Dict]]:
    """View of each graph keeping only edges at or above the tier.

    Returns the views plus one report each (kept/dropped), so a no-op
    filter — golem's single-valued graph — is stated, not implied.
    """
    if min_confidence not in CONFIDENCE_TIERS:
        raise ValueError(
            f"Unknown confidence: {min_confidence}. Known: {', '.join(CONFIDENCE_TIERS)}"
        )
    floor = CONFIDENCE_TIERS.index(min_confidence)
    out, reports = [], []
    for graph in graphs:
        mix = graph.confidence_mix()
        below = sum(v for k, v in mix.items() if CONFIDENCE_TIERS.index(k) > floor)
        edges = [e for e in graph.edges if CONFIDENCE_TIERS.index(e.confidence) <= floor]
        report = {
            "engine": graph.engine,
            "sourceFile": graph.source_file,
            "edgesBefore": len(graph.edges),
            "edgesKept": len(edges),
            "edgesDropped": below,
            "keptMix": dict(sorted(Counter(e.confidence for e in edges).items())),
        }
        if below == 0:
            report["note"] = (
                "no-op: every edge is the same confidence tier"
                f" ({next(iter(mix))}), so this filter cannot reduce the graph"
                if len(mix) == 1
                else "no-op: no edge sits below the requested tier"
            )
        elif not edges:
            report["note"] = "removed every edge: nothing in this graph reaches the tier"
        out.append(graph.view_with_edges(edges))
        reports.append(report)
    return out, reports


# -- metrics ------------------------------------------------------------------


def _restricted_betweenness(
    graph: UnifiedCallGraph, sources: Sequence[str], sink_ids: Set[str]
) -> Tuple[Dict[str, float], int]:
    """Brandes' accumulation over shortest paths from ``sources`` into
    ``sink_ids`` only (the flow model's source→sink pairs).

    One BFS-with-path-counting per source bounds the work; no path is ever
    materialised. Returns per-node betweenness and the number of
    source→sink pairs connected by at least one path.
    """
    betweenness: Dict[str, float] = defaultdict(float)
    pairs = 0
    for source in sources:
        sigma: Dict[str, int] = defaultdict(int)
        dist: Dict[str, int] = {source: 0}
        pred: Dict[str, List[str]] = defaultdict(list)
        sigma[source] = 1
        queue = deque([source])
        order: List[str] = []
        while queue:
            node = queue.popleft()
            order.append(node)
            for nxt in graph.adj.get(node, ()):
                if nxt not in dist:
                    dist[nxt] = dist[node] + 1
                    queue.append(nxt)
                if dist[nxt] == dist[node] + 1:
                    sigma[nxt] += sigma[node]
                    pred[nxt].append(node)
        pairs += sum(1 for t in sink_ids if t in dist and t != source)
        delta: Dict[str, float] = defaultdict(float)
        for node in reversed(order):
            for parent in pred[node]:
                share = sigma[parent] / sigma[node] if sigma[node] else 0.0
                delta[parent] += share * ((1.0 if node in sink_ids else 0.0) + delta[node])
            if node != source:
                betweenness[node] += delta[node]
    return dict(betweenness), pairs


def compute_chokepoints(
    graph: UnifiedCallGraph,
    flow_sources: Optional[Set[str]] = None,
    flow_sinks: Optional[Set[str]] = None,
    endpoints: Optional[Sequence[Dict]] = None,
    max_sources: int = DEFAULT_MAX_CHOKEPOINT_SOURCES,
    include_external: bool = False,
) -> Dict:
    """Nodes on the most source→sink shortest paths — one fix, most paths.

    Sources come from the flow model where one is joined (golem/rusi flows
    anchored in the graph), else the engine's roots, else anchored
    endpoints, else zero-in-degree internal nodes; every rung below the
    first is labeled. When more sources exist than ``max_sources``, only the
    first ``max_sources`` (sorted, so the cut is deterministic) are
    enumerated and the output says the scores are a lower bound — the cap is
    never applied silently.
    """
    flow_sources = flow_sources or set()
    flow_sinks = flow_sinks or set()
    anchored_sources = anchor_all(graph, flow_sources)
    anchored_sinks = anchor_all(graph, flow_sinks)
    diagnostics: List[str] = []
    if anchored_sources and anchored_sinks:
        sources, sinks = anchored_sources, set(anchored_sinks)
        seed = {"policy": "flow-sources→flow-sinks", "source": "engine"}
        diagnostics.append(
            f"{len(anchored_sources)} of {len(flow_sources)} flow source function(s)"
            f" and {len(anchored_sinks)} of {len(flow_sinks)} sink function(s)"
            " anchored in the call graph; the rest are not nodes of it."
        )
    else:
        sources, seed = entry_seeds(graph, endpoints or [])
        sinks = set(graph.by_id)
        if flow_sources and not anchored_sources:
            diagnostics.append(
                "no flow source function anchors in this call graph; fell back"
                f" to '{seed['policy']}' seeds."
            )
    if not sources:
        return {
            "engine": graph.engine,
            "sourceFile": graph.source_file,
            "computed": False,
            "reason": (
                "no source node could be identified (no flow model joined, no"
                " engine roots in the graph, and no zero-in-degree node to"
                " fall back to)"
            ),
            "diagnostics": diagnostics,
        }
    capped = len(sources) > max_sources
    used = sorted(sources)[:max_sources]
    betweenness, pairs = _restricted_betweenness(graph, used, sinks)
    rows = []
    for node_id, score in sorted(betweenness.items(), key=lambda kv: (-kv[1], kv[0])):
        if score <= 0:
            # Nodes with no positive betweenness sit on no source→sink path as
            # an intermediate; listing them would rank noise.
            continue
        node = graph.by_id.get(node_id)
        if node is None or (node.external and not include_external):
            continue
        rows.append(
            {
                "id": node.id,
                "name": node.name,
                "file": node.file,
                "line": node.line,
                "package": node.package,
                "external": node.external,
                "betweenness": round(score, 3),
                "pairShare": round(score / pairs, 3) if pairs else 0.0,
                **(
                    {"engineFanIn": node.fan_in, "engineFanOut": node.fan_out}
                    if node.fan_in is not None or node.fan_out is not None
                    else {}
                ),
            }
        )
    result = {
        "engine": graph.engine,
        "sourceFile": graph.source_file,
        "computed": True,
        "seeds": {**seed, "sources": len(sources), "sinks": len(sinks), "pairs": pairs},
        "externalNodesExcludedFromRanking": (0 if include_external else len(graph.external_ids)),
        "ranked": rows,
        "diagnostics": diagnostics,
    }
    if capped:
        result["capped"] = {
            "sourcesEnumerated": max_sources,
            "sourcesAvailable": len(sources),
            "effect": "betweenness scores are a lower bound",
        }
    return result


def compute_centrality(
    graph: UnifiedCallGraph,
    include_external: bool = False,
    algorithms: Optional[Dict[str, Dict]] = None,
) -> Dict:
    """PageRank and degree. Ours is computed here; atom's own
    ``algorithms --type centrality`` values, when supplied, are joined by
    method name and kept verbatim next to ours."""
    out_degree = Counter(e.caller for e in graph.edges)
    in_degree = Counter(e.callee for e in graph.edges)
    ranks = _pagerank(list(graph.by_id), graph.adj)
    atom_by_method = {
        entry.get("method"): entry
        for entry in (algorithms or {}).get("centrality", {}).get("ranking") or []
    }
    joined = 0
    rows = []
    for node in graph.nodes:
        if node.external and not include_external:
            continue
        row = {
            "id": node.id,
            "name": node.name,
            "file": node.file,
            "line": node.line,
            "package": node.package,
            "external": node.external,
            "pageRank": round(ranks.get(node.id, 0.0), 6),
            "inDegree": in_degree.get(node.id, 0),
            "outDegree": out_degree.get(node.id, 0),
        }
        if node.fan_in is not None or node.fan_out is not None:
            row["engineFanIn"], row["engineFanOut"] = node.fan_in, node.fan_out
        atom_row = atom_by_method.get(node.id)
        if atom_row is not None:
            joined += 1
            row["atomPageRank"] = atom_row.get("pageRank")
            row["atomInDegree"] = atom_row.get("inDegree")
        rows.append(row)
    rows.sort(key=lambda r: (-r["pageRank"], r["id"]))
    return {
        "engine": graph.engine,
        "sourceFile": graph.source_file,
        "computed": True,
        "externalNodesExcludedFromRanking": (0 if include_external else len(graph.external_ids)),
        "atomAlgorithmsJoined": joined,
        "ranked": rows,
    }


def _pagerank(
    nodes: Sequence[str],
    adj: Dict[str, List[str]],
    damping: float = 0.85,
    tol: float = 1e-8,
    max_iter: int = 100,
) -> Dict[str, float]:
    if not nodes:
        return {}
    node_set = set(nodes)
    out_count = Counter()
    for caller, callees in adj.items():
        if caller in node_set:
            out_count[caller] += len([c for c in callees if c in node_set])
    ranks = {n: 1.0 / len(nodes) for n in nodes}
    dangling = [n for n in nodes if out_count.get(n, 0) == 0]
    for _ in range(max_iter):
        base = (1 - damping) / len(nodes)
        dangling_share = damping * sum(ranks[n] for n in dangling) / len(nodes)
        incoming: Dict[str, float] = defaultdict(float)
        for caller, callees in adj.items():
            if caller not in node_set or out_count.get(caller, 0) == 0:
                continue
            share = ranks[caller] / out_count[caller]
            for callee in callees:
                if callee in node_set:
                    incoming[callee] += share
        fresh = {n: base + dangling_share + damping * incoming.get(n, 0.0) for n in nodes}
        delta = sum(abs(fresh[n] - ranks[n]) for n in nodes)
        ranks = fresh
        if delta < tol:
            break
    return ranks


def compute_blast_radius(graph: UnifiedCallGraph, node_ref: str, max_depth: int = 1000) -> Dict:
    """Everything that falls when one function is compromised: the forward
    closure of the node, split internal/external, with files and packages."""
    ids = graph.anchor(node_ref)
    if not ids:
        raise ValueError(
            f"Node '{node_ref}' not found in {graph.source_file}: not a node id"
            " and not a unique node name."
        )
    start = ids[0]
    depths = {start: 0}
    queue = deque([start])
    reached = {start}
    while queue:
        current = queue.popleft()
        if depths[current] >= max_depth:
            continue
        for nxt in graph.adj.get(current, ()):
            if nxt not in reached:
                reached.add(nxt)
                depths[nxt] = depths[current] + 1
                queue.append(nxt)
    nodes = [graph.by_id[i] for i in reached if i in graph.by_id]
    internal = [n for n in nodes if not n.external]
    external = [n for n in nodes if n.external]
    return {
        "engine": graph.engine,
        "sourceFile": graph.source_file,
        "computed": True,
        "node": start,
        "name": graph.by_id[start].name,
        "file": graph.by_id[start].file,
        "line": graph.by_id[start].line,
        "package": graph.by_id[start].package,
        "reachIncludingSelf": len(reached),
        "internalReachable": len(internal),
        "externalReachable": len(external),
        "maxDepth": max(depths.values()),
        "files": sorted({n.file for n in nodes if n.file}),
        "packages": sorted({n.package for n in nodes if n.package}),
        "purls": sorted({n.purl for n in nodes if n.purl}),
        "externalTargets": sorted(n.name for n in external)[:50],
    }


def compute_entry_depth(
    graph: UnifiedCallGraph, endpoints: Optional[Sequence[Dict]] = None
) -> Dict:
    """Minimum hops from the nearest entry point.

    Two engines supply this themselves and are never second-guessed:

    - dosai's ``DepthFromEntryPoint``, on exactly the nodes it deems reachable
      from entry points (20 of 315 in the fixture). Nothing is derived beside
      them: the engine's entry points are not nodes of the committed slice, so
      a BFS over that subgraph could only ever reproduce "unreachable".
    - golem's ``reachability.nodes[].minDepth``, present on the nodes
      reachable from its own roots. Those are carried as ``engine`` and a BFS
      fills in the rest, labeled ``derived`` — the two are reported separately
      rather than blended, and the diagnostic says which covered what.

    Everything else gets a BFS over the engine's own seeds, labeled
    ``derived``.
    """
    endpoints = endpoints or []
    engine_depths = {
        n.id: n.min_depth_from_entry for n in graph.nodes if n.min_depth_from_entry is not None
    }
    rows: List[Dict] = []
    diagnostics: List[str] = []
    derived_count = 0
    if graph.engine == "dosai" and engine_depths:
        for node in sorted(engine_depths, key=lambda i: (engine_depths[i], i)):
            entry = graph.by_id[node]
            rows.append(
                {
                    "id": entry.id,
                    "name": entry.name,
                    "file": entry.file,
                    "line": entry.line,
                    "package": entry.package,
                    "depth": entry.min_depth_from_entry,
                    "depthSource": "engine",
                    "entryPoints": entry.reachable_entry_points or [],
                }
            )
        diagnostics.append(
            f"dosai's own DepthFromEntryPoint covers {len(engine_depths)} of"
            f" {len(graph.nodes)} nodes (the ones it deems reachable from entry"
            " points); the rest are, per the engine, unreachable from any entry"
            " point over its full run, so no depth is derived for them here."
        )
        seeds = {"policy": "engine-depths", "source": "engine", "sources": len(engine_depths)}
    else:
        for node_id in sorted(engine_depths, key=lambda i: (engine_depths[i], i)):
            entry = graph.by_id[node_id]
            rows.append(
                {
                    "id": entry.id,
                    "name": entry.name,
                    "file": entry.file,
                    "line": entry.line,
                    "package": entry.package,
                    "depth": entry.min_depth_from_entry,
                    "depthSource": "engine",
                    "entryPoints": entry.reachable_entry_points or [],
                }
            )
        if engine_depths:
            diagnostics.append(
                f"{len(engine_depths)} node(s) carry the engine's own depth from its"
                " roots; those are reported as 'engine' and are not recomputed."
            )
        sources, seed = entry_seeds(graph, endpoints)
        if sources:
            depths = {k: v for k, v in _bfs_depths(graph, sources).items() if k not in engine_depths}
            # External nodes are reached but not listed, so the count has to be
            # of what is actually reported -- a count larger than the rows it
            # describes is the kind of small discrepancy that makes a reader
            # stop trusting the rest of the document.
            derived_count = sum(
                1 for n in graph.nodes if n.id in depths and not n.external
            )
            supplies = (
                "the engine supplied no depth for these nodes"
                if engine_depths
                else "this engine supplies no depth of its own"
            )
            diagnostics.append(
                f"entry-depth derived by BFS from {len(sources)} seed(s) via the"
                f" '{seed['policy']}' policy; {supplies}."
            )
            for node in sorted(graph.nodes, key=lambda n: (depths.get(n.id, 1 << 30), n.id)):
                if node.id not in depths or node.external:
                    continue
                rows.append(
                    {
                        "id": node.id,
                        "name": node.name,
                        "file": node.file,
                        "line": node.line,
                        "package": node.package,
                        "depth": depths[node.id],
                        "depthSource": "derived",
                    }
                )
            seeds = {**seed, "sources": len(sources)}
        else:
            seeds = {"policy": "none", "source": "none", "sources": 0}
            diagnostics.append("no entry seeds found; entry-depth not derived.")
    engine_unreachable = sum(
        1
        for n in graph.nodes
        if n.reachable_entry_points is not None and not n.reachable_entry_points
    )
    return {
        "engine": graph.engine,
        "sourceFile": graph.source_file,
        "computed": bool(rows),
        "seeds": seeds,
        "engineDepths": len(engine_depths),
        "derivedDepths": derived_count,
        "engineUnreachableFromEntryPoints": engine_unreachable or None,
        "depths": rows,
        "diagnostics": diagnostics,
    }


def _bfs_depths(graph: UnifiedCallGraph, seeds: Sequence[str]) -> Dict[str, int]:
    depths = {s: 0 for s in seeds}
    queue = deque(seeds)
    while queue:
        current = queue.popleft()
        for nxt in graph.adj.get(current, ()):
            if nxt not in depths:
                depths[nxt] = depths[current] + 1
                queue.append(nxt)
    return depths


def compute_dead_code(graph: UnifiedCallGraph) -> Dict:
    """Dead code is the engine's verdict or nothing.

    A naive metric — "no reachable entry point ⇒ deletable" — would announce
    295 deletable functions on the dosai fixture (only 20 of 315
    Reachability entries name a reachable entry point) while the engine's
    own ``DeadCode`` array is empty and its diagnostics say that list is
    capped at 500. Unreachable-from-entry-points is *not* dead code (it
    includes functions called only from main, tests, or background work),
    so this metric never derives it: dosai's ``DeadCode[]`` and golem's
    ``reachableFromRoots`` are reported as what they are, with their
    definitions attached.
    """
    result: Dict[str, Any] = {
        "engine": graph.engine,
        "sourceFile": graph.source_file,
        "diagnostics": [],
    }
    if graph.engine == "dosai":
        unreachable = sum(
            1
            for n in graph.nodes
            if n.reachable_entry_points is not None and not n.reachable_entry_points
        )
        result.update(
            {
                "computed": True,
                "source": "engine",
                "deadCode": list(graph.engine_dead_code),
                "deadCodeCount": len(graph.engine_dead_code),
                **({"unreachableFromEntryPointsPerEngine": unreachable} if unreachable else {}),
            }
        )
        if unreachable:
            result["diagnostics"].append(
                f"{unreachable} of {len(graph.nodes)} nodes have no reachable"
                " entry point per the engine's own reachability — that is not a"
                " deletability verdict (functions called only from main, tests"
                " or background work are unreachable from entry points too),"
                " and it is reported separately from DeadCode on purpose."
            )
        for diagnostic in graph.engine_diagnostics:
            if "dead" in diagnostic.lower():
                result["diagnostics"].append(f"engine diagnostic: {diagnostic}")
        if not graph.engine_dead_code:
            result["diagnostics"].append("the engine's DeadCode array is empty in this input.")
        return result
    if graph.engine == "golem":
        verdicts = [n for n in graph.nodes if n.reachable_from_roots is not None]
        unreachable = [n for n in verdicts if n.reachable_from_roots is False]
        result.update(
            {
                "computed": True,
                "source": "engine",
                "unreachableFromRootsPerEngine": len(unreachable),
                "nodesWithVerdict": len(verdicts),
                "rootsTotal": len(graph.engine_roots),
                "rootsInGraph": sum(1 for r in graph.engine_roots if r in graph.by_id),
                "rootReasons": dict(graph.engine_root_reasons),
            }
        )
        result["diagnostics"].append(
            "golem's reachability measures reachability from its own roots"
            f" ({len(graph.engine_roots)} root(s), reasons:"
            f" {', '.join(f'{k} {v}' for k, v in sorted(graph.engine_root_reasons.items()))});"
            " unreachable-from-roots is the engine's liveness verdict over its"
            " full run, not a deletability claim."
        )
        if graph.engine_roots and not any(r in graph.by_id for r in graph.engine_roots):
            result["diagnostics"].append(
                "none of the engine's roots are nodes of this (sub)graph, so the"
                " verdicts above cannot be re-checked here."
            )
        return result
    result.update(
        {
            "computed": False,
            "source": "none",
            "reason": (
                f"{graph.engine} emits no dead-code or liveness verdict, and"
                " atom-tools will not derive one: 'unreachable from the entry"
                " points we happen to have' is not dead code."
            ),
        }
    )
    return result


def compute_cycles(graph: UnifiedCallGraph, algorithms: Optional[Dict[str, Dict]] = None) -> Dict:
    """Recursion clusters: dosai's ``RecursionClusters`` verbatim, atom's
    ``algorithms --type scc`` verbatim when supplied, Tarjan-derived
    (labeled) everywhere else."""
    result: Dict[str, Any] = {
        "engine": graph.engine,
        "sourceFile": graph.source_file,
    }
    if graph.engine == "dosai" and graph.engine_cycles:
        clusters = [
            {"id": c.get("Id"), "size": c.get("Size"), "members": c.get("MemberIds") or []}
            for c in graph.engine_cycles
        ]
        result.update(
            {
                "computed": True,
                "source": "engine",
                "clusters": clusters,
                "clusterCount": len(clusters),
                "recursiveClusterCount": len(clusters),
                "nodesInRecursiveCycle": sum(1 for n in graph.nodes if n.in_cycle),
            }
        )
        return result
    atom_scc = (algorithms or {}).get("scc") or {}
    if graph.engine == "atom" and atom_scc:
        result.update(
            {
                "computed": True,
                "source": "engine",
                "clusterCount": atom_scc.get("componentCount"),
                "recursiveClusterCount": atom_scc.get("recursiveComponentCount"),
                "clusters": [
                    {"members": members} for members in atom_scc.get("recursiveComponents") or []
                ],
            }
        )
        return result
    clusters = _tarjan(graph)
    recursive = [c for c in clusters if len(c) > 1]
    recursive += [c for c in clusters if len(c) == 1 and c[0] in graph.adj.get(c[0], ())]
    recursive.sort(key=lambda c: (-len(c), c[0]))
    result.update(
        {
            "computed": True,
            "source": "derived",
            "clusterCount": len(clusters),
            "recursiveClusterCount": len(recursive),
            "clusters": [{"members": c} for c in recursive],
        }
    )
    return result


def _tarjan(graph: UnifiedCallGraph) -> List[List[str]]:
    """Iterative Tarjan SCC over the whole node set."""
    index: Dict[str, int] = {}
    low: Dict[str, int] = {}
    on_stack: Set[str] = set()
    stack: List[str] = []
    components: List[List[str]] = []
    counter = 0
    for root in graph.by_id:
        if root in index:
            continue
        index[root] = low[root] = counter
        counter += 1
        stack.append(root)
        on_stack.add(root)
        work = [(root, iter(graph.adj.get(root, ())))]
        while work:
            node, neighbours = work[-1]
            advanced = False
            for nxt in neighbours:
                if nxt not in graph.by_id:
                    continue
                if nxt not in index:
                    index[nxt] = low[nxt] = counter
                    counter += 1
                    stack.append(nxt)
                    on_stack.add(nxt)
                    work.append((nxt, iter(graph.adj.get(nxt, ()))))
                    advanced = True
                    break
                if nxt in on_stack:
                    low[node] = min(low[node], index[nxt])
            if advanced:
                continue
            work.pop()
            if work:
                parent = work[-1][0]
                low[parent] = min(low[parent], low[node])
            if low[node] == index[node]:
                component = []
                while True:
                    member = stack.pop()
                    on_stack.discard(member)
                    component.append(member)
                    if member == node:
                        break
                components.append(sorted(component))
    return components


# -- the document -------------------------------------------------------------


METRICS = (
    "chokepoints",
    "centrality",
    "blast-radius",
    "entry-depth",
    "dead-code",
    "cycles",
)


def compute_graph_document(
    graphs: Sequence[UnifiedCallGraph],
    metric: str,
    flow_sources: Optional[Set[str]] = None,
    flow_sinks: Optional[Set[str]] = None,
    endpoints_by_source: Optional[Dict[str, List[Dict]]] = None,
    min_confidence: str = "",
    include_external: bool = False,
    blast_radius_node: str = "",
    max_chokepoint_sources: int = DEFAULT_MAX_CHOKEPOINT_SOURCES,
    algorithms: Optional[Dict[str, Dict]] = None,
) -> Dict:
    """Compute one metric over one or more call graphs.

    Engines mix freely; each graph keeps its own engine's verdicts and its
    own seed policy. ``endpoints_by_source`` maps a source file path to that
    input's endpoints (for seed anchoring), so seeds from one engine's id
    space are never handed to another's graph.
    """
    if metric not in METRICS:
        raise ValueError(f"Unknown metric: {metric}. Known: {', '.join(METRICS)}")
    if metric == "blast-radius" and not blast_radius_node:
        raise ValueError("The blast-radius metric needs --blast-radius NODE.")
    diagnostics: List[str] = []
    if min_confidence:
        graphs, reports = filter_by_confidence(graphs, min_confidence)
        for report in reports:
            note = report.get("note")
            diagnostics.append(
                f"--min-confidence {min_confidence} on {report['engine']}"
                f" ({report['sourceFile']}): kept {report['edgesKept']} of"
                f" {report['edgesBefore']} edges" + (f" — {note}" if note else "")
            )
    endpoints_by_source = endpoints_by_source or {}

    results = []
    for graph in graphs:
        endpoints = endpoints_by_source.get(graph.source_file, [])
        if metric == "chokepoints":
            result = compute_chokepoints(
                graph,
                flow_sources=flow_sources,
                flow_sinks=flow_sinks,
                endpoints=endpoints,
                max_sources=max_chokepoint_sources,
                include_external=include_external,
            )
        elif metric == "centrality":
            result = compute_centrality(graph, include_external, algorithms)
        elif metric == "blast-radius":
            result = compute_blast_radius(graph, blast_radius_node)
        elif metric == "entry-depth":
            result = compute_entry_depth(graph, endpoints)
        elif metric == "dead-code":
            result = compute_dead_code(graph)
        else:
            result = compute_cycles(graph, algorithms)
        results.append(result)
        for diagnostic in result.pop("diagnostics", []):
            diagnostics.append(f"{graph.engine}: {diagnostic}")
        if graph.trimmed:
            diagnostics.append(
                f"{graph.engine} call graph in {graph.source_file} is a subgraph"
                f" of the engine's run ({len(graph.edges)} of {graph.full_edges}"
                f" edges, {len(graph.nodes)} of {graph.full_nodes} nodes, per its"
                " own stats block); every metric is computed within that"
                " subgraph."
            )

    return {
        "graphVersion": GRAPH_VERSION,
        "metric": metric,
        "engines": sorted({g.engine for g in graphs}),
        "sources": [g.source_file for g in graphs],
        "options": {
            "minConfidence": min_confidence or None,
            "includeExternal": include_external,
            **(
                {"maxChokepointSources": max_chokepoint_sources} if metric == "chokepoints" else {}
            ),
            **({"node": blast_radius_node} if blast_radius_node else {}),
        },
        "graphs": [g.to_dict() for g in graphs],
        "results": results,
        "diagnostics": diagnostics,
    }


# -- renderings ---------------------------------------------------------------


METRIC_TITLES = {
    "chokepoints": "chokepoints — nodes on the most source→sink paths",
    "centrality": "centrality — PageRank and degree",
    "blast-radius": "blast radius — what falls if one node is compromised",
    "entry-depth": "entry-depth — hops behind the front door",
    "dead-code": "dead-code — the engine's own verdict",
    "cycles": "cycles — recursion clusters",
}


def _display(row: Dict) -> str:
    where = f"  {row.get('file', '')}" if row.get("file") else ""
    if where and row.get("line"):
        where += f":{row['line']}"
    pkg = f"  [{row.get('package')}]" if row.get("package") else ""
    ext = "  (external)" if row.get("external") else ""
    return f"{row.get('name') or row.get('id') or ''}{where}{pkg}{ext}"


def render_console(document: Dict, top: int = 15) -> List[str]:
    """Console rendering, as lines for cleo's io — never bare print()."""
    lines: List[str] = []
    metric = document["metric"]
    lines.append(
        f"Call graph metric: {METRIC_TITLES[metric]}"
        f" ({'+'.join(document['engines'])}, {len(document['sources'])} input(s))"
    )
    for graph in document["graphs"]:
        lines.append(
            f"{graph['engine']}: {graph['nodes']} nodes"
            f" ({graph['internalNodes']} internal, {graph['externalNodes']} external),"
            f" {graph['edges']} edges"
        )
        mix = ", ".join(f"{k} {v}" for k, v in graph["callTypeMix"].items())
        lines.append(f"  call types: {mix}")
        if graph["engineRoots"]:
            lines.append(
                f"  engine roots: {graph['engineRootsInGraph']} of"
                f" {graph['engineRoots']} in this graph"
            )
    for result in document["results"]:
        lines.append("")
        lines.append(f"-- {result['engine']} ({result['sourceFile']}) --")
        if not result.get("computed"):
            lines.append(f"not computed: {result.get('reason', 'no data')}")
            continue
        if metric == "chokepoints":
            lines.extend(_render_chokepoints(result, top))
        elif metric == "centrality":
            lines.extend(_render_centrality(result, top))
        elif metric == "blast-radius":
            lines.extend(_render_blast_radius(result))
        elif metric == "entry-depth":
            lines.extend(_render_entry_depth(result, top))
        elif metric == "dead-code":
            lines.extend(_render_dead_code(result))
        else:
            lines.extend(_render_cycles(result, top))
    for diagnostic in document["diagnostics"]:
        lines.append(f"note: {diagnostic}")
    return lines


def _render_chokepoints(result: Dict, top: int) -> List[str]:
    lines = []
    seeds = result["seeds"]
    lines.append(
        f"seeds: {seeds['sources']} source(s) → {seeds['sinks']} sink(s)"
        f" via {seeds['policy']} ({seeds['source']});"
        f" {seeds['pairs']} source→sink pair(s) connected"
    )
    if result.get("capped"):
        cap = result["capped"]
        lines.append(
            f"PATH ENUMERATION CAPPED at {cap['sourcesEnumerated']} of"
            f" {cap['sourcesAvailable']} source nodes — {cap['effect']}."
        )
    excluded = result.get("externalNodesExcludedFromRanking")
    if excluded:
        lines.append(
            f"{excluded} external node(s) excluded from the ranking"
            " (--include-external to rank them)."
        )
    rows = result["ranked"][:top]
    if not rows:
        lines.append("no node lies on any source→sink path.")
        return lines
    for position, row in enumerate(rows, 1):
        engine = ""
        if "engineFanIn" in row:
            engine = f"  engine fan-in/out {row['engineFanIn']}/{row['engineFanOut']}"
        lines.append(
            f"{position:>3}. {_display(row)}  betweenness {row['betweenness']}"
            f"  ({round(100 * row['pairShare'])}% of pairs){engine}"
        )
    total = len(result["ranked"])
    if total > top:
        lines.append(f"… {total - top} more ranked node(s) in the json output.")
    return lines


def _render_centrality(result: Dict, top: int) -> List[str]:
    lines = []
    excluded = result.get("externalNodesExcludedFromRanking")
    if excluded:
        lines.append(
            f"{excluded} external node(s) excluded from the ranking"
            " (--include-external to rank them)."
        )
    if result.get("atomAlgorithmsJoined"):
        lines.append(
            f"atom's own algorithms --type centrality ranking joined verbatim"
            f" for {result['atomAlgorithmsJoined']} node(s)."
        )
    rows = result["ranked"][:top]
    for position, row in enumerate(rows, 1):
        engine = ""
        if "engineFanIn" in row:
            engine = f"  engine fan-in/out {row['engineFanIn']}/{row['engineFanOut']}"
        atom = ""
        if "atomPageRank" in row:
            atom = f"  atom pageRank {round(row['atomPageRank'], 6)}"
        lines.append(
            f"{position:>3}. {_display(row)}  pageRank {row['pageRank']}"
            f"  in/out {row['inDegree']}/{row['outDegree']}{engine}{atom}"
        )
    total = len(result["ranked"])
    if total > top:
        lines.append(f"… {total - top} more ranked node(s) in the json output.")
    return lines


def _render_blast_radius(result: Dict) -> List[str]:
    lines = [
        f"node: {_display(result)}",
        (
            f"reach (including the node): {result['reachIncludingSelf']}"
            f" — {result['internalReachable']} internal,"
            f" {result['externalReachable']} external, max depth {result['maxDepth']}"
        ),
    ]
    if result["files"]:
        shown = ", ".join(result["files"][:5])
        more = f" (+{len(result['files']) - 5} more)" if len(result["files"]) > 5 else ""
        lines.append(f"files: {shown}{more}")
    if result["purls"]:
        shown = ", ".join(result["purls"][:3])
        more = f" (+{len(result['purls']) - 3} more)" if len(result["purls"]) > 3 else ""
        lines.append(f"packages: {shown}{more}")
    if result["externalTargets"]:
        shown = ", ".join(result["externalTargets"][:5])
        more = (
            f" (+{len(result['externalTargets']) - 5} more)"
            if len(result["externalTargets"]) > 5
            else ""
        )
        lines.append(f"external targets: {shown}{more}")
    return lines


def _render_entry_depth(result: Dict, top: int) -> List[str]:
    seeds = result.get("seeds") or {}
    lines = [
        (
            f"seeds: {seeds.get('sources', 0)} via {seeds.get('policy', 'none')}"
            f" ({seeds.get('source', 'none')}); depths:"
            f" {result.get('engineDepths', 0)} engine value(s),"
            f" {result.get('derivedDepths', 0)} derived"
        )
    ]
    rows = result["depths"][:top]
    for position, row in enumerate(rows, 1):
        lines.append(
            f"{position:>3}. depth {row['depth']} ({row['depthSource']})  {_display(row)}"
        )
    total = len(result["depths"])
    if total > top:
        lines.append(f"… {total - top} more node(s) in the json output.")
    return lines


def _render_dead_code(result: Dict) -> List[str]:
    lines = [f"source: {result['source']}"]
    if result["engine"] == "dosai":
        lines.append(f"engine DeadCode entries: {result['deadCodeCount']}")
    if result["engine"] == "golem":
        lines.append(
            "nodes unreachable from the engine's roots:"
            f" {result['unreachableFromRootsPerEngine']} of"
            f" {result['nodesWithVerdict']} with a verdict"
        )
    return lines


def _render_cycles(result: Dict, top: int) -> List[str]:
    lines = [f"source: {result['source']}"]
    lines.append(
        f"recursive cluster(s): {result.get('recursiveClusterCount')} of"
        f" {result.get('clusterCount')} component(s)"
    )
    clusters = result.get("clusters") or []
    for position, cluster in enumerate(clusters, 1):
        if position > top:
            lines.append(f"… {len(clusters) - top} more cluster(s) in the json output.")
            break
        members = cluster["members"]
        shown = ", ".join(members[:4])
        more = f" (+{len(members) - 4} more)" if len(members) > 4 else ""
        lines.append(f"{position:>3}. size {len(members)}: {shown}{more}")
    if not clusters:
        lines.append("no recursion cluster found.")
    return lines


def render_mermaid(document: Dict, graphs: Sequence[UnifiedCallGraph], top: int = 12) -> str:
    """Top-N subgraph around the ranked hotspots, hard-capped.

    Full call graphs are unreadable as mermaid; this keeps the top ``top``
    ranked nodes, adds their direct callees, and stops at
    ``MERMAID_NODE_CAP`` nodes — a cap node in the diagram says so when it
    binds. Metrics without a ranking (blast-radius, dead-code) say so
    instead of drawing something misleading.
    """
    from atom_tools.lib.visualizer import mm_escape, mm_label

    lines = ["flowchart LR"]
    lines.append("    classDef hot fill:#cf222e,stroke:#a40e26,color:#fff")
    lines.append("    classDef internal fill:#1a7f37,stroke:#116329,color:#fff")
    lines.append("    classDef external fill:#8b949e,stroke:#57606a,color:#fff")
    result = next((r for r in document["results"] if r.get("computed")), None)
    if result is None:
        return "\n".join(lines + ['    empty["no metric result to draw"]']) + "\n"
    rows = result.get("ranked") or result.get("depths") or []
    if not rows:
        return (
            "\n".join(
                lines
                + [
                    '    empty["'
                    + mm_escape(
                        f"{document['metric']}: nothing to draw for this input"
                        " — see the console rendering or use --export"
                    )
                    + '"]'
                ]
            )
            + "\n"
        )
    lines.append(
        f'    title["{mm_escape(document["metric"])} — top {min(top, len(rows))}'
        f' of {len(rows)} ({result["engine"]})"]:::external'
    )
    graph = next(
        (g for g in graphs if g.source_file == result["sourceFile"]),
        None,
    )
    shown: Dict[str, str] = {}
    counter = 0

    def node_id(row_id: str) -> Optional[str]:
        nonlocal counter
        if row_id not in shown:
            if len(shown) >= MERMAID_NODE_CAP:
                return None
            counter += 1
            shown[row_id] = f"n{counter}"
        return shown[row_id]

    for row in rows[:top]:
        node = node_id(row["id"])
        if node is None:
            break
        label = row.get("name") or row["id"]
        extra = f" · depth {row.get('depth')}" if document["metric"] == "entry-depth" else ""
        cls = "external" if row.get("external") else "internal"
        lines.append(f'    {node}("{mm_label(label, 30)}{extra}"):::{cls}')
    if graph is not None:
        for row in rows[:top]:
            src = shown.get(row["id"])
            if src is None:
                break
            for edge in graph.edges:
                if edge.caller != row["id"] or edge.callee not in graph.by_id:
                    continue
                callee = graph.by_id[edge.callee]
                nid = node_id(callee.name)
                if nid is None:
                    break
                lines.append(
                    f'    {nid}("{mm_label(callee.name, 30)}"):::'
                    + ("external" if callee.external else "internal")
                )
                arrow = f' -- "{mm_escape(edge.call_type)}" --> ' if edge.call_type else " --> "
                lines.append(f"    {src}{arrow}{nid}")
                break
    if len(shown) >= MERMAID_NODE_CAP:
        lines.append(
            f'    cap["diagram capped at {MERMAID_NODE_CAP} nodes — json output'
            ' carries everything"]:::external'
        )
    return "\n".join(lines) + "\n"


# -- GraphML / GEXF export (key-compatible with dosai's own exporters) --------

GRAPHML_NODE_KEYS = (
    ("label", "string"),
    ("kind", "string"),
    ("file", "string"),
    ("purl", "string"),
    ("external", "boolean"),
    ("reachableEntryPoints", "string"),
    ("minDepthFromEntryPoint", "int"),
    ("fanIn", "int"),
    ("fanOut", "int"),
    ("inRecursiveCycle", "boolean"),
    ("derivedEntryDepth", "int"),
)
GRAPHML_EDGE_KEYS = (
    ("callType", "string"),
    ("sourcePurl", "string"),
    ("targetPurl", "string"),
    ("location", "string"),
    ("callSiteCount", "int"),
    ("dispatchConfidence", "string"),
    ("confidence", "string"),
    ("candidateCount", "int"),
)


def _xml_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _sorted_nodes(graph: UnifiedCallGraph) -> List[CallNode]:
    return sorted(graph.nodes, key=lambda n: n.id)


def _sorted_edges(graph: UnifiedCallGraph) -> List[CallEdge]:
    return sorted(graph.edges, key=lambda e: (e.caller, e.callee, e.location, e.call_type))


def _node_data_pairs(node: CallNode) -> List[Tuple[str, str]]:
    pairs = [
        ("label", node.label or node.name),
        ("kind", node.kind),
        ("file", node.file),
        ("purl", node.purl),
        ("external", "true" if node.external else "false"),
    ]
    if node.reachable_entry_points is not None:
        pairs.append(("reachableEntryPoints", ",".join(node.reachable_entry_points)))
    if node.min_depth_from_entry is not None:
        # The engine's key is used only for the engine's value; anything we
        # derived goes under a distinct key so the two never blur.
        if node.depth_source == "engine":
            pairs.append(("minDepthFromEntryPoint", str(node.min_depth_from_entry)))
        else:
            pairs.append(("derivedEntryDepth", str(node.min_depth_from_entry)))
    if node.fan_in is not None:
        pairs.append(("fanIn", str(node.fan_in)))
    if node.fan_out is not None:
        pairs.append(("fanOut", str(node.fan_out)))
    if node.in_cycle is not None:
        pairs.append(("inRecursiveCycle", "true" if node.in_cycle else "false"))
    return [(k, v) for k, v in pairs if v not in ("", None)]


def _edge_data_pairs(edge: CallEdge) -> List[Tuple[str, str]]:
    pairs = [
        ("callType", edge.call_type),
        ("location", edge.location),
        ("confidence", edge.confidence),
        ("sourcePurl", edge.source_purl),
        ("targetPurl", edge.target_purl),
    ]
    if edge.dispatch_confidence is not None:
        pairs.append(("dispatchConfidence", str(edge.dispatch_confidence)))
    if edge.call_site_count is not None:
        pairs.append(("callSiteCount", str(edge.call_site_count)))
    if edge.candidate_count is not None:
        pairs.append(("candidateCount", str(edge.candidate_count)))
    return [(k, v) for k, v in pairs if v not in ("", None)]


def export_graphml(graphs: Sequence[UnifiedCallGraph]) -> str:
    """GraphML with dosai's own key vocabulary, so artefacts interoperate.

    Node and edge order match dosai's exporter (id-ordinal), edge ids are
    e1..eN, booleans are lowercase. Engine-computed values (fanIn,
    minDepthFromEntryPoint, ...) are written only when the engine supplied
    them; ours go under distinct keys (derivedEntryDepth, confidence).
    """
    lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    lines.append('<graphml xmlns="http://graphml.graphdrawing.org/xmlns">')
    for key, kind in GRAPHML_NODE_KEYS:
        lines.append(f'  <key id="{key}" for="node" attr.name="{key}" attr.type="{kind}" />')
    for key, kind in GRAPHML_EDGE_KEYS:
        lines.append(f'  <key id="{key}" for="edge" attr.name="{key}" attr.type="{kind}" />')
    for graph in graphs:
        lines.append(
            f'  <graph id="callgraph-{_xml_escape(graph.engine)}" edgedefault="directed">'
        )
        for node in _sorted_nodes(graph):
            lines.append(f'    <node id="{_xml_escape(node.id)}">')
            for key, value in _node_data_pairs(node):
                lines.append(f'      <data key="{key}">{_xml_escape(str(value))}</data>')
            lines.append("    </node>")
        for index, edge in enumerate(_sorted_edges(graph), 1):
            lines.append(
                f'    <edge id="e{index}" source="{_xml_escape(edge.caller)}"'
                f' target="{_xml_escape(edge.callee)}">'
            )
            for key, value in _edge_data_pairs(edge):
                lines.append(f'      <data key="{key}">{_xml_escape(str(value))}</data>')
            lines.append("    </edge>")
        lines.append("  </graph>")
    lines.append("</graphml>")
    return "\n".join(lines) + "\n"


def export_gexf(graphs: Sequence[UnifiedCallGraph]) -> str:
    """GEXF 1.3 with the same attribute vocabulary as the GraphML export."""
    lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    lines.append('<gexf xmlns="http://www.gexf.net/1.3" version="1.3">')
    lines.append('  <graph mode="static" defaultedgetype="directed">')
    lines.append('    <attributes class="node">')
    for key, kind in GRAPHML_NODE_KEYS:
        lines.append(f'      <attribute id="{key}" title="{key}" type="{kind}" />')
    lines.append("    </attributes>")
    lines.append('    <attributes class="edge">')
    for key, kind in GRAPHML_EDGE_KEYS:
        lines.append(f'      <attribute id="{key}" title="{key}" type="{kind}" />')
    lines.append("    </attributes>")
    for graph in graphs:
        lines.append("    <nodes>")
        for node in _sorted_nodes(graph):
            lines.append(
                f'      <node id="{_xml_escape(node.id)}"'
                f' label="{_xml_escape(node.label or node.name)}">'
            )
            lines.append("        <attvalues>")
            for key, value in _node_data_pairs(node):
                lines.append(
                    f'          <attvalue for="{key}" value="{_xml_escape(str(value))}" />'
                )
            lines.append("        </attvalues>")
            lines.append("      </node>")
        lines.append("    </nodes>")
        lines.append("    <edges>")
        for index, edge in enumerate(_sorted_edges(graph), 1):
            lines.append(
                f'      <edge id="e{index}" source="{_xml_escape(edge.caller)}"'
                f' target="{_xml_escape(edge.callee)}">'
            )
            lines.append("        <attvalues>")
            for key, value in _edge_data_pairs(edge):
                lines.append(
                    f'          <attvalue for="{key}" value="{_xml_escape(str(value))}" />'
                )
            lines.append("        </attvalues>")
            lines.append("      </edge>")
        lines.append("    </edges>")
    lines.append("  </graph>")
    lines.append("</gexf>")
    return "\n".join(lines) + "\n"

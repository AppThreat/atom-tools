"""The attack surface of a report: entry points, exposure tiers, and what each reaches.

``query-endpoints`` lists routes and ``visualize`` groups flows by file; neither
answers the question a reviewer actually asks — *which entry points are exposed,
and what does each one reach?* dosai answers it for .NET with its own
``AttackSurface[]`` array. This module produces the same view for every engine,
as a pure function over parsed inputs — no engine invocation, so it runs in
seconds in CI.

Three facts measured against the real fixtures shaped the design:

**Flow links come from the engine or through the call graph.** dosai's
``Slices`` carry no entry-point reference and its per-entry-point reach is
taken verbatim instead. golem's ``dataFlow.slices`` and ``apiEndpoints`` live
in separate id spaces, and rusi is the same — for those two the join goes
through the call graph: anchor the endpoint's handler in the call graph, take
the transitive callee closure, and attach every flow whose source function
sits inside that closure. kosi is the exception: its ``apiEndpoints[]``
records name the slices that entered through them (``sliceIds``, populated
when ``--endpoint-sources`` seeded the handler parameters), so those endpoints
carry the engine's own link directly and the call graph is the fallback.
dosai is never joined this way — its own ``AttackSurface[]`` already carries
the engine's per-entry-point weakness and sink-category data, which is
strictly better than anything we could traverse, so it is taken verbatim.

**Authentication state is only known to dosai.** Its ``AllowAnonymous`` flag is
an input to its analysis, not the verdict (24 of the 27 ``anonymous-http`` entry
points in the eShopOnWeb fixture have ``AllowAnonymous: false``), and nothing in
another engine's ``Kind`` splits anonymous from authenticated. Every non-dosai
endpoint lands in the ``unknown-auth`` tier — rendered last and marked as a gap,
because a fabricated ``anonymous`` classification would be worse than an honest
one.

**"Reaches nothing" and "reach not computed" are opposite findings** and get
opposite renderings. Each entry point carries a reach *state*: ``engine``
(dosai's own data), ``computed`` (traversal ran and the handler was found — an
empty result then genuinely means unreachable from that entry point),
``seed-not-found`` (the call graph exists but the handler could not be anchored
in it), and ``not-computed`` (no call graph to traverse). A call graph that is
itself a subgraph of the engine's full run is reported alongside, the same way
``drift`` reports a truncated run.
"""

import logging
import os
import re
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from atom_tools.lib import taxonomy
from atom_tools.lib.drift import normalize_path
from atom_tools.lib.unified import UnifiedFlow, UnifiedReport

logger = logging.getLogger(__name__)

SURFACE_VERSION = 1

# dosai's exposure ordering, most exposed first. ``unknown-auth`` is appended
# rather than inserted: no engine that emits it knows anything about exposure,
# so it must not be read as outranking (or sitting under) any known tier.
TIERS = (
    "anonymous-http",
    "anonymous-rpc",
    "anonymous",
    "mcp",
    "queue",
    "cli",
    "authenticated-http",
    "authenticated-rpc",
    "internal",
)
UNKNOWN_AUTH = "unknown-auth"
TIER_ORDER = TIERS + (UNKNOWN_AUTH,)

# Reach states, in decreasing order of confidence.
REACH_ENGINE = "engine"  # the engine's own per-entry-point analysis (dosai)
REACH_COMPUTED = "computed"  # traversal ran with resolved seeds; empty means empty
REACH_SEED_NOT_FOUND = "seed-not-found"  # call graph present, handler not in it
REACH_NOT_COMPUTED = "not-computed"  # nothing to traverse

KIND_FAMILIES = (
    # (marker, tier): kinds that name a tier family on their own. Everything
    # else — every http/rpc flavour — stays unknown-auth, because the auth half
    # of the tier cannot be derived from a kind.
    ("mcp", "mcp"),
    ("queue", "queue"),
    ("consumer", "queue"),
    ("cli", "cli"),
)

# atom nodes tagged with these are network-facing entry points (chen's
# framework-route marks an annotated route; service-ingress a network listener).
ATOM_ROUTE_TAGS = ("framework-route", "service-ingress")


@dataclass
class SurfaceInput:
    """One parsed input: its unified report plus the original document.

    ``report`` is None for atom usages slices, which no adapter parses; their
    engine is recorded directly.
    """

    report: Optional[UnifiedReport]
    raw: Any
    path: str
    engine: str = ""

    def __post_init__(self):
        if not self.engine:
            object.__setattr__(self, "engine", self.report.engine if self.report else "atom")


# A path whose first token is an HTTP method already states its method.
_METHOD_IN_PATH = re.compile(
    r"^/?(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS|CONNECT|TRACE)\s+\S"
)


@dataclass
class EntryPoint:
    """One entry point with its exposure tier and whatever reach is known."""

    engine: str
    id: str
    tier: str
    tier_source: str  # "engine" (dosai's own) | "kind"
    kind: str = ""
    method: Optional[str] = None
    path: Optional[str] = None
    file: str = ""
    line: Optional[int] = None
    framework: str = ""
    handler: Optional[str] = None
    package: str = ""
    weaknesses: int = 0
    high_severity_weaknesses: int = 0
    chains: int = 0
    cwes: List[str] = field(default_factory=list)
    weakness_kinds: List[str] = field(default_factory=list)
    sink_categories: List[str] = field(default_factory=list)
    allow_anonymous: Optional[bool] = None  # dosai only; None = unknown
    reach_state: str = REACH_NOT_COMPUTED
    reach_sinks: List[str] = field(default_factory=list)
    reach_purls: List[str] = field(default_factory=list)
    reach_functions: List[str] = field(default_factory=list)
    reach_flows: int = 0
    reach_flow_ids: List[str] = field(default_factory=list)
    seeds: List[str] = field(default_factory=list)
    note: str = ""
    source_file: str = ""
    raw: Dict = field(default_factory=dict)  # the engine's endpoint record

    @property
    def label(self) -> str:
        if self.path:
            # "ANY" is our word, not the engine's, and it asserts something:
            # that the route answers every method. golem records Go 1.22
            # ServeMux patterns ("GET /static/") whole as the path and leaves
            # the method empty, so asserting ANY over a path that names GET
            # contradicts the path beside it. Print the path alone there.
            if self.method:
                return f"{self.method} {self.path}"
            if _METHOD_IN_PATH.match(self.path):
                return self.path
            return f"ANY {self.path}"
        # golem records Go's literal nil as the handler string of listeners on
        # the DefaultServeMux; "nil" and a synthetic id are locations, not
        # names, and the kind says more than either.
        if self.handler and self.handler != "nil":
            return self.handler
        return self.kind or self.id

    @property
    def reaches(self) -> bool:
        return bool(self.reach_sinks or self.reach_flows or self.reach_functions)

    def rank_key(self) -> Tuple:
        """dosai's ranking: high-severity weaknesses, then weaknesses, then
        chains, all descending; ties broken deterministically by label."""
        return (
            -self.high_severity_weaknesses,
            -self.weaknesses,
            -self.chains,
            self.label,
            self.file,
            self.id,
        )

    def to_dict(self) -> Dict:
        """dosai's per-entry-point AttackSurface shape plus atom-tools additions.

        The dosai keys (EntryPointId, Exposure, WeaknessCount, ...) keep their
        names and semantics so downstream tooling can consume both engines'
        arrays interchangeably; ``AllowAnonymous: null`` says the producing
        engine could not know, where dosai says true/false.
        """
        return {
            "EntryPointId": self.id,
            "Exposure": self.tier,
            "Kind": self.kind or None,
            "HttpMethod": self.method,
            "Route": self.path,
            "FileName": os.path.basename(self.file) if self.file else None,
            "LineNumber": self.line,
            "AllowAnonymous": self.allow_anonymous,
            "ExploitChainCount": self.chains,
            "WeaknessCount": self.weaknesses,
            "HighSeverityWeaknessCount": self.high_severity_weaknesses,
            "WeaknessKinds": list(self.weakness_kinds),
            "Cwes": list(self.cwes),
            "SinkCategories": list(self.sink_categories),
            "Engine": self.engine,
            "Handler": self.handler,
            "Package": self.package or None,
            "Framework": self.framework or None,
            "File": self.file or None,
            "Reach": {
                "state": self.reach_state,
                "flows": self.reach_flows,
                "sinkCategories": list(self.reach_sinks),
                "purls": list(self.reach_purls),
                "functions": list(self.reach_functions),
                "seeds": list(self.seeds),
                # The flow ids behind the count, so narrative consumers (explain)
                # can name the entry point a flow hangs off without a second join.
                **({"flowIds": list(self.reach_flow_ids)} if self.reach_flow_ids else {}),
                **({"note": self.note} if self.note else {}),
            },
        }


def is_usages_slice(raw: Any) -> bool:
    """True for atom usages slices (the OpenAPI converter's input shape)."""
    return isinstance(raw, dict) and isinstance(raw.get("objectSlices"), list)


def tier_for_kind(kind: str) -> Tuple[str, str]:
    """Map an engine's endpoint kind onto a tier, honestly.

    Only the families whose tier does not depend on authentication (cli, queue,
    mcp) resolve beyond ``unknown-auth``: an http-route kind says nothing about
    whether the route is anonymous, and guessing is the one failure this command
    must never dress up as data.
    """
    lowered = (kind or "").lower()
    for marker, tier in KIND_FAMILIES:
        if marker in lowered:
            return tier, "kind"
    return UNKNOWN_AUTH, "kind"


# -- dosai: take the engine's own attack surface -------------------------------


def _dosai_entry_points(inputs: List[SurfaceInput]) -> List[EntryPoint]:
    """dosai entry points, tiered and enriched from the engine's AttackSurface.

    ``AllowAnonymous`` is carried as data but never used to derive the tier: in
    the eShopOnWeb fixture it disagrees with the engine's own verdict on 24 of
    27 anonymous entry points, which is what "the engine analysed something we
    did not" looks like in practice.
    """
    by_id: Dict[str, EntryPoint] = {}
    surface: Dict[str, Dict] = {}
    for inp in inputs:
        for tier_el in (inp.raw.get("AttackSurface") or []) if isinstance(inp.raw, dict) else []:
            for ep in tier_el.get("EntryPoints") or []:
                surface[ep.get("EntryPointId")] = {
                    "exposure": tier_el.get("Exposure"),
                    "weaknesses": ep.get("WeaknessCount") or 0,
                    "high": ep.get("HighSeverityWeaknessCount") or 0,
                    "chains": ep.get("ExploitChainCount") or 0,
                    "cwes": ep.get("Cwes") or [],
                    "kinds": ep.get("WeaknessKinds") or [],
                    "sinks": ep.get("SinkCategories") or [],
                }
        for ep in (inp.raw.get("EntryPoints") or []) if isinstance(inp.raw, dict) else []:
            if ep.get("Id") in by_id:
                continue
            known = surface.get(ep.get("Id"))
            tier, tier_source = (
                (known["exposure"], "engine") if known else tier_for_kind(ep.get("Kind"))
            )
            by_id[ep["Id"]] = EntryPoint(
                engine="dosai",
                id=ep.get("Id"),
                tier=tier,
                tier_source=tier_source,
                kind=ep.get("Kind") or "",
                method=ep.get("HttpMethod"),
                path=ep.get("Route") or ep.get("Path"),
                file=ep.get("Path") or ep.get("FileName") or "",
                line=ep.get("LineNumber"),
                handler=".".join(
                    p for p in (ep.get("Namespace"), ep.get("ClassName"), ep.get("MethodName")) if p
                )
                or ep.get("MethodId"),
                package=ep.get("Namespace") or "",
                allow_anonymous=ep.get("AllowAnonymous"),
                reach_state=REACH_ENGINE,
                reach_sinks=list(known["sinks"]) if known else [],
                sink_categories=list(known["sinks"]) if known else [],
                weaknesses=known["weaknesses"] if known else 0,
                high_severity_weaknesses=known["high"] if known else 0,
                chains=known["chains"] if known else 0,
                cwes=list(known["cwes"]) if known else [],
                weakness_kinds=list(known["kinds"]) if known else [],
                source_file=inp.path,
            )
    # Records not present in any top-level EntryPoints array (the engine
    # truncated that array but not AttackSurface) still belong to the surface.
    for ep_id, known in surface.items():
        if ep_id not in by_id:
            by_id[ep_id] = EntryPoint(
                engine="dosai",
                id=ep_id,
                tier=known["exposure"],
                tier_source="engine",
                reach_state=REACH_ENGINE,
                reach_sinks=list(known["sinks"]),
                weaknesses=known["weaknesses"],
                high_severity_weaknesses=known["high"],
                chains=known["chains"],
                cwes=list(known["cwes"]),
                weakness_kinds=list(known["kinds"]),
            )
    return list(by_id.values())


# -- the call-graph join (golem, rusi) -----------------------------------------


class _CallGraph:
    """A minimal forward graph with the indexes the endpoint anchor needs."""

    def __init__(self, engine: str, nodes: List[Dict], edges: List[Dict]):
        self.engine = engine
        self.by_id = {}
        # Every name spelling a node carries, keyed bare and paired with its
        # package: golem handlers are bare function names scoped by packagePath,
        # rusi handlers are fully qualified (``pkg::path::to::fn``), kosi
        # handlers are the JVM canonical name (``pkg.Class.method``, lambda
        # spellings included) scoped by modulePath.
        self.by_name_pkg: Dict[Tuple[str, Optional[str]], List[str]] = defaultdict(list)
        self.by_name: Dict[str, List[str]] = defaultdict(list)
        self.by_file: Dict[str, List[Tuple[Optional[int], str]]] = defaultdict(list)
        for node in nodes:
            node_id = node.get("id")
            self.by_id[node_id] = node
            names = {
                n
                for n in (
                    node.get("name"),
                    node.get("qualified_name"),
                    node.get("canonical_name"),
                    node.get("canonicalName"),
                    node.get("qualifiedName"),
                )
                if n
            }
            package = node.get("packagePath") or node.get("package_path") or node.get("modulePath")
            for name in names:
                self.by_name[name].append(node_id)
                self.by_name_pkg[(name, package)].append(node_id)
            pos = node.get("position") or {}
            filename = pos.get("filename") or node.get("file_path") or node.get("filename")
            if filename:
                self.by_file[filename].append((pos.get("line"), node_id))
        self.adj: Dict[str, List[str]] = defaultdict(list)
        for edge in edges:
            source = edge.get("sourceId") or edge.get("source_id")
            target = edge.get("targetId") or edge.get("target_id")
            if source and target:
                self.adj[source].append(target)

    def anchor(self, ep: Dict) -> Tuple[List[str], str]:
        """Locate an endpoint's handler in the graph; empty means not found.

        The chain is deliberately strict — id, then name+package, then the same
        spelling alone (only when unambiguous), then the file range — because a
        wrong anchor is worse than an honest seed-not-found: it would attach
        someone else's reach to this route. A bare handler name is never
        matched when several packages define the same name.

        Returns (seeds, how) with ``how`` empty when nothing anchored. rusi's
        own fixtures need the third step: five of its fourteen endpoints carry
        a ``package_path`` that disagrees with the call graph's node for the
        same qualified handler.
        """
        handler = ep.get("handler")
        if handler:
            if handler in self.by_id:
                return [handler], "id"
            by_pkg = self.by_name_pkg.get((handler, ep.get("package")))
            if by_pkg:
                return list(by_pkg), "name+package"
            same_spelling = self.by_name.get(handler, [])
            if len(same_spelling) == 1:
                return list(same_spelling), "name"
        seeds = self._anchor_by_range(ep)
        return seeds, "range" if seeds else ""

    def reaches_function(self, closure_ids: set, function: str) -> bool:
        """Whether ``function`` is a node inside the closure.

        golem's call-graph node ids *are* the function symbols its slices
        reference; rusi's ids are opaque hex and the qualified function name
        must go through the name index, and kosi's are ``node-*`` integers —
        its slices name functions, so the same name-index route applies.
        """
        if function in closure_ids:
            return True
        return any(node_id in closure_ids for node_id in self.by_name.get(function, ()))

    def _anchor_by_range(self, ep: Dict) -> List[str]:
        """Anchor by the endpoint's file position when its name is unusable.

        gin registers closures for most routes — golem reports their handler as
        the literal string "func literal" — so the name matches nothing. The
        endpoint's range is the closure body, and call-graph nodes carry
        positions, so a node whose position falls inside the range *is* the
        handler. Without a line span there is nothing to anchor to: a bare file
        name alone would pick up whichever function the engine listed first.
        kosi publishes a single position per endpoint rather than a range; that
        one line is the anchor, and only for kosi — widening this to every
        engine's position field would change how rusi endpoints anchor, and
        their reach verdicts are pinned against the committed fixtures.
        """
        raw = ep.get("raw") or {}
        rng = raw.get("range") or {}
        start, end = rng.get("start") or {}, rng.get("end") or {}
        filename = start.get("filename") or ep.get("file")
        first = start.get("line")
        last = end.get("line")
        if (not filename or first is None) and self.engine == "kosi":
            position = raw.get("position") or {}
            filename = position.get("filename") or ep.get("file")
            first = position.get("line")
            last = first
        if not filename or first is None:
            return []
        if last is None:
            last = first
        return [
            node_id
            for line, node_id in self.by_file.get(filename, [])
            if line is None or first <= line <= last
        ]

    def closure(self, seeds: List[str]) -> List[str]:
        """The transitive callees of ``seeds``, seeds included."""
        seen = set(seeds)
        queue = deque(seeds)
        while queue:
            current = queue.popleft()
            for nxt in self.adj.get(current, ()):
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append(nxt)
        return list(seen)


def _golem_call_graph(raw: Dict) -> Optional[Tuple[_CallGraph, Dict]]:
    graph = (raw.get("callGraph") or {}) if isinstance(raw, dict) else {}
    if not graph.get("nodes") and not graph.get("edges"):
        return None
    stats = graph.get("stats") or {}
    meta = {
        "present": True,
        "nodes": len(graph.get("nodes") or []),
        "edges": len(graph.get("edges") or []),
        "fullNodes": stats.get("nodeCount"),
        "fullEdges": stats.get("edgeCount"),
    }
    meta["trimmed"] = bool(
        (meta["fullNodes"] and meta["fullNodes"] > meta["nodes"])
        or (meta["fullEdges"] and meta["fullEdges"] > meta["edges"])
    )
    return _CallGraph("golem", graph.get("nodes") or [], graph.get("edges") or []), meta


def _rusi_call_graph(raw: Dict) -> Optional[Tuple[_CallGraph, Dict]]:
    graph = (raw.get("call_graph") or {}) if isinstance(raw, dict) else {}
    if not graph.get("nodes") and not graph.get("edges"):
        return None
    return (
        _CallGraph("rusi", graph.get("nodes") or [], graph.get("edges") or []),
        {"present": True, "nodes": len(graph.get("nodes") or []), "edges": len(graph.get("edges") or [])},
    )


def _kosi_call_graph(raw: Dict) -> Optional[Tuple[_CallGraph, Dict]]:
    """kosi's ``callGraph`` section, or None when the run emitted an explicit
    null (its callgraph modes off). The section describes the whole graph the
    engine built — kosi's stats count the graph itself, so unlike golem there
    is no full-run counter to compare against and no trim question."""
    graph = (raw.get("callGraph") or {}) if isinstance(raw, dict) else {}
    if not graph.get("nodes") and not graph.get("edges"):
        return None
    return (
        _CallGraph("kosi", graph.get("nodes") or [], graph.get("edges") or []),
        {"present": True, "nodes": len(graph.get("nodes") or []), "edges": len(graph.get("edges") or [])},
    )


def _apply_engine_slice_links(entry_points: List[EntryPoint], reports: List[UnifiedReport]) -> int:
    """Attach the reach kosi states itself via ``apiEndpoints[].sliceIds``.

    When ``--endpoint-sources`` seeded the handler parameters, an
    endpoint-rooted slice names the endpoint it entered through — a direct
    engine statement no traversal here could reproduce, and the one flow link
    in the ecosystem that does not go through a call graph. Where the link
    resolves, it replaces the closure-derived reach: the engine's own join is
    the authority, the traversal the fallback for endpoints it says nothing
    about. Returns how many endpoints carry an engine link.
    """
    flows_by_id = {f.id: f for r in reports for f in r.flows}
    linked = 0
    for ep in entry_points:
        raw = ep.raw.get("raw") or ep.raw
        slice_ids = raw.get("sliceIds") if isinstance(raw, dict) else None
        if not slice_ids:
            continue
        matched = [flows_by_id[s] for s in slice_ids if s in flows_by_id]
        if not matched:
            continue
        ep.reach_state = REACH_ENGINE
        ep.seeds = []
        ep.reach_flows = len(matched)
        ep.reach_flow_ids = sorted(f.id for f in matched)
        ep.reach_sinks = sorted({f.sink_category for f in matched if f.sink_category})
        ep.reach_purls = sorted({p for f in matched for p in f.purls})
        ep.reach_functions = sorted({_source_function(f) for f in matched if _source_function(f)})
        ep.note = (
            "reach from the engine's own slice link (apiEndpoints[].sliceIds),"
            " not a call-graph traversal"
        )
        linked += 1
    return linked


def _source_function(flow: UnifiedFlow) -> str:
    """The function a flow's source sits in, in the engine's own spelling."""
    raw = flow.raw or {}
    if flow.engine in ("golem", "kosi"):
        return raw.get("sourceFunction") or (flow.source.function if flow.source else "") or ""
    if flow.engine == "rusi":
        return raw.get("source_function") or ""
    return (flow.source.function if flow.source else "") or ""


def _join_call_graph(
    entry_points: List[EntryPoint],
    reports: List[UnifiedReport],
    graphs: List[_CallGraph],
) -> Tuple[int, int]:
    """Attach call-graph reach to every entry point; returns (flows, attached).

    A flow joins an entry point when its source function is inside that entry
    point's callee closure. Each graph anchors the endpoint itself, so seeds
    from one engine's id space are never handed to another's. Endpoints whose
    handler never resolves in any graph keep ``seed-not-found`` — an honest
    gap, never folded into "reaches nothing".
    """
    by_function: Dict[str, List[UnifiedFlow]] = defaultdict(list)
    flows = 0
    for report in reports:
        for flow in report.flows:
            flows += 1
            function = _source_function(flow)
            if function:
                by_function[function].append(flow)
    attached = 0
    for ep in entry_points:
        # The anchor reads the engine's own endpoint record (the adapter's dict
        # nests it under "raw") so golem's range and rusi's position are visible.
        endpoint = {
            "handler": ep.handler,
            "package": ep.package,
            "file": ep.file,
            "raw": ep.raw.get("raw") or ep.raw,
        }
        matched: List[UnifiedFlow] = []
        seeds: List[str] = []
        anchored_how = ""
        for graph in graphs:
            anchored, how = graph.anchor(endpoint)
            if not anchored:
                continue
            seeds.extend(anchored)
            anchored_how = anchored_how or how
            in_closure = set(graph.closure(anchored))
            matched.extend(
                flow
                for function, group in by_function.items()
                if graph.reaches_function(in_closure, function)
                for flow in group
                if flow.engine == graph.engine
            )
        if not seeds:
            ep.reach_state = REACH_SEED_NOT_FOUND
            continue
        ep.seeds = seeds
        ep.reach_state = REACH_COMPUTED
        if anchored_how == "name":
            ep.note = (
                "anchored by handler name alone: the endpoint's package did not"
                " match the call graph node's package, so this reach may belong"
                " to a same-named function in another package"
            )
        matched = list({flow.id: flow for flow in matched}.values())
        ep.reach_flows = len(matched)
        ep.reach_flow_ids = sorted(f.id for f in matched)
        ep.reach_sinks = sorted({f.sink_category for f in matched if f.sink_category})
        ep.reach_purls = sorted({p for f in matched for p in f.purls})
        ep.reach_functions = sorted({_source_function(f) for f in matched if _source_function(f)})
        attached += len(matched)
    return flows, attached


# -- golem and rusi ------------------------------------------------------------


def _engine_entry_points(inputs: List[SurfaceInput], engine: str) -> List[EntryPoint]:
    entry_points: List[EntryPoint] = []
    seen = set()
    for inp in inputs:
        for endpoint in inp.report.endpoints:
            key = (
                (endpoint.get("method") or "").upper(),
                endpoint.get("path") or "",
                endpoint.get("kind") or "",
                normalize_path(endpoint.get("file") or "", ""),
            )
            if key in seen:
                continue
            seen.add(key)
            kind = endpoint.get("kind") or ""
            tier, tier_source = tier_for_kind(kind)
            entry_points.append(
                EntryPoint(
                    engine=engine,
                    id=endpoint.get("id") or f"{engine}-{len(entry_points) + 1}",
                    tier=tier,
                    tier_source=tier_source,
                    kind=kind,
                    method=(endpoint.get("method") or "").upper() or None,
                    path=endpoint.get("path"),
                    file=endpoint.get("file") or "",
                    line=endpoint.get("line"),
                    framework=endpoint.get("framework") or "",
                    handler=endpoint.get("handler"),
                    package=endpoint.get("package") or "",
                    reach_state=REACH_NOT_COMPUTED,
                    source_file=inp.path,
                    raw=endpoint,
                )
            )
    return entry_points


# -- atom: routes from reachables, endpoints from usages ------------------------


def _atom_entry_points(inputs: List[SurfaceInput]) -> Tuple[List[EntryPoint], int]:
    """atom entry points from both of its shapes.

    Reachables documents tag the node a route terminates at (``framework-route``
    in petclinic's case) but never spell out the route path — the tags are
    markers, not values — so the entry point is the (file, handler method) the
    marker sits in. Usages slices go through the same OpenAPI conversion
    ``query-endpoints`` uses, which yields real method+path endpoints.
    Neither shape links flows to entry points by id, so reach is joined by
    source location where the marker is in the same document, and otherwise
    reported as not computed.
    """
    entry_points: List[EntryPoint] = []
    by_location: Dict[Tuple[str, str], EntryPoint] = {}
    usages_files = 0
    for inp in inputs:
        raw = inp.raw
        if is_usages_slice(raw):
            usages_files += 1
            entry_points.extend(_atom_usages_entry_points(inp))
            continue
        # Reachables: route-tagged sink nodes are the entry points.
        routes: Dict[Tuple[str, str], EntryPoint] = {}
        for flow in inp.report.flows:
            for node in flow.nodes:
                if not any(tag in node.tags for tag in ATOM_ROUTE_TAGS):
                    continue
                location = (node.file or "", node.function or node.name or "")
                if location not in routes:
                    routes[location] = EntryPoint(
                        engine="atom",
                        id=f"atom:{location[0]}#{location[1]}",
                        tier=UNKNOWN_AUTH,
                        tier_source="kind",
                        kind="http-route",
                        file=node.file or "",
                        handler=location[1] or None,
                        reach_state=REACH_NOT_COMPUTED,
                        source_file=inp.path,
                    )
                entry = routes[location]
                entry.reach_state = REACH_COMPUTED
                entry.reach_flows += 1
                entry.reach_flow_ids.append(flow.id)
                if flow.sink_category and flow.sink_category not in entry.reach_sinks:
                    entry.reach_sinks.append(flow.sink_category)
                for purl in flow.purls:
                    if purl not in entry.reach_purls:
                        entry.reach_purls.append(purl)
        for entry in routes.values():
            entry.note = (
                "atom emits no call graph; reach is the count of flows in this"
                " document whose source sits in the route's (file, method)."
            )
            entry.reach_flow_ids.sort()
        for location, entry in routes.items():
            if location not in by_location:
                by_location[location] = entry
                entry_points.append(entry)
    return entry_points, usages_files


def _atom_usages_entry_points(inp: SurfaceInput) -> List[EntryPoint]:
    """Entry points from the OpenAPI conversion of a usages slice."""
    from atom_tools.lib.converter import OpenAPI

    # The origin type only picks the converter's language heuristics; java is
    # the default the CLI itself uses and the only fixture shape committed.
    converter = OpenAPI("openapi3.1.0", "java", inp.path)
    result = converter.endpoints_to_openapi("")
    entry_points = []
    for path, item in sorted((result.get("paths") or {}).items()):
        operations = [
            op
            for op in (item or {}).keys()
            if isinstance(op, str)
            and op.lower() in ("get", "post", "put", "delete", "patch", "head", "options")
        ]
        if not operations:
            continue
        usages = (item or {}).get("x-atom-usages") or {}
        call_files = sorted((usages.get("call") or {}).keys())
        for operation in sorted(operations):
            entry_points.append(
                EntryPoint(
                    engine="atom",
                    id=f"atom:{operation.upper()} {path}",
                    tier=UNKNOWN_AUTH,
                    tier_source="kind",
                    kind="http-route",
                    method=operation.upper(),
                    path=path,
                    file=call_files[0] if call_files else "",
                    framework="usages",
                    handler=", ".join(call_files) or None,
                    reach_state=REACH_NOT_COMPUTED,
                    note=(
                        "converted from a usages slice; no reachables document was"
                        " supplied for this input, so reach is not computed"
                    ),
                    source_file=inp.path,
                )
            )
    return entry_points


# -- the document ---------------------------------------------------------------


def _reaches_high_risk_sink(ep: EntryPoint) -> bool:
    """
    Whether an entry point reaches something worth the headline.

    Two independent signals, because the engines supply different ones. dosai
    states a high-severity weakness count directly. Everything else states sink
    categories in its own vocabulary, so those go through the shared taxonomy
    mapping — the same one ``unified.py`` uses — and are checked against
    ``HIGH_RISK_SINKS``. Reading only the engine's weakness count, as the first
    version did, made the headline claim "reaches a high-risk sink" while
    measuring something else entirely, and reported 0 for every engine that
    does not emit weaknesses at all.
    """
    if ep.high_severity_weaknesses > 0:
        return True
    categories = ep.reach_sinks if ep.reach_state in (REACH_COMPUTED, REACH_ENGINE) else []
    for category in list(categories) + list(ep.sink_categories):
        if category in taxonomy.HIGH_RISK_SINKS:
            return True
        mapped = taxonomy.category_to_tag(category)
        if mapped and mapped in taxonomy.HIGH_RISK_SINKS:
            return True
    return False


def _group_and_rank(entry_points: List[EntryPoint]) -> List[Dict]:
    tiers: Dict[str, List[EntryPoint]] = defaultdict(list)
    for ep in entry_points:
        tiers[ep.tier].append(ep)
    out = []
    for tier in TIER_ORDER:
        members = tiers.get(tier) or []
        if not members:
            continue
        members.sort(key=EntryPoint.rank_key)
        out.append(
            {
                "Exposure": tier,
                "EntryPointCount": len(members),
                "ExploitChainCount": sum(e.chains for e in members),
                "WeaknessCount": sum(e.weaknesses for e in members),
                "HighSeverityWeaknessCount": sum(e.high_severity_weaknesses for e in members),
                "EntryPointsTruncated": False,
                "EntryPoints": [e.to_dict() for e in members],
                "Engine": sorted({e.engine for e in members}),
                "TierSource": sorted({e.tier_source for e in members}),
                "EntryPointsWithReach": sum(1 for e in members if e.reaches),
            }
        )
    return out


def compute_attack_surface(inputs: List[SurfaceInput], min_exposure: str = "") -> Dict:
    """Compute the attack-surface document for one or more parsed inputs.

    Engines are mixed freely; each entry point is tiered by its own engine's
    knowledge (dosai's verdict, or an honest unknown-auth everywhere else) and
    its reach computed only from evidence that input actually carries.
    """
    diagnostics: List[str] = []
    coverage: Dict[str, Dict] = {}
    entry_points: List[EntryPoint] = []

    dosai_inputs = [i for i in inputs if i.engine == "dosai"]
    golem_inputs = [i for i in inputs if i.engine == "golem"]
    rusi_inputs = [i for i in inputs if i.engine == "rusi"]
    kosi_inputs = [i for i in inputs if i.engine == "kosi"]
    atom_inputs = [i for i in inputs if i.engine == "atom"]

    if dosai_inputs:
        entry_points.extend(_dosai_entry_points(dosai_inputs))
        missing = sum(1 for e in entry_points if e.tier_source != "engine")
        if missing:
            diagnostics.append(
                f"{missing} dosai entry point(s) are absent from the report's"
                " AttackSurface array and fell back to kind-derived tiers."
            )
        coverage["dosai"] = {
            "engine": "dosai",
            "reachSource": "the engine's own AttackSurface array",
            "endpoints": len([e for e in entry_points if e.engine == "dosai"]),
        }
    for engine, engine_inputs, loader in (
        ("golem", golem_inputs, _golem_call_graph),
        ("rusi", rusi_inputs, _rusi_call_graph),
        ("kosi", kosi_inputs, _kosi_call_graph),
    ):
        if not engine_inputs:
            continue
        eps = _engine_entry_points(engine_inputs, engine)
        entry_points.extend(eps)
        graphs, metas = [], []
        for inp in engine_inputs:
            loaded = loader(inp.raw)
            if loaded:
                graph, meta = loaded
                graphs.append(graph)
                meta["engine"] = engine
                meta["file"] = inp.path
                metas.append(meta)
        if graphs:
            flows, attached = _join_call_graph(eps, [i.report for i in engine_inputs], graphs)
            # kosi may state the join itself: endpoints whose records name the
            # slices that entered through them take the engine's verdict over
            # the closure this loop just derived.
            engine_linked = 0
            if engine == "kosi":
                engine_linked = _apply_engine_slice_links(eps, [i.report for i in engine_inputs])
                if engine_linked:
                    diagnostics.append(
                        f"{engine_linked} kosi endpoint(s) carry the engine's own"
                        " slice link (apiEndpoints[].sliceIds); their reach is"
                        " the engine's, not the call-graph traversal's."
                    )
            coverage[engine] = {
                "engine": engine,
                "callGraphs": metas,
                "endpoints": len(eps),
                "endpointsAnchored": sum(1 for e in eps if e.reach_state == REACH_COMPUTED),
                **(
                    {"endpointsEngineLinked": engine_linked}
                    if engine_linked
                    else {}
                ),
                "flows": flows,
                "flowsAttached": attached,
            }
            for meta in metas:
                if meta.get("trimmed"):
                    diagnostics.append(
                        f"{engine} call graph in {os.path.basename(meta['file'])} is a"
                        f" subgraph of the engine's run ({meta['edges']} of"
                        f" {meta['fullEdges']} edges present); reach is computed"
                        " within that subgraph only."
                    )
            unanchored = sum(1 for e in eps if e.reach_state == REACH_SEED_NOT_FOUND)
            if unanchored:
                diagnostics.append(
                    f"{unanchored} {engine} endpoint(s) could not be anchored in the"
                    " call graph (closure handler, name and file range all missed);"
                    " their reach is reported as seed-not-found, not as empty."
                )
        else:
            coverage[engine] = {
                "engine": engine,
                "callGraphs": [],
                "endpoints": len(eps),
                "endpointsAnchored": 0,
            }
            diagnostics.append(
                f"no call graph in the supplied {engine} report(s); reach is not"
                " computed for its entry points."
            )
    if atom_inputs:
        atom_eps, usages_files = _atom_entry_points(atom_inputs)
        entry_points.extend(atom_eps)
        coverage["atom"] = {
            "engine": "atom",
            "endpoints": len(atom_eps),
            "usagesFiles": usages_files,
            "note": (
                "atom emits no call graph; reach is joined by flow source location"
                " for reachables inputs and is not computed for usages-only inputs."
            ),
        }

    if min_exposure:
        entry_points, filtered_out = _apply_min_exposure(entry_points, min_exposure)
        if filtered_out:
            diagnostics.append(
                f"--min-exposure {min_exposure} filtered out {filtered_out} entry"
                " point(s) in later or unknown tiers."
            )

    tiers = _group_and_rank(entry_points)

    reach_computed = any(e.reach_state in (REACH_ENGINE, REACH_COMPUTED) for e in entry_points)
    anonymous = [
        e for e in entry_points if e.tier.startswith("anonymous") and e.tier in TIERS
    ]
    anonymous_high = sum(1 for e in anonymous if _reaches_high_risk_sink(e))
    headline = None
    if anonymous and reach_computed:
        # The denominator is the anonymous entry points, not every entry point.
        # "0 of 60 entry points are anonymous and reach a high-risk sink" reads
        # as "none are anonymous" when 27 of them are, which buries the number
        # the reader came for.
        percent = 100 * anonymous_high // len(anonymous)
        headline = (
            f"{anonymous_high} of {len(anonymous)} anonymous entry points ({percent}%)"
            f" reach at least one high-risk sink ({len(anonymous)} of"
            f" {len(entry_points)} entry points are anonymous)."
        )
    return {
        "attackSurfaceVersion": SURFACE_VERSION,
        "engine": "+".join(sorted({i.engine for i in inputs})),
        "sources": [i.path for i in inputs],
        "tierOrder": list(TIER_ORDER),
        "tiers": tiers,
        "summary": {
            "entryPoints": len(entry_points),
            "byTier": {t["Exposure"]: t["EntryPointCount"] for t in tiers},
            "byEngine": dict(
                sorted(
                    {
                        engine: sum(1 for e in entry_points if e.engine == engine)
                        for engine in {e.engine for e in entry_points}
                    }.items()
                )
            ),
            "reachComputed": reach_computed,
            "entryPointsWithReach": sum(1 for e in entry_points if e.reaches),
            "anonymousReach": {
                "computed": bool(reach_computed and anonymous),
                "anonymousEntryPoints": len(anonymous),
                "reachingHighSeveritySink": anonymous_high,
            },
            **({"headline": headline} if headline else {}),
        },
        "coverage": coverage,
        "diagnostics": diagnostics,
    }


def _apply_min_exposure(
    entry_points: List[EntryPoint], min_exposure: str
) -> Tuple[List[EntryPoint], int]:
    """Keep entry points in tiers at least as exposed as ``min_exposure``.

    ``unknown-auth`` never matches a minimum-exposure filter: its whole point is
    that exposure is unknown, so claiming it meets any bar would be a guess.
    Returns the kept entry points and how many were filtered out, so the caller
    can diagnose the hidden count instead of leaving the reader to notice that
    the tiers do not add up.
    """
    if min_exposure not in TIERS:
        raise ValueError(
            f"Unknown exposure: {min_exposure}. Known: {', '.join(TIERS)}, {UNKNOWN_AUTH}"
        )
    cutoff = TIERS.index(min_exposure)
    kept = [
        ep
        for ep in entry_points
        if ep.tier in TIERS and TIERS.index(ep.tier) <= cutoff
    ]
    return kept, len(entry_points) - len(kept)


# -- renderings -----------------------------------------------------------------


def _reach_line(ep: EntryPoint) -> str:
    if ep.reach_state == REACH_ENGINE:
        sinks = ", ".join(ep.sink_categories) if ep.sink_categories else "none reported"
        return f"reach: engine · sinks: {sinks}"
    if ep.reach_state == REACH_COMPUTED:
        if ep.reach_flows:
            sinks = ", ".join(ep.reach_sinks) if ep.reach_sinks else "untagged sinks"
            return f"reach: {ep.reach_flows} flow(s) · sinks: {sinks}"
        return "reach: computed — reaches no analysed flow"
    if ep.reach_state == REACH_SEED_NOT_FOUND:
        return "reach: seed-not-found (handler not locatable in the call graph)"
    return "reach: not computed (no call graph to traverse)"


def _entry_line(ep: EntryPoint) -> str:
    auth = ""
    if ep.allow_anonymous is None and ep.tier == UNKNOWN_AUTH:
        auth = "  [auth unknown]"
    if not ep.file:
        return f"{ep.label}{auth}"
    # atom routes carry no line number; printing "file:None" would put a
    # Python literal where a number belongs.
    where = f"  {ep.file}:{ep.line}" if ep.line is not None else f"  {ep.file}"
    return f"{ep.label}{where}{auth}"


def render_console(document: Dict, max_entries: int = 200) -> List[str]:
    """Console rendering: a tree per tier, exposure-first, with honest reach.

    Returned as plain lines so the command emits them through cleo's io (bare
    ``print()`` bypasses it, which is how query-endpoints once hid an empty
    listing from every test).
    """
    lines: List[str] = []
    summary = document["summary"]
    engines = document["engine"]
    sources = len(document["sources"])
    lines.append(
        f"Attack surface: {summary['entryPoints']} entry point(s)"
        f" from {sources} report(s) ({engines})"
    )
    lines.append(
        "tiers run most-exposed first; only dosai classifies authentication —"
        " every other engine's entries sit in unknown-auth, which is a gap, not a finding."
    )
    lines.append("")
    shown = 0
    truncated = False
    for tier in document["tiers"]:
        marker = "  ? " if tier["Exposure"] == UNKNOWN_AUTH else "  * "
        name = (
            f"{tier['Exposure']} [auth unknown — not an exposure verdict]"
            if tier["Exposure"] == UNKNOWN_AUTH
            else tier["Exposure"]
        )
        lines.append(
            f"{marker}{name}: {tier['EntryPointCount']} entry point(s),"
            f" {tier['WeaknessCount']} weakness(es)"
            f" ({tier['HighSeverityWeaknessCount']} high severity)"
        )
        for position, ep_dict in enumerate(tier["EntryPoints"]):
            if shown >= max_entries:
                truncated = True
                break
            ep = _ep_from_dict(ep_dict)
            branch = "   └── " if position == tier["EntryPointCount"] - 1 else "   ├── "
            lines.append(f"{branch}{_entry_line(ep)}")
            lines.append(f"   {'    '}{_reach_line(ep)}")
            if ep.reach_purls:
                shown_purls = ", ".join(ep.reach_purls[:3])
                more = f" (+{len(ep.reach_purls) - 3} more)" if len(ep.reach_purls) > 3 else ""
                lines.append(f"       packages: {shown_purls}{more}")
            shown += 1
        if truncated:
            break
        lines.append("")
    if truncated:
        lines.append(
            f"listing truncated at --max-entries {max_entries}; the json output"
            " carries every entry point."
        )
        lines.append("")
    present = {t["Exposure"] for t in document["tiers"]}
    empty = [t for t in document["tierOrder"] if t not in present]
    if empty:
        lines.append(f"tiers with no entry points here: {', '.join(empty)}")
    if summary.get("headline"):
        lines.append(f"headline: {summary['headline']}")
    elif not summary["anonymousReach"]["computed"]:
        lines.append(
            "headline suppressed: no input classifies authentication, so no entry"
            " point is known to be anonymous — a percentage here would invent a denominator."
        )
    for diagnostic in document.get("diagnostics", []):
        lines.append(f"note: {diagnostic}")
    return lines


def _ep_from_dict(ep_dict: Dict) -> EntryPoint:
    """Rehydrate enough of an entry point for rendering from its dict form."""
    reach = ep_dict.get("Reach") or {}
    return EntryPoint(
        engine=ep_dict.get("Engine") or "",
        id=ep_dict.get("EntryPointId") or "",
        tier=ep_dict.get("Exposure") or "",
        tier_source="engine",
        kind=ep_dict.get("Kind"),
        method=ep_dict.get("HttpMethod"),
        path=ep_dict.get("Route"),
        file=ep_dict.get("File") or "",
        line=ep_dict.get("LineNumber"),
        handler=ep_dict.get("Handler"),
        reach_state=reach.get("state", REACH_NOT_COMPUTED),
        reach_sinks=reach.get("sinkCategories") or [],
        reach_purls=reach.get("purls") or [],
        reach_functions=reach.get("functions") or [],
        reach_flows=reach.get("flows", 0),
        sink_categories=ep_dict.get("SinkCategories") or [],
    )


def render_mermaid(document: Dict, label_wrap: int = 26) -> str:
    """Mermaid flowchart with tiers as subgraphs, exposure-first.

    Entry points link to the sink categories they reach; endpoints whose reach
    is unknown or empty render without outgoing edges, which is the honest
    picture — a route with no drawn edge is a coverage gap on display.
    """
    from atom_tools.lib.visualizer import mm_escape, mm_label

    lines = ["flowchart TB"]
    lines.append("    classDef entry fill:#1a7f37,stroke:#116329,color:#fff")
    lines.append("    classDef sinkHigh fill:#cf222e,stroke:#a40e26,color:#fff")
    lines.append("    classDef sinkWarn fill:#d29922,stroke:#9a6700,color:#fff")
    counter = 0
    high_risk = {"sql", "ssrf", "code-execution", "command-injection", "path-traversal",
                 "deserialization", "xxe", "ldap", "xss", "log", "crypto", "file-write"}
    for tier_index, tier in enumerate(document["tiers"]):
        unknown = tier["Exposure"] == UNKNOWN_AUTH
        title = (
            f"{tier['Exposure']} — {tier['EntryPointCount']} (auth unknown)"
            if unknown
            else f"{tier['Exposure']} — {tier['EntryPointCount']}"
        )
        lines.append(f'    subgraph tier{tier_index}["{mm_escape(title)}"]')
        for ep_dict in tier["EntryPoints"]:
            counter += 1
            ep = _ep_from_dict(ep_dict)
            node_id = f"e{counter}"
            label = mm_label(ep.label, label_wrap)
            lines.append(f'        {node_id}("{label}"):::entry')
            for sink in ep.reach_sinks if ep.reach_state in (REACH_COMPUTED, REACH_ENGINE) else ep.sink_categories:
                counter += 1
                sink_id = f"s{counter}"
                kind = "sinkHigh" if sink in high_risk else "sinkWarn"
                lines.append(f'        {sink_id}["{mm_escape(sink, 40)}"]:::{kind}')
                lines.append(f"        {node_id} --> {sink_id}")
        lines.append("    end")
        if unknown:
            lines.append(f"    style tier{tier_index} stroke:#8b949e,stroke-dasharray: 4 3")
    return "\n".join(lines) + "\n"


HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>atom-tools attack surface</title>
<script src="{mermaid_src}"></script>
<style>
 body {{ background: #0d1117; color: #c9d1d9; font-family: -apple-system, sans-serif;
        margin: 0; padding: 2rem; }}
 h1 {{ color: #58a6ff; font-size: 1.4rem; }}
 .summary {{ display: flex; gap: 1.5rem; flex-wrap: wrap; margin-bottom: 1.5rem; }}
 .card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px;
         padding: .8rem 1.2rem; }}
 .card b {{ display: block; font-size: 1.4rem; color: #58a6ff; }}
 .headline {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px;
            padding: .8rem 1.2rem; margin-bottom: 1.5rem; }}
 .diagram {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px;
            padding: 1rem; overflow: auto; }}
 footer {{ color: #8b949e; margin-top: 1rem; font-size: .8rem; }}
</style>
</head>
<body>
<h1>Attack surface</h1>
<div class="summary">{summary}</div>
<div class="headline">{headline}</div>
<div class="diagram"><pre class="mermaid">{diagram}</pre></div>
<footer>Generated by atom-tools attack-surface from {source}. Subgraphs are
exposure tiers, most exposed first. The dashed grey tier is unknown-auth: those
endpoints' authentication state is unknown, which is a gap in the analysis, not
a verdict. Green nodes are entry points; red nodes are high-risk sink categories;
orange nodes are other reached sinks.</footer>
<script>mermaid.initialize({{ startOnLoad: true, theme: "dark" }});</script>
</body>
</html>
"""


def render_html(document: Dict, diagram: str, source: str, mermaid_js: Optional[str] = None) -> str:
    """Single-file HTML page embedding the tiered mermaid diagram."""
    import html as html_module

    from atom_tools.lib.visualizer import MERMAID_CDN

    summary = document["summary"]
    cards = [
        ("Entry points", summary["entryPoints"]),
        ("Tiers present", len(document["tiers"])),
        ("With reach", summary["entryPointsWithReach"]),
    ]
    card_html = "".join(
        f'<div class="card"><b>{value}</b>{html_module.escape(str(label))}</div>'
        for label, value in cards
    )
    if summary.get("headline"):
        headline = html_module.escape(summary["headline"])
    else:
        headline = (
            "Anonymous reach not reported: no input classifies authentication, so"
            " no entry point is known to be anonymous."
        )
    if mermaid_js:
        safe_js = mermaid_js.replace("</script", "<\\/script")
        head = f"<script>{safe_js}</script>"
    else:
        head = f'<script src="{MERMAID_CDN}"></script>'
    template = HTML_TEMPLATE.replace('<script src="{mermaid_src}"></script>', "{mermaid_head}")
    return template.format(
        mermaid_head=head,
        summary=card_html,
        headline=headline,
        diagram=html_module.escape(diagram),
        source=html_module.escape(os.path.basename(source)),
    )

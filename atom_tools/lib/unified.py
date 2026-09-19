"""The unified flow model.

Every supported engine (atom, dosai, golem, rusi, kosi) emits the same three shapes
— a source→sink flow, the nodes along its path, and an endpoint table — in
four incompatible schemas. The adapters in :mod:`atom_tools.lib.adapters`
normalise each of them into the dataclasses here, and
:func:`to_reachables_document` projects a unified report back into the atom
``reachables`` shape so every existing command (stats, visualize,
convert -f sarif, check-reachable, filter, query-endpoints) works on any
engine's report unchanged.

Honesty rules carried by the model:

- ``severity_source`` says whether the level came from the engine ("engine")
  or was derived from the shared taxonomy ("derived"). Never blended.
- ``path_truncated`` marks a path that is a truncated or representative
  witness rather than the complete story (golem caps trace ids per slice and
  flags report-level truncation; rusi records one representative witness).
- ``raw`` and ``extra`` keep the original record and engine-specific fields so
  the model is not a lossy lowest common denominator.
"""

import logging
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional

from atom_tools.lib import taxonomy

logger = logging.getLogger(__name__)

SEVERITY_LEVELS = ("error", "warning", "note")


@dataclass
class UnifiedNode:
    """One step of a flow's path, hydrated from whatever the engine emitted."""

    name: str
    code: str = ""
    file: str = ""
    line: Optional[int] = None
    column: Optional[int] = None
    symbol: Optional[str] = None
    function: Optional[str] = None
    package: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    purl: Optional[str] = None
    role: str = "step"  # "source" | "sink" | "sanitizer" | "step"

    @classmethod
    def from_dict(cls, data: Dict) -> "UnifiedNode":
        """Rebuild a node from :meth:`UnifiedReport.to_dict` output."""
        return cls(
            name=data.get("name", ""),
            code=data.get("code", ""),
            file=data.get("file", ""),
            line=data.get("line"),
            column=data.get("column"),
            symbol=data.get("symbol"),
            function=data.get("function"),
            package=data.get("package"),
            tags=list(data.get("tags") or []),
            purl=data.get("purl"),
            role=data.get("role", "step"),
        )


@dataclass
class UnifiedFlow:
    """A single source→sink flow with its hydrated, ordered path."""

    id: str
    nodes: List[UnifiedNode]
    source_category: str
    sink_category: str
    severity: str  # error | warning | note
    severity_source: str  # "engine" | "derived"
    confidence: Optional[str] = None
    taint_kinds: List[str] = field(default_factory=list)
    purls: List[str] = field(default_factory=list)
    sanitized: bool = False
    path_truncated: bool = False
    engine: str = ""
    engine_version: str = ""
    analysis_mode: str = ""
    raw: Dict = field(default_factory=dict)
    extra: Dict = field(default_factory=dict)

    @property
    def source(self) -> Optional[UnifiedNode]:
        return self.nodes[0] if self.nodes else None

    @property
    def sink(self) -> Optional[UnifiedNode]:
        return self.nodes[-1] if self.nodes else None

    @classmethod
    def from_dict(cls, data: Dict) -> "UnifiedFlow":
        """Rebuild a flow from :meth:`UnifiedReport.to_dict` output."""
        return cls(
            id=data.get("id", ""),
            nodes=[UnifiedNode.from_dict(n) for n in data.get("nodes") or []],
            source_category=data.get("source_category", ""),
            sink_category=data.get("sink_category", ""),
            severity=data.get("severity", "note"),
            severity_source=data.get("severity_source", "derived"),
            confidence=data.get("confidence"),
            taint_kinds=list(data.get("taint_kinds") or []),
            purls=list(data.get("purls") or []),
            sanitized=bool(data.get("sanitized", False)),
            path_truncated=bool(data.get("path_truncated", False)),
            engine=data.get("engine", ""),
            engine_version=data.get("engine_version", ""),
            analysis_mode=data.get("analysis_mode", ""),
            raw=dict(data.get("raw") or {}),
            extra=dict(data.get("extra") or {}),
        )


@dataclass
class UnifiedReport:
    """A whole engine report normalised: flows plus the surrounding context."""

    engine: str
    engine_version: str = ""
    schema_version: str = ""
    analysis_mode: str = ""
    source_file: str = ""
    flows: List[UnifiedFlow] = field(default_factory=list)
    endpoints: List[Dict] = field(default_factory=list)
    packages: List[Dict] = field(default_factory=list)
    diagnostics: List[str] = field(default_factory=list)
    provenance: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "UnifiedReport":
        """Rebuild a unified report from :meth:`to_dict` output.

        The unified document written by ``ingest --emit unified`` used to be
        write-only: no loader, and ``detect_engine`` returned None on it, so
        every command that takes a report rejected it. The ``detect``/``parse``
        pair below registers this loader alongside the engine adapters, making
        the round-trip ``parse_report → to_dict → from_dict`` exact.
        """
        return cls(
            engine=data.get("engine", ""),
            engine_version=data.get("engine_version", ""),
            schema_version=data.get("schema_version", ""),
            analysis_mode=data.get("analysis_mode", ""),
            source_file=data.get("source_file", ""),
            flows=[UnifiedFlow.from_dict(f) for f in data.get("flows") or []],
            endpoints=[dict(e) for e in data.get("endpoints") or []],
            packages=[dict(p) for p in data.get("packages") or []],
            diagnostics=list(data.get("diagnostics") or []),
            provenance=dict(data.get("provenance") or {}),
        )


def detect(content) -> bool:
    """True for a document produced by ``UnifiedReport.to_dict()``.

    The signature — a string ``engine``, a ``flows`` list, a ``provenance``
    dict and a string ``schema_version`` at the top level — is carried by no
    engine's own report (dosai nests its metadata, golem/rusi/kosi use ``tool``,
    atom has no envelope), so it cannot shadow vendor detection.
    """
    return (
        isinstance(content, dict)
        and isinstance(content.get("engine"), str)
        and bool(content.get("engine"))
        and isinstance(content.get("flows"), list)
        and isinstance(content.get("provenance"), dict)
        and isinstance(content.get("schema_version"), str)
    )


def parse(content, source_file: str = "") -> UnifiedReport:
    """Adapter-shaped loader for unified documents (registered in ENGINE_MODULES)."""
    report = UnifiedReport.from_dict(content)
    report.source_file = source_file
    return report


def hydrate(
    flow_id: str,
    id_order: List[str],
    nodes_by_id: Dict[str, Dict],
    dropped: List[str],
) -> List[Dict]:
    """
    Resolve an ordered list of node ids against a node table.

    This is the core join the non-atom engines require: they store id
    references, atom embeds node objects. Missing ids are collected in
    ``dropped`` (the caller turns that into a diagnostic and drops the flow —
    never silently).
    """
    hydrated: List[Dict] = []
    for node_id in id_order:
        node = nodes_by_id.get(node_id)
        if node is None:
            dropped.append(node_id)
        else:
            hydrated.append(node)
    return hydrated


def check_schema_version(
    engine: str,
    schema_version: str,
    supported: str,
    diagnostics: List[str],
) -> None:
    """
    Warn (and continue) when a report's schema version is not the supported
    one; never hard-fail. Comparison is on the trailing version token, so both
    semver ("5.0.0") and URI (".../schema/v6", ".../report-0.1") styles work.
    """

    def version_token(value: str) -> str:
        return value.rstrip("/").rsplit("/", 1)[-1].rsplit("-", 1)[-1].split(".", 1)[0]

    if not schema_version:
        return
    if version_token(schema_version) != version_token(supported):
        message = (
            f"{engine} schema version '{schema_version}' differs from the supported "
            f"'{supported}'; ingesting anyway — field names may have drifted."
        )
        logger.warning(message)
        diagnostics.append(message)


def merge_reports(reports: List["UnifiedReport"]) -> "UnifiedReport":
    """Merge unified reports from several inputs into one (ingest command)."""
    if not reports:
        raise ValueError("No reports to merge.")
    primary = reports[0]
    merged = UnifiedReport(
        engine="+".join(r.engine for r in reports),
        engine_version=primary.engine_version,
        schema_version=primary.schema_version,
        analysis_mode="+".join(sorted({r.analysis_mode for r in reports if r.analysis_mode})),
        source_file=",".join(r.source_file for r in reports if r.source_file),
        flows=[f for r in reports for f in r.flows],
        endpoints=[e for r in reports for e in r.endpoints],
        packages=[p for r in reports for p in r.packages],
        diagnostics=[d for r in reports for d in r.diagnostics],
        provenance={"sources": [r.provenance | {"file": r.source_file} for r in reports]},
    )
    return merged


def _compat_node(node: UnifiedNode, flow_purls: List[str]) -> Dict:
    """
    Project a UnifiedNode into the node shape atom emits inside reachables
    entries (name/code/parentFileName/lineNumber/columnNumber/tags with purls
    embedded comma-separated, exactly like chen writes them).

    Engine category names are kept *and* their chen equivalent is added
    alongside, so tag-driven consumers (``stats`` source/sink counting,
    ``filter``, ``sarif`` rule derivation) recognise an engine flow the same
    way they recognise an atom one. Without the mapped tag a golem report's
    ``configuration`` source and ``external-service`` sink are invisible to
    every one of them.
    """
    tags = [t for t in node.tags if t]
    for tag in list(tags):
        mapped = taxonomy.category_to_tag(tag)
        if mapped and mapped not in tags:
            tags.append(mapped)
    tags.extend(p for p in flow_purls if p and p not in tags)
    compat = {
        "label": node.symbol or node.name,
        "name": node.name,
        "fullName": node.symbol or "",
        "isExternal": bool(node.purl and node.purl.startswith("pkg:")),
        "code": node.code or node.name,
        "parentFileName": node.file,
        "lineNumber": node.line if isinstance(node.line, int) and node.line >= 0 else None,
        "columnNumber": node.column,
        "tags": ",".join(tags),
    }
    return {k: v for k, v in compat.items() if v is not None}


# The key each engine publishes its endpoint table under, used to rebuild that
# table when the source document was a unified one rather than the engine's own.
ENDPOINT_ARRAY_KEYS = {"golem": "apiEndpoints", "rusi": "api_endpoints", "kosi": "apiEndpoints"}


def to_reachables_document(report: UnifiedReport, original: Optional[Dict] = None) -> Dict:
    """
    Project a unified report into an atom ``reachables``-shaped document.

    The document also preserves the engine's own endpoint arrays under their
    original keys (``apiEndpoints`` for golem, ``api_endpoints`` for rusi) so
    endpoint-oriented consumers keep working on the same file. Entries carry
    ``severity``/``severitySource``/``confidence``/``pathTruncated`` keys when
    known; atom's own entries never have them, which is how downstream code
    distinguishes engine-provided levels from derived ones without behaviour
    changes on atom slices.
    """
    entries = []
    for flow in report.flows:
        nodes = [_compat_node(n, flow.purls) for n in flow.nodes]
        if not nodes:
            continue
        entry = {
            "flows": nodes,
            "purls": sorted(flow.purls),
            "severity": flow.severity,
            "severitySource": flow.severity_source,
            "pathTruncated": flow.path_truncated,
            "engine": flow.engine,
        }
        if flow.confidence:
            entry["confidence"] = flow.confidence
        if flow.id:
            entry["flowId"] = flow.id
        entries.append(entry)
    document = {"reachables": entries}
    # Analysis provenance travels with the compat document so consumers can
    # tell the reader that an engine stopped early. A truncated run silently
    # reported as a flow count reads as a complete picture, which is exactly
    # the claim the evidence does not support.
    provenance = dict(report.provenance or {})
    if report.diagnostics:
        provenance["diagnostics"] = list(report.diagnostics)
    if provenance:
        document["analysisProvenance"] = provenance
    copied = False
    if isinstance(original, dict):
        for key in ("apiEndpoints", "api_endpoints"):
            if isinstance(original.get(key), list):
                document[key] = original[key]
                copied = True
    if not copied:
        # Nothing to copy: either there is no vendor document, or the one we
        # have is itself a unified document -- which became a valid input when
        # from_dict landed. The model keeps each endpoint's verbatim vendor
        # entry in ``raw``, so rebuild the array from those rather than dropping
        # the endpoints. Without this, round-tripping a golem report through
        # ``--emit unified`` and back silently lost all 57 of its endpoints, and
        # go_converter/rust_converter read exactly these keys.
        key = ENDPOINT_ARRAY_KEYS.get(report.engine)
        raws = [e["raw"] for e in report.endpoints if isinstance(e.get("raw"), dict)]
        if key and raws:
            document[key] = raws
    return document

"""Adapter for Dosai data-flow reports (.NET).

Dosai (schema 5.0.0) emits a ``DataFlowResult`` with ``Slices[]`` that
reference nodes and edges by id; the adapter hydrates ``NodeIds`` against the
``Nodes`` table. Slices carry an explicit ``Severity``
(info/low/medium/high/critical — the engine derives it from the sink pattern,
we treat the emitted field as authoritative) and ``Confidence``; both are
normalised onto the shared scales with ``severity_source="engine"``.

The methods report (``dosai methods``) has no ``Slices`` section by design; it
is parsed with zero flows and its ``ApiEndpoints``/``CallGraph`` context kept.
The crypto report (``dosai crypto``) nests its dataflows payload under
``CryptoDataFlows``; that sub-document is read as the flow source
(``analysis_mode="crypto"``) while the crypto inventory (Assets/Findings/...)
stays engine-side for ``crypto-reach``.
"""

import logging
from typing import Dict, List

from atom_tools.lib import taxonomy
from atom_tools.lib.unified import (
    UnifiedFlow,
    UnifiedNode,
    UnifiedReport,
    check_schema_version,
    hydrate,
)

logger = logging.getLogger(__name__)

ENGINE = "dosai"
SUPPORTED_SCHEMA = "5.0.0"


def detect(content) -> bool:
    """True for Dosai reports (``Metadata.Tool == "Dosai"``)."""
    metadata = content.get("Metadata") if isinstance(content, dict) else None
    return isinstance(metadata, dict) and metadata.get("Tool") == "Dosai"


def _node(raw: Dict, role: str) -> UnifiedNode:
    return UnifiedNode(
        name=raw.get("Name") or raw.get("Symbol") or "",
        code=raw.get("Code") or "",
        file=raw.get("FileName") or raw.get("Path") or "",
        line=raw.get("LineNumber"),
        column=raw.get("ColumnNumber"),
        symbol=raw.get("Symbol"),
        function=raw.get("MethodName"),
        package=raw.get("Namespace"),
        tags=[raw["Category"]] if raw.get("Category") else [],
        purl=raw.get("Purl"),
        role=role,
    )


def _endpoints(content: Dict) -> List[Dict]:
    endpoints: List[Dict] = []
    for ep in content.get("ApiEndpoints") or []:
        endpoints.append(
            {
                "method": ep.get("HttpMethod"),
                "path": ep.get("Route") or ep.get("Path"),
                "file": ep.get("FilePath") or ep.get("FileName"),
                "line": ep.get("Line"),
                "framework": ep.get("Framework"),
                "handler": ".".join(
                    p
                    for p in (ep.get("Namespace"), ep.get("ClassName"), ep.get("MethodName"))
                    if p
                )
                or None,
                "raw": ep,
            }
        )
    for ep in content.get("EntryPoints") or []:
        endpoints.append(
            {
                "method": None,
                "path": None,
                "file": ep.get("FileName") or ep.get("Path"),
                "line": ep.get("Line"),
                "kind": ep.get("Kind"),
                "handler": ".".join(
                    p
                    for p in (ep.get("Namespace"), ep.get("ClassName"), ep.get("MethodName"))
                    if p
                )
                or ep.get("MethodId"),
                "id": ep.get("Id"),
                "raw": ep,
            }
        )
    return endpoints


def parse(content, source_file: str = "") -> UnifiedReport:
    """Normalise a Dosai dataflows (or methods/crypto) report into a unified report."""
    metadata = content.get("Metadata") or {}
    # The crypto command nests the whole dataflows payload under
    # CryptoDataFlows and puts the crypto inventory beside it; the flow
    # sections are read from there so flows, endpoints and packages parse
    # exactly as they do from a dataflows report.
    cdf = content.get("CryptoDataFlows")
    source = content if not isinstance(cdf, dict) or content.get("Slices") is not None else cdf
    if content.get("Slices") is not None:
        mode = "dataflows"
    elif source is cdf:
        mode = "crypto"
    else:
        mode = "methods"
    diagnostics: List[str] = list(source.get("Diagnostics") or [])
    check_schema_version(ENGINE, metadata.get("SchemaVersion", ""), SUPPORTED_SCHEMA, diagnostics)

    nodes_by_id = {n.get("Id"): n for n in source.get("Nodes") or []}
    sanitized_ids = {
        sf.get("SliceId") for sf in source.get("SanitizedFlows") or [] if sf.get("SliceId")
    }
    weakness_by_slice: Dict[str, List[str]] = {}
    for wc in source.get("WeaknessCandidates") or []:
        if wc.get("SliceId"):
            weakness_by_slice.setdefault(wc["SliceId"], []).append(wc.get("Id") or "")

    flows: List[UnifiedFlow] = []
    dropped_ids: List[str] = []
    dropped_flows = 0
    for sl in source.get("Slices") or []:
        id_order = sl.get("NodeIds") or [sl.get("SourceId"), sl.get("SinkId")]
        missing: List[str] = []
        hydrated = hydrate(sl.get("Id", ""), [i for i in id_order if i], nodes_by_id, missing)
        if missing:
            dropped_ids.extend(missing)
            dropped_flows += 1
            continue
        nodes = [
            _node(n, "source" if i == 0 else "sink" if i == len(hydrated) - 1 else "step")
            for i, n in enumerate(hydrated)
        ]
        for node, raw in zip(nodes, hydrated):
            if raw.get("IsSource"):
                node.role = "source"
            elif raw.get("IsSink"):
                node.role = "sink"
        level = taxonomy.normalise_engine_severity(sl.get("Severity"))
        severity_source = "engine" if level else "derived"
        if not level:
            level, tag = taxonomy.derive_level_and_tag(
                sl.get("SourceCategory"), sl.get("SinkCategory")
            )
        else:
            _, tag = taxonomy.derive_level_and_tag(
                sl.get("SourceCategory"), sl.get("SinkCategory")
            )
        purls = [p for p in sl.get("Purls") or [] if isinstance(p, str)]
        flows.append(
            UnifiedFlow(
                id=sl.get("Id", ""),
                nodes=nodes,
                source_category=sl.get("SourceCategory") or "",
                sink_category=sl.get("SinkCategory") or "",
                severity=level or "note",
                severity_source=severity_source,
                confidence=(sl.get("Confidence") or "").lower() or None,
                taint_kinds=list(sl.get("TaintKinds") or []),
                purls=purls,
                sanitized=sl.get("Id") in sanitized_ids,
                engine=ENGINE,
                engine_version=metadata.get("AnalyzerVersion", ""),
                analysis_mode=mode,
                raw=sl,
                extra={
                    k: sl[k]
                    for k in (
                        "SourcePurl",
                        "SinkPurl",
                        "SinkArgument",
                        "SinkArgumentIndex",
                        "Summary",
                        "FieldPaths",
                        "EdgeIds",
                    )
                    if sl.get(k)
                }
                | {"weakness_ids": weakness_by_slice.get(sl.get("Id"), [])}
                | ({"derived_tag": tag} if tag else {}),
            )
        )

    if dropped_flows:
        message = (
            f"Dropped {dropped_flows} dosai slice(s) with unresolvable node ids: "
            f"{sorted(set(dropped_ids))[:5]}"
        )
        logger.warning(message)
        diagnostics.append(message)

    packages = [
        {
            "purl": pr.get("Purl"),
            "reachable": pr.get("Reachable"),
            "kind": pr.get("ReachabilityKind"),
            "confidence": (pr.get("Confidence") or "").lower() or None,
        }
        for pr in source.get("PackageReachability") or []
    ]
    return UnifiedReport(
        engine=ENGINE,
        engine_version=metadata.get("AnalyzerVersion", ""),
        schema_version=metadata.get("SchemaVersion", ""),
        analysis_mode=mode,
        source_file=source_file,
        flows=flows,
        endpoints=_endpoints(source),
        packages=packages,
        diagnostics=diagnostics,
        provenance={
            "engine": ENGINE,
            "engine_version": metadata.get("AnalyzerVersion", ""),
            "schema_version": metadata.get("SchemaVersion", ""),
            "analysis_mode": mode,
            "generated_at": metadata.get("GeneratedAt"),
            "severity": "engine",
        },
    )

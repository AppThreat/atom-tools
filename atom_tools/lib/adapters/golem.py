"""Adapter for golem reports (Go).

golem's ``dataFlow.slices[]`` reference ``dataFlow.nodes`` by id (the ``seam-*``
id space, separate from the ``callGraph`` id space). Slices carry an explicit
severity and confidence (``severity_source="engine"``).

Witness honesty: golem emits one representative witness path per slice,
capped at 64 trace nodes / 128 trace edges by default, and flags report-level
truncation in ``dataFlow.stats`` (this run hit the 1000-slice limit — see
PROVENANCE.md). Slices at or beyond the trace caps get ``path_truncated=True``,
and the report-level flag/reasons are carried into diagnostics.
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

ENGINE = "golem"
SUPPORTED_SCHEMA = "https://cdxgen.github.io/cdxgen-plugins-bin/golem/schema/v6"
# golem's defaults (dataflow-max-trace-nodes / dataflow-max-trace-edges).
TRACE_NODE_CAP = 64
TRACE_EDGE_CAP = 128


def detect(content) -> bool:
    """True for golem reports carrying a flow or endpoint section."""
    tool = content.get("tool") if isinstance(content, dict) else None
    return (
        isinstance(tool, dict)
        and tool.get("name") == "golem"
        and ("dataFlow" in content or "apiEndpoints" in content)
    )


def _node(raw: Dict, role: str) -> UnifiedNode:
    position = raw.get("position") or {}
    return UnifiedNode(
        name=raw.get("name") or raw.get("label") or "",
        code=raw.get("code") or raw.get("label") or "",
        file=raw.get("filename") or raw.get("file") or position.get("filename") or "",
        line=raw.get("line") if isinstance(raw.get("line"), int) else position.get("line"),
        column=raw.get("column") if isinstance(raw.get("column"), int) else position.get("column"),
        symbol=raw.get("symbol"),
        function=raw.get("function"),
        package=raw.get("packagePath"),
        tags=[raw["category"]] if raw.get("category") else [],
        purl=raw.get("purl"),
        role=role,
    )


def _endpoint(ep: Dict) -> Dict:
    start = (ep.get("range") or {}).get("start") or {}
    return {
        "method": ep.get("method"),
        "path": ep.get("path"),
        "kind": ep.get("kind"),
        "framework": ep.get("framework"),
        "handler": ep.get("handler"),
        "file": ep.get("file") or start.get("filename"),
        "line": start.get("line"),
        "package": ep.get("packagePath"),
        "purl": ep.get("purl"),
        "raw": ep,
    }


def parse(content, source_file: str = "") -> UnifiedReport:
    """Normalise a golem report into a unified report."""
    tool = content.get("tool") or {}
    diagnostics: List[str] = []
    check_schema_version(ENGINE, content.get("schemaVersion", ""), SUPPORTED_SCHEMA, diagnostics)

    data_flow = content.get("dataFlow") or {}
    df_stats = data_flow.get("stats") or {}
    if df_stats.get("truncated"):
        reasons = "; ".join(df_stats.get("truncationReasons") or [])
        diagnostics.append(f"golem data-flow truncated: {reasons or 'reason not stated'}")
    mode = data_flow.get("mode") or "none"

    nodes_by_id = {n.get("id"): n for n in data_flow.get("nodes") or []}
    flows: List[UnifiedFlow] = []
    dropped_ids: List[str] = []
    dropped_flows = 0
    for sl in data_flow.get("slices") or []:
        id_order = sl.get("nodeIds") or [sl.get("sourceId"), sl.get("sinkId")]
        missing: List[str] = []
        hydrated = hydrate(sl.get("id", ""), [i for i in id_order if i], nodes_by_id, missing)
        if missing:
            dropped_ids.extend(missing)
            dropped_flows += 1
            continue
        nodes = [
            _node(n, "source" if i == 0 else "sink" if i == len(hydrated) - 1 else "step")
            for i, n in enumerate(hydrated)
        ]
        level = taxonomy.normalise_engine_severity(sl.get("severity"))
        severity_source = "engine" if level else "derived"
        if not level:
            level, _ = taxonomy.derive_level_and_tag(
                sl.get("sourceCategory"), sl.get("sinkCategory")
            )
        purls = [p for p in sl.get("purls") or [] if isinstance(p, str)]
        path_truncated = (
            len(sl.get("nodeIds") or []) >= TRACE_NODE_CAP
            or len(sl.get("edgeIds") or []) >= TRACE_EDGE_CAP
        )
        flows.append(
            UnifiedFlow(
                id=sl.get("id", ""),
                nodes=nodes,
                source_category=sl.get("sourceCategory") or "",
                sink_category=sl.get("sinkCategory") or "",
                severity=level or "note",
                severity_source=severity_source,
                confidence=(sl.get("confidence") or "").lower() or None,
                taint_kinds=list(sl.get("taintKinds") or []),
                purls=purls,
                sanitized=bool(sl.get("sanitizerNodeIds")),
                path_truncated=path_truncated,
                engine=ENGINE,
                engine_version=tool.get("version", ""),
                analysis_mode=mode,
                raw=sl,
                extra={
                    k: sl[k]
                    for k in (
                        "flowKey",
                        "duplicateOf",
                        "duplicateIndex",
                        "ruleId",
                        "ruleName",
                        "riskScore",
                        "crossesDependency",
                        "dependencyHops",
                        "sourcePurl",
                        "sinkPurl",
                        "sinkArgumentIndex",
                        "fieldPaths",
                        "edgeKinds",
                    )
                    if sl.get(k)
                },
            )
        )

    if dropped_flows:
        message = (
            f"Dropped {dropped_flows} golem slice(s) with unresolvable node ids: "
            f"{sorted(set(dropped_ids))[:5]}"
        )
        logger.warning(message)
        diagnostics.append(message)

    packages = [
        {"purl": p, "reachable": None, "kind": None, "confidence": None}
        for p in sorted({p for f in flows for p in f.purls})
    ]
    return UnifiedReport(
        engine=ENGINE,
        engine_version=tool.get("version", ""),
        schema_version=content.get("schemaVersion", ""),
        analysis_mode=mode,
        source_file=source_file,
        flows=flows,
        endpoints=[_endpoint(ep) for ep in content.get("apiEndpoints") or []],
        packages=packages,
        diagnostics=diagnostics,
        provenance={
            "engine": ENGINE,
            "engine_version": tool.get("version", ""),
            "schema_version": content.get("schemaVersion", ""),
            "analysis_mode": mode,
            "severity": "engine",
            "dataflow_truncated": bool(df_stats.get("truncated")),
            "callgraph_mode": (content.get("callGraph") or {}).get("mode"),
        },
    )

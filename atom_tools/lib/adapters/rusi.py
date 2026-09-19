"""Adapter for rusi reports (Rust).

rusi's ``data_flow.slices[]`` (snake_case) reference ``data_flow.nodes`` by
id. Slices carry **no severity field** — only a ``rule_name`` — so levels are
derived from the source/sink categories through the shared taxonomy with
``severity_source="derived"`` (the real reports behind
``test/data/ecosystem/PROVENANCE.md`` confirmed there is nothing to take from
the engine here).

Witness honesty: rusi records one representative witness per slice
(``node_ids``/``edge_ids``, documented cap of 32 ids per value, chains over 64
steps dropped). Slices at or beyond the cap get ``path_truncated=True``; the
representative-witness caveat itself is recorded in provenance.
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

ENGINE = "rusi"
SUPPORTED_SCHEMA = "https://appthreat.github.io/rusi/schema/report-0.1"
# rusi's documented per-value witness cap.
WITNESS_CAP = 32


def detect(content) -> bool:
    """True for rusi reports carrying a flow or endpoint section."""
    tool = content.get("tool") if isinstance(content, dict) else None
    return (
        isinstance(tool, dict)
        and tool.get("name") == "rusi"
        and ("data_flow" in content or "api_endpoints" in content)
    )


def _node(raw: Dict, role: str) -> UnifiedNode:
    position = raw.get("position") or {}
    return UnifiedNode(
        name=raw.get("name") or "",
        code=raw.get("name") or "",
        file=position.get("filename") or raw.get("filename") or "",
        line=position.get("line"),
        column=position.get("column"),
        symbol=None,
        function=raw.get("function"),
        package=raw.get("package_path"),
        tags=[raw["category"]] if raw.get("category") else [],
        purl=raw.get("purl"),
        role=role,
    )


def _endpoint(ep: Dict) -> Dict:
    return {
        "method": ep.get("method"),
        "path": ep.get("path"),
        "kind": "http-route",
        "framework": ep.get("framework"),
        "handler": ep.get("handler"),
        "file": ep.get("file_path"),
        "line": (ep.get("position") or {}).get("line"),
        "package": ep.get("package_path"),
        "purl": ep.get("purl"),
        "raw": ep,
    }


def parse(content, source_file: str = "") -> UnifiedReport:
    """Normalise a rusi report into a unified report."""
    tool = content.get("tool") or {}
    diagnostics: List[str] = [
        d.get("message") or str(d) for d in content.get("diagnostics") or [] if isinstance(d, dict)
    ]
    check_schema_version(ENGINE, content.get("schema_version", ""), SUPPORTED_SCHEMA, diagnostics)

    data_flow = content.get("data_flow") or {}
    mode = data_flow.get("mode") or "none"

    nodes_by_id = {n.get("id"): n for n in data_flow.get("nodes") or []}
    flows: List[UnifiedFlow] = []
    dropped_ids: List[str] = []
    dropped_flows = 0
    for sl in data_flow.get("slices") or []:
        id_order = sl.get("node_ids") or [sl.get("source_id"), sl.get("sink_id")]
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
        for node, raw in zip(nodes, hydrated):
            if raw.get("kind") == "source":
                node.role = "source"
            elif raw.get("kind") == "sink":
                node.role = "sink"
        # rusi emits no severity: derive from the categories, never blend.
        level, tag = taxonomy.derive_level_and_tag(
            sl.get("source_category"), sl.get("sink_category")
        )
        purls = [p for p in sl.get("purls") or [] if isinstance(p, str)]
        path_truncated = (
            len(sl.get("node_ids") or []) >= WITNESS_CAP
            or len(sl.get("edge_ids") or []) >= WITNESS_CAP
        )
        flows.append(
            UnifiedFlow(
                id=sl.get("id", ""),
                nodes=nodes,
                source_category=sl.get("source_category") or "",
                sink_category=sl.get("sink_category") or "",
                severity=level,
                severity_source="derived",
                confidence=None,
                taint_kinds=[sl["rule_name"]] if sl.get("rule_name") else [],
                purls=purls,
                sanitized=False,
                path_truncated=path_truncated,
                engine=ENGINE,
                engine_version=tool.get("version", ""),
                analysis_mode=mode,
                raw=sl,
                extra={
                    k: sl[k]
                    for k in (
                        "rule_name",
                        "description",
                        "path_length",
                        "sourcePurl",
                        "targetPurl",
                        "source_parameter_index",
                        "sink_parameter_index",
                        "source_type_name",
                        "sink_type_name",
                        "edge_ids",
                    )
                    if sl.get(k) is not None
                }
                | ({"derived_tag": tag} if tag else {}),
            )
        )

    if dropped_flows:
        message = (
            f"Dropped {dropped_flows} rusi slice(s) with unresolvable node ids: "
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
        schema_version=content.get("schema_version", ""),
        analysis_mode=mode,
        source_file=source_file,
        flows=flows,
        endpoints=[_endpoint(ep) for ep in content.get("api_endpoints") or []],
        packages=packages,
        diagnostics=diagnostics,
        provenance={
            "engine": ENGINE,
            "engine_version": tool.get("version", ""),
            "schema_version": content.get("schema_version", ""),
            "analysis_mode": mode,
            "severity": "derived",
            "witness": "one representative witness per slice",
        },
    )

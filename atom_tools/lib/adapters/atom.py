"""Adapter for atom reachable slices (the native format).

atom embeds full node objects inline in each flow group, so unlike the other
engines there is no hydration join to do. The tag string on each node mixes
purls, framework markers and semantic classes; it is split here and mapped
onto the shared taxonomy. atom emits no severity, so levels are always
derived (``severity_source="derived"``).
"""

import logging
from typing import Dict, List

from atom_tools.lib import taxonomy
from atom_tools.lib.unified import UnifiedFlow, UnifiedNode, UnifiedReport

logger = logging.getLogger(__name__)

ENGINE = "atom"
ENGINE_VERSION = ""  # atom slices carry no tool version in the document


def split_node_tags(value) -> List[str]:
    """Split a node's comma separated tag string, dropping purls and markers."""
    if isinstance(value, list):
        parts = [str(t) for t in value]
    else:
        parts = (value or "").split(",")
    return [
        t.strip()
        for t in parts
        if t.strip() and not t.strip().startswith("pkg:") and t.strip() != "framework"
    ]


def detect(content) -> bool:
    """True for atom reachables documents (wrapped or bare-array form)."""
    if isinstance(content, list):
        return bool(content) and isinstance(content[0], dict) and "flows" in content[0]
    return isinstance(content, dict) and isinstance(content.get("reachables"), list)


def _node_purl(raw: Dict):
    """Pull the pkg: purl embedded in a node's tag string or list, if any."""
    tags = raw.get("tags")
    if isinstance(tags, str):
        return next((t.strip() for t in tags.split(",") if t.strip().startswith("pkg:")), None)
    if isinstance(tags, list):
        return next((t for t in tags if isinstance(t, str) and t.startswith("pkg:")), None)
    return None


def _node(raw: Dict, role: str) -> UnifiedNode:
    return UnifiedNode(
        name=raw.get("name") or raw.get("code") or "",
        code=raw.get("code") or "",
        file=raw.get("parentFileName") or raw.get("fileName") or "",
        line=raw.get("lineNumber"),
        column=raw.get("columnNumber"),
        symbol=raw.get("fullName") or raw.get("label"),
        function=raw.get("parentMethodName"),
        package=raw.get("parentPackageName"),
        tags=split_node_tags(raw.get("tags")),
        purl=_node_purl(raw),
        role=role,
    )


def parse(content, source_file: str = "") -> UnifiedReport:
    """
    Normalise an atom reachables document (``{"reachables": [...]}`` or the
    bare chunk array) into a unified report.
    """
    entries = content if isinstance(content, list) else content.get("reachables", [])
    entries = entries or []
    flows: List[UnifiedFlow] = []
    for index, entry in enumerate(entries):
        raw_nodes = entry.get("flows") or []
        if not raw_nodes:
            continue
        nodes = [
            _node(n, "source" if i == 0 else "sink" if i == len(raw_nodes) - 1 else "step")
            for i, n in enumerate(raw_nodes)
        ]
        source_tags = nodes[0].tags if nodes else []
        sink_tags = nodes[-1].tags if nodes else []
        source_category = source_tags[0] if source_tags else ""
        sink_category = sink_tags[0] if sink_tags else ""
        level, tag = taxonomy.derive_level_and_tag(source_category, sink_category)
        flows.append(
            UnifiedFlow(
                id=str(entry.get("id") or f"atom-flow-{index}"),
                nodes=nodes,
                source_category=source_category,
                sink_category=sink_category,
                severity=level,
                severity_source="derived",
                purls=[p for p in entry.get("purls") or [] if isinstance(p, str)],
                engine=ENGINE,
                engine_version=ENGINE_VERSION,
                analysis_mode="reachables",
                raw=entry,
                extra={"derived_tag": tag} if tag else {},
            )
        )
    return UnifiedReport(
        engine=ENGINE,
        engine_version=ENGINE_VERSION,
        analysis_mode="reachables",
        source_file=source_file,
        flows=flows,
        provenance={"engine": ENGINE, "analysis_mode": "reachables", "severity": "derived"},
    )

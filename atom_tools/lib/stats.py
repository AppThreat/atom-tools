"""
Slice statistics.

Summarises any atom slice type (usages, reachables, data-flow, parsedeps,
semantics and the rusi/golem api endpoint reports) into the numbers that matter
during triage: how many flows exist, which files they live in, which packages
(purls) and which chen tags are involved. Designed for both humans (the stats
command) and CI (``--json`` output).
"""

import logging
from collections import Counter
from typing import Dict, List

logger = logging.getLogger(__name__)

# Tags treated as taint sources / sinks by atom's default reachables profile.
SOURCE_TAGS = (
    "framework-input",
    "framework-route",
    "cli-source",
    "driver-source",
    "sensitive-data",
    "pii",
    "service-ingress",
    "mcp-input",
)
SINK_TAGS = (
    "framework-output",
    "library-call",
    "sql",
    "http",
    "file-io",
    "code-execution",
    "shell-exec",
    "ssrf",
    "path-traversal",
    "template-injection",
    "xxe",
    "reflection",
    "unsafe-deserialization",
    "service-egress",
    "on-device-ai",
    "ai-prompt",
    "ai-invoke",
    "tracker",
    "adware",
)


def split_tags(value) -> List[str]:
    """Normalise a node tags value (string or list) into individual tags."""
    if isinstance(value, list):
        parts = [str(t) for t in value]
    else:
        parts = (value or "").split(",")
    return [t.strip() for t in parts if t.strip()]


def _top(counter: Dict[str, int], limit: int = 10) -> Dict[str, int]:
    """Return the ``limit`` most common entries of a counter."""
    return dict(sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))[:limit])


class SliceStats:
    """
    Computes statistics for a parsed atom slice.

    Args:
        content (dict): The parsed slice document.
        slice_type (str): One of usages, reachables, data-flow, parsedeps,
            semantics or api_endpoints.
        source (str): The file the slice was loaded from (for reports).
    """

    def __init__(self, content: Dict, slice_type: str, source: str = "") -> None:
        self.content = content
        self.slice_type = slice_type
        self.source = source

    def to_dict(self) -> Dict:
        """
        Compute the statistics document for the slice.

        Returns:
            A JSON-serialisable dict with a ``slice_type`` key and per-type
            detail sections.
        """
        summary: Dict = {"slice_type": self.slice_type}
        if self.slice_type == "usages":
            summary.update(self._usages_stats())
        elif self.slice_type == "reachables":
            summary.update(self._reachables_stats(self.content.get("reachables", [])))
        elif self.slice_type == "data-flow":
            summary.update(self._dataflow_stats())
        elif self.slice_type == "parsedeps":
            summary.update(self._parsedeps_stats())
        else:
            summary.update(self._generic_stats())
        # Present only on engine (dosai/golem/rusi/kosi) compat documents; atom
        # slices carry no such key, so their output is unchanged. Reporting a
        # count from a run the engine cut short, without saying so, overstates
        # what the evidence covers.
        provenance = self.content.get("analysisProvenance")
        if isinstance(provenance, dict) and provenance:
            summary["analysis"] = provenance
        return summary

    def _usages_stats(self) -> Dict:
        object_slices = self.content.get("objectSlices", [])
        types = self.content.get("userDefinedTypes", [])
        files = Counter()
        usages = 0
        external_calls = 0
        internal_calls = 0
        procedures = 0
        for method in object_slices:
            if method.get("fileName"):
                files[method["fileName"]] += 1
            method_usages = method.get("usages") or []
            usages += len(method_usages)
            for usage in method_usages:
                for call in usage.get("invokedCalls", []) + usage.get("argToCalls", []):
                    if call.get("isExternal"):
                        external_calls += 1
                    else:
                        internal_calls += 1
        for defined in types:
            procedures += len(defined.get("procedures", []) or [])
        return {
            "object_slices": len(object_slices),
            "user_defined_types": len(types),
            "usages": usages,
            "procedures": procedures,
            "calls": {"external": external_calls, "internal": internal_calls},
            "top_files": _top(files),
        }

    def _reachables_stats(self, entries: List[Dict]) -> Dict:
        flow_groups = len(entries)
        nodes = 0
        files = Counter()
        tags = Counter()
        purls = set()
        sources = 0
        sinks = 0
        for entry in entries:
            flows = entry.get("flows") or []
            nodes += len(flows)
            purls.update(p for p in entry.get("purls") or [] if isinstance(p, str))
            if not flows:
                continue
            for tag in split_tags(flows[0].get("tags")):
                if tag.startswith("pkg:"):
                    continue
                tags[tag] += 1
                if tag in SOURCE_TAGS:
                    sources += 1
                    break
            sink_tags = [t for t in split_tags(flows[-1].get("tags")) if not t.startswith("pkg:")]
            if any(t in SINK_TAGS for t in sink_tags):
                sinks += 1
            for tag in sink_tags:
                tags[tag] += 1
            for node in flows:
                if node.get("parentFileName"):
                    files[node["parentFileName"]] += 1
        return {
            "flow_groups": flow_groups,
            "flow_nodes": nodes,
            "sources": sources,
            "sinks": sinks,
            "unique_files": len(files),
            "top_files": _top(files),
            "purls": {"count": len(purls), "list": sorted(purls)},
            "tags": _top(tags),
        }

    def _dataflow_stats(self) -> Dict:
        graph = self.content.get("graph", {})
        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])
        edge_labels = Counter(e.get("label", "unknown") for e in edges)
        return {
            "nodes": len(nodes),
            "edges": len(edges),
            "paths": len(self.content.get("paths", [])),
            "edge_labels": _top(edge_labels),
        }

    def _parsedeps_stats(self) -> Dict:
        modules = self.content.get("modules", [])
        symbols = sum(len(m.get("importedSymbols", []) or []) for m in modules)
        return {
            "modules": len(modules),
            "imported_symbols": symbols,
            "top_modules": _top(Counter(m.get("name", "?") for m in modules)),
        }

    def _generic_stats(self) -> Dict:
        return {
            "top_level_keys": sorted(self.content.keys()),
            "entries": sum(len(v) for v in self.content.values() if isinstance(v, list)),
        }

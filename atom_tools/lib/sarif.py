"""
Conversion of atom reachable slices to SARIF 2.1.0.

Every reachable flow group becomes a SARIF result: the terminal (sink) node is
the primary location, the whole flow is preserved as a code flow thread, and
the atom tag vocabulary (sql, ssrf, pii, tracker, ...) drives the rule id and
level. The output loads into SARIF consumers such as GitHub code scanning, VS
Code SARIF explorer and anything that already ingests dep-scan / blint
reports.
"""

import hashlib
import logging
from typing import Dict, List, Optional, Tuple

from atom_tools import __version__
from atom_tools.lib.reachables import load_reachables
from atom_tools.lib.taxonomy import HIGH_RISK_SINKS, RULE_TAGS

logger = logging.getLogger(__name__)

SARIF_SCHEMA = "https://docs.oasis-open.org/sarif/sarif/v2.1.0/errata01/os/schemas/sarif-schema-2.1.0.json"

# The sink/severity vocabulary above now lives in atom_tools.lib.taxonomy so
# the engine adapters derive levels from the exact same sets; the names are
# re-exported here for existing callers.


def normalise_path(filename: str) -> str:
    """Normalise slice file names into SARIF artifact URIs."""
    return (filename or "").replace("\\", "/")


def node_tags(node: Dict) -> List[str]:
    """Split a node's comma separated tag string, dropping purl tags."""
    tags = node.get("tags") or ""
    if isinstance(tags, list):
        parts = [str(t) for t in tags]
    else:
        parts = tags.split(",")
    return [t.strip() for t in parts if t.strip() and not t.strip().startswith("pkg:") and t.strip() != "framework"]


def rule_for(tags: List[str]) -> Tuple[str, str]:
    """
    Derive a rule id and level from the tags carried by a flow.

    High risk sink tags (sql, ssrf, ...) produce an error; any other
    recognised tag (framework-input, pii, tracker, ...) a warning. Callers
    should pass the merged tags of the source and sink nodes: atom often tags
    only the source end of a flow (framework-input, pii-*) while dangerous
    sinks carry their own tags, so looking at one end alone misses rules.

    Args:
        tags: Normalised tags collected from a flow's source and sink nodes.

    Returns:
        A ``(rule_id, level)`` tuple. rule_id is ``atom:<tag>`` for the first
        recognised tag, else ``atom:reachable-flow``; level is one of the SARIF
        levels error, warning or note.
    """
    for tag in tags:
        if tag in HIGH_RISK_SINKS:
            return f"atom:{tag}", "error"
    for tag in tags:
        if tag in RULE_TAGS:
            return f"atom:{tag}", "warning"
    return "atom:reachable-flow", "note"


def node_location(node: Dict) -> Optional[Dict]:
    """
    Build a SARIF physical location for a slice node.

    Args:
        node: A SliceNode dict from a reachable flow.

    Returns:
        A physicalLocation dict, or None when the node has no file.
    """
    filename = node.get("parentFileName") or node.get("fileName")
    if not filename:
        return None
    location = {
        "artifactLocation": {"uri": normalise_path(filename)},
    }
    line = node.get("lineNumber")
    if isinstance(line, int) and line >= 0:
        location["region"] = {"startLine": line}
        code = node.get("code")
        if code:
            location["region"]["snippet"] = {"text": str(code)[:512]}
    return location


def flow_fingerprint(entry: Dict) -> str:
    """
    Build a stable GitHub-friendly fingerprint for a flow group.

    Includes the code snippet, column number and the entry's purls as well as
    file, line and name: flows that only differ by CPG node ids are duplicates
    (GitHub should merge those alerts), while flows sharing a location but
    reaching different packages must stay distinct.
    """
    parts = []
    for node in entry.get("flows", []):
        parts.append(
            f"{node.get('parentFileName')}:{node.get('lineNumber')}:"
            f"{node.get('columnNumber')}:{node.get('name')}:{node.get('code')}"
        )
    parts.extend(sorted(p for p in entry.get("purls") or [] if isinstance(p, str)))
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]
    return f"{digest}"


class Sarif:
    """
    Converts a reachable slice into a SARIF 2.1.0 document.

    Args:
        input_slice (str): The reachable slice file, glob pattern, or comma
            separated list. Sibling chunks are picked up automatically.
        origin_type (str): The originating language, recorded in the tool
            metadata.

    Attributes:
        entries (list): The reachable flow groups.
    """

    def __init__(self, input_slice: str, origin_type: str | None = None) -> None:
        self.origin_type = origin_type
        self.entries = load_reachables(input_slice).get("reachables", [])

    def convert(self) -> Dict:
        """
        Convert the reachable slice into a SARIF document.

        Returns:
            A SARIF 2.1.0 dict with a single run; empty (no results) when the
            slice had no flows.
        """
        results = []
        rules: Dict[str, Dict] = {}
        for entry in self.entries:
            flows = entry.get("flows") or []
            if not flows:
                continue
            sink = flows[-1]
            source = flows[0]
            # Merge both ends: atom tags sources (framework-input, pii-*) and
            # sinks (sql, ssrf, ...) separately, and either end alone would
            # leave most flows without a rule on real data.
            flow_tags = list(dict.fromkeys(node_tags(source) + node_tags(sink)))
            rule_id, level = rule_for(flow_tags)
            # Engine-normalised entries (from the adapters) carry the engine's
            # own severity; use it over the tag-derived level and record where
            # it came from. atom's own entries have neither key, so behaviour
            # on atom slices is unchanged.
            engine_level = entry.get("severity")
            severity_source = entry.get("severitySource")
            if engine_level in ("error", "warning", "note"):
                level = engine_level
            purls = sorted(p for p in entry.get("purls") or [] if isinstance(p, str))
            if rule_id not in rules:
                rules[rule_id] = self._rule(rule_id)
            message = (
                f"Data flows from '{source.get('name') or source.get('code', '?')}' "
                f"to '{sink.get('name') or sink.get('code', '?')}' over {len(flows)} steps"
            )
            if purls:
                message += f" via {', '.join(purls[:3])}"
            if entry.get("engine"):
                message += f" ({entry['engine']})"
            properties = {
                "tags": sorted(flow_tags),
                "purls": purls,
            }
            if severity_source:
                properties["severitySource"] = severity_source
            if entry.get("pathTruncated"):
                # Witness honesty: this path is a truncated/representative
                # witness, never "the" path.
                properties["pathTruncated"] = True
            result = {
                "ruleId": rule_id,
                "level": level,
                "message": {"text": message},
                "partialFingerprints": {"atomToolsFlow/v1": flow_fingerprint(entry)},
                "properties": properties,
            }
            if location := node_location(sink):
                result["locations"] = [{"physicalLocation": location}]
            code_flow = self._code_flow(flows)
            if code_flow:
                result["codeFlows"] = [code_flow]
            results.append(result)
        return {
            "$schema": SARIF_SCHEMA,
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "name": "atom-tools",
                            "version": __version__,
                            "informationUri": "https://github.com/AppThreat/atom-tools",
                            "rules": list(rules.values()),
                        }
                    },
                    "results": results,
                }
            ],
        }

    @staticmethod
    def _rule(rule_id: str) -> Dict:
        """Build a minimal rule descriptor for a derived rule id."""
        return {
            "id": rule_id,
            "shortDescription": {
                "text": f"Reachable data flow ({rule_id.removeprefix('atom:')})"
            },
            "properties": {"tags": ["security", "reachability"]},
        }

    @staticmethod
    def _code_flow(flows: List[Dict]) -> Optional[Dict]:
        """Build a SARIF codeFlow tracing the whole source to sink path."""
        locations = []
        for node in flows:
            location = node_location(node)
            if not location:
                continue
            step = {
                "location": {
                    "physicalLocation": location,
                    "message": {
                        "text": node.get("code") or node.get("name") or node.get("label", "")
                    },
                },
            }
            tags = node_tags(node)
            if tags:
                step["location"]["message"]["text"] += f" [tags: {', '.join(tags[:4])}]"
            locations.append(step)
        if not locations:
            return None
        return {"threadFlows": [{"locations": locations}]}

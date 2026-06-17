"""
Pipeline helpers for Android apk analysis.

This module discovers Android application files, drives blint (for SBOM
generation) and atom (for usage and reachable slices) as external commands, and
loads the resulting reports for presentation.
"""

import json
import logging
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Recognized Android application files.
APP_EXTENSIONS = (".apk", ".apkm", ".apks", ".xapk", ".aab")

# Permissions that are commonly considered sensitive. Used to highlight
# dangerous permissions during presentation.
DANGEROUS_PERMISSIONS = {
    "ACCESS_BACKGROUND_LOCATION",
    "ACCESS_COARSE_LOCATION",
    "ACCESS_FINE_LOCATION",
    "BODY_SENSORS",
    "CAMERA",
    "READ_CALENDAR",
    "READ_CALL_LOG",
    "READ_CONTACTS",
    "READ_EXTERNAL_STORAGE",
    "READ_PHONE_NUMBERS",
    "READ_PHONE_STATE",
    "READ_SMS",
    "RECEIVE_SMS",
    "RECORD_AUDIO",
    "SEND_SMS",
    "WRITE_CONTACTS",
    "WRITE_EXTERNAL_STORAGE",
}

# Tag prefixes emitted by atom's android-specific tagging passes, grouped into
# the categories analysts care about. These mirror the tags produced by the
# PII, tracker and Android-services passes:
#   - PII pass: fine-grained ``pii-*``/``pci-*``/``phi-*``/``finance-*`` category
#     tags, the ``sensitive-data`` umbrella, the compliance tags ``gdpr``/``ccpa``/
#     ``hipaa``/``pci-dss``, plus ``pii`` and ``secret``/``secret-*``.
#   - Tracker pass: ``tracker``/``tracker-*`` and ``adware`` for third-party SDKs.
#   - Android-services pass: ``service-egress``/``service-ingress``/
#     ``on-device-ai`` umbrella tags plus a ``service-<category>`` tag per service
#     category (cloud, storage, ai-llm, ai-local, analytics, monitoring, location,
#     messaging, social, payment, http).
TAG_CATEGORIES = {
    "PII / Sensitive data": (
        "pii",
        "pci",
        "phi",
        "finance",
        "sensitive-data",
        "gdpr",
        "ccpa",
        "hipaa",
    ),
    "Secrets / Credentials": ("secret",),
    "Trackers / Adware": ("tracker", "adware"),
    "Cloud LLM services": ("service-ai-llm",),
    "On-device AI": ("on-device-ai", "service-ai-local"),
    "Cloud / Storage": ("service-cloud", "service-storage"),
    "Analytics / Monitoring": ("service-analytics", "service-monitoring"),
    "Location": ("service-location",),
    "Messaging / Social": ("service-messaging", "service-social"),
    "Payment": ("service-payment",),
    "Generic HTTP egress": ("service-http",),
    "Data egress (sinks)": ("service-egress",),
    "Remote content (sources)": ("service-ingress",),
}


@dataclass
class AppAnalysis:
    """Holds the outcome of analysing a single application file."""

    app_file: str
    bom_file: Optional[str] = None
    usages_file: Optional[str] = None
    reachables_file: Optional[str] = None
    callgraph_file: Optional[str] = None
    errors: List[str] = field(default_factory=list)


def find_apps(input_path: str) -> List[str]:
    """
    Discover Android application files under the given path.

    Args:
        input_path: A file or directory to search.

    Returns:
        A sorted list of application file paths.
    """
    if os.path.isfile(input_path):
        return [input_path] if input_path.endswith(APP_EXTENSIONS) else []
    results = []
    for root, _, files in os.walk(input_path):
        for name in files:
            if name.endswith(APP_EXTENSIONS):
                results.append(os.path.join(root, name))
    return sorted(results)


def resolve_tool(names: List[str]) -> Optional[str]:
    """
    Resolve the first available command from a list of candidate names.

    Args:
        names: Candidate command names.

    Returns:
        The resolved command name, or None when none are available.
    """
    for name in names:
        if shutil.which(name):
            return name
    return None


def resolve_blint(blint_venv: Optional[str] = None) -> Optional[str]:
    """
    Resolve the blint command, optionally from a dedicated virtual environment.

    blint is frequently installed in its own virtual environment (its native
    disassembly extras pin specific build tooling). When ``blint_venv`` points at
    such an environment - or directly at a blint executable - that takes
    precedence over whatever is on PATH.

    Args:
        blint_venv: A path to a blint virtualenv, its ``bin`` directory, or the
            blint executable itself. May be None.

    Returns:
        The resolved blint command, or None when unavailable.
    """
    if blint_venv:
        candidates = [
            blint_venv,
            os.path.join(blint_venv, "blint"),
            os.path.join(blint_venv, "bin", "blint"),
        ]
        for candidate in candidates:
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                return candidate
        logger.warning("No blint executable found under %s", blint_venv)
    env_venv = os.environ.get("BLINT_HOME")
    if env_venv and env_venv != blint_venv:
        return resolve_blint(env_venv)
    return resolve_tool(["blint"])


def check_prerequisites(
    skip_atom: bool, blint_venv: Optional[str] = None
) -> Dict[str, Optional[str]]:
    """
    Resolve the external tools required by the pipeline.

    Args:
        skip_atom: When True, atom is not required.
        blint_venv: Optional path to a blint virtual environment / executable.

    Returns:
        A mapping of tool name to its resolved command (or None when missing).
    """
    tools: Dict[str, Optional[str]] = {"blint": resolve_blint(blint_venv)}
    if not skip_atom:
        tools["atom"] = resolve_tool(["atom", "atom.sh"])
    return tools


def _report_path(reports_dir: str, app_file: str, suffix: str) -> str:
    """Build a report file path based on the application file name."""
    base = os.path.basename(app_file)
    return os.path.join(reports_dir, f"{base}.{suffix}")


def run_command(args: List[str]) -> subprocess.CompletedProcess:
    """
    Run an external command, capturing its output.

    Args:
        args: The command line arguments.

    Returns:
        The completed process.
    """
    logger.info("Executing: %s", " ".join(args))
    return subprocess.run(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=os.environ.copy(),
        encoding="utf-8",
        check=False,
    )


def run_blint_sbom(
    blint_cmd: str, app_file: str, reports_dir: str, deep: bool
) -> Optional[str]:
    """
    Generate a CycloneDX SBOM for an application using blint.

    A single invocation produces everything we need: deep mode embeds the dex
    behavioural findings as component properties in the BOM, and ``--disassembly``
    additionally emits the Dalvik callgraph sidecar. There is no need for a
    second blint run.

    Args:
        blint_cmd: The resolved blint command.
        app_file: The application file to analyse.
        reports_dir: The directory to write reports to.
        deep: Whether to enable blint deep mode (also turns on disassembly so the
            callgraph sidecar is produced).

    Returns:
        The path to the generated SBOM, or None on failure.
    """
    bom_file = _report_path(reports_dir, app_file, "bom.json")
    args = [blint_cmd, "sbom", "--src", app_file, "--output-file", bom_file]
    if deep:
        # Deep mode parses dex classes (needed for service / behaviour detection);
        # disassembly additionally emits the Dalvik callgraph sidecar.
        args.append("--deep")
        args.append("--disassembly")
    cp = run_command(args)
    if cp.returncode != 0 or not os.path.exists(bom_file):
        logger.warning("blint failed for %s: %s", app_file, (cp.stdout or "").strip())
        return None
    return bom_file


def dex_callgraph_path(bom_file: str, app_file: str) -> Optional[str]:
    """
    Return the Dalvik callgraph sidecar path blint writes next to a BOM.

    blint names it ``<bom-stem>-<app-basename>.dex-callgraph.json``. Returns the
    path when it exists, else None.
    """
    if not bom_file:
        return None
    stem = os.path.splitext(bom_file)[0]
    candidate = f"{stem}-{os.path.basename(app_file)}.dex-callgraph.json"
    return candidate if os.path.exists(candidate) else None


def run_atom_slices(
    atom_cmd: str, app_file: str, reports_dir: str
) -> Dict[str, Optional[str]]:
    """
    Generate usage and reachable slices for an application using atom.

    Args:
        atom_cmd: The resolved atom command.
        app_file: The application file to analyse.
        reports_dir: The directory to write reports to.

    Returns:
        A mapping with the ``usages`` and ``reachables`` slice paths.
    """
    atom_file = _report_path(reports_dir, app_file, "atom")
    usages_file = _report_path(reports_dir, app_file, "usages.json")
    reachables_file = _report_path(reports_dir, app_file, "reachables.json")
    result: Dict[str, Optional[str]] = {"usages": None, "reachables": None}
    # Build reachables first: it produces an atom that carries data dependencies
    # in addition to the AST. The usages slice only needs the AST, so it can then
    # reuse that richer atom rather than rebuilding the CPG from scratch.
    reachables_cp = run_command(
        [
            atom_cmd,
            "reachables",
            "-l",
            "apk",
            "-o",
            atom_file,
            "-s",
            reachables_file,
            app_file,
        ]
    )
    if reachables_cp.returncode == 0 and os.path.exists(reachables_file):
        result["reachables"] = reachables_file
    else:
        logger.warning(
            "atom reachables failed for %s: %s",
            app_file,
            (reachables_cp.stdout or "").strip(),
        )
    usages_cmd = [
        atom_cmd,
        "usages",
        "-l",
        "apk",
        "-o",
        atom_file,
        "-s",
        usages_file,
        app_file,
    ]
    # Only reuse the atom when reachables actually produced one.
    if result["reachables"] is not None and os.path.exists(atom_file):
        usages_cmd.append("--reuse-atom")
    usages_cp = run_command(usages_cmd)
    if usages_cp.returncode == 0 and os.path.exists(usages_file):
        result["usages"] = usages_file
    else:
        logger.warning(
            "atom usages failed for %s: %s", app_file, (usages_cp.stdout or "").strip()
        )
    return result


def analyze_app(
    app_file: str,
    reports_dir: str,
    tools: Dict[str, Optional[str]],
    deep: bool,
    skip_atom: bool,
) -> AppAnalysis:
    """
    Run the full analysis pipeline for a single application.

    Args:
        app_file: The application file to analyse.
        reports_dir: The directory to write reports to.
        tools: The resolved tool commands.
        deep: Whether to enable blint deep mode.
        skip_atom: When True, the atom slicing step is skipped.

    Returns:
        An AppAnalysis describing the produced reports.
    """
    analysis = AppAnalysis(app_file=app_file)
    if blint_cmd := tools.get("blint"):
        analysis.bom_file = run_blint_sbom(blint_cmd, app_file, reports_dir, deep)
        if not analysis.bom_file:
            analysis.errors.append("SBOM generation failed.")
        elif deep:
            analysis.callgraph_file = dex_callgraph_path(analysis.bom_file, app_file)
    if not skip_atom and (atom_cmd := tools.get("atom")):
        slices = run_atom_slices(atom_cmd, app_file, reports_dir)
        analysis.usages_file = slices["usages"]
        analysis.reachables_file = slices["reachables"]
        if not analysis.reachables_file:
            analysis.errors.append("Reachable slicing failed.")
    return analysis


def load_json(path: Optional[str]) -> Optional[dict]:
    """
    Load a JSON file, returning None when unavailable or invalid.

    Args:
        path: The file path. May be None.

    Returns:
        The parsed JSON, or None.
    """
    if not path or not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (ValueError, OSError) as e:
        logger.debug("Unable to read %s: %s", path, e)
        return None


def summarize_bom(bom: Optional[dict]) -> dict:
    """
    Extract a presentation-friendly summary from a CycloneDX SBOM.

    Args:
        bom: The parsed SBOM document.

    Returns:
        A dict with application metadata, permissions and component details.
    """
    summary = {
        "name": "",
        "version": "",
        "properties": {},
        "permissions": [],
        "features": [],
        "components": [],
    }
    if not bom:
        return summary
    parent = _parent_component(bom)
    if parent:
        summary["name"] = parent.get("name", "")
        summary["version"] = parent.get("version", "")
        for prop in parent.get("properties", []):
            name = prop.get("name", "")
            value = prop.get("value", "")
            if name == "internal.appPermissions":
                summary["permissions"] = [p for p in value.split("\n") if p]
            elif name == "internal.appFeatures":
                summary["features"] = [f for f in value.split("\n") if f]
            else:
                summary["properties"][name] = value
    summary["components"] = [
        {
            "name": c.get("name", ""),
            "version": c.get("version", ""),
            "purl": c.get("purl", ""),
            "type": c.get("type", ""),
        }
        for c in bom.get("components", [])
    ]
    return summary


def collect_behaviours(bom: Optional[dict]) -> list:
    """
    Extract Dalvik behavioural findings recorded by blint from the SBOM.

    blint's deep-mode dex review attaches behavioural findings to each dex
    component as ``internal:behaviour:<ID>`` properties whose value is
    ``<severity>|<count>|<sample evidence>``. This aggregates them across all
    components into a single sorted list for presentation, summing counts for
    the same rule id across dex files.

    Args:
        bom: The parsed SBOM document.

    Returns:
        A list of dicts ``{id, severity, count, evidence}`` sorted by severity
        then count, highest first.
    """
    if not bom:
        return []
    severity_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    aggregated: Dict[str, dict] = {}
    for component in bom.get("components", []):
        for prop in component.get("properties", []):
            name = prop.get("name", "")
            if not name.startswith("internal:behaviour:"):
                continue
            rule_id = name.split("internal:behaviour:", 1)[1]
            parts = (prop.get("value", "") or "").split("|", 2)
            severity = parts[0] if parts else "info"
            try:
                count = int(parts[1]) if len(parts) > 1 else 0
            except ValueError:
                count = 0
            evidence = parts[2] if len(parts) > 2 else ""
            entry = aggregated.get(rule_id)
            if entry is None:
                aggregated[rule_id] = {
                    "id": rule_id,
                    "severity": severity,
                    "count": count,
                    "evidence": evidence,
                }
            else:
                entry["count"] += count
                if not entry["evidence"]:
                    entry["evidence"] = evidence
    return sorted(
        aggregated.values(),
        key=lambda x: (severity_rank.get(x["severity"], 5), -x["count"]),
    )


def _parent_component(bom: dict) -> Optional[dict]:
    """Return the parent application component from a CycloneDX SBOM."""
    metadata = bom.get("metadata", {})
    component = metadata.get("component", {})
    nested = component.get("components", [])
    if nested:
        return nested[0]
    return component or None


def is_dangerous_permission(permission: str) -> bool:
    """
    Check whether a permission is in the dangerous permission set.

    Args:
        permission: A fully-qualified android permission name.

    Returns:
        True when the permission is considered dangerous.
    """
    return permission.rsplit(".", 1)[-1] in DANGEROUS_PERMISSIONS


def collect_tags(node, found: Dict[str, int]) -> None:
    """
    Recursively collect atom tags from an arbitrary reachables structure.

    Tags are emitted by atom in a variety of shapes (a delimited string, a
    list, or nested objects). This walks the structure and counts every tag.

    Args:
        node: The current node (dict, list or scalar).
        found: An accumulator mapping tag to occurrence count.
    """
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "tags":
                for tag in _normalize_tags(value):
                    found[tag] = found.get(tag, 0) + 1
            else:
                collect_tags(value, found)
    elif isinstance(node, list):
        for item in node:
            collect_tags(item, found)


def _normalize_tags(value) -> List[str]:
    """Normalize a tags value into a list of individual tag strings."""
    tags: List[str] = []
    if isinstance(value, str):
        for part in value.replace(",", "|").split("|"):
            if part.strip():
                tags.append(part.strip())
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, str) and item.strip():
                tags.append(item.strip())
            elif isinstance(item, dict) and item.get("name"):
                tags.append(str(item["name"]).strip())
    return tags


# Umbrella tags that describe the direction of a service data flow.
SERVICE_EGRESS = "service-egress"
SERVICE_INGRESS = "service-ingress"
ON_DEVICE_AI = "on-device-ai"


def _iter_tag_groups(node):
    """
    Yield the tag list of every node that carries a ``tags`` key.

    Vendor tags (``service:<Name>``, ``tracker:<Name>``) and their category /
    direction tags are emitted together on the same node, so grouping by node
    preserves the association between a vendor and the data it touches.

    Args:
        node: The current node (dict, list or scalar).

    Yields:
        Lists of normalized tag strings.
    """
    if isinstance(node, dict):
        if "tags" in node:
            yield _normalize_tags(node["tags"])
        for key, value in node.items():
            if key != "tags":
                yield from _iter_tag_groups(value)
    elif isinstance(node, list):
        for item in node:
            yield from _iter_tag_groups(item)


def collect_attribution(reachables: Optional[dict]):
    """
    Attribute reachable flows to the concrete services and trackers involved.

    Args:
        reachables: The parsed reachables slice (list or dict).

    Returns:
        A tuple ``(services, trackers)``. Each maps a vendor name to a dict with
        the co-occurring ``categories`` (set), reachable ``flows`` count and, for
        services, the observed data-flow direction flags (``egress``, ``ingress``,
        ``local``).
    """
    services: Dict[str, dict] = {}
    trackers: Dict[str, dict] = {}
    if reachables is None:
        return services, trackers
    for tags in _iter_tag_groups(reachables):
        if not tags:
            continue
        tagset = set(tags)
        service_cats = sorted(
            t[len("service-") :]
            for t in tagset
            if t.startswith("service-") and t not in (SERVICE_EGRESS, SERVICE_INGRESS)
        )
        tracker_cats = sorted(
            t[len("tracker-") :] for t in tagset if t.startswith("tracker-")
        )
        for tag in tags:
            if tag.startswith("service:"):
                name = tag.split(":", 1)[1]
                entry = services.setdefault(
                    name,
                    {
                        "categories": set(),
                        "flows": 0,
                        "egress": False,
                        "ingress": False,
                        "local": False,
                    },
                )
                entry["flows"] += 1
                entry["categories"].update(service_cats)
                entry["egress"] = entry["egress"] or SERVICE_EGRESS in tagset
                entry["ingress"] = entry["ingress"] or SERVICE_INGRESS in tagset
                entry["local"] = entry["local"] or ON_DEVICE_AI in tagset
            elif tag.startswith("tracker:"):
                name = tag.split(":", 1)[1]
                entry = trackers.setdefault(name, {"categories": set(), "flows": 0})
                entry["flows"] += 1
                entry["categories"].update(tracker_cats)
    return services, trackers


def build_cyclonedx_services(services: Dict[str, dict]) -> List[dict]:
    """
    Convert detected services into CycloneDX ``service`` objects.

    The data-flow direction is expressed relative to the service, per the
    CycloneDX specification: data leaving the device for a remote service enters
    that service (``inbound``); remote content fetched onto the device leaves the
    service (``outbound``); on-device AI runtimes stay within the trust boundary.

    Args:
        services: The service attribution produced by ``collect_attribution``.

    Returns:
        A list of CycloneDX service objects, sorted by name.
    """
    result: List[dict] = []
    for name in sorted(services):
        info = services[name]
        categories = sorted(info["categories"])
        if info["egress"] and info["ingress"]:
            flow = "bi-directional"
        elif info["ingress"]:
            flow = "outbound"
        elif info["egress"] or info["local"]:
            flow = "inbound"
        else:
            flow = "unknown"
        classifications = categories or ["unknown"]
        service = {
            "bom-ref": f"service:{name}",
            "name": name,
            "x-trust-boundary": not info["local"],
            "data": [{"flow": flow, "classification": c} for c in classifications],
            "properties": [
                {"name": "internal:reachableFlows", "value": str(info["flows"])},
            ],
        }
        if categories:
            service["group"] = categories[0]
        if info["local"]:
            service["properties"].append(
                {"name": "internal:onDeviceAi", "value": "true"}
            )
        result.append(service)
    return result


def enrich_bom_with_services(
    bom: Optional[dict], services: List[dict]
) -> Optional[dict]:
    """
    Merge detected CycloneDX services into a SBOM document.

    Existing services with a matching ``bom-ref`` are replaced so the function is
    idempotent when run against an already-enriched BOM.

    Args:
        bom: The parsed SBOM document.
        services: CycloneDX service objects from ``build_cyclonedx_services``.

    Returns:
        The updated SBOM document, or None when no BOM was provided.
    """
    if bom is None:
        return None
    if not services:
        return bom
    existing = {
        s.get("bom-ref"): s for s in bom.get("services", []) if s.get("bom-ref")
    }
    for service in services:
        existing[service["bom-ref"]] = service
    unkeyed = [s for s in bom.get("services", []) if not s.get("bom-ref")]
    bom["services"] = unkeyed + list(existing.values())
    return bom


def categorize_tags(reachables: Optional[dict]) -> Dict[str, Dict[str, int]]:
    """
    Group reachable-slice tags into analyst-friendly categories.

    Args:
        reachables: The parsed reachables slice (list or dict).

    Returns:
        A mapping of category name to a mapping of tag to count. Only
        non-empty categories are returned.
    """
    found: Dict[str, int] = {}
    if reachables is not None:
        collect_tags(reachables, found)
    categorized: Dict[str, Dict[str, int]] = {}
    for category, prefixes in TAG_CATEGORIES.items():
        matches = {
            tag: count for tag, count in found.items() if tag.startswith(prefixes)
        }
        if matches:
            categorized[category] = dict(sorted(matches.items()))
    return categorized

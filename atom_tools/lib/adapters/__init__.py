"""Engine adapters: the only modules that know a vendor schema.

Each adapter exposes ``detect(content)``, ``parse(content, source_file)``
(returning a :class:`~atom_tools.lib.unified.UnifiedReport`) and an
``ENGINE`` name. ``detect_engine``/``normalize_engine_report`` here are the
entry points the rest of atom-tools uses; nothing outside this package
touches a vendor field name (PLAN.md's layering rule, mirroring cdxgen).
"""

import logging
from importlib import import_module
from typing import Dict, List, Optional

from atom_tools.lib.unified import (
    UnifiedReport,
    detect as detect_unified,
    merge_reports,
    to_reachables_document,
)

logger = logging.getLogger(__name__)

# Lazily imported so `import atom_tools.lib.slices` stays cheap. "unified"
# points at the loader for our own document, not a vendor schema; it lives in
# unified.py next to the writer it round-trips.
ENGINE_MODULES = {
    "dosai": "atom_tools.lib.adapters.dosai",
    "golem": "atom_tools.lib.adapters.golem",
    "rusi": "atom_tools.lib.adapters.rusi",
    "kosi": "atom_tools.lib.adapters.kosi",
    "atom": "atom_tools.lib.adapters.atom",
    "unified": "atom_tools.lib.unified",
}


def _module(engine: str):
    return import_module(ENGINE_MODULES[engine])


def detect_engine(content) -> Optional[str]:
    """
    Identify the engine that produced a parsed report document.

    Returns the engine name, or None for atom slices and unknown documents
    (those keep flowing through the existing slice detection). golem/rusi
    reports are only claimed when they carry a flow or endpoint section so
    endpoint-only extracts keep their historical handling. Unified documents
    (``ingest --emit unified`` output) are detected by their own signature and
    reload through :func:`atom_tools.lib.unified.from_dict`, so every command
    that takes a report also accepts a unified one.
    """
    if not isinstance(content, dict):
        return None
    if detect_unified(content):
        return "unified"
    metadata = content.get("Metadata")
    if isinstance(metadata, dict) and metadata.get("Tool") == "Dosai":
        return "dosai"
    tool = content.get("tool")
    if isinstance(tool, dict):
        name = tool.get("name")
        if name == "golem" and ("dataFlow" in content or "apiEndpoints" in content):
            return "golem"
        if name == "rusi" and ("data_flow" in content or "api_endpoints" in content):
            return "rusi"
        if name == "kosi" and ("dataFlow" in content or "apiEndpoints" in content):
            return "kosi"
    return None


def parse_report(content, source_file: str = "", engine: Optional[str] = None) -> UnifiedReport:
    """
    Parse one engine report (or atom reachables document) into a unified report.

    Args:
        content: The parsed JSON document.
        source_file: Path the document was loaded from (provenance).
        engine: Force an engine instead of detection (the ingest command's
            ``--engine`` escape hatch).

    Raises:
        ValueError: When no engine is detected and none was forced, or the
            forced engine cannot parse the document.
    """
    detected = engine or detect_engine(content)
    if detected is None:
        if isinstance(content, list) or (isinstance(content, dict) and "reachables" in content):
            detected = "atom"
        else:
            raise ValueError(
                "Could not detect the producing engine and none was forced with --engine."
            )
    report = _module(detected).parse(content, source_file=source_file)
    report.source_file = source_file
    return report


def normalize_engine_report(content, source_file: str = "") -> Optional[Dict]:
    """
    Convert a non-atom engine report into the atom reachables shape.

    Returns None for anything that is not a recognised engine report (atom
    slices and unknown documents keep their existing handling); otherwise a
    ``{"reachables": [...]}`` document whose entries carry the unified flow
    data plus the engine's own endpoint arrays under their original keys.
    """
    engine = detect_engine(content)
    if engine is None:
        return None
    report = parse_report(content, source_file=source_file, engine=engine)
    return to_reachables_document(report, original=content)


def ingest_inputs(files: List[str]) -> UnifiedReport:
    """
    Load and unify one or more report files (any engine, mixed freely).

    Flows, endpoints and packages are concatenated; each input's provenance is
    kept in ``provenance.sources``.
    """
    import json

    reports = []
    for path in files:
        with open(path, encoding="utf-8") as f:
            content = json.load(f)
        reports.append(parse_report(content, source_file=path))
    return merge_reports(reports)

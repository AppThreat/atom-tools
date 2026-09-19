"""
Source analysis pipeline.

Drives the atom CLI for any supported language, then post-processes the
artefacts with atom-tools itself: chunked reachables are merged, slice stats
are computed, OpenAPI endpoints are extracted from the usages slice and the
reachables are exported to SARIF. This is the same pattern the apk-analysis
command uses for Android apps, generalised to every language atom supports.
"""

import logging
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from atom_tools.lib.apk_pipeline import resolve_tool, run_command
from atom_tools.lib.reachables import load_reachables, sibling_chunks
from atom_tools.lib.utils import export_json

logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    """Holds the outcome of analysing a source tree."""

    input_path: str
    language: str
    atom_file: Optional[str] = None
    usages_file: Optional[str] = None
    reachables_file: Optional[str] = None
    openapi_file: Optional[str] = None
    sarif_file: Optional[str] = None
    stats_file: Optional[str] = None
    stats: Dict = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)


def run_atom_slices(
    atom_cmd: str,
    src: str,
    language: str,
    reports_dir: str,
    name: Optional[str] = None,
    skip_usages: bool = False,
) -> Dict[str, Optional[str]]:
    """
    Generate usage and reachable slices for a source tree using atom.

    Reachables are built first: they produce an atom that carries data
    dependencies in addition to the AST, so the usages slice can reuse that
    richer atom instead of rebuilding the CPG from scratch.

    Args:
        atom_cmd: The resolved atom command.
        src: The source file or directory to analyse.
        language: The atom language code (java, python, jssrc, c, ruby, ...).
        reports_dir: The directory to write reports to.
        name: Base name for the report files; defaults to the src basename.
        skip_usages: Skip the usages slice when only reachables are needed.

    Returns:
        A mapping with the ``usages`` and ``reachables`` slice paths (None when
        a step failed).
    """
    base = name or os.path.basename(os.path.abspath(src))
    atom_file = os.path.join(reports_dir, f"{base}.atom")
    usages_file = os.path.join(reports_dir, f"{base}.usages.json")
    reachables_file = os.path.join(reports_dir, f"{base}.reachables.json")
    result: Dict[str, Optional[str]] = {"usages": None, "reachables": None}
    reachables_cp = run_command(
        [
            atom_cmd,
            "reachables",
            "-l",
            language,
            "-o",
            atom_file,
            "-s",
            reachables_file,
            src,
        ]
    )
    if reachables_cp.returncode == 0 and os.path.exists(reachables_file):
        result["reachables"] = reachables_file
    else:
        logger.warning(
            "atom reachables failed for %s: %s", src, (reachables_cp.stdout or "").strip()
        )
    if skip_usages:
        return result
    usages_cmd = [
        atom_cmd,
        "usages",
        "-l",
        language,
        "-o",
        atom_file,
        "-s",
        usages_file,
        src,
    ]
    # Only reuse the atom when reachables actually produced one.
    if result["reachables"] is not None and os.path.exists(atom_file):
        usages_cmd.append("--reuse-atom")
    usages_cp = run_command(usages_cmd)
    if usages_cp.returncode == 0 and os.path.exists(usages_file):
        result["usages"] = usages_file
    else:
        logger.warning("atom usages failed for %s: %s", src, (usages_cp.stdout or "").strip())
    return result


def merge_chunked_reachables(reachables_file: str) -> Optional[str]:
    """
    Merge atom's chunked reachables output next to the first slice file.

    Args:
        reachables_file: The path of the first reachable slice file.

    Returns:
        The path of the merged document, or None when there were no sibling
        chunks to merge (the original file is already complete).
    """
    chunks = sibling_chunks(reachables_file)
    if not chunks:
        return None
    merged_file = f"{os.path.splitext(reachables_file)[0]}.merged.json"
    export_json(load_reachables(reachables_file), merged_file)
    logger.info("Merged %d chunk file(s) into %s.", len(chunks), merged_file)
    return merged_file


def _write_stats(result: AnalysisResult, reachables_file: Optional[str]) -> None:
    """Compute and persist slice stats for the reachables slice."""
    if not reachables_file:
        return
    from atom_tools.lib.slices import AtomSlice
    from atom_tools.lib.stats import SliceStats

    atom_slice = AtomSlice(reachables_file)
    stats = SliceStats(atom_slice.content, atom_slice.slice_type, reachables_file).to_dict()
    result.stats = stats
    result.stats_file = f"{os.path.splitext(reachables_file)[0]}.stats.json"
    export_json(stats, result.stats_file, 4)


def _write_openapi(result: AnalysisResult, usages_file: Optional[str], language: str) -> None:
    """Extract API endpoints from the usages slice into an OpenAPI document."""
    if not usages_file:
        return
    from atom_tools.lib.converter import OpenAPI

    converter = OpenAPI("openapi3.1.0", language, usages_file, None)
    document = converter.endpoints_to_openapi(None)
    if not document:
        logger.warning("No endpoints extracted from %s.", usages_file)
        return
    result.openapi_file = f"{os.path.splitext(usages_file)[0]}.openapi.json"
    export_json(document, result.openapi_file, 4)
    logger.info("OpenAPI document written to %s.", result.openapi_file)


def _write_sarif(result: AnalysisResult, reachables_file: Optional[str], language: str) -> None:
    """Export the reachables slice as a SARIF document."""
    if not reachables_file:
        return
    from atom_tools.lib.sarif import Sarif

    document = Sarif(reachables_file, language).convert()
    result.sarif_file = f"{os.path.splitext(reachables_file)[0]}.sarif.json"
    export_json(document, result.sarif_file, 4)
    logger.info("SARIF document written to %s.", result.sarif_file)


def analyze_source(
    input_path: str,
    language: str,
    reports_dir: str,
    atom_cmd: Optional[str] = None,
    extract_endpoints: bool = False,
    generate_sarif: bool = False,
    skip_usages: bool = False,
) -> AnalysisResult:
    """
    Run the full analysis pipeline for a source tree.

    Args:
        input_path: The source file or directory to analyse.
        language: The atom language code.
        reports_dir: The directory to write reports to.
        atom_cmd: An explicit atom command; resolved from PATH when None.
        extract_endpoints: Also extract an OpenAPI document from usages.
        generate_sarif: Also export the reachables to SARIF.
        skip_usages: Skip the usages slice when only reachables are needed.

    Returns:
        An AnalysisResult describing the produced reports.
    """
    result = AnalysisResult(input_path=input_path, language=language)
    resolved = atom_cmd or resolve_tool(["atom", "atom.sh"])
    if not resolved:
        result.errors.append(
            "atom command not found. Install it with npm install -g @appthreat/atom"
            " or use the atom-tools container image."
        )
        return result
    os.makedirs(reports_dir, exist_ok=True)
    base = os.path.basename(os.path.abspath(input_path))
    result.atom_file = os.path.join(reports_dir, f"{base}.atom")
    slices = run_atom_slices(resolved, input_path, language, reports_dir, base, skip_usages)
    result.usages_file = slices["usages"]
    result.reachables_file = slices["reachables"]
    if not result.reachables_file:
        result.errors.append("Reachable slicing failed.")
        return result
    merged = merge_chunked_reachables(result.reachables_file)
    if merged:
        result.reachables_file = merged
    _write_stats(result, result.reachables_file)
    if extract_endpoints:
        _write_openapi(result, result.usages_file, language)
    if generate_sarif:
        _write_sarif(result, result.reachables_file, language)
    return result

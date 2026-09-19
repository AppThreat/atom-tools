"""
Loading and merging of reachable slices.

atom writes reachable slices in chunks: ``reachables.json``, ``reachables_1.json``,
``reachables_2.json``, ... with 1000 flow groups per file, and each chunk is a
bare JSON array of ``ReachableFlows`` objects rather than the
``{"reachables": [...]}`` document older atom versions produced. The helpers
here understand both shapes, discover sibling chunks automatically, and merge
everything into a single document that the rest of atom-tools can consume.
"""

import glob
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from atom_tools.lib.adapters import normalize_engine_report

logger = logging.getLogger(__name__)

# reachables_1.json, reachables.slices_12.json, ...
CHUNK_PATTERN = re.compile(r"^(?P<base>.+?)_(?P<index>\d+)$")


def load_json_report(path: str, what: str = "report") -> Any:
    """
    json.load that names the file and its role when the read fails.

    Every command that loads an engine report goes through here, so a
    malformed or truncated download reports its own path and parse position
    (``could not read the report x.json: Expecting value: line 5 ...``)
    instead of a bare character offset into a file that is never named.

    Args:
        path: The file to open and parse.
        what: The role this document plays for the calling command
            ("baseline report", "algorithms document", ...), used verbatim
            in the error message.

    Returns:
        The parsed JSON value.

    Raises:
        ValueError: If the file is not valid UTF-8 JSON; the message names
            the file and carries the underlying parse error.
    """
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise ValueError(f"could not read the {what} {path}: {e}") from e


def parse_reachable_file(filename: str | Path) -> List[Dict]:
    """
    Parse a single reachable slice file.

    Supports both the wrapped ``{"reachables": [...]}`` document and the bare
    array format atom writes for chunked output.

    Args:
        filename: The path of the slice file.

    Returns:
        The list of ReachableFlows entries. Empty when the file cannot be read.
    """
    path = Path(filename)
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as e:
        logger.warning("Failed to load reachable slice %s: %s", path, e)
        return []
    if isinstance(content, list):
        return [entry for entry in content if isinstance(entry, dict)]
    if isinstance(content, dict):
        # Non-atom engine reports (dosai/golem/rusi/kosi) are normalised into
        # reachables entries through the adapters so consumers that load
        # flows directly (sarif, visualize) work on them unchanged. Engine
        # reports without flows (endpoint-only extracts) yield no entries,
        # exactly as before.
        engine_doc = normalize_engine_report(content, str(path))
        if engine_doc is not None:
            entries = engine_doc.get("reachables", [])
            return [entry for entry in entries if isinstance(entry, dict)]
        entries = content.get("reachables", [])
        return entries if isinstance(entries, list) else []
    return []


def sibling_chunks(filename: str | Path) -> List[str]:
    """
    Discover the sibling chunk files atom writes next to a reachable slice.

    For an input of ``reachables.json`` this returns ``reachables_1.json``,
    ``reachables_2.json``, ... in numeric order. The input file itself is not
    included.

    Args:
        filename: The path of the (first) slice file.

    Returns:
        Sorted list of chunk file paths that exist.
    """
    path = Path(filename)
    if path.suffix != ".json":
        return []
    base = str(path.with_suffix(""))
    candidates = glob.glob(f"{base}_*.json")
    chunked = []
    for candidate in candidates:
        match = CHUNK_PATTERN.search(Path(candidate).with_suffix("").name)
        if match and match.group("base") == path.with_suffix("").name:
            chunked.append(candidate)
    return sorted(
        chunked,
        key=lambda c: int(CHUNK_PATTERN.search(Path(c).with_suffix("").name).group("index")),
    )


def expand_inputs(pattern: str) -> List[str]:
    """
    Expand a comma separated list of files and glob patterns into file paths.

    Args:
        pattern: Comma separated files and/or glob patterns.

    Returns:
        A de-duplicated, order preserved list of existing file paths.
    """
    files: List[str] = []
    for part in pattern.split(","):
        part = part.strip()
        if not part:
            continue
        matches = sorted(glob.glob(part))
        if matches:
            files.extend(matches)
        elif Path(part).exists():
            files.append(part)
        else:
            logger.warning("No slice files found for input: %s", part)
    seen = set()
    unique = [f for f in files if not (f in seen or seen.add(f))]
    return unique


def flow_fingerprint(entry: Dict) -> Tuple:
    """
    Build a stable fingerprint identifying a ReachableFlows entry.

    Node ids are only unique within a single CPG, so file, line and code of each
    node are combined with the entry purls to survive merges across projects
    and languages.

    Args:
        entry: A ReachableFlows dict with ``flows`` and ``purls``.

    Returns:
        A hashable fingerprint.
    """
    nodes = []
    for node in entry.get("flows", []):
        nodes.append(
            (
                node.get("parentFileName", ""),
                node.get("lineNumber"),
                node.get("name", ""),
                node.get("code", ""),
            )
        )
    return (tuple(nodes), tuple(sorted(entry.get("purls") or [])))


def load_reachables(pattern: str | Path, dedupe: bool = True) -> Dict:
    """
    Load one or more reachable slice files into a single document.

    Every input file contributes its sibling chunks as well, so passing
    ``reachables.json`` for a chunked atom run picks up ``reachables_1.json``
    and friends automatically.

    Args:
        pattern: A file path, a glob pattern, or a comma separated mix.
        dedupe: Drop duplicate flow groups encountered across inputs.

    Returns:
        A ``{"reachables": [...]}`` document.
    """
    inputs = expand_inputs(str(pattern))
    files: List[str] = []
    for path in inputs:
        files.append(path)
        files.extend(s for s in sibling_chunks(path) if s not in files)
    entries: List[Dict] = []
    seen: set = set()
    duplicates = 0
    for path in files:
        parsed = parse_reachable_file(path)
        logger.debug("Loaded %d reachable entries from %s", len(parsed), path)
        file_fingerprints: set = set()
        for entry in parsed:
            if dedupe:
                fingerprint = flow_fingerprint(entry)
                # Only flows already seen in a *different* file are dropped:
                # entries repeated within one file are left as emitted by atom
                # so single-file inputs keep their historical counts.
                if fingerprint in seen:
                    duplicates += 1
                    continue
                file_fingerprints.add(fingerprint)
            entries.append(entry)
        seen |= file_fingerprints
    if duplicates:
        logger.info("Skipped %d duplicate reachable flow(s) while merging.", duplicates)
    return {"reachables": entries}

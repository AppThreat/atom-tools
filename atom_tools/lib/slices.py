"""
Classes and functions for working with slices.
"""

import json
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Tuple, Dict

import json_flatten  # type: ignore

from atom_tools.lib.adapters import normalize_engine_report
from atom_tools.lib.reachables import load_reachables
from atom_tools.lib.regex_utils import FilteringPatternCollection

logger = logging.getLogger(__name__)
patterns = FilteringPatternCollection()


def create_attrib_dicts(data: Dict) -> Dict[str, Dict]:
    """Creates a flattened slice and individual attribute dictionaries."""
    attributes: Dict[str, Dict] = {
        "filename": {},
        "fullname": {},
        "callname": {},
        "name": {},
        "linenumber": {},
        "signature": {},
    }

    for k, v in data.items():
        if "fileName" in k or "parentFileName" in k:
            attributes["filename"] = process_attrib_dict(attributes["filename"], k, v)
        elif "fullName" in k:
            attributes["fullname"] = process_attrib_dict(attributes["fullname"], k, v)
        elif "callName" in k:
            attributes["callname"] = process_attrib_dict(attributes["callname"], k, v)
        elif "name" in k:
            attributes["name"] = process_attrib_dict(attributes["name"], k, v)
        elif k.endswith("lineNumber$int"):
            attributes["linenumber"] = process_attrib_dict(attributes["linenumber"], k, v)
        elif "signature" in k:
            attributes["signature"] = process_attrib_dict(attributes["signature"], k, v)

    return attributes


def import_flat_slice(content: Dict) -> Dict[str, Dict]:
    """
    Import a slice from a JSON file.

    Args:
        content (dict): The contents of the JSON file

    Returns:
        tuple[dict, str]: The contents of the JSON file and the type of slice

    Raises:
        JSONDecodeError: If the JSON file cannot be decoded.
        UnicodeDecodeError: If there is an encoding error.
        FileNotFoundError: If the specified file cannot be found.

    Warnings:
        If the JSON file is not a valid slice, a warning is logged.
    """
    content = json_flatten.flatten(content)
    return create_attrib_dicts(content)


def import_slice(filename: str | Path) -> Tuple[Dict, str, str]:
    """
    Import a slice from a JSON file.

    Args:
        filename (str): The path to the JSON file.

    Returns:
        tuple[dict, str]: The contents of the JSON file and the type of slice

    Raises:
        JSONDecodeError: If the JSON file cannot be decoded.
        UnicodeDecodeError: If there is an encoding error.
        FileNotFoundError: If the specified file cannot be found.

    Warnings:
        If the JSON file is not a valid slice, a warning is logged.
    """
    content: Dict = {}
    slice_type = ""
    custom_attr = ""
    filename = str(filename) if filename is not None else filename
    if not filename or not Path(filename).exists():
        logger.warning("No filename specified: %s", filename)
        return content, slice_type, custom_attr
    try:
        with open(filename, "r", encoding="utf-8") as f:
            raw_content = f.read().replace(r"\\", "/")
            if "flask" in raw_content:
                custom_attr = "flask"
            elif "django" in raw_content:
                custom_attr = "django"
            elif "play" in raw_content:
                custom_attr = "playframework"
            elif "akka" in raw_content:
                custom_attr = "akka"
            content = json.loads(raw_content)
        if isinstance(content, list):
            # atom writes chunked reachable slices as bare JSON arrays.
            content = {"reachables": content}
        engine_doc = normalize_engine_report(content, str(filename))
        if engine_doc is not None:
            # dosai/golem/rusi reports: normalise into the atom reachables
            # shape (keeping the engine's endpoint arrays) so every command
            # works on them unchanged. Engine detection happens before the
            # atom checks because e.g. rusi reports also carry a "modules"
            # key that would otherwise read as a parsedeps slice.
            content = engine_doc
            slice_type = "reachables"
        elif content.get("config") or "semantics.slices" in filename:
            slice_type = "semantics"
        elif "objectSlices" in content:
            slice_type = "usages"
        elif "reachables" in content:
            slice_type = "reachables"
        elif "api_endpoints" in content:
            # Rusi (cdxgen-plugins-bin) reports — Rust analyzer output.
            # The api_endpoints array is the structured endpoint table
            # produced by rusi's api-discovery pass.
            slice_type = "api_endpoints"
        elif "apiEndpoints" in content:
            # Golem (cdxgen-plugins-bin) reports — Go analyzer output.
            # Uses camelCase apiEndpoints (rather than snake_case) so
            # it's disambiguated from rusi reports at the slice-loading
            # layer even though converter dispatch is by origin_type.
            slice_type = "api_endpoints"
        elif "graph" in content and "paths" in content:
            # Data-flow slice produced by `atom data-flow`:
            # {"graph": {"nodes": [...], "edges": [...]}, "paths": [...]}
            slice_type = "data-flow"
        elif "modules" in content:
            # Dependency slice produced by `atom parsedeps` (python only):
            # {"modules": [{"name", "version", "versionSpecifiers",
            #               "importedSymbols"}]}
            slice_type = "parsedeps"
    except (json.decoder.JSONDecodeError, UnicodeDecodeError) as e:
        logger.warning(
            f"Failed to load usages slice: {filename}: {e}\nPlease check that you specified a"
            f" valid json file."
        )
    except FileNotFoundError:
        logger.exception(f"Failed to locate the following slice file: {filename}")
        sys.exit(1)
    if not slice_type:
        logger.warning("Slice type not recognized.")
        sys.exit(1)
    return content, slice_type, custom_attr


def process_attrib_dict(attrib_dict: Dict, k: str, v: str) -> Dict:
    """Adds an attribute to a dictionary."""
    if v in attrib_dict:
        attrib_dict[v].append(k)
    else:
        attrib_dict[v] = [k]
    return attrib_dict


class AtomSlice:
    """
    This class is responsible for importing and storing atom slices.

    Args:
        filename (str): The path to the JSON file.

    Attributes:
        content (dict): The dictionary loaded from the usages JSON file.
        slice_type (str): The type of slice.
        origin_type (str): The originating language.

    Methods:
        import_slice: Imports a slice from a JSON file.
    """

    def __init__(self, filename: str | Path, origin_type: str | None = None) -> None:
        self.content, self.slice_type, self.custom_attr = import_slice(filename)
        self.origin_type = origin_type
        if self.slice_type == "reachables":
            # atom chunks large reachable slices into <base>_1.json and so on.
            # Fold the sibling chunks in so every command sees the full set.
            merged = load_reachables(filename)
            if len(merged["reachables"]) > len(self.content.get("reachables", [])):
                logger.debug(
                    "Merged sibling chunks into %s: %d total reachable entries.",
                    filename,
                    len(merged["reachables"]),
                )
                self.content = merged


@dataclass
class FlatSlice:
    """Class to store a flattened version of a slice."""

    content: Dict = field(init=False)
    slice_file: str = field(init=True)
    slice_type: str = field(init=False)
    attrib_dicts: Dict = field(default_factory=dict)

    def __post_init__(self):
        self.content, self.slice_type, self.custom_attr = import_slice(self.slice_file)
        self.attrib_dicts = import_flat_slice(self.content)

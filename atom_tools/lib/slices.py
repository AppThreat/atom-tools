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

from atom_tools.lib.regex_utils import FilteringPatternCollection

logger = logging.getLogger(__name__)
patterns = FilteringPatternCollection()


def create_attrib_dicts(data: Dict) -> Dict[str, Dict]:
    """Creates a flattened slice and individual attribute dictionaries."""
    attributes: Dict[str, Dict] = {
        'filename': {},
        'fullname': {},
        'callname': {},
        'name': {},
        'linenumber': {},
        'signature': {}
    }

    for k, v in data.items():
        if 'fileName' in k or 'parentFileName' in k:
            attributes['filename'] = process_attrib_dict(attributes['filename'], k, v)
        elif 'fullName' in k:
            attributes['fullname'] = process_attrib_dict(attributes['fullname'], k, v)
        elif 'callName' in k:
            attributes['callname'] = process_attrib_dict(attributes['callname'], k, v)
        elif 'name' in k:
            attributes['name'] = process_attrib_dict(attributes['name'], k, v)
        elif k.endswith('lineNumber$int'):
            attributes['linenumber'] = process_attrib_dict(attributes['linenumber'], k, v)
        elif 'signature' in k:
            attributes['signature'] = process_attrib_dict(attributes['signature'], k, v)

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
    slice_type = ''
    custom_attr = ''
    if not filename or not Path(filename).exists():
        logger.warning('No filename specified.', filename)
        return content, slice_type, custom_attr
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            raw_content = f.read().replace(r'\\', '/')
            if 'flask' in raw_content:
                custom_attr = 'flask'
            elif 'django' in raw_content:
                custom_attr = 'django'
            elif 'play' in raw_content:
                custom_attr = 'playframework'
            elif 'akka' in raw_content:
                custom_attr = 'akka'
            content = json.loads(raw_content)
        if content.get("config") or "semantics.slices" in filename:
            slice_type = 'semantics'
        elif 'objectSlices' in content:
            slice_type = 'usages'
        elif 'reachables' in content:
            slice_type = 'reachables'
    except (json.decoder.JSONDecodeError, UnicodeDecodeError):
        logger.warning(
            f'Failed to load usages slice: {filename}\nPlease check that you specified a valid'
            f' json file.'
        )
    except FileNotFoundError:
        logger.exception(f'Failed to locate the following slice file: {filename}')
        sys.exit(1)
    if not slice_type:
        logger.warning('Slice type not recognized.')
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

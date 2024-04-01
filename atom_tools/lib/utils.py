"""Utility functions"""
import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Tuple


logger = logging.getLogger(__name__)


def add_params_to_cmd(cmd: str, outfile: str, origin_type: str = '') -> Tuple[str, str]:
    """
    Adds the outfile to the command.
    """
    # Check that the input slice has not already been specified
    args = ''
    if origin_type and '-t ' not in cmd and '--type' not in cmd:
        cmd += f' -t {origin_type}'
    if '-i ' in cmd or '--input-slice' in cmd:
        logging.warning(
            'Input slice specified in command to be filtered. Replacing with filtered slice.')
        if match := re.search(r'((?:-i|--input-slice)\s\S+)', cmd):
            cmd = cmd.replace(match[1], f'-i {Path(outfile)}')
    else:
        cmd += f' -i {Path(outfile)}'
    if not args:
        cmd, args = cmd.split(' ', 1)
    return cmd, args


def export_json(data: Dict, outfile: str, indent: int | None = None) -> None:
    """Exports data to json"""
    with open(outfile, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=indent, sort_keys=True)


def output_endpoints(data: Dict, names_only: bool, line_range: Tuple[int, int] | Tuple) -> None:
    """Outputs endpoints"""
    to_print = ''
    for endpoint, values in data.get('paths', {}).items():
        to_print += f'{endpoint}'
        usages = values.get("x-atom-usages", {}).get('call', {})
        if names_only:
            to_print += '\n'
            continue
        for k, v in usages.items():
            for i in v:
                if line_range[0] <= i <= line_range[1]:
                    to_print += f':{k}:{i}'
                    break
            to_print += '\n'
    print(to_print)


def remove_duplicates_list(obj: List[Dict]) -> List[Dict]:
    """Removes duplicates from a list of dictionaries."""
    if not obj:
        return obj
    unique_objs = []
    seen = set()
    for o in obj:
        key = tuple(o.get(k) for k, v in o.items())
        if key not in seen:
            unique_objs.append(o)
            seen.add(key)
    return unique_objs


def sort_dict(result: Dict) -> Dict:
    """Sorts a dictionary"""
    for k, v in result.items():
        if isinstance(v, dict):
            result[k] = sort_dict(v)
        elif isinstance(v, list) and len(v) >= 2:
            result[k] = sort_list(v)
    return result


def sort_list(lst: List) -> List:
    """Sorts a list"""
    if not lst:
        return lst
    if isinstance(lst[0], (str, int)):
        lst.sort()
        return lst
    if isinstance(lst[0], dict):
        if lst[0].get('name'):
            return sorted(lst, key=lambda x: x['name'])
        if lst[0].get('fullName'):
            return sorted(lst, key=lambda x: x['code'])
        return sorted(lst, key=lambda x: x.get('callName'))
    return lst

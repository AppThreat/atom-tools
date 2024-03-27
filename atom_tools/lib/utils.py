"""Utility functions"""
import json
import logging
import re
from typing import Dict, Mapping


logger = logging.getLogger(__name__)


def merge_dicts(d1: Dict, d2: Dict) -> Dict:
    """Merges two dictionaries"""
    for k in d2:
        if k in d1 and isinstance(d1[k], dict) and isinstance(d2[k], Mapping):
            merge_dicts(d1[k], d2[k])
        else:
            d1[k] = d2[k]
    return d1


def export_json(data: Dict, outfile: str, indent: int | None = None) -> None:
    """Exports data to json"""
    with open(outfile, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=indent)


def add_outfile_to_cmd(cmd: str, outfile: str):
    """
    Adds the outfile to the command.
    """
    # Check that the input slice has not already been specified
    args = ''
    if '-i ' in cmd or '--input-slice' in cmd:
        cmd = cmd.replace('--input-slice ', '-i ')
        logging.warning(
            'Input slice specified in command to be filtered. Replacing with filtered slice.')
        if match := re.search(r'((?:-i|--input-slice)\s\S+)', cmd):
            cmd = cmd.replace(match[1], f'-i {outfile}')
    else:
        cmd += f' -i {outfile}'
    if not args:
        cmd, args = cmd.split(' ', 1)
    return cmd, args


def sort_dict(result: Dict) -> Dict:
    """Sorts a dictionary"""
    for k, v in result.items():
        if isinstance(v, dict):
            result[k] = sort_dict(v)
        elif isinstance(v, list) and len(v) >= 2:
            result[k] = sort_list(v)
    return result


def sort_list(lst):
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

"""
Utilities for slices
"""
import logging
import re
from dataclasses import dataclass
from typing import Tuple, List, Dict, Any

logger = logging.getLogger(__name__)

PY_TYPE_MAPPING = {'int': 'integer', 'string': 'string', 'float': 'number', 'path': 'string'}


@dataclass
class RegexCollection:
    """
    Collection of regular expressions needed for conversions.
    """
    endpoints = re.compile(r'[\'"](\S*?)[\'"]')
    # This regex is used to extract parameters enclosed in curly braces
    processed_param = re.compile(r'{(?P<pname>[^\s}]+)}')
    # This regex is used to extract named python parameters that include a type
    py_param = re.compile(r'<(?P<ptype>\w+):(?P<pname>\w+)>')
    # This regex is used to detect when a path contains a regex set
    detect_regex = re.compile(
        r'[|$^]|\\[sbigmd]|\\[dhsvwpbagz\dnfrtu]|\?P?[<:!]|\{\d|\[\S+]|\Wr\"')
    # This regex is used to extract regexes so we can escape forward slashes not part of the path.
    extract_parentheses = re.compile(r'(?P<paren>[(\[][^\s)]+[)\]])')
    # This regex is used to extract named parameters regardless of language
    named_param_generic_extract = re.compile(r'\(\?P?:?<?(?P<pname>[^\[]+)>([^)]+\))')
    # This regex will extract regexes not in a group.
    unnamed_param_generic_extract = re.compile(r'(?P<pattern>\(?\?[:!][^\s)]+[^\w(/.]+)')


regex = RegexCollection()


def py_helper(endpoint: str) -> Tuple[str, List[Dict]]:
    """
    Handles Python path parameters.
    Args:
        endpoint (str): The endpoint string

    Returns:
        tuple[str,list]: The modified endpoint and parameters
    """
    params = []

    if matches := regex.py_param.findall(endpoint):
        endpoint = re.sub(regex.py_param, path_param_repl, endpoint)
        for m in matches:
            p = {'in': 'path', 'name': m[1], 'required': True}
            if PY_TYPE_MAPPING.get(m[0]):
                p['schema'] = {'type': PY_TYPE_MAPPING[m[0]]}
            params.append(p)
    return endpoint, params


def js_helper(endpoint: str) -> str:
    """
    Formats path sections which are parameters correctly.

    Args:
        endpoint (str): The list of endpoints to format.

    Returns:
        tuple[str, list[str]]: The formatted endpoint and parameters.

    """
    return '/'.join(
        [
            f'{{{comp[1:]}}}' if comp.startswith(':') else comp
            for comp in endpoint.split('/')
        ]
    )


def path_param_repl(match: re.Match) -> str:
    """For substituting path parameters."""
    return '{' + match['pname'] + '}'


def regex_match_helper(
        element: str,
        m: Tuple | str,
        orig_element: str,
        param_named: bool,
        count: int
) -> Tuple[str, Dict[str, Any], int]:
    """
    Creates a parameter object from a regex match.
    """
    if param_named:
        p = {
            'in': 'path',
            'name': m[0],
            'required': True,
            'schema': {'type': 'string', 'pattern': m[1].rstrip(')')}
        }
    else:
        ele_name, element, count = create_tmp_regex_name(element, m, count)
        p = {
            'in': 'path',
            'name': ele_name,
            'required': True,
            'schema': {'type': 'string', 'pattern': orig_element}
        }
    return element, p, count


def create_tmp_regex_name(element: str, m: Tuple | str, count: int) -> Tuple[str, str, int]:
    """
    Handles regex parameters without named groups.
    """
    count += 1
    ele_name = f'regex_param_{count}'
    if isinstance(m, str):
        element = f'{"{" + ele_name + "}"}'
    if isinstance(m, tuple):
        element = '{' + element.replace(m[0], f'{ele_name}') + '}'
    return ele_name, element, count


def fwd_slash_repl(match):
    """For substituting forward slashes."""
    return match['paren'].replace('/', '$L@$H')

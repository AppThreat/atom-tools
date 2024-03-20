"""
Utilities for slices
"""
import logging
import re
from dataclasses import dataclass
from typing import Tuple, List, Dict, Any


logger: logging.Logger = logging.getLogger(__name__)
py_type_mapping = {'int': 'integer', 'string': 'string', 'float': 'number', 'path': 'string'}


@dataclass
class OpenAPIRegexCollection:
    """
    Collection of regular expressions needed for conversions.
    """
    endpoints = re.compile(r'[\'"](\S*?)[\'"]')
    # This regex is used to extract parameters enclosed in curly braces
    processed_param = re.compile(r'{(?P<pname>[^\s}]+)}')
    # This regex is used to extract named python parameters that include a type
    py_param = re.compile(r'<(?P<ptype>\w+):(?P<pname>\w+)>')
    # Secondary python parameter regex
    py_param_2 = re.compile(r'<(?P<pname>[^\s>]+)>')
    # This regex is used to detect when a path contains a regex set
    detect_regex = re.compile(r'[|$^]|\\[sbigmd]|\\[dhsvwpbagznfrtu\d]|\?P?[<:!]|\{\d|\[\S+]|\Wr\"')
    # This regex is used to extract regexes so we can escape forward slashes not part of the path.
    extract_parentheses = re.compile(r'(?P<paren>[(\[][^\s)]+[)\]])')
    # This regex is used to extract named parameters regardless of language
    named_param_generic_extract = re.compile(r'\(\?P?:?<?(?P<pname>[^\[]+)>([^)]+\))')
    # This regex will extract regexes not in a group.
    unnamed_param_generic_extract = re.compile(r'(?P<pattern>\(?\?[:!][^\s)]+[^\w(/.]+)')


@dataclass(init=True)
class ValidationRegexCollection:  # pylint: disable=too-many-instance-attributes
    """
    A collection of regular expressions used for validation.

    Attributes:
        java_lib_type (Pattern): Pattern for matching Java library types.
        java_udt_regex (Pattern): Pattern for matching Java user-defined types.
        tests_regex (Pattern): Pattern for matching test-related strings.
        single_char_var (Pattern): Pattern for matching single-character variables.
        js_import (Pattern): Pattern for matching JavaScript import statements.
        js_require_extract (Pattern): Pattern for extracting JavaScript require statements.
        py_func_name (Pattern): Pattern for extracting Python function names.
        py_mod_members (Pattern): Pattern for matching Python module members.
    """
    java_lib_type = re.compile(r'java.[^.\s]+.(?P<type>\w+)')
    java_udt_regex = re.compile(r'(?:(void\()?com|org)[a-z0-9.]+(?P<udt>([A-Z]\w+)*)(?=\(?\))')
    tests_regex = re.compile(r'test.|tests.|/test/|/tests/', re.IGNORECASE)
    single_char_var = re.compile(r'(?<=[(\s])[a-z](?=[\s),.\[])')
    js_import = re.compile(r'import \{ (?P<lib>[\w,\s]+) } from (?P<mod>\S+)')
    js_require_extract = re.compile(r'require\((?P<lib>\S+)\).(?P<mod>\S+)')
    py_func_name = re.compile(r'(?<=\().+?(?=\))')
    py_mod_members = re.compile(r'(?<=:<module>.)(?P<class>[A-Z][^<.]+)?\.?(?P<func>[^<.]+)?')


def py_helper(endpoint: str, regex: OpenAPIRegexCollection) -> Tuple[str, List[Dict]]:
    """
    Handles Python path parameters.
    Args:
        endpoint (str): The endpoint string
        regex (OpenAPIRegexCollection): The regex collection

    Returns:
        tuple[str,list]: The modified endpoint and parameters
    """
    params = []

    if ':' in endpoint and (matches := regex.py_param.findall(endpoint)):
        endpoint = re.sub(regex.py_param, path_param_repl, endpoint)
        for m in matches:
            p = {'in': 'path', 'name': m[1], 'required': True}
            if py_type_mapping.get(m[0]):
                p['schema'] = {'type': py_type_mapping[m[0]]}
            params.append(p)
    elif matches := regex.py_param_2.findall(endpoint):
        endpoint = re.sub(regex.py_param_2, path_param_repl, endpoint)
        for m in matches:
            p = {'in': 'path', 'name': m, 'required': True}
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


def fwd_slash_repl(match: re.Match) -> str:
    """For substituting forward slashes."""
    return str(match['paren'].replace('/', '$L@$H'))

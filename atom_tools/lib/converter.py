"""
Classes and functions used to convert slices.
"""
import contextlib
import json.encoder
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

import jmespath

from atom_tools.lib.regex_utils import (
    py_helper,
    path_param_repl,
    regex_match_helper,
    js_helper,
    fwd_slash_repl,
    OpenAPIRegexCollection
)
from atom_tools.lib.slices import AtomSlice


logger = logging.getLogger(__name__)
regex = OpenAPIRegexCollection()
exclusions = ['/content-type', '/application/javascript', '/application/json', '/application/text',
              '/application/xml', '/*', '/*/*', '/allow']


class OpenAPI:
    """Represents an OpenAPI converter object."""

    def __init__(
        self,
        dest_format: str,
        origin_type: str,
        usages: str,
    ) -> None:
        self.usages: AtomSlice = AtomSlice(usages, origin_type)
        self.openapi_version = dest_format.replace('openapi', '')
        self.title = f'OpenAPI Specification for {Path(usages).parent.stem}'
        self.file_endpoint_map: Dict = {}
        self.params: Dict[str, List[Dict]] = {}
        self.regex_param_count = 0
        self.target_line_nums: Dict[str, Dict] = {}

    def convert_usages(self) -> Dict[str, Dict]:
        """
        Converts usages to OpenAPI.
        """
        methods = self._process_methods()
        methods = self.methods_to_endpoints(methods)
        self.target_line_nums = self._identify_target_line_nums(methods)
        self.file_endpoint_map = self.create_file_to_method_dict(methods)
        methods = self._process_calls(methods)
        return self.populate_endpoints(methods)

    def create_file_to_method_dict(self, method_map: Dict[str, Any]) -> Dict[str, List]:
        """
        Creates a dictionary of endpoints and methods.
        """
        if not method_map:
            return {}
        file_names = list(method_map.get('file_names', {}).keys())
        file_endpoint_map: Dict = {i: [] for i in file_names}
        for full_name in file_names:
            for values in method_map['file_names'][full_name]['resolved_methods'].values():
                file_endpoint_map[full_name].extend(values.get('endpoints'))
        for k, v in file_endpoint_map.items():
            endpoints = set(v)
            for i in endpoints:
                if self.file_endpoint_map.get(i):
                    self.file_endpoint_map[i].add(k)
                else:
                    self.file_endpoint_map[i] = {k}
        return {k: list(v) for k, v in self.file_endpoint_map.items()}

    def create_paths_item(self, filename: str, paths_dict: Dict) -> Dict:
        """
        Create paths item object based on provided endpoints and calls.
        Args:
            filename (str): The name of the file
            paths_dict (dict): The object containing endpoints and calls
        Returns:
            dict: The paths item object
        """
        endpoints = paths_dict[1].get('endpoints')
        calls = paths_dict[1].get('calls')
        call_line_numbers = paths_dict[1].get('line_nos')
        target_line_number = None
        if self.target_line_nums:
            with contextlib.suppress(KeyError):
                target_line_number = self.target_line_nums[filename][paths_dict[0]]

        paths_object: Dict = {}

        for ep in set(endpoints):
            ep, paths_item_object = self._paths_object_helper(
                calls, ep, filename, call_line_numbers, target_line_number
            )
            if paths_object.get(ep):
                paths_object[ep] = merge_path_objects(paths_object[ep], paths_item_object)
            else:
                paths_object |= {ep: paths_item_object}

        return remove_nested_parameters(paths_object)

    def endpoints_to_openapi(self, server: str = '') -> Any:
        """
        Generates an OpenAPI document with paths from usages.
        """
        paths_obj = self.convert_usages()
        output = {
            'openapi': self.openapi_version,
            'info': {'title': self.title, 'version': '1.0.0'},
            'paths': paths_obj
        }
        if server:
            output['servers'] = [{'url': server}]  # type: ignore[list-item]

        return output

    def methods_to_endpoints(self, method_map: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert a method map to a map of endpoints.

        Args:
            method_map (dict): A dictionary mapping method names to resolved methods.

        Returns:
            dict: A new method map containing endpoints.
        """
        new_method_map: Dict = {'file_names': {}}
        for file_name, resolved_methods in method_map.items():
            if new_resolved := self._process_resolved_methods(resolved_methods):
                new_method_map['file_names'][file_name] = {'resolved_methods': new_resolved}
        return new_method_map

    def populate_endpoints(self, method_map: Dict) -> Dict[str, Any]:
        """
        Populate the endpoints based on the provided method_map.
        Args:
            method_map (dict): The method_map mapping resolved methods to
            endpoints.
        Returns:
            dict: The populated endpoints.

        """
        paths_object: Dict = {}
        for resolved_methods in method_map.values():
            for key, value in resolved_methods.items():
                for m in value['resolved_methods'].items():
                    new_path_item = self.create_paths_item(key, m)
                    if paths_object:
                        paths_object = merge_path_objects(paths_object, new_path_item)
                    else:
                        paths_object = new_path_item
        return paths_object

    def _calls_to_params(self, ep: str, orig_ep: str, call: Dict | None) -> Dict[str, Any]:
        """
        Transforms a call and endpoint into a parameter object and organizes it
        into a dictionary based on the call name.
        Args:
            call (dict): The call object
            ep (str): The endpoint
            orig_ep (str): The original endpoint
        Returns:
            dict: The operation object
        """
        if not call:
            call = {}
        ops = {'get', 'put', 'post', 'delete', 'options', 'head', 'patch'}
        call_name = call.get('callName', '')
        params = []
        if call_name in ops:
            params = self._create_param_object(ep, orig_ep, call)
            result: Dict[str, Dict] = {call_name: {'responses': {}}}
            if params:
                result[call_name] |= {'parameters': params}
            return result
        return determine_operations(call, params)

    def _check_path_elements_regex(self, ele: str) -> Tuple[str, List]:
        """Try to interpret regexes in the path"""
        if '<' in ele:
            matches = regex.named_param_generic_extract.findall(ele)
            named = True
        else:
            matches = regex.unnamed_param_generic_extract.findall(ele)
            named = False

        if matches:
            ele, params = self._process_regex_matches(ele, named, matches)
        else:
            self.regex_param_count += 1
            ele_name = f'regex_param_{self.regex_param_count}'
            params = [{
                      'in': 'path',
                      'name': ele_name,
                      'required': True,
                      'schema': {'type': 'string', 'pattern': ele}
                      }]

        return ele, params

    def _create_param_object(self, ep: str, orig_ep: str, call: Dict | None) -> List[Dict]:
        """
        Create a parameter object for each parameter in the input list.

        Args:
            call (dict): The call object
            ep (str): The endpoint

        Returns:
            list[dict]: The list of parameter objects

        """
        params = self._generic_params_helper(ep, orig_ep) if '{' in ep else []
        if not params and call:
            ptypes = set(call.get('paramTypes', []))
            if len(ptypes) > 1:
                params = [{'name': param, 'in': 'header'} for param in ptypes if param != 'ANY']
            else:
                params = [{'name': param, 'in': 'header'} for param in ptypes]
        return params

    def _extract_endpoints(self, method: str) -> List[str]:
        """
        Extracts endpoints from the given code based on the specified language.

        Args:
            method (str): The code from which to extract endpoints.

        Returns:
            list: A list of endpoints extracted from the code.

        """
        if not method or not (matches := re.findall(regex.endpoints, method)):
            return []
        matches = self._filter_matches(matches, method)
        return [
            v for v in matches
            if v and v not in exclusions and not v.lower().startswith('/x-')
        ]

    def _extract_params(self, ep: str) -> Tuple[str, bool, List]:
        tmp_params: List = []
        py_special_case = False
        if self.usages.origin_type in ('js', 'ts', 'javascript', 'typescript'):
            ep = js_helper(ep)
        elif self.usages.origin_type in ('py', 'python'):
            ep, tmp_params = py_helper(ep, regex)
            py_special_case = True
        return ep, py_special_case, tmp_params

    def _filter_matches(self, matches: List[str], code: str) -> List[str]:
        """
        Filters a list of matches based on certain criteria.

        Args:
            matches (list[str]): A list of matching strings.
            code (str): The code from which to extract endpoints.

        Returns:
            list[str]: Filtered matches that meet the specified criteria.
        """
        filtered_matches: List[str] = []

        match self.usages.origin_type:
            case 'java' | 'jar':
                if not (
                    code.startswith('@') and ('Mapping' in code or 'Path' in code) and '(' in code
                ):
                    return filtered_matches
            case 'js' | 'ts' | 'javascript' | 'typescript':
                if 'app.' not in code and 'route' not in code and 'ftp' not in code:
                    return filtered_matches

        for m in matches:
            if m and m[0] not in ('.', '@', ','):
                nm = m.replace('"', '').replace("'", '').lstrip('/')
                filtered_matches.append(f'/{nm}')

        return filtered_matches

    def _generic_params_helper(self, endpoint: str, orig_endpoint: str) -> List[Dict[str, Any]]:
        """
        Extracts generic path parameters from the given endpoint.

        Args:
            endpoint (str): The endpoint string with generic path parameters.
            orig_endpoint (str): The original endpoint string.

        Returns:
            list: A list of dictionaries containing the extracted parameters.
        """
        params = []
        existing_path_params = set()
        if self.params.get(orig_endpoint):
            params.extend(self.params[orig_endpoint])
            existing_path_params = {i['name'] for i in params}
        if matches := regex.processed_param.findall(endpoint):
            params.extend(
                [{'name': m, 'in': 'path', 'required': True} for m in matches if
                    m not in existing_path_params]
            )
        return params

    def _identify_target_line_nums(self, methods: Dict[str, Any]) -> Dict:
        file_names = list(methods['file_names'].keys())
        if not file_names:
            return {}
        conditional = [f'fileName==`{i}`' for i in file_names]
        conditional = '*[?' + ' || '.join(conditional) + (  # type: ignore
            '][].{file_name: fileName, methods: usages[].targetObj[].{resolved_method: '
            'resolvedMethod || callName || code || name, line_number: lineNumber}}')
        pattern = jmespath.compile(conditional)  # type: ignore
        result = pattern.search(self.usages.content)
        result = {i['file_name']: i['methods'] for i in result if i['methods']}
        targets: Dict = {i: {} for i in result}

        for k, v in result.items():
            for i in v:
                targets[k] = merge_targets(targets[k], {i['resolved_method']: i['line_number']})

        return targets

    def _paths_object_helper(
            self,
            calls: List,
            ep: str,
            filename: str,
            call_line_numbers: List,
            line_number: int | None
    ) -> Tuple[str, Dict]:
        """
        Creates a paths item object.
        """
        paths_item_object: Dict = {}
        tmp_params: List = []
        py_special_case = False
        orig_ep = ep
        if ':' in ep or '<' in ep:
            ep, py_special_case, tmp_params = self._extract_params(ep)
        if '{' in ep and not py_special_case:
            tmp_params = self._generic_params_helper(ep, orig_ep)
        if tmp_params:
            paths_item_object['parameters'] = tmp_params
        if calls:
            for call in calls:
                paths_item_object |= self._calls_to_params(ep, orig_ep, call)
        if (call_line_numbers or line_number) and (line_nos := create_ln_entries(
                filename, list(set(call_line_numbers)), line_number)):
            if 'x-atom-usages' in paths_item_object:
                paths_item_object['x-atom-usages'] = merge_x_atom(
                    paths_item_object['x-atom-usages'], line_nos)
            else:
                paths_item_object |= line_nos
        return ep, paths_item_object

    def _parse_path_regexes(self, endpoint: str) -> str:
        """
        Parses path regexes in the endpoint, extracts params for later use.
        """
        if '(' in endpoint:
            endpoint = regex.extract_parentheses.sub(fwd_slash_repl, endpoint)
        endpoint_elements = endpoint.lstrip('/').rstrip('$').rstrip('/').split('/')
        endpoint_elements = [
            i.lstrip('/').lstrip('^').rstrip('/').rstrip('$').replace('$L@$H', '/')
            for i in endpoint_elements
        ]
        params = []
        new_endpoint = ''
        for i in endpoint_elements:
            if regex.detect_regex.search(i):
                e, b = self._check_path_elements_regex(i)
                new_endpoint += f'/{e}'
                params.extend(b)
            else:
                new_endpoint += f'/{i}'
        if params:
            self.params[new_endpoint] = params
        return new_endpoint

    def _process_calls(self, method_map: Dict) -> Dict[str, Any]:
        """
        Process calls and return a new method map.
        Args:
            method_map (dict): A mapping of file names to resolved methods.
        Returns:
            dict: A new method map containing calls.
        """
        for file_name, resolved_methods in method_map['file_names'].items():
            if res := self._query_calls(file_name, resolved_methods['resolved_methods'].keys()):
                mmap = filter_calls(res, resolved_methods)
            else:
                mmap = filter_calls([], resolved_methods)

            method_map['file_names'][file_name]['resolved_methods'] = mmap.get('resolved_methods')

        return method_map

    def _process_methods(self) -> Dict[str, List[str]]:
        """
        Create a dictionary of file names and their corresponding methods.
        """
        method_map = self._process_methods_helper(
            'objectSlices[].{file_name: fileName, resolved_methods: usages[].*.resolvedMethod[]}')

        calls = self._process_methods_helper(
            'objectSlices[].{file_name: fileName, resolved_methods: usages[].*[?resolvedMethod][]'
            '[].resolvedMethod[]}')

        user_defined_types = self._process_methods_helper(
            'userDefinedTypes[].{file_name: name, resolved_methods: fields[].name}')

        for key, value in calls.items():
            if method_map.get(key):
                method_map[key]['resolved_methods'].extend(value.get('resolved_methods'))
            else:
                method_map[key] = {'resolved_methods': value.get('resolved_methods')}

        for key, value in user_defined_types.items():
            if method_map.get(key):
                method_map[key]['resolved_methods'].extend(value.get('resolved_methods'))
            else:
                method_map[key] = {'resolved_methods': value.get('resolved_methods')}

        for k, v in method_map.items():
            method_map[k] = list(set(v.get('resolved_methods')))

        return method_map

    def _process_methods_helper(self, pattern: str) -> Dict[str, Any]:
        """
        Process the given pattern and return the resolved methods.

        Args:
            pattern (str): The pattern to be processed and resolved.

        Returns:
            dict: The resolved methods.

        """
        dict_resolved_pattern = jmespath.compile(pattern)
        result = []
        if matches := dict_resolved_pattern.search(self.usages.content):
            result = [
                i for i in matches
                if i.get('resolved_methods')
            ]
        resolved: Dict = {}
        for r in result:
            file_name = r['file_name']
            methods = r['resolved_methods']
            resolved.setdefault(file_name, {'resolved_methods': []})[
                'resolved_methods'].extend(methods)

        return resolved

    def _process_regex_matches(
            self,
            element: str,
            param_named: bool,
            matches: List[Tuple[str, str]]
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Processes regex matches and generates parameters for a path element.

        Args:
            - element (str): The original path element.
            - param_named (bool): Indicates whether the path element contains named parameters.
            - matches (List[str]): The regex matches found in the path element.

        Returns:
            - Tuple[str, List[Dict[str, Any]]]: A tuple containing the processed path element and a
                                                list of parameter dictionaries.
        """
        orig_element = element
        if param_named:
            element = re.sub(regex.named_param_generic_extract, path_param_repl, element)

        params = []
        for m in matches:
            element, p, self.regex_param_count = regex_match_helper(
                element, m, orig_element, param_named, self.regex_param_count)

            params.append(p)

        return element, params

    def _process_resolved_methods(self, resolved_methods: Dict) -> Dict:
        """
        Processes the resolved methods and extracts their endpoints.

        Args:
            resolved_methods (dict): The resolved methods.

        Returns:
            dict: A dictionary mapping each method to its extracted endpoints.
        """
        resolved_map = {}
        for method in resolved_methods:
            if endpoints := self._extract_endpoints(method):
                eps = [self._parse_path_regexes(ep) for ep in endpoints]
                resolved_map[method] = {'endpoints': eps}
        return resolved_map

    def _query_calls(self, file_name: str, resolved_methods: List[str]) -> List:
        """
        Query calls for the given function name and resolved methods.

        Args:
            file_name (str): The name of the function to query calls for.
            resolved_methods (list[str]): List of resolved methods.

        Returns:
            list[dict]: List of invoked calls and argument to calls.
        """
        result = self._query_calls_helper(file_name)
        calls = []
        for call in result:
            m = call.get('resolvedMethod', '')
            if m and m in resolved_methods:
                calls.append(call)
        return calls

    def _query_calls_helper(self, file_name: str) -> List[Dict]:
        """
        A function to help query calls.

        Args:
            file_name (str): The name of the function to query calls for.

        Returns:
             list: The result of searching for the calls pattern in the usages.
        """
        pattern = (f'objectSlices[?fileName==`{json.dumps(file_name.encode().decode())}`].usages[]'
                   f'.*[?callName][][]')
        compiled_pattern = jmespath.compile(pattern)
        return compiled_pattern.search(self.usages.content)


def create_ln_entries(filename: str, call_line_numbers: List, line_number: int | None) -> Dict:
    """
    Creates line number entries for a given filename and line numbers.

    Args:
        filename (str): The name of the file.
        call_line_numbers (list): A list of call line numbers.
        line_number (int): Target line number.

    Returns:
        dict: A dictionary containing line number entries.
    """
    fn = filename.split(':')[0]
    x_atom: Dict = {'x-atom-usages': {}}
    if call_line_numbers:
        x_atom['x-atom-usages']['call'] = {fn: call_line_numbers}
    if line_number:
        x_atom['x-atom-usages']['target'] = {fn: line_number}
    return x_atom


def determine_operations(call: Dict, params: List) -> Dict[str, Any]:
    """
    Determine the supported operations based on the call and parameters.

    Args:
        call (dict): The call information.
        params (list): The parameters for the call.

    Returns:
        dict: A dictionary containing the supported operations and their
        parameters and responses.
    """
    ops = {'get', 'put', 'post', 'delete', 'options', 'head', 'patch'}
    if found := [op for op in ops if op in call.get('resolvedMethod', '').lower()]:
        if params:
            return {op: {'parameters': params, 'responses': {}} for op in found}
        return {op: {'responses': {}} for op in found}
    return {'parameters': params} if params else {}


def filter_calls(
        queried_calls: List[Dict[str, Any]], resolved_methods: Dict) -> Dict[str, List]:
    """
    Iterate through the invokedCalls and argToCalls and create a relevant
    dictionary of endpoints and calls.
    Args:
        queried_calls: List of invokes
        resolved_methods: Dictionary of resolved method objects
    Returns:
        dict: Dictionary of relevant endpoints and calls
    """
    for method in resolved_methods['resolved_methods'].keys():
        calls = [
            i for i in queried_calls
            if i.get('resolvedMethod', '') == method
        ]
        lns = [
            i.get('lineNumber')
            for i in calls
            if i.get('lineNumber') and i.get('resolvedMethod', '') == method
        ]
        resolved_methods['resolved_methods'][method].update({'calls': calls, 'line_nos': lns})
    return resolved_methods


def merge_operations(op1: Dict, op2: Dict) -> Dict:
    """
    Merge two dictionaries of operations.

    Args:
        op1 (dict): The first dictionary of operations.
        op2 (dict): The second dictionary of operations.

    Returns:
        dict: The merged dictionary of operations.
    """
    for k, v in op2.items():
        if v and not op1.get(k) or op1[k] == {}:
            op1[k] = v
        elif k == 'parameters' and v:
            op1[k] = merge_params(op1[k], v)
    return op1


def merge_params(p1: List, p2: List) -> List:
    """
    Merge two lists of parameters.

    Args:
        p1 (list): The first list of parameters.
        p2 (list): The second list of parameters.

    Returns:
        list: The merged list of parameters.
    """
    names = [i.get('name') for i in p1]
    for i in p2:
        if i.get('name', '') not in names:
            p1.append(i)
    return p1


def merge_path_objects(p1: Dict, p2: Dict) -> Dict:
    """
    Merge two dictionaries representing path objects.

    Args:
        p1 (dict): The first dictionary representing a path object.
        p2 (dict): The second dictionary representing a path object.

    Returns:
        dict: The merged dictionary representing the path object.
    """
    for key, value in p2.items():
        if key not in p1:
            p1[key] = value
            continue
        for k, v in value.items():
            if p1[key].get(k):
                if k == 'x-atom-usages':
                    p1[key][k] = merge_x_atom(p1[key][k], v)
                elif k == 'parameters':
                    p1[key][k] = merge_params(p1[key][k], v)
                elif k in {'get', 'put', 'post', 'delete', 'options', 'head', 'patch'}:
                    p1[key][k] = merge_operations(p1[key][k], v)
                continue
            p1[key][k] = v

    return p1


def merge_targets(t1: Dict, t2: Dict) -> Dict:
    """
    Merge two dictionaries of targets.

    Args:
        t1 (dict): The first dictionary of targets.
        t2 (dict): The second dictionary of targets.

    Returns:
        dict: The merged dictionary of targets.
    """
    for k, v in t2.items():
        if k in t1:
            t1[k].append(v)
        else:
            t1[k] = [v]
    return t1


def merge_x_atom(x1: Dict, x2: Dict) -> Dict:
    """
    Merge two dictionaries of x-atom-usages.

    Args:
        x1 (dict): The first dictionary of x atoms.
        x2 (dict): The second dictionary of x atoms.

    Returns:
        dict: The merged dictionary of x atoms.
    """
    for key, value in x2.items():
        if key not in x1:
            x1[key] = value
            continue
        for k, v in value.items():
            if x1[key].get(k):
                x1[key][k].extend(v)
            else:
                x1[key][k] = v
    return x1


def remove_nested_parameters(data: Dict) -> Dict[str, Dict | List]:
    """
    Removes nested path parameters from the given data.

    Args:
        data (dict): The data containing nested path parameters.

    Returns:
        dict: The modified data with the nested path parameters removed.
    """
    for value in data.values():
        for v in value.values():
            if isinstance(v, dict) and 'parameters' in v and isinstance(v['parameters'], list):
                v['parameters'] = [param for param in v['parameters'] if
                                   param.get('in') != 'path']
    return data

"""
Classes and functions used to convert slices.
"""
import json.encoder
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

import jmespath

from atom_tools.lib.regex_utils import (
    regex, py_helper, path_param_repl, regex_match_helper, js_helper, fwd_slash_repl
)
from atom_tools.lib.slices import AtomSlice

logger = logging.getLogger(__name__)


class OpenAPI:
    """
    Represents an OpenAPI converter.

    Args:
        dest_format (str): The destination format.
        origin_type (str): The origin type.
        usages (str): Path of the usages slice.

    Attributes:
        usages (AtomSlice): The usage slice.
        openapi_version (str): The OpenAPI version.
        title (str): The title for the OpenAPI document
        file_endpoint_map (dict): Stores the originating filename for endpoints
        params (dict): Stores params identified from regexes in the path
        regex_param_count: Keeps count of params from unnamed regexes

    Methods:
        _create_ln_entries: Creates an x-atom-usages entry.
        _filter_matches: Filters a list of matches based on certain criteria.
        _js_helper: Formats path sections which are parameters correctly.
        _process_methods_helper: Utility for process_methods.
        _query_calls_helper: A helper function to query calls.
        _remove_nested_parameters: Removes nested path parameters from the get/post/etc.
        calls_to_params: Transforms a call and endpoint into parameter object.
        collect_methods: Collects and combines methods that may be endpoints.
        convert_usages: Converts usages to OpenAPI.
        create_param_object: Creates a parameter object for each parameter.
        create_paths_item: Creates paths item object.
        determine_operations: Determines the supported operations.
        endpoints_to_openapi: Generates an OpenAPI document.
        extract_endpoints: Extracts endpoints from the given code.
        filter_calls: Filters invokedCalls and argToCalls.
        methods_to_endpoints: Converts a method map to a map of endpoints.
        populate_endpoints: Populates the endpoints based on the method_map.
        process_calls: Processes calls and returns a new method map.
        process_methods: Creates a dictionary of endpoints and methods.
        query_calls: Queries calls for the given function name and methods.
    """

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

    def create_file_to_method_dict(self, method_map):
        """
        Creates a dictionary of endpoints and methods.
        """
        full_names = list(method_map.get('full_names').keys())
        file_endpoint_map = {i: [] for i in full_names}
        for full_name in full_names:
            for values in method_map['full_names'][full_name]['resolved_methods'].values():
                file_endpoint_map[full_name].extend(values.get('endpoints'))
        for k, v in file_endpoint_map.items():
            filename = k.split(':')[0]
            endpoints = set(v)
            for i in endpoints:
                if self.file_endpoint_map.get(i):
                    self.file_endpoint_map[i].add(filename)
                else:
                    self.file_endpoint_map[i] = {filename}
        self.file_endpoint_map = {k: list(v) for k, v in self.file_endpoint_map.items()}

    def convert_usages(self) -> Dict[str, Any]:
        """
        Converts usages to OpenAPI.
        """
        methods = self.process_methods()
        methods = self.methods_to_endpoints(methods)
        self.create_file_to_method_dict(methods)
        methods = self.process_calls(methods)
        return self.populate_endpoints(methods)

    def generic_params_helper(self, endpoint: str, orig_endpoint: str) -> List[Dict[str, Any]]:
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

    def process_methods(self) -> Dict[str, List[str]]:
        """
        Create a dictionary of full names and their corresponding methods.
        """
        method_map = self._process_methods_helper(
            'objectSlices[].{full_name: fullName, resolved_methods: usages[].*.resolvedMethod[]}')

        calls = self._process_methods_helper(
            'objectSlices[].{full_name: fullName, resolved_methods: usages[].*[?resolvedMethod][]'
            '[].resolvedMethod[]}')

        user_defined_types = self._process_methods_helper(
            'userDefinedTypes[].{full_name: name, resolved_methods: fields[].name}')

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

    def query_calls(self, full_name: str, resolved_methods: List[str]) -> List:
        """
        Query calls for the given function name and resolved methods.

        Args:
            full_name (str): The name of the function to query calls for.
            resolved_methods (list[str]): List of resolved methods.

        Returns:
            list[dict]: List of invoked calls and argument to calls.
        """
        result = self._query_calls_helper(full_name)
        calls = []
        for call in result:
            m = call.get('resolvedMethod', '')
            if m and m in resolved_methods:
                calls.append(call)
        return calls

    def _query_calls_helper(self, full_name: str) -> List[Dict]:
        """
        A function to help query calls.

        Args:
            full_name (str): The name of the function to query calls for.

        Returns:
             list: The result of searching for the calls pattern in the usages.
        """
        pattern = f'objectSlices[?fullName==`{json.dumps(full_name)}`].usages[].*[?callName][][]'
        compiled_pattern = jmespath.compile(pattern)
        return compiled_pattern.search(self.usages.content)

    def process_calls(self, method_map: Dict) -> Dict[str, Any]:
        """
        Process calls and return a new method map.
        Args:
            method_map (dict): A mapping of full names to resolved methods.
        Returns:
            dict: A new method map containing calls.
        """
        for full_name, resolved_methods in method_map['full_names'].items():
            if res := self.query_calls(full_name, resolved_methods['resolved_methods'].keys()):
                mmap = self.filter_calls(res, resolved_methods)
            else:
                mmap = self.filter_calls([], resolved_methods)

            method_map['full_names'][full_name]['resolved_methods'] = mmap.get('resolved_methods')

        return method_map

    @staticmethod
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

    def methods_to_endpoints(self, method_map: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert a method map to a map of endpoints.

        Args:
            method_map (dict): A dictionary mapping method names to resolved
            methods.

        Returns:
            dict: A new method map containing endpoints.
        """
        new_method_map: Dict = {'full_names': {}}
        for full_name, resolved_methods in method_map.items():
            if new_resolved := self.process_resolved_methods(resolved_methods):
                new_method_map['full_names'][full_name] = {
                    'resolved_methods': new_resolved
                }

        return new_method_map

    def process_resolved_methods(self, resolved_methods: Dict) -> Dict:
        """
        Processes the resolved methods and extracts their endpoints.

        Args:
            resolved_methods (dict): The resolved methods.

        Returns:
            dict: A dictionary mapping each method to its extracted endpoints.
        """
        resolved_map = {}
        for method in resolved_methods:
            if endpoints := self.extract_endpoints(method):
                eps = [self.parse_path_regexes(ep) for ep in endpoints]
                resolved_map[method] = {'endpoints': eps}
        return resolved_map

    def _process_methods_helper(self, pattern: str) -> Dict[str, Any]:
        """
        Process the given pattern and return the resolved methods.

        Args:
            pattern (str): The pattern to be processed and resolved.

        Returns:
            dict: The resolved methods.

        """
        dict_resolved_pattern = jmespath.compile(pattern)
        result = [
            i for i in dict_resolved_pattern.search(self.usages.content)
            if i.get('resolved_methods')
        ]

        resolved: Dict = {}
        for r in result:
            full_name = r['full_name']
            methods = r['resolved_methods']
            resolved.setdefault(full_name, {'resolved_methods': []})[
                'resolved_methods'].extend(methods)

        return resolved

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
                        paths_object = self.merge_path_objects(paths_object, new_path_item)
                    else:
                        paths_object = new_path_item

        return paths_object

    @staticmethod
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
            if p1.get(key):
                p1[key].update(value)
            else:
                p1[key] = value
        return p1

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
        line_numbers = paths_dict[1].get('line_nos')
        paths_object: Dict = {}

        for ep in set(endpoints):
            if ep.startswith('/ftp(?!/quarantine)'):
                print('found')
            ep, paths_item_object = self._paths_object_helper(
                calls,
                ep,
                filename,
                line_numbers,
                )
            if paths_object.get(ep):
                paths_object[ep] |= paths_item_object
            else:
                paths_object |= {ep: paths_item_object}

        return self._remove_nested_parameters(paths_object)

    def _paths_object_helper(
            self, calls: List, ep: str, filename: str, line_numbers: List) -> Tuple[str, Dict]:
        """
        Creates a paths item object.
        """
        paths_item_object: Dict = {}
        tmp_params: List = []
        py_special_case = False
        orig_ep = ep
        if ':' in ep:
            ep, py_special_case, tmp_params = self._extract_params(ep)
        if '{' in ep and not py_special_case:
            tmp_params = self.generic_params_helper(ep, orig_ep)
        if tmp_params:
            paths_item_object['parameters'] = tmp_params
        if calls:
            for call in calls:
                paths_item_object |= self.calls_to_params(ep, orig_ep, call)
        if line_numbers and (line_nos := self._create_ln_entries(
                filename, list(set(line_numbers)))):
            paths_item_object |= line_nos
        return ep, paths_item_object

    def _extract_params(self, ep: str) -> Tuple[str, bool, List]:
        tmp_params: List = []
        py_special_case = False
        if self.usages.origin_type in ('js', 'ts', 'javascript', 'typescript'):
            ep = js_helper(ep)
        elif self.usages.origin_type in ('py', 'python'):
            ep, tmp_params = py_helper(ep)
            py_special_case = True
        return ep, py_special_case, tmp_params

    @staticmethod
    def _create_ln_entries(filename, line_numbers):
        """
        Creates line number entries for a given filename and line numbers.

        Args:
            filename (str): The name of the file.
            line_numbers (list): A list of line numbers.

        Returns:
            dict: A dictionary containing line number entries.
        """
        fn = filename.split(':')[0]
        return {'x-atom-usages': {fn: line_numbers}}

    @staticmethod
    def _remove_nested_parameters(data: Dict) -> Dict[str, Dict | List]:
        """
        Removes nested path parameters from the given data.

        Args:
            data (dict): The data containing nested path parameters.

        Returns:
            dict: The modified data with the nested path parameters removed.
        """
        for value in data.values():
            for v in value.values():
                if isinstance(v, dict) and "parameters" in v and isinstance(v["parameters"], list):
                    v["parameters"] = [param for param in v["parameters"] if
                                       param.get("in") != "path"]
        return data

    @staticmethod
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

    def calls_to_params(self, ep: str, orig_ep: str, call: Dict | None) -> Dict[str, Any]:
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
        return self.determine_operations(call, params)

    def _create_param_object(self, ep: str, orig_ep: str, call: Dict | None) -> List[Dict]:
        """
        Create a parameter object for each parameter in the input list.

        Args:
            call (dict): The call object
            ep (str): The endpoint

        Returns:
            list[dict]: The list of parameter objects

        """
        params = self.generic_params_helper(ep, orig_ep) if '{' in ep else []
        if not params and call:
            ptypes = set(call.get('paramTypes', []))
            if len(ptypes) > 1:
                params = [{'name': param, 'in': 'header'} for param in ptypes if param != 'ANY']
            else:
                params = [{'name': param, 'in': 'header'} for param in ptypes]
        return params

    def extract_endpoints(self, method: str) -> List[str]:
        """
        Extracts endpoints from the given code based on the specified language.

        Args:
            method (str): The code from which to extract endpoints.

        Returns:
            list: A list of endpoints extracted from the code.

        """
        endpoints: List[str] = []
        if not method:
            return endpoints
        if not (matches := re.findall(regex.endpoints, method)):
            return endpoints
        matches = self._filter_matches(matches, method)
        return [v for v in matches if v]

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
                    code.startswith('@')
                    and ('Mapping' in code or 'Path' in code)
                    and '(' in code
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

    def check_path_elements_regex(self, ele: str) -> Tuple[str, List]:
        """Try to interpret regexes in the path"""
        if '<' in ele:
            matches = regex.named_param_generic_extract.findall(ele)
            named = True
        else:
            matches = regex.unnamed_param_generic_extract.findall(ele)
            named = False

        if matches:
            ele, params = self.process_regex_matches(ele, named, matches)
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

    def parse_path_regexes(self, endpoint: str) -> str:
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
                e, b = self.check_path_elements_regex(i)
                new_endpoint += f'/{e}'
                params.extend(b)
            else:
                new_endpoint += f'/{i}'
        if params:
            self.params[new_endpoint] = params
        return new_endpoint

    def process_regex_matches(
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

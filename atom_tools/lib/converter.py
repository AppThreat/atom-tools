"""
Classes and functions used to convert slices.
"""
import json.encoder
import logging
import re

from pathlib import Path

import jmespath

from atom_tools.lib.slices import AtomSlice


logger = logging.getLogger(__name__)


class RegexCollection:
    """
    Collection of regular expressions needed for conversions.

    Attributes:
        endpoints (re.compile): Regex to find endpoints
        param (re.compile): Regex to find path parameters
        py_param (re.compile): Regex to find Python path parameters
        py_regex_in_path (re.compile): Regex to find Python path parameters

    Methods:
        py_helper(endpoint): Handles Python path parameters
        _py_repl(match): Replaces Python path parameters
    """
    def __init__(self):
        self.endpoints = re.compile(r'[\'"](\S*?)[\'"]', re.IGNORECASE)
        self.param = re.compile(r'{(?P<pname>[^\s}]+)}', re.IGNORECASE)
        self.py_param = re.compile(r'<(?P<ptype>\w+):(?P<pname>\w+)>')
        self.py_regex_in_path = re.compile(r'(?<=\?P<)(?P<field>\w+)(?=>)')

    def py_helper(self, endpoint):
        """
        Handles Python path parameters.
        Args:
            endpoint (str): The endpoint string

        Returns:
            tuple[str,list]: The modified endpoint and parameters
        """
        type_mapping = {
            'int': 'integer', 'string': 'string',
            'float': 'number', 'path': 'string'
        }
        params = []

        if matches := self.py_param.findall(endpoint):
            endpoint = re.sub(self.py_param, self._py_repl, endpoint)
            for m in matches:
                p = {'in': 'path', 'name': m[1], 'required': True}
                if type_mapping.get(m[0]):
                    p['schema'] = {'type': type_mapping[m[0]]}
                params.append(p)
        return endpoint, params

    @staticmethod
    def _py_repl(match):
        return '{' + match.group('pname') + '}'


class OpenAPI:
    """
    Represents an OpenAPI converter.

    Args:
        dest_format (str): The destination format.
        origin_type (str): The origin type.
        usages (list, optional): The list of usages. Defaults to None.

    Attributes:
        usages (AtomSlice): The usage slice.
        origin_type (str): The origin type.
        openapi_version (str): The OpenAPI version.
        title (str): The title of the OpenAPI specification.
        regex (RegexCollection): collection of regular expressions

    Methods:
        _js_helper: Formats path sections which are parameters correctly.
        _process_methods_helper: Utility for process_methods.
        _query_calls_helper: A helper function to query calls.
        calls_to_params: Transforms a call and endpoint into parameter object.
        collect_methods: Collects and combines methods that may be endpoints.
        convert_usages: Converts usages to OpenAPI.
        create_param_object: Creates a parameter object for each parameter.
        create_paths_item: Creates paths item object.
        determine_operations: Determines the supported operations.
        endpoints_to_openapi: Generates an OpenAPI document.
        extract_endpoints: Extracts endpoints from the given code.
        filter_calls: Filters invokedCalls and argToCalls.
        filter_matches: Filters a list of matches based on certain criteria.
        methods_to_endpoints: Converts a method map to a map of endpoints.
        populate_endpoints: Populates the endpoints based on the method_map.
        process_calls: Processes calls and returns a new method map.
        process_methods: Creates a dictionary of endpoints and methods.
        query_calls: Queries calls for the given function name and methods.
    """

    def __init__(
        self,
        dest_format,
        origin_type,
        usages=None,
    ):
        self.usages = AtomSlice(usages, origin_type) if usages else None
        self.origin_type = origin_type
        self.openapi_version = dest_format.replace('openapi', '')
        self.title = f'OpenAPI Specification for {Path(usages).parent.stem}'
        self.regex = RegexCollection()

    def endpoints_to_openapi(self, server=None):
        """
        Generates an OpenAPI document with paths from usages.

        Args:
            server (str): The server URL.
        """
        paths_obj = self.convert_usages()
        output = {
            'openapi': self.openapi_version,
            'info': {'title': self.title, 'version': '1.0.0'},
            'paths': paths_obj
        }
        if server:
            output['servers'] = [{'url': server}]
        return output

    def convert_usages(self):
        """
        Converts usages to OpenAPI.
        """
        methods = self.process_methods()
        methods = self.methods_to_endpoints(methods)
        methods = self.process_calls(methods)
        return self.populate_endpoints(methods)

    def _js_helper(self, endpoint):
        """
        Formats path sections which are parameters correctly.

        Args:
            endpoint (list): The list of endpoints to format.

        Returns:
            tuple[str, list]: The formatted endpoint and parameters.

        """
        endpoint = '/'.join([
            f'{{{comp[1:]}}}' if comp.startswith(':')
            else comp for comp
            in endpoint.split('/')
        ])

        params = self.generic_params_helper(endpoint)
        return endpoint, params

    def generic_params_helper(self, endpoint):
        """
        Extracts generic path parameters from the given endpoint.

        Args:
            endpoint (str): The endpoint string with generic path parameters.

        Returns:
            list: A list of dictionaries containing the extracted parameters.
        """
        matches = self.regex.param.findall(endpoint)
        return [
            {'name': m, 'in': 'path', 'required': True} for m in matches
        ] if matches else []

    def process_methods(self):
        """
        Create a dictionary of full names and their corresponding methods.
        """
        method_map = self._process_methods_helper(
            'objectSlices[].{fullName: fullName, resolvedMethods: usages['
            '].*.resolvedMethod[]}')

        calls = self._process_methods_helper(
            'objectSlices[].{fullName: fullName, resolvedMethods: usages['
            '].invokedCalls[?resolvedMethod].resolvedMethod[]}')

        user_defined_types = self._process_methods_helper(
            'userDefinedTypes[].{fullName: name, resolvedMethods: fields['
            '].name}')
        for key, value in calls.items():
            if method_map.get(key):
                method_map[key]['resolved_methods'].extend(
                    value.get('resolved_methods'))
            else:
                method_map[key] = {
                    'resolved_methods': value.get('resolved_methods')}

        for key, value in user_defined_types.items():
            if method_map.get(key):
                method_map[key]['resolved_methods'].extend(
                    value.get('resolved_methods'))
            else:
                method_map[key] = {
                    'resolved_methods': value.get('resolved_methods')}

        for k, v in method_map.items():
            method_map[k] = list(set(v.get('resolved_methods')))

        return method_map

    def query_calls(self, full_name, resolved_methods):
        """
        Query calls for the given function name and resolved methods.

        Args:
            full_name (str): The name of the function to query calls for.
            resolved_methods (list): List of resolved methods.

        Returns:
            list: List of invoked calls and argument to calls.
        """
        result = self._query_calls_helper(full_name, '].invokedCalls[][]')
        calls = []
        for call in result:
            m = call.get('resolvedMethod', '')
            if m and m in resolved_methods:
                calls.append(call)
        result = self._query_calls_helper(full_name, '].argToCalls[][]')
        for call in result:
            m = call.get('resolvedMethod', '')
            if m and m in resolved_methods:
                calls.append(call)
        return calls

    def _query_calls_helper(self, full_name, call_type_str):
        """
        A function to help query calls.

        Args:
            full_name (str): The name of the function to query calls for.
            call_type_str (str): The string to append to the calls pattern.

        Returns:
             list: The result of searching for the calls pattern in the usages.
        """
        calls_pattern = (f'objectSlices[].usages[?fullName=='
                         f'{json.dumps(full_name)}{call_type_str}')
        calls_pattern = jmespath.compile(calls_pattern)
        return calls_pattern.search(self.usages.content)

    def process_calls(self, method_map):
        """
        Process calls and return a new method map.
        Args:
            method_map (dict): A mapping of full names to resolved methods.
        Returns:
            dict: A new method map containing calls.
        """
        for full_name, resolved_methods in method_map['full_names'].items():
            if res := self.query_calls(
                    full_name, resolved_methods['resolved_methods'].keys()):
                mmap = self.filter_calls(res, resolved_methods)
            else:
                mmap = self.filter_calls([], resolved_methods)
            method_map['full_names'][full_name]['resolved_methods'] = (
                mmap.get('resolved_methods'))

        return method_map

    @staticmethod
    def filter_calls(queried_calls, resolved_methods):
        """
        Iterate through the invokedCalls and argToCalls and create a relevant
        dictionary of endpoints and calls.
        Args:
            queried_calls: list of invokes
            resolved_methods: dictionary of resolved method objects
        Returns:
            relevant: dictionary of relevant endpoints and calls
        """
        for method in resolved_methods['resolved_methods'].keys():
            calls = [
                i for i in queried_calls
                if i.get('resolvedMethod', '') == method
            ]
            resolved_methods['resolved_methods'][method].update(
                {'calls': calls})
        return resolved_methods

    def methods_to_endpoints(self, method_map):
        """
        Convert a method map to a map of endpoints.

        Args:
            method_map (dict): A dictionary mapping method names to resolved
            methods.

        Returns:
            dict: A new method map containing endpoints.
        """
        reparsed = {'full_names': {}}
        for full_name, resolved_methods in method_map.items():
            reparsed['full_names'] |= {full_name: {
                'resolved_methods': list(set(resolved_methods))}
            }
        new_method_map = {'full_names': {}}
        for full_name, resolved_methods in method_map.items():
            if new_resolved := self.process_resolved_methods(resolved_methods):
                new_method_map['full_names'][full_name] = {
                    'resolved_methods': new_resolved
                }

        return new_method_map

    def process_resolved_methods(self, resolved_methods):
        """

        Args:
            resolved_methods (list):

        Returns:

        """
        resolved_map = {}
        for method in resolved_methods:
            if endpoint := self.extract_endpoints(method):
                resolved_map[method] = {'endpoints': endpoint}
        return resolved_map

    def _process_methods_helper(self, pattern):
        """
        Process the given pattern and return the resolved methods.

        Args:
            pattern (str): The pattern to be processed and resolved.

        Returns:
            dict: The resolved methods.

        """
        dict_resolved_pattern = jmespath.compile(pattern)
        result = [i for i in dict_resolved_pattern.search(self.usages.content)
                  if i.get('resolvedMethods')]

        resolved = {}
        for r in result:
            full_name = r['fullName']
            methods = r['resolvedMethods']
            resolved.setdefault(full_name, {'resolved_methods': []})[
                'resolved_methods'].extend(methods)

        return resolved

    def populate_endpoints(self, method_map):
        """
        Populate the endpoints based on the provided method_map.
        Args:
            method_map (dict): The method_map mapping resolved methods to
            endpoints.
        Returns:
            dict: The populated endpoints.

        """
        paths_object = {}
        for resolved_methods in method_map.values():
            for value in resolved_methods.values():
                for m in value['resolved_methods'].items():
                    new_path_item = self.create_paths_item(m)
                    if paths_object:
                        paths_object = self.merge_path_objects(
                            paths_object, new_path_item)
                    else:
                        paths_object = new_path_item

        return paths_object

    @staticmethod
    def merge_path_objects(p1, p2):
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

    def create_paths_item(self, paths_dict):
        """
        Create paths item object based on provided endpoints and calls.
        Args:
            paths_dict (dict): The object containing endpoints and calls
        Returns:
            dict: The paths item object

        """
        endpoints = paths_dict[1].get('endpoints')
        calls = paths_dict[1].get('calls')
        paths_object = {}

        for ep in endpoints:
            paths_item_object = {}
            if ':' in ep or '{' in ep or '<' in ep:
                match self.origin_type:
                    case 'js' | 'ts' | 'javascript' | 'typescript':
                        [ep, tmp_paths_item_object] = self._js_helper(ep)
                    case 'py' | 'python':
                        [ep, tmp_paths_item_object] = self.regex.py_helper(ep)
                    case _:
                        tmp_paths_item_object = self.generic_params_helper(ep)
                if tmp_paths_item_object:
                    paths_item_object['parameters'] = tmp_paths_item_object
            if calls:
                for call in calls:
                    paths_item_object |= self.calls_to_params(ep, call)
            else:
                paths_item_object |= self.calls_to_params(ep)
            if paths_item_object:
                if paths_object.get(ep):
                    paths_object[ep] |= paths_item_object
                else:
                    paths_object |= {ep: paths_item_object}
            else:
                paths_object[ep] = {}

        return paths_object

    @staticmethod
    def determine_operations(call, params):
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
        if found := [
            op for op in ops if op in call.get('resolvedMethod', '').lower()
        ]:
            if params:
                return {op: {
                    'parameters': params, 'responses': {}} for op in found
                }
            return {
                op: {'responses': {}} for op in found}
        return {'parameters': params} if params else {}

    def calls_to_params(self, ep, call=None):
        """
        Transforms a call and endpoint into a parameter object and organizes it
        into a dictionary based on the call name.
        Args:
            call (dict): The call object
            ep (str): The endpoint
        Returns:
            dict: The operation object
        """
        if not call:
            call = {}
        ops = {'get', 'put', 'post', 'delete', 'options', 'head', 'patch'}
        call_name = call.get('callName', '')
        params = []
        if call_name in ops:
            params = self.create_param_object(ep, call)
            result = {call_name: {'responses': {}}}
            if params:
                result[call_name] |= {'parameters': params}
            return result
        return self.determine_operations(call, params)

    def create_param_object(self, ep, call=None):
        """
        Create a parameter object for each parameter in the input list.

        Args:
            call (dict): The call object
            ep (str): The endpoint

        Returns:
            list: The list of parameter objects

        """
        params = self.generic_params_helper(ep) if '{' in ep else []
        if not params and call:
            params = [
                {'name': param, 'in': 'header'}
                for param in set(call.get('paramTypes', [])) if param != 'ANY'
            ]
        return params

    def collect_methods(self):
        """
        Collects and combines methods that may be endpoints based on the object
        slices and user-defined types (UDTs) from the content.

        Returns:
            list: A list of unique methods.
        """
        # Surely there is a way to combine these...
        target_obj_pattern = jmespath.compile(
            'objectSlices[].usages[].targetObj.resolvedMethod')
        defined_by_pattern = jmespath.compile(
            'objectSlices[].usages[].definedBy.resolvedMethod')
        invoked_calls_pattern = jmespath.compile(
            'objectSlices[].usages[].invokedCalls[].resolvedMethod')
        udt_jmespath_query = jmespath.compile(
            'userDefinedTypes[].fields[].name')
        methods = target_obj_pattern.search(self.usages.content) or []
        methods.extend(defined_by_pattern.search(self.usages.content) or [])
        methods.extend(invoked_calls_pattern.search(self.usages.content) or [])
        methods.extend(udt_jmespath_query.search(self.usages.content) or [])
        return list(set(methods))

    def extract_endpoints(self, method):
        """
        Extracts endpoints from the given code based on the specified language.

        Args:
            method (str): The code from which to extract endpoints.

        """
        endpoints = []
        if not method:
            return endpoints
        if not (matches := re.findall(self.regex.endpoints, method)):
            return endpoints
        matches = self.filter_matches(matches, method)
        return [v for v in matches if v]

    def filter_matches(self, matches, code):
        """
        Filters a list of matches based on certain criteria.

        Args:
            matches (list): A list of matching strings.
            code (str): The code from which to extract endpoints.

        Returns:
            list: A list of filtered matches that meet the specified criteria.
        """
        filtered_matches = []

        match self.origin_type:
            case 'java' | 'jar':
                if not (
                    code.startswith('@')
                    and ('Mapping' in code or 'Path' in code)
                    and '(' in code
                ):
                    return filtered_matches
            case 'js' | 'ts' | 'javascript' | 'typescript':
                if 'app.' not in code and 'route' not in code:
                    return filtered_matches

        for m in matches:
            if m and m[0] not in ('.', '@') and '/' in m:
                nm = m.replace('"', '').replace("'", '').lstrip('/')
                filtered_matches.append(f'/{nm}')

        return filtered_matches

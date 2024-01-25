"""
Classes and functions used to convert slices.
"""
import json.encoder
import logging
import re

from pathlib import Path

import jmespath

from atom_tools.lib.slices import UsageSlice, ReachablesSlice


logger = logging.getLogger(__name__)


class OpenAPI:
    """
    Represents an OpenAPI object.

    Args:
        dest_format (str): The destination format.
        origin_type (str): The origin type.
        usages (list, optional): The list of usages. Defaults to None.
        reachables (list, optional): The list of reachables. Defaults to None.

    Attributes:
        usages (UsageSlice): The usage slice.
        reachables (ReachablesSlice): The reachables slice.
        origin_type (str): The origin type.
        openapi_version (str): The OpenAPI version.
        endpoints_regex (re.Pattern): The regular expression for endpoints.
        param_regex (re.Pattern): The regular expression pattern for params.
        title (str): The title of the OpenAPI specification.

    Methods:
        endpoints_to_openapi: Generates an OpenAPI document.
        convert_usages: Converts usages to OpenAPI.
        convert_reachables: Converts reachables to OpenAPI.
        js_helper: Formats path sections which are parameters correctly.
        process_methods: Creates a dictionary of endpoints and methods.
        query_calls: Queries calls for the given function name and methods.
        query_calls_helper: A helper function to query calls.
        process_calls: Processes calls and returns a new method map.
        filter_calls: Filters invokedCalls and argToCalls.
        methods_to_endpoints: Converts a method map to a map of endpoints.
        process_methods_helper: Utility for process_methods.
        populate_endpoints: Populates the endpoints based on the method_map.
        create_paths_item: Creates paths item object.
        determine_operations: Determines the supported operations.
        calls_to_params: Transforms a call and endpoint into parameter object.
        create_param_object: Creates a parameter object for each parameter.
        collect_methods: Collects and combines methods that may be endpoints.
        extract_endpoints: Extracts endpoints from the given code.
        filter_matches: Filters a list of matches based on certain criteria.
    """

    def __init__(
        self,
        dest_format,
        origin_type,
        usages=None,
        reachables=None,
    ):
        self.usages = UsageSlice(usages, origin_type) if usages else None
        self.reachables = (
            ReachablesSlice(reachables, origin_type) if reachables else None
        )
        self.origin_type = origin_type
        self.openapi_version = dest_format.replace('openapi', '')
        self.endpoints_regex = re.compile(r'[\'"](\S*?)[\'"]', re.IGNORECASE)
        self.param_regex = re.compile(r'(?<={)[^\s}]+(?=})', re.IGNORECASE)
        self.title = f'OpenAPI Specification for {Path(usages).parent.stem}'

    def endpoints_to_openapi(self, server=None):
        """
        Generates an OpenAPI document with paths from usages.

        Args:
            server (str): The server URL.
        """
        paths_obj = self.convert_usages()
        output = {
            'openapi': self.openapi_version,
            'info': {'title': 'Atom Usages', 'version': '1.0.0'},
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
        return self.populate_endpoints(methods)

    def convert_reachables(self):
        """
        Converts reachables to OpenAPI.
        """
        raise NotImplementedError

    @staticmethod
    def js_helper(endpoints):
        """
        Formats path sections which are parameters correctly.

        Args:
            endpoints (list): The list of endpoints to format.

        Returns:
            list: The formatted list of endpoints.

        """
        new_endpoints = set()

        for endpoint in endpoints:
            if ':' in endpoint:
                endpoint_comp = [
                    f'{{{comp[1:]}}}' if comp.startswith(':')
                    else comp for comp
                    in endpoint.split('/')
                ]
                new_endpoints.add('/'.join(endpoint_comp))
            else:
                new_endpoints.add(endpoint)

        return list(new_endpoints)

    def process_methods(self):
        """
        Create a dictionary of endpoints and their corresponding methods.
        """
        method_map = self.process_methods_helper(
            'objectSlices[].{fullName: fullName, resolvedMethods: usages['
            '].*.resolvedMethod[]}'
        )

        calls = self.process_methods_helper(
            'objectSlices[].{fullName: fullName, resolvedMethods: usages['
            '].invokedCalls[?resolvedMethod].resolvedMethod[]}'
        )

        user_defined_types = self.process_methods_helper(
            'userDefinedTypes[].{fullName: name, resolvedMethods: fields['
            '].name}'
        )
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

        return self.process_calls(self.methods_to_endpoints(method_map))

    def query_calls(self, full_name, resolved_methods):
        """
        Query calls for the given function name and resolved methods.

        Args:
            full_name (str): The name of the function to query calls for.
            resolved_methods (list): List of resolved methods.

        Returns:
            list: List of invoked calls and argument to calls.
        """
        result = self.query_calls_helper(full_name, '].invokedCalls[][]')
        invokes = []
        for call in result:
            m = call.get('resolvedMethod', '')
            if m in resolved_methods:
                invokes.append(call)
        result = self.query_calls_helper(full_name, '].argToCalls[][]')
        for call in result:
            m = call.get('resolvedMethod', '')
            if m in resolved_methods:
                invokes.append(call)
        return invokes

    def query_calls_helper(self, full_name, call_type_str):
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
        new_method_map = {}
        for call in method_map.keys():
            resolved_method_obj = method_map[call]
            if res := self.query_calls(call, resolved_method_obj.keys()):
                mmap = self.filter_calls(res, resolved_method_obj)
                new_method_map[call] = mmap
        return new_method_map

    @staticmethod
    def filter_calls(invokes, resolved_method_obj):
        """
        Iterate through the invokedCalls and argToCalls and create a relevant
        dictionary of endpoints and calls.
        Args:
            invokes: list of invokes
            resolved_method_obj: dictionary of resolved method objects
        Returns:
            relevant: dictionary of relevant endpoints and calls
        """
        relevant = {
            k: {'endpoints': v, 'calls': []}
            for k, v in resolved_method_obj.items()
        }
        for i in invokes:
            relevant[i.get('resolvedMethod')]['calls'].append(i)
        return relevant

    def methods_to_endpoints(self, method_map):
        """
        Convert a method map to a map of endpoints.

        Args:
            method_map (dict): A dictionary mapping method names to resolved
            methods.

        Returns:
            dict: A new method map containing endpoints.
        """
        new_method_map = {}
        for full_name, resolved_methods in method_map.items():
            endpoints = {}
            for method in resolved_methods:
                if res := self.extract_endpoints(method):
                    endpoints[method] = {r: {} for r in res}
            if endpoints:
                new_method_map[full_name] = endpoints
        return new_method_map

    def process_methods_helper(self, pattern):
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
        for key in method_map.keys():
            for k in method_map[key].keys():
                paths_object |= self.create_paths_item(method_map[key][k])
        return paths_object

    def create_paths_item(self, obj):
        """
        Create paths item object based on provided endpoints and calls.
        Args:
            obj (dict): The object containing endpoints and calls
        Returns:
            dict: The paths item object

        """
        endpoints = obj.get('endpoints', [])
        calls = obj.get('calls', [])

        paths_object = {}
        for ep in endpoints:
            paths_item_object = {}
            for call in calls:
                paths_item_object |= self.calls_to_params(call, ep)
            if paths_item_object and paths_object.get(ep):
                paths_object[ep] |= paths_item_object
            elif paths_item_object:
                paths_object[ep] = paths_item_object

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
            return {
                op: {'parameters': params, 'responses': {}} for op in found}
        return {'parameters': params} if params else {}

    def calls_to_params(self, call, ep):
        """
        Transforms a call and endpoint into a parameter object and organizes it
        into a dictionary based on the call name.
        Args:
            call (dict): The call object
            ep (str): The endpoint
        Returns:
            dict: The operation object
        """
        ops = {'get', 'put', 'post', 'delete', 'options', 'head', 'patch'}
        call_name = call.get('callName', '')
        params = []
        if '{' in ep:
            if matches := self.param_regex.findall(ep):
                params = [
                    {'name': match, 'in': 'path', 'required': True}
                    for match in matches
                ]
        if call_name in ops:
            params = self.create_param_object(call, ep)
            return {call_name: {'parameters': params, 'responses': {}}}
        return self.determine_operations(call, params)

    def create_param_object(self, call, ep):
        """
        Create a parameter object for each parameter in the input list.
        Args:
            call (dict): The call object
            ep (str): The endpoint
        Returns:
            list: The list of parameter objects

        """
        params = []
        if '{' in ep:
            matches = self.param_regex.findall(ep)
            params = [
                {'name': m, 'in': 'path', 'required': True} for m in matches
            ]
        if not params:
            params = [
                {'name': param, 'in': 'query'}
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
        matches = re.findall(self.endpoints_regex, method) or []
        if not matches:
            return endpoints
        match self.origin_type:
            case 'java' | 'jar':
                matches = self.filter_matches(matches, method)
                endpoints.extend([v for v in matches if v])
            case 'js' | 'ts' | 'javascript' | 'typescript':
                matches = self.js_helper(self.filter_matches(matches, method))
                endpoints.extend([v for v in matches if v])
            case _:
                to_add = []
                for v in matches:
                    if v and len(v) > 2 and '/' in v:
                        ep = (
                            v.replace('"', '')
                            .replace("'", "")
                            .replace('\n', '')
                            .lstrip('/')
                        )
                        to_add.append(f'/{ep}')
                if to_add:
                    endpoints.extend(to_add)
        return endpoints

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

"""
Classes and functions for working with slices.
"""

import json
import logging
import os.path
import re
import jmespath


class UsageSlice:
    """
    This class is responsible for importing and storing usage slices.

    Args:
        filename (str): The path to the JSON file.

    Attributes:
        usages (dict): The dictionary loaded from the usages JSON file.

    Methods:
        import_slice: Imports a slice from a JSON file.
        generate_endpoints: Generates a list of endpoints from a slice.
        extract_endpoints: Extracts a list of endpoints from a usage.
    """

    def __init__(self, filename, language):
        self.usages = self.import_slice(filename)
        self.language = language
        self.endpoints_regex = re.compile(r'[\'"](\S*?)[\'"]', re.IGNORECASE)

    @staticmethod
    def import_slice(filename):
        """
        Import a slice from a JSON file.

        Args:
            filename (str): The path to the JSON file.

        Returns:
            dict: The contents of the JSON file.

        Raises:
            JSONDecodeError: If the JSON file cannot be decoded.
            UnicodeDecodeError: If there is an encoding error.
            FileNotFoundError: If the specified file cannot be found.

        Warnings:
            If the JSON file is not a valid usage slice, a warning is logged.
        """
        if not filename:
            return {}
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                content = json.load(f)
            return content
        except (json.decoder.JSONDecodeError, UnicodeDecodeError):
            logging.warning(
                f'Failed to load usages slice: {filename}\nPlease check '
                f'that you specified a valid json file.')
        except FileNotFoundError:
            logging.warning(
                f'Failed to locate the usages slice file in the location '
                f'specified: {filename}')

        logging.warning(f'This does not appear to be a valid usage slice: '
                        f'{filename}\nPlease check that you specified the '
                        f'correct usages slice file.')
        return {}

    def generate_endpoints(self):
        """
        Generates and returns a dictionary of endpoints based on the object
        slices and user-defined types (UDTs).

        Returns:
            list: A list of unique endpoints.
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
        methods = target_obj_pattern.search(self.usages) or []
        methods.extend(defined_by_pattern.search(self.usages) or [])
        methods.extend(invoked_calls_pattern.search(self.usages) or [])
        methods.extend(udt_jmespath_query.search(self.usages) or [])
        methods = list(set(methods))

        endpoints = []
        if methods:
            for method in methods:
                endpoints.extend(self.extract_endpoints(method))

        return list(set(endpoints))

    def extract_endpoints(self, code):
        """
        Extracts endpoints from the given code based on the specified language.

        Args:
            code (str): The code from which to extract endpoints.

        Returns:
            list: A list of extracted endpoints.

        Raises:
            None.
        """
        endpoints = []
        if not code:
            return endpoints
        matches = re.findall(self.endpoints_regex, code) or []
        match self.language:
            case 'java' | 'jar':
                if code.startswith('@') and (
                        'Mapping' in code or 'Path' in code) and '(' in code:
                    endpoints.extend(
                        [
                            f'/{v.replace('"', '')
                                .replace("'", "")
                                .lstrip('/')}'
                            for v in matches
                            if v and not v.startswith(".")
                            and "/" in v and not v.startswith("@")
                        ]
                    )
            case 'js' | 'ts' | 'javascript' | 'typescript':
                if 'app.' in code or 'route' in code:
                    endpoints.extend(
                        [
                            f'/{v.replace('"', '')
                                .replace("'", "").lstrip('/')}'
                            for v in matches
                            if v and not v.startswith(".")
                            and '/' in v and not v.startswith('@')
                            and not v.startswith('application/')
                            and not v.startswith('text/')
                        ]
                    )
            case _:
                endpoints.extend([
                    f'/{v.replace('"', '')
                        .replace("'", "")
                        .replace('\n', '')
                        .lstrip('/')}'
                    for v in matches or [] if len(v) > 2 and '/' in v
                ])
        return endpoints


class ReachablesSlice:
    """
    This class is responsible for importing and storing reachables slices.

    Args:
        filename: The name of the file to import the reachables from.

    Attributes:
        reachables: A list of reachables.

    Methods:
        import_slice: Imports the reachables slice from a file.
    """

    def __init__(self, filename, language):
        self.reachables = self.import_slice(filename)
        self.language = language

    @staticmethod
    def import_slice(filename):
        """
        Import a slice from a JSON file.

        Args:
            filename (str): The path to the JSON file.

        Returns:
            list: A list of the reachables slices.

        Raises:
            JSONDecodeError: If the JSON file cannot be decoded.
            UnicodeDecodeError: If there is an encoding error.
            FileNotFoundError: If the specified file cannot be found.

        Warnings:
            A warning is logged if the JSON file is not a valid slice.
        """
        if not filename or not os.path.isfile(filename):
            return []
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                content = json.load(f)
                return content.get('reachables', [])
        except (json.decoder.JSONDecodeError, UnicodeDecodeError):
            logging.warning(
                f'Failed to load usages slice: {filename}\nPlease check '
                f'that you specified a valid json file.'
            )
        except FileNotFoundError:
            logging.warning(
                f'Failed to locate the usages slice file in the location '
                f'specified: {filename}'
            )

        logging.warning(
            f'This does not appear to be a valid usage slice: {filename}\n'
            f'Please check that you specified the correct usages slice file.'
        )
        return []

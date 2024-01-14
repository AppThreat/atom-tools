"""
Classes and functions for working with slices.
"""

import json
import logging
import os.path
import re


class UsageSlice:
    """
    Represents a usage slice.

    This class is responsible for importing and storing usage slices.

    Args:
        filename (str): The path to the JSON file.

    Attributes:
        object_slices (list): A list of object slices.
        user_defined_types (list): A list of user-defined types.

    Methods:
        import_slice: Imports a slice from a JSON file.

    """
    ENDPOINTS_REGEX = re.compile(r'[\'"](\S*?)[\'"]', re.IGNORECASE)

    def __init__(self, filename, language):
        [self.object_slices, self.user_defined_types] = self.import_slice(
            filename
        )
        self.language = language

    @staticmethod
    def import_slice(filename):
        """
        Import a slice from a JSON file.

        Args:
            filename (str): The path to the JSON file.

        Returns:
            tuple: A tuple containing the object slices and user-defined types.
                   The object slices is a list of object slices.
                   The user-defined types is a list of user-defined types.

        Raises:
            JSONDecodeError: If the JSON file cannot be decoded.
            UnicodeDecodeError: If there is an encoding error.
            FileNotFoundError: If the specified file cannot be found.

        Warnings:
            If the JSON file is not a valid usage slice, a warning is logged.
        """
        if not filename:
            return [], []
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                content = json.load(f)
            if content.get('objectSlices'):
                return content.get('objectSlices', []), content.get(
                    'userDefinedTypes', []
                )
        except [json.decoder.JSONDecodeError, UnicodeDecodeError]:
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
            f'This does not appear to be a valid usage slice: '
            f'{filename}\nPlease check that you specified the '
            f'correct usages slice file.'
        )
        return [], []

    def generate_endpoints(self):
        """
        Generates and returns a dictionary of endpoints based on the object
        slices and user-defined types (UDTs).

        Returns:
            list: A list of endpoints.
        """
        endpoints = []
        for object_slice in self.object_slices:
            parent = (
                '/' + object_slice.get('fullName', '')
                .split(':')[0]
                # .split('.')[-1]
                .rstrip('/')
            )
            endpoints.extend(
                self.extract_endpoints_from_usages(
                    object_slice.get('usages', []), parent)
            )
        endpoints.extend(self.extract_endpoints_from_udts())
        return list(set(endpoints))

    def extract_endpoints(self, code, pkg):
        """
        Extracts endpoints from the given code based on the specified language.

        Args:
            code (str): The code from which to extract endpoints.
            pkg (str): The package name to prepend to the extracted endpoints.

        Returns:
            list: A list of extracted endpoints.
        """
        endpoints = []
        if not code:
            return endpoints
        matches = re.findall(UsageSlice.ENDPOINTS_REGEX, code) or []
        match self.language:
            case 'java', 'jar':
                if code.startswith('@') and (
                        'Mapping' in code or 'Path' in code) and '(' in code:
                    endpoints.extend(
                        [
                            pkg + v.replace('"', '').replace("'", "")
                            for v in matches
                            if v and not v.startswith(".")
                            and "/" in v and not v.startswith("@")
                        ]
                    )
            case 'js', 'ts', 'javascript', 'typescript':
                if 'app.' in code or 'route' in code:
                    endpoints.extend(
                        [
                            pkg + v.replace('"', '').replace("'", "")
                            for v in matches
                            if v and not v.startswith(".")
                            and '/' in v and not v.startswith('@')
                            and not v.startswith('application/')
                            and not v.startswith('text/')
                        ]
                    )
            case _:
                endpoints.extend([
                    pkg + v.replace('"', '').replace("'", "").replace('\n', '')
                    for v in matches or [] if len(v) > 2 and '/' in v
                ])
        return endpoints

    def extract_endpoints_from_usages(self, usages, pkg):
        """
        Extracts endpoints from the given list of usages.

        Args:
            usages (List[Dict]): A list of dicts representing the usages.
            pkg (str): The package name.

        Returns:
            List: A list of extracted endpoints.
        """
        endpoints = []
        for usage in usages:
            target_obj = usage.get('targetObj', {})
            defined_by = usage.get('definedBy', {})
            invoked_calls = usage.get('invokedCalls', [])
            if resolved_method := target_obj.get('resolvedMethod'):
                endpoints.extend(self.extract_endpoints(resolved_method, pkg))
            elif resolved_method := defined_by.get('resolvedMethod'):
                endpoints.extend(self.extract_endpoints(resolved_method, pkg))
            if invoked_calls:
                for call in invoked_calls:
                    if resolved_method := call.get('resolvedMethod'):
                        endpoints.extend(
                            self.extract_endpoints(resolved_method, pkg))
        return endpoints

    def extract_endpoints_from_udts(self):
        """
        Extracts endpoints from user-defined types.

        Returns:
            list: A list of endpoints extracted from the user-defined types.
        """
        endpoints = []
        for udt in self.user_defined_types:
            pkg = udt.get('name')
            if fields := udt.get('fields'):
                for f in fields:
                    endpoints.extend(
                        self.extract_endpoints(f.get('name'), pkg))
        return endpoints


class ReachablesSlice:
    """
    Represents a slice of reachables.

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
            tuple: A tuple containing the object slices and user-defined types.
                   The object slices is a list of object slices.
                   The user-defined types is a list of user-defined types.

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
        except [json.decoder.JSONDecodeError, UnicodeDecodeError]:
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

    @property
    def slices(self):
        """
        Get reachables
        Returns:
            A list of reachables.
        """
        return self.reachables

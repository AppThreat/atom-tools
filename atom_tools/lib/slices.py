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

    # TODO:
    def extract_endpoints(self, code):
        """
        Extracts endpoints from the given code based on the language specified.

        Parameters:
            code (str): The code to extract endpoints from.

        Returns:
            list: A list of extracted endpoints.
        """
        endpoints = []

        if not code:
            return endpoints

        pattern = re.compile(r'[\'"](\.*?)[\'"]', re.IGNORECASE)
        matches = re.findall(pattern, code) or []

        match self.language:
            case 'java', 'jar':
                if code.startswith('@') and (
                        'Mapping' in code or 'Path' in code) and (
                        '(' in code):
                    endpoints = (
                        [v.replace('"', '').replace("'", "") for v in
                            matches if v and not v.startswith(
                            ".") and "/" in v and not v.startswith("@")])
            case 'js', 'ts', 'javascript', 'typescript':
                if "app." in code or "route" in code:
                    endpoints = (
                    [v.replace('"', '').replace("'", "") for v in
                     matches if v and not v.startswith(
                        ".") and "/" in v and not v.startswith(
                        "@") and not v.startswith(
                        "application/") and not v.startswith("text/")])
            case 'py', 'python':
                endpoints = ([v.replace('"', '').replace("'", "").replace(
                    "\n", "") for v in matches if len(v) > 2])

        return endpoints

    @staticmethod
    def construct_root_name(slc):
        """
        Generate the root name for a service based on the given slice.

        Args:
            slc (dict): The slc dictionary object containing the slice.

        Returns:
            str: The constructed root name for the service.

        """
        service_name = ''
        if slc.get('fullName'):
            service_name = slc['fullName'].split(':')[0].replace('.', '-')
        elif slc.get('fileName'):
            service_name = os.path.basename(slc.get('fileName')).split('.')[0]
        return service_name

    @property
    def slices(self):
        """
        Get the object slices.
        Returns:
            list: A list of object slices.
        """
        return self.object_slices

    @property
    def udts(self):
        """
        Get the user-defined types.
        Returns:
            list: A list of user-defined types.
        """
        return self.user_defined_types


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

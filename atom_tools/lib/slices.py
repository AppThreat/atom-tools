"""
Classes and functions for working with slices.
"""

import json
import logging
import os.path
import re

logger = logging.getLogger(__name__)
if os.getenv("ATOM_TOOLS_DEBUG") in ['True', 'true', '1']:
    logger.setLevel(logging.DEBUG)


class UsageSlice:
    """
    This class is responsible for importing and storing usage slices.

    Args:
        filename (str): The path to the JSON file.

    Attributes:
        content (dict): The dictionary loaded from the usages JSON file.

    Methods:
        import_slice: Imports a slice from a JSON file.
        generate_endpoints: Generates a list of endpoints from a slice.
        extract_endpoints: Extracts a list of endpoints from a usage.
    """

    def __init__(self, filename, language):
        self.content = self.import_slice(filename)
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
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                content = json.load(f)
            if content.get('objectSlices'):
                return content
        except (json.decoder.JSONDecodeError, UnicodeDecodeError):
            logger.warning(
                f'Failed to load usages slice: {filename}\nPlease check '
                f'that you specified a valid json file.')
        except FileNotFoundError:
            logger.warning(
                f'Failed to locate the usages slice file in the location '
                f'specified: {filename}')

        logger.warning('Failed to load usages slice.')
        return {}


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
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                content = json.load(f)
                return content.get('reachables', [])
        except (json.decoder.JSONDecodeError, UnicodeDecodeError):
            logging.warning(
                f'Failed to load reachables slice: {filename}\nPlease check '
                f'that you specified a valid json file.')
        except FileNotFoundError:
            logging.warning(
                f'Failed to locate the reachables slice file in the location '
                f'specified: {filename}')

        logging.warning('Failed to load reachables slice.')
        return []

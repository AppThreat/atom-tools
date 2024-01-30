"""
Classes and functions for working with slices.
"""

import json
import logging
import re

logger = logging.getLogger(__name__)


class AtomSlice:
    """
    This class is responsible for importing and storing usage slices.

    Args:
        filename (str): The path to the JSON file.

    Attributes:
        content (dict): The dictionary loaded from the usages JSON file.

    Methods:
        import_slice: Imports a slice from a JSON file.
    """

    def __init__(self, filename: str) -> None:
        self.content = self.import_slice(filename)
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

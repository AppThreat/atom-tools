"""
Classes and functions for working with slices.
"""

import json
import logging

logger = logging.getLogger(__name__)


class AtomSlice:
    """
    This class is responsible for importing and storing usage slices.

    Args:
        filename (str): The path to the JSON file.

    Attributes:
        content (dict): The dictionary loaded from the usages JSON file.
        slice_type (str): The type of slice.
        origin_type (str): The originating language.

    Methods:
        import_slice: Imports a slice from a JSON file.
    """

    def __init__(self, filename: str, origin_type: str) -> None:
        self.content, self.slice_type = self.import_slice(filename)
        self.origin_type = origin_type

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
            logger.warning('No filename specified.')
            return {}
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                content = json.load(f)
            if content.get('objectSlices'):
                return content, 'usages'
            if content.get('reachables'):
                return content, 'reachables'
        except (json.decoder.JSONDecodeError, UnicodeDecodeError):
            logger.warning(
                f'Failed to load usages slice: {filename}\nPlease check that you specified a valid'
                f' json file.'
            )
        except FileNotFoundError:
            logger.warning(f'Failed to locate the following slice file: {filename}')
        logger.warning('Slice type not recognized.')
        return {}, 'unknown'

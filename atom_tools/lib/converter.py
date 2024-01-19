"""
Classes and functions used to convert slices.
"""
import logging
import os

from atom_tools.lib.slices import UsageSlice, ReachablesSlice


logger = logging.getLogger(__name__)
if os.getenv("ATOM_TOOLS_DEBUG"):
    logger.setLevel(logging.DEBUG)


class OpenAPI:
    """
    This class is responsible for converting slices to OpenAPI format.

    Args:
        dest_format (str): The destination format for the OpenAPI output.
        origin_type (str): The programming language or filetype of the
                            originating project.
        usages (str, optional): The path to the usages file.
        reachables (str, optional): The path to the reachables file.

    Attributes:
        usages (UsageSlice): The usage slice object.
        reachables (ReachablesSlice): The reachables slice object.
        origin_type (str): The originating language or filetype of the source
                                project.
        openapi_version (str): The version of OpenAPI.

    Methods:
        get_template: Generates the template for the OpenAPI output.
        create_paths_item: Creates a path item object for the paths object.
        endpoints_to_openapi: Generates an OpenAPI dict with paths from usages.
        convert_usages: Converts usages to OpenAPI.
        convert_reachables: Converts reachables to OpenAPI.
        js_helper: Formats path sections which are parameters for js.

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

    def get_template(self):
        """
        Generates the template for the OpenAPI output.

        Returns:
            dict: The template for the OpenAPI output.
        """
        # with open(
        #     'atom_data/openapi_slices_schemas.json', 'r', encoding='utf-8'
        # ) as f:
        #     comp = json.load(f)
        #
        # return {
        #     'openapi': self.openapi_version,
        #     'info': {
        #         'title': 'Atom Usage Slices',
        #         'version': '1.0.0',
        #     },
        #     'paths': {},
        #     'components': comp,
        # }
        raise NotImplementedError

    def create_paths_item(self):
        """
        Creates a path item object for the paths object.
        """
        raise NotImplementedError

    def endpoints_to_openapi(self):
        """
        Generates an OpenAPI document with paths from usages.
        """
        endpoints = self.convert_usages()
        paths_obj = {r: {} for r in endpoints} or {}
        return {
            'openapi': self.openapi_version,
            'info': {'title': 'Atom Usages', 'version': '1.0.0'},
            'paths': paths_obj
        }

    def convert_usages(self):
        """
        Converts usages to OpenAPI.
        """
        endpoints = sorted(
            set(self.usages.generate_endpoints())) if self.usages else []
        if self.origin_type in ('javascript', 'js'):
            endpoints = list(self.js_helper(endpoints))
        return endpoints

    def convert_reachables(self):
        """
        Converts reachables to OpenAPI.
        """
        raise NotImplementedError

    @staticmethod
    def js_helper(js_endpoints):
        """
        Formats path sections which are parameters correctly.

        Args:
            js_endpoints (list): A list of endpoints.

        Yields:
            str: The parsed endpoint.

        """
        for endpoint in js_endpoints:
            if ':' in endpoint:
                endpoint_comp = [
                    f'{{{comp[1:]}}}' if comp.startswith(':')
                    else comp for comp
                    in endpoint.split('/')
                ]
                yield '/'.join(endpoint_comp)
            else:
                yield endpoint

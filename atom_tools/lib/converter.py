"""
Classes and functions used to convert slices.
"""

from atom_tools.lib.slices import UsageSlice, ReachablesSlice


class OpenAPI:
    """
    Represents an OpenAPI converter.

    This class is responsible for converting slices to OpenAPI format.

    Args:
        dest_format (str): The destination format for the OpenAPI output.
        language (str): The programming language for the OpenAPI output.
        usages (str, optional): The path to the usages file.
        reachables (str, optional): The path to the reachables file.

    Attributes:
        usages (UsageSlice): The usage slice object.
        reachables (ReachablesSlice): The reachables slice object.
        language (str): The programming language for the OpenAPI output.
        openapi_version (str): The version of OpenAPI.

    Methods:
        get_template: Generates the template for the OpenAPI output.
        convert_slices: Converts slices to OpenAPI.
        combine_converted: Combines converted slices into a single document.
        convert_usages: Converts usages to OpenAPI.
        convert_reachables: Converts reachables to OpenAPI.

    """

    def __init__(
        self,
        dest_format,
        language,
        usages=None,
        reachables=None,
    ):
        self.usages = UsageSlice(usages, language) if usages else None
        self.reachables = (
            ReachablesSlice(reachables, language) if reachables else None
        )
        self.language = language
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

    def convert_slices(self):
        """
        Converts slices.

        This function converts available slices

        Returns:
            The converted slices, or None if no slices are available.

        """
        if self.usages and self.reachables:
            return self.combine_converted(self.usages, self.reachables)
        if self.usages:
            return self.convert_usages()
        return self.convert_reachables() if self.reachables else None

    def combine_converted(self, usages, reachables):
        """
        Combines converted usages and reachables into a single document.
        """
        raise NotImplementedError

    def convert_usages(self):
        """
        Converts usages to OpenAPI.
        """
        endpoints = self.usages.generate_endpoints()
        return {
            'openapi': self.openapi_version,
            'info': {'title': 'Atom Usages', 'version': '1.0.0'},
            'paths': {endpoint: {} for endpoint in endpoints}
        }

    def convert_reachables(self):
        """
        Converts reachables to OpenAPI.
        """
        raise NotImplementedError
        # endpoints = self.bom.generate_endpoints()
        # with open(self.reachables_file, 'r', encoding='utf-8') as f:
        #     data = json.load(f).get('reachables')
        #
        # with open('schemas/template.json', 'r', encoding='utf-8') as f:
        #     template = json.load(f)
        #
        # paths = []
        # reached = {}
        #
        # for endpoint in endpoints:
        #     new_path = {
        #         endpoint: {
        #             'x-atom-reachables': {}
        #         }
        #     }

"""
Classes and functions used to convert slices.
"""

import json
import logging
import os.path

from atom_tools.lib.slices import UsageSlice, ReachablesSlice


class BomFile:
    """
    Represents a Bill of Materials (BOM) file.

    This class is responsible for importing a BOM file and generating a list of
    services and endpoints.

    Args:
        filename (str): The path to the BOM file.

    Attributes:
        services (list): The list of services extracted from the BOM file.

    Methods:
        import_bom: Imports a BOM file and returns the list of services
        generate_endpoints: Generates a list of endpoints based on the services

    """

    def __init__(self, filename):
        self.services = self.import_bom(filename)

    @property
    def endpoints(self):
        """
        Generates a list of endpoints based on the services provided.

        Returns:
            list: A list containing all the generated endpoints.
        """
        return self.generate_endpoints()

    @staticmethod
    def import_bom(filename):
        """
        Imports a Bill of Materials file and returns the list of services.

        Args:
            filename (str): The path to the BOM file.

        Returns:
            list: The list of services extracted from the BOM file.

        Raises:
            FileNotFoundError: If the specified file does not exist.
            JSONDecodeError: If the BOM file is not valid JSON.
        """
        content = {}
        if not filename or not os.path.isfile(filename):
            logging.error(f'Unable to locate bom file: {filename}')
            return None

        try:
            with open(filename, 'r', encoding='utf-8') as f:
                content = json.load(f)
        except json.JSONDecodeError:
            logging.error(f'Invalid JSON in {filename}')
        except FileNotFoundError:
            logging.error(f'File not found: {filename}')

        return content.get('services')

    def generate_endpoints(self):
        """
        Generates a list of endpoints based on the services provided.

        Returns:
            list: A list containing all the generated endpoints.
        """
        if not self.services:
            return {}
        endpoints = {}
        for service in self.services:
            if not endpoints.get(service['name']):
                endpoints[service['name']] = service['endpoints']
            else:
                endpoints[service['name']].extend(service['endpoints'])
        return endpoints


class OpenAPI:
    """
    Represents an OpenAPI converter.

    This class is responsible for converting slices to OpenAPI format.

    Args:
        dest_format (str): The destination format for the OpenAPI output.
        bom_file (str): The path to the Bill of Materials (BOM) file.
        language (str): The programming language for the OpenAPI output.
        usages (str, optional): The path to the usages file.
        reachables (str, optional): The path to the reachables file.

    Attributes:
        usages (UsageSlice): The usage slice object.
        reachables (ReachablesSlice): The reachables slice object.
        bom (BomFile): The BOM file object.
        language (str): The programming language for the OpenAPI output.
        openapi_version (str): The version of OpenAPI.

    Methods:
        get_template: Generates the template for the OpenAPI output.
        create_paths_object: Creates the paths object for the OpenAPI output.
        create_paths_item: Creates a path item object for the paths object.
        convert_slices: Converts slices to OpenAPI.
        combine_converted: Combines converted slices into a single document.
        convert_usages: Converts usages to OpenAPI.
        convert_reachables: Converts reachables to OpenAPI.

    """

    def __init__(
        self,
        dest_format,
        bom_file,
        language,
        usages=None,
        reachables=None,
    ):
        self.usages = UsageSlice(usages, language) if usages else None
        self.reachables = (
            ReachablesSlice(reachables, language) if reachables else None
        )
        self.bom = BomFile(bom_file)
        self.language = language
        self.openapi_version = dest_format.replace('openapi', '')

    def get_template(self):
        """
        Generates the template for the OpenAPI output.

        Returns:
            dict: The template for the OpenAPI output.
        """
        with open(
            'schemas/openapi_slices_schemas.json', 'r', encoding='utf-8'
        ) as f:
            comp = json.load(f)

        return {
            'openapi': self.openapi_version,
            'info': {
                'title': 'Atom Usage Slices',
                'version': '1.0.0',
            },
            'paths': {},
            'components': comp,
        }

    def create_paths_object(self, endpoints):
        """
        Creates the paths object for the OpenAPI output.

        Args:
            endpoints (list): A list of endpoints.
        """
        return {endpoint: self.create_paths_item() for endpoint in endpoints}

    def create_paths_item(self):
        """
        Creates a path item object for the paths object.
        """
        return {}

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
        if not self.usages:
            logging.warning('No usages slice provided')
            return {}
        endpoints = self.bom.generate_endpoints()
        paths_obj = self.create_paths_object(endpoints)
        output = self.get_template()
        output.update({'paths': paths_obj})
        return output

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

"""
Convert Command for the atom-tools CLI.
"""
import logging
import os
import sys

from cleo.helpers import option

from atom_tools.cli.commands.command import Command
from atom_tools.lib.converter import OpenAPI
from atom_tools.lib.utils import export_json

logger = logging.getLogger(__name__)


class ConvertCommand(Command):
    """
    This command handles the conversion of an atom slice to a specified
    destination format.

    Attributes:
        name (str): The name of the command.
        description (str): The description of the command.
        options (list): The list of options for the command.
        help (str): The help message for the command.

    Methods:
        handle: Executes the command and performs the conversion.
    """

    name = 'convert'
    description = 'Convert an atom slice to a different format.'
    options = [
        option(
            'format',
            'f',
            'Destination format',
            flag=False,
            default='openapi3.1.0',
        ),
        option(
            'input-slice',
            'i',
            'Usages slice file',
            flag=False,
            default='usages.slices.json',
            value_required=True,
        ),
        option(
            'semantics-slice',
            'e',
            'Semantics slice file',
            default='semantics.slices.json',
            flag=False
        ),
        option(
            'type',
            't',
            'Origin type of source on which the atom slice was generated.',
            flag=False,
            default='java',
        ),
        option(
            'output-file',
            'o',
            'Output file',
            flag=False,
            default=os.getenv("OPENAPI_FILENAME", "openapi.json"),
        ),
        option(
            'server',
            's',
            'The server url to be included in the server object.',
            flag=False,
            default=os.getenv("OPENAPI_SERVER_URL")
        )
    ]
    help = """The convert command converts an atom slice to a different format.
Currently supports creating an OpenAPI 3.x document based on a usages slice."""
    loggers = ['atom_tools.lib.converter', 'atom_tools.lib.regex_utils', 'atom_tools.lib.slices',
               'atom_tools.lib.utils']

    def handle(self):
        """
        Executes the convert command and performs the conversion.
        """
        supported_types = {'java', 'jar', 'python', 'py', 'javascript', 'js', 'typescript', 'ts', "ruby", "rb", "scala", "sbt"}
        if self.option('type') not in supported_types:
            raise ValueError(f'Unknown origin type: {self.option("type")}')
        match self.option('format'):
            case 'openapi3.1.0' | 'openapi3.0.1':
                converter = OpenAPI(
                    self.option('format'),
                    self.option('type'),
                    self.option('input-slice'),
                    self.option('semantics-slice'),
                )

                if not (result := converter.endpoints_to_openapi(self.option('server'))):
                    logging.warning('No results produced!')
                    sys.exit(1)
                export_json(result, self.option('output-file'), 4)
                logger.info(f'OpenAPI document written to {self.option("output-file")}.')
            case _:
                raise ValueError(f'Unknown destination format: {self.option("format")}')

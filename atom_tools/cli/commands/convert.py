"""
Convert Command for the atom-tools CLI.
"""
import json
import logging

from cleo.commands.command import Command
from cleo.helpers import option

from atom_tools.lib.converter import OpenAPI


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
    description = 'Convert an atom slice to a different format'
    options = [
        option(
            'format',
            'f',
            'Destination format',
            flag=False,
            default='openapi3.0.1',
        ),
        option(
            'usages-slice',
            'u',
            'Usages slice file',
            flag=False,
            default=None,
            value_required=True,
        ),
        # option(
        #     'reachables-slice',
        #     'r',
        #     'Reachables slice file',
        #     flag=False,
        #     default=None,
        # ),
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
            default='openapi_from_slice.json',
        ),
        option(
            'server',
            's',
            'The server url to be included in the server object.',
            flag=False,
            default='',
        )
    ]
    help = """The convert command converts an atom slice to a different format.
Currently supports creating an OpenAPI 3.x document based on a usages slice."""
    loggers = ['atom_tools.lib.converter', 'atom_tools.lib.slices']

    def handle(self):
        """
        Executes the convert command and performs the conversion.
        """
        supported_types = ['java', 'jar', 'python', 'py', 'javascript', 'js', 'typescript', 'ts']
        if self.option('type') not in supported_types:
            raise ValueError(f'Unknown origin type: {self.option("type")}')
        match self.option('format'):
            case 'openapi3.1.0' | 'openapi3.0.1':
                converter = OpenAPI(
                    self.option('format'),
                    self.option('type'),
                    self.option('usages-slice'),
                )

                if not (result := converter.endpoints_to_openapi(self.option('server'))):
                    logging.error('No results produced!')
                    return 1
                with open(self.option('output-file'), 'w', encoding='utf-8') as f:
                    json.dump(result, f, indent=4, sort_keys=True)
                logging.info(f'OpenAPI document written to {self.option("output-file")}.')
            case _:
                raise ValueError(
                    f'Unknown destination format: {self.option("format")}'
                )

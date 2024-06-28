# pylint: disable=R0801
"""Query Endpoints Command for the atom-tools CLI."""
import logging

from cleo.helpers import option

from atom_tools.cli.commands.command import Command
from atom_tools.lib.converter import OpenAPI
from atom_tools.lib.filtering import get_ln_range
from atom_tools.lib.utils import output_endpoints


logger = logging.getLogger(__name__)


class QueryEndpointsCommand(Command):
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

    name = 'query-endpoints'
    description = 'List elements to display in the console.'
    options = [
        option(
            'input-slice',
            'i',
            'Slice file',
            flag=False,
            value_required=True,
        ),
        option(
            'type',
            't',
            'Origin type of source on which the atom slice was generated.',
            flag=False,
            default='java',
        ),
        option(
            'filter-lines',
            'f',
            'Filter endpoints by line number or range.',
            flag=False,
        ),
        option(
            'sparse',
            's',
            'Only display names; do not include path and line numbers.',
        )
    ]
    help = """The query command can be used to return endpoint results directly to the console. """
    loggers = ['atom_tools.lib.converter', 'atom_tools.lib.regex_utils', 'atom_tools.lib.slices',
               'atom_tools.lib.utils']

    def handle(self):
        """
        Executes the query command and performs the conversion.
        """
        supported_types = {'java', 'jar', 'python', 'py', 'javascript', 'js', 'typescript', 'ts'}
        if self.option('type') not in supported_types:
            raise ValueError(f'Unknown origin type: {self.option("type")}')
        converter = OpenAPI(
            'openapi3.1.0',
            self.option('type'),
            self.option('input-slice'),
        )
        result = converter.endpoints_to_openapi('')
        if not result.get('paths'):
            logger.warning('No results produced!')
            print('')
        else:
            line_filter = ()
            if self.option('filter-lines'):
                line_filter = get_ln_range(self.option('filter-lines'))
            output = output_endpoints(result, self.option('sparse'), line_filter)
            print(output)

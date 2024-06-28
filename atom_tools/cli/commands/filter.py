"""
Filter Command for the atom-tools CLI.
"""
import logging
from pathlib import Path

from cleo.helpers import option

from atom_tools.cli.commands.command import Command
from atom_tools.lib.filtering import Filter, parse_filters
from atom_tools.lib.utils import add_params_to_cmd, export_json


logger = logging.getLogger(__name__)


class FilterCommand(Command):
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

    name = 'filter'
    description = 'Filter an atom slice based on specified criteria.'
    options = [
        option('input-slice', 'i', 'Slice file to filter.', flag=False, value_required=True, ),
        option(
            'criteria',
            'c',
            description='Filter based on an attribute of the slice. May be a Python regular '
                        'expression. Please see documentation for syntax.',
            flag=False,
        ),
        option(
            'package-version',
            'p',
            description='Filter a reachables slice based on a package name and version in format '
                        'package:version. May include multiple separated by a comma.',
            flag=False,
        ),
        option(
            'outfile',
            'o',
            'File to re-export filtered slice to.',
            flag=False,
        ),
        option(
            'fuzz',
            'f',
            description='Minimum percentage to match with the given criteria INSTEAD of using a '
                        'regex. Must be a number between 0 and 100.',
            flag=False,
        ),
        option(
            'execute',
            'e',
            description='Command to execute after filtering.',
            flag=False,
            default='export',
        ),
    ]
    help = """The filter command filters an atom slice based on specified criteria."""
    loggers = ['atom_tools.lib.filtering', 'atom_tools.lib.utils',
               'atom_tools.cli.commands.filter', 'atom_tools.lib.slices', ]

    def handle(self):
        """
        Executes the filter command.
        """
        if self.option('fuzz') and not self.option('fuzz').isnumeric():
            raise ValueError('Fuzz must be a number between 0 and 100.')
        criteria = self.option('criteria')
        outfile = self.option('outfile')
        if not outfile:
            slice_file = Path(self.option('input-slice'))
            outfile = str(slice_file.parent / f'{slice_file.stem}_filtered{slice_file.suffix}')
        cmd, args = 'export', ''
        if self.option('execute') != 'export':
            cmd, args = add_params_to_cmd(self.option('execute'), outfile)
        filter_runner = Filter(self.option('input-slice'), outfile, self.option('fuzz'))
        if criteria:
            filters = parse_filters(criteria)
            filter_runner.add_filters(filters)
        if result := filter_runner.filter_slice():
            export_json(result, outfile, 2)
            logger.info(f'Filtered slice written to {outfile}.')
        if cmd != 'export':
            self.call(cmd, args)

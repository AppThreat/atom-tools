# pylint: disable=R0801
"""Query Reachables Command for the atom-tools CLI."""
import logging

from cleo.helpers import option

from atom_tools.cli.commands.command import Command
from atom_tools.lib.slices import AtomSlice
from atom_tools.lib.utils import check_reachable


logger = logging.getLogger(__name__)


class CheckReachableCommand(Command):
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

    name = 'check-reachable'
    description = ('Find out if there are hits for a given package:version or file:linenumber in '
                   'an atom slice.')
    options = [
        option(
            'input-slice',
            'i',
            'Slice file',
            flag=False,
            value_required=True,
        ),
        option(
            'pkg',
            'p',
            'Package to search for in the format of <package_name>:<version>',
            flag=False,
        ),
        option(
            'location',
            'l',
            'Filename with line number to search for in the format of <filename>:<linenumber>',
            flag=False,
        ),
    ]
    help = """Checks for reachable flows for a pkg:version or file:linenumber in an atom slice."""

    loggers = ['atom_tools.lib.filtering', 'atom_tools.lib.regex_utils', 'atom_tools.lib.slices',
               'atom_tools.lib.utils']

    def handle(self):
        """
        Executes the query command and performs the search.
        """
        atom_slice = AtomSlice(self.option('input-slice'))
        print(check_reachable(atom_slice.content, self.option('pkg'), self.option('location')))

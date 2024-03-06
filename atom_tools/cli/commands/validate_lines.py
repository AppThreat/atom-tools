# pylint: disable=duplicate-code
"""
Line validation command for the atom-tools CLI.
"""
import os
import pathlib
import sys

from cleo.helpers import option

from atom_tools.cli.commands.command import Command
from atom_tools.lib.validator import LineValidator


class ValidateLinesCommand(Command):
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
    name = 'validate-lines'
    description = 'Check the accuracy of the line numbers in an atom slice.'
    options = [
        option(
            'input-slice',
            'i',
            'Slice file to validate.',
            flag=False,
        ),
        option(
            'type',
            't',
            'Origin type of source on which the atom slice was generated.',
            flag=False,
            default='java',
        ),
        option(
            'base-path',
            'd',
            'This should be the same path that was used by atom when the slice was generated.',
            flag=False,
        ),
        option(
            'interval',
            'l',
            'Try matching within a range. Ex. slice has line number 567, with interval of 5, '
            'we check lines 562-572. Use 0 for exact matching.',
            flag=False,
            default=5,
        ),
        option(
            'report',
            'r',
            'Output summary to file. Defaults to output.txt in the current directory.',
            flag=False,
            default='output.txt',
        ),
        option(
            'export-json',
            'j',
            'JSON report file to store invalid lines. Include valid lines as well using -v flag.',
            flag=False,
        )

    ]
    help = """Validate source file line numbers in an atom usages or reachables slice."""
    loggers = ['atom_tools.lib.validator', 'atom_tools.lib.regex_utils', 'atom_tools.lib.slices']

    def handle(self):
        """
        Executes the line validation and outputs the results.
        """
        if not os.path.isfile(self.option('input-slice')):
            self.line(f'Could not locate {self.option("input-slice")}.')
            sys.exit(1)
        if not str(self.option('interval')).isnumeric():
            self.line('Interval must be an integer.')
            sys.exit(1)
        supported_types = ['java', 'python', 'py', 'javascript', 'js', 'typescript', 'ts']
        if self.option('type') not in supported_types:
            raise ValueError(f'Unknown origin type: {self.option("type")}')
        self.validate_lines()

    def validate_lines(self):
        """
        Validate the line numbers in an atom slice file.
        """
        input_slice = pathlib.Path(self.option('input-slice'))
        if self.option('base-path'):
            base_path = pathlib.Path(self.option('base-path'))
        elif self.option('input-slice'):
            base_path = pathlib.Path(self.option('input-slice')).parent
        else:
            base_path = pathlib.Path.cwd()
            input_slice = base_path / 'slices.json'
        interval = int(self.option('interval'))
        validator = LineValidator(input_slice, base_path, interval, self.option('type'))
        validator.validate_line_numbers()
        summary = validator.get_results()
        print(summary)
        validator.write_report(self.option('report'), summary, self.io.is_verbose())
        if self.option('export-json'):
            validator.export_validation_results(self.option('export-json'))

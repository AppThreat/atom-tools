"""
Base console application.
"""

from importlib import import_module
from typing import Callable

from cleo.application import Application as BaseApplication
from cleo.commands.command import Command

from atom_tools import __version__
from atom_tools.cli.command_loader import CommandLoader


def load_command(name: str) -> Callable[[], Command]:
    """
    Load a command dynamically based on the given name.

    This function dynamically imports the module and retrieves the command
    class based on the name. It returns a callable that can be used to
    instantiate the command.

    Args:
        name (str): The name of the command.

    Returns:
        Callable[[], Command]: A callable that of an instance of the command.

    """

    def _load() -> Command:
        words = name.split(' ')
        module = import_module('atom_tools.cli.commands.' + '.'.join(words))
        command_class = getattr(
            module, ''.join(c.title() for c in words) + 'Command'
        )
        command: Command = command_class()
        return command

    return _load


COMMANDS = [
    'convert',
]


class Application(BaseApplication):
    """
    Represents the main application.

    This class initializes the application with the appropriate command loader
    and command names.

    """

    def __init__(self) -> None:
        super().__init__('atom-tools', __version__)

        command_loader = CommandLoader(
            {name: load_command(name) for name in COMMANDS}
        )
        self.set_command_loader(command_loader)


def main() -> int:
    """
    The entry point of the application.

    This function initializes and runs the application.

    Returns:
        int: The exit code of the application.

    """
    exit_code: int = Application().run()
    return exit_code


if __name__ == '__main__':
    main()

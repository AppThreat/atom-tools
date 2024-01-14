"""
Command Loader for the atom-tools CLI.
"""
from collections.abc import Callable

from cleo.commands.command import Command
from cleo.exceptions import CleoLogicError
from cleo.loaders.factory_command_loader import FactoryCommandLoader


class CommandLoader(FactoryCommandLoader):
    """
    Command Loader for the atom-tools CLI.
    """

    def register_factory(
        self, command_name: str, factory: Callable[[], Command]
    ) -> None:
        """
        Register a command factory.

        Args:
            command_name (str): The name of the command.
            factory (Callable[[], Command]): A callable that returns a Command.

        Raises:
            CleoLogicError: If the command with the given name already exists.

        Returns:
            None
        """
        if command_name in self._factories:
            raise CleoLogicError(
                f'The command "{command_name}" already exists.'
            )

        self._factories[command_name] = factory

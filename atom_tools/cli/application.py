"""
Base console application.
"""
import logging
from importlib import import_module
from typing import Callable

from cleo.application import Application as BaseApplication
from cleo.events.console_command_event import ConsoleCommandEvent
from cleo.events.console_events import COMMAND
from cleo.events.event import Event
from cleo.events.event_dispatcher import EventDispatcher
from cleo.io.io import IO

from atom_tools import __version__
from atom_tools.cli.command_loader import CommandLoader
from atom_tools.cli.commands.command import Command
from atom_tools.cli.logging_config import ATOM_TOOLS_FILTER, IOFormatter, IOHandler


def load_command(name: str) -> Callable[[], Command]:
    """
    Loads a command dynamically based on the given name.

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
        module = import_module('atom_tools.cli.commands.' + '.'.join(words).replace('-', '_'))
        command_class = getattr(
            module, ''.join(c.title() for c in words).replace('-', '') + 'Command'
        )
        command: Command = command_class()
        return command

    return _load


COMMANDS = [
    'convert',
    'validate-lines',
]


class Application(BaseApplication):
    """
    Represents the main application.

    This class initializes the application with the appropriate command loader
    and command names. It also sets up logging.

    """

    def __init__(self) -> None:
        super().__init__('atom-tools', __version__)
        self._io: IO | None = None
        dispatcher = EventDispatcher()
        dispatcher.add_listener(COMMAND, self.register_command_loggers)
        self.set_event_dispatcher(dispatcher)
        self._io = self.create_io()
        command_loader = CommandLoader({name: load_command(name) for name in COMMANDS})
        self.set_command_loader(command_loader)

    @staticmethod
    def register_command_loggers(event: Event, event_name: str, _: EventDispatcher) -> None:  # pylint: disable=unused-argument
        """
        Registers the command loggers.

        Args:
            event (Event): The event.
            event_name (str): The event name.
            _: EventDispatcher: The event dispatcher.
        """
        assert isinstance(event, ConsoleCommandEvent)
        command = event.command
        if not isinstance(command, Command):
            return

        io = event.io

        loggers = []
        loggers += command.loggers

        handler = IOHandler(io)
        handler.setFormatter(IOFormatter())

        level = logging.WARNING

        if io.is_debug():
            level = logging.DEBUG
        elif io.is_very_verbose() or io.is_verbose():
            level = logging.INFO

        logging.basicConfig(level=level, handlers=[handler])

        # only log third-party packages when very verbose
        if not io.is_very_verbose():
            handler.addFilter(ATOM_TOOLS_FILTER)

        for name in loggers:
            logger = logging.getLogger(name)
            logger.setLevel(level)


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

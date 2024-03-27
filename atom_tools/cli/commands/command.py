# pylint: disable-all
from __future__ import annotations

from typing import ClassVar

from cleo.commands.command import Command as BaseCommand


class Command(BaseCommand):
    loggers: ClassVar[list[str]] = ['atom_tools.cli.commands.filter']

    def handle(self):
        pass

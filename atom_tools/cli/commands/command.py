# pylint: disable=missing-class-docstring,missing-function-docstring,missing-module-docstring
from __future__ import annotations

from typing import ClassVar

from cleo.commands.command import Command as BaseCommand


class Command(BaseCommand):
    loggers: ClassVar[list[str]] = []

    def handle(self):
        pass

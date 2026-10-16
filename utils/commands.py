import importlib
import pkgutil

import commands


def add_commands_to(bot):
    command_list = [
        importlib.import_module(f"{commands.__name__}.{name}")
        for _, name, _ in pkgutil.iter_modules(commands.__path__)
    ]

    for command in command_list:
        command.add_command_to(bot)

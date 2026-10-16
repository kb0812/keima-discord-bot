import os

import discord
from dotenv import load_dotenv

from utils.interfaces import IBot
from utils.persistence import get_guild_ids


class Bot(IBot):
    def __init__(self):
        super().__init__(intents=discord.Intents.default())
        self.tree = discord.app_commands.CommandTree(self)
        self.guild_ids = get_guild_ids()

    async def setup_hook(self):
        await self.tree.sync()

        from utils.tasks import get_tasks

        for task in get_tasks(self):
            task.start()

        print(
            "Slash commands registered:",
            [command.name for command in self.tree.get_commands()],
        )


def main():
    load_dotenv()
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN is missing from .env")

    bot = Bot()
    from utils.commands import add_commands_to

    add_commands_to(bot)

    @bot.event
    async def on_ready():
        await bot.change_presence(
            status=discord.Status.online,
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="Flag 1.0 「世界はアイで動いてる」",
            ),
        )
        print(f"Logged in as {bot.user}")

    bot.run(token)


if __name__ == "__main__":
    main()

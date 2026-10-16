from discord.ext import tasks

from utils.interfaces import IBot
from utils.persistence import add_guild_id, get_guild_ids


def get_task(bot: IBot):
    @tasks.loop(hours=1)
    async def add_new_guild_ids():
        guild_ids = get_guild_ids()

        for guild_id in bot.guild_ids:
            if guild_id not in guild_ids:
                add_guild_id(guild_id)

    @add_new_guild_ids.before_loop
    async def before_send_regular_message():
        await bot.wait_until_ready()

    return add_new_guild_ids

import discord

from utils.command_helpers import (
    require_permission,
    send_instruction,
    track_guild,
    validate_activity_name,
)
from utils.interfaces import IBot
from utils.persistence import create_activity as save_activity
from utils.persistence import get_activity


def add_command_to(bot: IBot):
    @bot.tree.command(name="create_activity", description="create a new Activity")
    @discord.app_commands.describe(
        activity_name="the name of the Activity",
        description="a description of the Activity",
    )
    async def create_activity(
        interaction: discord.Interaction,
        activity_name: str,
        description: str | None = "",
    ):
        if not await require_permission(interaction, bot, "owner"):
            return
        activity_name = await validate_activity_name(
            interaction, activity_name, creating=True
        )
        if activity_name is None:
            return
        guild_id = track_guild(interaction, bot)
        if get_activity(guild_id, activity_name) is not None:
            await interaction.response.send_message(
                "the Activity already exists", ephemeral=True
            )
            return
        save_activity(guild_id, activity_name, description, interaction.user.id)
        await send_instruction(
            interaction, "create_activity", activity_name, description=description
        )

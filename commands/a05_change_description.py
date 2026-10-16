import discord

from utils.command_helpers import require_activity, send_instruction
from utils.interfaces import IBot
from utils.persistence import change_description as save_description


def add_command_to(bot: IBot):
    @bot.tree.command(
        name="change_description", description="change the description of an Activity"
    )
    @discord.app_commands.describe(
        activity_name="the name of the Activity",
        description="new description of the Activity",
    )
    async def change_description(
        interaction: discord.Interaction,
        activity_name: str,
        description: str | None = "",
    ):
        activity = await require_activity(
            interaction, bot, activity_name, permission="owner_or_core"
        )
        if activity is None:
            return
        activity_name = activity.activity_name
        save_description(interaction.guild_id, activity_name, description)
        await send_instruction(
            interaction, "change_description", activity_name, description=description
        )

import discord

from utils.command_helpers import require_activity, send_instruction
from utils.interfaces import IBot
from utils.persistence import set_activity_archived


def add_command_to(bot: IBot):
    @bot.tree.command(name="unarchive_activity", description="unarchive an Activity")
    @discord.app_commands.describe(activity_name="the name of the Activity")
    async def unarchive_activity(
        interaction: discord.Interaction,
        activity_name: str,
    ):
        activity = await require_activity(
            interaction, bot, activity_name, permission="owner"
        )
        if activity is None:
            return
        activity_name = activity.activity_name
        if not activity.archived_flag:
            await interaction.response.send_message(
                "the Activity is not archived", ephemeral=True
            )
            return
        set_activity_archived(interaction.guild_id, activity_name, False)
        await send_instruction(interaction, "unarchive_activity", activity_name)

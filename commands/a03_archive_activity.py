import discord

from utils.command_helpers import require_activity, send_instruction
from utils.interfaces import IBot
from utils.persistence import get_future_sessions, set_activity_archived


def add_command_to(bot: IBot):
    @bot.tree.command(name="archive_activity", description="archive an Activity")
    @discord.app_commands.describe(activity_name="the name of the Activity")
    async def archive_activity(
        interaction: discord.Interaction,
        activity_name: str,
    ):
        activity = await require_activity(
            interaction, bot, activity_name, permission="owner"
        )
        if activity is None:
            return
        activity_name = activity.activity_name
        guild_id = interaction.guild_id
        if activity.archived_flag:
            await interaction.response.send_message(
                "the Activity is already archived", ephemeral=True
            )
            return
        if any(
            session.activity_name == activity_name
            for session in get_future_sessions(guild_id)
        ):
            await interaction.response.send_message(
                "cannot archive an Activity that has a proposed session", ephemeral=True
            )
            return
        set_activity_archived(guild_id, activity_name, True)
        await send_instruction(interaction, "archive_activity", activity_name)

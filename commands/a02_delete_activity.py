import discord

from utils.command_helpers import require_activity, send_instruction
from utils.interfaces import IBot
from utils.persistence import delete_activity as delete_saved_activity
from utils.persistence import get_future_sessions


def add_command_to(bot: IBot):
    @bot.tree.command(name="delete_activity", description="delete an Activity")
    @discord.app_commands.describe(activity_name="the name of the Activity")
    async def delete_activity(
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
        if any(
            session.activity_name == activity_name
            for session in get_future_sessions(guild_id)
        ):
            await interaction.response.send_message(
                "cannot delete an Activity that has a proposed session", ephemeral=True
            )
            return
        delete_saved_activity(guild_id, activity_name)
        await send_instruction(interaction, "delete_activity", activity_name)

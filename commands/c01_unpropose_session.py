import discord

from utils.command_helpers import require_activity, send_instruction
from utils.interfaces import IBot
from utils.persistence import remove_future_session


def add_command_to(bot: IBot):
    @bot.tree.command(
        name="unpropose_session",
        description="unpropose a session for an Activity (core members only)",
    )
    @discord.app_commands.describe(activity_name="the name of the Activity")
    async def unpropose_session(
        interaction: discord.Interaction,
        activity_name: str,
    ):
        activity = await require_activity(
            interaction, bot, activity_name, permission="core"
        )
        if activity is None:
            return
        activity_name = activity.activity_name
        if not remove_future_session(interaction.guild_id, activity_name):
            await interaction.response.send_message(
                "there is no proposed session for the Activity", ephemeral=True
            )
            return
        await send_instruction(interaction, "unpropose_session", activity_name)

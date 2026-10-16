import discord

from utils.command_helpers import require_activity, send_instruction
from utils.interfaces import IBot
from utils.persistence import remove_activity_member_rel


def add_command_to(bot: IBot):
    @bot.tree.command(name="leave_activity", description="leave an Activity")
    @discord.app_commands.describe(activity_name="the name of the Activity")
    async def leave_activity(
        interaction: discord.Interaction,
        activity_name: str,
    ):
        activity = await require_activity(interaction, bot, activity_name)
        if activity is None:
            return
        activity_name = activity.activity_name
        if not remove_activity_member_rel(
            interaction.guild_id, activity_name, interaction.user.id
        ):
            await interaction.response.send_message(
                f"{interaction.user.mention} was not a member of the Activity",
                ephemeral=True,
            )
            return
        await send_instruction(interaction, "leave_activity", activity_name)

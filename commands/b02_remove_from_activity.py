import discord

from utils.command_helpers import require_activity, send_instruction
from utils.interfaces import IBot
from utils.persistence import remove_activity_member_rel


def add_command_to(bot: IBot):
    @bot.tree.command(
        name="remove_from_activity", description="remove member from an Activity"
    )
    @discord.app_commands.describe(
        activity_name="the name of the Activity", member="the member to be removed"
    )
    async def remove_from_activity(
        interaction: discord.Interaction,
        activity_name: str,
        member: discord.Member,
    ):
        activity = await require_activity(
            interaction, bot, activity_name, permission="owner"
        )
        if activity is None:
            return
        activity_name = activity.activity_name
        if not remove_activity_member_rel(
            interaction.guild_id, activity_name, member.id
        ):
            await interaction.response.send_message(
                f"{member.mention} was not a member of the Activity", ephemeral=True
            )
            return
        await send_instruction(
            interaction, "remove_from_activity", activity_name, member=member
        )

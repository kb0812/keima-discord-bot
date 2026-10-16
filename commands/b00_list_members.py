import discord

from utils.command_helpers import require_activity
from utils.interfaces import IBot
from utils.persistence import get_activity_member_rels


def add_command_to(bot: IBot):
    @bot.tree.command(
        name="list_members", description="list the members of an Activity"
    )
    @discord.app_commands.describe(activity_name="the name of the Activity")
    async def list_members(
        interaction: discord.Interaction,
        activity_name: str,
    ):
        activity = await require_activity(interaction, bot, activity_name)
        if activity is None:
            return
        members = [
            member
            for member in get_activity_member_rels(interaction.guild_id)
            if member.activity_name == activity.activity_name
        ]
        response = "\n".join(
            f"`{idx}`:member=<@{member.member_id}>,core_flag=`{member.core_flag}`"
            for idx, member in enumerate(members)
        )
        await interaction.response.send_message(
            response or "the Activity has no members", ephemeral=True
        )

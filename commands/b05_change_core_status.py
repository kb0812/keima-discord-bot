import discord

from utils.command_helpers import require_activity, send_instruction
from utils.interfaces import IBot
from utils.persistence import change_core_status as save_core_status
from utils.persistence import get_activity_member_rels


def add_command_to(bot: IBot):
    @bot.tree.command(
        name="change_core_status", description="set/unset a member as a core member"
    )
    @discord.app_commands.describe(
        activity_name="the name of the Activity",
        member="the member",
        core_flag="1 = set as core, 0 = unset as core",
    )
    async def change_core_status(
        interaction: discord.Interaction,
        activity_name: str,
        member: discord.Member,
        core_flag: str,
    ):
        activity = await require_activity(
            interaction, bot, activity_name, permission="owner"
        )
        if activity is None:
            return
        activity_name = activity.activity_name
        membership = next(
            (
                rel
                for rel in get_activity_member_rels(interaction.guild_id)
                if rel.member_id == member.id and rel.activity_name == activity_name
            ),
            None,
        )
        if membership is None:
            await interaction.response.send_message(
                f"{member.mention} is not a member of the Activity", ephemeral=True
            )
            return
        core_flag = core_flag.strip()
        if core_flag not in ("0", "1"):
            await interaction.response.send_message(
                "core_flag must be 1 or 0", ephemeral=True
            )
            return
        is_core = core_flag == "1"
        if membership.core_flag == is_core:
            await interaction.response.send_message(
                "command failed: the specified value of core_flag is already the current value",
                ephemeral=True,
            )
            return
        save_core_status(interaction.guild_id, activity_name, member.id, is_core)
        await send_instruction(
            interaction,
            "change_core_status",
            activity_name,
            member=member,
            core_flag=core_flag,
        )

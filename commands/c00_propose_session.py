import datetime
import re

import discord

from utils.command_helpers import require_activity
from utils.interfaces import IBot
from utils.persistence import (
    add_future_session,
    get_activity_member_rels,
    get_future_sessions,
)
from utils.session_times import normalise_start_time, parse_start_time


async def _propose_session(
    interaction: discord.Interaction, activity_name, start_time, dt
):
    members = [
        rel
        for rel in get_activity_member_rels(interaction.guild_id)
        if rel.activity_name == activity_name
    ]
    mentions = " ".join(f"<@{member.member_id}>" for member in members)
    message_contents = f"{mentions}\nIf you are available for `{activity_name}` <t:{int(dt.timestamp())}:R>, please react with a :thumbsup: to this message.\nAt the indicated time, if all core members have reacted, all users who have reacted will be mentioned again."
    await interaction.response.send_message(message_contents)
    message = await interaction.original_response()
    await message.add_reaction("👍")
    add_future_session(
        interaction.guild_id, activity_name, start_time, message.id, message.channel.id
    )


def add_command_to(bot: IBot):
    @bot.tree.command(
        name="propose_session",
        description="propose a session for an Activity (core members only)",
    )
    @discord.app_commands.describe(
        activity_name="the name of the Activity",
        start_time="the start time (in UTC) of the proposed session, in the format [yyyy-MM-dd-HH:mm]",
    )
    async def propose_session(
        interaction: discord.Interaction,
        activity_name: str,
        start_time: str,
    ):
        activity = await require_activity(
            interaction, bot, activity_name, permission="core"
        )
        if activity is None:
            return
        activity_name = activity.activity_name
        guild_id = interaction.guild_id
        if activity.archived_flag:
            await interaction.response.send_message(
                "cannot propose sessions for archived Activities", ephemeral=True
            )
            return
        future_session = next(
            (
                session
                for session in get_future_sessions(guild_id)
                if session.activity_name == activity_name
            ),
            None,
        )
        if future_session is not None:
            link = f"https://discord.com/channels/{guild_id}/{future_session.channel_id}/{future_session.message_id}"
            await interaction.response.send_message(
                f"there is already a proposed session for the Activity: {link}",
                ephemeral=True,
            )
            return
        start_time = normalise_start_time(start_time)
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}-\d{2}:\d{2}", start_time):
            await interaction.response.send_message(
                "start_time should be in the format [yyyy-MM-dd-HH:mm]", ephemeral=True
            )
            return
        try:
            dt = parse_start_time(start_time)
        except ValueError:
            await interaction.response.send_message(
                f"invalid time: {start_time}", ephemeral=True
            )
            return
        if dt < datetime.datetime.now(datetime.timezone.utc):
            await interaction.response.send_message(
                "start_time must be in the future", ephemeral=True
            )
            return
        await _propose_session(interaction, activity_name, start_time, dt)

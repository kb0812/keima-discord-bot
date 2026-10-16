import datetime
import logging

import discord
from discord.ext import tasks

from utils.interfaces import IBot, IFutureSession
from utils.persistence import (
    get_activity_member_rels,
    get_future_sessions,
    get_guild_ids,
    move_to_past_session,
)
from utils.session_times import parse_start_time

logger = logging.getLogger(__name__)


async def _check_reacts(bot: IBot, future_session: IFutureSession, guild_id):
    channel_id = future_session.channel_id
    channel = bot.get_channel(channel_id)
    if channel is None:
        channel = await bot.fetch_channel(channel_id)

    message_id = future_session.message_id
    message = await channel.fetch_message(message_id)

    reaction = next(
        (reaction for reaction in message.reactions if str(reaction.emoji) == "👍"),
        None,
    )
    if reaction is None:
        return False
    reacter_ids = [user.id async for user in reaction.users() if user.id != bot.user.id]

    activity_name = future_session.activity_name
    activity_member_rels = [
        activity_member_rel
        for activity_member_rel in get_activity_member_rels(guild_id)
        if activity_name == activity_member_rel.activity_name
    ]

    core_ids = [
        activity_member_rel.member_id
        for activity_member_rel in activity_member_rels
        if activity_member_rel.core_flag
    ]
    if any(core_id not in reacter_ids for core_id in core_ids):
        return False

    mentions = " ".join(f"<@{reacter_id}>" for reacter_id in reacter_ids)
    message_contents = (
        f"{mentions}\nIt is now the scheduled time for `{activity_name}`."
    )
    await channel.send(message_contents)

    return True


async def _check_session(future_session: IFutureSession, bot: IBot, guild_id):
    activity_name = future_session.activity_name
    start_time = future_session.start_time

    dt = parse_start_time(start_time)
    if dt >= datetime.datetime.now(datetime.timezone.utc):
        return

    confirmed_flag = await _check_reacts(bot, future_session, guild_id)
    move_to_past_session(guild_id, activity_name, start_time, confirmed_flag)


def get_task(bot: IBot):
    @tasks.loop(seconds=30)
    async def check_future_sessions():
        guild_ids = get_guild_ids()

        for guild_id in guild_ids:
            future_sessions = get_future_sessions(guild_id)
            for future_session in future_sessions:
                try:
                    await _check_session(future_session, bot, guild_id)
                except discord.NotFound:
                    # A deleted proposal cannot gather reactions; finish it as unconfirmed.
                    move_to_past_session(
                        guild_id,
                        future_session.activity_name,
                        future_session.start_time,
                        False,
                    )
                except (discord.HTTPException, ValueError):
                    logger.exception(
                        "Could not check session %s in guild %s",
                        future_session.activity_name,
                        guild_id,
                    )

    @check_future_sessions.before_loop
    async def before_send_regular_message():
        await bot.wait_until_ready()

    return check_future_sessions

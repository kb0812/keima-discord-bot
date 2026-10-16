from typing import Literal

import discord

from utils.authorisation import is_activity_core_member, is_server_owner
from utils.interfaces import IActivity, IBot
from utils.persistence import get_activity

Permission = Literal["owner", "core", "owner_or_core"]


async def require_guild(interaction: discord.Interaction) -> bool:
    if interaction.guild_id is not None:
        return True
    await interaction.response.send_message(
        "this command can only be used in a server", ephemeral=True
    )
    return False


def track_guild(interaction: discord.Interaction, bot: IBot) -> int:
    guild_id = interaction.guild_id
    if guild_id not in bot.guild_ids:
        bot.guild_ids.append(guild_id)
    return guild_id


async def require_permission(
    interaction: discord.Interaction,
    bot: IBot,
    permission: Permission,
    activity_name: str = "",
) -> bool:
    if not await require_guild(interaction):
        return False
    if permission == "owner":
        allowed = is_server_owner(interaction, bot)
    elif permission == "core":
        allowed = is_activity_core_member(interaction, activity_name)
    else:
        allowed = is_server_owner(interaction, bot) or is_activity_core_member(
            interaction, activity_name
        )
    if not allowed:
        await interaction.response.send_message(
            "you do not have permission for this command", ephemeral=True
        )
    return allowed


async def validate_activity_name(
    interaction: discord.Interaction, activity_name: str, *, creating: bool = False
) -> str | None:
    activity_name = activity_name.strip()
    if not activity_name or any(character.isspace() for character in activity_name):
        message = (
            "the Activity's name must not contain whitespace"
            if creating
            else "Activity names do not contain whitespace"
        )
        await interaction.response.send_message(message, ephemeral=True)
        return None
    return activity_name


async def require_activity(
    interaction: discord.Interaction,
    bot: IBot,
    activity_name: str,
    *,
    permission: Permission | None = None,
) -> IActivity | None:
    # Preserve permission checks before validation and activity lookup.
    if permission:
        if not await require_permission(interaction, bot, permission, activity_name):
            return None
    elif not await require_guild(interaction):
        return None
    activity_name = await validate_activity_name(interaction, activity_name)
    if activity_name is None:
        return None
    guild_id = track_guild(interaction, bot)
    activity = get_activity(guild_id, activity_name)
    if activity is None:
        await interaction.response.send_message(
            "the Activity does not exist", ephemeral=True
        )
    return activity


async def send_instruction(
    interaction: discord.Interaction, command_name: str, activity_name: str, **values
):
    payload = {"activity_name": activity_name, **values}
    await interaction.response.send_message(
        f"{command_name} instruction received: \n{payload}", ephemeral=True
    )

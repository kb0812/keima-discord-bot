import discord

from utils.interfaces import IBot


def is_server_owner(interaction: discord.Interaction, bot: IBot):
    guild_id = interaction.guild_id
    member_id = interaction.user.id
    if guild_id is None:
        return False
    guild = getattr(interaction, "guild", None) or bot.get_guild(guild_id)
    return guild is not None and member_id == guild.owner_id


def is_activity_core_member(interaction: discord.Interaction, activity_name):
    guild_id = interaction.guild_id
    member_id = interaction.user.id

    if guild_id is None:
        return False

    from utils.persistence import get_activity_member_rels

    activity_member_rels = get_activity_member_rels(guild_id)

    for activity_member_rel in activity_member_rels:
        if (
            activity_name != activity_member_rel.activity_name
            or member_id != activity_member_rel.member_id
        ):
            continue
        return activity_member_rel.core_flag
    return False

import discord


class IBot(discord.Client):
    tree: discord.app_commands.CommandTree
    guild_ids: list[int]


class IActivity:
    activity_name: str
    description: str
    archived_flag: bool


class IActivityMemberRel:
    activity_name: str
    member_id: int
    core_flag: bool


class IFutureSession:
    activity_name: str
    start_time: str
    message_id: int
    channel_id: int


class IPastSession:
    activity_name: str
    start_time: str
    confirmed_flag: bool

import discord

from utils.command_helpers import require_guild, track_guild
from utils.interfaces import IBot
from utils.persistence import get_activities, get_past_sessions


def add_command_to(bot: IBot):
    @bot.tree.command(name="list_activities", description="list all Activities")
    @discord.app_commands.describe()
    async def list_activities(
        interaction: discord.Interaction,
    ):
        if not await require_guild(interaction):
            return
        guild_id = track_guild(interaction, bot)
        activities = get_activities(guild_id)

        past_sessions = [
            past_session
            for past_session in get_past_sessions(guild_id)
            if past_session.confirmed_flag
        ]
        past_sessions.sort(
            key=lambda past_session: past_session.start_time, reverse=True
        )

        def get_previous_session_time(activity_name):
            for past_session in past_sessions:
                if past_session.activity_name == activity_name:
                    return past_session.start_time
            return "never"

        response = "\n".join(
            [
                f"`{idx}`:activity_name=`{activity.activity_name}`"
                + (
                    f",description=`{activity.description}`"
                    if activity.description
                    else ""
                )
                + f",archived_flag=`{activity.archived_flag}`"
                + f",previous_session=`{get_previous_session_time(activity.activity_name)}`"
                for (idx, activity) in enumerate(activities)
            ]
        )

        await interaction.response.send_message(
            response or "no Activity exists",
            ephemeral=True,
        )

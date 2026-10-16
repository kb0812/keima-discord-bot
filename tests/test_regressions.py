from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from tasks.check_future_sessions import _check_session
from utils import persistence


async def test_latest_confirmed_session_is_listed(bot, interaction, seed):
    seed("activity", ("chess", "", "0"))
    seed(
        "past_session",
        ("chess", "2020-01-01-00:00", "1"),
        ("chess", "2022-01-01-00:00", "0"),
        ("chess", "2021-01-01-00:00", "1"),
    )

    await bot.tree.get_command("list_activities").callback(interaction)

    text = interaction.response.send_message.call_args.args[0]
    assert "previous_session=`2021-01-01-00:00`" in text


async def test_duplicate_join_preserves_core_membership(bot, interaction, seed):
    seed("activity", ("chess", "", "0"))
    seed("activity_member_rel", ("chess", 1, "1"))

    await bot.tree.get_command("join_activity").callback(interaction, "chess")

    members = persistence.get_activity_member_rels(100)
    assert len(members) == 1
    assert members[0].core_flag is True
    interaction.response.send_message.assert_awaited_once_with(
        "<@1> is already a member of the Activity", ephemeral=True
    )


@pytest.mark.parametrize("flag", ["", " ", "10", "2", "yes"])
async def test_invalid_core_flag_does_not_change_membership(
    bot, interaction, seed, flag
):
    seed("activity", ("chess", "", "0"))
    seed("activity_member_rel", ("chess", 1, "1"))

    await bot.tree.get_command("change_core_status").callback(
        interaction, "chess", interaction.user, flag
    )

    assert persistence.get_activity_member_rels(100)[0].core_flag is True
    interaction.response.send_message.assert_awaited_once_with(
        "core_flag must be 1 or 0", ephemeral=True
    )


async def test_delete_and_recreate_activity(bot, interaction, seed):
    seed("activity", ("chess", "old", "0"))
    seed("activity_member_rel", ("chess", 1, "1"), ("chess", 2, "0"))
    seed("past_session", ("chess", "2020-01-01-00:00", "1"))

    await bot.tree.get_command("delete_activity").callback(interaction, "chess")
    interaction.response.send_message.reset_mock()
    await bot.tree.get_command("create_activity").callback(interaction, "chess", "new")

    assert persistence.get_activities(100)[0].description == "new"
    members = persistence.get_activity_member_rels(100)
    assert [(m.member_id, m.core_flag) for m in members] == [(1, True)]
    assert persistence.get_past_sessions(100) == []


async def test_due_session_is_committed_once(bot, seed):
    seed("activity", ("chess", "", "0"))
    seed("activity_member_rel", ("chess", 1, "1"))
    seed("future_session", ("chess", "2000-01-01-00:00", 50, 60))

    async def users():
        for member_id in (1, 2, 999):
            yield SimpleNamespace(id=member_id)

    reaction = SimpleNamespace(emoji="👍", users=users)
    channel = SimpleNamespace(
        fetch_message=AsyncMock(return_value=SimpleNamespace(reactions=[reaction])),
        send=AsyncMock(),
    )
    bot.get_channel.return_value = channel

    for session in persistence.get_future_sessions(100):
        await _check_session(session, bot, 100)
    for session in persistence.get_future_sessions(100):
        await _check_session(session, bot, 100)

    assert persistence.get_future_sessions(100) == []
    history = persistence.get_past_sessions(100)
    assert [(s.activity_name, s.start_time, s.confirmed_flag) for s in history] == [
        ("chess", "2000-01-01-00:00", True)
    ]
    channel.send.assert_awaited_once_with(
        "<@1> <@2>\nIt is now the scheduled time for `chess`."
    )

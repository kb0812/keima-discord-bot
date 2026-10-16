from types import SimpleNamespace
from unittest.mock import AsyncMock

import discord
import pytest

from tasks import check_future_sessions
from utils import persistence


@pytest.fixture
def core_activity(seed):
    seed("activity", ("chess", "", "0"))
    seed("activity_member_rel", ("chess", 1, "1"), ("chess", 2, "0"))


@pytest.mark.parametrize(
    "start_time,message",
    [
        ("tomorrow", "start_time should be in the format [yyyy-MM-dd-HH:mm]"),
        ("2099-02-30-12:00", "invalid time: 2099-02-30-12:00"),
        ("2099-01-01-25:00", "invalid time: 2099-01-01-25:00"),
        ("2000-01-01-00:00", "start_time must be in the future"),
    ],
)
async def test_invalid_session_time(
    start_time, message, invoke, interaction, core_activity
):
    await invoke("propose_session", start_time=start_time)

    interaction.response.send_message.assert_awaited_once_with(message, ephemeral=True)
    interaction.original_response.assert_not_awaited()
    assert persistence.get_future_sessions(100) == []


async def test_propose_session_posts_public_message_and_saves_ids(
    invoke, interaction, core_activity
):
    await invoke("propose_session", start_time="[2099-01-01 12:00]")

    message = interaction.response.send_message.call_args.args[0]
    assert message.startswith("<@1> <@2>\nIf you are available for `chess`")
    assert "<t:4070952000:R>" in message
    assert interaction.response.send_message.call_args.kwargs == {}
    interaction.original_response.return_value.add_reaction.assert_awaited_once_with(
        "👍"
    )
    session = persistence.get_future_sessions(100)[0]
    assert (
        session.activity_name,
        session.start_time,
        session.message_id,
        session.channel_id,
    ) == ("chess", "2099-01-01-12:00", 50, 60)


async def test_duplicate_proposal_links_existing_message(
    invoke, interaction, core_activity, seed
):
    seed("future_session", ("chess", "2099-01-01-12:00", 50, 60))
    await invoke("propose_session")
    interaction.response.send_message.assert_awaited_once_with(
        "there is already a proposed session for the Activity: https://discord.com/channels/100/60/50",
        ephemeral=True,
    )
    assert len(persistence.get_future_sessions(100)) == 1


async def test_archived_activity_cannot_propose(invoke, interaction, core_activity):
    persistence.set_activity_archived(100, "chess", True)
    await invoke("propose_session")
    interaction.response.send_message.assert_awaited_once_with(
        "cannot propose sessions for archived Activities", ephemeral=True
    )
    assert persistence.get_future_sessions(100) == []


@pytest.mark.parametrize("command", ["propose_session", "unpropose_session"])
async def test_owner_without_core_membership_cannot_manage_sessions(
    command, invoke, interaction, seed
):
    seed("activity", ("chess", "", "0"))
    await invoke(command)
    interaction.response.send_message.assert_awaited_once_with(
        "you do not have permission for this command", ephemeral=True
    )


async def test_unpropose_session_and_missing_proposal(
    invoke, interaction, core_activity, seed
):
    seed("future_session", ("chess", "2099-01-01-12:00", 50, 60))
    await invoke("unpropose_session")
    assert persistence.get_future_sessions(100) == []
    interaction.response.send_message.assert_awaited_once_with(
        "unpropose_session instruction received: \n{'activity_name': 'chess'}",
        ephemeral=True,
    )
    interaction.response.send_message.reset_mock()
    await invoke("unpropose_session")
    interaction.response.send_message.assert_awaited_once_with(
        "there is no proposed session for the Activity", ephemeral=True
    )


def reaction(emoji, member_ids):
    async def users():
        for member_id in member_ids:
            yield SimpleNamespace(id=member_id)

    return SimpleNamespace(emoji=emoji, users=users)


@pytest.mark.parametrize(
    "reactions,confirmed",
    [
        ([], False),
        ([reaction("👎", [1])], False),
        ([reaction("👍", [2, 999])], False),
        ([reaction("👎", [1]), reaction("👍", [1, 2, 999])], True),
    ],
)
async def test_reactions_require_thumbs_up_from_every_core(
    reactions, confirmed, bot, core_activity
):
    channel = SimpleNamespace(
        fetch_message=AsyncMock(return_value=SimpleNamespace(reactions=reactions)),
        send=AsyncMock(),
    )
    bot.get_channel.return_value = None
    bot.fetch_channel.return_value = channel
    session = persistence.FutureSession(("chess", "2000-01-01-00:00", 50, 60))

    result = await check_future_sessions._check_reacts(bot, session, 100)

    assert result is confirmed
    bot.fetch_channel.assert_awaited_once_with(60)
    channel.fetch_message.assert_awaited_once_with(50)
    if confirmed:
        channel.send.assert_awaited_once_with(
            "<@1> <@2>\nIt is now the scheduled time for `chess`."
        )
    else:
        channel.send.assert_not_awaited()


async def test_session_requires_all_core_members(bot, core_activity, seed):
    seed("activity_member_rel", ("chess", 3, "1"), ("other", 4, "1"))
    channel = SimpleNamespace(
        fetch_message=AsyncMock(
            return_value=SimpleNamespace(reactions=[reaction("👍", [1, 2])])
        ),
        send=AsyncMock(),
    )
    bot.get_channel.return_value = channel
    session = persistence.FutureSession(("chess", "2000-01-01-00:00", 50, 60))
    assert await check_future_sessions._check_reacts(bot, session, 100) is False
    channel.send.assert_not_awaited()


async def test_future_session_is_not_checked_early(bot, seed):
    seed("future_session", ("chess", "2099-01-01-12:00", 50, 60))
    await check_future_sessions._check_session(
        persistence.get_future_sessions(100)[0], bot, 100
    )
    bot.get_channel.assert_not_called()
    assert len(persistence.get_future_sessions(100)) == 1
    assert persistence.get_past_sessions(100) == []


async def test_missing_reactions_finish_session_as_unconfirmed(
    bot, core_activity, seed
):
    seed("future_session", ("chess", "2000-01-01-00:00", 50, 60))
    channel = SimpleNamespace(
        fetch_message=AsyncMock(return_value=SimpleNamespace(reactions=[])),
        send=AsyncMock(),
    )
    bot.get_channel.return_value = channel

    await check_future_sessions._check_session(
        persistence.get_future_sessions(100)[0], bot, 100
    )

    assert persistence.get_future_sessions(100) == []
    assert persistence.get_past_sessions(100)[0].confirmed_flag is False
    channel.send.assert_not_awaited()


async def test_failed_reminder_send_stays_pending_and_retries_once(
    bot, core_activity, seed, caplog
):
    persistence.add_guild_id(100)
    seed("future_session", ("chess", "2000-01-01-00:00", 50, 60))
    response = SimpleNamespace(status=503, reason="Service unavailable")
    channel = SimpleNamespace(
        fetch_message=AsyncMock(
            return_value=SimpleNamespace(reactions=[reaction("👍", [1, 2, 999])])
        ),
        send=AsyncMock(
            side_effect=[discord.HTTPException(response, "try later"), None]
        ),
    )
    bot.get_channel.return_value = channel
    loop = check_future_sessions.get_task(bot)

    await loop.coro()

    assert len(persistence.get_future_sessions(100)) == 1
    assert persistence.get_past_sessions(100) == []
    assert "Could not check session chess" in caplog.text

    await loop.coro()
    await loop.coro()

    assert persistence.get_future_sessions(100) == []
    history = persistence.get_past_sessions(100)
    assert len(history) == 1
    assert history[0].confirmed_flag is True
    assert channel.send.await_count == 2


@pytest.mark.parametrize("failure", ["deleted", "forbidden", "malformed"])
async def test_poll_continues_after_one_session_fails(failure, bot, seed, caplog):
    persistence.add_guild_id(100)
    seed(
        "future_session",
        ("broken", "2000-01-01-00:00" if failure != "malformed" else "bad", 50, 60),
        ("healthy", "2000-01-01-00:00", 51, 60),
    )
    response = SimpleNamespace(
        status=404 if failure == "deleted" else 403, reason="failure"
    )
    error = (
        discord.NotFound(response, "deleted")
        if failure == "deleted"
        else discord.Forbidden(response, "forbidden")
    )
    channel = SimpleNamespace(
        fetch_message=AsyncMock(
            side_effect=[SimpleNamespace(reactions=[])]
            if failure == "malformed"
            else [error, SimpleNamespace(reactions=[])]
        ),
        send=AsyncMock(),
    )
    bot.get_channel.return_value = channel

    await check_future_sessions.get_task(bot).coro()

    assert "healthy" in [s.activity_name for s in persistence.get_past_sessions(100)]
    if failure == "deleted":
        assert persistence.get_future_sessions(100) == []
    else:
        assert [s.activity_name for s in persistence.get_future_sessions(100)] == [
            "broken"
        ]
        assert "Could not check session broken" in caplog.text

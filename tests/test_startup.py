import importlib
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import discord
import pytest

from tasks import add_new_guild_ids
from utils import authorisation, persistence
from utils.tasks import get_tasks


def test_import_main_does_not_require_token_or_start_bot(monkeypatch):
    monkeypatch.delenv("DISCORD_TOKEN", raising=False)
    run = Mock(side_effect=AssertionError("import must not connect to Discord"))
    monkeypatch.setattr(discord.Client, "run", run)
    import main

    importlib.reload(main)

    run.assert_not_called()
    assert list(persistence.DATA_DIR.iterdir()) == []


def test_missing_token_fails_at_startup(monkeypatch):
    import main

    monkeypatch.delenv("DISCORD_TOKEN", raising=False)
    monkeypatch.setattr(main, "load_dotenv", Mock())
    with pytest.raises(RuntimeError, match="DISCORD_TOKEN is missing"):
        main.main()


async def test_setup_registers_commands_and_starts_tasks(monkeypatch):
    import main
    import utils.tasks
    from utils.commands import add_commands_to

    background_tasks = [Mock(), Mock()]
    monkeypatch.setattr(utils.tasks, "get_tasks", Mock(return_value=background_tasks))
    async with main.Bot() as bot:
        add_commands_to(bot)
        bot.tree.sync = AsyncMock()

        await bot.setup_hook()

        assert len(bot.tree.get_commands()) == 14
        bot.tree.sync.assert_awaited_once_with()
        for task in background_tasks:
            task.start.assert_called_once_with()


async def test_entry_point_runs_with_token_and_sets_presence(monkeypatch):
    import main

    registered_events = {}

    def event(function):
        registered_events[function.__name__] = function
        return function

    bot = SimpleNamespace(
        event=event, run=Mock(), change_presence=AsyncMock(), user="Keima"
    )
    monkeypatch.setattr(main, "Bot", Mock(return_value=bot))
    monkeypatch.setattr(main, "load_dotenv", Mock())
    monkeypatch.setenv("DISCORD_TOKEN", "test-token")
    register = Mock()
    monkeypatch.setattr("utils.commands.add_commands_to", register)

    main.main()

    register.assert_called_once_with(bot)
    bot.run.assert_called_once_with("test-token")
    assert "on_ready" in registered_events
    await registered_events["on_ready"]()
    presence = bot.change_presence.call_args.kwargs
    assert presence["status"] == discord.Status.online
    assert presence["activity"].type == discord.ActivityType.watching


async def test_task_discovery_and_guild_registry_loop(bot):
    bot.wait_until_ready = AsyncMock()
    loops = get_tasks(bot)
    assert {loop.coro.__name__ for loop in loops} == {
        "add_new_guild_ids",
        "check_future_sessions",
    }
    bot.guild_ids = [100, 200]
    persistence.add_guild_id(100)

    await add_new_guild_ids.get_task(bot).coro()
    await add_new_guild_ids.get_task(bot).coro()

    assert persistence.get_guild_ids() == [100, 200]


def test_authorisation_handles_guild_and_core_membership(bot, interaction, seed):
    assert authorisation.is_server_owner(interaction, bot) is True
    interaction.user.id = 2
    assert authorisation.is_server_owner(interaction, bot) is False
    interaction.guild = SimpleNamespace(owner_id=2)
    bot.get_guild.return_value = None
    assert authorisation.is_server_owner(interaction, bot) is True
    seed("activity_member_rel", ("chess", 2, "1"), ("other", 2, "0"))
    assert authorisation.is_activity_core_member(interaction, "chess") is True
    assert authorisation.is_activity_core_member(interaction, "other") is False
    assert authorisation.is_activity_core_member(interaction, "missing") is False
    interaction.guild_id = None
    assert authorisation.is_server_owner(interaction, bot) is False
    assert authorisation.is_activity_core_member(interaction, "chess") is False

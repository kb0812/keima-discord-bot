from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import discord
import pytest
import pytest_asyncio

from utils import persistence
from utils.commands import add_commands_to


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    monkeypatch.setattr(persistence, "DATA_DIR", tmp_path)


@pytest_asyncio.fixture
async def bot():
    async with discord.Client(intents=discord.Intents.default()) as client:
        bot = SimpleNamespace(
            tree=discord.app_commands.CommandTree(client),
            guild_ids=[],
            get_guild=Mock(return_value=SimpleNamespace(owner_id=1)),
            get_channel=Mock(),
            fetch_channel=AsyncMock(),
            user=SimpleNamespace(id=999),
        )
        add_commands_to(bot)
        yield bot


@pytest.fixture
def interaction():
    message = SimpleNamespace(
        id=50, channel=SimpleNamespace(id=60), add_reaction=AsyncMock()
    )
    return SimpleNamespace(
        guild_id=100,
        user=SimpleNamespace(id=1, mention="<@1>"),
        response=SimpleNamespace(send_message=AsyncMock()),
        original_response=AsyncMock(return_value=message),
    )


@pytest.fixture
def invoke(bot, interaction):
    async def call(name, **overrides):
        command = bot.tree.get_command(name)
        values = {
            "activity_name": "chess",
            "member": SimpleNamespace(id=2, mention="<@2>"),
            "core_flag": "1",
            "start_time": "2099-01-01-12:00",
        }
        values.update(overrides)
        arguments = {
            parameter.name: values[parameter.name]
            for parameter in command.parameters
            if parameter.required or parameter.name in overrides
        }
        await command.callback(interaction, **arguments)

    return call


@pytest.fixture
def seed():
    def insert(table, *rows, guild_id=100):
        connection = persistence.get_connection(guild_id)
        try:
            placeholders = ", ".join("?" for _ in rows[0])
            connection.executemany(f"INSERT INTO {table} VALUES ({placeholders})", rows)
            connection.commit()
        finally:
            connection.close()

    return insert

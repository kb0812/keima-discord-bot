from unittest.mock import Mock

import pytest

from utils import persistence

OWNER_COMMANDS = (
    "create_activity",
    "delete_activity",
    "archive_activity",
    "unarchive_activity",
    "add_to_activity",
    "remove_from_activity",
    "change_core_status",
)
CORE_COMMANDS = ("propose_session", "unpropose_session")
COMMANDS = (
    *OWNER_COMMANDS,
    *CORE_COMMANDS,
    "change_description",
    "list_activities",
    "list_members",
    "join_activity",
    "leave_activity",
)
EXISTING_COMMANDS = tuple(
    c for c in COMMANDS if c not in ("create_activity", "list_activities")
)


async def test_slash_command_schema_is_preserved(bot):
    assert {command.name for command in bot.tree.get_commands()} == set(COMMANDS)
    for command in bot.tree.get_commands():
        expected = (
            [] if command.name == "list_activities" else [("activity_name", True, 3)]
        )
        if command.name in ("create_activity", "change_description"):
            expected.append(("description", False, 3))
            assert command.parameters[-1].default == ""
        if command.name in (
            "add_to_activity",
            "remove_from_activity",
            "change_core_status",
        ):
            expected.append(("member", True, 6))
        if command.name == "change_core_status":
            expected.append(("core_flag", True, 3))
        if command.name == "propose_session":
            expected.append(("start_time", True, 3))
        assert [
            (p.name, p.required, p.type.value) for p in command.parameters
        ] == expected


@pytest.mark.parametrize("command", COMMANDS)
async def test_commands_reject_dms_without_creating_database(
    command, invoke, interaction
):
    interaction.guild_id = None

    await invoke(command)

    interaction.response.send_message.assert_awaited_once_with(
        "this command can only be used in a server", ephemeral=True
    )
    assert list(persistence.DATA_DIR.iterdir()) == []


@pytest.mark.parametrize("command", OWNER_COMMANDS)
async def test_owner_permission_precedes_validation_and_database(
    command, invoke, interaction, bot
):
    interaction.user.id = 3

    await invoke(command, activity_name="invalid name")

    interaction.response.send_message.assert_awaited_once_with(
        "you do not have permission for this command", ephemeral=True
    )
    assert bot.guild_ids == []
    assert list(persistence.DATA_DIR.iterdir()) == []


@pytest.mark.parametrize("command", (*CORE_COMMANDS, "change_description"))
async def test_regular_members_cannot_manage_activity(
    command, invoke, interaction, seed
):
    seed("activity", ("chess", "original", "0"))
    seed("activity_member_rel", ("chess", 3, "0"))
    interaction.user.id = 3

    await invoke(command)

    interaction.response.send_message.assert_awaited_once_with(
        "you do not have permission for this command", ephemeral=True
    )
    assert persistence.get_activities(100)[0].description == "original"
    assert persistence.get_future_sessions(100) == []


@pytest.mark.parametrize("command", EXISTING_COMMANDS)
async def test_unknown_activity_has_one_ephemeral_response(
    command, invoke, interaction, seed
):
    # Existing orphan membership makes the core-only commands reach activity lookup.
    seed("activity_member_rel", ("chess", 1, "1"))

    await invoke(command)

    interaction.response.send_message.assert_awaited_once_with(
        "the Activity does not exist", ephemeral=True
    )
    assert persistence.get_activities(100) == []
    assert persistence.get_future_sessions(100) == []


@pytest.mark.parametrize("name", ["bad name", "bad\tname", "bad\nname", "", "  "])
async def test_invalid_activity_names_are_rejected(invoke, interaction, name):
    await invoke("create_activity", activity_name=name)

    interaction.response.send_message.assert_awaited_once_with(
        "the Activity's name must not contain whitespace", ephemeral=True
    )
    assert list(persistence.DATA_DIR.iterdir()) == []


@pytest.mark.parametrize("name", ["bad name", "bad\tname", "bad\nname", "", "  "])
async def test_existing_activity_validation_rejects_invalid_names(
    invoke, interaction, name
):
    await invoke("join_activity", activity_name=name)
    interaction.response.send_message.assert_awaited_once_with(
        "Activity names do not contain whitespace", ephemeral=True
    )
    assert list(persistence.DATA_DIR.iterdir()) == []


async def test_create_normalises_name_and_assigns_creator_core(
    invoke, interaction, bot
):
    await invoke("create_activity", activity_name=" chess ", description="Play chess")

    activity = persistence.get_activity(100, "chess")
    assert (activity.description, activity.archived_flag) == ("Play chess", False)
    member = persistence.get_activity_member_rels(100)[0]
    assert (member.activity_name, member.member_id, member.core_flag) == (
        "chess",
        1,
        True,
    )
    interaction.response.send_message.assert_awaited_once_with(
        "create_activity instruction received: \n{'activity_name': 'chess', 'description': 'Play chess'}",
        ephemeral=True,
    )
    await invoke("list_activities")
    assert bot.guild_ids == [100]


async def test_duplicate_creation_preserves_existing_activity(
    invoke, interaction, seed
):
    seed("activity", ("chess", "original", "0"))

    await invoke("create_activity", description="replacement")

    assert persistence.get_activity(100, "chess").description == "original"
    assert persistence.get_activity_member_rels(100) == []
    interaction.response.send_message.assert_awaited_once_with(
        "the Activity already exists", ephemeral=True
    )


@pytest.mark.parametrize("command", ["delete_activity", "archive_activity"])
async def test_proposed_session_blocks_delete_and_archive(
    command, invoke, interaction, seed
):
    seed("activity", ("chess", "", "0"))
    seed("future_session", ("chess", "2099-01-01-12:00", 50, 60))

    await invoke(command)

    verb = command.split("_")[0]
    interaction.response.send_message.assert_awaited_once_with(
        f"cannot {verb} an Activity that has a proposed session", ephemeral=True
    )
    assert persistence.get_activity(100, "chess").archived_flag is False
    assert len(persistence.get_future_sessions(100)) == 1


async def test_archive_and_unarchive_transitions_and_unchanged_states(
    invoke, interaction, seed
):
    seed("activity", ("chess", "", "0"))
    await invoke("archive_activity", activity_name=" chess ")
    assert persistence.get_activity(100, "chess").archived_flag is True
    interaction.response.send_message.reset_mock()
    await invoke("archive_activity")
    interaction.response.send_message.assert_awaited_once_with(
        "the Activity is already archived", ephemeral=True
    )
    await invoke("unarchive_activity")
    assert persistence.get_activity(100, "chess").archived_flag is False
    interaction.response.send_message.reset_mock()
    await invoke("unarchive_activity")
    interaction.response.send_message.assert_awaited_once_with(
        "the Activity is not archived", ephemeral=True
    )


@pytest.mark.parametrize("member_id", [1, 3])
async def test_owner_or_core_can_change_description(
    member_id, invoke, interaction, seed
):
    seed("activity", ("chess", "old", "0"))
    seed("activity_member_rel", ("chess", 3, "1"))
    interaction.user.id = member_id

    await invoke("change_description", description="new")

    assert persistence.get_activity(100, "chess").description == "new"
    assert interaction.response.send_message.await_count == 1
    assert interaction.response.send_message.call_args.kwargs == {"ephemeral": True}


async def test_membership_commands_use_target_or_caller(invoke, interaction, seed):
    seed("activity", ("chess", "", "0"))
    await invoke("add_to_activity")
    await invoke("join_activity")
    assert {m.member_id for m in persistence.get_activity_member_rels(100)} == {1, 2}
    await invoke("remove_from_activity")
    assert [m.member_id for m in persistence.get_activity_member_rels(100)] == [1]
    await invoke("leave_activity")
    assert persistence.get_activity_member_rels(100) == []


@pytest.mark.parametrize(
    "command,member_id", [("remove_from_activity", 2), ("leave_activity", 1)]
)
async def test_remove_absent_member(command, member_id, invoke, interaction, seed):
    seed("activity", ("chess", "", "0"))

    await invoke(command)

    interaction.response.send_message.assert_awaited_once_with(
        f"<@{member_id}> was not a member of the Activity", ephemeral=True
    )


async def test_duplicate_add_preserves_core_membership(invoke, interaction, seed):
    seed("activity", ("chess", "", "0"))
    seed("activity_member_rel", ("chess", 2, "1"))
    await invoke("add_to_activity")
    assert persistence.get_activity_member_rels(100)[0].core_flag is True
    interaction.response.send_message.assert_awaited_once_with(
        "<@2> is already a member of the Activity", ephemeral=True
    )


async def test_core_status_transitions_and_unchanged_flag(invoke, interaction, seed):
    seed("activity", ("chess", "", "0"))
    seed("activity_member_rel", ("chess", 2, "0"))
    await invoke("change_core_status", core_flag=" 1 ")
    assert persistence.get_activity_member_rels(100)[0].core_flag is True
    interaction.response.send_message.reset_mock()
    await invoke("change_core_status", core_flag="1")
    interaction.response.send_message.assert_awaited_once_with(
        "command failed: the specified value of core_flag is already the current value",
        ephemeral=True,
    )
    await invoke("change_core_status", core_flag="0")
    assert persistence.get_activity_member_rels(100)[0].core_flag is False


async def test_core_status_rejects_absent_member(invoke, interaction, seed):
    seed("activity", ("chess", "", "0"))
    await invoke("change_core_status")
    interaction.response.send_message.assert_awaited_once_with(
        "<@2> is not a member of the Activity", ephemeral=True
    )


async def test_member_listing_filters_activity(invoke, interaction, seed):
    seed("activity", ("chess", "", "0"))
    seed("activity_member_rel", ("chess", 1, "1"), ("other", 2, "0"))
    await invoke("list_members")
    interaction.response.send_message.assert_awaited_once_with(
        "`0`:member=<@1>,core_flag=`True`", ephemeral=True
    )


@pytest.mark.parametrize(
    "command,expected",
    [
        ("list_activities", "no Activity exists"),
        ("list_members", "the Activity has no members"),
    ],
)
async def test_empty_list_messages(command, expected, invoke, interaction, seed):
    if command == "list_members":
        seed("activity", ("chess", "", "0"))
    await invoke(command)
    interaction.response.send_message.assert_awaited_once_with(expected, ephemeral=True)


async def test_missing_guild_cache_denies_owner_without_crash(bot, invoke, interaction):
    bot.get_guild = Mock(return_value=None)
    await invoke("create_activity")
    interaction.response.send_message.assert_awaited_once_with(
        "you do not have permission for this command", ephemeral=True
    )
    assert list(persistence.DATA_DIR.iterdir()) == []

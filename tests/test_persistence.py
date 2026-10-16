import sqlite3

import pytest

from utils import persistence


def install_trigger(sql):
    connection = persistence.get_connection(100)
    try:
        connection.execute(sql)
        connection.commit()
    finally:
        connection.close()


def test_create_activity_rolls_back_if_creator_membership_fails():
    install_trigger("""
        CREATE TRIGGER reject_member BEFORE INSERT ON activity_member_rel
        BEGIN SELECT RAISE(ABORT, 'membership failed'); END
    """)

    with pytest.raises(sqlite3.IntegrityError, match="membership failed"):
        persistence.create_activity(100, "chess", "description", 1)

    assert persistence.get_activities(100) == []
    assert persistence.get_activity_member_rels(100) == []
    # A new writer can immediately acquire a transaction after the exception.
    persistence.create_activity(200, "other", "", 1)
    assert persistence.get_activity(200, "other") is not None


def test_session_history_rolls_back_if_insert_fails(seed):
    seed("future_session", ("chess", "2000-01-01-00:00", 50, 60))
    install_trigger("""
        CREATE TRIGGER reject_history BEFORE INSERT ON past_session
        BEGIN SELECT RAISE(ABORT, 'history failed'); END
    """)

    with pytest.raises(sqlite3.IntegrityError, match="history failed"):
        persistence.move_to_past_session(100, "chess", "2000-01-01-00:00", True)

    assert len(persistence.get_future_sessions(100)) == 1
    assert persistence.get_past_sessions(100) == []


def test_delete_rolls_back_related_rows_on_failure(seed):
    seed("activity", ("chess", "", "0"))
    seed("activity_member_rel", ("chess", 1, "1"))
    seed("past_session", ("chess", "2000-01-01-00:00", "1"))
    install_trigger("""
        CREATE TRIGGER reject_delete BEFORE DELETE ON activity
        BEGIN SELECT RAISE(ABORT, 'delete failed'); END
    """)

    with pytest.raises(sqlite3.IntegrityError, match="delete failed"):
        persistence.delete_activity(100, "chess")

    assert persistence.get_activity(100, "chess") is not None
    assert len(persistence.get_activity_member_rels(100)) == 1
    assert len(persistence.get_past_sessions(100)) == 1


def test_session_move_is_idempotent_and_preserves_replacement(seed):
    seed("future_session", ("chess", "2000-01-01-00:00", 50, 60))
    assert (
        persistence.move_to_past_session(100, "chess", "2000-01-01-00:00", False) == 1
    )
    assert persistence.move_to_past_session(100, "chess", "2000-01-01-00:00", True) == 0
    history = persistence.get_past_sessions(100)
    assert len(history) == 1
    assert history[0].confirmed_flag is False

    persistence.add_future_session(100, "chess", "2099-01-01-00:00", 51, 60)
    assert persistence.move_to_past_session(100, "chess", "2000-01-01-00:00", True) == 0
    assert persistence.get_future_sessions(100)[0].start_time == "2099-01-01-00:00"


def test_guild_databases_are_isolated():
    persistence.create_activity(100, "chess", "first", 1)
    persistence.create_activity(200, "chess", "second", 2)
    persistence.delete_activity(100, "chess")

    assert persistence.get_activities(100) == []
    assert persistence.get_activity(200, "chess").description == "second"
    assert persistence.get_activity_member_rels(200)[0].member_id == 2


def test_registry_is_durable_and_idempotent():
    persistence.add_guild_id(100)
    persistence.add_guild_id(100)
    persistence.add_guild_id(200)
    assert persistence.get_guild_ids() == [100, 200]


def test_membership_and_session_deletions_return_affected_count():
    assert persistence.remove_activity_member_rel(100, "chess", 1) == 0
    assert persistence.add_activity_member_rel(100, "chess", 1, "1") == 1
    assert persistence.add_activity_member_rel(100, "chess", 1) == 0
    assert persistence.get_activity_member_rels(100)[0].core_flag is True
    assert persistence.remove_activity_member_rel(100, "chess", 1) == 1
    assert persistence.remove_future_session(100, "chess") == 0
    persistence.add_future_session(100, "chess", "2099-01-01-00:00", 50, 60)
    assert persistence.remove_future_session(100, "chess") == 1


def test_database_connections_close_on_success_and_failure(monkeypatch):
    connections = []

    class TrackedConnection(sqlite3.Connection):
        closed = False

        def close(self):
            self.closed = True
            super().close()

    connect = sqlite3.connect

    def tracked_connect(path):
        connection = connect(path, factory=TrackedConnection)
        connections.append(connection)
        return connection

    monkeypatch.setattr(persistence.sqlite3, "connect", tracked_connect)
    persistence.create_activity(100, "chess", "", 1)
    persistence.get_activities(100)
    persistence.add_guild_id(100)
    with pytest.raises(sqlite3.IntegrityError):
        persistence.create_activity(100, "chess", "", 1)
    assert len(connections) == 4
    assert all(connection.closed for connection in connections)

import sqlite3
from contextlib import closing, contextmanager
from pathlib import Path

from utils.interfaces import IActivity, IActivityMemberRel, IFutureSession, IPastSession

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@contextmanager
def _database(guild_id=None):
    """Commit successful operations, roll back failures, and always close."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if guild_id is None:
        connection = sqlite3.connect(DATA_DIR / "db.db")
    else:
        connection = get_connection(guild_id)
    with closing(connection), connection:
        if guild_id is None:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS guild (guild_id INTEGER PRIMARY KEY)"
            )
        yield connection


def get_guild_ids():
    with _database() as connection:
        return [row[0] for row in connection.execute("SELECT guild_id FROM guild")]


def add_guild_id(guild_id):
    with _database() as connection:
        connection.execute("INSERT OR IGNORE INTO guild VALUES (?)", (guild_id,))


class Activity(IActivity):
    def __init__(self, row: tuple[str, str, str]):
        self.activity_name, self.description, _archived_flag = row
        self.archived_flag = _archived_flag == "1"


class ActivityMemberRel(IActivityMemberRel):
    def __init__(self, row: tuple[str, int, str]):
        self.activity_name, self.member_id, _core_flag = row
        self.core_flag = _core_flag == "1"


class FutureSession(IFutureSession):
    def __init__(self, row: tuple[str, str, int, int]):
        self.activity_name, self.start_time, self.message_id, self.channel_id = row


class PastSession(IPastSession):
    def __init__(self, row: tuple[str, str, str]):
        self.activity_name, self.start_time, _confirmed_flag = row
        self.confirmed_flag = _confirmed_flag == "1"


def create_tables_if_not_exist(connection):
    connection.execute("""
        CREATE TABLE IF NOT EXISTS activity (
            activity_name TEXT PRIMARY KEY,
            description TEXT,
            archived_flag TEXT
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS activity_member_rel (
            activity_name TEXT,
            member_id INTEGER,
            core_flag TEXT,
            UNIQUE ( activity_name, member_id )
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS future_session (
            activity_name TEXT PRIMARY KEY,
            start_time TEXT,
            message_id INTEGER,
            channel_id INTEGER
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS past_session (
            activity_name TEXT,
            start_time TEXT,
            confirmed_flag TEXT
        )
    """)


def get_connection(guild_id):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATA_DIR / f"guild_{guild_id}.db")
    try:
        create_tables_if_not_exist(connection)
    except Exception:
        connection.close()
        raise
    return connection


def _fetch(guild_id, query, model, parameters=()):
    with _database(guild_id) as connection:
        return [model(row) for row in connection.execute(query, parameters)]


def _execute(guild_id, query, parameters=()):
    with _database(guild_id) as connection:
        return connection.execute(query, parameters).rowcount


def get_activities(guild_id):
    return _fetch(guild_id, "SELECT * FROM activity", Activity)


def get_activity(guild_id, activity_name):
    activities = _fetch(
        guild_id,
        "SELECT * FROM activity WHERE activity_name=?",
        Activity,
        (activity_name,),
    )
    return next(iter(activities), None)


def get_activity_member_rels(guild_id):
    return _fetch(guild_id, "SELECT * FROM activity_member_rel", ActivityMemberRel)


def get_future_sessions(guild_id):
    return _fetch(guild_id, "SELECT * FROM future_session", FutureSession)


def get_past_sessions(guild_id):
    return _fetch(guild_id, "SELECT * FROM past_session", PastSession)


def create_activity(guild_id, activity_name, description, creator_id):
    with _database(guild_id) as connection:
        connection.execute(
            "INSERT INTO activity VALUES (?, ?, '0')", (activity_name, description)
        )
        connection.execute(
            "INSERT INTO activity_member_rel VALUES (?, ?, '1')",
            (activity_name, creator_id),
        )


def delete_activity(guild_id, activity_name):
    with _database(guild_id) as connection:
        connection.execute(
            "DELETE FROM activity_member_rel WHERE activity_name=?", (activity_name,)
        )
        connection.execute(
            "DELETE FROM future_session WHERE activity_name=?", (activity_name,)
        )
        connection.execute(
            "DELETE FROM past_session WHERE activity_name=?", (activity_name,)
        )
        connection.execute(
            "DELETE FROM activity WHERE activity_name=?", (activity_name,)
        )


def set_activity_archived(guild_id, activity_name, archived):
    _execute(
        guild_id,
        "UPDATE activity SET archived_flag=? WHERE activity_name=?",
        (str(int(archived)), activity_name),
    )


def change_description(guild_id, activity_name, description):
    _execute(
        guild_id,
        "UPDATE activity SET description=? WHERE activity_name=?",
        (description, activity_name),
    )


def change_core_status(guild_id, activity_name, member_id, core_flag):
    _execute(
        guild_id,
        "UPDATE activity_member_rel SET core_flag=? WHERE activity_name=? AND member_id=?",
        (str(int(core_flag)), activity_name, member_id),
    )


def add_activity_member_rel(guild_id, activity_name, member_id, core_flag="0"):
    return _execute(
        guild_id,
        "INSERT INTO activity_member_rel VALUES (?, ?, ?) ON CONFLICT(activity_name, member_id) DO NOTHING",
        (activity_name, member_id, core_flag),
    )


def remove_activity_member_rel(guild_id, activity_name, member_id):
    return _execute(
        guild_id,
        "DELETE FROM activity_member_rel WHERE activity_name=? AND member_id=?",
        (activity_name, member_id),
    )


def add_future_session(guild_id, activity_name, start_time, message_id, channel_id):
    _execute(
        guild_id,
        "INSERT INTO future_session VALUES (?, ?, ?, ?)",
        (activity_name, start_time, message_id, channel_id),
    )


def remove_future_session(guild_id, activity_name):
    return _execute(
        guild_id, "DELETE FROM future_session WHERE activity_name=?", (activity_name,)
    )


def move_to_past_session(guild_id, activity_name, start_time, confirmed_flag):
    with _database(guild_id) as connection:
        deleted = connection.execute(
            "DELETE FROM future_session WHERE activity_name=? AND start_time=?",
            (activity_name, start_time),
        ).rowcount
        if deleted:
            connection.execute(
                "INSERT INTO past_session VALUES (?, ?, ?)",
                (activity_name, start_time, str(int(confirmed_flag))),
            )
        return deleted
